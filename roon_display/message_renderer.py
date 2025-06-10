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

        # Get font and wrap text to fit screen
        font = self._get_font_for_text(message)
        wrapped_message = self._wrap_text_for_screen(message, font)

        # Split wrapped message into lines and calculate total height
        lines = wrapped_message.split("\n")
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

    def create_error_overlay(
        self, error_message: str, background_size: tuple
    ) -> Image.Image:
        """Create a small error overlay for bottom-right corner.

        Args:
            error_message: Error text to display
            background_size: Size of the background image (width, height)

        Returns:
            PIL Image for the error overlay
        """
        # Calculate overlay size (max 1/3 of background width/height)
        max_width = background_size[0] // 3
        max_height = background_size[1] // 4

        # Minimum overlay size for readability
        min_width = 200
        min_height = 100

        overlay_width = max(min_width, min(max_width, 400))
        overlay_height = max(min_height, min(max_height, 150))

        # Create overlay with semi-transparent white background
        overlay = Image.new(
            "RGBA", (overlay_width, overlay_height), (255, 255, 255, 240)
        )
        draw = ImageDraw.Draw(overlay)

        # Add red border
        border_width = 2
        draw.rectangle(
            [0, 0, overlay_width - 1, overlay_height - 1],
            outline=(255, 0, 0, 255),
            width=border_width,
        )

        # Get smaller font for overlay
        font = self._get_overlay_font(overlay_width)

        # Wrap text to fit overlay
        wrapped_text = self._wrap_text_for_overlay(
            error_message, font, overlay_width - 20
        )

        # Calculate text position (centered)
        text_bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        text_x = (overlay_width - text_width) // 2
        text_y = (overlay_height - text_height) // 2

        # Draw text
        draw.multiline_text(
            (text_x, text_y),
            wrapped_text,
            fill=(0, 0, 0, 255),
            font=font,
            align="center",
        )

        # Convert to RGB for compatibility
        rgb_overlay = Image.new("RGB", (overlay_width, overlay_height), "white")
        rgb_overlay.paste(overlay, mask=overlay.split()[-1])  # Use alpha as mask

        return rgb_overlay

    def _get_overlay_font(self, overlay_width: int):
        """Get appropriately sized font for error overlay."""
        # Scale font size based on overlay width
        base_size = max(12, overlay_width // 20)

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", base_size)
        except (OSError, IOError):
            try:
                font = ImageFont.load_default()
            except:
                font = None
        return font

    def _wrap_text_for_overlay(self, text: str, font, max_width: int) -> str:
        """Wrap text to fit within overlay width."""
        if not font:
            # Simple character-based wrapping fallback
            chars_per_line = max_width // 8  # Estimate
            words = text.split()
            lines = []
            current_line = ""

            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                if len(test_line) <= chars_per_line:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word

            if current_line:
                lines.append(current_line)

            return "\n".join(lines)

        # Use font metrics for accurate wrapping
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_width = self._get_text_size_width(test_line, font)

            if test_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return "\n".join(lines)

    def _get_text_size_width(self, text: str, font) -> int:
        """Get text width using font metrics."""
        if font:
            try:
                # Create temporary draw to measure text
                temp_img = Image.new("RGB", (1, 1), "white")
                temp_draw = ImageDraw.Draw(temp_img)
                bbox = temp_draw.textbbox((0, 0), text, font=font)
                return bbox[2] - bbox[0]
            except AttributeError:
                # Fallback for older Pillow versions
                temp_img = Image.new("RGB", (1, 1), "white")
                temp_draw = ImageDraw.Draw(temp_img)
                return temp_draw.textsize(text, font=font)[0]
        else:
            # Estimate text width without font
            return len(text) * 8

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
        
        # Calculate available space (with margins)
        margin = max(20, self.screen_width // 40)
        available_width = self.screen_width - 2 * margin
        available_height = self.screen_height - 2 * margin
        
        # Start with a reasonable font size based on screen size
        if max_lines > 5:
            start_size = max(12, self.screen_width // 40)
        elif max_lines > 3:
            start_size = max(16, self.screen_width // 35)
        else:
            start_size = max(20, self.screen_width // 30)
        
        # Find the largest font size that fits
        for font_size in range(start_size, 8, -2):  # Try smaller sizes until it fits
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
            except (OSError, IOError):
                try:
                    font = ImageFont.load_default()
                except:
                    font = None
                    break
            
            if self._text_fits_in_bounds(message, font, available_width, available_height):
                return font
        
        # Fallback - use smallest font or None
        try:
            return ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 10)
        except (OSError, IOError):
            try:
                return ImageFont.load_default()
            except:
                return None
    
    def _text_fits_in_bounds(self, message: str, font, available_width: int, available_height: int) -> bool:
        """Check if text with given font fits within the available space."""
        if not font:
            return True  # Can't measure without font, assume it fits
        
        # For this check, we'll use the text as-is since wrapping could cause recursion
        # The actual rendering will handle wrapping
        lines = message.split("\n")
        line_heights = []
        max_line_width = 0
        
        # Create temporary draw to measure text
        temp_img = Image.new("RGB", (1, 1), "white")
        temp_draw = ImageDraw.Draw(temp_img)
        
        for line in lines:
            line_width, line_height = self._get_text_size(temp_draw, line, font)
            line_heights.append(line_height)
            max_line_width = max(max_line_width, line_width)
        
        # Check if width fits (should fit since we wrapped it, but double-check)
        if max_line_width > available_width:
            return False
        
        # Check if height fits (including line spacing)
        line_spacing = max(4, font.size // 8) if hasattr(font, 'size') else 4
        total_height = sum(line_heights) + (len(lines) - 1) * line_spacing
        
        return total_height <= available_height
    
    def _wrap_text_for_screen(self, message: str, font) -> str:
        """Wrap text to fit screen width, respecting existing line breaks."""
        if not font:
            # Simple character-based wrapping fallback
            margin = max(20, self.screen_width // 40)
            chars_per_line = (self.screen_width - 2 * margin) // 8  # Estimate
            return self._simple_wrap_text(message, chars_per_line)
        
        # Calculate available width
        margin = max(20, self.screen_width // 40)
        available_width = self.screen_width - 2 * margin
        
        # Process each paragraph (separated by existing newlines) separately
        paragraphs = message.split("\n")
        wrapped_paragraphs = []
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                wrapped_paragraphs.append("")  # Preserve empty lines
                continue
                
            wrapped_paragraph = self._wrap_paragraph_to_width(paragraph, font, available_width)
            wrapped_paragraphs.append(wrapped_paragraph)
        
        return "\n".join(wrapped_paragraphs)
    
    def _wrap_paragraph_to_width(self, paragraph: str, font, max_width: int) -> str:
        """Wrap a single paragraph to fit within the specified width."""
        words = paragraph.split()
        if not words:
            return ""
        
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_width = self._get_text_size_width(test_line, font)
            
            if test_width <= max_width:
                current_line = test_line
            else:
                # Word doesn't fit, start new line
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # Single word is too long - break it if possible
                    if len(word) > 20:  # Only break very long words
                        # Split long word across lines
                        while word:
                            chars_that_fit = self._find_max_chars_that_fit(word, font, max_width)
                            if chars_that_fit == 0:
                                chars_that_fit = 1  # Take at least one char
                            lines.append(word[:chars_that_fit])
                            word = word[chars_that_fit:]
                        current_line = ""
                    else:
                        current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return "\n".join(lines)
    
    def _find_max_chars_that_fit(self, text: str, font, max_width: int) -> int:
        """Find maximum number of characters that fit within max_width."""
        for i in range(len(text), 0, -1):
            if self._get_text_size_width(text[:i], font) <= max_width:
                return i
        return 0
    
    def _simple_wrap_text(self, text: str, chars_per_line: int) -> str:
        """Simple character-based wrapping fallback when no font is available."""
        paragraphs = text.split("\n")
        wrapped_paragraphs = []
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                wrapped_paragraphs.append("")
                continue
                
            words = paragraph.split()
            lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                if len(test_line) <= chars_per_line:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
            
            wrapped_paragraphs.append("\n".join(lines))
        
        return "\n".join(wrapped_paragraphs)

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
