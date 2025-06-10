"""Anniversary message management for the Roon display application."""

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from PIL import Image, ImageDraw, ImageFont

from .message_renderer import MessageRenderer
from .utils import (
    ensure_anniversary_dir_exists,
    get_extra_images_dir,
    get_last_track_time,
    set_last_track_time,
)

logger = logging.getLogger(__name__)


class AnniversaryManager:
    """Manages anniversary messages and displays."""

    def __init__(self, config_manager):
        """Initialize anniversary manager with configuration."""
        self.config_manager = config_manager

        # Load last track time from file, default to 1 hour ago if not found
        saved_time = get_last_track_time()
        if saved_time is not None:
            self.last_track_time = saved_time
            logger.info(f"Loaded last track time from file: {saved_time}")
        else:
            self.last_track_time = time.time() - 3600  # 1 hour ago
            logger.info("No saved track time found, defaulting to 1 hour ago")

        # Create directories for all configured anniversaries
        for anniversary in self.config_manager.get_anniversaries_list():
            ensure_anniversary_dir_exists(anniversary["name"])

        # Track when we last checked for anniversaries
        self.last_check_date = None
        self.cached_anniversary_info = None  # Cache anniversary info without image path

    # No longer need image rotation tracking since we use random selection

    def update_last_track_time(self):
        """Update the timestamp of the last track change."""
        self.last_track_time = time.time()
        # Save to file for persistence across restarts
        set_last_track_time(self.last_track_time)


    def _get_current_image(self, anniversary: Dict) -> Optional[str]:
        """Get a random image from the anniversary's directory."""
        anniversary_name = anniversary["name"]
        anniversary_dir = get_extra_images_dir() / anniversary_name

        if not anniversary_dir.exists():
            logger.warning(f"Anniversary directory not found: {anniversary_dir}")
            return None

        # Find all image files in the directory
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tiff",
            ".webp",
            ".avif",
        }
        image_files = []

        for file_path in anniversary_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                # Test if PIL can actually open this format
                try:
                    with Image.open(file_path) as test_img:
                        test_img.verify()  # Check if it's a valid image
                    image_files.append(file_path)
                except Exception as e:
                    logger.warning(f"Skipping unsupported image {file_path.name}: {e}")
                    continue

        if not image_files:
            logger.warning(f"No image files found in {anniversary_dir}")
            return None

        # Choose a random image
        import random

        selected_file = random.choice(image_files)

        # Create relative path for logging
        try:
            relative_path = selected_file.relative_to(Path.cwd())
        except ValueError:
            # If can't make relative, use the name
            relative_path = f"{anniversary_name}/{selected_file.name}"

        logger.info(f"Selected anniversary image: {relative_path}")
        return str(selected_file)


    def check_anniversary_if_date_changed(self) -> Optional[Dict]:
        """Only check for anniversaries if the date has changed since last check."""
        if not self.config_manager.get_anniversaries_enabled():
            return None

        today = datetime.now().date()

        # If we haven't checked today, or date changed, do a fresh anniversary detection
        if self.last_check_date != today:
            logger.debug(
                f"Date changed from {self.last_check_date} to {today}, checking anniversaries"
            )
            self.last_check_date = today
            self.cached_anniversary_info = self._get_anniversary_info_for_today()
        else:
            logger.debug("Date unchanged, using cached anniversary info")

        # If we have an anniversary for today, check if it's ready to display (with fresh image)
        if self.cached_anniversary_info:
            return self._check_anniversary_ready_with_fresh_image(
                self.cached_anniversary_info
            )

        return None

    def _get_anniversary_info_for_today(self) -> Optional[Dict]:
        """Get anniversary info for today (without image path, for caching)."""
        anniversaries_list = self.config_manager.get_anniversaries_list()
        if not anniversaries_list:
            return None

        today = datetime.now()
        current_day = today.day
        current_month = today.month
        current_year = today.year

        for anniversary in anniversaries_list:
            try:
                # Parse date (dd/mm/yyyy format)
                date_parts = anniversary["date"].split("/")
                if len(date_parts) != 3:
                    logger.warning(
                        f"Invalid date format for {anniversary['name']}: {anniversary['date']}"
                    )
                    continue

                day, month, year = date_parts
                anniversary_day = int(day)
                anniversary_month = int(month)

                # Check if today matches the anniversary date
                if (
                    current_day == anniversary_day
                    and current_month == anniversary_month
                ):
                    # Calculate years since the anniversary year
                    years_since = current_year - int(year)

                    # Process message template
                    message = anniversary["message"].replace(
                        "${years}", str(years_since)
                    )

                    # Log that we found this anniversary (only on date change)
                    logger.info(
                        f"Anniversary found: {anniversary['name']} - {message} (wait time: {anniversary['wait_minutes']} minutes)"
                    )

                    return {
                        "name": anniversary["name"],
                        "message": message,
                        "years_since": years_since,
                        "wait_minutes": anniversary["wait_minutes"],
                        "config": anniversary,  # Keep original config for image selection
                    }

            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Error processing anniversary {anniversary['name']}: {e}"
                )
                continue

        # Log if no anniversaries found for today (only on date change)
        logger.info("No anniversaries configured for today")
        return None

    def _check_anniversary_ready_with_fresh_image(
        self, anniversary_info: Dict
    ) -> Optional[Dict]:
        """Check if cached anniversary is ready to display, with fresh image selection."""
        # Check if enough time has passed since last track
        time_since_track = (time.time() - self.last_track_time) / 60  # minutes

        if time_since_track >= anniversary_info["wait_minutes"]:
            logger.debug(f"Anniversary {anniversary_info['name']} ready to display now")

            # Get fresh random image each time
            image_path = self._get_current_image(anniversary_info["config"])

            return {
                "name": anniversary_info["name"],
                "message": anniversary_info["message"],
                "image_path": image_path,
                "years_since": anniversary_info["years_since"],
            }
        else:
            minutes_needed = anniversary_info["wait_minutes"] - time_since_track
            logger.debug(
                f"Anniversary {anniversary_info['name']} waiting - need {minutes_needed:.1f} more minutes"
            )
            return None

    def create_anniversary_display(
        self, anniversary: Dict, image_processor, config_manager
    ) -> Image.Image:
        """Create anniversary display image (text or custom image)."""
        image_path = anniversary.get("image_path")
        message = anniversary["message"]
        

        # Use the reusable message renderer with custom border
        renderer = MessageRenderer(config_manager)
        
        # If there's an image, create image with text using configurable border
        if image_path and Path(image_path).exists():
            return self._create_image_with_text_custom_border(image_path, message, image_processor, config_manager)
        else:
            return renderer.create_text_message(message, image_path)

    def _create_text_only_image(self, message: str, image_processor, config_manager) -> Image.Image:
        """Create a text-only image with centered text."""
        width = config_manager.get_screen_width()
        height = config_manager.get_screen_height()

        # Create blank image
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        # Get font
        font = ImageFont.truetype(config_manager.get_font(), config_manager.get_font_size())

        # Calculate text position (centered)
        text_width, text_height = self._get_text_size(draw, message, font)
        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # Draw text
        draw.text((x, y), message, fill="black", font=font)

        return img

    def _create_image_with_text(
        self, image_path: str, message: str, image_processor, config_manager
    ) -> Image.Image:
        """Create anniversary display with natural image scaling and text below."""
        screen_width = config_manager.get_screen_width()
        screen_height = config_manager.get_screen_height()

        # Create blank canvas
        canvas = Image.new("RGB", (screen_width, screen_height), "white")

        # Define layout parameters from config
        border_fraction = self.config_manager.get_anniversary_border_percent() / 100.0  # Convert to decimal
        text_area_fraction = self.config_manager.get_anniversary_text_percent() / 100.0  # Convert to decimal

        # Calculate areas
        border_size = int(screen_width * border_fraction)
        text_area_height = int(screen_height * text_area_fraction)

        # Image area: screen minus borders and text area
        image_area_width = screen_width - (2 * border_size)
        image_area_height = screen_height - border_size - text_area_height

        # Load and scale image to fit image area (always fill the space well)
        anniversary_img = Image.open(image_path)
        img_ratio = anniversary_img.width / anniversary_img.height
        area_ratio = image_area_width / image_area_height

        # Scale image to fit within the image area boundaries
        if img_ratio > area_ratio:
            # Image is wider - fit to width, height will be smaller
            scaled_width = image_area_width
            scaled_height = int(scaled_width / img_ratio)
            # Ensure we don't exceed height limit
            if scaled_height > image_area_height:
                scaled_height = image_area_height
                scaled_width = int(scaled_height * img_ratio)
        else:
            # Image is taller - fit to height, width will be smaller
            scaled_height = image_area_height
            scaled_width = int(scaled_height * img_ratio)
            # Ensure we don't exceed width limit
            if scaled_width > image_area_width:
                scaled_width = image_area_width
                scaled_height = int(scaled_width / img_ratio)

        # Always resize (expand small images, shrink large ones)
        anniversary_img = anniversary_img.resize(
            (scaled_width, scaled_height), Image.Resampling.LANCZOS
        )

        # Center image in the image area
        image_x = border_size + (image_area_width - scaled_width) // 2
        image_y = border_size + (image_area_height - scaled_height) // 2

        # Debug logging
        logger.debug(f"Screen: {screen_width}x{screen_height}")
        logger.debug(f"Border: {border_size}, Text area: {text_area_height}")
        logger.debug(f"Image area: {image_area_width}x{image_area_height}")
        logger.debug(f"Scaled image: {scaled_width}x{scaled_height}")
        logger.debug(f"Image position: ({image_x}, {image_y})")

        # Position text in the text area at bottom
        font = ImageFont.truetype(config_manager.get_font(), config_manager.get_font_size())
        draw = ImageDraw.Draw(canvas)
        text_width, text_height = self._get_text_size(draw, message, font)

        text_x = (screen_width - text_width) // 2
        text_y = (
            screen_height - text_area_height + (text_area_height - text_height) // 2
        )

        # Draw image and text
        canvas.paste(anniversary_img, (image_x, image_y))
        draw.text((text_x, text_y), message, fill="black", font=font)

        return canvas

    def _create_image_with_text_custom_border(
        self, image_path: str, message: str, image_processor, config_manager
    ) -> Image.Image:
        """Create anniversary display with custom border percentage."""
        # Use effective screen dimensions that respect scale_x/scale_y from config
        effective_width = image_processor.image_width
        effective_height = image_processor.image_height
        full_screen_width = image_processor.screen_width
        full_screen_height = image_processor.screen_height

        # Create blank canvas for full screen
        canvas = Image.new("RGB", (full_screen_width, full_screen_height), "white")
        

        # Define layout parameters using configurable border
        border_fraction = config_manager.get_anniversary_border_percent() / 100.0  # Convert to decimal
        text_area_fraction = self.config_manager.get_anniversary_text_percent() / 100.0  # Convert to decimal

        # Calculate areas within effective screen space
        border_size = int(min(effective_width, effective_height) * border_fraction)
        text_area_height = int(effective_height * text_area_fraction)

        image_area_width = effective_width - 2 * border_size
        image_area_height = effective_height - border_size - text_area_height
        
        # Calculate offset to center effective area on full screen
        offset_x = (full_screen_width - effective_width) // 2 + image_processor.position_offset_x
        offset_y = (full_screen_height - effective_height) // 2 + image_processor.position_offset_y

        try:
            # Load and process image
            anniversary_img = Image.open(image_path)
            if anniversary_img.mode != "RGB":
                anniversary_img = anniversary_img.convert("RGB")

            # Calculate scaling to fit image area while maintaining aspect ratio
            img_width, img_height = anniversary_img.size
            img_ratio = img_width / img_height

            # Scale to fit the available image area
            if img_width > img_height:
                # Image is wider - fit to width
                scaled_width = image_area_width
                scaled_height = int(scaled_width / img_ratio)
                # If height exceeds area, fit to height instead
                if scaled_height > image_area_height:
                    scaled_height = image_area_height
                    scaled_width = int(scaled_height * img_ratio)
            else:
                # Image is taller - fit to height
                scaled_height = image_area_height
                scaled_width = int(scaled_height * img_ratio)
                # If width exceeds area, fit to width instead
                if scaled_width > image_area_width:
                    scaled_width = image_area_width
                    scaled_height = int(scaled_width / img_ratio)

            # Resize image
            anniversary_img = anniversary_img.resize(
                (scaled_width, scaled_height), Image.Resampling.LANCZOS
            )

            # Center image in the image area (within effective screen, then offset to full screen)
            image_x = offset_x + border_size + (image_area_width - scaled_width) // 2
            image_y = offset_y + border_size + (image_area_height - scaled_height) // 2

            # Position text in the text area at bottom (within effective screen, then offset)
            font = ImageFont.truetype(config_manager.get_font(), config_manager.get_font_size())
            draw = ImageDraw.Draw(canvas)
            text_width, text_height = self._get_text_size(draw, message, font)

            text_x = offset_x + (effective_width - text_width) // 2
            text_y = offset_y + (
                effective_height - text_area_height + (text_area_height - text_height) // 2
            )

            # Draw image and text
            canvas.paste(anniversary_img, (image_x, image_y))
            draw.text((text_x, text_y), message, fill="black", font=font)

        except Exception as e:
            logger.warning(f"Could not load anniversary image {image_path}: {e}")
            # Fall back to text-only
            renderer = MessageRenderer(config_manager)
            return renderer.create_text_message(message)

        return canvas


    def _get_text_size(self, draw, text: str, font):
        """Get text dimensions with fallback for different Pillow versions."""
        if font:
            try:
                # Use textbbox for newer Pillow versions
                bbox = draw.textbbox((0, 0), text, font=font)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                # Fallback for older Pillow versions
                return draw.textsize(text, font=font)
        else:
            # Estimate text size without font
            return len(text) * 10, 20
