"""Configuration management for the Roon display application."""

import configparser
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and default config creation."""

    def __init__(self, config_path=None):
        """Initialize config manager with optional config path."""
        if config_path is None:
            config_path = Path("roon.cfg")
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self):
        """Load configuration from file, creating default if needed."""
        if not self.config_path.exists():
            logger.info(
                f"Configuration file {self.config_path} not found. Creating default config."
            )
            self._create_default_config()

        config = configparser.ConfigParser()
        config.read(self.config_path)

        logger.info("Configuration loaded")
        return config

    def _create_default_config(self):
        """Create a default configuration file."""
        config = configparser.ConfigParser()

        config["APP"] = {
            "extension_id": "python_roon_album_display",
            "display_name": "Album Art Display",
            "display_version": "1.0.0",
            "publisher": "Richard Kemp",
            "email": "richardtkemp@gmail.com",
        }

        config["DISPLAY"] = {
            "type": "epd13in3E",
            "tkinter_fullscreen": "false",
            # Options:
            # - 'system_display': Standard display connected to your computer
            # - 'epd13in3E': Waveshare Spectra 6 13.3 inch
            # tkinter_fullscreen: true/false (ignored by e-ink displays)
        }

        config["IMAGE_RENDER"] = {
            "colour_balance_adjustment": "1",
            "contrast_adjustment": "1",
            "sharpness_adjustment": "1",
            "brightness_adjustment": "1",
        }

        config["IMAGE_POSITION"] = {
            "position_offset_x": "0",
            "position_offset_y": "0",
            "scale_x": "1",
            "scale_y": "1",
            "rotation": "270",
        }

        config["ZONES"] = {
            "allowed_zone_names": "comma,separated,list of zone names",
            "forbidden_zone_names": "comma,separated,list of zone names",
        }

        with open(self.config_path, "w") as f:
            config.write(f)

        logger.info(f"Default configuration created at {self.config_path}")
        logger.info("Please review the configuration and re-run")
        sys.exit(0)

    def get_app_info(self):
        """Get app information for Roon API."""
        return {
            "extension_id": self.config.get("APP", "extension_id"),
            "display_name": self.config.get("APP", "display_name"),
            "display_version": self.config.get("APP", "display_version"),
            "publisher": self.config.get("APP", "publisher"),
            "email": self.config.get("APP", "email"),
        }

    def get_zone_config(self):
        """Get zone configuration."""
        allowed = [
            zone.strip()
            for zone in self.config.get("ZONES", "allowed_zone_names").split(",")
            if zone.strip()
        ]
        forbidden = [
            zone.strip()
            for zone in self.config.get("ZONES", "forbidden_zone_names").split(",")
            if zone.strip()
        ]
        return allowed, forbidden

    def save_server_config(self, server_ip, server_port):
        """Save server details to config file."""
        try:
            if "SERVER" not in self.config:
                self.config["SERVER"] = {}

            self.config["SERVER"]["ip"] = server_ip
            self.config["SERVER"]["port"] = str(server_port)

            with open(self.config_path, "w") as configfile:
                self.config.write(configfile)

            logger.info(f"Saved server details ({server_ip}:{server_port}) to config")
        except Exception as e:
            logger.error(f"Error saving server details to config: {e}")

    def get_server_config(self):
        """Get saved server configuration."""
        if "SERVER" in self.config:
            ip = self.config.get("SERVER", "ip", fallback=None)
            port = self.config.getint("SERVER", "port", fallback=None)
            return ip, port
        return None, None

    def get_tkinter_fullscreen(self):
        """Get tkinter fullscreen setting."""
        return self.config.getboolean("DISPLAY", "tkinter_fullscreen", fallback=False)
