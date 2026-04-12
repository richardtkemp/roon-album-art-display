"""Base viewer class for displaying album art."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from ..health import HealthManager
from ..image_processing.processor import ImageProcessor

if TYPE_CHECKING:
    from ..config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class BaseViewer(ABC):
    """Abstract base class for all viewers."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize viewer with configuration manager."""
        self.config_manager = config_manager
        self.image_processor = ImageProcessor(config_manager)

        # Initialize health manager if health script is configured
        self.health_manager = HealthManager(config_manager)

        # Render coordinator callback for tracking display state
        self.render_coordinator: Any = None

        # Optional callback invoked after each successful render completes.
        # Set by callers that need to react to display completion (e.g. standalone mode).
        self.on_display_complete: Optional[Callable[[], None]] = None

    def set_render_coordinator(self, coordinator: Any) -> None:
        """Set the render coordinator for display state tracking."""
        self.render_coordinator = coordinator

    def _finalize_successful_render(self, image_key: Optional[str]) -> None:
        """Common logic for successful renders — update tracking."""
        from ..utils import set_current_image_key

        if image_key:
            set_current_image_key(image_key)

        if self.on_display_complete is not None:
            self.on_display_complete()

    def _log_render_error(
        self, error: Exception, title: str, duration: Optional[float] = None
    ) -> None:
        """Common error logging for render failures."""
        duration_str = f" after {duration:.2f}s" if duration else ""
        logger.error(f"Error displaying image{duration_str} for {title}: {error}")

    def set_screen_size(self, width: int, height: int) -> None:
        """Set screen dimensions and update config manager."""
        self.config_manager.set_screen_width(width)
        self.config_manager.set_screen_height(height)

    def startup(self) -> None:
        """Startup hook for viewers — now handled by coordinator."""
        pass

    @abstractmethod
    def render(
        self, image: Any, image_key: Optional[str], title: Optional[str]
    ) -> None:
        """Blocking render. Raises RenderCancelledError if cancelled mid-render."""
        pass

    @abstractmethod
    def cancel(self) -> None:
        """Signal current render to abort. No-op if idle."""
        pass
