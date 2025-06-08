"""Tests for image processing functionality."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from roon_display.image_processing.processor import ImageProcessor


class TestImageProcessor:
    """Test ImageProcessor class."""

    @pytest.fixture
    def image_processor(self, config_manager):
        """Create ImageProcessor instance for testing."""
        return ImageProcessor(config_manager.config)

    def test_initialization(self, image_processor):
        """Test ImageProcessor initialization."""
        assert image_processor.colour_balance_adjustment == 1.0
        assert image_processor.contrast_adjustment == 1.2
        assert image_processor.sharpness_adjustment == 1.1
        assert image_processor.brightness_adjustment == 0.9
        assert image_processor.position_offset_x == 10
        assert image_processor.position_offset_y == 20
        assert image_processor.scale_x == 0.8
        assert image_processor.scale_y == 0.9
        assert image_processor.rotation == 90

    def test_initialization_zero_scale_raises_error(self, temp_dir, sample_config):
        """Test that zero scale values raise ValueError."""
        sample_config["IMAGE_POSITION"]["scale_x"] = "0"

        config_path = temp_dir / "zero_scale.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        from roon_display.config.config_manager import ConfigManager

        config_manager = ConfigManager(config_path)

        with pytest.raises(ValueError, match="Scale values cannot be zero"):
            ImageProcessor(config_manager.config)

    def test_set_screen_size(self, image_processor):
        """Test setting screen size."""
        image_processor.set_screen_size(800, 600)

        assert image_processor.screen_width == 800
        assert image_processor.screen_height == 600
        assert image_processor.image_width == int(800 * 0.8)  # scale_x = 0.8
        assert image_processor.image_height == int(600 * 0.9)  # scale_y = 0.9
        assert image_processor.image_size == min(640, 540)  # min of above

    def test_fetch_image_success(self, image_processor, temp_dir, sample_image):
        """Test successful image loading."""
        image_path = temp_dir / "test_image.jpg"
        sample_image.save(image_path)

        result = image_processor.fetch_image(image_path)

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size

    def test_fetch_image_file_not_found(self, image_processor, temp_dir):
        """Test loading non-existent image."""
        image_path = temp_dir / "nonexistent.jpg"

        result = image_processor.fetch_image(image_path)

        assert result is None

    def test_fetch_image_invalid_file(self, image_processor, temp_dir):
        """Test loading invalid image file."""
        image_path = temp_dir / "invalid.jpg"
        image_path.write_text("This is not an image")

        with pytest.raises(FileNotFoundError):
            image_processor.fetch_image(image_path)

        # File should be deleted after failed load
        assert not image_path.exists()

    @patch("os.remove")
    def test_fetch_image_cleanup_fails_silently(
        self, mock_remove, image_processor, temp_dir
    ):
        """Test that cleanup failure doesn't crash the application."""
        image_path = temp_dir / "invalid.jpg"
        image_path.write_text("This is not an image")
        mock_remove.side_effect = OSError("Permission denied")

        with pytest.raises(FileNotFoundError):
            image_processor.fetch_image(image_path)

    def test_apply_rotation_90(self, image_processor, sample_image):
        """Test 90-degree rotation."""
        image_processor.rotation = 90
        result = image_processor.apply_rotation(sample_image)

        # 90-degree rotation swaps width and height
        assert result.size == (sample_image.size[1], sample_image.size[0])

    def test_apply_rotation_180(self, image_processor, sample_image):
        """Test 180-degree rotation."""
        image_processor.rotation = 180
        result = image_processor.apply_rotation(sample_image)

        # 180-degree rotation preserves dimensions
        assert result.size == sample_image.size

    def test_apply_rotation_270(self, image_processor, sample_image):
        """Test 270-degree rotation."""
        image_processor.rotation = 270
        result = image_processor.apply_rotation(sample_image)

        # 270-degree rotation swaps width and height
        assert result.size == (sample_image.size[1], sample_image.size[0])

    def test_apply_rotation_none(self, image_processor, sample_image):
        """Test no rotation (0 degrees)."""
        image_processor.rotation = 0
        result = image_processor.apply_rotation(sample_image)

        # No rotation should return same image
        assert result.size == sample_image.size

    def test_resize_image_no_resize_needed(self, image_processor, sample_image):
        """Test resize when image is already correct size."""
        image_processor.set_screen_size(100, 100)
        image_processor.image_width = 100
        image_processor.screen_height = 100
        image_processor.scale_x = 1.0
        image_processor.scale_y = 1.0

        result = image_processor.resize_image(sample_image)
        assert result.size == sample_image.size

    def test_resize_image_resize_needed(self, image_processor, sample_image):
        """Test resize when image needs resizing."""
        image_processor.set_screen_size(200, 150)

        result = image_processor.resize_image(sample_image)

        # Should be resized according to scale factors
        expected_width = int(
            sample_image.size[0] * 0.8 * 0.9
        )  # scale_x * max(scale_x, scale_y)
        expected_height = int(
            sample_image.size[1] * 0.9 * 0.9
        )  # scale_y * max(scale_x, scale_y)
        assert result.size == (expected_width, expected_height)

    def test_pad_image_to_size(self, image_processor, sample_image):
        """Test padding image to screen size."""
        image_processor.set_screen_size(200, 200)

        result = image_processor.pad_image_to_size(sample_image)

        assert result.size == (200, 200)
        # Background should be white
        # Check corner pixel (should be white background)
        corner_pixel = result.getpixel((0, 0))
        assert corner_pixel == (255, 255, 255)

    def test_pad_image_with_offset(self, image_processor, sample_image):
        """Test padding with position offset."""
        image_processor.set_screen_size(200, 200)
        image_processor.position_offset_x = 50
        image_processor.position_offset_y = 30

        result = image_processor.pad_image_to_size(sample_image)

        assert result.size == (200, 200)

    def test_process_image_position_full_pipeline(self, image_processor, sample_image):
        """Test complete image position processing pipeline."""
        image_processor.set_screen_size(150, 150)
        image_processor.rotation = 90

        result = image_processor.process_image_position(sample_image)

        # Final result should be screen size
        assert result.size == (150, 150)

    def test_apply_enhancements_all_settings(self, image_processor, sample_image):
        """Test applying all image enhancements."""
        result = image_processor.apply_enhancements(sample_image)

        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size
        # Should be a copy, not the same object
        assert result is not sample_image

    def test_apply_enhancements_no_changes_needed(self, image_processor, sample_image):
        """Test enhancements when all adjustments are 1.0."""
        # Set all adjustments to 1.0 (no change)
        image_processor.colour_balance_adjustment = 1.0
        image_processor.contrast_adjustment = 1.0
        image_processor.brightness_adjustment = 1.0
        image_processor.sharpness_adjustment = 1.0

        result = image_processor.apply_enhancements(sample_image)

        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size

    def test_apply_enhancements_invalid_input(self, image_processor):
        """Test enhancement with invalid input."""
        invalid_input = "not an image"

        result = image_processor.apply_enhancements(invalid_input)

        # Should return the input unchanged
        assert result == invalid_input

    def test_apply_enhancements_error_handling(self, image_processor, sample_image):
        """Test enhancement error handling."""
        # Mock an enhancer to raise an exception
        with patch("PIL.ImageEnhance.Color") as mock_color:
            mock_color.side_effect = Exception("Enhancement failed")

            result = image_processor.apply_enhancements(sample_image)

            # Should return a valid image with same properties as original
            # Note: Currently returns a copy due to img.copy() - see TODO in processor
            assert isinstance(result, Image.Image)
            assert result.size == sample_image.size
            assert result.mode == sample_image.mode

    def test_needs_enhancement_true(self, image_processor):
        """Test needs_enhancement when enhancements are configured."""
        # Default config has contrast_adjustment = 1.2
        assert image_processor.needs_enhancement() is True

    def test_needs_enhancement_false(self, image_processor):
        """Test needs_enhancement when no enhancements needed."""
        # Set all to 1.0
        image_processor.colour_balance_adjustment = 1.0
        image_processor.contrast_adjustment = 1.0
        image_processor.brightness_adjustment = 1.0
        image_processor.sharpness_adjustment = 1.0

        assert image_processor.needs_enhancement() is False

    def test_image_processor_with_different_modes(self, image_processor):
        """Test processor works with different image modes."""
        # Test with RGBA image
        rgba_image = Image.new("RGBA", (50, 50), (255, 0, 0, 128))
        result = image_processor.apply_enhancements(rgba_image)
        assert isinstance(result, Image.Image)

        # Test with L (grayscale) image
        l_image = Image.new("L", (50, 50), 128)
        result = image_processor.apply_enhancements(l_image)
        assert isinstance(result, Image.Image)

    def test_large_image_processing(self, image_processor):
        """Test processing with a larger image."""
        large_image = Image.new("RGB", (2000, 1500), "blue")
        image_processor.set_screen_size(800, 600)

        result = image_processor.process_image_position(large_image)

        assert result.size == (800, 600)

    @pytest.mark.parametrize("rotation", [0, 90, 180, 270, 45])
    def test_rotation_parameters(self, image_processor, sample_image, rotation):
        """Test various rotation values."""
        image_processor.rotation = rotation

        if rotation in [90, 180, 270]:
            result = image_processor.apply_rotation(sample_image)
            assert isinstance(result, Image.Image)
        else:
            # Non-standard rotation should return original
            result = image_processor.apply_rotation(sample_image)
            assert result.size == sample_image.size
