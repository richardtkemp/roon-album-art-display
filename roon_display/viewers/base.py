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
        self.config = config_manager.config
        self.image_processor = ImageProcessor(self.config)

        # Initialize health manager if health script is configured
        health_script_path = config_manager.get_health_script()
        health_recheck_interval = config_manager.get_health_recheck_interval()
        self.health_manager = HealthManager(health_script_path, health_recheck_interval)

    def set_screen_size(self, width, height):
        """Set screen dimensions and update image processor."""
        self.image_processor.set_screen_size(width, height)
        self.screen_width = width
        self.screen_height = height

    def startup(self):
        """Load any existing image on startup."""
        try:
            image_key = get_current_image_key()
            if image_key:
                image_path = get_saved_image_dir() / f"album_art_{image_key}.jpg"
                if Path(image_path).exists():
                    self.update(image_key, image_path, None, "startup")
        except Exception as e:
            logger.warning(f"Error during startup image loading: {e}")

    @abstractmethod
    def update(self, image_key, image_path, img, title):
        """Update the display with a new image."""
        pass

    @abstractmethod
    def display_image(self, image_key, image_path, img, title):
        """Display an image on the device."""
        pass

    @abstractmethod
    def update_anniversary(self, message, image_path=None):
        """Display anniversary message and optional image."""
        pass
