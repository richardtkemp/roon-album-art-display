"""Tests for configuration manager."""

import sys
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from roon_display.config.config_manager import ConfigManager


class TestConfigManager:
    """Test ConfigManager class."""

    def test_init_with_existing_config(self, config_manager):
        """Test initialization with existing config file."""
        assert config_manager.get_display_type() is not None
        assert config_manager.config_path.exists()

    def test_init_creates_default_config(self, temp_dir):
        """Test that default config is created when file doesn't exist."""
        config_path = temp_dir / "new_config.cfg"

        ConfigManager(config_path)

        # Config file should be created
        assert config_path.exists()

    def test_get_app_info(self, config_manager):
        """Test getting app information."""
        app_info = config_manager.get_app_info()

        assert isinstance(app_info, dict)
        assert "extension_id" in app_info
        assert "display_name" in app_info
        assert "display_version" in app_info
        assert "publisher" in app_info
        assert "email" in app_info

        assert app_info["extension_id"] == "python_roon_album_display"
        assert app_info["display_name"] == "Roon Display"

    def test_get_zone_config(self, config_manager):
        """Test getting zone configuration."""
        # Test individual getters
        allowed_str = config_manager.get_allowed_zone_names()
        forbidden_str = config_manager.get_forbidden_zone_names()

        # Parse like the client does
        allowed = [zone.strip() for zone in allowed_str.split(",") if zone.strip()]
        forbidden = [zone.strip() for zone in forbidden_str.split(",") if zone.strip()]

        assert isinstance(allowed, list)
        assert isinstance(forbidden, list)
        assert "Living Room" in allowed
        assert "Kitchen" in allowed
        assert "Bedroom" in forbidden

    def test_get_zone_config_empty_values(self, temp_dir, sample_config):
        """Test zone config with empty values."""
        sample_config["ZONES"]["allowed_zone_names"] = ""
        sample_config["ZONES"]["forbidden_zone_names"] = "   "

        config_path = temp_dir / "empty_zones.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        # Test individual getters with empty values
        allowed_str = config_manager.get_allowed_zone_names()
        forbidden_str = config_manager.get_forbidden_zone_names()

        # Parse like the client does
        allowed = [zone.strip() for zone in allowed_str.split(",") if zone.strip()]
        forbidden = [zone.strip() for zone in forbidden_str.split(",") if zone.strip()]

        assert allowed == []
        assert forbidden == []

    def test_get_zone_config_with_spaces(self, temp_dir, sample_config):
        """Test zone config strips whitespace."""
        sample_config["ZONES"]["allowed_zone_names"] = " Living Room , Kitchen , "

        config_path = temp_dir / "spaced_zones.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        allowed, forbidden = config_manager.get_zone_config()

        assert "Living Room" in allowed
        assert "Kitchen" in allowed
        assert "" not in allowed  # Empty strings should be filtered out

    def test_save_server_config(self, config_manager, temp_dir):
        """Test saving server configuration."""
        server_ip = "192.168.1.200"
        server_port = 9330

        config_manager.save_server_config(server_ip, server_port)

        ip, port = config_manager.get_server_config()
        assert ip == server_ip
        assert port == server_port

    def test_save_server_config_creates_section(self, temp_dir, sample_config):
        """Test that ROON_SERVER section is created if it doesn't exist."""
        sample_config.remove_section("ROON_SERVER")

        config_path = temp_dir / "no_server.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        config_manager.save_server_config("192.168.1.50", 9330)

        ip, port = config_manager.get_server_config()
        assert ip == "192.168.1.50"
        assert port == 9330

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_save_server_config_error_handling(self, mock_file, config_manager):
        """Test error handling when saving server config fails."""
        # Should not raise exception, just log error
        config_manager.save_server_config("192.168.1.100", 9330)

        # Config object should still be updated even if file write fails
        ip, port = config_manager.get_server_config()
        assert ip == "192.168.1.100"

    def test_get_server_config(self, config_manager):
        """Test getting server configuration."""
        ip, port = config_manager.get_server_config()

        assert ip == "192.168.1.100"
        assert port == 9330

    def test_get_server_config_no_section(self, temp_dir, sample_config):
        """Test getting server config when ROON_SERVER section doesn't exist."""
        sample_config.remove_section("ROON_SERVER")

        config_path = temp_dir / "no_server.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        ip, port = config_manager.get_server_config()

        assert ip is None
        assert port is None

    def test_get_server_config_missing_values(self, temp_dir, sample_config):
        """Test getting server config with missing values."""
        sample_config["ROON_SERVER"] = {}  # Empty section

        config_path = temp_dir / "empty_server.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        ip, port = config_manager.get_server_config()

        assert ip is None
        assert port is None

    def test_get_tkinter_fullscreen_default(self, config_manager):
        """Test getting tkinter fullscreen setting with default value."""
        # Should return False by default
        fullscreen = config_manager.get_tkinter_fullscreen()
        assert fullscreen is False

    def test_get_tkinter_fullscreen_true(self, temp_dir, sample_config):
        """Test getting tkinter fullscreen setting when set to true."""
        sample_config["DISPLAY"]["tkinter_fullscreen"] = "true"

        config_path = temp_dir / "fullscreen_true.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        fullscreen = config_manager.get_tkinter_fullscreen()
        assert fullscreen is True

    def test_get_tkinter_fullscreen_false(self, temp_dir, sample_config):
        """Test getting tkinter fullscreen setting when set to false."""
        sample_config["DISPLAY"]["tkinter_fullscreen"] = "false"

        config_path = temp_dir / "fullscreen_false.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        fullscreen = config_manager.get_tkinter_fullscreen()
        assert fullscreen is False

    def test_create_default_config_structure(self, temp_dir):
        """Test that default config has all required sections."""
        config_path = temp_dir / "default_test.cfg"

        ConfigManager(config_path)

        # Read the created config
        import configparser

        config = configparser.ConfigParser()
        config.read(config_path)

        # Verify all required sections exist
        required_sections = [
            "DISPLAY",
            "IMAGE_RENDER",
            "IMAGE_POSITION",
            "ZONES",
        ]
        for section in required_sections:
            assert config.has_section(section)

        # Verify some key values from the current CONFIG_SCHEMA defaults
        assert config.get("DISPLAY", "type") == "epd13in3E"
        assert config.get("DISPLAY", "tkinter_fullscreen") == "false"
        assert config.get("IMAGE_RENDER", "contrast") == "1.0"

    def test_config_path_storage(self, config_file):
        """Test that config path is stored correctly."""
        config_manager = ConfigManager(config_file)
        assert config_manager.config_path == config_file

    def test_default_config_path(self, temp_dir):
        """Test default config path when none provided."""
        original_cwd = Path.cwd()
        try:
            # Change to temp directory to avoid creating roon.cfg in project root
            import os

            os.chdir(temp_dir)

            cm = ConfigManager()  # Creates default config at roon.cfg
            assert cm.config_path == Path("roon.cfg")
        finally:
            os.chdir(original_cwd)

    def test_get_display_config(self, config_manager):
        """Test getting display configuration."""
        display_config = config_manager.get_display_config()

        assert display_config["type"] == "system_display"
        assert display_config["interrupt_on_skip"] is False

    def test_get_display_config_interrupt_on_skip_true(self, temp_dir, sample_config):
        """Test getting display config with interrupt_on_skip enabled."""
        sample_config["DISPLAY"]["interrupt_on_skip"] = "true"

        config_path = temp_dir / "interrupt_on_skip.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        display_config = config_manager.get_display_config()

        assert display_config["type"] == "system_display"
        assert display_config["interrupt_on_skip"] is True

    def test_get_display_config_fallback(self, temp_dir, sample_config):
        """Test getting display config with missing interrupt_on_skip (fallback to False)."""
        # Remove interrupt_on_skip setting to test fallback
        if "interrupt_on_skip" in sample_config["DISPLAY"]:
            del sample_config["DISPLAY"]["interrupt_on_skip"]

        config_path = temp_dir / "no_interrupt_on_skip.cfg"
        with open(config_path, "w") as f:
            sample_config.write(f)

        config_manager = ConfigManager(config_path)
        display_config = config_manager.get_display_config()

        assert display_config["type"] == "system_display"
        assert display_config["interrupt_on_skip"] is False

    def test_get_health_script_configured(self, config_manager):
        """Test getting health script when configured."""
        config_manager.set_health_script("/path/to/health.sh")

        script_path = config_manager.get_health_script()
        assert script_path == "/path/to/health.sh"

    def test_get_health_script_empty(self, config_manager):
        """Test getting health script when empty."""
        config_manager.set_health_script("")

        script_path = config_manager.get_health_script()
        assert script_path is None

    def test_get_health_script_not_configured(self, config_manager):
        """Test getting health script when section doesn't exist."""
        # sample_config fixture has no MONITORING section, so no setup needed
        script_path = config_manager.get_health_script()
        assert script_path is None

    def test_get_health_recheck_interval_configured(self, config_manager):
        """Test getting health recheck interval when configured."""
        config_manager.set_health_recheck_interval("3600")

        interval = config_manager.get_health_recheck_interval()
        assert interval == 3600

    def test_get_health_recheck_interval_default(self, config_manager):
        """Test getting health recheck interval with default value."""
        # sample_config fixture has no MONITORING section, so no setup needed
        interval = config_manager.get_health_recheck_interval()
        assert interval == 1800  # Default 30 minutes

    def test_get_health_recheck_interval_fallback(self, config_manager):
        """Test getting health recheck interval with fallback value."""
        # Set health_script but not health_recheck_interval
        config_manager.set_health_script("/path/to/script.sh")

        interval = config_manager.get_health_recheck_interval()
        assert interval == 1800  # Default 30 minutes
