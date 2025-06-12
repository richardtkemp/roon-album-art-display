"""Configuration handling for the web interface."""

import configparser
import logging
import os
import platform
import psutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple
from werkzeug.utils import secure_filename

from ..config.config_manager import ConfigManager
from ..utils import ensure_anniversary_dir_exists
from .utils import validate_image_format

logger = logging.getLogger(__name__)


class WebConfigHandler:
    """Handles configuration loading, saving, and validation for the web interface."""

    def __init__(self, config_path=None):
        """Initialize with optional config path."""
        self.config_path = config_path or Path("roon.cfg")
        self.config_manager = ConfigManager(self.config_path)

    def get_config_sections(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration sections with metadata for dynamic rendering."""
        sections = {}

        # Define metadata for each section and field
        field_metadata = {
            "NETWORK": {
                "internal_server_port": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Port for internal HTTP server (default: 9090)",
                },
                "web_config_port": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Port for web configuration server (default: 8080)",
                },
                "simulation_server_port": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Port for simulation server (default: 9999)",
                },
                "internal_server_host": {
                    "type": "text",
                    "comment": "Host address for internal server (default: 127.0.0.1)",
                },
                "web_config_host": {
                    "type": "text",
                    "comment": "Host address for web config server (default: 0.0.0.0)",
                },
            },
            "TIMEOUTS": {
                "roon_authorization_timeout": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Roon authorization timeout in seconds (default: 300)",
                },
                "health_script_timeout": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Health script execution timeout in seconds (default: 30)",
                },
                "reconnection_interval": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Time between reconnection attempts in seconds (default: 60)",
                },
                "web_request_timeout": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Web request timeout in seconds (default: 5)",
                },
            },
            "IMAGE_QUALITY": {
                "jpeg_quality": {
                    "type": "number",
                    "input_type": "number",
                    "min": "1",
                    "max": "100",
                    "comment": "JPEG quality for web images (1-100, default: 85)",
                },
                "web_image_max_width": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Maximum width for web images in pixels (default: 600)",
                },
                "thumbnail_size": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Thumbnail size in pixels (square, default: 100)",
                },
            },
            "DISPLAY_TIMING": {
                "web_auto_refresh_seconds": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Web interface auto-refresh interval in seconds (default: 10)",
                },
                "anniversary_check_interval": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Anniversary check interval in seconds (default: 60)",
                },
                "eink_success_threshold": {
                    "type": "number",
                    "input_type": "number",
                    "step": "1",
                    "min": "0",
                    "comment": "E-ink success threshold in seconds (default: 12)",
                },
                "preview_auto_revert_seconds": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Preview auto-revert time in seconds (default: 30)",
                },
                "preview_debounce_ms": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Preview debounce time in milliseconds (default: 500)",
                },
            },
            "LAYOUT": {
                "overlay_size_x_percent": {
                    "type": "number",
                    "input_type": "number",
                    "min": "5",
                    "max": "50",
                    "comment": "Overlay width percentage (5-50%, default: 33%)",
                },
                "overlay_size_y_percent": {
                    "type": "number",
                    "input_type": "number",
                    "min": "5",
                    "max": "50",
                    "comment": "Overlay height percentage (5-50%, default: 25%)",
                },
                "overlay_border_size": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Overlay border size in pixels (default: 20)",
                },
                "overlay_margin": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Overlay margin from screen edge in pixels (default: 20)",
                },
                "anniversary_border_percent": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Anniversary border percentage (default: 5%)",
                },
                "anniversary_text_percent": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Anniversary text area percentage (default: 15%)",
                },
                "line_spacing_ratio": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Line spacing ratio for text rendering (default: 8)",
                },
            },
            "DISPLAY": {
                "type": {
                    "type": "select",
                    "options": ["system_display", "epd13in3E"],
                    "comment": "Display type: system_display for regular monitors, epd13in3E for e-ink",
                },
                "tkinter_fullscreen": {
                    "type": "boolean",
                    "comment": "Enable fullscreen mode for system displays (ignored by e-ink)",
                },
            },
            "IMAGE_RENDER": {
                "colour_balance_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.01",
                    "min": "0",
                    "max": "3.0",
                    "comment": "Color balance adjustment (0.1-3, default: 1)",
                },
                "contrast_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.01",
                    "min": "0",
                    "max": "3.0",
                    "comment": "Contrast adjustment (0.1-3, default: 1)",
                },
                "sharpness_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.01",
                    "min": "0",
                    "max": "3.0",
                    "comment": "Sharpness adjustment (0.1-3, default: 1)",
                },
                "brightness_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.01",
                    "min": "0",
                    "max": "3.0",
                    "comment": "Brightness adjustment (0.1-3, default: 1)",
                },
            },
            "IMAGE_POSITION": {
                "position_offset_x": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Horizontal position offset in pixels",
                },
                "position_offset_y": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Vertical position offset in pixels",
                },
                "scale_x": {
                    "type": "number",
                    "input_type": "number",
                    "min": "0.1",
                    "max": "3.0",
                    "step": "0.01",
                    "comment": "Horizontal scale factor (0.1-3, default: 1)",
                },
                "scale_y": {
                    "type": "number",
                    "input_type": "number",
                    "min": "0.1",
                    "max": "3.0",
                    "step": "0.01",
                    "comment": "Vertical scale factor (0.1-3, default: 1)",
                },
                "rotation": {
                    "type": "select",
                    "options": ["0", "90", "180", "270"],
                    "comment": "Image rotation in degrees",
                },
            },
            "ZONES": {
                "allowed_zone_names": {
                    "type": "text",
                    "comment": "Comma-separated list of allowed zone names (leave blank for all)",
                },
                "forbidden_zone_names": {
                    "type": "text",
                    "comment": "Comma-separated list of forbidden zone names",
                },
            },
            "ANNIVERSARIES": {
                "enabled": {
                    "type": "boolean",
                    "comment": "Enable anniversary notifications",
                },
            },
            "MONITORING": {
                "log_level": {
                    "type": "select",
                    "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
                    "comment": "Logging level",
                },
                "loop_time": {
                    "type": "text",
                    "comment": 'Event loop sleep time (e.g., "10 minutes", "30 seconds")',
                },
                "performance_logging": {
                    "type": "select",
                    "options": ["", "info", "debug"],
                    "comment": "Enable performance logging (empty = disabled)",
                },
                "health_script": {
                    "type": "text",
                    "comment": "Path to health monitoring script (optional)",
                },
                "health_recheck_interval": {
                    "type": "text",
                    "comment": 'Time between health script calls (e.g., "30 minutes")',
                },
            },
        }

        # Define mapping from fields to config_manager getter methods
        field_getters = {
            "NETWORK": {
                "internal_server_port": self.config_manager.get_internal_server_port,
                "web_config_port": self.config_manager.get_web_config_port,
                "simulation_server_port": self.config_manager.get_simulation_server_port,
                "internal_server_host": self.config_manager.get_internal_server_host,
                "web_config_host": self.config_manager.get_web_config_host,
            },
            "TIMEOUTS": {
                "roon_authorization_timeout": self.config_manager.get_roon_authorization_timeout,
                "health_script_timeout": self.config_manager.get_health_script_timeout,
                "reconnection_interval": self.config_manager.get_reconnection_interval,
                "web_request_timeout": self.config_manager.get_web_request_timeout,
            },
            "IMAGE_QUALITY": {
                "jpeg_quality": self.config_manager.get_jpeg_quality,
                "web_image_max_width": self.config_manager.get_web_image_max_width,
                "thumbnail_size": self.config_manager.get_thumbnail_size,
            },
            "DISPLAY_TIMING": {
                "web_auto_refresh_seconds": self.config_manager.get_web_auto_refresh_seconds,
                "anniversary_check_interval": self.config_manager.get_anniversary_check_interval,
                "eink_success_threshold": self.config_manager.get_eink_success_threshold,
                "preview_auto_revert_seconds": self.config_manager.get_preview_auto_revert_seconds,
                "preview_debounce_ms": self.config_manager.get_preview_debounce_ms,
            },
            "LAYOUT": {
                "overlay_size_x_percent": self.config_manager.get_overlay_size_x_percent,
                "overlay_size_y_percent": self.config_manager.get_overlay_size_y_percent,
                "overlay_border_size": self.config_manager.get_overlay_border_size,
                "overlay_margin": self.config_manager.get_overlay_margin,
                "anniversary_border_percent": self.config_manager.get_anniversary_border_percent,
                "anniversary_text_percent": self.config_manager.get_anniversary_text_percent,
                "line_spacing_ratio": self.config_manager.get_line_spacing_ratio,
            },
            "IMAGE_RENDER": {
                "colour_balance_adjustment": self.config_manager.get_colour_balance_adjustment,
                "contrast_adjustment": self.config_manager.get_contrast_adjustment,
                "sharpness_adjustment": self.config_manager.get_sharpness_adjustment,
                "brightness_adjustment": self.config_manager.get_brightness_adjustment,
            },
            "IMAGE_POSITION": {
                "position_offset_x": self.config_manager.get_position_offset_x,
                "position_offset_y": self.config_manager.get_position_offset_y,
                "scale_x": self.config_manager.get_scale_x,
                "scale_y": self.config_manager.get_scale_y,
                "rotation": self.config_manager.get_rotation,
            },
            "DISPLAY": {
                "type": self.config_manager.get_display_type,
                "tkinter_fullscreen": self.config_manager.get_tkinter_fullscreen,
            },
            "ZONES": {
                "allowed_zone_names": self.config_manager.get_allowed_zone_names,
                "forbidden_zone_names": self.config_manager.get_forbidden_zone_names,
            },
            "MONITORING": {
                "log_level": self.config_manager.get_log_level_string,
                "loop_time": self.config_manager.get_loop_time_string,
                "performance_logging": self.config_manager.get_performance_logging_string,
                "health_script": self.config_manager.get_health_script,
                "health_recheck_interval": self.config_manager.get_health_recheck_interval_string,
            },
            "ANNIVERSARIES": {
                "enabled": self.config_manager.get_anniversaries_enabled,
            },
        }

        # Build sections with current values from config_manager
        for section_name, section_fields in field_metadata.items():
            sections[section_name] = {}

            # Process all fields defined in metadata
            for field_name, field_metadata_item in section_fields.items():
                metadata = field_metadata_item.copy()

                # Get current value using config_manager getter method
                if (
                    section_name in field_getters
                    and field_name in field_getters[section_name]
                ):
                    try:
                        current_value = field_getters[section_name][field_name]()
                        metadata["value"] = current_value
                    except Exception as e:
                        logger.warning(
                            f"Error getting value for {section_name}.{field_name}: {e}"
                        )
                        metadata["value"] = ""
                elif section_name == "DISPLAY":
                    # Special handling for DISPLAY section using individual getters
                    try:
                        if field_name == "type":
                            metadata["value"] = self.config_manager.get_display_type()
                        elif field_name == "tkinter_fullscreen":
                            metadata[
                                "value"
                            ] = self.config_manager.get_tkinter_fullscreen()
                        else:
                            metadata["value"] = ""
                    except Exception as e:
                        logger.warning(
                            f"Error getting display config for {field_name}: {e}"
                        )
                        metadata["value"] = ""
                else:
                    # This shouldn't happen now that all sections have getters
                    logger.warning(
                        f"No getter method found for {section_name}.{field_name}"
                    )
                    metadata["value"] = ""

                # Set default input type if not specified
                if "input_type" not in metadata:
                    metadata["input_type"] = "text"

                # Handle boolean conversion
                if metadata["type"] == "boolean":
                    if isinstance(metadata["value"], bool):
                        # Already a boolean
                        pass
                    else:
                        # Convert string to boolean
                        metadata["value"] = str(metadata["value"]).lower() in (
                            "true",
                            "1",
                            "yes",
                            "on",
                        )

                sections[section_name][field_name] = metadata

            # Handle anniversary entries separately (existing logic)
            if section_name == "ANNIVERSARIES":
                anniversaries_config = self.config_manager.get_anniversaries_config()
                for anniversary in anniversaries_config.get("anniversaries", []):
                    name = anniversary["name"]
                    date = anniversary["date"]
                    message = anniversary["message"]
                    wait_minutes = anniversary["wait_minutes"]

                    # Convert wait minutes back to string format
                    if wait_minutes >= 60:
                        wait_str = (
                            f"{wait_minutes // 60} hours"
                            if wait_minutes >= 120
                            else f"{wait_minutes // 60} hour"
                        )
                        if wait_minutes % 60 > 0:
                            wait_str += f" {wait_minutes % 60} minutes"
                    else:
                        wait_str = f"{wait_minutes} minutes"

                    sections[section_name][name] = {
                        "type": "anniversary",
                        "value": f"{date},{message},{wait_str}",
                        "input_type": "text",
                    }

        return sections

    def get_system_info(self) -> Dict[str, Dict[str, Any]]:
        """Get read-only system information for display."""

        def get_host_ip():
            """Get the primary host IP address."""
            try:
                # Connect to a remote address to determine local IP
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    return s.getsockname()[0]
            except Exception:
                return "Unknown"

        def get_wifi_ssid():
            """Get the current WiFi SSID."""
            try:
                if platform.system() == "Darwin":  # macOS
                    result = subprocess.run(
                        ["iwgetid", "-r"], capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
                elif platform.system() == "Linux":
                    # Try nmcli first
                    result = subprocess.run(
                        ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        for line in result.stdout.strip().split("\n"):
                            if line.startswith("yes:"):
                                return line.split(":", 1)[1]

                    # Fallback to iwgetid
                    result = subprocess.run(
                        ["iwgetid", "-r"], capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()

                return "Not connected to WiFi"
            except Exception:
                return "Unknown"

        def get_uptime():
            """Get system uptime."""
            try:
                uptime_seconds = psutil.boot_time()
                import time

                uptime_duration = time.time() - uptime_seconds
                days = int(uptime_duration // 86400)
                hours = int((uptime_duration % 86400) // 3600)
                minutes = int((uptime_duration % 3600) // 60)
                return f"{days}d {hours}h {minutes}m"
            except Exception:
                return "Unknown"

        def get_memory_usage():
            """Get memory usage percentage."""
            try:
                memory = psutil.virtual_memory()
                free_percent = round((memory.available / memory.total) * 100, 1)
                return f"{free_percent}% free"
            except Exception:
                return "Unknown"

        def get_disk_usage():
            """Get root disk usage percentage."""
            try:
                disk = psutil.disk_usage("/")
                free_percent = round((disk.free / disk.total) * 100, 1)
                return f"{free_percent}% free"
            except Exception:
                return "Unknown"

        system_info = {
            "ROON_SERVER": {
                "roon_server_ip": {
                    "label": "Roon Server IP",
                    "value": self.config_manager.get_roon_server_ip()
                    or "Not configured",
                    "type": "info",
                },
                "roon_server_port": {
                    "label": "Roon Server Port",
                    "value": self.config_manager.get_roon_server_port()
                    or "Not configured",
                    "type": "info",
                },
            },
            "HOST_SYSTEM": {
                "host_ip": {
                    "label": "Host IP Address",
                    "value": get_host_ip(),
                    "type": "info",
                },
                "wifi_ssid": {
                    "label": "WiFi Network",
                    "value": get_wifi_ssid(),
                    "type": "info",
                },
                "uptime": {
                    "label": "System Uptime",
                    "value": get_uptime(),
                    "type": "info",
                },
                "memory": {
                    "label": "Free Memory",
                    "value": get_memory_usage(),
                    "type": "info",
                },
                "disk": {
                    "label": "Free Disk Space",
                    "value": get_disk_usage(),
                    "type": "info",
                },
            },
        }
        return system_info

    def save_config(
        self, form_data: Dict[str, str], files: Dict[str, Any]
    ) -> Tuple[bool, List[str], Dict[str, str]]:
        """Save configuration from form data and handle image uploads.

        Returns:
            Tuple of (success: bool, error_messages: List[str], config_updates: Dict[str, str])
        """
        error_messages = []
        config_updates = {}  # Track changes for live update

        try:
            config = configparser.ConfigParser()
            config.read(self.config_path)

            # Process regular form data
            for field_name, value in form_data.items():
                if "." in field_name and not field_name.startswith("anniversary_"):
                    section_name, key = field_name.split(".", 1)

                    if section_name not in config:
                        config[section_name] = {}

                    # Track what's changing for live update
                    old_value = config[section_name].get(key, "")
                    if old_value != value:
                        config_updates[field_name] = value

                    config[section_name][key] = value

            # Handle anniversary entries separately
            anniversary_names = {}
            anniversary_dates = {}
            anniversary_messages = {}
            anniversary_waits = {}

            for field_name, value in form_data.items():
                if field_name.startswith("anniversary_name_"):
                    index = field_name.split("_")[-1]
                    anniversary_names[index] = value
                elif field_name.startswith("anniversary_date_"):
                    index = field_name.split("_")[-1]
                    anniversary_dates[index] = value
                elif field_name.startswith("anniversary_message_"):
                    index = field_name.split("_")[-1]
                    anniversary_messages[index] = value
                elif field_name.startswith("anniversary_wait_"):
                    index = field_name.split("_")[-1]
                    anniversary_waits[index] = value

            # Clear existing anniversary entries (except enabled/comments)
            if "ANNIVERSARIES" in config:
                keys_to_remove = []
                for key in config["ANNIVERSARIES"]:
                    if key not in ["enabled"] and not key.startswith("#"):
                        keys_to_remove.append(key)
                for key in keys_to_remove:
                    del config["ANNIVERSARIES"][key]

            # Add new anniversary entries
            if "ANNIVERSARIES" not in config:
                config["ANNIVERSARIES"] = {}

            for index in anniversary_names:
                if (
                    index in anniversary_dates
                    and index in anniversary_messages
                    and index in anniversary_waits
                ):
                    name = anniversary_names[index].strip()
                    date = anniversary_dates[index].strip()
                    message = anniversary_messages[index].strip()
                    wait = anniversary_waits[index].strip()

                    if name and date and message and wait:
                        # Combine into the expected format
                        config_value = f"{date},{message},{wait}"

                        # Track anniversary changes for live update
                        old_value = config["ANNIVERSARIES"].get(name, "")
                        if old_value != config_value:
                            config_updates[f"ANNIVERSARIES.{name}"] = config_value

                        config["ANNIVERSARIES"][name] = config_value

                        # Handle image uploads for this anniversary
                        file_field = f"anniversary_images_{index}"
                        if file_field in files:
                            uploaded_files = files.getlist(file_field)
                            if uploaded_files and uploaded_files[0].filename:
                                # Ensure anniversary directory exists
                                anniversary_dir = ensure_anniversary_dir_exists(name)

                                for uploaded_file in uploaded_files:
                                    if uploaded_file.filename:
                                        # Validate image
                                        file_data = uploaded_file.read()
                                        if validate_image_format(
                                            file_data, uploaded_file.filename
                                        ):
                                            # Save the file
                                            safe_filename = secure_filename(
                                                uploaded_file.filename
                                            )
                                            file_path = anniversary_dir / safe_filename

                                            with open(file_path, "wb") as f:
                                                f.write(file_data)

                                            logger.info(
                                                f"Saved anniversary image: {file_path}"
                                            )
                                        else:
                                            error_messages.append(
                                                f"Invalid image format for {uploaded_file.filename}. "
                                                f"Supported formats: JPG, PNG, BMP, GIF, TIFF, WebP, AVIF"
                                            )

            # Handle unchecked checkboxes
            sections = self.get_config_sections()
            for section_name, section_data in sections.items():
                for key, config_item in section_data.items():
                    if config_item["type"] == "boolean":
                        field_name = f"{section_name}.{key}"
                        if field_name not in form_data:
                            if section_name not in config:
                                config[section_name] = {}

                            # Track checkbox changes for live update
                            old_value = config[section_name].get(
                                key, "true"
                            )  # Default might be true
                            if old_value != "false":
                                config_updates[field_name] = "false"

                            config[section_name][key] = "false"

            # Save config file
            with open(self.config_path, "w") as f:
                config.write(f)

            logger.info("Configuration saved successfully")
            return True, error_messages, config_updates

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            error_messages.append(f"Error saving configuration: {e}")
            return False, error_messages, {}
