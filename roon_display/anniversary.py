"""Anniversary message management for the Roon display application."""

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from .utils import get_extra_images_dir, get_last_track_time, set_last_track_time, ensure_anniversary_dir_exists

logger = logging.getLogger(__name__)


class AnniversaryManager:
    """Manages anniversary messages and displays."""

    def __init__(self, anniversaries_config: Dict):
        """Initialize anniversary manager with configuration."""
        self.enabled = anniversaries_config.get("enabled", False)
        self.anniversaries = anniversaries_config.get("anniversaries", [])
        
        # Load last track time from file, default to 1 hour ago if not found
        saved_time = get_last_track_time()
        if saved_time is not None:
            self.last_track_time = saved_time
            logger.info(f"Loaded last track time from file: {saved_time}")
        else:
            self.last_track_time = time.time() - 3600  # 1 hour ago
            logger.info("No saved track time found, defaulting to 1 hour ago")
            
        # Create directories for all configured anniversaries
        for anniversary in self.anniversaries:
            ensure_anniversary_dir_exists(anniversary["name"])
            
# No longer need image rotation tracking since we use random selection

    def update_last_track_time(self):
        """Update the timestamp of the last track change."""
        self.last_track_time = time.time()
        # Save to file for persistence across restarts
        set_last_track_time(self.last_track_time)

    def get_current_anniversary(self) -> Optional[Dict]:
        """Get current anniversary message if conditions are met."""
        if not self.enabled or not self.anniversaries:
            return None

        today = datetime.now()
        current_date = today.strftime("%d/%m")
        current_year = today.year

        for anniversary in self.anniversaries:
            try:
                # Parse date (dd/mm/yyyy format)
                date_parts = anniversary["date"].split("/")
                if len(date_parts) != 3:
                    logger.warning(f"Invalid date format for {anniversary['name']}: {anniversary['date']}")
                    continue

                day, month, year = date_parts
                anniversary_date = f"{day}/{month}"
                
                # Check if today matches the anniversary date
                if current_date == anniversary_date:
                    # Check if enough time has passed since last track
                    time_since_track = (time.time() - self.last_track_time) / 60  # minutes
                    
                    if time_since_track >= anniversary["wait_minutes"]:
                        # Calculate years since the anniversary year
                        years_since = current_year - int(year)
                        
                        # Process message template
                        message = anniversary["message"].replace("${years}", str(years_since))
                        
                        # Get current image for this anniversary
                        image_path = self._get_current_image(anniversary)
                        
                        return {
                            "name": anniversary["name"],
                            "message": message,
                            "image_path": image_path,
                            "years_since": years_since
                        }
            except (ValueError, IndexError) as e:
                logger.warning(f"Error processing anniversary {anniversary['name']}: {e}")
                continue

        return None

    def _get_current_image(self, anniversary: Dict) -> Optional[str]:
        """Get a random image from the anniversary's directory."""
        anniversary_name = anniversary["name"]
        anniversary_dir = get_extra_images_dir() / anniversary_name
        
        if not anniversary_dir.exists():
            logger.warning(f"Anniversary directory not found: {anniversary_dir}")
            return None
        
        # Find all image files in the directory
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        image_files = []
        
        for file_path in anniversary_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                image_files.append(file_path)
        
        if not image_files:
            logger.warning(f"No image files found in {anniversary_dir}")
            return None

        # Choose a random image
        import random
        selected_file = random.choice(image_files)
        
        logger.debug(f"Selected random anniversary image: {selected_file.name} from {anniversary_name}/")
        return str(selected_file)

    def should_display_anniversary(self) -> bool:
        """Check if an anniversary should be displayed now."""
        return self.get_current_anniversary() is not None


    def create_anniversary_display(self, anniversary: Dict, image_processor) -> Image.Image:
        """Create anniversary display image (text or custom image)."""
        image_path = anniversary.get("image_path")
        message = anniversary["message"]
        
        if image_path and Path(image_path).exists():
            # Image + text: image at 1/3 height, text below
            return self._create_image_with_text(image_path, message, image_processor)
        else:
            # Text only: centered on screen
            return self._create_text_only_image(message, image_processor)

    def _create_text_only_image(self, message: str, image_processor) -> Image.Image:
        """Create a text-only image with centered text."""
        width = image_processor.screen_width
        height = image_processor.screen_height
        
        # Create blank image
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Get font
        font = self._get_font(width)
        
        # Calculate text position (centered)
        text_width, text_height = self._get_text_size(draw, message, font)
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Draw text
        draw.text((x, y), message, fill='black', font=font)
        
        return img

    def _create_image_with_text(self, image_path: str, message: str, image_processor) -> Image.Image:
        """Create anniversary display with natural image scaling and text below."""
        screen_width = image_processor.screen_width
        screen_height = image_processor.screen_height
        
        # Create blank canvas
        canvas = Image.new('RGB', (screen_width, screen_height), 'white')
        
        # Define layout parameters
        border_percent = 0.05  # 5% border on top and sides
        text_area_percent = 0.15  # Reserve 15% of height for text area at bottom
        
        # Calculate areas
        border_size = int(screen_width * border_percent)
        text_area_height = int(screen_height * text_area_percent)
        
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
        anniversary_img = anniversary_img.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
        
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
        font = self._get_font(screen_width)
        draw = ImageDraw.Draw(canvas)
        text_width, text_height = self._get_text_size(draw, message, font)
        
        text_x = (screen_width - text_width) // 2
        text_y = screen_height - text_area_height + (text_area_height - text_height) // 2
        
        # Draw image and text
        canvas.paste(anniversary_img, (image_x, image_y))
        draw.text((text_x, text_y), message, fill='black', font=font)
        
        return canvas

    def _get_font(self, screen_width: int):
        """Get appropriate font for the screen size."""
        try:
            font_size = max(24, screen_width // 20)
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.load_default()
            except:
                font = None
        return font

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