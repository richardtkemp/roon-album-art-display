"""Configuration handling for the web interface."""

import configparser
import logging
import os
import platform
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import psutil
from werkzeug.utils import secure_filename

from ..config.config_manager import CONFIG_SCHEMA, COMPONENT_LOGGERS, ConfigManager
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

        # Build sections with current values from CONFIG_SCHEMA
        for section_name, schema_fields in CONFIG_SCHEMA.items():
            sections[section_name] = {}

            # Process all fields defined in schema
            for field_name, field_config in schema_fields.items():
                metadata = field_config.copy()

                # Get current value using auto-generated getter method
                getter_method_name = f"get_{field_name}"
                try:
                    if hasattr(self.config_manager, getter_method_name):
                        getter_method = getattr(self.config_manager, getter_method_name)
                        current_value = getter_method()
                        metadata["value"] = current_value
                    else:
                        logger.warning(
                            f"No getter method found for {section_name}.{field_name}"
                        )
                        metadata["value"] = field_config["default"]
                except Exception as e:
                    logger.warning(
                        f"Error getting value for {section_name}.{field_name}: {e}"
                    )
                    metadata["value"] = field_config["default"]

                # Add default value for restore/reset functionality
                metadata["default_value"] = field_config["default"]

                # Set default input type if not specified
                if "input_type" not in metadata:
                    if metadata["type"] == "boolean":
                        metadata["input_type"] = "checkbox"
                    elif metadata["type"] == "select":
                        metadata["input_type"] = "select"
                    elif metadata["type"] == "textarea":
                        metadata["input_type"] = "textarea"
                    else:
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

        # Add dynamic LOG_LEVELS section
        sections["LOG_LEVELS"] = {}
        for (
            component_name,
            default_level,
            logger_name,
            description,
        ) in COMPONENT_LOGGERS:
            # Get current value from config
            current_value = self.config_manager._config.get(
                "LOG_LEVELS", component_name, fallback=default_level
            )

            sections["LOG_LEVELS"][component_name] = {
                "type": "select",
                "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
                "value": current_value,
                "default": default_level,
                "default_value": default_level,
                "input_type": "select",
                "comment": f"Log level for {description}",
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
                "ip": {
                    "label": "Roon Server IP",
                    "value": self.config_manager.get_roon_server_ip()
                    or "Not configured",
                    "type": "info",
                },
                "port": {
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
