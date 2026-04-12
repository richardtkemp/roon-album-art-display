"""Tests for anniversary module."""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from roon_display.anniversary import AnniversaryManager


@pytest.fixture
def anniversary_manager(config_manager):
    """Create an AnniversaryManager with test config."""
    with patch("roon_display.anniversary.get_last_track_time", return_value=None):
        with patch("roon_display.anniversary.ensure_anniversary_dir_exists"):
            return AnniversaryManager(config_manager)


class TestUpdateLastTrackTime:
    """Tests for track time tracking."""

    def test_updates_timestamp(self, anniversary_manager):
        """update_last_track_time sets current time."""
        with patch("roon_display.anniversary.set_last_track_time"):
            before = time.time()
            anniversary_manager.update_last_track_time()
            after = time.time()
            assert before <= anniversary_manager.last_track_time <= after


class TestCheckAnniversary:
    """Tests for anniversary date checking."""

    def test_returns_none_when_disabled(self, anniversary_manager, config_manager):
        """Returns None when anniversaries are disabled."""
        config_manager.get_anniversaries_enabled = MagicMock(return_value=False)
        assert anniversary_manager.check_anniversary_if_date_changed() is None

    def test_caches_by_date(self, anniversary_manager, config_manager):
        """Only rechecks when the date changes."""
        config_manager.get_anniversaries_enabled = MagicMock(return_value=True)
        config_manager.get_anniversaries_list = MagicMock(return_value=[])

        # First call checks and caches
        anniversary_manager.check_anniversary_if_date_changed()
        first_date = anniversary_manager.last_check_date

        # Second call on same date uses cache
        anniversary_manager.check_anniversary_if_date_changed()
        assert anniversary_manager.last_check_date == first_date

    def test_finds_matching_anniversary(self, anniversary_manager, config_manager):
        """Finds an anniversary matching today's date."""
        today = datetime.now()
        config_manager.get_anniversaries_enabled = MagicMock(return_value=True)
        config_manager.get_anniversaries_list = MagicMock(
            return_value=[
                {
                    "name": "test_event",
                    "date": f"{today.day}/{today.month}/2020",
                    "message": "Happy ${years} years!",
                    "wait_minutes": 0,
                }
            ]
        )

        # Set last track time to long ago so wait_minutes=0 is satisfied
        anniversary_manager.last_track_time = time.time() - 7200

        with patch.object(anniversary_manager, "_get_current_image", return_value=None):
            result = anniversary_manager.check_anniversary_if_date_changed()

        assert result is not None
        assert result["name"] == "test_event"
        expected_years = today.year - 2020
        assert str(expected_years) in result["message"]

    def test_respects_wait_minutes(self, anniversary_manager, config_manager):
        """Anniversary not shown if wait_minutes not elapsed."""
        today = datetime.now()
        config_manager.get_anniversaries_enabled = MagicMock(return_value=True)
        config_manager.get_anniversaries_list = MagicMock(
            return_value=[
                {
                    "name": "test",
                    "date": f"{today.day}/{today.month}/2020",
                    "message": "Test",
                    "wait_minutes": 999,
                }
            ]
        )

        # Set last track time to just now
        anniversary_manager.last_track_time = time.time()

        result = anniversary_manager.check_anniversary_if_date_changed()
        assert result is None

    def test_no_match_returns_none(self, anniversary_manager, config_manager):
        """Returns None when no anniversary matches today."""
        config_manager.get_anniversaries_enabled = MagicMock(return_value=True)
        config_manager.get_anniversaries_list = MagicMock(
            return_value=[
                {
                    "name": "test",
                    "date": "1/1/2000",  # January 1st - unlikely to be today
                    "message": "Test",
                    "wait_minutes": 0,
                }
            ]
        )

        # Force date re-check
        anniversary_manager.last_check_date = None

        # Only None if today isn't Jan 1
        today = datetime.now()
        if today.month != 1 or today.day != 1:
            result = anniversary_manager.check_anniversary_if_date_changed()
            assert result is None


class TestCreateAnniversaryDisplay:
    """Tests for display image creation."""

    def test_text_only_when_no_image(self, anniversary_manager, config_manager):
        """Creates text-only display when no image available."""
        mock_processor = MagicMock()
        mock_processor.screen_width = 800
        mock_processor.screen_height = 600

        anniversary = {"name": "test", "message": "Hello", "image_path": None}
        result = anniversary_manager.create_anniversary_display(
            anniversary, mock_processor, config_manager
        )
        assert isinstance(result, Image.Image)

    def test_with_image(self, anniversary_manager, config_manager, temp_dir):
        """Creates display with image when path is valid."""
        mock_processor = MagicMock()
        mock_processor.screen_width = 800
        mock_processor.screen_height = 600

        # Create test image
        test_img = Image.new("RGB", (200, 200), "green")
        img_path = temp_dir / "anniv.jpg"
        test_img.save(img_path)

        anniversary = {
            "name": "test",
            "message": "Happy day",
            "image_path": str(img_path),
        }
        result = anniversary_manager.create_anniversary_display(
            anniversary, mock_processor, config_manager
        )
        assert isinstance(result, Image.Image)
        assert result.size == (800, 600)
