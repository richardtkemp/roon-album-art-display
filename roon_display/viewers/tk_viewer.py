"""Tkinter-based viewer for system displays."""

import logging

from ..utils import set_current_image_key
from .base import BaseViewer

logger = logging.getLogger(__name__)


class TkViewer(BaseViewer):
    """Viewer for system displays using Tkinter."""

    def __init__(self, config_manager, root):
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
            # Use the explicit size we set
            window_width = 800
            window_height = 600

        self.set_screen_size(window_width, window_height)

        # Configure window
        self.root.title("Album Art Viewer")
        self._setup_window_appearance()
        self._setup_window_behavior()

        # Track pending updates for thread safety
        self.pending_image_data = None

        self.startup()

    def _configure_window_size(self):
        """Configure window size and fullscreen mode. Returns fullscreen state."""
        # Set fullscreen mode based on config
        fullscreen = self.config.getboolean(
            "DISPLAY", "tkinter_fullscreen", fallback=False
        )
        self.root.attributes("-fullscreen", fullscreen)

        # If not fullscreen, set a reasonable window size
        if not fullscreen:
            self.root.geometry("800x600")

        return fullscreen

    def _setup_window_appearance(self):
        """Configure window appearance."""
        # Force light theme
        self.root.tk_setPalette(
            background="#f0f0f0",
            foreground="black",
            activeBackground="#e0e0e0",
            activeForeground="black",
        )

        # Create image label
        import tkinter as tk

        self.label = tk.Label(self.root)
        self.label.pack(fill=tk.BOTH, expand=True)

    def _setup_window_behavior(self):
        """Configure window event handling."""
        # Escape key to close
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def check_pending_updates(self):
        """Check for pending image updates (call from main thread)."""
        # Schedule next check
        self.root.after(100, self.check_pending_updates)

        # Process pending update
        if self.pending_image_data is not None:
            image_key, image_path, img, title = self.pending_image_data
            self.display_image(image_key, image_path, img, title)
            logger.info(f"Updated display with {title}")
            self.pending_image_data = None

    def display_image(self, image_key, image_path, img, title):
        """Display image (must be called from main thread)."""
        # Load and process image if not provided
        if img is None:
            if image_path is None:
                logger.warning(f"No image or path provided for display: {title}")
                return
            img = self.image_processor.fetch_image(image_path)
            if img is None:
                logger.warning(f"Could not load image for display: {image_path}")
                return
            img = self.image_processor.process_image_position(img)
        # If img is provided, use it directly (already processed for anniversaries)

        try:
            # Convert to PhotoImage for Tkinter
            from PIL import ImageTk

            self.photo = ImageTk.PhotoImage(img)

            # Update label
            self.label.configure(image=self.photo)
            self.label.image = self.photo  # Keep reference for GC

            # Update current image key
            set_current_image_key(image_key)

        except Exception as e:
            logger.error(f"Error displaying image in Tkinter: {e}")

    def update(self, image_key, image_path, img, title):
        """Thread-safe method to request image update."""
        # Store update data for main thread to process
        self.pending_image_data = (image_key, image_path, img, title)

    def update_anniversary(self, message, image_path=None):
        """Display anniversary message and optional image."""
        # This method is now handled by RoonClient using shared anniversary logic
        # Left as placeholder for interface compatibility
        pass
