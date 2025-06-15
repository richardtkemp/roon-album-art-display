"""Centralized render coordinator that manages main content and overlay display."""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


class RenderCoordinator:
    """Coordinates rendering with main content slot and overlay slot."""

    def __init__(
        self,
        viewer,
        image_processor,
        message_renderer,
        config_manager,
        anniversary_manager=None,
    ):
        """Initialize render coordinator."""
        self.viewer = viewer
        self.image_processor = image_processor
        self.message_renderer = message_renderer
        self.anniversary_manager = anniversary_manager
        self.config_manager = config_manager

        # Content slots
        self.main_content = None  # Art or anniversary content (fullscreen)
        self.overlay_content = None  # Errors or temporary messages (bottom-right)
        self.overlay_timeout = None  # When overlay should auto-clear

        # Rendering control
        self.currently_rendering = False
        self.render_lock = threading.Lock()

        # E-ink display persistence tracking
        self.eink_display_persistent = hasattr(viewer, "epd")  # Check if this is e-ink
        self.current_display_image_key = None

        # Image caching for web access
        self.last_rendered_image = None
        self.last_render_metadata = {}

        logger.info("RenderCoordinator initialized with main/overlay slots")

        # Check if there's a current image displayed (for e-ink persistence)
        self._initialize_current_display_state()

        # Start anniversary checking if enabled
        if self.anniversary_manager:
            self.anniversary_manager.start_anniversary_monitor(self)

    def create_final_display_image(
        self, main_content, config_manager, overrides: Optional[Dict[str, Any]] = None
    ) -> Image.Image:
        """
        Create the final display image by compositing main content onto a white canvas.

        This function centralizes all image processing and positioning logic in one place.
        It handles the complete flow from raw content image to final display-ready image.

        Data Flow:
        1. Extract screen dimensions and positioning parameters from config_manager
        2. Allow web interface overrides to take precedence over config values
        3. Create a white canvas at full screen dimensions
        4. Process the main content image: scale, rotate, and position
        5. Composite the processed image onto the canvas, centered with offsets
        6. Return the final composite image ready for display

        Args:
            main_content: The source image to be displayed (album art, anniversary, etc.)
            config_manager: Configuration manager providing default values for all parameters
            overrides: Optional dict with web interface overrides. Keys can include:
                            - 'screen_width', 'screen_height': Display dimensions
                            - 'scale_x', 'scale_y': Scaling factors (1.0 = no scaling)
                            - 'rotation': Rotation angle (0, 90, 180, 270 degrees)
                            - 'image_offset_x', 'image_offset_y': Position offsets in pixels
                            - 'color_enhance', 'contrast', 'brightness', 'sharpness': Image enhancements (1.0 = no change)

        Returns:
            PIL.Image: Final composite image at screen dimensions, ready for display

        Processing Steps:
        - Gets screen dimensions from config or overrides
        - Gets scaling factors (default 1.0 = no scaling)
        - Gets rotation angle (default 0 = no rotation)
        - Gets position offsets (default 0 = centered)
        - Gets image enhancement values (default 1.0 = no change)
        - Creates white background canvas at screen size
        - Scales main content image by scale_x and scale_y factors
        - Rotates image by specified angle
        - Applies image enhancements (color, contrast, brightness, sharpness)
        - Positions image at center + offsets on the canvas
        - Returns final composite ready for viewer
        """
        # Extract all configuration parameters
        screen_width = config_manager.get_config(overrides, "screen_width")
        screen_height = config_manager.get_config(overrides, "screen_height")
        scale_x = config_manager.get_config(overrides, "scale_x")
        scale_y = config_manager.get_config(overrides, "scale_y")
        rotation = str(config_manager.get_config(overrides, "rotation"))
        offset_x = config_manager.get_config(overrides, "image_offset_x")
        offset_y = config_manager.get_config(overrides, "image_offset_y")

        # IMAGE_RENDER configuration parameters
        color_enhance = config_manager.get_config(overrides, "color_enhance")
        contrast = config_manager.get_config(overrides, "contrast")
        brightness = config_manager.get_config(overrides, "brightness")
        sharpness = config_manager.get_config(overrides, "sharpness")

        # Create white canvas at screen dimensions
        canvas = Image.new("RGB", (screen_width, screen_height), "white")

        # Process the main content image
        logger.debug(f"Preview for {main_content}")
        processed_image = main_content["img"].copy()

        # First, fit the source image to canvas dimensions while preserving aspect ratio
        original_width, original_height = processed_image.size
        canvas_size = min(screen_width, screen_height)
        processed_image = processed_image.resize(
            (canvas_size, canvas_size), Image.Resampling.LANCZOS
        )
        logger.debug(
            f"Fitted image to canvas size: {original_width}x{original_height} → {canvas_size}x{canvas_size}"
        )

        # Then apply scaling on top of the fitted image
        if scale_x != 1.0 or scale_y != 1.0:
            fitted_width, fitted_height = processed_image.size
            new_width = int(fitted_width * scale_x)
            new_height = int(fitted_height * scale_y)
            processed_image = processed_image.resize(
                (new_width, new_height), Image.Resampling.LANCZOS
            )
            logger.debug(
                f"Scaled fitted image: {fitted_width}x{fitted_height} → {new_width}x{new_height}"
            )

        # Apply rotation
        if rotation == "90":
            processed_image = processed_image.transpose(Image.ROTATE_90)
        elif rotation == "180":
            processed_image = processed_image.transpose(Image.ROTATE_180)
        elif rotation == "270":
            processed_image = processed_image.transpose(Image.ROTATE_270)

        if rotation != "0":
            logger.debug(f"Rotated image by {rotation}°: {processed_image.size}")

        # Apply IMAGE_RENDER enhancements
        enhancement_applied = False

        if color_enhance != 1.0:
            enhancer = ImageEnhance.Color(processed_image)
            processed_image = enhancer.enhance(color_enhance)
            enhancement_applied = True

        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(processed_image)
            processed_image = enhancer.enhance(contrast)
            enhancement_applied = True

        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(processed_image)
            processed_image = enhancer.enhance(brightness)
            enhancement_applied = True

        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(processed_image)
            processed_image = enhancer.enhance(sharpness)
            enhancement_applied = True

        if enhancement_applied:
            logger.debug(
                f"Applied enhancements: color={color_enhance}, contrast={contrast}, brightness={brightness}, sharpness={sharpness}"
            )

        # Calculate centered position with offsets
        img_width, img_height = processed_image.size
        center_x = (screen_width - img_width) // 2
        center_y = (screen_height - img_height) // 2
        final_x = center_x + offset_x
        final_y = center_y + offset_y

        # Composite onto canvas
        canvas.paste(processed_image, (final_x, final_y))

        logger.debug(
            f"Final composite: {screen_width}x{screen_height} canvas, "
            f"image at ({final_x}, {final_y}), "
            f"scale=({scale_x}, {scale_y}), rotation={rotation}°, offset=({offset_x}, {offset_y})"
        )

        # Cache the rendered image for web access
        self._cache_rendered_image(canvas)

        return canvas

    def set_main_content(
        self,
        content_type: str,
        image_key: str = None,
        image_path: Path = None,
        img: Optional[Image.Image] = None,
        track_info: str = None,
        **kwargs,
    ):
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

        if content_type == "last_art":
            img = self.image_processor.fetch_image(image_path)

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

    def set_overlay(self, message: str, timeout: Optional[float] = None):
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

    def clear_overlay(self):
        """Clear overlay content."""
        if self.overlay_content:
            logger.info("Clearing overlay")
            self.overlay_content = None
            self.overlay_timeout = None
            self._render_display()

    def _render_display(self):
        """Render the current state to the display."""
        if self.currently_rendering:
            return

        # Check for overlay timeout
        if self.overlay_timeout and time.time() > self.overlay_timeout:
            self.overlay_content = None
            self.overlay_timeout = None

        with self.render_lock:
            if self.currently_rendering:
                return
            self.currently_rendering = True

        # Determine what to render
        if self.main_content:
            img = self.create_final_display_image(
                self.main_content, self.config_manager, None
            )
        elif self.overlay_content:
            img = self._render_overlay_fullscreen()
        else:
            logger.warning("No content to render")
            return None

        logger.debug(f"Rendering display content: {self.main_content}")
        self.viewer.update(
            self.main_content["image_key"], None, img, self.main_content["track_info"]
        )
        with self.render_lock:
            self.currently_rendering = False

    def force_refresh(self):
        """Force a re-render of the current display content with updated config values."""
        logger.info("Force refresh triggered from web interface")
        self._render_display()

    def _initialize_current_display_state(self):
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

    def set_current_display_image_key(self, image_key: str):
        """Update the current display image key (called by viewers after successful renders)."""
        self.current_display_image_key = image_key
        logger.debug(f"Updated current display image key: {image_key}")

    def _cache_rendered_image(self, image: Optional[Image.Image]):
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

            # Use centralized rendering function with config overrides
            preview_image = self.create_final_display_image(
                self.main_content,
                self.config_manager,
                config_data,  # Pass config_data directly - no conversion needed
            )

            logger.debug(
                "Preview image generated successfully using centralized renderer"
            )
            return preview_image

        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            return None
