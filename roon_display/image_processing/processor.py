"""Image processing functions for album art display."""

import logging
import os
from pathlib import Path

from PIL import Image, ImageEnhance

from ..utils import log_performance

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image processing operations."""

    def __init__(self, config_manager):
        """Initialize with configuration manager."""
        self.config_manager = config_manager

        # Validate scale values at initialization
        scale_x = self.config_manager.get_scale_x()
        scale_y = self.config_manager.get_scale_y()
        if scale_x == 0 or scale_y == 0:
            logger.error("Scale must not be set to zero! Check config file")
            raise ValueError("Scale values cannot be zero")


    @log_performance(threshold=0.5, description="Image file loading")
    def fetch_image(self, image_path):
        """Load an image from file path."""
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Couldn't find image file {image_path}")
            return None

        try:
            img = Image.open(image_path)
            logger.info(f"IMAGESIZE: Loaded image {image_path} with size {img.size}")
            return img
        except Exception as e:
            logger.error(f"Couldn't read image file {image_path}, error: {e}")
            try:
                os.remove(image_path)
            except OSError:
                pass
            raise FileNotFoundError(f"Could not load image: {e}")

    def apply_rotation(self, img):
        """Apply rotation to image based on config."""
        rotation = self.config_manager.get_rotation()
        logger.info(f"IMAGESIZE: Before rotation: {img.size}, rotation={rotation}")
        if rotation == 90:
            result = img.transpose(Image.ROTATE_90)
        elif rotation == 180:
            result = img.transpose(Image.ROTATE_180)
        elif rotation == 270:
            result = img.transpose(Image.ROTATE_270)
        else:
            result = img
        logger.info(f"IMAGESIZE: After rotation: {result.size}")
        return result

    @log_performance(threshold=0.5, description="Image resizing")
    def resize_image(self, img):
        """Resize image to fit screen while maintaining aspect ratio."""
        img_width, img_height = img.size
        screen_width = self.config_manager.get_screen_width()
        screen_height = self.config_manager.get_screen_height()
        scale_x = self.config_manager.get_scale_x()
        scale_y = self.config_manager.get_scale_y()
        
        target_width = int(screen_width * scale_x)
        target_height = int(screen_height * scale_y)
        
        logger.info(f"IMAGESIZE: Before resize: {img.size}, target screen: {screen_width}x{screen_height}")
        logger.info(f"IMAGESIZE: Target image size: {target_width}x{target_height}")

        # Check if we need to resize
        if (
            img_width != target_width
            or img_height != target_height
            or scale_x != scale_y
        ):
            logger.info("IMAGESIZE: Resizing image")
            new_width = int(img_width * scale_x)
            new_height = int(img_height * scale_y)
            logger.info(f"IMAGESIZE: Calculated resize to: {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.LANCZOS)
            logger.info(f"IMAGESIZE: After resize: {img.size}")
        else:
            logger.info("IMAGESIZE: No resize needed")

        return img

    def pad_image_to_size(self, img):
        """Pad image to target screen size with white background."""
        logger.debug("Padding image")

        original_width, original_height = img.size

        # Get live config values
        screen_width = self.config_manager.get_screen_width()
        screen_height = self.config_manager.get_screen_height()
        offset_x = self.config_manager.get_position_offset_x()
        offset_y = self.config_manager.get_position_offset_y()

        # Create new white background
        new_image = Image.new(
            "RGB", (screen_width, screen_height), color="white"
        )

        # Calculate paste position (centered with offset)
        paste_x = offset_x + (screen_width - original_width) // 2
        paste_y = offset_y + (screen_height - original_height) // 2

        # Paste original image onto background
        new_image.paste(img, (paste_x, paste_y))

        return new_image

    @log_performance(threshold=0.5, description="Image position processing")
    def process_image_position(self, img):
        """Apply position processing: rotation, scaling, and padding."""
        logger.debug("Starting to process image position")

        # Apply rotation
        img = self.apply_rotation(img)

        # Resize if needed
        img = self.resize_image(img)

        # Pad to screen size if needed
        screen_width = self.config_manager.get_screen_width()
        screen_height = self.config_manager.get_screen_height()
        if img.size != (screen_width, screen_height):
            img = self.pad_image_to_size(img)

        return img

    @log_performance(threshold=0.5, description="Image enhancements")
    def apply_enhancements(self, img):
        """Apply color/contrast/brightness/sharpness adjustments."""
        logger.debug("Starting image enhancement")

        # Validate input
        if not hasattr(img, "mode") or not callable(getattr(img, "convert", None)):
            logger.error(f"Input is not a valid PIL Image: {type(img)}")
            return img

        try:
            # TODO: This copy may be unnecessary since PIL enhance() methods return new images
            # Consider removing after testing - would improve performance and memory usage
            img = img.copy()

            # Apply enhancements using live config values
            colour_balance = self.config_manager.get_colour_balance_adjustment()
            if colour_balance != 1:
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(colour_balance)

            contrast = self.config_manager.get_contrast_adjustment()
            if contrast != 1:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(contrast)

            brightness = self.config_manager.get_brightness_adjustment()
            if brightness != 1:
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(brightness)

            sharpness = self.config_manager.get_sharpness_adjustment()
            if sharpness != 1:
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(sharpness)

            logger.debug("Image enhancement completed successfully")
            return img

        except Exception as e:
            logger.error(f"Error during image enhancement: {str(e)}")
            return img

