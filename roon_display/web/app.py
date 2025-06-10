"""Main Flask application for Roon Display web configuration."""

import io
import logging
from pathlib import Path
from typing import Any, Dict

import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from .config_handler import WebConfigHandler
from .utils import (
    create_placeholder_image,
    create_thumbnail,
    delete_anniversary_image,
    get_anniversary_images,
)
from ..utils import get_extra_images_dir

logger = logging.getLogger(__name__)


class InternalAppClient:
    """HTTP client for communication with the main Roon display app."""

    def __init__(self, config_manager):
        """Initialize client with config manager."""
        self.config_manager = config_manager
        host = config_manager.get_internal_server_host()
        port = config_manager.get_internal_server_port()
        self.base_url = f"http://{host}:{port}"

    def get_current_image(self) -> bytes:
        """Get current display image from main app."""
        try:
            timeout = self.config_manager.get_web_request_timeout()
            response = requests.get(f"{self.base_url}/current-image", timeout=timeout)
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(
                    f"Failed to get current image: HTTP {response.status_code}"
                )
                return None
        except requests.RequestException as e:
            logger.debug(f"Failed to get current image: {e}")
            return None

    def get_current_status(self) -> Dict[str, Any]:
        """Get current display status from main app."""
        try:
            timeout = self.config_manager.get_web_request_timeout()
            response = requests.get(f"{self.base_url}/current-status", timeout=timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"Failed to get current status: HTTP {response.status_code}"
                )
                return {}
        except requests.RequestException as e:
            logger.debug(f"Failed to get current status: {e}")
            return {}

    def generate_preview(self, config_data: Dict) -> bytes:
        """Generate preview image with config changes."""
        try:
            response = requests.post(
                f"{self.base_url}/preview",
                json=config_data,
                timeout=self.config_manager.get_web_request_timeout() * 2,
            )
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(
                    f"Failed to generate preview: HTTP {response.status_code}"
                )
                return None
        except requests.RequestException as e:
            logger.debug(f"Failed to generate preview: {e}")
            return None

    def check_health(self) -> bool:
        """Check if main app is responsive."""
        try:
            timeout = max(2, self.config_manager.get_web_request_timeout() // 2)
            response = requests.get(f"{self.base_url}/health", timeout=timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def update_config(self, config_updates: dict) -> dict:
        """Send configuration updates to main app."""
        try:
            timeout = self.config_manager.get_web_request_timeout()
            response = requests.post(
                f"{self.base_url}/update-config", json=config_updates, timeout=timeout
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to update config: HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except requests.RequestException as e:
            logger.debug(f"Failed to update config: {e}")
            return {"success": False, "error": str(e)}


def create_app(config_path=None, port=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "roon-display-config-key"

    # Initialize configuration handler
    config_handler = WebConfigHandler(config_path)
    internal_client = InternalAppClient(config_handler.config_manager)

    # Store instances for route access
    app.config["config_handler"] = config_handler
    app.config["internal_client"] = internal_client

    @app.route("/", methods=["GET", "POST"])
    def config_interface():
        """Main configuration interface."""
        if request.method == "POST":
            # Check if this is an AJAX request
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

            success, error_messages, config_updates = config_handler.save_config(
                request.form, request.files
            )

            if is_ajax:
                # Return JSON response for AJAX requests
                if success:
                    message = "Configuration updated successfully!"

                    # Send config updates to main process for immediate effect
                    if config_updates:
                        update_result = internal_client.update_config(config_updates)
                        if not update_result.get("success"):
                            message = f'Configuration saved but live update failed: {update_result.get("error", "Unknown error")}'
                            logger.warning(f"Live config update failed: {update_result}")
                        else:
                            logger.info(
                                f"Live config update successful: {update_result.get('updated_keys', [])}"
                            )

                    # Include any image upload warnings in the message
                    if error_messages:
                        warnings_text = "; ".join(error_messages)
                        message = f"{message} (Warnings: {warnings_text})"

                    return jsonify({"success": True, "message": message})
                else:
                    error_text = "Error saving configuration!"
                    if error_messages:
                        error_text = "; ".join([error_text] + error_messages)

                    return jsonify({"success": False, "message": error_text})
            else:
                # Traditional form submission - keep existing redirect behavior
                if success:
                    # Send config updates to main process for immediate effect
                    if config_updates:
                        update_result = internal_client.update_config(config_updates)
                        if update_result.get("success"):
                            flash("Configuration updated successfully!", "success")
                            logger.info(
                                f"Live config update successful: {update_result.get('updated_keys', [])}"
                            )
                        else:
                            flash(
                                f'Configuration saved but live update failed: {update_result.get("error", "Unknown error")}',
                                "error",
                            )
                            logger.warning(f"Live config update failed: {update_result}")
                    else:
                        flash("Configuration saved successfully!", "success")

                    # Show any image upload warnings
                    for error_msg in error_messages:
                        flash(error_msg, "error")

                else:
                    flash("Error saving configuration!", "error")
                    for error_msg in error_messages:
                        flash(error_msg, "error")

                # Store current tab and scroll position for redirect
                current_tab = request.form.get("current_tab", "Image")
                scroll_position = request.form.get("scroll_position", "0")
                return redirect(
                    url_for("config_interface", tab=current_tab, scroll=scroll_position)
                )

        # GET request - show form
        sections = config_handler.get_config_sections()

        # Organize sections into tabs
        tab_sections = {
            "Image": {
                "IMAGE_RENDER": sections.get("IMAGE_RENDER", {}),
                "IMAGE_POSITION": sections.get("IMAGE_POSITION", {}),
                "LAYOUT": sections.get("LAYOUT", {}),
                "IMAGE_QUALITY": sections.get("IMAGE_QUALITY", {}),
            },
            "Features": {
                "ZONES": sections.get("ZONES", {}),
                "ANNIVERSARIES": sections.get("ANNIVERSARIES", {}),
            },
            "Advanced": {
                "DISPLAY": sections.get("DISPLAY", {}),
                "NETWORK": sections.get("NETWORK", {}),
                "TIMEOUTS": sections.get("TIMEOUTS", {}),
                "DISPLAY_TIMING": sections.get("DISPLAY_TIMING", {}),
                "MONITORING": sections.get("MONITORING", {}),
            },
        }

        # Count anniversary entries for JavaScript counter
        anniversary_count = 0
        if "ANNIVERSARIES" in sections:
            anniversary_count = len(
                [
                    k
                    for k in sections["ANNIVERSARIES"].keys()
                    if k not in ["enabled"] and not k.startswith("#")
                ]
            )

        # Get existing anniversary images
        anniversary_images = get_anniversary_images()

        # Get web timing values from config
        refresh_interval_seconds = config_handler.config_manager.get_web_auto_refresh_seconds()
        debounce_ms = config_handler.config_manager.get_preview_debounce_ms()
        auto_revert_seconds = config_handler.config_manager.get_preview_auto_revert_seconds()

        return render_template(
            "config_form.html",
            tab_sections=tab_sections,
            sections=sections,
            anniversary_count=anniversary_count,
            anniversary_images=anniversary_images,
            web_refresh_interval=refresh_interval_seconds * 1000,  # Convert to milliseconds
            preview_debounce_ms=debounce_ms,
            preview_auto_revert_ms=auto_revert_seconds * 1000,  # Convert to milliseconds
        )

    @app.route("/thumbnail/<anniversary_name>/<filename>")
    def serve_thumbnail(anniversary_name, filename):
        """Serve thumbnail images for anniversary photos."""
        try:
            # Validate the anniversary name and filename for security
            safe_anniversary = secure_filename(anniversary_name)
            safe_filename = secure_filename(filename)

            if not safe_anniversary or not safe_filename:
                return "Invalid filename", 400

            # Get the image path
            image_path = get_extra_images_dir() / safe_anniversary / safe_filename

            if not image_path.exists():
                return "Image not found", 404

            # Create and return thumbnail
            thumbnail_size = config_handler.config_manager.get_thumbnail_size()
            jpeg_quality = config_handler.config_manager.get_jpeg_quality()
            thumbnail_data = create_thumbnail(
                image_path,
                max_size=(thumbnail_size, thumbnail_size),
                jpeg_quality=jpeg_quality,
            )
            if thumbnail_data:
                return send_file(
                    io.BytesIO(thumbnail_data),
                    mimetype="image/jpeg",
                    as_attachment=False,
                    download_name=f"thumb_{safe_filename}",
                )
            else:
                return "Could not create thumbnail", 500

        except Exception as e:
            logger.error(f"Error serving thumbnail {anniversary_name}/{filename}: {e}")
            return "Internal server error", 500

    @app.route("/delete-image", methods=["POST"])
    def delete_image():
        """Delete an anniversary image."""
        try:
            data = request.get_json()
            anniversary_name = data.get("anniversary_name")
            filename = data.get("filename")

            if not anniversary_name or not filename:
                return jsonify(
                    {"success": False, "error": "Missing anniversary name or filename"}
                )

            # Validate and secure the filenames
            safe_anniversary = secure_filename(anniversary_name)
            safe_filename = secure_filename(filename)

            if not safe_anniversary or not safe_filename:
                return jsonify({"success": False, "error": "Invalid filename"})

            # Delete the image
            success = delete_anniversary_image(safe_anniversary, safe_filename)

            if success:
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to delete image"})

        except Exception as e:
            logger.error(f"Error in delete image endpoint: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/display-status")
    def display_status():
        """Get current display status from main app."""
        try:
            status_data = internal_client.get_current_status()

            # Add connection status
            status_data["internal_app_connected"] = internal_client.check_health()

            return jsonify(status_data)
        except Exception as e:
            logger.error(f"Error getting display status: {e}")
            return jsonify(
                {
                    "internal_app_connected": False,
                    "track_info": "Connection error",
                    "timestamp": None,
                }
            )

    @app.route("/current-display-image")
    def serve_current_display_image():
        """Proxy current display image from main app."""
        try:
            image_data = internal_client.get_current_image()
            if image_data:
                return send_file(
                    io.BytesIO(image_data), mimetype="image/jpeg", as_attachment=False
                )
            else:
                # Return placeholder image when no image available
                jpeg_quality = config_handler.config_manager.get_jpeg_quality()
                placeholder_data = create_placeholder_image(jpeg_quality)
                if placeholder_data:
                    return send_file(
                        io.BytesIO(placeholder_data), mimetype="image/jpeg", as_attachment=False
                    )
                else:
                    return jsonify({"error": "No image available"}), 404
        except Exception as e:
            logger.error(f"Error serving current display image: {e}")
            jpeg_quality = config_handler.config_manager.get_jpeg_quality()
            placeholder_data = create_placeholder_image(jpeg_quality)
            if placeholder_data:
                return send_file(
                    io.BytesIO(placeholder_data), mimetype="image/jpeg", as_attachment=False
                )
            else:
                return jsonify({"error": "No image available"}), 404

    @app.route("/preview-image", methods=["POST"])
    def generate_preview_image():
        """Generate preview image with form changes."""
        try:
            # Parse form data into config format, excluding file uploads for now
            config_data = _parse_form_to_config_for_preview(request.form, request.files)

            # Request preview from main app
            preview_data = internal_client.generate_preview(config_data)

            if preview_data:
                return send_file(
                    io.BytesIO(preview_data), mimetype="image/jpeg", as_attachment=False
                )
            else:
                return jsonify({"error": "Preview generation failed"}), 500
        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            return jsonify({"error": str(e)}), 500

    def _parse_form_to_config_for_preview(form_data, files) -> Dict[str, Any]:
        """Parse form data for preview generation, excluding non-serializable file objects."""
        config = {}

        try:
            # Parse regular configuration fields (section.field format)
            for key, value in form_data.items():
                if "." in key and not key.startswith("anniversary_"):
                    # Handle nested config like IMAGE_RENDER.brightness_adjustment
                    config[key] = value
                elif key.startswith("anniversary_"):
                    # Handle anniversary fields
                    config[key] = value
                else:
                    # Handle other fields
                    config[key] = value

            # Handle checkboxes that are only present when checked
            checkbox_fields = ["ANNIVERSARIES.enabled", "DISPLAY.tkinter_fullscreen"]

            for checkbox_field in checkbox_fields:
                if checkbox_field not in config:
                    config[checkbox_field] = "false"

            # For preview, we'll skip file uploads for now
            if files:
                file_count = sum(
                    len(file_list) if hasattr(file_list, "__len__") else 1
                    for file_list in files.values()
                    if file_list
                )
                if file_count > 0:
                    config["_has_file_uploads"] = str(file_count)
                    logger.debug(
                        f"Preview request has {file_count} file uploads (skipped for preview)"
                    )

            logger.debug(f"Parsed form to preview config with {len(config)} fields")
            return config

        except Exception as e:
            logger.error(f"Error parsing form data for preview: {e}")
            return {}

    return app


def main():
    """Main entry point for web config server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Roon Display Web Configuration Server"
    )
    parser.add_argument(
        "--port", type=int, help="Port to run server on (overrides config)"
    )
    parser.add_argument("--host", help="Host to bind to (overrides config)")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create Flask app
    app = create_app(config_path=args.config)
    config_handler = app.config["config_handler"]

    # Get host and port from config or command line
    host = args.host or config_handler.config_manager.get_web_config_host()
    port = args.port or config_handler.config_manager.get_web_config_port()

    logger.info(f"Starting Roon Display web configuration server on {host}:{port}")

    try:
        app.run(host=host, port=port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Web configuration server stopped")


if __name__ == "__main__":
    main()