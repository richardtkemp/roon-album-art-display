"""Centralized render coordinator with a two-stage prepare → render pipeline."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, Tuple, TypeVar

from PIL import Image

from .exceptions import RenderCancelledError

if TYPE_CHECKING:
    from .config.config_manager import ConfigManager
    from .image_processing.processor import ImageProcessor
    from .message_renderer import MessageRenderer

logger = logging.getLogger(__name__)

T = TypeVar("T")


class LatestSlot(Generic[T]):
    """Thread-safe single-slot mailbox. Always holds the latest value.

    ``set()`` always overwrites. ``wait_and_take()`` blocks until a value is
    available, then returns and clears the slot. The generation counter lets
    callers detect whether a newer item has arrived since they took their item.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._value: Optional[T] = None
        self._generation: int = 0

    def set(self, value: T) -> None:
        """Overwrite the slot and increment the generation counter."""
        with self._cond:
            self._generation += 1
            value.generation = self._generation  # type: ignore[attr-defined]
            self._value = value
            self._cond.notify_all()

    def wait_and_take(self) -> T:
        """Block until a value is available, then return and clear it."""
        with self._cond:
            while self._value is None:
                self._cond.wait()
            value = self._value
            self._value = None
            return value

    def try_take(self) -> Optional[T]:
        """Non-blocking take. Returns None if slot is empty."""
        with self._lock:
            value = self._value
            self._value = None
            return value

    def is_current(self, generation: int) -> bool:
        """Return True if no newer item has arrived since this generation."""
        with self._lock:
            return self._generation == generation


@dataclass
class RenderTarget:
    """A request to render a particular piece of content."""

    content_type: str
    image_key: Optional[str]
    image_path: Optional[Path]
    img: Optional[Image.Image]
    track_info: Optional[str]
    force: bool = False
    generation: int = 0
    queued_at: float = field(default_factory=time.time)


@dataclass
class PreparedItem:
    """A fully processed, display-ready image paired with its source target."""

    target: RenderTarget
    image: Image.Image


