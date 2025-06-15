"""Pytest configuration and fixtures."""

import configparser
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from PIL import Image

from roon_display.config.config_manager import ConfigManager


def pytest_configure(config):
    """Configure pytest with fast timing for tests."""
    os.environ["EINK_SUCCESS_THRESHOLD"] = "0.5"  # 0.5 seconds threshold
    os.environ["EINK_MOCK_SUCCESS_DELAY"] = "0.6"  # 0.6 seconds = successful render
    os.environ["EINK_MOCK_FAILURE_DELAY"] = "0.1"  # 0.1 seconds = failed render


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    config = configparser.ConfigParser()

    config["APP"] = {
        "extension_id": "test_extension",
        "display_name": "Test Display",
        "display_version": "1.0.0",
        "publisher": "Test Publisher",
        "email": "test@example.com",
    }

    config["DISPLAY"] = {"type": "system_display", "partial_refresh": "false"}

    config["IMAGE_RENDER"] = {
        "colour_balance_adjustment": "1.0",
        "contrast_adjustment": "1.2",
        "sharpness_adjustment": "1.1",
        "brightness_adjustment": "0.9",
    }

    config["IMAGE_POSITION"] = {
        "position_offset_x": "10",
        "position_offset_y": "20",
        "scale_x": "0.8",
        "scale_y": "0.9",
        "rotation": "90",
    }

    config["ZONES"] = {
        "allowed_zone_names": "Living Room,Kitchen",
        "forbidden_zone_names": "Bedroom",
    }

    config["SERVER"] = {"ip": "192.168.1.100", "port": "9330"}

    return config


@pytest.fixture
def config_file(temp_dir, sample_config):
    """Create a temporary config file."""
    config_path = temp_dir / "test_config.cfg"
    with open(config_path, "w") as f:
        sample_config.write(f)
    return config_path


@pytest.fixture
def config_manager(config_file):
    """Create a ConfigManager instance with test config."""
    return ConfigManager(config_file)


@pytest.fixture
def sample_image():
    """Create a sample PIL Image for testing."""
    # Create a simple 100x100 RGB image
    img = Image.new("RGB", (100, 100), color="red")
    return img


@pytest.fixture
def mock_roon_api():
    """Create a mock RoonApi instance."""
    mock_api = Mock()
    mock_api.host = "192.168.1.100"
    mock_api.zones = {
        "zone1": {
            "display_name": "Living Room",
            "now_playing": {
                "image_key": "test_image_key_123",
                "three_line": {
                    "line1": "Test Song",
                    "line2": "Test Artist",
                    "line3": "Test Album",
                },
            },
        }
    }
    mock_api.token = "test_token"
    mock_api.get_image = Mock(return_value="http://test.com/image.jpg")
    mock_api.stop = Mock()
    return mock_api


@pytest.fixture
def mock_eink_module():
    """Create a mock e-ink module for testing."""
    import time

    from timing_config import timing_config

    mock_module = Mock()
    mock_module.EPD_WIDTH = 800
    mock_module.EPD_HEIGHT = 600

    # Use MagicMock to properly track attribute assignments
    mock_epd = MagicMock()
    mock_epd.Init = Mock()

    # Mock display method that simulates slow e-ink update
    def slow_display(*args, **kwargs):
        time.sleep(timing_config.mock_success_delay)  # Use configurable delay

    mock_epd.display = Mock(side_effect=slow_display)
    mock_epd.getbuffer = Mock(return_value=b"test_buffer")

    mock_module.EPD = Mock(return_value=mock_epd)
    return mock_module


@pytest.fixture
def mock_requests():
    """Create a mock requests response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"fake_image_data"
    mock_response.raise_for_status = Mock()
    return mock_response
