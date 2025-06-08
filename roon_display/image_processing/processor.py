"""Image processing functions for album art display."""

import logging
import os
from pathlib import Path

from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image processing operations."""

    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self._load_image_settings()

    def _load_image_settings(self):
        """Load image processing settings from config."""
        for name in ["colour_balance", "contrast", "sharpness", "brightness"]:
            attr_name = f"{name}_adjustment"
            setattr(
                self,
                attr_name,
                float(self.config.get("IMAGE_RENDER", f"{name}_adjustment")),
            )

        self.position_offset_x = int(
            self.config.get("IMAGE_POSITION", "position_offset_x")
        )
        self.position_offset_y = int(
            self.config.get("IMAGE_POSITION", "position_offset_y")
        )
        self.scale_x = float(self.config.get("IMAGE_POSITION", "scale_x"))
        self.scale_y = float(self.config.get("IMAGE_POSITION", "scale_y"))
        self.rotation = float(self.config.get("IMAGE_POSITION", "rotation"))

        if self.scale_x == 0 or self.scale_y == 0:
            logger.error("Scale must not be set to zero! Check config file")
            raise ValueError("Scale values cannot be zero")

    def set_screen_size(self, width, height):
        """Set the target screen dimensions."""
        self.screen_width = int(width)
        self.screen_height = int(height)
        self.image_width = int(width * self.scale_x)
        self.image_height = int(height * self.scale_y)
        self.image_size = min(self.image_width, self.image_height)

    def fetch_image(self, image_path):
        """Load an image from file path."""
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Couldn't find image file {image_path}")
            return None

        try:
            img = Image.open(image_path)
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
        if self.rotation == 90:
            return img.transpose(Image.ROTATE_90)
        elif self.rotation == 180:
            return img.transpose(Image.ROTATE_180)
        elif self.rotation == 270:
            return img.transpose(Image.ROTATE_270)
        return img

    def resize_image(self, img):
        """Resize image to fit screen while maintaining aspect ratio."""
        img_width, img_height = img.size

        # Check if we need to resize
        if (
            img_width != self.image_width
            or img_height != self.screen_height
            or self.scale_x != self.scale_y
        ):
            logger.debug("Resizing image")
            scale_ratio = max(self.scale_x, self.scale_y)
            new_width = int(img_width * self.scale_x * scale_ratio)
            new_height = int(img_height * self.scale_y * scale_ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)

        return img

    def pad_image_to_size(self, img):
        """Pad image to target screen size with white background."""
        logger.debug("Padding image")

        original_width, original_height = img.size

        # Create new white background
        new_image = Image.new(
            "RGB", (self.screen_width, self.screen_height), color="white"
        )

        # Calculate paste position (centered with offset)
        paste_x = self.position_offset_x + (self.screen_width - original_width) // 2
        paste_y = self.position_offset_y + (self.screen_height - original_height) // 2

        # Paste original image onto background
        new_image.paste(img, (paste_x, paste_y))

        return new_image

    def process_image_position(self, img):
        """Apply position processing: rotation, scaling, and padding."""
        logger.debug("Starting to process image position")

        # Apply rotation
        img = self.apply_rotation(img)

        # Resize if needed
        img = self.resize_image(img)

        # Pad to screen size if needed
        if img.size != (self.screen_width, self.screen_height):
            img = self.pad_image_to_size(img)

        return img

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

            # Apply enhancements
            if self.colour_balance_adjustment != 1:
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(self.colour_balance_adjustment)

            if self.contrast_adjustment != 1:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(self.contrast_adjustment)

            if self.brightness_adjustment != 1:
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(self.brightness_adjustment)

            if self.sharpness_adjustment != 1:
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(self.sharpness_adjustment)

            logger.debug("Image enhancement completed successfully")
            return img

        except Exception as e:
            logger.error(f"Error during image enhancement: {str(e)}")
            return img

    def needs_enhancement(self):
        """Check if any image enhancements are configured."""
        return not (
            self.contrast_adjustment == 1
            and self.colour_balance_adjustment == 1
            and self.brightness_adjustment == 1
            and self.sharpness_adjustment == 1
        )
