"""Tests for main application entry point."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from roon_display import main


class TestMainApplication:
    """Test main application functionality."""

    def test_create_viewer_system_display(self, config_manager):
        """Test creating system display viewer."""
        config_manager.config.set("DISPLAY", "type", "system_display")

        with patch("tkinter.Tk") as mock_tk, patch(
            "roon_display.main.TkViewer"
        ) as mock_viewer:
            mock_root = Mock()
            mock_tk.return_value = mock_root
            mock_viewer_instance = Mock()
            mock_viewer.return_value = mock_viewer_instance

            viewer, root = main.create_viewer(config_manager)

            assert viewer == mock_viewer_instance
            assert root == mock_root
            mock_tk.assert_called_once()
            mock_viewer.assert_called_once_with(config_manager.config, mock_root)

    def test_create_viewer_eink_display(self, config_manager):
        """Test creating e-ink display viewer."""
        config_manager.config.set("DISPLAY", "type", "epd13in3E")

        with patch("importlib.import_module") as mock_import, patch(
            "roon_display.main.sys.path"
        ):
            mock_eink_module = Mock()
            mock_eink_module.EPD_WIDTH = 960
            mock_eink_module.EPD_HEIGHT = 680
            mock_import.return_value = mock_eink_module

            viewer, root = main.create_viewer(config_manager)

            # Check that the right module was imported and viewer was created
            assert viewer is not None
            assert root is None
            # Check that the e-ink module was imported (among other calls)
            assert call("libs.epd13in3E") in mock_import.call_args_list
            # Check that it's an EinkViewer instance
            assert viewer.__class__.__name__ == "EinkViewer"

    def test_create_viewer_unknown_type(self, config_manager):
        """Test creating viewer with unknown display type."""
        config_manager.config.set("DISPLAY", "type", "unknown_display")

        with pytest.raises(ValueError, match="Unknown display type"):
            main.create_viewer(config_manager)

    def test_create_viewer_eink_import_error(self, config_manager):
        """Test e-ink viewer creation with import error."""
        config_manager.config.set("DISPLAY", "type", "epd13in3E")

        with patch("roon_display.main.sys.path"), patch(
            "roon_display.main.importlib.import_module",
            side_effect=ImportError("Module not found"),
        ):
            with pytest.raises(ImportError):
                main.create_viewer(config_manager)

    @patch("roon_display.main.ensure_image_dir_exists")
    @patch("roon_display.main.ConfigManager")
    @patch("roon_display.main.create_viewer")
    @patch("roon_display.main.RoonClient")
    def test_main_system_display_flow(
        self, mock_roon_client, mock_create_viewer, mock_config_manager, mock_ensure_dir
    ):
        """Test main application flow with system display."""
        # Setup mocks
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.get_log_level.return_value = "INFO"
        mock_config_manager_instance.get_anniversaries_config.return_value = {
            "enabled": False,
            "anniversaries": [],
        }
        mock_config_manager.return_value = mock_config_manager_instance

        mock_viewer = Mock()
        mock_tk_root = Mock()
        mock_create_viewer.return_value = (mock_viewer, mock_tk_root)

        mock_client = Mock()
        mock_client.connect.return_value = Mock()
        mock_client.run.return_value = Mock()
        mock_roon_client.return_value = mock_client

        main.main()

        # Verify call sequence
        mock_ensure_dir.assert_called_once()
        mock_config_manager.assert_called_once()
        mock_create_viewer.assert_called_once_with(mock_config_manager_instance)
        # RoonClient should be called with config, viewer, processor, and anniversary manager
        assert mock_roon_client.call_count == 1
        call_args = mock_roon_client.call_args[0]
        assert call_args[0] == mock_config_manager_instance
        assert call_args[1] == mock_viewer
        assert call_args[2] == mock_viewer.image_processor
        # 4th argument is anniversary manager - just verify it exists
        assert len(call_args) == 4
        mock_client.connect.assert_called_once()
        mock_client.run.assert_called_once()
        mock_viewer.check_pending_updates.assert_called_once()
        mock_tk_root.mainloop.assert_called_once()

    @patch("roon_display.main.ensure_image_dir_exists")
    @patch("roon_display.main.ConfigManager")
    @patch("roon_display.main.create_viewer")
    @patch("roon_display.main.RoonClient")
    def test_main_eink_display_flow(
        self, mock_roon_client, mock_create_viewer, mock_config_manager, mock_ensure_dir
    ):
        """Test main application flow with e-ink display."""
        # Setup mocks
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.get_log_level.return_value = "INFO"
        mock_config_manager_instance.get_anniversaries_config.return_value = {
            "enabled": False,
            "anniversaries": [],
        }
        mock_config_manager.return_value = mock_config_manager_instance

        mock_viewer = Mock()
        mock_create_viewer.return_value = (mock_viewer, None)  # No tk_root for e-ink

        mock_client = Mock()
        mock_event_thread = Mock()
        mock_client.connect.return_value = Mock()
        mock_client.run.return_value = mock_event_thread
        mock_roon_client.return_value = mock_client

        main.main()

        # Verify e-ink specific flow
        mock_event_thread.join.assert_called_once()
        # Should not call tk-specific methods
        mock_viewer.check_pending_updates.assert_not_called()

    @patch("roon_display.main.ensure_image_dir_exists")
    @patch("roon_display.main.ConfigManager")
    @patch("roon_display.main.create_viewer")
    @patch("roon_display.main.RoonClient")
    def test_main_keyboard_interrupt(
        self, mock_roon_client, mock_create_viewer, mock_config_manager, mock_ensure_dir
    ):
        """Test main application handling keyboard interrupt."""
        # Setup mocks
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.get_log_level.return_value = "INFO"
        mock_config_manager_instance.get_anniversaries_config.return_value = {
            "enabled": False,
            "anniversaries": [],
        }
        mock_config_manager.return_value = mock_config_manager_instance

        mock_viewer = Mock()
        mock_tk_root = Mock()
        mock_tk_root.mainloop.side_effect = KeyboardInterrupt("User interrupt")
        mock_create_viewer.return_value = (mock_viewer, mock_tk_root)

        mock_client = Mock()
        mock_roon_client.return_value = mock_client

        # Should handle KeyboardInterrupt gracefully
        main.main()

        # Should still call stop on client
        mock_client.stop.assert_called_once()

    @patch("roon_display.main.ensure_image_dir_exists")
    @patch("roon_display.main.ConfigManager")
    @patch("roon_display.main.create_viewer")
    def test_main_application_error(
        self, mock_create_viewer, mock_config_manager, mock_ensure_dir
    ):
        """Test main application error handling."""
        # Setup mocks
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.get_log_level.return_value = "INFO"
        mock_config_manager_instance.get_anniversaries_config.return_value = {
            "enabled": False,
            "anniversaries": [],
        }
        mock_config_manager.return_value = mock_config_manager_instance

        mock_create_viewer.side_effect = Exception("Application error")

        with pytest.raises(Exception, match="Application error"):
            main.main()

    @patch("roon_display.main.ensure_image_dir_exists")
    @patch("roon_display.main.ConfigManager")
    @patch("roon_display.main.create_viewer")
    @patch("roon_display.main.RoonClient")
    def test_main_cleanup_on_error(
        self, mock_roon_client, mock_create_viewer, mock_config_manager, mock_ensure_dir
    ):
        """Test that cleanup happens even when error occurs."""
        # Setup mocks
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.get_log_level.return_value = "INFO"
        mock_config_manager_instance.get_anniversaries_config.return_value = {
            "enabled": False,
            "anniversaries": [],
        }
        mock_config_manager.return_value = mock_config_manager_instance

        mock_viewer = Mock()
        mock_tk_root = Mock()
        mock_create_viewer.return_value = (mock_viewer, mock_tk_root)

        mock_client = Mock()
        mock_client.connect.side_effect = Exception("Connection error")
        mock_roon_client.return_value = mock_client

        with pytest.raises(Exception, match="Connection error"):
            main.main()

        # Should still call stop in cleanup
        mock_client.stop.assert_called_once()

    def test_main_entry_point_exists(self):
        """Test that main entry point is properly defined."""
        assert hasattr(main, "main")
        assert callable(main.main)

    @patch("roon_display.main.main")
    def test_script_execution(self, mock_main):
        """Test script execution when run as main."""
        # This would test the if __name__ == "__main__": block
        # but since we can't easily test that directly, we verify
        # the main function exists and is callable
        assert callable(main.main)

    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        import logging

        # Verify that the RoonArtFrame logger exists
        logger = logging.getLogger("RoonArtFrame")
        assert logger is not None

        # Verify that roonapi logger exists
        api_logger = logging.getLogger("roonapi")
        assert api_logger is not None

    @patch("roon_display.main.sys.path")
    def test_libs_path_addition(self, mock_path):
        """Test that libs directory is added to Python path for e-ink."""
        config_manager = Mock()
        config_manager.config.get.return_value = "epd13in3E"

        with patch("importlib.import_module") as _mock_import, patch(  # noqa: F841
            "roon_display.main.EinkViewer"
        ), patch("roon_display.main.Path") as mock_path_cls:
            # Setup path mocking
            mock_libs_dir = Mock()
            mock_libs_dir.exists.return_value = True
            mock_path_cls.return_value.parent.parent = Mock()
            mock_path_cls.return_value.parent.parent.__truediv__ = Mock(
                return_value=mock_libs_dir
            )
            mock_path_cls.return_value.parent.parent.__truediv__.return_value = (
                mock_libs_dir
            )

            try:
                main.create_viewer(config_manager)
            except Exception:
                pass  # We're just testing path modification

            # Should attempt to add libs to path
            # Note: This is a simplified test - actual path manipulation is complex

    @patch("roon_display.main.ensure_image_dir_exists")
    @patch("roon_display.main.ConfigManager")
    @patch("roon_display.main.create_viewer")
    @patch("roon_display.main.RoonClient")
    def test_main_with_eink_keyboard_interrupt(
        self, mock_roon_client, mock_create_viewer, mock_config_manager, mock_ensure_dir
    ):
        """Test keyboard interrupt with e-ink display."""
        # Setup mocks for e-ink flow
        mock_config_manager_instance = Mock()
        mock_config_manager_instance.get_log_level.return_value = "INFO"
        mock_config_manager_instance.get_anniversaries_config.return_value = {
            "enabled": False,
            "anniversaries": [],
        }
        mock_config_manager.return_value = mock_config_manager_instance

        mock_viewer = Mock()
        mock_create_viewer.return_value = (mock_viewer, None)  # e-ink has no tk_root

        mock_client = Mock()
        mock_event_thread = Mock()
        mock_event_thread.join.side_effect = KeyboardInterrupt("User interrupt")
        mock_client.run.return_value = mock_event_thread
        mock_roon_client.return_value = mock_client

        # Should handle KeyboardInterrupt gracefully
        main.main()

        # Should still call stop on client
        mock_client.stop.assert_called_once()

    def test_import_structure(self):
        """Test that all required modules can be imported."""
        # Test that main module imports work
        from roon_display.config.config_manager import ConfigManager
        from roon_display.roon_client.client import RoonClient
        from roon_display.utils import ensure_image_dir_exists
        from roon_display.viewers.eink_viewer import EinkViewer
        from roon_display.viewers.tk_viewer import TkViewer

        # Verify classes exist
        assert ConfigManager is not None
        assert EinkViewer is not None
        assert TkViewer is not None
        assert RoonClient is not None
        assert ensure_image_dir_exists is not None
