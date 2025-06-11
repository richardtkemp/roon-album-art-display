"""Configuration management for the Roon display application."""

import configparser
import logging
import sys
from pathlib import Path

from ..time_utils import parse_time_to_minutes, parse_time_to_seconds
from ..utils import get_extra_images_dir

logger = logging.getLogger(__name__)

# Hardcoded app information (moved from config file)
APP_INFO = {
    "extension_id": "python_roon_album_display",
    "display_name": "Album Art Display",
    "display_version": "1.0.0",
    "publisher": "Richard Kemp",
    "email": "richardtkemp@gmail.com",
}


class ConfigManager:
    """Manages configuration loading and default config creation."""

    def __init__(self, config_path=None):
        """Initialize config manager with optional config path."""
        if config_path is None:
            config_path = Path("roon.cfg")
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self):
        """Load configuration from file, creating default if needed."""
        needs_default = False
        
        if not self.config_path.exists():
            needs_default = True
            logger.info(
                f"Configuration file {self.config_path} not found. Creating default config."
            )
        else:
            # Check if file is empty or has no sections
            config = configparser.ConfigParser()
            try:
                config.read(self.config_path)
                if not config.sections():  # File exists but has no sections
                    needs_default = True
                    logger.info(
                        f"Configuration file {self.config_path} is empty. Creating default config."
                    )
            except Exception:
                needs_default = True
                logger.info(
                    f"Configuration file {self.config_path} is corrupted. Creating default config."
                )
        
        if needs_default:
            self._create_default_config()

        config = configparser.ConfigParser()
        config.read(self.config_path)

        logger.info("Configuration loaded")
        return config

    def _create_default_config(self):
        """Create a default configuration file."""
        config = configparser.ConfigParser()

        config["NETWORK"] = {
            "internal_server_port": "9090",
            "web_config_port": "8080",
            "simulation_server_port": "9999",
            "internal_server_host": "127.0.0.1",
            "web_config_host": "0.0.0.0",
        }

        config["TIMEOUTS"] = {
            "roon_authorization_timeout": "300",
            "health_script_timeout": "30",
            "reconnection_interval": "60",
            "web_request_timeout": "5",
        }

        config["IMAGE_QUALITY"] = {
            "jpeg_quality": "85",
            "web_image_max_width": "600",
            "thumbnail_size": "100",
        }

        config["DISPLAY_TIMING"] = {
            "web_auto_refresh_seconds": "10",
            "anniversary_check_interval": "60",
            "performance_threshold_seconds": "0.5",
            "eink_success_threshold": "12.0",
            "eink_warning_threshold": "30",
            "eink_check_interval": "5",
            "preview_auto_revert_seconds": "30",
            "preview_debounce_ms": "500",
        }

        config["LAYOUT"] = {
            "overlay_size_x_percent": "33",
            "overlay_size_y_percent": "25",
            "overlay_border_size": "20",
            "overlay_margin": "20",
            "anniversary_border_percent": "5",
            "anniversary_text_percent": "15",
            "font_size_ratio_base": "20",
            "line_spacing_ratio": "8",
        }

        config["DISPLAY"] = {
            "type": "system_display",
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

        config["ANNIVERSARIES"] = {
            "enabled": "false",
            "# Format: name = dd/mm/yyyy,message,wait_time": "",
            "# Example: birthday_john = 15/03/1990,Happy ${years} birthday John!,30 minutes": "",
            "# Date format: dd/mm/yyyy (year used to calculate ${years} = current_year - birth_year)": "",
            "# wait_time: time to wait before showing if no new track (accepts: '30 mins', '2h', etc.)": "",
            "# Images: Put images in extra_images/[name]/ directory (e.g. extra_images/birthday_john/)": "",
            "# All images in the directory will be used randomly": "",
        }

        config["MONITORING"] = {
            "log_level": "INFO",
            "# log_level options: DEBUG, INFO, WARNING, ERROR": "",
            "loop_time": "10 minutes",
            "# loop_time: Event loop sleep time (default: 10 minutes). Accepts: '5 mins', '30 seconds', '2h', etc.": "",
            "performance_logging": "",
            "# performance_logging: Enable detailed timing logs for functions >0.5s": "",
            "# Options: '' (disabled), 'info', 'debug', 'DEBUG', etc. Case insensitive.": "",
            "# health_script: Path to script called with health status": "",
            "# Script receives param1=good/bad and param2='$additional_info'": "",
            "# Called on render success/failure and re-called at health_recheck_interval": "",
            "health_script": "",
            "health_recheck_interval": "30 minutes",
            "# health_recheck_interval: Time between health script re-calls (default: 30 minutes). Accepts: '5 mins', '2h', etc.": "",
        }

        with open(self.config_path, "w") as f:
            config.write(f)

        logger.info(f"Default configuration created at {self.config_path}")

    def get_app_info(self):
        """Get app information for Roon API (hardcoded values)."""
        return APP_INFO.copy()



    def get_display_type(self):
        """Get display type."""
        return self._config.get("DISPLAY", "type", fallback="system_display")

    def get_tkinter_fullscreen(self):
        """Get tkinter fullscreen setting."""
        return self._config.getboolean("DISPLAY", "tkinter_fullscreen", fallback=False)

    def save_server_config(self, server_ip, server_port):
        """Save server details to config file."""
        try:
            if "SERVER" not in self._config:
                self._config["SERVER"] = {}

            self._config["SERVER"]["ip"] = server_ip
            self._config["SERVER"]["port"] = str(server_port)

            with open(self.config_path, "w") as configfile:
                self._config.write(configfile)

            logger.info(f"Saved server details ({server_ip}:{server_port}) to config")
        except Exception as e:
            logger.error(f"Error saving server details to config: {e}")


    def get_roon_server_ip(self):
        """Get saved Roon server IP address."""
        if "SERVER" in self._config:
            return self._config.get("SERVER", "ip", fallback=None)
        return None

    def get_roon_server_port(self):
        """Get saved Roon server port."""
        if "SERVER" in self._config:
            return self._config.getint("SERVER", "port", fallback=None)
        return None

    def get_log_level(self):
        """Get logging level from config."""
        log_level_str = self._config.get(
            "MONITORING", "log_level", fallback="INFO"
        ).upper()

        # Map string to logging constants
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }

        return level_map.get(log_level_str, logging.INFO)

    def get_performance_logging(self):
        """Get performance logging setting from config.

        Returns:
            str: Performance logging level or empty string if disabled
        """
        perf_logging = (
            self._config.get("MONITORING", "performance_logging", fallback="")
            .strip()
            .lower()
        )

        # Map various string values to standardized levels
        level_mapping = {
            "": "",  # Empty/disabled
            "none": "",
            "false": "",
            "off": "",
            "0": "",
            "info": "info",
            "information": "info",
            "debug": "debug",
            "dbg": "debug",
            "verbose": "debug",
            "true": "info",  # Default to info for backward compatibility
            "1": "info",
            "on": "info",
        }

        return level_mapping.get(
            perf_logging, perf_logging
        )  # Return as-is if not in mapping

    def get_loop_time(self):
        """Get event loop sleep time in seconds."""
        time_str = self._config.get("MONITORING", "loop_time", fallback="10 minutes")
        try:
            return parse_time_to_seconds(time_str)
        except ValueError as e:
            logger.warning(
                f"Invalid loop_time format '{time_str}': {e}. Using default 600 seconds."
            )
            return 600

    def get_anniversaries_config(self):
        """Get anniversary configuration."""
        if "ANNIVERSARIES" not in self._config:
            return {"enabled": False, "anniversaries": []}

        enabled = self.get_anniversaries_enabled()
        
        if not enabled:
            return {"enabled": False, "anniversaries": []}

        anniversaries = []
        for key, value in self._config["ANNIVERSARIES"].items():
            if key.startswith("#") or key in ["enabled"]:
                continue

            try:
                parts = [part.strip() for part in value.split(",")]
                if len(parts) < 3:
                    logger.warning(f"Invalid anniversary config for {key}: {value}")
                    continue

                date_str = parts[0]
                message = parts[1]
                wait_time_str = parts[2]

                # Parse wait time using natural language parser
                try:
                    wait_minutes = parse_time_to_minutes(wait_time_str)
                except ValueError:
                    # Fallback: try to parse as plain integer (backward compatibility)
                    wait_minutes = int(wait_time_str)

                anniversaries.append(
                    {
                        "name": key,
                        "date": date_str,
                        "message": message,
                        "wait_minutes": wait_minutes,
                    }
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing anniversary config for {key}: {e}")
                continue

        return {"enabled": True, "anniversaries": anniversaries}


    def get_health_script(self):
        """Get health script configuration."""
        if "MONITORING" not in self._config:
            return None

        script_path = self._config.get(
            "MONITORING", "health_script", fallback=""
        ).strip()
        return script_path if script_path else None

    def get_health_recheck_interval(self):
        """Get health recheck interval in seconds."""
        if "MONITORING" not in self._config:
            return 1800  # Default 30 minutes

        time_str = self._config.get(
            "MONITORING", "health_recheck_interval", fallback="30 minutes"
        )
        try:
            return parse_time_to_seconds(time_str)
        except ValueError as e:
            logger.warning(
                f"Invalid health_recheck_interval format '{time_str}': {e}. Using default 1800 seconds."
            )
            return 1800

    # Network Configuration Methods
    def get_internal_server_port(self):
        """Get internal server port."""
        return self._config.getint("NETWORK", "internal_server_port", fallback=9090)

    def get_web_config_port(self):
        """Get web config server port."""
        return self._config.getint("NETWORK", "web_config_port", fallback=8080)

    def get_simulation_server_port(self):
        """Get simulation server port."""
        return self._config.getint("NETWORK", "simulation_server_port", fallback=9999)

    def get_internal_server_host(self):
        """Get internal server host."""
        return self._config.get("NETWORK", "internal_server_host", fallback="127.0.0.1")

    def get_web_config_host(self):
        """Get web config server host."""
        return self._config.get("NETWORK", "web_config_host", fallback="0.0.0.0")

    # Timeout Configuration Methods
    def get_roon_authorization_timeout(self):
        """Get Roon authorization timeout in seconds."""
        return self._config.getint("TIMEOUTS", "roon_authorization_timeout", fallback=300)

    def get_health_script_timeout(self):
        """Get health script timeout in seconds."""
        return self._config.getint("TIMEOUTS", "health_script_timeout", fallback=30)

    def get_reconnection_interval(self):
        """Get reconnection interval in seconds."""
        return self._config.getint("TIMEOUTS", "reconnection_interval", fallback=60)

    def get_web_request_timeout(self):
        """Get web request timeout in seconds."""
        return self._config.getint("TIMEOUTS", "web_request_timeout", fallback=5)

    # Image Quality Configuration Methods
    def get_jpeg_quality(self):
        """Get JPEG quality (0-100)."""
        quality = self._config.getint("IMAGE_QUALITY", "jpeg_quality", fallback=85)
        return max(1, min(100, quality))  # Clamp to valid range

    def get_web_image_max_width(self):
        """Get maximum width for web images in pixels."""
        return self._config.getint("IMAGE_QUALITY", "web_image_max_width", fallback=600)

    def get_thumbnail_size(self):
        """Get thumbnail size in pixels (square)."""
        return self._config.getint("IMAGE_QUALITY", "thumbnail_size", fallback=100)

    # Display Timing Configuration Methods
    def get_web_auto_refresh_seconds(self):
        """Get web auto-refresh interval in seconds."""
        return self._config.getint("DISPLAY_TIMING", "web_auto_refresh_seconds", fallback=10)

    def get_anniversary_check_interval(self):
        """Get anniversary check interval in seconds."""
        return self._config.getint("DISPLAY_TIMING", "anniversary_check_interval", fallback=60)


    def get_eink_success_threshold(self):
        """Get e-ink success threshold in seconds."""
        return self._config.getfloat("DISPLAY_TIMING", "eink_success_threshold", fallback=12.0)


    def get_preview_auto_revert_seconds(self):
        """Get preview auto-revert time in seconds."""
        return self._config.getint("DISPLAY_TIMING", "preview_auto_revert_seconds", fallback=30)

    def get_preview_debounce_ms(self):
        """Get preview debounce time in milliseconds."""
        return self._config.getint("DISPLAY_TIMING", "preview_debounce_ms", fallback=500)

    def get_font(self):
        """Get font path."""
        return self._config.get("LAYOUT", "font", fallback="arial")

    def get_font_size(self):
        """Get font size."""
        return self._config.getint("LAYOUT", "font_size", fallback=16)

    # Layout Configuration Methods
    def get_overlay_size_x_percent(self):
        """Get overlay width percentage."""
        size = self._config.getint("LAYOUT", "overlay_size_x_percent", fallback=33)
        return max(5, min(50, size))  # Clamp to reasonable range

    def get_overlay_size_y_percent(self):
        """Get overlay height percentage."""
        size = self._config.getint("LAYOUT", "overlay_size_y_percent", fallback=25)
        return max(5, min(50, size))  # Clamp to reasonable range

    def get_overlay_border_size(self):
        """Get overlay border size in pixels."""
        return self._config.getint("LAYOUT", "overlay_border_size", fallback=20)

    def get_overlay_margin(self):
        """Get overlay margin in pixels."""
        return self._config.getint("LAYOUT", "overlay_margin", fallback=20)

    def get_anniversary_border_percent(self):
        """Get anniversary border percentage."""
        return self._config.getint("LAYOUT", "anniversary_border_percent", fallback=5)

    def get_anniversary_text_percent(self):
        """Get anniversary text area percentage."""
        return self._config.getint("LAYOUT", "anniversary_text_percent", fallback=15)


    def get_line_spacing_ratio(self):
        """Get line spacing ratio."""
        return self._config.getint("LAYOUT", "line_spacing_ratio", fallback=8)

    # Image Render Configuration Methods
    def get_colour_balance_adjustment(self):
        """Get colour balance adjustment."""
        return self._config.getfloat("IMAGE_RENDER", "colour_balance_adjustment", fallback=1.0)

    def get_contrast_adjustment(self):
        """Get contrast adjustment."""
        return self._config.getfloat("IMAGE_RENDER", "contrast_adjustment", fallback=1.0)

    def get_sharpness_adjustment(self):
        """Get sharpness adjustment."""
        return self._config.getfloat("IMAGE_RENDER", "sharpness_adjustment", fallback=1.0)

    def get_brightness_adjustment(self):
        """Get brightness adjustment."""
        return self._config.getfloat("IMAGE_RENDER", "brightness_adjustment", fallback=1.0)

    # Image Position Configuration Methods
    def get_position_offset_x(self):
        """Get position offset X."""
        return self._config.getint("IMAGE_POSITION", "position_offset_x", fallback=0)

    def get_position_offset_y(self):
        """Get position offset Y."""
        return self._config.getint("IMAGE_POSITION", "position_offset_y", fallback=0)

    def get_scale_x(self):
        """Get scale X factor."""
        return self._config.getfloat("IMAGE_POSITION", "scale_x", fallback=1.0)

    def get_scale_y(self):
        """Get scale Y factor."""
        return self._config.getfloat("IMAGE_POSITION", "scale_y", fallback=1.0)

    def get_rotation(self):
        """Get rotation in degrees."""
        return self._config.getint("IMAGE_POSITION", "rotation", fallback=0)

    # Zone Configuration Methods  
    def get_allowed_zone_names(self):
        """Get allowed zone names as string."""
        return self._config.get("ZONES", "allowed_zone_names", fallback="")

    def get_forbidden_zone_names(self):
        """Get forbidden zone names as string."""
        return self._config.get("ZONES", "forbidden_zone_names", fallback="")

    # Monitoring Configuration Methods
    def get_log_level_string(self):
        """Get log level as string."""
        return self._config.get("MONITORING", "log_level", fallback="INFO")

    def get_loop_time_string(self):
        """Get loop time as string."""
        return self._config.get("MONITORING", "loop_time", fallback="10 minutes")

    def get_performance_logging_string(self):
        """Get performance logging setting as string."""
        return self._config.get("MONITORING", "performance_logging", fallback="")

    def get_health_recheck_interval_string(self):
        """Get health recheck interval as string."""
        return self._config.get("MONITORING", "health_recheck_interval", fallback="30 minutes")

    # Anniversary Configuration Methods
    def get_anniversaries_enabled(self):
        """Get anniversaries enabled setting."""
        return self._config.getboolean("ANNIVERSARIES", "enabled", fallback=False)

    def get_anniversaries_list(self):
        """Get list of configured anniversaries."""
        anniversaries_config = self.get_anniversaries_config()
        return anniversaries_config.get("anniversaries", [])

    def set_screen_width(self, width):
        """Set screen width for runtime use."""
        self.screen_width = width

    def set_screen_height(self, height):
        """Set screen height for runtime use."""
        self.screen_height = height

    def get_screen_width(self):
        """Get current screen width."""
        return getattr(self, 'screen_width', 800)  # Default fallback

    def get_screen_height(self):
        """Get current screen height."""
        return getattr(self, 'screen_height', 600)  # Default fallback

    def update_config_values(self, config_updates: dict) -> bool:
        """Update configuration values in memory and persist to file.
        
        Args:
            config_updates: Dictionary of config updates in format:
                {'SECTION.key': 'value', 'OTHER_SECTION.other_key': 'value'}
                
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Update in-memory config
            for key, value in config_updates.items():
                if '.' not in key:
                    logger.warning(f"Invalid config key format: {key}")
                    continue
                    
                section_name, config_key = key.split('.', 1)
                
                # Ensure section exists
                if section_name not in self._config:
                    self._config[section_name] = {}
                    
                # Update the value
                self._config[section_name][config_key] = str(value)
                logger.debug(f"Updated config: {section_name}.{config_key} = {value}")
            
            # Persist to file
            self._write_config_file()
            logger.info(f"Updated {len(config_updates)} configuration values")
            return True
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
    
    def _write_config_file(self):
        """Write current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                self._config.write(f)
            logger.debug(f"Configuration written to {self.config_path}")
        except Exception as e:
            logger.error(f"Error writing config file: {e}")
            raise
