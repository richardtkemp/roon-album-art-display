"""Tests for utility functions."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from roon_display.utils import (
    ensure_image_dir_exists,
    get_current_image_key,
    get_root_dir,
    get_saved_image_dir,
    set_current_image_key,
)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_root_dir(self):
        """Test getting root directory."""
        root_dir = get_root_dir()
        assert isinstance(root_dir, Path)
        assert root_dir.exists()

    def test_get_saved_image_dir(self):
        """Test getting saved image directory path."""
        image_dir = get_saved_image_dir()
        assert isinstance(image_dir, Path)
        assert image_dir.name == "album_art"

    def test_set_current_image_key_valid(self, temp_dir):
        """Test setting a valid image key."""
        with patch("roon_display.utils.get_saved_image_dir", return_value=temp_dir):
            key = "test_image_key_123"
            set_current_image_key(key)

            key_file = temp_dir / "current_key"
            assert key_file.exists()
            assert key_file.read_text() == key

    def test_set_current_image_key_empty(self):
        """Test setting empty image key raises error."""
        with pytest.raises(ValueError, match="Image key cannot be empty"):
            set_current_image_key("")

    def test_set_current_image_key_none(self):
        """Test setting None image key raises error."""
        with pytest.raises(ValueError, match="Image key cannot be empty"):
            set_current_image_key(None)

    def test_get_current_image_key_exists(self, temp_dir):
        """Test getting existing image key."""
        with patch("roon_display.utils.get_saved_image_dir", return_value=temp_dir):
            # Create key file
            key_file = temp_dir / "current_key"
            key_file.write_text("test_key_456")

            result = get_current_image_key()
            assert result == "test_key_456"

    def test_get_current_image_key_not_exists(self, temp_dir):
        """Test getting image key when file doesn't exist."""
        with patch("roon_display.utils.get_saved_image_dir", return_value=temp_dir):
            result = get_current_image_key()
            assert result is None

    def test_get_current_image_key_strips_whitespace(self, temp_dir):
        """Test that get_current_image_key strips whitespace."""
        with patch("roon_display.utils.get_saved_image_dir", return_value=temp_dir):
            key_file = temp_dir / "current_key"
            key_file.write_text("  test_key_with_spaces  \n")

            result = get_current_image_key()
            assert result == "test_key_with_spaces"

    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_ensure_image_dir_exists_creates_dir(self, mock_makedirs, mock_exists):
        """Test that ensure_image_dir_exists creates directory when needed."""
        mock_exists.return_value = False

        result = ensure_image_dir_exists()

        mock_makedirs.assert_called_once()
        assert result == get_saved_image_dir()

    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_ensure_image_dir_exists_dir_exists(self, mock_makedirs, mock_exists):
        """Test that ensure_image_dir_exists doesn't create existing directory."""
        mock_exists.return_value = True

        result = ensure_image_dir_exists()

        mock_makedirs.assert_not_called()
        assert result == get_saved_image_dir()
