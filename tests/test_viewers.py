"""Tests for viewer classes."""

import logging
import threading
import time
from unittest.mock import Mock, call, patch

import pytest

from roon_display.viewers.base import BaseViewer
from roon_display.viewers.eink_viewer import EinkViewer, RenderCancelledError
from roon_display.viewers.tk_viewer import TkViewer


class TestBaseViewer:
    """Test BaseViewer abstract class."""

    def test_cannot_instantiate_base_viewer(self, config_manager):
        """Test that BaseViewer cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseViewer(config_manager)

    def test_base_viewer_interface(self):
        """Test that BaseViewer defines required abstract methods."""
        assert hasattr(BaseViewer, "render")
        assert hasattr(BaseViewer, "cancel")
        assert BaseViewer.render.__isabstractmethod__
        assert BaseViewer.cancel.__isabstractmethod__

    @pytest.fixture
    def concrete_viewer(self, config_manager):
        """Create a concrete implementation of BaseViewer for testing."""

        class ConcreteViewer(BaseViewer):
            def __init__(self, config_manager):
                super().__init__(config_manager)
                self.render_calls = []
                self.cancel_called = False

            def render(self, image, image_key, title):
                self.render_calls.append((image, image_key, title))

            def cancel(self):
                self.cancel_called = True

        return ConcreteViewer(config_manager)

    def test_initialization(self, concrete_viewer):
        """Test BaseViewer initialization."""
        assert concrete_viewer.config_manager is not None
        assert concrete_viewer.image_processor is not None

    def test_set_screen_size(self, concrete_viewer):
        """Test set_screen_size method."""
        width, height = 1920, 1080
        concrete_viewer.set_screen_size(width, height)
        assert concrete_viewer.config_manager.get_screen_width() == width
        assert concrete_viewer.config_manager.get_screen_height() == height

    def test_startup_is_noop(self, concrete_viewer):
        """Test startup is a no-op — image loading is handled by RenderCoordinator."""
        concrete_viewer.startup()
        assert len(concrete_viewer.render_calls) == 0


class TestEinkViewer:
    """Test EinkViewer class."""

    @pytest.fixture
    def eink_viewer(self, config_manager, mock_eink_module):
        """Create EinkViewer instance for testing."""
        with patch("roon_display.utils.set_current_image_key"):
            viewer = EinkViewer(config_manager, mock_eink_module)
            viewer.startup = Mock()
            return viewer

    def test_initialization(self, config_manager, mock_eink_module):
        """Test EinkViewer initialization."""
        with patch("roon_display.utils.set_current_image_key"):
            viewer = EinkViewer(config_manager, mock_eink_module)
            assert viewer.eink == mock_eink_module
            assert viewer.epd is not None
            mock_eink_module.EPD.assert_called_once()
            viewer.epd.Init.assert_called_once()

    def test_render_success(self, eink_viewer, sample_image):
        """Test successful render."""
        eink_viewer.render(sample_image, "test_key_123", "Test Song")
        eink_viewer.epd.getbuffer.assert_called_once_with(sample_image)
        eink_viewer.epd.display.assert_called_once()

    @patch("roon_display.utils.set_current_image_key")
    def test_render_sets_current_key(self, mock_set_key, eink_viewer, sample_image):
        """Test that render sets the current image key."""
        eink_viewer.render(sample_image, "test_key_456", "Test Song")
        mock_set_key.assert_called_once_with("test_key_456")

    def test_render_error_handling(self, eink_viewer, sample_image):
        """Test error handling in render."""
        eink_viewer.epd.display.side_effect = Exception("Display error")
        # Should not raise exception
        eink_viewer.render(sample_image, "test_key", "Test Song")

    def test_render_is_blocking(self, eink_viewer, sample_image):
        """Test that render blocks until epd.display completes."""
        display_done = threading.Event()

        def slow_display(*args, **kwargs):
            time.sleep(0.05)
            display_done.set()

        eink_viewer.epd.display.side_effect = slow_display

        render_done = threading.Event()

        def run_render():
            eink_viewer.render(sample_image, "key", "Title")
            render_done.set()

        t = threading.Thread(target=run_render)
        t.start()
        render_done.wait(timeout=1)

        # If render blocked until display completed, display_done is set
        assert display_done.is_set()
        t.join(timeout=1)

    def test_fast_render_detection(self, eink_viewer, sample_image, caplog):
        """Test detection of fast renders that indicate hardware problems."""
        with caplog.at_level(logging.ERROR):
            eink_viewer.render(sample_image, "fast_key", "Fast Render Test")

        error_logs = [r.message for r in caplog.records if r.levelname == "ERROR"]
        critical_logs = [
            msg for msg in error_logs if "FAST DISPLAY RENDER DETECTED" in msg
        ]
        assert len(critical_logs) > 0
        assert any("expected ~25s" in msg for msg in error_logs)

    def test_normal_render_timing_no_warning(self, eink_viewer, sample_image, caplog):
        """Test that normal render timing doesn't trigger warnings."""
        eink_viewer.config_manager.set_display_timing_eink_success_threshold("0.001")
        with caplog.at_level(logging.ERROR):
            eink_viewer.render(sample_image, "normal_key", "Normal Render Test")

        error_logs = [r.message for r in caplog.records if r.levelname == "ERROR"]
        critical_logs = [
            msg for msg in error_logs if "FAST DISPLAY RENDER DETECTED" in msg
        ]
        assert len(critical_logs) == 0

    # --- Cancellation tests ---

    def test_cancel_sets_event(self, eink_viewer):
        """cancel() sets the _cancel_render event."""
        assert not eink_viewer._cancel_render.is_set()
        eink_viewer.cancel()
        assert eink_viewer._cancel_render.is_set()

    def test_render_clears_cancel_event_at_start(self, eink_viewer, sample_image):
        """render() clears the cancel event before touching hardware."""
        eink_viewer._cancel_render.set()
        eink_viewer.render(sample_image, "key", "Test")
        # Init must have been called — event was cleared before hardware access
        eink_viewer.epd.Init.assert_called()

    def test_render_calls_reset_on_cancel(self, eink_viewer, sample_image):
        """When display() raises RenderCancelledError, Reset() is called."""
        eink_viewer.epd.display.side_effect = RenderCancelledError("test cancel")
        with pytest.raises(RenderCancelledError):
            eink_viewer.render(sample_image, "key", "Test")
        eink_viewer.epd.Reset.assert_called_once()

    def test_render_does_not_finalize_on_cancel(self, eink_viewer, sample_image):
        """Cancelled render does not update the current image key."""
        eink_viewer.epd.display.side_effect = RenderCancelledError("test cancel")
        with patch("roon_display.utils.set_current_image_key") as mock_set_key:
            with pytest.raises(RenderCancelledError):
                eink_viewer.render(sample_image, "key", "Test")
            mock_set_key.assert_not_called()

    def test_render_disarms_cancel_event_on_success(self, eink_viewer, sample_image):
        """After a normal render, set_cancel_event(None) is called to disarm."""
        eink_viewer.render(sample_image, "key", "Test")
        calls = eink_viewer.epd.set_cancel_event.call_args_list
        assert calls[-1] == call(None)

    def test_render_clears_cancel_event_before_hardware(
        self, eink_viewer, sample_image
    ):
        """render() clears the cancel event before touching hardware."""
        eink_viewer._cancel_render.set()
        eink_viewer.render(sample_image, "key", "Test")
        eink_viewer.epd.Init.assert_called()

    def test_initialization_with_interrupt_on_skip(
        self, config_manager, mock_eink_module
    ):
        """Test EinkViewer initialization reads interrupt_on_skip from config."""
        config_manager.set_display_interrupt_on_skip("true")
        with patch("roon_display.utils.set_current_image_key"):
            viewer = EinkViewer(config_manager, mock_eink_module)
            viewer.startup = Mock()
            assert viewer.eink == mock_eink_module
            assert config_manager.get_display_interrupt_on_skip() is True


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
        mock_root.destroy = Mock()

        # after(0, callback) executes immediately in tests
        def execute_after(ms, callback, *args):
            if ms == 0:
                callback(*args)

        mock_root.after = Mock(side_effect=execute_after)
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
            "roon_display.viewers.tk_viewer.set_current_image_key",
            create=True,
        ):
            viewer = TkViewer(config_manager, mock_tk_root)
            viewer.startup = Mock()
            return viewer

    def test_initialization(self, config_manager, mock_tk_root, mock_tk_label):
        """Test TkViewer initialization."""
        config_manager.set_display_tkinter_fullscreen("true")
        with patch("tkinter.Label", return_value=mock_tk_label), patch(
            "roon_display.viewers.tk_viewer.set_current_image_key",
            create=True,
        ):
            viewer = TkViewer(config_manager, mock_tk_root)
            assert viewer.root == mock_tk_root
            mock_tk_root.title.assert_called_with("Album Art Viewer")
            mock_tk_root.tk_setPalette.assert_called_once()
            mock_tk_root.attributes.assert_called_with("-fullscreen", True)
            mock_tk_root.geometry.assert_not_called()
            mock_tk_root.bind.assert_called()
            mock_tk_root.protocol.assert_called()

    def test_fullscreen_configuration(
        self, config_manager, mock_tk_root, mock_tk_label
    ):
        """Test TkViewer with fullscreen enabled."""
        config_manager.set_display_tkinter_fullscreen("true")
        with patch("tkinter.Label", return_value=mock_tk_label), patch(
            "roon_display.viewers.tk_viewer.set_current_image_key",
            create=True,
        ):
            TkViewer(config_manager, mock_tk_root)
            mock_tk_root.attributes.assert_called_with("-fullscreen", True)
            mock_tk_root.geometry.assert_not_called()

    def test_render_success(self, tk_viewer, sample_image):
        """Test successful render."""
        with patch("PIL.ImageTk.PhotoImage") as mock_photo, patch(
            "roon_display.utils.set_current_image_key"
        ) as mock_set_key:
            mock_photo_instance = Mock()
            mock_photo.return_value = mock_photo_instance

            tk_viewer.render(sample_image, "test_key", "Test Song")

            mock_photo.assert_called_once()
            tk_viewer.label.configure.assert_called_with(image=mock_photo_instance)
            mock_set_key.assert_called_once_with("test_key")

    def test_render_schedules_on_main_thread(self, tk_viewer, sample_image):
        """render() calls root.after(0, …) to schedule work on the main thread."""
        with patch("PIL.ImageTk.PhotoImage"):
            tk_viewer.render(sample_image, "key", "Title")
        # root.after should have been called with delay=0
        after_calls = [c for c in tk_viewer.root.after.call_args_list if c[0][0] == 0]
        assert len(after_calls) >= 1

    def test_render_error_propagates(self, tk_viewer, sample_image):
        """Exceptions raised inside the Tk callback are re-raised from render()."""
        with patch("PIL.ImageTk.PhotoImage", side_effect=RuntimeError("ImageTk error")):
            with pytest.raises(RuntimeError, match="ImageTk error"):
                tk_viewer.render(sample_image, "key", "Title")

    def test_cancel_is_noop(self, tk_viewer):
        """cancel() returns without error."""
        tk_viewer.cancel()  # Should not raise

    def test_image_reference_maintained(self, tk_viewer, sample_image):
        """Image reference is stored on label to prevent GC."""
        with patch("PIL.ImageTk.PhotoImage") as mock_photo:
            mock_photo_instance = Mock()
            mock_photo.return_value = mock_photo_instance
            tk_viewer.render(sample_image, "test_key", "Test Song")
            assert tk_viewer.label.image == mock_photo_instance

    def test_window_event_handlers(self, config_manager, mock_tk_root, mock_tk_label):
        """Window event handlers are set up correctly."""
        with patch("tkinter.Label", return_value=mock_tk_label), patch(
            "roon_display.viewers.tk_viewer.set_current_image_key",
            create=True,
        ):
            TkViewer(config_manager, mock_tk_root)
            escape_calls = [
                c for c in mock_tk_root.bind.call_args_list if "<Escape>" in str(c)
            ]
            assert len(escape_calls) > 0
            protocol_calls = [
                c
                for c in mock_tk_root.protocol.call_args_list
                if "WM_DELETE_WINDOW" in str(c)
            ]
            assert len(protocol_calls) > 0
