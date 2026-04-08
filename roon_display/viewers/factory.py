"""Factory for creating viewer instances based on configuration."""

import importlib
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def create_viewer(config_manager):
    """Create appropriate viewer based on configuration.

    Returns a tuple of (viewer, tk_root) where tk_root is None for non-Tkinter viewers.
    """
    display_type = config_manager.get_display_type()

    if display_type == "system_display":
        logger.info("Creating Tkinter system display viewer")
        import tkinter as tk

        from .tk_viewer import TkViewer

        root = tk.Tk()
        viewer = TkViewer(config_manager, root)
        return viewer, root

    elif display_type == "epd13in3E":
        logger.info(f"Creating e-ink viewer for {display_type}")

        # Add libs directory to path for e-ink modules
        libs_dir = Path(__file__).parent.parent.parent / "libs"
        if libs_dir.exists():
            sys.path.insert(0, str(libs_dir))

        try:
            eink_module = importlib.import_module(f"libs.{display_type}")
        except ImportError as e:
            logger.error(f"Could not import e-ink module {display_type}: {e}")
            raise

        from .eink_viewer import EinkViewer

        viewer = EinkViewer(config_manager, eink_module)
        return viewer, None

    else:
        raise ValueError(f"Unknown display type: {display_type}")
