"""Reusable message rendering for displaying text and images on screen."""

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class MessageRenderer:
    """Handles creation of message display images with text and optional images."""

    def __init__(self, screen_width: int, screen_height: int):
        """Initialize with screen dimensions."""
        self.screen_width = screen_width
        self.screen_height = screen_height

    def create_text_message(
        self, message: str, image_path: Optional[str] = None
    ) -> Image.Image:
        """Create a message display image.

        Args:
            message: Text message to display
            image_path: Optional path to image to display above text

        Returns:
            PIL Image ready for display
        """
        if image_path and Path(image_path).exists():
            return self._create_image_with_text(image_path, message)
        else:
            return self._create_text_only_image(message)

    def _create_text_only_image(self, message: str) -> Image.Image:
        """Create a text-only image with centered text."""
        # Create blank white image
        img = Image.new("RGB", (self.screen_width, self.screen_height), "white")
        draw = ImageDraw.Draw(img)

        # Get font - start with smaller size for better fit
        font = self._get_font_for_text(message)

        # Split message into lines and calculate total height
        lines = message.split("\n")
        line_heights = []
        max_line_width = 0

        for line in lines:
            line_width, line_height = self._get_text_size(draw, line, font)
            line_heights.append(line_height)
            max_line_width = max(max_line_width, line_width)

        # Calculate total text block height (including line spacing)
        line_spacing = max(4, font.size // 8) if font else 4
        total_height = sum(line_heights) + (len(lines) - 1) * line_spacing

        # Center the text block
        start_y = (self.screen_height - total_height) // 2

        # Draw each line centered
        current_y = start_y
        for i, line in enumerate(lines):
            line_width, line_height = self._get_text_size(draw, line, font)
            x = (self.screen_width - line_width) // 2
            draw.text((x, current_y), line, fill="black", font=font)
            current_y += line_height + line_spacing

        return img

    def _create_image_with_text(self, image_path: str, message: str) -> Image.Image:
        """Create display with image above and text below."""
        # Create blank canvas
        canvas = Image.new("RGB", (self.screen_width, self.screen_height), "white")

        # Define layout areas
        border_size = max(20, self.screen_width // 40)
        text_area_height = max(100, self.screen_height // 6)

        image_area_width = self.screen_width - 2 * border_size
        image_area_height = self.screen_height - text_area_height - 2 * border_size

        try:
            # Load and process image
            msg_img = Image.open(image_path)
            if msg_img.mode != "RGB":
                msg_img = msg_img.convert("RGB")

            # Calculate scaling to fit image area
            img_width, img_height = msg_img.size
            img_ratio = img_width / img_height

            if img_width > img_height:
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

            # Resize image
            msg_img = msg_img.resize(
                (scaled_width, scaled_height), Image.Resampling.LANCZOS
            )

            # Center image in the image area
            image_x = border_size + (image_area_width - scaled_width) // 2
            image_y = border_size + (image_area_height - scaled_height) // 2

            # Paste image onto canvas
            canvas.paste(msg_img, (image_x, image_y))

        except Exception as e:
            logger.warning(f"Could not load image {image_path}: {e}")
            # Fall back to text-only if image fails

        # Add text at bottom
        font = self._get_font()
        draw = ImageDraw.Draw(canvas)
        text_width, text_height = self._get_text_size(draw, message, font)

        text_x = (self.screen_width - text_width) // 2
        text_y = (
            self.screen_height
            - text_area_height
            + (text_area_height - text_height) // 2
        )

        draw.text((text_x, text_y), message, fill="black", font=font)

        return canvas

    def _get_font(self):
        """Get appropriate font for the screen size."""
        try:
            font_size = max(24, self.screen_width // 20)
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.load_default()
            except:
                font = None
        return font

    def _get_font_for_text(self, message: str):
        """Get appropriately sized font that fits the message on screen."""
        lines = message.split("\n")
        max_lines = len(lines)

        # Start with smaller font size for multi-line text
        if max_lines > 3:
            base_size = max(16, self.screen_width // 30)
        else:
            base_size = max(20, self.screen_width // 25)

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", base_size)
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
