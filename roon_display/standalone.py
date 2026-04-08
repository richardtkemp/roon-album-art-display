"""Standalone image display mode — sends one image to the configured display and exits.

Usage:
    python -m roon_display.main --image /path/to/image.jpg
    python -m roon_display.main --image /path/to/images/
"""

import logging
import random
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}
)


def resolve_image(path: Path) -> Path:
    """Return a concrete image path from a file path or directory.

    If *path* is a directory, a file is chosen at random from its immediate
    contents.  Raises ``FileNotFoundError`` if no suitable image is found.
    """
    if path.is_dir():
        candidates = [f for f in path.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
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

    if tk_root is not None:
        _run_tkinter(viewer, tk_root, image_path)
    else:
        _run_eink(viewer, image_path)


def _run_tkinter(viewer, tk_root, image_path: Path) -> None:
    """Display image via TkViewer and exit when rendering is complete."""
    # Register completion callback: quit the mainloop once the image is shown.
    viewer.on_display_complete = tk_root.quit

    # Kick off the pending-update polling loop, then queue our image.
    viewer.check_pending_updates()
    viewer.update("standalone", image_path, None, image_path.name)

    tk_root.mainloop()
    sys.exit(0)


def _run_eink(viewer, image_path: Path) -> None:
    """Display image via EinkViewer and exit when rendering is complete."""
    try:
        viewer.update("standalone", image_path, None, image_path.name)

        # EinkViewer.update() spawns a thread for the hardware operation; wait for it.
        if viewer.update_thread is not None:
            viewer.update_thread.join()
    finally:
        if hasattr(viewer, "cleanup"):
            viewer.cleanup()

    sys.exit(0)
