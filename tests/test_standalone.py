"""Tests for standalone module."""

import pytest
from PIL import Image

from roon_display.standalone import resolve_image


class TestResolveImage:
    """Tests for resolve_image()."""

    def test_file_path_returned_as_is(self, temp_dir):
        """A valid file path is returned unchanged."""
        img = Image.new("RGB", (10, 10), "red")
        path = temp_dir / "test.jpg"
        img.save(path)
        assert resolve_image(path) == path

    def test_nonexistent_file_raises(self, temp_dir):
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="does not exist"):
            resolve_image(temp_dir / "nonexistent.png")

    def test_directory_picks_random_image(self, temp_dir):
        """Directory resolves to one of its image files."""
        for name in ["a.jpg", "b.png", "c.bmp"]:
            Image.new("RGB", (10, 10)).save(temp_dir / name)
        result = resolve_image(temp_dir)
        assert result.parent == temp_dir
        assert result.suffix.lower() in {".jpg", ".png", ".bmp"}

    def test_empty_directory_raises(self, temp_dir):
        """Empty directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No image files"):
            resolve_image(temp_dir)

    def test_directory_ignores_non_image_files(self, temp_dir):
        """Non-image files in a directory are ignored."""
        (temp_dir / "readme.txt").write_text("not an image")
        (temp_dir / "data.csv").write_text("1,2,3")
        with pytest.raises(FileNotFoundError, match="No image files"):
            resolve_image(temp_dir)
