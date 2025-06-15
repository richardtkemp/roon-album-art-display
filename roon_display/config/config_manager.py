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

# Complete configuration schema - single source of truth
CONFIG_SCHEMA = {
    "NETWORK": {
        "internal_server_port": {
            "default": "9090",
            "type": "number",
            "input_type": "number",
            "min": 1024,
            "max": 65535,
            "comment": "Port for internal server communication",
        },
        "web_config_port": {
            "default": "8080",
            "type": "number",
            "input_type": "number",
            "min": 1024,
            "max": 65535,
            "comment": "Port for web configuration interface",
        },
        "simulation_server_port": {
            "default": "9999",
            "type": "number",
            "input_type": "number",
            "min": 1024,
            "max": 65535,
            "comment": "Port for simulation server",
        },
        "internal_server_host": {
            "default": "127.0.0.1",
            "type": "string",
            "input_type": "text",
            "comment": "Host for internal server",
        },
        "web_config_host": {
            "default": "0.0.0.0",
            "type": "string",
            "input_type": "text",
            "comment": "Host for web configuration interface",
        },
    },
    "TIMEOUTS": {
        "roon_authorization_timeout": {
            "default": "300",
            "type": "number",
            "input_type": "number",
            "min": 30,
            "max": 3600,
            "comment": "Timeout for Roon authorization (seconds)",
        },
        "health_script_timeout": {
            "default": "30",
            "type": "number",
            "input_type": "number",
            "min": 5,
            "max": 300,
            "comment": "Timeout for health check script (seconds)",
        },
        "reconnection_interval": {
            "default": "60",
            "type": "number",
            "input_type": "number",
            "min": 10,
            "max": 600,
            "comment": "Interval between reconnection attempts (seconds)",
        },
        "web_request_timeout": {
            "default": "5",
            "type": "number",
            "input_type": "number",
            "min": 1,
            "max": 30,
            "comment": "Timeout for web requests (seconds)",
        },
    },
    "IMAGE_QUALITY": {
        "thumbnail_size": {
            "default": "100",
            "type": "number",
            "input_type": "number",
            "min": 50,
            "max": 500,
            "comment": "Size of thumbnail images (pixels)",
        },
    },
    "DISPLAY_TIMING": {
        "web_auto_refresh_seconds": {
            "default": "10",
            "type": "number",
            "input_type": "number",
            "min": 1,
            "max": 60,
            "comment": "Auto-refresh interval for web interface (seconds)",
        },
        "anniversary_check_interval": {
            "default": "60",
            "type": "number",
            "input_type": "number",
            "min": 10,
            "max": 3600,
            "comment": "How often to check for anniversaries (seconds)",
        },
        "performance_threshold_seconds": {
            "default": "0.5",
            "type": "number",
            "input_type": "number",
            "min": 0.1,
            "max": 10.0,
            "step": 0.1,
            "comment": "Performance threshold for logging (seconds)",
        },
        "eink_success_threshold": {
            "default": "15.0",
            "type": "number",
            "input_type": "number",
            "min": 1.0,
            "max": 60.0,
            "step": 0.1,
            "comment": "E-ink display success threshold (seconds)",
        },
        "preview_auto_revert_seconds": {
            "default": "30",
            "type": "number",
            "input_type": "number",
            "min": 5,
            "max": 300,
            "comment": "Auto-revert time for preview images (seconds)",
        },
        "preview_debounce_ms": {
            "default": "500",
            "type": "number",
            "input_type": "number",
            "min": 100,
            "max": 2000,
            "comment": "Debounce delay for preview generation (milliseconds)",
        },
        "loop_time": {
            "default": "2.5",
            "type": "number",
            "input_type": "number",
            "min": 0.1,
            "max": 60.0,
            "step": 0.1,
            "comment": "Main loop interval (seconds)",
        },
    },
    "LAYOUT": {
        "overlay_size_x_percent": {
            "default": "50",
            "type": "number",
            "input_type": "range",
            "min": 10,
            "max": 100,
            "step": 1,
            "comment": "Overlay width as percentage of image width",
        },
        "overlay_size_y_percent": {
            "default": "20",
            "type": "number",
            "input_type": "range",
            "min": 5,
            "max": 50,
            "step": 1,
            "comment": "Overlay height as percentage of image height",
        },
        "overlay_bottom_percent": {
            "default": "5",
            "type": "number",
            "input_type": "range",
            "min": 0,
            "max": 50,
            "step": 1,
            "comment": "Overlay distance from bottom as percentage",
        },
        "overlay_left_percent": {
            "default": "5",
            "type": "number",
            "input_type": "range",
            "min": 0,
            "max": 50,
            "step": 1,
            "comment": "Overlay distance from left as percentage",
        },
        "artist_display_time": {
            "default": "3",
            "type": "number",
            "input_type": "number",
            "min": 1,
            "max": 30,
            "comment": "Time to display artist information (seconds)",
        },
        "album_display_time": {
            "default": "3",
            "type": "number",
            "input_type": "number",
            "min": 1,
            "max": 30,
            "comment": "Time to display album information (seconds)",
        },
        "track_display_time": {
            "default": "3",
            "type": "number",
            "input_type": "number",
            "min": 1,
            "max": 30,
            "comment": "Time to display track information (seconds)",
        },
    },
    "DISPLAY": {
        "type": {
            "default": "system_display",
            "type": "select",
            "options": ["system_display", "epd13in3E"],
            "comment": "Display type to use",
        },
        "tkinter_fullscreen": {
            "default": "false",
            "type": "boolean",
            "comment": "Enable fullscreen mode for tkinter display",
        },
    },
    "IMAGE_RENDER": {
        "color_enhance": {
            "default": "1.0",
            "type": "number",
            "input_type": "range",
            "min": 0.0,
            "max": 3.0,
            "step": 0.1,
            "comment": "Color enhancement factor",
        },
        "contrast": {
            "default": "1.0",
            "type": "number",
            "input_type": "range",
            "min": 0.0,
            "max": 3.0,
            "step": 0.1,
            "comment": "Contrast adjustment factor",
        },
        "brightness": {
            "default": "1.0",
            "type": "number",
            "input_type": "range",
            "min": 0.0,
            "max": 3.0,
            "step": 0.1,
            "comment": "Brightness adjustment factor",
        },
        "sharpness": {
            "default": "1.0",
            "type": "number",
            "input_type": "range",
            "min": 0.0,
            "max": 3.0,
            "step": 0.1,
            "comment": "Sharpness adjustment factor",
        },
    },
    "IMAGE_POSITION": {
        "scale_x": {
            "default": "1.0",
            "type": "number",
            "input_type": "range",
            "min": 0.1,
            "max": 3.0,
            "step": 0.01,
            "comment": "Horizontal scaling factor",
        },
        "scale_y": {
            "default": "1.0",
            "type": "number",
            "input_type": "range",
            "min": 0.1,
            "max": 3.0,
            "step": 0.01,
            "comment": "Vertical scaling factor",
        },
        "rotation": {
            "default": "0",
            "type": "select",
            "options": ["0", "90", "180", "270"],
            "comment": "Image rotation angle (degrees)",
        },
        "image_offset_x": {
            "default": "0",
            "type": "number",
            "input_type": "range",
            "min": -1000,
            "max": 1000,
            "step": 1,
            "comment": "Horizontal image offset in pixels",
        },
        "image_offset_y": {
            "default": "0",
            "type": "number",
            "input_type": "range",
            "min": -1000,
            "max": 1000,
            "step": 1,
            "comment": "Vertical image offset in pixels",
        },
    },
    "ZONES": {
        "allowed_zone_names": {
            "default": "",
            "type": "textarea",
            "comment": "Comma-separated list of allowed Roon zone names (empty = all zones)",
        },
        "forbidden_zone_names": {
            "default": "",
            "type": "textarea",
            "comment": "Comma-separated list of forbidden Roon zone names",
        },
    },
    "ROON_SERVER": {
        "roon_server_ip": {
            "default": "",
            "type": "string",
            "input_type": "text",
            "comment": "Saved Roon server IP address (auto-discovered)",
        },
        "roon_server_port": {
            "default": "",
            "type": "string",
            "input_type": "text",
            "comment": "Saved Roon server port (auto-discovered)",
        },
    },
    "ANNIVERSARIES": {
        "enabled": {
            "default": "false",
            "type": "boolean",
            "comment": "Enable anniversary notifications",
        }
        ### Other annivesary config fields not mentioned as they have specific functions to handle them
    },
    "MONITORING": {
        "log_level": {
            "default": "INFO",
            "type": "select",
            "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
            "comment": "Global logging level (overridden by LOG_LEVELS section)",
        },
        "performance_logging": {
            "default": "false",
            "type": "boolean",
            "comment": "Enable detailed performance logging",
        },
        "health_script": {
            "default": "",
            "type": "string",
            "input_type": "text",
            "comment": "Path to health check script",
        },
        "health_recheck_interval": {
            "default": "300",
            "type": "number",
            "input_type": "number",
            "min": 60,
            "max": 3600,
            "comment": "Health check recheck interval (seconds)",
        },
    },
}

