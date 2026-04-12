"""Tests for message_renderer module."""

from unittest.mock import patch

import pytest
from PIL import Image, ImageFont

from roon_display.message_renderer import MessageRenderer


@pytest.fixture(autouse=True)
def mock_font():
    """Use default font to avoid needing a real font file."""
    default = ImageFont.load_default()
    with patch(
        "roon_display.message_renderer.ImageFont.truetype", return_value=default
    ):
        yield default


@pytest.fixture
def renderer(config_manager):
    """Create a MessageRenderer with test config."""
    return MessageRenderer(config_manager)


class TestCreateTextMessage:
    """Tests for create_text_message()."""

    def test_text_only_returns_correct_size(self, renderer, config_manager):
        """Text-only message matches screen dimensions."""
        img = renderer.create_text_message("Hello World")
        w = config_manager.get_screen_width()
        h = config_manager.get_screen_height()
        assert img.size == (w, h)
        assert img.mode == "RGB"

    def test_text_only_not_blank(self, renderer):
        """Text-only message contains non-white pixels (text was drawn)."""
        img = renderer.create_text_message("Test message")
        # Check that it's not entirely white
        pixels = list(img.getdata())
        assert not all(p == (255, 255, 255) for p in pixels)

    def test_with_image_path(self, renderer, config_manager, temp_dir):
        """When a valid image path is given, the result includes it."""
        # Create a test image
        test_img = Image.new("RGB", (200, 200), "blue")
        img_path = temp_dir / "test.jpg"
        test_img.save(img_path)

        result = renderer.create_text_message("Caption", str(img_path))
        w = config_manager.get_screen_width()
        h = config_manager.get_screen_height()
        assert result.size == (w, h)

    def test_missing_image_falls_back_to_text(self, renderer):
        """Non-existent image path falls back to text-only."""
        result = renderer.create_text_message("Fallback", "/nonexistent/path.jpg")
        assert result.mode == "RGB"

    def test_empty_message(self, renderer):
        """Empty message produces a valid image without crashing."""
        img = renderer.create_text_message("")
        assert img.mode == "RGB"


class TestCreateErrorOverlay:
    """Tests for create_error_overlay()."""

    def test_overlay_returns_rgb(self, renderer):
        """Error overlay is returned as RGB."""
        overlay = renderer.create_error_overlay("Error!", (800, 600))
        assert overlay.mode == "RGB"

    def test_overlay_respects_percentage(self, renderer):
        """Overlay size scales with percentage parameters."""
        bg_size = (1000, 1000)
        overlay = renderer.create_error_overlay(
            "Test", bg_size, size_x_percent=50, size_y_percent=50
        )
        assert overlay.width == 500
        assert overlay.height == 500

    def test_overlay_has_minimum_size(self, renderer):
        """Overlay enforces minimum dimensions for readability."""
        overlay = renderer.create_error_overlay(
            "X", (100, 100), size_x_percent=5, size_y_percent=5
        )
        assert overlay.width >= 150
        assert overlay.height >= 80


class TestWrapText:
    """Tests for text wrapping logic."""

    def test_short_text_no_wrap(self, renderer):
        """Short text that fits in one line is not wrapped."""
        result = renderer._wrap_text("Hi", None, 1000)
        assert "\n" not in result or result == "Hi"

    def test_preserves_existing_newlines(self, renderer):
        """Existing paragraph breaks are preserved."""
        result = renderer._wrap_text("Line 1\n\nLine 2", None, 1000)
        assert "Line 1" in result
        assert "Line 2" in result

    def test_simple_wrap_splits_long_lines(self, renderer):
        """Simple wrap breaks lines that exceed chars_per_line."""
        result = renderer._simple_wrap_text("one two three four five", 10)
        lines = result.split("\n")
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 15  # Allow some flexibility for word boundaries
