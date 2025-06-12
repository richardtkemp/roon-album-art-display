"""Tests for viewer classes."""

import logging
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from roon_display.viewers.base import BaseViewer
from roon_display.viewers.eink_viewer import EinkViewer
from roon_display.viewers.tk_viewer import TkViewer


class TestBaseViewer:
    """Test BaseViewer abstract class."""

    def test_cannot_instantiate_base_viewer(self, config_manager):
        """Test that BaseViewer cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseViewer(config_manager)

    def test_base_viewer_interface(self):
        """Test that BaseViewer defines required abstract methods."""
        assert hasattr(BaseViewer, "update")
        assert hasattr(BaseViewer, "display_image")
        assert BaseViewer.update.__isabstractmethod__
        assert BaseViewer.display_image.__isabstractmethod__

    @pytest.fixture
    def concrete_viewer(self, config_manager):
        """Create a concrete implementation of BaseViewer for testing."""

        class ConcreteViewer(BaseViewer):
            def __init__(self, config_manager):
                super().__init__(config_manager)
                self.update_calls = []
                self.display_calls = []
                self.anniversary_calls = []

            def update(self, image_key, image_path, img, title):
                self.update_calls.append((image_key, image_path, img, title))

            def display_image(self, image_key, image_path, img, title):
                self.display_calls.append((image_key, image_path, img, title))

            def update_anniversary(self, message, image_path=None):
                self.anniversary_calls.append((message, image_path))

        return ConcreteViewer(config_manager)

    def test_initialization(self, concrete_viewer):
        """Test BaseViewer initialization."""
        # Should have config and image_processor
        assert concrete_viewer.config is not None
        assert concrete_viewer.image_processor is not None

        # Should not have screen dimensions set initially
        assert not hasattr(concrete_viewer, "screen_width")
        assert not hasattr(concrete_viewer, "screen_height")

    def test_set_screen_size(self, concrete_viewer):
        """Test set_screen_size method."""
        width, height = 1920, 1080

        concrete_viewer.set_screen_size(width, height)

        # Should set viewer dimensions
        assert concrete_viewer.screen_width == width
        assert concrete_viewer.screen_height == height

        # Should also set image processor dimensions
        assert concrete_viewer.image_processor.screen_width == width
        assert concrete_viewer.image_processor.screen_height == height

    def test_startup_no_existing_image(self, concrete_viewer):
        """Test startup method when no existing image."""
        with patch(
            "roon_display.viewers.base.get_current_image_key", return_value=None
        ):
            # Should not call update when no existing image
            concrete_viewer.startup()
            assert len(concrete_viewer.update_calls) == 0

    def test_startup_existing_image_no_file(self, concrete_viewer, temp_dir):
        """Test startup method with existing image key but no file."""
        image_key = "test_image_123"
        _expected_path = (
            temp_dir / "album_art" / f"album_art_{image_key}.jpg"
        )  # noqa: F841

        with patch(
            "roon_display.viewers.base.get_current_image_key", return_value=image_key
        ), patch(
            "roon_display.viewers.base.get_saved_image_dir",
            return_value=temp_dir / "album_art",
        ):
            # Should not call update when file doesn't exist
            concrete_viewer.startup()
            assert len(concrete_viewer.update_calls) == 0

    def test_startup_existing_image_with_file(
        self, concrete_viewer, temp_dir, sample_image
    ):
        """Test startup method with existing image key and file."""
        image_key = "test_image_456"
        image_dir = temp_dir / "album_art"
        image_dir.mkdir()
        image_path = image_dir / f"album_art_{image_key}.jpg"

        # Create the image file
        sample_image.save(image_path)

        with patch(
            "roon_display.viewers.base.get_current_image_key", return_value=image_key
        ), patch(
            "roon_display.viewers.base.get_saved_image_dir", return_value=image_dir
        ):
            concrete_viewer.startup()

            # Should call update with correct parameters
            assert len(concrete_viewer.update_calls) == 1
            call_args = concrete_viewer.update_calls[0]
            assert call_args[0] == image_key  # image_key
            assert call_args[1] == image_path  # image_path
            assert call_args[2] is None  # img (let update load it)
            assert call_args[3] == "startup"  # title

    def test_startup_handles_exceptions(self, concrete_viewer):
        """Test that startup method handles exceptions gracefully."""
        with patch(
            "roon_display.viewers.base.get_current_image_key",
            side_effect=Exception("Test error"),
        ):
            # Should not raise exception
            concrete_viewer.startup()
            assert len(concrete_viewer.update_calls) == 0


class TestEinkViewer:
    """Test EinkViewer class."""

    @pytest.fixture
    def eink_viewer(self, config_manager, mock_eink_module):
        """Create EinkViewer instance for testing."""
        with patch("roon_display.viewers.eink_viewer.set_current_image_key"):
            viewer = EinkViewer(
                config_manager.config, mock_eink_module, partial_refresh=False
            )
            viewer.startup = Mock()  # Mock startup to avoid file operations
            return viewer

    def test_initialization(self, config_manager, mock_eink_module):
        """Test EinkViewer initialization."""
        with patch("roon_display.viewers.eink_viewer.set_current_image_key"):
            viewer = EinkViewer(
                config_manager.config, mock_eink_module, partial_refresh=False
            )

            assert viewer.eink == mock_eink_module
            assert viewer.screen_width == 800
            assert viewer.screen_height == 600
            assert viewer.epd is not None
            assert viewer.partial_refresh is False
            mock_eink_module.EPD.assert_called_once()
            viewer.epd.Init.assert_called_once()

    def test_display_image_success(self, eink_viewer, sample_image):
        """Test successful image display."""
        image_key = "test_key_123"
        title = "Test Song"

        eink_viewer.display_image(image_key, None, sample_image, title)

        # Verify e-ink display methods were called
        eink_viewer.epd.getbuffer.assert_called_once_with(sample_image)
        eink_viewer.epd.display.assert_called_once()


    @patch("roon_display.viewers.eink_viewer.set_current_image_key")
    def test_display_image_sets_current_key(
        self, mock_set_key, eink_viewer, sample_image
    ):
        """Test that display_image sets the current image key."""
        image_key = "test_key_456"
        title = "Test Song"

        eink_viewer.display_image(image_key, None, sample_image, title)

        mock_set_key.assert_called_once_with(image_key)

    def test_display_image_error_handling(self, eink_viewer, sample_image):
        """Test error handling in display_image."""
        eink_viewer.epd.display.side_effect = Exception("Display error")

        # Should not raise exception
        eink_viewer.display_image("test_key", None, sample_image, "Test Song")

    def test_update_with_provided_image(self, eink_viewer, sample_image):
        """Test update method with image provided."""
        image_key = "test_key_789"
        image_path = "/fake/path/image.jpg"
        title = "Test Song"

        eink_viewer.update(image_key, image_path, sample_image, title)

        # Should start update thread
        assert eink_viewer.update_thread is not None
        assert isinstance(eink_viewer.update_thread, threading.Thread)
        assert eink_viewer.update_thread.is_alive()

        # Clean up thread
        eink_viewer.update_thread.join(timeout=1)

    def test_update_loads_image_when_none_provided(
        self, eink_viewer, temp_dir, sample_image
    ):
        """Test update method loads image when none provided."""
        image_path = temp_dir / "test_image.jpg"
        sample_image.save(image_path)

        eink_viewer.update("test_key", image_path, None, "Test Song")

        # Should start update thread
        assert eink_viewer.update_thread is not None

        # Clean up thread
        eink_viewer.update_thread.join(timeout=1)

    def test_update_handles_missing_image(self, eink_viewer, temp_dir):
        """Test update method handles missing image file."""
        image_path = temp_dir / "nonexistent.jpg"

        eink_viewer.update("test_key", image_path, None, "Test Song")

        # Should not start thread for missing image
        # Note: This depends on the image_processor.fetch_image returning None

    def test_update_stops_previous_thread(self, eink_viewer, sample_image):
        """Test that update waits for previous thread when partial_refresh is False."""
        # Start first update
        eink_viewer.update("key1", "/path1", sample_image, "Song 1")
        first_thread = eink_viewer.update_thread

        # Verify initial state and first thread exists

        assert first_thread is not None, "First update should create a thread"

        # Start second update - with partial_refresh=False, should NOT set stop flag
        eink_viewer.update("key2", "/path2", sample_image, "Song 2")

        # Should NOT set stop flag with partial_refresh=False


        # Clean up threads
        if first_thread:
            first_thread.join(timeout=1)
        if eink_viewer.update_thread:
            eink_viewer.update_thread.join(timeout=1)

    def test_thread_safety(self, eink_viewer, sample_image):
        """Test thread safety of multiple rapid updates."""
        threads = []

        # Start multiple updates rapidly
        for i in range(5):
            eink_viewer.update(f"key_{i}", f"/path_{i}", sample_image, f"Song {i}")
            if eink_viewer.update_thread:
                threads.append(eink_viewer.update_thread)

        # Clean up all threads
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=1)

    def test_no_concurrent_display_calls(self, eink_viewer, sample_image):
        """Test that display() is never called concurrently."""
        display_call_count = 0
        active_calls = 0
        max_concurrent = 0

        _original_display = eink_viewer.epd.display  # noqa: F841

        def tracking_display(*args, **kwargs):
            nonlocal display_call_count, active_calls, max_concurrent
            display_call_count += 1
            active_calls += 1
            max_concurrent = max(max_concurrent, active_calls)

            # Simulate slow display with sleep
            time.sleep(0.1)

            active_calls -= 1

        eink_viewer.epd.display.side_effect = tracking_display

        # Start multiple rapid updates
        threads = []
        for i in range(3):
            eink_viewer.update(f"key_{i}", f"/path_{i}", sample_image, f"Song {i}")
            if eink_viewer.update_thread:
                threads.append(eink_viewer.update_thread)

        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=2)

        # Should never have more than 1 concurrent display() call
        assert max_concurrent <= 1, f"Had {max_concurrent} concurrent display calls"
        assert display_call_count >= 1, "Should have made at least one display call"

    def test_fast_render_detection(self, eink_viewer, sample_image, caplog):
        """Test detection of fast renders that indicate hardware problems."""

        from timing_config import timing_config

        # Mock display to complete quickly (simulating failed render)
        def fast_display(*args, **kwargs):
            time.sleep(
                timing_config.mock_failure_delay
            )  # Use configurable failure timing

        eink_viewer.epd.display.side_effect = fast_display

        with caplog.at_level(logging.ERROR):
            eink_viewer.update(
                "fast_key", "/fast/path", sample_image, "Fast Render Test"
            )

            # Wait for thread to complete
            if eink_viewer.update_thread:
                eink_viewer.update_thread.join(timeout=1)

        # Should have logged the critical error
        error_logs = [
            record.message for record in caplog.records if record.levelname == "ERROR"
        ]
        critical_logs = [
            log for log in error_logs if "FAST DISPLAY RENDER DETECTED" in log
        ]

        assert len(critical_logs) > 0, "Should have detected and logged fast render"
        assert any(
            "expected ~25s" in log for log in error_logs
        ), "Should mention expected timing"

    def test_normal_render_timing_no_warning(self, eink_viewer, sample_image, caplog):
        """Test that normal render timing doesn't trigger warnings."""
        with caplog.at_level(logging.ERROR):
            eink_viewer.update(
                "normal_key", "/normal/path", sample_image, "Normal Render Test"
            )

            # Wait for thread to complete
            if eink_viewer.update_thread:
                eink_viewer.update_thread.join(timeout=1)

        # Should not have any critical render warnings
        error_logs = [
            record.message for record in caplog.records if record.levelname == "ERROR"
        ]
        critical_logs = [
            log for log in error_logs if "FAST DISPLAY RENDER DETECTED" in log
        ]

        assert (
            len(critical_logs) == 0
        ), f"Should not warn about normal timing, but got: {critical_logs}"