# Component loggers configuration (component_name, default_level, logger_name, description)
COMPONENT_LOGGERS = [
    (
        "render_coordinator",
        "DEBUG",
        "roon_display.render_coordinator",
        "Render coordinator component",
    ),
    ("roon_client", "INFO", "roon_display.roon_client.client", "Roon client component"),
    (
        "image_processing",
        "INFO",
        "roon_display.image_processing.processor",
        "Image processing component",
    ),
    ("web", "INFO", "roon_display.web", "Web interface component"),
    (
        "config",
        "INFO",
        "roon_display.config.config_manager",
        "Configuration management",
    ),
    ("anniversary", "INFO", "roon_display.anniversary", "Anniversary management"),
    ("viewers", "INFO", "roon_display.viewers", "Display viewers"),
    ("utils", "INFO", "roon_display.utils", "Utility functions"),
]


class ConfigManager:
    """Manages configuration loading and default config creation."""

    def __init__(self, config_path=None):
        """Initialize config manager with optional config path."""
        if config_path is None:
            config_path = Path("roon.cfg")
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def get_app_info(self):
        """Get app information for Roon API (hardcoded values)."""
        return APP_INFO.copy()

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
        """Create a default configuration file using CONFIG_SCHEMA."""
        config = configparser.ConfigParser()

        # Generate config sections from schema
        for section_name, fields in CONFIG_SCHEMA.items():
            config[section_name] = {}
            for field_name, field_config in fields.items():
                config[section_name][field_name] = field_config["default"]

        # Add ANNIVERSARIES comments for user guidance
        config["ANNIVERSARIES"]["# Format: name = dd/mm/yyyy,message,wait_time"] = ""
        config["ANNIVERSARIES"][
            "# Example: birthday_john = 15/03/1990,Happy ${years} birthday John!,30 minutes"
        ] = ""
        config["ANNIVERSARIES"][
            "# Date format: dd/mm/yyyy (year used to calculate ${years} = current_year - birth_year)"
        ] = ""
        config["ANNIVERSARIES"][
            "# wait_time: time to wait before showing if no new track (accepts: '30 mins', '2h', etc.)"
        ] = ""
        config["ANNIVERSARIES"][
            "# Images: Put images in extra_images/[name]/ directory (e.g. extra_images/birthday_john/)"
        ] = ""
        config["ANNIVERSARIES"][
            "# All images in the directory will be used randomly"
        ] = ""

        # Add MONITORING comments for user guidance
        config["MONITORING"]["# log_level options: DEBUG, INFO, WARNING, ERROR"] = ""
        config["MONITORING"][
            "# performance_logging: Enable detailed timing logs for functions >0.5s"
        ] = ""
        config["MONITORING"][
            "# Options: '' (disabled), 'info', 'debug', 'DEBUG', etc. Case insensitive."
        ] = ""
        config["MONITORING"][
            "# health_script: Path to script called with health status"
        ] = ""
        config["MONITORING"][
            "# Script receives param1=good/bad and param2='$additional_info'"
        ] = ""
        config["MONITORING"][
            "# Called on render success/failure and re-called at health_recheck_interval"
        ] = ""

        # Add DISPLAY comments for user guidance
        config["DISPLAY"]["# Options:"] = ""
        config["DISPLAY"][
            "# - 'tkinter': Standard display connected to your computer"
        ] = ""
        config["DISPLAY"][
            "# - 'eink': E-ink display (specific model auto-detected)"
        ] = ""
        config["DISPLAY"][
            "# tkinter_fullscreen: true/false (ignored by e-ink displays)"
        ] = ""

        with open(self.config_path, "w") as f:
            config.write(f)

        logger.info(f"Default configuration created at {self.config_path}")

        """Get app information for Roon API (hardcoded values)."""
        return APP_INFO.copy()

    def get_config(config_manager, overrides: dict, key: str):
        """
        Get configuration value with override support and proper type casting.

        This function provides a unified way to get configuration values that can be
        overridden by web interface inputs, with automatic type conversion based on
        the CONFIG_SCHEMA definitions.

        Args:
            config_manager: ConfigManager instance to get default values from
            overrides: Dictionary of override values (typically from web form)
            key: Configuration key to look up (e.g., 'rotation', 'scale_x')

        Returns:
            Properly typed configuration value (int, float, bool, or str)
        """
        # Look for override value
        override_value = None
        section_path = None
        if overrides:
            for override_key, value in overrides.items():
                if override_key.endswith(f".{key}"):
                    override_value = value
                    section_path = override_key.rsplit(".", 1)[
                        0
                    ]  # Extract section path
                    break

        # If we have an override value, convert it to the correct type
        if override_value is not None:
            # Use section_path to directly look up the field type
            field_type = None
            if section_path and section_path in CONFIG_SCHEMA:
                fields = CONFIG_SCHEMA[section_path]
                if key in fields:
                    field_type = fields[key]["type"]

            # Convert the override value to the correct type
            if field_type == "boolean":
                return str(override_value).lower() in ("true", "1", "yes", "on")
            elif field_type == "number":
                try:
                    # Try int first, then float
                    if "." in str(override_value):
                        return float(override_value)
                    else:
                        return int(override_value)
                except (ValueError, TypeError):
                    # If conversion fails, fall back to config manager
                    pass
            elif field_type == "select":
                return str(override_value)
            else:  # string, textarea
                return str(override_value)

        # Fall back to config manager method
        return getattr(config_manager, f"get_{key}")()

    def get_display_type(self):
        """Get display type."""
        return self._config.get("DISPLAY", "type", fallback="system_display")

    def save_server_config(self, server_ip, server_port):
        """Save server details to config file."""
        try:
            if "ROON_SERVER" not in self._config:
                self._config["ROON_SERVER"] = {}

            self._config["ROON_SERVER"]["ip"] = server_ip
            self._config["ROON_SERVER"]["port"] = str(server_port)

            with open(self.config_path, "w") as configfile:
                self._config.write(configfile)

            logger.info(f"Saved server details ({server_ip}:{server_port}) to config")
        except Exception as e:
            logger.error(f"Error saving server details to config: {e}")

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

    def configure_component_log_levels(self):
        """Configure log levels for individual components."""
        # Map string to logging constants
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }

        # Configure each component using COMPONENT_LOGGERS
        for (
            component_name,
            default_level,
            logger_name,
            description,
        ) in COMPONENT_LOGGERS:
            level_str = self._config.get(
                "LOG_LEVELS", component_name, fallback=default_level
            ).upper()
            level = level_map.get(level_str, logging.INFO)

            logger = logging.getLogger(logger_name)
            logger.setLevel(level)

            # Also handle sub-loggers for components with multiple modules
            if component_name == "web":
                # Configure all web sub-components
                for sub_component in ["app", "config_handler", "utils"]:
                    sub_logger = logging.getLogger(f"roon_display.web.{sub_component}")
                    sub_logger.setLevel(level)
            elif component_name == "viewers":
                # Configure all viewer sub-components
                for viewer_type in ["base", "tk_viewer", "eink_viewer"]:
                    sub_logger = logging.getLogger(
                        f"roon_display.viewers.{viewer_type}"
                    )
                    sub_logger.setLevel(level)

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
        """Get main loop interval in seconds."""
        return self._config.getfloat("DISPLAY_TIMING", "loop_time", fallback=2.5)

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

    # Timeout Configuration Methods

    # Display Timing Configuration Methods

    # Layout Configuration Methods
    def get_overlay_size_x_percent(self):
        """Get overlay width percentage."""
        size = self._config.getint("LAYOUT", "overlay_size_x_percent", fallback=33)
        return max(5, min(50, size))  # Clamp to reasonable range

    def get_overlay_size_y_percent(self):
        """Get overlay height percentage."""
        size = self._config.getint("LAYOUT", "overlay_size_y_percent", fallback=25)
        return max(5, min(50, size))  # Clamp to reasonable range

    # Image Render Configuration Methods

    # Image Position Configuration Methods

    # Zone Configuration Methods

    # Monitoring Configuration Methods

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
        return getattr(self, "screen_width", 800)  # Default fallback

    def get_screen_height(self):
        """Get current screen height."""
        return getattr(self, "screen_height", 600)  # Default fallback

    def get_config_diff(self, new_config_dict: dict) -> dict:
        """Compare new config with current config and return differences.

        Args:
            new_config_dict: Dictionary in format {'SECTION.key': 'value'} or anniversary form fields

        Returns:
            Dictionary of changed values in format:
            {'SECTION.key': {'old': 'old_value', 'new': 'new_value'}}
        """
        differences = {}

        # First, transform anniversary form fields into proper config format
        transformed_config = {}
        anniversary_entries = {}

        for key, value in new_config_dict.items():
            if key.startswith("anniversary_name_"):
                index = key.split("_")[-1]
                anniversary_entries.setdefault(index, {})["name"] = value
            elif key.startswith("anniversary_date_"):
                index = key.split("_")[-1]
                anniversary_entries.setdefault(index, {})["date"] = value
            elif key.startswith("anniversary_message_"):
                index = key.split("_")[-1]
                anniversary_entries.setdefault(index, {})["message"] = value
            elif key.startswith("anniversary_wait_"):
                index = key.split("_")[-1]
                anniversary_entries.setdefault(index, {})["wait"] = value
            else:
                transformed_config[key] = value

        # Convert anniversary entries to proper config format
        for index, entry in anniversary_entries.items():
            if all(k in entry for k in ["name", "date", "message", "wait"]):
                name = entry["name"].strip()
                if name:  # Only add if name is not empty
                    config_key = f"ANNIVERSARIES.{name}"
                    config_value = f"{entry['date']},{entry['message']},{entry['wait']}"
                    transformed_config[config_key] = config_value

        for key, new_value in transformed_config.items():
            if "." not in key:
                logger.warning(f"Invalid config key format for diff: {key}")
                continue

            section_name, config_key = key.split(".", 1)

            # Get current value from config
            try:
                if (
                    section_name in self._config
                    and config_key in self._config[section_name]
                ):
                    current_value = self._config[section_name][config_key]
                else:
                    # If section/key doesn't exist, use default from schema
                    schema_field = CONFIG_SCHEMA.get(section_name, {}).get(
                        config_key, {}
                    )
                    current_value = schema_field.get("default", "")

                # Convert values to strings for comparison
                current_str = str(current_value)
                new_str = str(new_value)

                # Only include if values are different
                if current_str != new_str:
                    differences[key] = {"old": current_str, "new": new_str}

            except Exception as e:
                logger.warning(f"Error comparing config value for {key}: {e}")
                continue

        return differences

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
                if "." not in key:
                    logger.warning(f"Invalid config key format: {key}")
                    continue

                section_name, config_key = key.split(".", 1)

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
            with open(self.config_path, "w") as f:
                self._config.write(f)
            logger.debug(f"Configuration written to {self.config_path}")
        except Exception as e:
            logger.error(f"Error writing config file: {e}")
            raise

    def _get_typed_value(self, section_name, field_name, field_type):
        """Get a configuration value with appropriate type conversion."""
        raw_value = self._config.get(section_name, field_name, fallback="")

        if field_type == "boolean":
            return raw_value.lower() in ("true", "1", "yes", "on")
        elif field_type == "number":
            try:
                # Try int first, then float
                if "." in raw_value:
                    return float(raw_value)
                else:
                    return int(raw_value)
            except ValueError:
                # Return default if conversion fails
                schema_field = CONFIG_SCHEMA.get(section_name, {}).get(field_name, {})
                default_value = schema_field.get("default", "0")
                return (
                    float(default_value) if "." in default_value else int(default_value)
                )
        else:
            return raw_value


# Auto-generate getter methods from CONFIG_SCHEMA
def _generate_getter_methods():
    """Generate getter methods for all fields in CONFIG_SCHEMA."""
    for section_name, fields in CONFIG_SCHEMA.items():
        for field_name, field_config in fields.items():
            method_name = f"get_{field_name}"
            field_type = field_config["type"]

            def make_getter(section, field, ftype):
                def getter(self):
                    return self._get_typed_value(section, field, ftype)

                getter.__name__ = method_name
                getter.__doc__ = f"Get {field} from {section} section."
                return getter

            # Add the method to the ConfigManager class
            setattr(
                ConfigManager,
                method_name,
                make_getter(section_name, field_name, field_type),
            )


# Generate all getter methods
_generate_getter_methods()
