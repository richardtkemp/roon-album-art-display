"""Standalone display mode — sends one image (or the current time) to the
configured display and exits.

Usage:
    python -m roon_display.main --image /path/to/image.jpg
    python -m roon_display.main --image /path/to/images/
    python -m roon_display.main --time
"""

from __future__ import annotations

import logging
import random
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from .utils import SUPPORTED_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)


def resolve_image(path: Path) -> Path:
    """Return a concrete image path from a file path or directory.

    If *path* is a directory, a file is chosen at random from its immediate
    contents.  Raises ``FileNotFoundError`` if no suitable image is found.
    """
    if path.is_dir():
        candidates = [
            f for f in path.iterdir() if f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]
        if not candidates:
            raise FileNotFoundError(f"No image files found in directory: {path}")
        chosen = random.choice(candidates)
        logger.info(f"Selected image from directory: {chosen.name}")
        return chosen

    if not path.is_file():
        raise FileNotFoundError(f"Image path does not exist: {path}")

    return path


def run(image_path: Path) -> None:
    """Display *image_path* on the configured display and exit.

    Creates a minimal environment (ConfigManager + viewer) and sends the image
    directly, bypassing the Roon client and all web servers.
    """
    from .config.config_manager import ConfigManager
    from .viewers.factory import create_viewer

    image_path = resolve_image(image_path)
    logger.info(f"Standalone display: {image_path}")

    config_manager = ConfigManager()
    viewer, tk_root = create_viewer(config_manager)

    prepared = viewer.image_processor.prepare(None, image_path)
    _display_and_exit(viewer, tk_root, prepared, image_path.name)


def run_time() -> None:
    """Render the current date/time on the configured display and exit.

    A Roon-free way to confirm the display works end to end. Note: on a frame
    where the service already owns the e-ink, use ``simulate_track_change.py
    --time`` instead so the running app renders it (avoids a hardware clash).
    """
    from .config.config_manager import ConfigManager
    from .message_renderer import MessageRenderer
    from .time_utils import current_time_message
    from .viewers.factory import create_viewer

    config_manager = ConfigManager()
    viewer, tk_root = create_viewer(config_manager)

    message = current_time_message()
    logger.info(f"Standalone time display: {message!r}")
    time_image = MessageRenderer(config_manager).create_text_message(message)

    prepared = viewer.image_processor.prepare(time_image, None)
    _display_and_exit(viewer, tk_root, prepared, "time")


def _display_and_exit(
    viewer: Any, tk_root: Any, prepared: Optional[Any], name: str
) -> None:
    """Render a prepared image on the viewer, then exit the process."""
    if prepared is None:
        logger.error(f"Failed to prepare image for: {name}")
        sys.exit(1)

    if tk_root is not None:
        _run_tkinter(viewer, tk_root, prepared, name)
    else:
        _run_eink(viewer, prepared, name)


def _run_tkinter(viewer: Any, tk_root: Any, prepared: Any, name: str) -> None:
    """Render via TkViewer and exit once the image is shown.

    ``TkViewer.render()`` blocks until the Tk main thread runs the update
    (via ``root.after``), so it must be called off the main thread while
    ``mainloop()`` pumps events here. ``on_display_complete`` quits the loop.
    """
    viewer.on_display_complete = tk_root.quit

    def _worker() -> None:
        try:
            viewer.render(prepared, None, name)
        except Exception as e:
            logger.error(f"Failed to display {name}: {e}")
            tk_root.quit()

    threading.Thread(target=_worker, daemon=True, name="standalone-render").start()
    tk_root.mainloop()
    sys.exit(0)


def _run_eink(viewer: Any, prepared: Any, name: str) -> None:
    """Render via EinkViewer (blocking) and exit."""
    try:
        viewer.render(prepared, None, name)
    except Exception as e:
        logger.error(f"Failed to display {name}: {e}")
        sys.exit(1)
    finally:
        if hasattr(viewer, "cleanup"):
            viewer.cleanup()

    sys.exit(0)
