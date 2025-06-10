"""Centralized render coordinator that manages main content and overlay display."""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

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
