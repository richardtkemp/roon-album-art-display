"""Internal HTTP server for communication between main app and web config."""

import io
import logging
import threading
import time
from typing import Optional, Tuple, Dict, Any

from flask import Flask, send_file, request, jsonify
from PIL import Image

logger = logging.getLogger(__name__)


class InternalServer:
    """Internal HTTP server for render coordinator communication."""
    
    def __init__(self, render_coordinator, config_manager):
        """Initialize internal server."""
        self.render_coordinator = render_coordinator
        self.config_manager = config_manager
        self.app = Flask(__name__)
        self.app.logger.setLevel(logging.WARNING)  # Reduce Flask logging
        self.setup_routes()
        
    def setup_routes(self):
        """Setup internal API routes."""
        
        @self.app.route('/current-image')
        def get_current_image():
            """Return the exact image currently on display."""
            try:
                image, metadata = self.render_coordinator.get_current_rendered_image()
                if image:
                    # Convert PIL image to bytes
                    img_io = io.BytesIO()
                    # Resize for web if needed
                    web_image = self._resize_for_web(image)
                    jpeg_quality = self.config_manager.get_jpeg_quality()
                    web_image.save(img_io, 'JPEG', quality=jpeg_quality)
                    img_io.seek(0)
                    return send_file(img_io, mimetype='image/jpeg')
                else:
                    return self._create_placeholder_image()
            except Exception as e:
                logger.error(f"Error serving current image: {e}")
                return self._create_error_image(str(e))
        
        @self.app.route('/current-status')
        def get_current_status():
            """Return current display status metadata."""
            try:
                image, metadata = self.render_coordinator.get_current_rendered_image()
                return jsonify({
                    'has_image': image is not None,
                    'timestamp': metadata.get('timestamp'),
                    'content_type': metadata.get('content_type'),
                    'image_key': metadata.get('image_key'),
                    'track_info': metadata.get('track_info'),
                    'has_overlay': metadata.get('has_overlay', False),
                    'image_size': [image.width, image.height] if image else None
                })
            except Exception as e:
                logger.error(f"Error getting current status: {e}")
                return jsonify({
                    'has_image': False,
                    'error': str(e)
                })
            
        @self.app.route('/preview', methods=['POST'])
        def generate_preview():
            """Generate preview image with provided configuration."""
            try:
                config_data = request.get_json()
                preview_image = self.render_coordinator.render_preview(config_data)
                
                if preview_image:
                    img_io = io.BytesIO()
                    web_image = self._resize_for_web(preview_image)
                    jpeg_quality = self.config_manager.get_jpeg_quality()
                    web_image.save(img_io, 'JPEG', quality=jpeg_quality)
                    img_io.seek(0)
                    return send_file(img_io, mimetype='image/jpeg')
                else:
                    return jsonify({'error': 'Preview generation failed'}), 500
            except Exception as e:
                logger.error(f"Error generating preview: {e}")
                return jsonify({'error': f'Preview error: {e}'}), 500
        
        @self.app.route('/health')
        def health_check():
            """Health check endpoint."""
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'has_coordinator': self.render_coordinator is not None
            })
        
        @self.app.route('/update-config', methods=['POST'])
        def update_config():
            """Update configuration values in real-time."""
            try:
                config_updates = request.get_json()
                if not config_updates:
                    return jsonify({'success': False, 'error': 'No config data provided'}), 400
                
                # Update configuration
                success = self.config_manager.update_config_values(config_updates)
                
                if success:
                    return jsonify({
                        'success': True, 
                        'message': f'Updated {len(config_updates)} configuration values',
                        'updated_keys': list(config_updates.keys())
                    })
                else:
                    return jsonify({'success': False, 'error': 'Failed to update configuration'}), 500
                    
            except Exception as e:
                logger.error(f"Error updating config via API: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    def _resize_for_web(self, image: Image.Image) -> Image.Image:
        """Resize image for web display while maintaining aspect ratio."""
        max_width = self.config_manager.get_web_image_max_width()
        if image.width <= max_width:
            return image.copy()
        
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        return image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    def _create_placeholder_image(self):
        """Create placeholder when no image available."""
        try:
            # Create simple placeholder image
            placeholder = Image.new('RGB', (400, 300), color=(128, 128, 128))
            
            # Add simple text (basic approach without fonts)
            # For now, just return gray placeholder
            img_io = io.BytesIO()
            jpeg_quality = self.config_manager.get_jpeg_quality()
            placeholder.save(img_io, 'JPEG', quality=jpeg_quality)
            img_io.seek(0)
            return send_file(img_io, mimetype='image/jpeg')
        except Exception as e:
            logger.error(f"Error creating placeholder: {e}")
            return jsonify({'error': 'No image available'}), 404
    
    def _create_error_image(self, error_msg: str):
        """Create error image when something goes wrong."""
        try:
            error_img = Image.new('RGB', (400, 300), color=(200, 100, 100))
            img_io = io.BytesIO()
            jpeg_quality = self.config_manager.get_jpeg_quality()
            error_img.save(img_io, 'JPEG', quality=jpeg_quality)
            img_io.seek(0)
            return send_file(img_io, mimetype='image/jpeg')
        except Exception:
            return jsonify({'error': error_msg}), 500
    
    def start(self):
        """Start the internal server in a background thread."""
        def run_server():
            try:
                # Disable Flask's startup messages
                import werkzeug
                werkzeug_logger = logging.getLogger('werkzeug')
                werkzeug_logger.setLevel(logging.WARNING)
                
                host = self.config_manager.get_internal_server_host()
                port = self.config_manager.get_internal_server_port()
                self.app.run(
                    host=host, 
                    port=port, 
                    debug=False, 
                    use_reloader=False,
                    threaded=True
                )
            except Exception as e:
                port = self.config_manager.get_internal_server_port()
                logger.error(f"Internal server failed to start on port {port}: {e}")
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        host = self.config_manager.get_internal_server_host()
        port = self.config_manager.get_internal_server_port()
        logger.info(f"Internal server started on http://{host}:{port}")
        
        # Give server a moment to start
        time.sleep(0.5)