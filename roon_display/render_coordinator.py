"""Centralized render coordinator that manages main content and overlay display."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from PIL import Image

if TYPE_CHECKING:
    from .config.config_manager import ConfigManager
    from .image_processing.processor import ImageProcessor

logger = logging.getLogger(__name__)


class RenderCoordinator:
    """Coordinates rendering with main content slot and overlay slot."""

    def __init__(
        self,
        viewer: Any,
        image_processor: "ImageProcessor",
        message_renderer: Any,
        config_manager: "ConfigManager",
        anniversary_manager: Any = None,
    ) -> None:
        """Initialize render coordinator."""
        self.viewer = viewer
        self.image_processor = image_processor
        self.message_renderer = message_renderer
        self.anniversary_manager = anniversary_manager
        self.config_manager = config_manager

        # Content slots
        self.main_content: Optional[Dict[str, Any]] = (
            None  # Art or anniversary content (fullscreen)
        )
        self.overlay_content: Optional[Dict[str, Any]] = (
            None  # Errors or temporary messages (bottom-right)
        )
        self.overlay_timeout: Optional[float] = None  # When overlay should auto-clear

        # Rendering control
        self._render_pending = False
        self.render_lock = threading.Lock()

        # E-ink display persistence tracking
        self.eink_display_persistent = hasattr(viewer, "epd")  # Check if this is e-ink
        self.current_display_image_key: Optional[str] = None

        # Image caching for web access
        self.last_rendered_image: Optional[Image.Image] = None
        self.last_render_metadata: Dict[str, Any] = {}

        logger.info("RenderCoordinator initialized with main/overlay slots")

        # Check if there's a current image displayed (for e-ink persistence)
        self._initialize_current_display_state()

        # Start anniversary checking if enabled
        if self.anniversary_manager:
            self.anniversary_manager.start_anniversary_monitor(self)

    def set_main_content(
        self,
        content_type: str,
        image_key: Optional[str] = None,
        image_path: Optional[Path] = None,
        img: Optional[Image.Image] = None,
        track_info: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Set main content (art or anniversary) for fullscreen display."""
        logger.info(f"Setting main content: {content_type}")

        # Check if this is already displayed on e-ink (no need to re-render)
        if (
            self.eink_display_persistent
            and image_key
            and self.current_display_image_key == image_key
        ):
            logger.info(
                f"Skipping render - image {image_key} already displayed on e-ink"
            )
            return

        # Store main content data
        self.main_content = {
            "content_type": content_type,
            "image_key": image_key,
            "image_path": image_path,
            "img": img,
            "track_info": track_info,
            "timestamp": time.time(),
            **kwargs,
        }

        # Update anniversary timing for new art (not for startup/cached art)
        if content_type == "art" and self.anniversary_manager:
            self.anniversary_manager.update_last_track_time()

        # Trigger render
        self._render_display()

    def set_overlay(self, message: str, timeout: Optional[float] = None) -> None:
        """Set overlay content (errors, messages) for bottom-right display."""
        logger.warning(f"Setting overlay: {message}")

        # Store overlay data
        self.overlay_content = {
            "message": message,
            "timestamp": time.time(),
        }

        # Set timeout for auto-clearing
        if timeout:
            self.overlay_timeout = time.time() + timeout
        else:
            self.overlay_timeout = None

        # Trigger render
        self._render_display()

    def clear_overlay(self) -> None:
        """Clear overlay content."""
        if self.overlay_content:
            logger.info("Clearing overlay")
            self.overlay_content = None
            self.overlay_timeout = None
            self._render_display()

    def _render_display(self) -> None:
        """Render the current state to the display."""
        self._render_pending = True
        if not self.render_lock.acquire(blocking=False):
            return  # render in progress; it will loop and pick up the flag

        try:
            while self._render_pending:
                self._render_pending = False

                # Check for overlay timeout
                if self.overlay_timeout and time.time() > self.overlay_timeout:
                    self.overlay_content = None
                    self.overlay_timeout = None

                # Determine what to render
                if self.main_content:
                    img = self.image_processor.prepare(
                        self.main_content["img"],
                        self.main_content["image_path"],
                    )
                    if img is None:
                        logger.error("Failed to prepare image for render")
                        continue
                    self._cache_rendered_image(img)
                elif self.overlay_content:
                    # No main content — render overlay as full-screen message
                    img = self.message_renderer.create_text_message(
                        self.overlay_content["message"]
                    )
                else:
                    logger.warning("No content to render")
                    continue

                logger.debug(f"Rendering display content: {self.main_content}")
                self.viewer.update(
                    self.main_content["image_key"] if self.main_content else None,
                    img,
                    self.main_content["track_info"] if self.main_content else None,
                )
        finally:
            self.render_lock.release()

    def force_refresh(self) -> None:
        """Force a re-render of the current display content with updated config values."""
        logger.info("Force refresh triggered from web interface")
        self._render_display()

    def _initialize_current_display_state(self) -> None:
        """Initialize coordinator with current display state (e-ink persistence)."""
        if self.eink_display_persistent:
            # Try to get current image key from utils
            try:
                from .utils import get_current_image_key

                self.current_display_image_key = get_current_image_key()
                if self.current_display_image_key:
                    logger.info(
                        f"E-ink display already showing image: {self.current_display_image_key}"
                    )
            except Exception as e:
                logger.debug(f"Could not get current image key: {e}")

    def set_current_display_image_key(self, image_key: str) -> None:
        """Update the current display image key (called by viewers after successful renders)."""
        self.current_display_image_key = image_key
        logger.debug(f"Updated current display image key: {image_key}")

    def _cache_rendered_image(self, image: Optional[Image.Image]) -> None:
        """Cache the rendered image for internal server access."""
        if image:
            self.last_rendered_image = image.copy()
        else:
            self.last_rendered_image = None

    def get_current_rendered_image(
        self,
    ) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
        """Get current rendered image and metadata for internal server."""
        return self.last_rendered_image, self.last_render_metadata.copy()

    def render_preview(self, config_data: Dict[str, Any]) -> Optional[Image.Image]:
        """
        Generate a preview image showing how the current display would look with modified settings.

        This function provides real-time preview functionality for the web configuration interface.
        Users can adjust settings in the web form and see immediate visual feedback of how those
        changes would affect the actual display output, without applying the changes permanently.

        Data Flow:
        1. Takes the current main content image (album art, anniversary image, etc.)
        2. Applies temporary configuration overrides from the web interface
        3. Uses the centralized create_final_display_image() function to render the result
        4. Returns the preview image for display in the web browser

        Configuration Handling:
        - Accepts config_data in web form format (e.g., "IMAGE_RENDER.brightness")
        - Passes overrides directly to create_final_display_image() without conversion
        - Falls back to current config values for any settings not overridden
        - Supports all rendering parameters: scaling, rotation, positioning, enhancements

        Use Cases:
        - Web interface live preview while adjusting sliders/inputs
        - Validating configuration changes before saving
        - Visual feedback for complex multi-parameter adjustments

        Args:
            config_data: Dictionary of configuration overrides from web form.
                        Keys should be in "SECTION.field" format (e.g., "IMAGE_POSITION.scale_x")
                        Values are typically strings from form inputs that get converted as needed

        Returns:
            PIL.Image: Preview image at full screen dimensions, or None if preview generation failed
        """
        try:
            # Get diff to show only changed values
            config_diff = self.config_manager.get_config_diff(config_data)
            if config_diff:
                changes_summary = []
                for key, diff in config_diff.items():
                    changes_summary.append(f"{key}: {diff['old']} → {diff['new']}")
                logger.info(
                    f"Generating preview with config changes: {', '.join(changes_summary)}"
                )
            else:
                logger.info("Generating preview with no config changes")

            # Get main content image directly
            if not self.main_content:
                logger.warning("No main content image available for preview")
                return None

            preview_image = self.image_processor.prepare(
                self.main_content["img"],
                self.main_content["image_path"],
                overrides=config_data,
            )

            logger.debug("Preview image generated successfully")
            return preview_image

        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            return None
