"""Roon API client for album art display."""

import logging
import threading
import time
from pathlib import Path

import requests
from PIL import Image
from roonapi import RoonApi, RoonDiscovery

from ..message_renderer import MessageRenderer
from ..utils import get_current_image_key, get_saved_image_dir, log_performance, set_current_image_key

logger = logging.getLogger(__name__)


class RoonClient:
    """Handles communication with Roon server."""

    def __init__(
        self,
        config_manager,
        viewer,
        image_processor,
        render_coordinator=None,
    ):
        """Initialize Roon client."""
        self.config_manager = config_manager
        self.viewer = viewer
        self.image_processor = image_processor
        self.render_coordinator = render_coordinator

        # Get configuration
        self.app_info = config_manager.get_app_info()
        self.allowed_zones, self.forbidden_zones = config_manager.get_zone_config()
        self.loop_time = config_manager.get_loop_time()

        # Token storage in current directory
        self.token_file = Path(".roon_album_display_token.txt")

        # State tracking
        self.current_image_path = None
        self.last_event = None
        # Initialize with current image key to prevent startup flash
        self.last_image_key = get_current_image_key()
        self.running = False
        self.connection_monitor_thread = None
        self.last_connection_check = time.time()
        self.last_reconnect_attempt = 0
        self.reconnect_interval = 60  # 1 minute between reconnect attempts
        
        # Connection state tracking (combines auth + connection)
        self.last_callback_time = 0
        self._is_connected = False

        logger.info(f"Allowed zones: {self.allowed_zones}")
        logger.info(f"Forbidden zones: {self.forbidden_zones}")
        logger.info(f"Event loop time: {self.loop_time} seconds")

    @property
    def is_connected(self):
        """Get connection status (combines auth + connection state)."""
        return self._is_connected
    
    @is_connected.setter
    def is_connected(self, value):
        """Set connection status with state change logging."""
        if self._is_connected != value:
            logger.warning(f"🔗 CONNECTION STATE CHANGE: {self._is_connected} → {value}")
            self._is_connected = value

    def connect(self):
        """Connect to Roon server."""
        logger.info("Connecting to Roon server...")

        # Try saved server first, then fall back to discovery
        server_ip, server_port = self._get_server_details()
        if server_ip and server_port:
            logger.info(f"Trying saved server at {server_ip}:{server_port}")
            self.roon = self._create_roon_connection(server_ip, server_port)

            # If saved server failed, try discovery
            if not self.roon:
                logger.warning(
                    "Saved server connection failed, falling back to discovery"
                )
                server_ip, server_port = self._discover_server()
                logger.info(
                    f"Connecting to discovered server at {server_ip}:{server_port}"
                )
                self.roon = self._create_roon_connection(server_ip, server_port)
        else:
            # No saved server, use discovery
            server_ip, server_port = self._discover_server()
            logger.info(f"Connecting to discovered server at {server_ip}:{server_port}")
            self.roon = self._create_roon_connection(server_ip, server_port)

        if not self.roon:
            self.is_connected = False
            self._report_health_failure("Failed to connect to Roon server")
            raise ConnectionError("Could not connect to Roon server")

        # Validate connection
        self._validate_connection()

        # Process current zones
        self._process_initial_zones()

        logger.info("Successfully connected to Roon server")
        return self.roon

    def _get_server_details(self):
        """Get saved server details if available."""
        return self.config_manager.get_server_config()

    def _discover_server(self):
        """Discover Roon server on network."""
        token = self._get_token()
        discover = RoonDiscovery(None)

        # Wait for server discovery
        while True:
            servers = discover.all()
            if servers:
                logger.info(f"Found {len(servers)} Roon server(s)")
                break
            logger.info("Waiting for Roon servers...")
            time.sleep(1)

        discover.stop()
        return servers[0]  # Return first server found

    def _create_roon_connection(self, server_ip, server_port):
        """Create RoonApi connection with authorization monitoring."""
        token = self._get_token()

        # Always start auth monitoring (even with existing token - it might be invalid)
        auth_monitor = self._start_auth_monitor()

        try:
            api = RoonApi(self.app_info, token, server_ip, server_port)
            logger.debug("RoonApi created successfully")

            # Test the connection by trying to fetch zones
            try:
                zones = api.zones
                if zones is not None:
                    logger.info("Successfully connected and validated!")
                    logger.debug(f"Found {len(zones)} zones")

                    # Save token and server details after successful connection
                    self._save_connection_details(api, server_ip, server_port)

                    # Report successful connection
                    self._report_health_success("Successfully connected to Roon server")

                    return api
                else:
                    api.stop()
                    logger.warning(
                        "Connected but couldn't fetch zones - token may be invalid"
                    )
                    self.is_connected = False
                    self._report_health_failure(
                        "Invalid or expired authentication token"
                    )
                    return None
            except Exception as zone_error:
                logger.warning(f"Error validating connection: {zone_error}")
                api.stop()
                self.is_connected = False
                self._report_health_failure(
                    f"Connection validation failed: {zone_error}"
                )
                return None

        except Exception as e:
            logger.error(f"Error creating RoonApi: {e}")
            self.is_connected = False
            self._report_health_failure(f"Roon connection failed: {e}")
            return None
        finally:
            # Stop authorization monitoring
            if auth_monitor:
                auth_monitor["stop_event"].set()
                auth_monitor["thread"].join(timeout=1)

    def _start_auth_monitor(self):
        """Start background thread to monitor for authorization needs."""
        import threading

        stop_event = threading.Event()
        auth_displayed = threading.Event()

        def monitor_auth():
            """Monitor for authorization state and display message."""
            # Wait a bit for websocket to connect
            time.sleep(2)

            timeout_seconds = 300  # 5 minutes timeout
            start_time = time.time()
            health_failure_sent = False

            while not stop_event.is_set():
                elapsed = time.time() - start_time

                # Check for timeout
                if elapsed > timeout_seconds:
                    logger.error("Authorization timeout after 5 minutes")
                    self.is_connected = False
                    if not health_failure_sent:
                        self._report_health_failure(
                            "Authorization timeout - user did not approve extension"
                        )
                        health_failure_sent = True
                    break

                # Check if we need authorization by trying to access zones
                try:
                    # If we can access zones, connection is working
                    if hasattr(self, "roon") and self.roon:
                        zones = self.roon.zones
                        if zones is not None:
                            # Connection is working, stop monitoring
                            logger.info("Connection successful - zones accessible")
                            self.is_connected = True
                            self._report_health_success(
                                "Roon connection successful - extension approved"
                            )
                            break
                except Exception as e:
                    logger.debug(f"Zones not accessible yet: {e}")

                # Still waiting for authorization - show message and send health failure
                if not auth_displayed.is_set():
                    self._display_authorization_message()
                    auth_displayed.set()

                    # Send health check failure for authorization needed
                    if not health_failure_sent:
                        self._report_health_failure(
                            "Waiting for Roon authorization - extension needs approval"
                        )
                        health_failure_sent = True

                time.sleep(2)

        thread = threading.Thread(target=monitor_auth, daemon=True)
        thread.start()

        return {"thread": thread, "stop_event": stop_event}

    def _get_token(self):
        """Get saved authentication token."""
        logger.info(f"Looking for token file at: {self.token_file}")
        if self.token_file.exists():
            try:
                token = self.token_file.read_text().strip()
                logger.info(f"Found existing auth token, length: {len(token)}")
                logger.info(f"Token starts with: {token[:20]}...")
                return token
            except Exception as e:
                logger.error(f"Error reading token file: {e}")
                return None
        else:
            logger.info("No existing auth token found")
            return None

    def _validate_connection(self):
        """Validate the Roon connection."""
        if not hasattr(self.roon, "_roonsocket"):
            raise ConnectionError("Invalid Roon connection: no socket")

        if not hasattr(self.roon._roonsocket, "failed_state"):
            raise ConnectionError("Invalid Roon connection: no state tracking")

        if self.roon._roonsocket.failed_state:
            raise ConnectionError("Roon connection is in failed state")

    def _process_initial_zones(self):
        """Process current zones for initial state."""
        for zone_id, zone_data in self.roon.zones.items():
            result = self._process_zone_data(zone_id, zone_data)
            if result:
                break

    def subscribe_to_events(self):
        """Subscribe to Roon zone change events."""
        logger.info("Subscribing to Roon events...")
        try:
            self.roon.register_state_callback(
                self._zone_event_callback, "zones_changed"
            )
            logger.info("Successfully subscribed to zone events")
        except Exception as e:
            logger.error(f"Error subscribing to events: {e}")

    def _zone_event_callback(self, event_type, data):
        """Handle zone change events."""
        try:
            # Update connection tracking - receiving callbacks means fully connected
            self.last_callback_time = time.time()
            if not self.is_connected:
                logger.info("Received zone callback - connection restored")
                self.is_connected = True
                
                # Clear any overlay errors when connection is restored
                if self.render_coordinator:
                    self.render_coordinator.clear_overlay()

            if isinstance(data, list):
                for zone_item in data:
                    if isinstance(zone_item, str):
                        zone_data = self.roon.zones.get(zone_item)
                        if zone_data:
                            self._process_zone_data(zone_item, zone_data)
                        else:
                            logger.warning(f"No zone data for ID: {zone_item}")
            else:
                logger.warning(f"Unexpected event data format: {type(data)}")

        except Exception as e:
            logger.error(f"Error in zone event callback: {e}")

    def _process_zone_data(self, zone_id, zone_data):
        """Process zone data and update display if needed."""
        try:
            name = zone_data.get("display_name", "")

            # Check zone filters
            if self.forbidden_zones and name in self.forbidden_zones:
                return False

            if self.allowed_zones and name not in self.allowed_zones:
                return False

            # Find now_playing data
            now_playing = self._extract_now_playing(zone_data)
            if now_playing:
                return self._process_now_playing(now_playing)

            return False

        except Exception as e:
            logger.error(f"Error processing zone data: {e}")
            return False

    def _extract_now_playing(self, zone_data):
        """Extract now_playing data from zone data structure."""
        if not isinstance(zone_data, dict):
            return None

        # Try direct access
        if "now_playing" in zone_data and zone_data["now_playing"]:
            return zone_data["now_playing"]

        # Try nested in state
        if (
            "state" in zone_data
            and isinstance(zone_data["state"], dict)
            and "now_playing" in zone_data["state"]
            and zone_data["state"]["now_playing"]
        ):
            return zone_data["state"]["now_playing"]

        # Try in queue
        if (
            "queue" in zone_data
            and isinstance(zone_data.get("queue"), dict)
            and "now_playing" in zone_data["queue"]
        ):
            return zone_data["queue"]["now_playing"]

        return None

    def _process_now_playing(self, now_playing):
        """Process now_playing data for image updates."""
        try:
            # Skip duplicate events
            if now_playing == self.last_event:
                return False

            self.last_event = now_playing

            # Extract image key
            image_key = (
                now_playing.get("image_key") if isinstance(now_playing, dict) else None
            )
            if not image_key:
                logger.warning("No image key found in now_playing data")
                return False

            # Skip if same image
            if image_key == self.last_image_key:
                return False

            logger.info(f"New track with image key: {image_key}")
            self.last_image_key = image_key

            # Extract track info
            track_info = self._extract_track_info(now_playing)
            logger.info(f"Now Playing: {track_info}")

            # Fetch and display album art
            self._fetch_and_display_album_art(image_key, track_info)
            return image_key

        except Exception as e:
            logger.error(f"Error processing now_playing: {e}")
            return False

    def _extract_track_info(self, now_playing):
        """Extract track information from now_playing data."""
        if not isinstance(now_playing, dict):
            return "Unknown Track"

        # Try three_line structure
        if "three_line" in now_playing and isinstance(now_playing["three_line"], dict):
            three_line = now_playing["three_line"]
            track = three_line.get("line1", "Unknown Track")
            artist = three_line.get("line2", "Unknown Artist")
            album = three_line.get("line3", "Unknown Album")
            return f"{track} - {artist} - {album}"

        # Try two_line structure
        if "two_line" in now_playing and isinstance(now_playing["two_line"], dict):
            two_line = now_playing["two_line"]
            track = two_line.get("line1", "Unknown Track")
            artist = two_line.get("line2", "Unknown Artist")
            return f"{track} - {artist}"

        # Try one_line structure
        if "one_line" in now_playing and isinstance(now_playing["one_line"], dict):
            return now_playing["one_line"].get("line1", "Unknown Track")

        return "Unknown Track"

    @log_performance(threshold=0.5, description="Fetch and display album art")
    def _fetch_and_display_album_art(self, image_key, track_info):
        """Fetch album art and update display."""
        try:
            image_path = get_saved_image_dir() / f"album_art_{image_key}.jpg"
            img = None

            if not image_path.exists():
                # Download new image
                img = self._download_album_art(image_key, image_path)
                if img is None:
                    logger.error("Failed to download album art")
                    return

            # Push art to render coordinator (or fallback to direct viewer update)
            if self.render_coordinator:
                self.render_coordinator.set_main_content(
                    content_type="art",
                    image_key=image_key,
                    image_path=image_path,
                    img=img,
                    track_info=track_info
                )
            else:
                logger.debug("No coordinator - updating viewer directly")
                self.viewer.update(image_key, image_path, img, track_info)

        except Exception as e:
            logger.error(f"Error fetching/displaying album art: {e}")

    @log_performance(threshold=0.5, description="Album art download")
    def _download_album_art(self, image_key, image_path):
        """Download album art from Roon server."""
        try:
            # Get image URL from Roon
            image_url = self.roon.get_image(
                image_key,
                "fit",
                self.image_processor.image_size,
                self.image_processor.image_size,
            )

            logger.info(f"Downloading album art from: {image_url}")

            # Download image
            response = requests.get(image_url, stream=True)
            response.raise_for_status()

            # Save to file
            with open(image_path, "wb") as f:
                f.write(response.content)

            # Load and process image
            img = Image.open(image_path)

            # Apply enhancements if configured
            if self.image_processor.needs_enhancement():
                img = self.image_processor.apply_enhancements(img)
                img.save(image_path)  # Save enhanced version

            logger.info(f"Successfully saved album art to {image_path}")
            return img

        except Exception as e:
            logger.error(f"Error downloading album art: {e}")
            return None


    def run(self):
        """Start the Roon client event loop."""
        self.subscribe_to_events()
        self.running = True

        # Start connection monitoring
        self.connection_monitor_thread = threading.Thread(
            target=self._monitor_connection, daemon=True
        )
        self.connection_monitor_thread.start()

        # Start event loop in separate thread
        event_thread = threading.Thread(target=self._event_loop)
        event_thread.start()

        return event_thread

    def _event_loop(self):
        """Main event loop."""
        try:
            logger.info("Roon client event loop started")

            while self.running:
                # Check if health script should be re-called (configurable interval)
                if (
                    self.viewer.health_manager
                    and self.viewer.health_manager.should_recheck_health()
                ):
                    self.viewer.health_manager.recheck_health()

                # Sleep for configured time - Roon events come via callbacks independently
                time.sleep(self.loop_time)
        except Exception as e:
            logger.error(f"Error in event loop: {e}")
        finally:
            self.cleanup()

    def _save_connection_details(self, api, server_ip, server_port):
        """Save token and server details after successful connection."""
        if not api or not api.token:
            logger.error("Cannot save connection details - no valid API or token")
            return

        # Save the token after successful connection
        try:
            logger.info(
                f"Saving token after successful connection: {api.token[:20]}..."
            )
            self.token_file.write_text(api.token)
            logger.info("Token saved successfully")

            # Verify token was saved
            if self.token_file.exists():
                saved_token = self.token_file.read_text().strip()
                logger.info(f"Verified token file exists, length: {len(saved_token)}")
            else:
                logger.error("Token file was not created!")
        except Exception as e:
            logger.error(f"Error saving token: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

        # Save server details
        self.config_manager.save_server_config(server_ip, server_port)

    def _report_health_success(self, message: str):
        """Report success to health manager."""
        if (
            self.viewer
            and hasattr(self.viewer, "health_manager")
            and self.viewer.health_manager
        ):
            self.viewer.health_manager.report_render_success(message)

    def _report_health_failure(self, message: str):
        """Report failure to health manager."""
        if (
            self.viewer
            and hasattr(self.viewer, "health_manager")
            and self.viewer.health_manager
        ):
            self.viewer.health_manager.report_render_failure(message)

    def _display_authorization_message(self):
        """Display authorization waiting message on screen."""
        try:
            message = (
                "Please approve this extension in the Roon app.\n\n"
                "Look for 'Album Art Display' in:\n"
                "Roon → Settings → Extensions\n\n"
                "Waiting for authorization...\n"
                "Timeout in 5:00"
            )

            renderer = MessageRenderer(
                self.image_processor.screen_width, self.image_processor.screen_height
            )
            img = renderer.create_text_message(message)

            # Push authorization error to coordinator (or fallback to direct viewer update)
            if self.render_coordinator:
                self.render_coordinator.set_overlay(
                    "Waiting for Roon authorization - extension needs approval"
                )
            else:
                self.viewer.update("auth_waiting", None, img, "Authorization Required")

        except Exception as e:
            logger.warning(f"Could not display authorization message: {e}")

    def _monitor_connection(self):
        """Monitor connection status and detect different failure types."""
        logger.info("Starting connection monitoring")

        while self.running:
            try:
                if hasattr(self, "roon") and self.roon:
                    # Check if RoonAPI is still connected
                    if hasattr(self.roon, "_roonsocket"):
                        socket_state = self.roon._roonsocket

                        # Check for failed state
                        if (
                            hasattr(socket_state, "failed_state")
                            and socket_state.failed_state
                        ):
                            logger.warning("RoonAPI socket is in failed state")
                            self._handle_connection_failure("roon_host_down")

                        # Check if websocket is still connected
                        elif hasattr(socket_state, "websocket"):
                            ws = socket_state.websocket
                            if ws and hasattr(ws, "sock") and ws.sock is None:
                                logger.warning("WebSocket connection lost")
                                self._handle_connection_failure("roon_host_down")

                        # Periodic connection health check
                        try:
                            if (
                                time.time() - self.last_connection_check > 30
                            ):  # Check every 30 seconds
                                self.last_connection_check = time.time()
                        except Exception as e:
                            logger.warning(f"Connection test failed: {e}")
                            # Distinguish between network errors and auth errors
                            if (
                                "unauthorized" in str(e).lower()
                                or "auth" in str(e).lower()
                            ):
                                self._handle_connection_failure("auth_revoked")
                            else:
                                self._handle_connection_failure("roon_host_down")
                
                # If disconnected, attempt reconnection every minute
                elif not self.is_connected:
                    current_time = time.time()
                    if current_time - self.last_reconnect_attempt >= self.reconnect_interval:
                        logger.info("Attempting to reconnect to Roon server...")
                        self.last_reconnect_attempt = current_time
                        try:
                            self.connect()
                            # Connection was established, but we need to wait for callbacks to confirm full connectivity
                            if hasattr(self, "roon") and self.roon:
                                logger.info("Reconnection attempt completed - waiting for zone callbacks to confirm connectivity")
                                # Don't immediately set is_connected = True - wait for callbacks
                                # The callback handler will set it when we receive zone updates
                            else:
                                logger.warning("Reconnection failed - no valid API connection")
                        except Exception as e:
                            logger.warning(f"Reconnection failed: {e}")
                            # Continue showing error and try again next interval

                time.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Error in connection monitoring: {e}")
                time.sleep(10)

    def _handle_connection_failure(self, failure_type: str):
        """Handle different types of connection failures."""
        logger.error(f"Connection failure detected: {failure_type}")
        
        # Set disconnected state for reconnection attempts
        if self.is_connected:
            self.is_connected = False
            self.last_reconnect_attempt = time.time()

        if failure_type == "auth_revoked":
            # Show re-authorization message
            message = (
                "Authorization has been revoked!\n\n"
                "Please re-approve this extension in the Roon app.\n\n"
                "Look for 'Album Art Display' in:\n"
                "Roon → Settings → Extensions\n\n"
                "Waiting for re-authorization..."
            )

            # Push authorization revoked error to coordinator
            if self.render_coordinator:
                self.render_coordinator.set_overlay(message, timeout=300)  # 5 minute timeout
            else:
                # Fallback to direct viewer update
                try:
                    renderer = MessageRenderer(
                        self.image_processor.screen_width,
                        self.image_processor.screen_height,
                    )
                    img = renderer.create_text_message(message)
                    self.viewer.update(
                        "auth_revoked", None, img, "Re-Authorization Required"
                    )
                    logger.info("Displayed re-authorization message")
                except Exception as e:
                    logger.error(f"Could not display re-auth message: {e}")

            # Report to health manager
            self._report_health_failure(
                "Roon authorization revoked - extension needs re-approval"
            )

        elif failure_type == "roon_host_down":
            # Roon host or process issue
            message = (
                "Connection to Roon server lost!\n\n"
                "Possible causes:\n"
                "• Roon server stopped\n"
                "• Roon host is down\n"
                "• Network connectivity issue\n"
                "• Server IP address changed\n\n"
                "Attempting to reconnect..."
            )

            # Push host down error to coordinator
            if self.render_coordinator:
                self.render_coordinator.set_overlay(message, timeout=120)  # 2 minute timeout
            else:
                # Fallback to direct viewer update
                try:
                    renderer = MessageRenderer(
                        self.image_processor.screen_width,
                        self.image_processor.screen_height,
                    )
                    img = renderer.create_text_message(message)
                    self.viewer.update(
                        "roon_host_down", None, img, "Roon Server Unavailable"
                    )
                    logger.info("Displayed Roon server unavailable message")
                except Exception as e:
                    logger.error(f"Could not display server unavailable message: {e}")

            # Report to health manager
            self._report_health_failure(
                "Roon server unavailable - host down or process not responding"
            )

    def stop(self):
        """Stop the client."""
        self.running = False

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up Roon client...")
        if hasattr(self, "roon") and self.roon:
            self.roon.stop()
