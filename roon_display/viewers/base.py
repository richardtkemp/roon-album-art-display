"""Base viewer class for displaying album art."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from ..health import HealthManager
from ..image_processing.processor import ImageProcessor
from ..utils import get_current_image_key, get_saved_image_dir

logger = logging.getLogger(__name__)


class BaseViewer(ABC):
    """Abstract base class for all viewers."""

    def __init__(self, config_manager):
        """Initialize viewer with configuration manager."""
        self.config_manager = config_manager
        self.image_processor = ImageProcessor(config_manager)

        # Initialize health manager if health script is configured
        self.health_manager = HealthManager(config_manager)

        # Render coordinator callback for tracking display state
        self.render_coordinator = None

    def set_render_coordinator(self, coordinator):
        """Set the render coordinator for display state tracking."""
        self.render_coordinator = coordinator

    def _notify_render_complete(self, image_key: str):
        """Notify render coordinator that a render completed successfully."""
        if self.render_coordinator and image_key:
            self.render_coordinator.set_current_display_image_key(image_key)

    def _finalize_successful_render(self, image_key: str):
        """Common logic for successful renders - update tracking and notify coordinator."""
        # Update current image key tracking
        from ..utils import set_current_image_key

        set_current_image_key(image_key)

        # Notify render coordinator of successful render
        self._notify_render_complete(image_key)

    def _load_and_process_image(self, img, image_path, title):
        """Common logic to load and process images."""
        # Load image if not provided
        if img is None:
            if image_path is None:
                logger.warning(f"No image or path provided for display: {title}")
                return None

            img = self.image_processor.fetch_image(image_path)
            if img is None:
                logger.warning(f"Could not load image for display: {image_path}")
                return None

            # Process image position (for fresh images)
            img = self.image_processor.process_image_position(img)

        # If img was provided, assume it's already processed (e.g., anniversaries, errors)
        return img


    def _log_render_error(self, error, title, duration=None):
        """Common error logging for render failures."""
        duration_str = f" after {duration:.2f}s" if duration else ""
        logger.error(f"Error displaying image{duration_str} for {title}: {error}")

    def set_screen_size(self, width, height):
        """Set screen dimensions and update config manager."""
        self.config_manager.set_screen_width(width)
        self.config_manager.set_screen_height(height)

    def startup(self):
        """Startup hook for viewers - now handled by coordinator."""
        # Startup image loading is now handled by the RenderCoordinator
        # This method is kept for backward compatibility
        pass

    @abstractmethod
    def update(self, image_key, image_path, img, title):
        """Update the display with a new image."""
        pass

    @abstractmethod
    def display_image(self, image_key, image_path, img, title):
        """Display an image on the device."""
        pass

