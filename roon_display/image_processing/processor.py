"""Image processing functions for album art display."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PIL import Image, ImageEnhance

from ..utils import log_performance

if TYPE_CHECKING:
    from ..config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image processing operations."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize with configuration manager."""
        self.config_manager = config_manager

        scale_x = self.config_manager.get_scale_x()
        scale_y = self.config_manager.get_scale_y()
        if scale_x == 0 or scale_y == 0:
            logger.error("Scale must not be set to zero! Check config file")
            raise ValueError("Scale values cannot be zero")

    @property
    def screen_width(self) -> int:
        """Current screen width from config manager."""
        return self.config_manager.get_screen_width()

    @property
    def screen_height(self) -> int:
        """Current screen height from config manager."""
        return self.config_manager.get_screen_height()

    def set_screen_size(self, width: int, height: int) -> None:
        """Set screen dimensions in config manager."""
        self.config_manager.set_screen_width(width)
        self.config_manager.set_screen_height(height)

    def needs_enhancement(self) -> bool:
        """Return True if any image enhancement value differs from 1.0."""
        return any(
            v != 1.0
            for v in [
                self.config_manager.get_color_enhance(),
                self.config_manager.get_contrast(),
                self.config_manager.get_brightness(),
                self.config_manager.get_sharpness(),
            ]
        )

    @log_performance(threshold=0.5, description="Image file loading")
    def fetch_image(self, image_path: Any) -> Optional[Image.Image]:
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

    def prepare(
        self,
        img: Optional[Image.Image],
        image_path: Optional[Any],
    ) -> Optional[Image.Image]:
        """Load (if needed) and produce a display-ready canvas.

        Single entry point for turning raw album art into a fully-processed,
        screen-sized image.  Pass either a PIL Image or a file path; loading,
        scaling, rotation, enhancements, and canvas composition all happen here.

        During preview rendering, config values are automatically overridden
        via config_manager.preview_overrides() — no explicit parameter needed.

        Args:
            img: Pre-loaded PIL Image, or None to load from image_path.
            image_path: Path to load from when img is None.

        Returns:
            A display-ready PIL Image at screen dimensions, or None on failure.
        """
        if img is None:
            if image_path is None:
                logger.error("prepare(): no image or path provided")
                return None
            img = self.fetch_image(image_path)
            if img is None:
                return None

        screen_width = self.config_manager.get_screen_width()
        screen_height = self.config_manager.get_screen_height()
        scale_x = self.config_manager.get_scale_x()
        scale_y = self.config_manager.get_scale_y()
        rotation = str(self.config_manager.get_rotation())
        offset_x = self.config_manager.get_image_offset_x()
        offset_y = self.config_manager.get_image_offset_y()
        color_enhance = self.config_manager.get_color_enhance()
        contrast = self.config_manager.get_contrast()
        brightness = self.config_manager.get_brightness()
        sharpness = self.config_manager.get_sharpness()

        canvas = Image.new("RGB", (screen_width, screen_height), "white")

        # Fit source image into the target size in one LANCZOS pass
        original_width, original_height = img.size
        canvas_size = min(screen_width, screen_height)
        target_w = int(canvas_size * scale_x)
        target_h = int(canvas_size * scale_y)
        processed = img.copy().resize((target_w, target_h), Image.Resampling.LANCZOS)
        logger.debug(
            f"Fitted image: {original_width}x{original_height} → {target_w}x{target_h}"
        )

        if rotation == "90":
            processed = processed.transpose(Image.Transpose.ROTATE_90)
        elif rotation == "180":
            processed = processed.transpose(Image.Transpose.ROTATE_180)
        elif rotation == "270":
            processed = processed.transpose(Image.Transpose.ROTATE_270)
        if rotation != "0":
            logger.debug(f"Rotated {rotation}°: {processed.size}")

        if color_enhance != 1.0:
            processed = ImageEnhance.Color(processed).enhance(color_enhance)
        if contrast != 1.0:
            processed = ImageEnhance.Contrast(processed).enhance(contrast)
        if brightness != 1.0:
            processed = ImageEnhance.Brightness(processed).enhance(brightness)
        if sharpness != 1.0:
            processed = ImageEnhance.Sharpness(processed).enhance(sharpness)

        iw, ih = processed.size
        final_x = (screen_width - iw) // 2 + offset_x
        final_y = (screen_height - ih) // 2 + offset_y
        canvas.paste(processed, (final_x, final_y))

        logger.debug(
            f"Canvas: {screen_width}x{screen_height}, image at ({final_x},{final_y}), "
            f"scale=({scale_x},{scale_y}), rotation={rotation}°, offset=({offset_x},{offset_y})"
        )
        return canvas

    def apply_rotation(self, img: Image.Image) -> Image.Image:
        """Apply rotation to image based on config."""
        rotation = self.config_manager.get_rotation()
        if rotation == 90:
            result = img.transpose(Image.Transpose.ROTATE_90)
        elif rotation == 180:
            result = img.transpose(Image.Transpose.ROTATE_180)
        elif rotation == 270:
            result = img.transpose(Image.Transpose.ROTATE_270)
        else:
            result = img

        if result.size != img.size:
            logger.debug(f"IMAGESIZE: Rotated {rotation}°: {img.size} → {result.size}")

        return result

    @log_performance(threshold=0.5, description="Image resizing")
    def resize_image(self, img: Image.Image) -> Image.Image:
        """Resize image to fit screen while maintaining aspect ratio."""
        img_width, img_height = img.size
        screen_width = self.config_manager.get_screen_width()
        screen_height = self.config_manager.get_screen_height()
        scale_x = self.config_manager.get_scale_x()
        scale_y = self.config_manager.get_scale_y()

        target_width = int(screen_width * scale_x)
        target_height = int(screen_height * scale_y)

        scale_factor_x = target_width / img_width
        scale_factor_y = target_height / img_height
        scale_factor = min(scale_factor_x, scale_factor_y)

        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)

        if new_width != img_width or new_height != img_height:
            logger.debug(
                f"IMAGESIZE: Resized {img.size} → {new_width}x{new_height} "
                f"(screen: {screen_width}x{screen_height}, scale: {scale_x}x{scale_y}, factor: {scale_factor:.3f})"
            )
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return img

    def pad_image_to_size(self, img: Image.Image) -> Image.Image:
        """Pad image to target screen size with white background."""
        logger.debug("Padding image")

        original_width, original_height = img.size

        screen_width = self.config_manager.get_screen_width()
        screen_height = self.config_manager.get_screen_height()
        offset_x = self.config_manager.get_image_offset_x()
        offset_y = self.config_manager.get_image_offset_y()

        new_image = Image.new("RGB", (screen_width, screen_height), color="white")

        paste_x = offset_x + (screen_width - original_width) // 2
        paste_y = offset_y + (screen_height - original_height) // 2

        new_image.paste(img, (paste_x, paste_y))

        return new_image

    @log_performance(threshold=0.5, description="Image position processing")
    def process_image_position(self, img: Image.Image) -> Image.Image:
        """Apply position processing: rotation, scaling, and padding."""
        logger.debug("Starting to process image position")

        img = self.apply_rotation(img)
        img = self.resize_image(img)

        screen_width = self.config_manager.get_screen_width()
        screen_height = self.config_manager.get_screen_height()
        if img.size != (screen_width, screen_height):
            img = self.pad_image_to_size(img)

        return img

    @log_performance(threshold=0.5, description="Image enhancements")
    def apply_enhancements(self, img: Image.Image) -> Image.Image:
        """Apply color/contrast/brightness/sharpness adjustments."""
        logger.debug("Starting image enhancement")

        if not hasattr(img, "mode") or not callable(getattr(img, "convert", None)):
            logger.error(f"Input is not a valid PIL Image: {type(img)}")
            return img

        try:
            color_enhance = self.config_manager.get_color_enhance()
            if color_enhance != 1:
                img = ImageEnhance.Color(img).enhance(color_enhance)

            contrast = self.config_manager.get_contrast()
            if contrast != 1:
                img = ImageEnhance.Contrast(img).enhance(contrast)

            brightness = self.config_manager.get_brightness()
            if brightness != 1:
                img = ImageEnhance.Brightness(img).enhance(brightness)

            sharpness = self.config_manager.get_sharpness()
            if sharpness != 1:
                img = ImageEnhance.Sharpness(img).enhance(sharpness)

            logger.debug("Image enhancement completed successfully")
            return img

        except Exception as e:
            logger.error(f"Error during image enhancement: {str(e)}")
            return img
