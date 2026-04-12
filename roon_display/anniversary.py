"""Anniversary message management for the Roon display application."""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from .message_renderer import MessageRenderer
from .utils import (
    ensure_anniversary_dir_exists,
    get_extra_images_dir,
    get_last_track_time,
    get_text_size,
    scale_image_to_fit,
    set_last_track_time,
)

if TYPE_CHECKING:
    from .config.config_manager import ConfigManager
    from .image_processing.processor import ImageProcessor

logger = logging.getLogger(__name__)


class AnniversaryManager:
    """Manages anniversary messages and displays."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize anniversary manager with configuration."""
        self.config_manager = config_manager
        self.render_coordinator: Any = None

        self.last_anniversary_check: float = 0.0

        saved_time = get_last_track_time()
        if saved_time is not None:
            self.last_track_time = saved_time
            logger.info(f"Loaded last track time from file: {saved_time}")
        else:
            self.last_track_time = time.time() - 3600
            logger.info("No saved track time found, defaulting to 1 hour ago")

        for anniversary in self.config_manager.get_anniversaries_list():
            ensure_anniversary_dir_exists(anniversary["name"])

        self.last_check_date: Optional[Any] = None
        self.cached_anniversary_info: Optional[Dict[str, Any]] = None

    def update_last_track_time(self) -> None:
        """Update the timestamp of the last track change."""
        self.last_track_time = time.time()
        set_last_track_time(self.last_track_time)

    def _get_current_image(self, anniversary: Dict[str, Any]) -> Optional[str]:
        """Get a random image from the anniversary's directory."""
        anniversary_name = anniversary["name"]
        anniversary_dir = get_extra_images_dir() / anniversary_name

        if not anniversary_dir.exists():
            logger.warning(f"Anniversary directory not found: {anniversary_dir}")
            return None

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
        image_files: List[Path] = []

        for file_path in anniversary_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                try:
                    with Image.open(file_path) as test_img:
                        test_img.verify()
                    image_files.append(file_path)
                except Exception as e:
                    logger.warning(f"Skipping unsupported image {file_path.name}: {e}")
                    continue

        if not image_files:
            logger.warning(f"No image files found in {anniversary_dir}")
            return None

        selected_file = random.choice(image_files)

        try:
            relative_path: Any = selected_file.relative_to(Path.cwd())
        except ValueError:
            relative_path = f"{anniversary_name}/{selected_file.name}"

        logger.info(f"Selected anniversary image: {relative_path}")
        return str(selected_file)

    def check_anniversary_if_date_changed(self) -> Optional[Dict[str, Any]]:
        """Only check for anniversaries if the date has changed since last check."""
        if not self.config_manager.get_anniversaries_enabled():
            return None

        today = datetime.now().date()

        if self.last_check_date != today:
            logger.debug(
                f"Date changed from {self.last_check_date} to {today}, checking anniversaries"
            )
            self.last_check_date = today
            self.cached_anniversary_info = self._get_anniversary_info_for_today()
        else:
            logger.debug("Date unchanged, using cached anniversary info")

        if self.cached_anniversary_info:
            return self._check_anniversary_ready_with_fresh_image(
                self.cached_anniversary_info
            )

        return None

    def _get_anniversary_info_for_today(self) -> Optional[Dict[str, Any]]:
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
                date_parts = anniversary["date"].split("/")
                if len(date_parts) != 3:
                    logger.warning(
                        f"Invalid date format for {anniversary['name']}: {anniversary['date']}"
                    )
                    continue

                day, month, year = date_parts
                anniversary_day = int(day)
                anniversary_month = int(month)

                if (
                    current_day == anniversary_day
                    and current_month == anniversary_month
                ):
                    years_since = current_year - int(year)

                    message = anniversary["message"].replace(
                        "${years}", str(years_since)
                    )

                    logger.info(
                        f"Anniversary found: {anniversary['name']} - {message} (wait time: {anniversary['wait_minutes']} minutes)"
                    )

                    return {
                        "name": anniversary["name"],
                        "message": message,
                        "years_since": years_since,
                        "wait_minutes": anniversary["wait_minutes"],
                        "config": anniversary,
                    }

            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Error processing anniversary {anniversary['name']}: {e}"
                )
                continue

        logger.info("No anniversaries configured for today")
        return None

    def _check_anniversary_ready_with_fresh_image(
        self, anniversary_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check if cached anniversary is ready to display, with fresh image selection."""
        time_since_track = (time.time() - self.last_track_time) / 60

        if time_since_track >= anniversary_info["wait_minutes"]:
            logger.debug(f"Anniversary {anniversary_info['name']} ready to display now")

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
        self,
        anniversary: Dict[str, Any],
        image_processor: ImageProcessor,
        config_manager: ConfigManager,
    ) -> Image.Image:
        """Create anniversary display image (text or custom image)."""
        logger.debug(
            f"create_anniversary_display called with anniversary: {anniversary}"
        )

        image_path = anniversary.get("image_path")
        message = anniversary["message"]

        logger.debug(f"Anniversary image_path: {image_path}")
        logger.debug(f"Anniversary message: {message}")

        renderer = MessageRenderer(config_manager)

        if image_path and Path(image_path).exists():
            logger.debug(f"Image path exists, creating image with text: {image_path}")
            return self._create_image_with_text_custom_border(
                image_path, message, image_processor, config_manager
            )
        else:
            logger.debug(
                "No image path or path doesn't exist, creating text-only message"
            )
            logger.debug(
                f"Image path check - path: {image_path}, exists: {Path(image_path).exists() if image_path else 'N/A'}"
            )
            return renderer.create_text_message(message, image_path)

    def _create_image_with_text_custom_border(
        self,
        image_path: str,
        message: str,
        image_processor: ImageProcessor,
        config_manager: ConfigManager,
    ) -> Image.Image:
        """Create anniversary display with custom border percentage."""
        full_screen_width = image_processor.screen_width
        full_screen_height = image_processor.screen_height
        effective_width = int(full_screen_width * config_manager.get_scale_x())
        effective_height = int(full_screen_height * config_manager.get_scale_y())

        canvas = Image.new("RGB", (full_screen_width, full_screen_height), "white")

        border_fraction = config_manager.get_anniversary_border_percent() / 100.0
        text_area_fraction = self.config_manager.get_anniversary_text_percent() / 100.0

        border_size = int(min(effective_width, effective_height) * border_fraction)
        text_area_height = int(effective_height * text_area_fraction)

        image_area_width = effective_width - 2 * border_size
        image_area_height = effective_height - border_size - text_area_height

        offset_x = (
            full_screen_width - effective_width
        ) // 2 + config_manager.get_image_offset_x()
        offset_y = (
            full_screen_height - effective_height
        ) // 2 + config_manager.get_image_offset_y()

        try:
            anniversary_img: Image.Image = Image.open(image_path)
            if anniversary_img.mode != "RGB":
                anniversary_img = anniversary_img.convert("RGB")

            scaled_width, scaled_height = scale_image_to_fit(
                anniversary_img.width,
                anniversary_img.height,
                image_area_width,
                image_area_height,
            )

            anniversary_img = anniversary_img.resize(
                (scaled_width, scaled_height), Image.Resampling.LANCZOS
            )

            image_x = offset_x + border_size + (image_area_width - scaled_width) // 2
            image_y = offset_y + border_size + (image_area_height - scaled_height) // 2

            font = ImageFont.truetype(
                config_manager.get_font(), config_manager.get_font_size()
            )
            draw = ImageDraw.Draw(canvas)
            text_width, text_height = get_text_size(draw, message, font)

            text_x = offset_x + (effective_width - text_width) // 2
            text_y = offset_y + (
                effective_height
                - text_area_height
                + (text_area_height - text_height) // 2
            )

            canvas.paste(anniversary_img, (image_x, image_y))
            draw.text((text_x, text_y), message, fill="black", font=font)

        except Exception as e:
            logger.warning(f"Could not load anniversary image {image_path}: {e}")
            renderer = MessageRenderer(config_manager)
            return renderer.create_text_message(message)

        return canvas

    def start_anniversary_monitor(self, render_coordinator: Any) -> None:
        """Start anniversary monitoring in background thread."""
        self.render_coordinator = render_coordinator

        def monitor_anniversaries() -> None:
            while True:
                try:
                    current_time = time.time()
                    anniversary_check_interval = (
                        self.config_manager.get_anniversary_check_interval()
                    )
                    if (
                        current_time - self.last_anniversary_check
                        >= anniversary_check_interval
                    ):
                        self.last_anniversary_check = current_time
                        self._check_anniversaries()
                        # TODO magic number
                    time.sleep(10)
                except Exception as e:
                    logger.error(f"Error in anniversary monitor: {e}")
                    time.sleep(self.config_manager.get_reconnection_interval())

        anniversary_thread = threading.Thread(target=monitor_anniversaries, daemon=True)
        anniversary_thread.start()
        logger.info("Started anniversary monitoring thread")

    def _check_anniversaries(self) -> None:
        """Check for anniversaries and update main content if needed."""
        try:
            anniversary = self.check_anniversary_if_date_changed()
            if anniversary:
                logger.info(
                    f"Anniversary triggered: {anniversary['name']} - {anniversary['message']}"
                )

                self.render_coordinator.set_art(
                    content_type="anniversary",
                    image_key="anniversary",
                    track_info=f"Anniversary: {anniversary['message']}",
                    **anniversary,
                )
        except Exception as e:
            logger.error(f"Error checking anniversaries: {e}")
