"""Tkinter-based viewer for system displays."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Optional

from .base import BaseViewer

if TYPE_CHECKING:
    from ..config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class TkViewer(BaseViewer):
    """Viewer for system displays using Tkinter."""

    def __init__(self, config_manager: ConfigManager, root: Any) -> None:
        """Initialize with Tkinter root window."""
        super().__init__(config_manager)
        self.root = root

        # Configure window first to get correct size
        fullscreen = self._configure_window_size()

        # Set screen size based on window configuration
        if fullscreen:
            window_width = self.root.winfo_screenwidth()
            window_height = self.root.winfo_screenheight()
        else:
            window_width = 600
            window_height = 600

        self.set_screen_size(window_width, window_height)

        # Configure window
        self.root.title("Album Art Viewer")
        self._setup_window_appearance()
        self._setup_window_behavior()

        self.startup()

    def _configure_window_size(self) -> bool:
        """Configure window size and fullscreen mode. Returns fullscreen state."""
        fullscreen = bool(self.config_manager.get_tkinter_fullscreen())
        self.root.attributes("-fullscreen", fullscreen)
        if not fullscreen:
            self.root.geometry("600x600")
        return fullscreen

    def _setup_window_appearance(self) -> None:
        """Configure window appearance."""
        self.root.tk_setPalette(
            background="#f0f0f0",
            foreground="black",
            activeBackground="#e0e0e0",
            activeForeground="black",
        )
        import tkinter as tk

        self.label = tk.Label(self.root)
        self.label.pack(fill=tk.BOTH, expand=True)

    def _setup_window_behavior(self) -> None:
        """Configure window event handling."""
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def render(
        self, image: Any, image_key: Optional[str], title: Optional[str]
    ) -> None:
        """Thread-safe blocking render via the Tk main thread.

        Schedules the actual Tk update on the main thread via ``root.after(0,
        …)`` and blocks until the callback fires.  This keeps Tk widget updates
        on the correct thread while allowing the coordinator's render worker to
        call render() from a background thread.
        """
        done = threading.Event()
        error_holder: list = []

        def _do_render() -> None:
            try:
                from PIL import ImageTk

                self.photo = ImageTk.PhotoImage(image)
                self.label.configure(image=self.photo)
                self.label.image = self.photo  # type: ignore[attr-defined]
                self._finalize_successful_render(image_key)
            except Exception as e:
                error_holder.append(e)
            finally:
                done.set()

        self.root.after(0, _do_render)
        done.wait()
        if error_holder:
            raise error_holder[0]

    def cancel(self) -> None:
        """No-op — Tk renders are fast and not worth cancelling."""
        pass
