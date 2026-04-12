"""Internal HTTP server for communication between main app and web config."""

from __future__ import annotations

import io
import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from flask import Flask, jsonify, request, send_file
from PIL import Image

if TYPE_CHECKING:
    from .config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class InternalServer:
    """Internal HTTP server for render coordinator communication."""

    def __init__(self, render_coordinator: Any, config_manager: ConfigManager) -> None:
        """Initialize internal server."""
        self.render_coordinator = render_coordinator
        self.config_manager = config_manager
        self.roon_client: Any = None
        self.app = Flask(__name__)
        self.app.logger.setLevel(logging.WARNING)
        self.setup_routes()

    def set_roon_client(self, roon_client: Any) -> None:
        """Register the Roon client so its connection state can be exposed."""
        self.roon_client = roon_client

    def setup_routes(self) -> None:
        """Setup internal API routes."""

        @self.app.route("/current-image")
        def get_current_image() -> Any:
            """Return the exact image currently on display."""
            try:
                image, metadata = self.render_coordinator.get_current_rendered_image()
                if image is not None:
                    img_io = io.BytesIO()
                    image.save(img_io, "JPEG", quality=85)
                    img_io.seek(0)
                    return send_file(img_io, mimetype="image/jpeg")
                else:
                    return self._create_placeholder_image()
            except Exception as e:
                logger.error(f"Error serving current image: {e}")
                return self._create_error_image(str(e))

        @self.app.route("/current-status")
        def get_current_status() -> Any:
            """Return current display status metadata."""
            try:
                image, metadata = self.render_coordinator.get_current_rendered_image()
                roon_state = (
                    self.roon_client.connection_state
                    if self.roon_client
                    else "disconnected"
                )
                return jsonify(
                    {
                        "has_image": image is not None,
                        "timestamp": metadata.get("timestamp"),
                        "content_type": metadata.get("content_type"),
                        "image_key": metadata.get("image_key"),
                        "track_info": metadata.get("track_info"),
                        "has_overlay": metadata.get("has_overlay", False),
                        "image_size": [image.width, image.height] if image else None,
                        "roon_state": roon_state,
                    }
                )
            except Exception as e:
                logger.error(f"Error getting current status: {e}")
                return jsonify({"has_image": False, "error": str(e)})

        @self.app.route("/preview", methods=["POST"])
        def generate_preview() -> Any:
            """Generate preview image with provided configuration."""
            try:
                config_data = request.get_json()
                preview_image = self.render_coordinator.render_preview(config_data)

                if preview_image:
                    img_io = io.BytesIO()
                    preview_image.save(img_io, "JPEG", quality=85)
                    img_io.seek(0)
                    return send_file(img_io, mimetype="image/jpeg")
                else:
                    return jsonify({"error": "Preview generation failed"}), 500
            except Exception as e:
                logger.error(f"Error generating preview: {e}")
                return jsonify({"error": f"Preview error: {e}"}), 500

        @self.app.route("/health")
        def health_check() -> Any:
            """Health check endpoint."""
            return jsonify(
                {
                    "status": "healthy",
                    "timestamp": time.time(),
                    "has_coordinator": self.render_coordinator is not None,
                }
            )

        @self.app.route("/update-config", methods=["POST"])
        def update_config() -> Any:
            """Update configuration values in real-time."""
            try:
                config_updates = request.get_json()
                if not config_updates:
                    return (
                        jsonify({"success": False, "error": "No config data provided"}),
                        400,
                    )

                success = self.config_manager.update_config_values(config_updates)

                if success:
                    return jsonify(
                        {
                            "success": True,
                            "message": f"Updated {len(config_updates)} configuration values",
                            "updated_keys": list(config_updates.keys()),
                        }
                    )
                else:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "Failed to update configuration",
                            }
                        ),
                        500,
                    )

            except Exception as e:
                logger.error(f"Error updating config via API: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/force-refresh", methods=["POST"])
        def force_refresh() -> Any:
            """Force a display refresh with current configuration."""
            try:
                self.render_coordinator.force_refresh()
                return jsonify(
                    {"success": True, "message": "Display refresh triggered"}
                )
            except Exception as e:
                logger.error(f"Error forcing display refresh: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

    def _create_placeholder_image(self) -> Any:
        """Create placeholder when no image available."""
        try:
            placeholder = Image.new("RGB", (400, 300), color=(128, 128, 128))
            img_io = io.BytesIO()
            placeholder.save(img_io, "JPEG", quality=85)
            img_io.seek(0)
            return send_file(img_io, mimetype="image/jpeg")
        except Exception as e:
            logger.error(f"Error creating placeholder: {e}")
            return jsonify({"error": "No image available"}), 404

    def _create_error_image(self, error_msg: str) -> Any:
        """Create error image when something goes wrong."""
        try:
            error_img = Image.new("RGB", (400, 300), color=(200, 100, 100))
            img_io = io.BytesIO()
            error_img.save(img_io, "JPEG", quality=85)
            img_io.seek(0)
            return send_file(img_io, mimetype="image/jpeg")
        except Exception:
            return jsonify({"error": error_msg}), 500

    def start(self) -> None:
        """Start the internal server in a background thread."""
        host = self.config_manager.get_internal_server_host()
        port = self.config_manager.get_internal_server_port()
        web_port = self.config_manager.get_web_config_port()

        if port == web_port:
            logger.error(
                f"internal_server_port ({port}) conflicts with "
                f"web_config_port ({web_port}) — web UI will not "
                f"be able to fetch display images. Change one of "
                f"them in the config file."
            )

        def run_server() -> None:
            try:
                import werkzeug  # noqa: F401

                werkzeug_logger = logging.getLogger("werkzeug")
                werkzeug_logger.setLevel(logging.WARNING)

                self.app.run(
                    host=host, port=port, debug=False, use_reloader=False, threaded=True
                )
            except Exception as e:
                logger.error(f"Internal server failed to start on port {port}: {e}")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        logger.info(f"Internal server started on http://{host}:{port}")

        time.sleep(0.5)
