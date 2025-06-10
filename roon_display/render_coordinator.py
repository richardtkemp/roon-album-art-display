"""Centralized render coordinator that manages main content and overlay display."""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class RenderCoordinator:
    """Coordinates rendering with main content slot and overlay slot."""

    def __init__(self, viewer, image_processor, message_renderer, anniversary_manager=None):
        """Initialize render coordinator."""
        self.viewer = viewer
        self.image_processor = image_processor
        self.message_renderer = message_renderer
        self.anniversary_manager = anniversary_manager
        
        # Get configuration for overlay sizing
        from .config.config_manager import ConfigManager
        config_manager = ConfigManager()
        self.overlay_config = config_manager.get_overlay_config()
        self.anniversary_config = config_manager.get_anniversaries_config()

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

        # Anniversary timing
        self.last_anniversary_check = 0
        self.anniversary_check_interval = 60  # Check every minute
        
        # Image caching for web access
        self.last_rendered_image = None
        self.last_render_metadata = {}

        logger.info("RenderCoordinator initialized with main/overlay slots")

        # Check if there's a current image displayed (for e-ink persistence)
        self._initialize_current_display_state()
        
        # Start anniversary checking if enabled
        if self.anniversary_manager:
            self._start_anniversary_monitor()

    def set_main_content(
        self,
        content_type: str,
        image_key: str = None,
        image_path: Path = None,
        img: Optional[Image.Image] = None,
        track_info: str = None,
        **kwargs
    ):
        """Set main content (art or anniversary) for fullscreen display."""
        logger.info(f"Setting main content: {content_type}")

        # Check if this is already displayed on e-ink (no need to re-render)
        if self.eink_display_persistent and image_key and self.current_display_image_key == image_key:
            logger.info(f"Skipping render - image {image_key} already displayed on e-ink")
            return

        # Store main content data
        self.main_content = {
            "content_type": content_type,
            "image_key": image_key,
            "image_path": image_path,
            "img": img,
            "track_info": track_info,
            "timestamp": time.time(),
            **kwargs
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

        try:
            # Determine what to render
            if self.main_content:
                self._render_main_with_overlay()
            elif self.overlay_content:
                self._render_overlay_fullscreen()
            else:
                logger.warning("No content to render")

        except Exception as e:
            logger.error(f"Error rendering display: {e}")
        finally:
            with self.render_lock:
                self.currently_rendering = False

    def _render_main_with_overlay(self):
        """Render main content with optional overlay."""
        # Get main content image
        main_img = self._get_main_content_image()
        if not main_img:
            # Fall back to overlay fullscreen if can't get main content
            if self.overlay_content:
                self._render_overlay_fullscreen()
            return

        # If we have overlay content, composite it
        if self.overlay_content:
            # Create error overlay with configurable size
            overlay_img = self.message_renderer.create_error_overlay(
                self.overlay_content["message"], 
                main_img.size, 
                size_x_percent=self.overlay_config["size_x"],
                size_y_percent=self.overlay_config["size_y"]
            )

            # Composite overlay onto main image
            final_img = main_img.copy()
            # Position overlay in bottom-right corner
            overlay_x = final_img.width - overlay_img.width - 20
            overlay_y = final_img.height - overlay_img.height - 20
            final_img.paste(overlay_img, (overlay_x, overlay_y))
        else:
            final_img = main_img

        # Send to viewer
        content_type = self.main_content["content_type"]
        image_key = self.main_content.get("image_key", content_type)
        track_info = self.main_content.get("track_info", f"{content_type} content")
        
        # Cache the rendered image for web access
        self._cache_rendered_image(final_img, {
            'timestamp': time.time(),
            'content_type': content_type,
            'image_key': image_key,
            'track_info': track_info,
            'has_overlay': bool(self.overlay_content)
        })
        
        self.viewer.update(image_key, self.main_content.get("image_path"), final_img, track_info)
        
        # Track successful render
        if self.main_content.get("image_key"):
            self.current_display_image_key = self.main_content["image_key"]

    def _render_overlay_fullscreen(self):
        """Render overlay fullscreen when no main content available."""
        if not self.overlay_content:
            return
            
        overlay_img = self.message_renderer.create_text_message(
            self.overlay_content["message"]
        )
        
        # Cache the overlay image for web access
        self._cache_rendered_image(overlay_img, {
            'timestamp': time.time(),
            'content_type': 'overlay_fullscreen',
            'image_key': 'overlay_fullscreen',
            'track_info': 'Fullscreen Message',
            'has_overlay': True
        })
        
        self.viewer.update("overlay_fullscreen", None, overlay_img, "Message")

    def _get_main_content_image(self) -> Optional[Image.Image]:
        """Get the image for main content."""
        if not self.main_content:
            return None
            
        content_type = self.main_content["content_type"]
        
        # If image is already provided, use it
        if self.main_content.get("img"):
            return self.main_content["img"]
            
        # For anniversary content, create the image (check BEFORE generic image_path)
        if content_type == "anniversary" and self.anniversary_manager:
            try:
                return self.anniversary_manager.create_anniversary_display(
                    self.main_content, self.image_processor, self.anniversary_config["border"]
                )
            except Exception as e:
                logger.error(f"Failed to create anniversary image: {e}")
                return None
                
        # If image path is provided, load it (for non-anniversary content)
        if self.main_content.get("image_path"):
            try:
                return Image.open(self.main_content["image_path"])
            except Exception as e:
                logger.error(f"Failed to load image from {self.main_content['image_path']}: {e}")
                return None
        
        return None

    def _start_anniversary_monitor(self):
        """Start anniversary monitoring in background thread."""
        def monitor_anniversaries():
            while True:
                try:
                    current_time = time.time()
                    if current_time - self.last_anniversary_check >= self.anniversary_check_interval:
                        self.last_anniversary_check = current_time
                        self._check_anniversaries()
                    time.sleep(10)  # Check every 10 seconds for timing
                except Exception as e:
                    logger.error(f"Error in anniversary monitor: {e}")
                    time.sleep(60)  # Wait longer on error

        anniversary_thread = threading.Thread(target=monitor_anniversaries, daemon=True)
        anniversary_thread.start()
        logger.info("Started anniversary monitoring thread")

    def _check_anniversaries(self):
        """Check for anniversaries and update main content if needed."""
        if not self.anniversary_manager:
            return

        try:
            anniversary = self.anniversary_manager.check_anniversary_if_date_changed()
            if anniversary:
                logger.info(f"Anniversary triggered: {anniversary['name']} - {anniversary['message']}")
                
                # Set anniversary as main content
                self.set_main_content(
                    content_type="anniversary",
                    image_key="anniversary", 
                    track_info=f"Anniversary: {anniversary['message']}",
                    **anniversary
                )
        except Exception as e:
            logger.error(f"Error checking anniversaries: {e}")

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
    
    def _cache_rendered_image(self, image: Optional[Image.Image], metadata: Dict[str, Any]):
        """Cache the rendered image for internal server access."""
        if image:
            self.last_rendered_image = image.copy()
        else:
            self.last_rendered_image = None
        self.last_render_metadata = metadata.copy()
        logger.debug(f"Cached rendered image: {metadata.get('content_type')} - {metadata.get('image_key')}")
    
    def get_current_rendered_image(self) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
        """Get current rendered image and metadata for internal server."""
        return self.last_rendered_image, self.last_render_metadata.copy()
        
    def render_preview(self, config_data: Dict[str, Any]) -> Optional[Image.Image]:
        """Render preview image with temporary configuration changes.
        
        Args:
            config_data: Configuration changes to apply for preview
            
        Returns:
            Preview image or None if preview generation failed
        """
        try:
            logger.info(f"Generating preview with config changes: {list(config_data.keys())}")
            
            # Get the current base image to apply changes to
            base_image = self._get_preview_base_image()
            if not base_image:
                logger.warning("No base image available for preview")
                return None
            
            # Apply different types of configuration changes
            preview_image = base_image.copy()
            
            # Apply image processing effects
            preview_image = self._apply_image_effects_preview(preview_image, config_data)
            
            # Apply position/scaling changes
            preview_image = self._apply_position_preview(preview_image, config_data)
            
            # Handle anniversary changes (if any)
            anniversary_preview = self._apply_anniversary_preview(config_data)
            if anniversary_preview:
                preview_image = anniversary_preview
            
            # Apply overlay if current display has one
            if self.overlay_content:
                preview_image = self._apply_overlay_preview(preview_image, config_data)
            
            logger.debug("Preview image generated successfully")
            return preview_image
                
        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            return None
    
    def _get_preview_base_image(self) -> Optional[Image.Image]:
        """Get the base image for preview generation."""
        if self.last_rendered_image:
            return self.last_rendered_image.copy()
        
        # If no rendered image, try to get the main content image
        if self.main_content:
            return self._get_main_content_image()
        
        return None
    
    def _apply_image_effects_preview(self, image: Image.Image, config_data: Dict[str, Any]) -> Image.Image:
        """Apply image processing effects for preview."""
        try:
            from PIL import ImageEnhance
            
            # Check for image render settings
            brightness = self._get_config_value(config_data, 'IMAGE_RENDER.brightness_adjustment')
            contrast = self._get_config_value(config_data, 'IMAGE_RENDER.contrast_adjustment')
            color = self._get_config_value(config_data, 'IMAGE_RENDER.colour_balance_adjustment')
            sharpness = self._get_config_value(config_data, 'IMAGE_RENDER.sharpness_adjustment')
            
            result_image = image.copy()
            
            # Apply brightness adjustment
            if brightness and float(brightness) != 1.0:
                enhancer = ImageEnhance.Brightness(result_image)
                result_image = enhancer.enhance(float(brightness))
            
            # Apply contrast adjustment
            if contrast and float(contrast) != 1.0:
                enhancer = ImageEnhance.Contrast(result_image)
                result_image = enhancer.enhance(float(contrast))
            
            # Apply color adjustment
            if color and float(color) != 1.0:
                enhancer = ImageEnhance.Color(result_image)
                result_image = enhancer.enhance(float(color))
            
            # Apply sharpness adjustment
            if sharpness and float(sharpness) != 1.0:
                enhancer = ImageEnhance.Sharpness(result_image)
                result_image = enhancer.enhance(float(sharpness))
            
            return result_image
            
        except Exception as e:
            logger.warning(f"Error applying image effects preview: {e}")
            return image
    
    def _apply_position_preview(self, image: Image.Image, config_data: Dict[str, Any]) -> Image.Image:
        """Apply position and scaling changes for preview."""
        try:
            # Check for position settings
            offset_x = self._get_config_value(config_data, 'IMAGE_POSITION.position_offset_x')
            offset_y = self._get_config_value(config_data, 'IMAGE_POSITION.position_offset_y')
            scale_x = self._get_config_value(config_data, 'IMAGE_POSITION.scale_x')
            scale_y = self._get_config_value(config_data, 'IMAGE_POSITION.scale_y')
            rotation = self._get_config_value(config_data, 'IMAGE_POSITION.rotation')
            
            result_image = image.copy()
            
            # Apply rotation
            if rotation and int(rotation) != 0:
                result_image = result_image.rotate(int(rotation), expand=True)
            
            # Apply scaling
            if (scale_x and float(scale_x) != 1.0) or (scale_y and float(scale_y) != 1.0):
                scale_x_val = float(scale_x) if scale_x else 1.0
                scale_y_val = float(scale_y) if scale_y else 1.0
                
                new_width = int(result_image.width * scale_x_val)
                new_height = int(result_image.height * scale_y_val)
                result_image = result_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Apply position offset (create larger canvas and position image)
            if (offset_x and int(offset_x) != 0) or (offset_y and int(offset_y) != 0):
                offset_x_val = int(offset_x) if offset_x else 0
                offset_y_val = int(offset_y) if offset_y else 0
                
                # Create larger canvas
                canvas_width = result_image.width + abs(offset_x_val) * 2
                canvas_height = result_image.height + abs(offset_y_val) * 2
                canvas = Image.new('RGB', (canvas_width, canvas_height), color=(128, 128, 128))
                
                # Position image on canvas
                paste_x = max(0, offset_x_val) + abs(offset_x_val)
                paste_y = max(0, offset_y_val) + abs(offset_y_val)
                canvas.paste(result_image, (paste_x, paste_y))
                result_image = canvas
            
            return result_image
            
        except Exception as e:
            logger.warning(f"Error applying position preview: {e}")
            return image
    
    def _apply_anniversary_preview(self, config_data: Dict[str, Any]) -> Optional[Image.Image]:
        """Generate anniversary preview if anniversary settings changed."""
        try:
            # Check if anniversaries are enabled and if any anniversary data is in config
            anniversary_enabled = self._get_config_value(config_data, 'ANNIVERSARIES.enabled')
            
            # Look for anniversary entries in the form data
            anniversary_entries = {}
            for key, value in config_data.items():
                if key.startswith('anniversary_name_'):
                    index = key.split('_')[-1]
                    name = value
                    date_key = f'anniversary_date_{index}'
                    message_key = f'anniversary_message_{index}'
                    wait_key = f'anniversary_wait_{index}'
                    
                    if (date_key in config_data and message_key in config_data 
                        and wait_key in config_data and name and config_data[date_key]):
                        anniversary_entries[name] = {
                            'date': config_data[date_key],
                            'message': config_data[message_key],
                            'wait_time': config_data[wait_key]
                        }
            
            # If we have anniversary entries, create a preview
            if anniversary_entries and anniversary_enabled == 'true':
                # Use the first anniversary for preview
                first_anniversary = list(anniversary_entries.values())[0]
                
                if self.anniversary_manager:
                    # Create a mock anniversary for preview
                    preview_anniversary = {
                        'name': list(anniversary_entries.keys())[0],
                        'message': first_anniversary['message'],
                        'date': first_anniversary['date']
                    }
                    
                    try:
                        return self.anniversary_manager.create_anniversary_display(
                            {'anniversary': preview_anniversary}, 
                            self.image_processor, 
                            self.anniversary_config.get("border", 10)
                        )
                    except Exception as e:
                        logger.warning(f"Could not create anniversary preview: {e}")
            
            return None
            
        except Exception as e:
            logger.warning(f"Error applying anniversary preview: {e}")
            return None
    
    def _apply_overlay_preview(self, image: Image.Image, config_data: Dict[str, Any]) -> Image.Image:
        """Apply overlay preview if overlay settings changed."""
        try:
            # Check for overlay size settings
            overlay_size_x = self._get_config_value(config_data, 'OVERLAY.size_x')
            overlay_size_y = self._get_config_value(config_data, 'OVERLAY.size_y')
            
            if overlay_size_x or overlay_size_y:
                # Create overlay with new settings
                size_x = int(overlay_size_x) if overlay_size_x else self.overlay_config["size_x"]
                size_y = int(overlay_size_y) if overlay_size_y else self.overlay_config["size_y"]
                
                overlay_img = self.message_renderer.create_error_overlay(
                    self.overlay_content["message"], 
                    image.size, 
                    size_x_percent=size_x,
                    size_y_percent=size_y
                )
                
                # Composite overlay onto image
                result_img = image.copy()
                overlay_x = result_img.width - overlay_img.width - 20
                overlay_y = result_img.height - overlay_img.height - 20
                result_img.paste(overlay_img, (overlay_x, overlay_y))
                return result_img
            
            return image
            
        except Exception as e:
            logger.warning(f"Error applying overlay preview: {e}")
            return image
    
    def _get_config_value(self, config_data: Dict[str, Any], key: str) -> Optional[str]:
        """Get configuration value from config data, handling both flat and nested keys."""
        # Try direct key first
        if key in config_data:
            return config_data[key]
        
        # Try nested key format (SECTION.field)
        if '.' in key:
            section, field = key.split('.', 1)
            nested_key = f"{section}.{field}"
            if nested_key in config_data:
                return config_data[nested_key]
        
        return None