class TestTkViewer:
    """Test TkViewer class."""

    @pytest.fixture
    def mock_tk_root(self):
        """Create mock Tkinter root window."""
        mock_root = Mock()
        mock_root.winfo_screenwidth.return_value = 1920
        mock_root.winfo_screenheight.return_value = 1080
        mock_root.title = Mock()
        mock_root.tk_setPalette = Mock()
        mock_root.attributes = Mock()
        mock_root.bind = Mock()
        mock_root.protocol = Mock()
        mock_root.after = Mock()
        mock_root.destroy = Mock()
        return mock_root

    @pytest.fixture
    def mock_tk_label(self):
        """Create mock Tkinter label."""
        mock_label = Mock()
        mock_label.pack = Mock()
        mock_label.configure = Mock()
        return mock_label

    @pytest.fixture
    def tk_viewer(self, config_manager, mock_tk_root, mock_tk_label):
        """Create TkViewer instance for testing."""
        with patch("tkinter.Label", return_value=mock_tk_label), patch(
            "roon_display.viewers.tk_viewer.set_current_image_key"
        ):
            viewer = TkViewer(config_manager.config, mock_tk_root)
            viewer.startup = Mock()  # Mock startup to avoid file operations
            return viewer

    def test_initialization(self, config_manager, mock_tk_root, mock_tk_label):
        """Test TkViewer initialization."""
        # Set fullscreen mode to get the expected screen dimensions
        config_manager.config.set("DISPLAY", "tkinter_fullscreen", "true")

        with patch("tkinter.Label", return_value=mock_tk_label), patch(
            "roon_display.viewers.tk_viewer.set_current_image_key"
        ):
            viewer = TkViewer(config_manager.config, mock_tk_root)

            assert viewer.root == mock_tk_root
            assert viewer.screen_width == 1920
            assert viewer.screen_height == 1080
            assert viewer.pending_image_data is None

            # Verify window setup
            mock_tk_root.title.assert_called_with("Album Art Viewer")
            mock_tk_root.tk_setPalette.assert_called_once()
            mock_tk_root.attributes.assert_called_with(
                "-fullscreen", True
            )  # Now using fullscreen
            mock_tk_root.geometry.assert_not_called()  # Not called in fullscreen mode
            mock_tk_root.bind.assert_called()
            mock_tk_root.protocol.assert_called()

    def test_fullscreen_configuration(
        self, config_manager, mock_tk_root, mock_tk_label
    ):
        """Test TkViewer with fullscreen enabled."""
        # Set fullscreen to true in config
        config_manager.config.set("DISPLAY", "tkinter_fullscreen", "true")

        with patch("tkinter.Label", return_value=mock_tk_label), patch(
            "roon_display.viewers.tk_viewer.set_current_image_key"
        ):
            _viewer = TkViewer(config_manager.config, mock_tk_root)  # noqa: F841

            # Verify fullscreen is enabled and no geometry call
            mock_tk_root.attributes.assert_called_with("-fullscreen", True)
            mock_tk_root.geometry.assert_not_called()

    def test_check_pending_updates_no_pending(self, tk_viewer):
        """Test check_pending_updates with no pending updates."""
        tk_viewer.check_pending_updates()

        # Should schedule next check
        tk_viewer.root.after.assert_called_with(100, tk_viewer.check_pending_updates)

        # No image update should occur
        assert tk_viewer.pending_image_data is None

    def test_check_pending_updates_with_pending(self, tk_viewer):
        """Test check_pending_updates with pending image data."""
        tk_viewer.pending_image_data = ("test_key", "/test/path", None, "Test Song")

        with patch.object(tk_viewer, "display_image") as mock_display:
            tk_viewer.check_pending_updates()

            mock_display.assert_called_once_with(
                "test_key", "/test/path", None, "Test Song"
            )
            assert tk_viewer.pending_image_data is None

    def test_display_image_success(self, tk_viewer, temp_dir, sample_image):
        """Test successful image display."""
        image_path = temp_dir / "test_image.jpg"
        sample_image.save(image_path)

        with patch("PIL.ImageTk.PhotoImage") as mock_photo, patch(
            "roon_display.viewers.tk_viewer.set_current_image_key"
        ) as mock_set_key:
            mock_photo_instance = Mock()
            mock_photo.return_value = mock_photo_instance

            tk_viewer.display_image("test_key", image_path, None, "Test Song")

            # Verify PhotoImage creation and label update
            mock_photo.assert_called_once()
            tk_viewer.label.configure.assert_called_with(image=mock_photo_instance)
            mock_set_key.assert_called_once_with("test_key")

    def test_display_image_missing_file(self, tk_viewer, temp_dir):
        """Test display_image with missing file."""
        image_path = temp_dir / "nonexistent.jpg"

        # Should handle gracefully and not crash
        tk_viewer.display_image("test_key", image_path, None, "Test Song")

    def test_display_image_error_handling(self, tk_viewer, temp_dir, sample_image):
        """Test error handling in display_image."""
        image_path = temp_dir / "test_image.jpg"
        sample_image.save(image_path)

        with patch("PIL.ImageTk.PhotoImage", side_effect=Exception("ImageTk error")):
            # Should not raise exception
            tk_viewer.display_image("test_key", image_path, None, "Test Song")

    def test_update_sets_pending_data(self, tk_viewer, sample_image):
        """Test that update sets pending image data."""
        image_key = "test_key_update"
        image_path = "/test/path/image.jpg"
        title = "Test Song Update"

        tk_viewer.update(image_key, image_path, sample_image, title)

        assert tk_viewer.pending_image_data == (
            image_key,
            image_path,
            sample_image,
            title,
        )

    def test_update_overwrites_pending_data(self, tk_viewer, sample_image):
        """Test that new update overwrites pending data."""
        # Set initial pending data
        tk_viewer.update("key1", "/path1", sample_image, "Song 1")
        assert tk_viewer.pending_image_data == (
            "key1",
            "/path1",
            sample_image,
            "Song 1",
        )

        # Update with new data
        tk_viewer.update("key2", "/path2", sample_image, "Song 2")
        assert tk_viewer.pending_image_data == (
            "key2",
            "/path2",
            sample_image,
            "Song 2",
        )

    def test_window_event_handlers(self, config_manager, mock_tk_root, mock_tk_label):
        """Test that window event handlers are set up correctly."""
        with patch("tkinter.Label", return_value=mock_tk_label), patch(
            "roon_display.viewers.tk_viewer.set_current_image_key"
        ):
            TkViewer(config_manager.config, mock_tk_root)

            # Verify escape key binding
            escape_calls = [
                call
                for call in mock_tk_root.bind.call_args_list
                if "<Escape>" in str(call)
            ]
            assert len(escape_calls) > 0

            # Verify close protocol
            protocol_calls = [
                call
                for call in mock_tk_root.protocol.call_args_list
                if "WM_DELETE_WINDOW" in str(call)
            ]
            assert len(protocol_calls) > 0

    def test_image_reference_handling(self, tk_viewer, temp_dir, sample_image):
        """Test that image references are properly maintained for GC."""
        image_path = temp_dir / "test_image.jpg"
        sample_image.save(image_path)

        with patch("PIL.ImageTk.PhotoImage") as mock_photo:
            mock_photo_instance = Mock()
            mock_photo.return_value = mock_photo_instance

            tk_viewer.display_image("test_key", image_path, None, "Test Song")

            # Verify that image reference is stored to prevent GC
            assert hasattr(tk_viewer.label, "image")
            assert tk_viewer.label.image == mock_photo_instance

    @patch("roon_display.viewers.tk_viewer.logger")
    def test_logging_on_successful_update(self, mock_logger, tk_viewer):
        """Test that successful updates are logged."""
        tk_viewer.pending_image_data = ("test_key", "/test/path", None, "Test Song")

        with patch.object(tk_viewer, "display_image"):
            tk_viewer.check_pending_updates()

            mock_logger.info.assert_called_with("Updated display with Test Song")

    def test_initialization_with_partial_refresh(
        self, config_manager, mock_eink_module
    ):
        """Test EinkViewer initialization with partial_refresh enabled."""
        with patch("roon_display.viewers.eink_viewer.set_current_image_key"):
            viewer = EinkViewer(
                config_manager.config, mock_eink_module, partial_refresh=True
            )

            assert viewer.partial_refresh is True
            assert viewer.eink == mock_eink_module

    def test_update_with_partial_refresh_disabled(
        self, config_manager, mock_eink_module, sample_image
    ):
        """Test that update waits for natural completion when partial_refresh is disabled."""
        with patch("roon_display.viewers.eink_viewer.set_current_image_key"):
            viewer = EinkViewer(
                config_manager.config, mock_eink_module, partial_refresh=False
            )
            viewer.startup = Mock()

            # Mock a slow display operation
            def slow_display(*args, **kwargs):
                time.sleep(0.1)

            viewer.epd.display.side_effect = slow_display

            # Start first update
            viewer.update("key1", "/path1", sample_image, "Song 1")
            time.sleep(0.01)  # Let first update start

            # Start second update - should wait for first to complete naturally
            with patch("time.sleep") as mock_sleep:
                viewer.update("key2", "/path2", sample_image, "Song 2")


            # Clean up threads
            if viewer.update_thread and viewer.update_thread.is_alive():
                viewer.update_thread.join(timeout=1)

