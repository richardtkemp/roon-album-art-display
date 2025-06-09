"""Integration tests for the complete application."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from roon_display.config.config_manager import ConfigManager
from roon_display.image_processing.processor import ImageProcessor
from roon_display.roon_client.client import RoonClient
from roon_display.viewers.eink_viewer import EinkViewer


class TestIntegration:
    """Integration tests that test components working together."""

    @pytest.fixture
    def integration_config_manager(self, temp_dir):
        """Create a config manager for integration testing."""
        config_path = temp_dir / "integration_config.cfg"

        # Create a complete config file
        config_content = """
[APP]
extension_id = integration_test
display_name = Integration Test
display_version = 1.0.0
publisher = Test Publisher
email = test@example.com

[DISPLAY]
type = system_display

[IMAGE_RENDER]
colour_balance_adjustment = 1.1
contrast_adjustment = 1.2
sharpness_adjustment = 1.0
brightness_adjustment = 0.95

[IMAGE_POSITION]
position_offset_x = 5
position_offset_y = 10
scale_x = 0.9
scale_y = 0.85
rotation = 90

[ZONES]
allowed_zone_names = Test Zone,Living Room
forbidden_zone_names = Bedroom

[SERVER]
ip = 192.168.1.100
port = 9330
"""
        config_path.write_text(config_content)
        return ConfigManager(config_path)

    def test_config_to_image_processor_integration(self, integration_config_manager):
        """Test that config manager properly configures image processor."""
        processor = ImageProcessor(integration_config_manager.config)

        # Verify config values are properly loaded
        assert processor.colour_balance_adjustment == 1.1
        assert processor.contrast_adjustment == 1.2
        assert processor.sharpness_adjustment == 1.0
        assert processor.brightness_adjustment == 0.95
        assert processor.position_offset_x == 5
        assert processor.position_offset_y == 10
        assert processor.scale_x == 0.9
        assert processor.scale_y == 0.85
        assert processor.rotation == 90

    def test_image_processor_with_viewer_integration(
        self, integration_config_manager, mock_eink_module
    ):
        """Test image processor working with viewer."""
        with patch("roon_display.viewers.eink_viewer.set_current_image_key"):
            viewer = EinkViewer(integration_config_manager.config, mock_eink_module)

            # Verify screen size is set correctly
            assert viewer.screen_width == 800  # From mock_eink_module
            assert viewer.screen_height == 600

            # Verify image processor has correct screen dimensions
            assert viewer.image_processor.screen_width == 800
            assert viewer.image_processor.screen_height == 600
            assert viewer.image_processor.image_width == int(800 * 0.9)  # scale_x
            assert viewer.image_processor.image_height == int(600 * 0.85)  # scale_y

    def test_config_to_roon_client_integration(self, integration_config_manager):
        """Test that config manager properly configures Roon client."""
        mock_viewer = Mock()
        mock_image_processor = Mock()

        with patch("roon_display.roon_client.client.Path.home") as mock_home:
            mock_home.return_value = Path("/fake/home")

            client = RoonClient(
                integration_config_manager, mock_viewer, mock_image_processor
            )

            # Verify app info
            app_info = client.app_info
            assert app_info["extension_id"] == "integration_test"
            assert app_info["display_name"] == "Integration Test"

            # Verify zone configuration
            assert client.allowed_zones == ["Test Zone", "Living Room"]
            assert client.forbidden_zones == ["Bedroom"]

    def test_full_image_processing_pipeline(
        self, integration_config_manager, sample_image
    ):
        """Test complete image processing pipeline."""
        processor = ImageProcessor(integration_config_manager.config)
        processor.set_screen_size(400, 300)

        # Test full pipeline: rotation, resizing, padding, enhancement
        result = processor.process_image_position(sample_image)

        # Final image should match screen size
        assert result.size == (400, 300)

        # Test enhancements
        if processor.needs_enhancement():
            enhanced = processor.apply_enhancements(sample_image)
            assert enhanced is not None
            assert enhanced.size == sample_image.size

    def test_roon_client_zone_filtering_integration(self, integration_config_manager):
        """Test Roon client zone filtering with config."""
        mock_viewer = Mock()
        mock_image_processor = Mock()

        with patch("roon_display.roon_client.client.Path.home") as mock_home:
            mock_home.return_value = Path("/fake/home")

            client = RoonClient(
                integration_config_manager, mock_viewer, mock_image_processor
            )

            # Test allowed zone
            allowed_zone_data = {
                "display_name": "Test Zone",
                "now_playing": {"image_key": "test_key"},
            }
            with patch.object(
                client, "_extract_now_playing", return_value={"image_key": "test_key"}
            ), patch.object(client, "_process_now_playing", return_value="test_key"):
                result = client._process_zone_data("zone1", allowed_zone_data)
                assert result == "test_key"

            # Test forbidden zone
            forbidden_zone_data = {
                "display_name": "Bedroom",
                "now_playing": {"image_key": "test_key"},
            }
            result = client._process_zone_data("zone2", forbidden_zone_data)
            assert result is False

            # Test non-allowed zone
            other_zone_data = {
                "display_name": "Office",
                "now_playing": {"image_key": "test_key"},
            }
            result = client._process_zone_data("zone3", other_zone_data)
            assert result is False

    def test_server_config_persistence_integration(
        self, integration_config_manager, temp_dir
    ):
        """Test server configuration persistence."""
        # Initial config should have server details
        ip, port = integration_config_manager.get_server_config()
        assert ip == "192.168.1.100"
        assert port == 9330

        # Update server config
        integration_config_manager.save_server_config("192.168.1.200", 9331)

        # Verify update
        ip, port = integration_config_manager.get_server_config()
        assert ip == "192.168.1.200"
        assert port == 9331

        # Create new config manager to test persistence
        new_config_manager = ConfigManager(integration_config_manager.config_path)
        ip, port = new_config_manager.get_server_config()
        assert ip == "192.168.1.200"
        assert port == 9331

    @patch("roon_display.roon_client.client.requests.get")
    @patch("roon_display.roon_client.client.Image.open")
    def test_album_art_download_and_processing_integration(
        self,
        mock_image_open,
        mock_requests,
        integration_config_manager,
        sample_image,
        temp_dir,
    ):
        """Test album art download and image processing integration."""
        mock_viewer = Mock()
        mock_image_processor = ImageProcessor(integration_config_manager.config)
        mock_image_processor.set_screen_size(200, 150)

        # Setup mocks
        mock_response = Mock()
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status = Mock()
        mock_requests.return_value = mock_response
        mock_image_open.return_value = sample_image

        with patch("roon_display.roon_client.client.Path.home") as mock_home, patch(
            "roon_display.roon_client.client.get_saved_image_dir", return_value=temp_dir
        ):
            mock_home.return_value = Path("/fake/home")

            client = RoonClient(
                integration_config_manager, mock_viewer, mock_image_processor
            )
            client.roon = Mock()
            client.roon.get_image.return_value = "http://test.com/image.jpg"

            # Test download and processing
            image_path = temp_dir / "album_art_test_key.jpg"
            result = client._download_album_art("test_key", image_path)

            # Should download and process image
            assert result is not None
            assert hasattr(result, "size")  # Is a PIL Image
            assert result.size == sample_image.size  # Same dimensions
            assert image_path.exists()

    def test_error_propagation_integration(self, integration_config_manager):
        """Test that errors are properly handled across components."""
        _mock_viewer = Mock()  # noqa: F841

        # Test invalid image processor config
        bad_config = integration_config_manager.config
        bad_config.set("IMAGE_POSITION", "scale_x", "0")  # Invalid scale

        with pytest.raises(ValueError, match="Scale values cannot be zero"):
            ImageProcessor(bad_config)

    def test_threading_integration(
        self, integration_config_manager, mock_eink_module, sample_image
    ):
        """Test threading behavior in integration scenario."""
        with patch("roon_display.viewers.eink_viewer.set_current_image_key"):
            viewer = EinkViewer(integration_config_manager.config, mock_eink_module)

            # Test multiple rapid updates (threading scenario)
            for i in range(3):
                viewer.update(f"key_{i}", f"/path_{i}", sample_image, f"Song {i}")

            # Last thread should be active
            if viewer.update_thread:
                assert viewer.update_thread.is_alive()
                viewer.update_thread.join(timeout=1)

    def test_memory_management_integration(
        self, integration_config_manager, sample_image
    ):
        """Test memory management across components."""
        processor = ImageProcessor(integration_config_manager.config)
        processor.set_screen_size(100, 100)

        # Process multiple images to test memory usage
        for i in range(5):
            # Create a copy to simulate multiple different images
            test_image = sample_image.copy()
            result = processor.process_image_position(test_image)

            # Verify result is independent of input
            assert result is not test_image
            assert result.size == (100, 100)

            # Test enhancements don't modify original
            if processor.needs_enhancement():
                enhanced = processor.apply_enhancements(test_image)
                assert enhanced is not test_image

    def test_configuration_validation_integration(self, temp_dir):
        """Test configuration validation across all components."""
        # Create minimal valid config
        config_path = temp_dir / "minimal_config.cfg"
        config_content = """
[APP]
extension_id = test
display_name = Test
display_version = 1.0.0
publisher = Test
email = test@test.com

[DISPLAY]
type = system_display

[IMAGE_RENDER]
colour_balance_adjustment = 1
contrast_adjustment = 1
sharpness_adjustment = 1
brightness_adjustment = 1

[IMAGE_POSITION]
position_offset_x = 0
position_offset_y = 0
scale_x = 1
scale_y = 1
rotation = 0

[ZONES]
allowed_zone_names =
forbidden_zone_names =
"""
        config_path.write_text(config_content)

        # Should work with all components
        config_manager = ConfigManager(config_path)
        processor = ImageProcessor(config_manager.config)

        assert processor.scale_x == 1.0
        assert processor.scale_y == 1.0
        assert not processor.needs_enhancement()

        # Zone config should handle empty values
        allowed, forbidden = config_manager.get_zone_config()
        assert allowed == []
        assert forbidden == []