class RenderCoordinator:
    """Coordinates rendering with a two-stage prepare → render pipeline.

    Stage 1 (prepare-loop): takes incoming RenderTargets, runs
    ``image_processor.prepare()`` to produce a display-ready image, and emits
    PreparedItems.  Stale targets (superseded before prepare completes) are
    silently discarded.

    Stage 2 (render-loop): takes PreparedItems and calls ``viewer.render()``,
    which blocks until the hardware finishes.  Stale prepared items are
    discarded; the dedup check skips re-renders of the same image unless an
    overlay changed or ``force=True`` was requested.
    """

    def __init__(
        self,
        viewer: Any,
        image_processor: "ImageProcessor",
        message_renderer: "MessageRenderer",
        config_manager: "ConfigManager",
        anniversary_manager: Any = None,
    ) -> None:
        self._viewer = viewer
        self.image_processor = image_processor
        self.message_renderer = message_renderer
        self.config_manager = config_manager
        self.anniversary_manager = anniversary_manager

        # Pipeline slots
        self._incoming: LatestSlot[RenderTarget] = LatestSlot()
        self._prepared: LatestSlot[PreparedItem] = LatestSlot()
        self._render_trigger: threading.Event = threading.Event()

        # Overlay state
        self._overlay_lock: threading.Lock = threading.Lock()
        self._overlay: Optional[str] = None
        self._overlay_timeout: Optional[float] = None

        # Display state
        self._current_key: Optional[str] = None
        self._last_rendered_target: Optional[RenderTarget] = None

        # Image caching for web access
        self.last_rendered_image: Optional[Image.Image] = None
        self.last_render_metadata: Dict[str, Any] = {}

        logger.info("RenderCoordinator initialized")

        # Initialise e-ink persistence (reads last-displayed key from disk)
        self._initialize_current_display_state()

        # Start pipeline workers
        threading.Thread(
            target=self._prepare_loop, daemon=True, name="prepare-loop"
        ).start()
        threading.Thread(
            target=self._render_loop, daemon=True, name="render-loop"
        ).start()

        # Start anniversary monitor if enabled
        if self.anniversary_manager:
            self.anniversary_manager.start_anniversary_monitor(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_art(
        self,
        content_type: str,
        image_key: Optional[str] = None,
        image_path: Optional[Path] = None,
        img: Optional[Image.Image] = None,
        track_info: Optional[str] = None,
        force: bool = False,
        **kwargs: Any,
    ) -> None:
        """Queue a render target. Returns immediately."""
        logger.info(f"Queuing render target: {content_type}")
        target = RenderTarget(
            content_type=content_type,
            image_key=image_key,
            image_path=image_path,
            img=img,
            track_info=track_info,
            force=force,
        )
        if content_type == "art" and self.anniversary_manager:
            self.anniversary_manager.update_last_track_time()
        self._incoming.set(target)
        if self.config_manager.get_interrupt_on_skip():
            self._viewer.cancel()

    def set_main_content(
        self,
        content_type: str,
        image_key: Optional[str] = None,
        image_path: Optional[Path] = None,
        img: Optional[Image.Image] = None,
        track_info: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Deprecated alias for set_art()."""
        self.set_art(
            content_type=content_type,
            image_key=image_key,
            image_path=image_path,
            img=img,
            track_info=track_info,
            **kwargs,
        )

    def set_overlay(self, message: str, timeout: Optional[float] = None) -> None:
        """Set an overlay message for bottom-right display."""
        logger.warning(f"Setting overlay: {message}")
        with self._overlay_lock:
            self._overlay = message
            self._overlay_timeout = time.time() + timeout if timeout else None
        self._render_trigger.set()

    def clear_overlay(self) -> None:
        """Clear the overlay."""
        with self._overlay_lock:
            if self._overlay is not None:
                logger.info("Clearing overlay")
                self._overlay = None
                self._overlay_timeout = None
        self._render_trigger.set()

    def force_refresh(self) -> None:
        """Re-render current content with the current config (e.g. after settings change)."""
        logger.info("Force refresh triggered")
        if self._last_rendered_target is not None:
            t = self._last_rendered_target
            target = RenderTarget(
                content_type=t.content_type,
                image_key=t.image_key,
                image_path=t.image_path,
                img=t.img,
                track_info=t.track_info,
                force=True,
            )
            self._incoming.set(target)

    def get_current_rendered_image(
        self,
    ) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
        """Return the last rendered image and metadata (for web UI)."""
        return self.last_rendered_image, self.last_render_metadata.copy()

    def render_preview(self, config_data: Dict[str, Any]) -> Optional[Image.Image]:
        """Generate a preview image with temporary config overrides."""
        try:
            config_diff = self.config_manager.get_config_diff(config_data)
            if config_diff:
                changes = [
                    f"{k}: {d['old']} → {d['new']}" for k, d in config_diff.items()
                ]
                logger.info(f"Generating preview with changes: {', '.join(changes)}")
            else:
                logger.info("Generating preview with no config changes")

            if self._last_rendered_target is None:
                logger.warning("No content available for preview")
                return None

            return self.image_processor.prepare(
                self._last_rendered_target.img,
                self._last_rendered_target.image_path,
                overrides=config_data,
            )
        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            return None

    # ------------------------------------------------------------------
    # Backward-compat shims (called by BaseViewer._notify_render_complete)
    # ------------------------------------------------------------------

    def set_current_display_image_key(self, image_key: str) -> None:
        """No-op: render loop updates _current_key directly after each render."""
        pass

    # ------------------------------------------------------------------
    # Pipeline workers
    # ------------------------------------------------------------------

    def _prepare_loop(self) -> None:
        """Stage-1 worker: prepare images for rendering."""
        while True:
            target = self._incoming.wait_and_take()
            try:
                image = self.image_processor.prepare(target.img, target.image_path)
            except Exception as e:
                logger.error(f"Error preparing image: {e}")
                continue
            if image is None:
                logger.error("image_processor.prepare() returned None")
                continue
            if not self._incoming.is_current(target.generation):
                logger.debug(f"Discarding stale prepared item gen={target.generation}")
                continue
            self._prepared.set(PreparedItem(target=target, image=image))
            self._render_trigger.set()

    def _render_loop(self) -> None:
        """Stage-2 worker: render prepared images to the display."""
        _last_prepared: Optional[PreparedItem] = None
        _rendered_overlay: Optional[str] = None

        while True:
            self._render_trigger.wait()
            self._render_trigger.clear()

            # Absorb the latest prepared item if one arrived
            new_item = self._prepared.try_take()
            if new_item is not None:
                if (
                    self._incoming.is_current(new_item.target.generation)
                    or new_item.target.force
                ):
                    _last_prepared = new_item
                else:
                    logger.debug("Discarding stale prepared item in render loop")

            # Check overlay timeout
            with self._overlay_lock:
                if self._overlay_timeout and time.time() > self._overlay_timeout:
                    self._overlay = None
                    self._overlay_timeout = None
                current_overlay = self._overlay

            try:
                if _last_prepared is not None:
                    # Staleness check — always applies, even when force=True
                    if not self._incoming.is_current(_last_prepared.target.generation):
                        logger.debug(
                            "Render loop: stale target, skipping until newer item"
                        )
                        continue

                    # Dedup: skip re-render if same image is already on screen
                    # and nothing has changed. force=True bypasses this check.
                    already_shown = _last_prepared.target.image_key == self._current_key
                    overlay_changed = current_overlay is not _rendered_overlay
                    if (
                        already_shown
                        and not overlay_changed
                        and not _last_prepared.target.force
                    ):
                        # E-ink render skip is correct, but ensure web cache
                        # is populated (it's None after restart while e-ink
                        # retains the physical image).
                        if self.last_rendered_image is None:
                            display_image = self._composite(
                                current_overlay, _last_prepared.image
                            )
                            self._cache_for_web(display_image, _last_prepared.target)
                        continue

                    display_image = self._composite(
                        current_overlay, _last_prepared.image
                    )
                    # Cache before render so the web UI shows the image while hardware
                    # is still updating (~25s on e-ink).
                    self._cache_for_web(display_image, _last_prepared.target)
                    try:
                        self._viewer.render(
                            display_image,
                            _last_prepared.target.image_key,
                            _last_prepared.target.track_info,
                        )
                        self._current_key = _last_prepared.target.image_key
                        _rendered_overlay = current_overlay
                        self._last_rendered_target = _last_prepared.target
                        queue_to_display = time.time() - _last_prepared.target.queued_at
                        logger.info(
                            f"Track displayed: {_last_prepared.target.image_key}"
                            f" — {queue_to_display:.1f}s from queue to display"
                        )
                    except RenderCancelledError:
                        logger.info(
                            "Render cancelled — will re-render when next item ready"
                        )

                elif current_overlay:
                    # No art yet — show overlay as full-screen message
                    display_image = self.message_renderer.create_text_message(
                        current_overlay
                    )
                    self._cache_for_web(
                        display_image,
                        RenderTarget(
                            content_type="overlay",
                            image_key=None,
                            image_path=None,
                            img=None,
                            track_info=None,
                        ),
                    )
                    try:
                        self._viewer.render(display_image, None, None)
                        _rendered_overlay = current_overlay
                    except RenderCancelledError:
                        logger.info("Render cancelled (overlay-only)")
                else:
                    logger.warning("No content to render")
            except Exception as e:
                logger.error(f"Render loop: unexpected error: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _composite(self, overlay_text: Optional[str], base: Image.Image) -> Image.Image:
        """Composite an error-overlay badge onto the bottom-right of base."""
        if overlay_text is None:
            return base
        overlay_img = self.message_renderer.create_error_overlay(
            overlay_text, base.size
        )
        result = base.copy()
        x = base.width - overlay_img.width
        y = base.height - overlay_img.height
        result.paste(overlay_img, (x, y))
        return result

    def _cache_for_web(self, display_image: Image.Image, target: RenderTarget) -> None:
        """Cache the rendered image and metadata for web UI access."""
        self.last_rendered_image = display_image.copy()
        self.last_render_metadata = {
            "timestamp": time.time(),
            "content_type": target.content_type,
            "image_key": target.image_key,
            "track_info": target.track_info,
            "has_overlay": self._overlay is not None,
        }

    def _initialize_current_display_state(self) -> None:
        """Read last-displayed key from disk for e-ink persistence across restarts."""
        if not hasattr(self._viewer, "epd"):
            return  # Not an e-ink display; no persistence needed
        try:
            from .utils import get_current_image_key

            self._current_key = get_current_image_key()
            if self._current_key:
                logger.info(f"E-ink display already showing: {self._current_key}")
        except Exception as e:
            logger.debug(f"Could not read current image key: {e}")
