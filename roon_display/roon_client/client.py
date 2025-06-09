"""Roon API client for album art display."""

import logging
import threading
import time
from pathlib import Path

import requests
from PIL import Image
from roonapi import RoonApi, RoonDiscovery

from ..utils import get_saved_image_dir, set_current_image_key

logger = logging.getLogger(__name__)


class RoonClient:
    """Handles communication with Roon server."""

    def __init__(
        self, config_manager, viewer, image_processor, anniversary_manager=None
    ):
        """Initialize Roon client."""
        self.config_manager = config_manager
        self.viewer = viewer
        self.image_processor = image_processor
        self.anniversary_manager = anniversary_manager

        # Get configuration
        self.app_info = config_manager.get_app_info()
        self.allowed_zones, self.forbidden_zones = config_manager.get_zone_config()

        # Token storage in current directory
        self.token_file = Path(".roon_album_display_token.txt")

        # State tracking
        self.current_image_path = None
        self.last_event = None
        self.last_image_key = None
        self.running = False

        logger.info(f"Allowed zones: {self.allowed_zones}")
        logger.info(f"Forbidden zones: {self.forbidden_zones}")

    def connect(self):
        """Connect to Roon server."""
        logger.info("Connecting to Roon server...")

        # Try saved server first, then discovery
        self.roon = self._try_saved_connection() or self._discover_and_connect()

        if not self.roon:
            raise ConnectionError("Could not connect to Roon server")

        # Validate connection
        self._validate_connection()

        # Process current zones
        self._process_initial_zones()

        logger.info("Successfully connected to Roon server")
        return self.roon

    def _try_saved_connection(self):
        """Try connecting to saved server details."""
        server_ip, server_port = self.config_manager.get_server_config()

        if not server_ip or not server_port:
            logger.info("No saved server details found")
            return None

        logger.info(f"Trying saved server at {server_ip}:{server_port}")

        try:
            token = self._get_token()
            api = RoonApi(self.app_info, token, server_ip, server_port)

            # Add validation to confirm the connection is actually working
            if api and api.host:
                # Test the connection by trying to fetch zones
                try:
                    zones = api.zones
                    if zones is not None and zones:
                        logger.info("Successfully connected to saved server!")
                        logger.debug(f"Zones data: {zones}")
                        return self._finalize_connection(api, server_ip, server_port)
                    else:
                        api.stop()
                        logger.warning(
                            "Connected but couldn't fetch zones - token may be invalid"
                        )
                        return None
                except Exception as zone_error:
                    logger.warning(f"Error fetching zones: {zone_error}")
                    api.stop()
                    return None
            else:
                logger.warning("Saved server connection failed initial validation")
                return None

        except Exception as e:
            logger.warning(f"Failed to connect to saved server: {e}")
            return None

    def _finalize_connection(self, api, server_ip, server_port):
        """Finalize connection by saving token and server details."""
        if not api or not api.token:
            logger.error("Cannot finalize connection - no valid API or token")
            return None

        # Always save the token after successful connection
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

        return api

    def _discover_and_connect(self):
        """Discover and connect to Roon server."""
        logger.info("Starting Roon server discovery...")

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

        # Connect to first server found
        server_ip, server_port = servers[0]
        logger.info(f"Connecting to {server_ip}:{server_port}")

        try:
            api = RoonApi(self.app_info, token, server_ip, server_port, False)

            # Handle authorization
            if token is None and api:
                logger.info("Waiting for authorization in Roon app...")
                while api.token is None:
                    logger.info("Please approve this extension in Roon...")
                    time.sleep(2)
                logger.info("Authorization successful")
            elif api is not None:
                logger.info("Successfully connected using existing token")

            return self._finalize_connection(api, server_ip, server_port)

        except Exception as e:
            logger.error(f"Error connecting to server: {e}")
            return None

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
            logger.debug(f"Processing {event_type} event with data: {data}")

            if isinstance(data, list):
                for zone_item in data:
                    if isinstance(zone_item, str):
                        logger.debug(f"Processing zone item: {zone_item}")
                        zone_data = self.roon.zones.get(zone_item)
                        if zone_data:
                            logger.debug(
                                f"Found zone data for {zone_item}, calling _process_zone_data"
                            )
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
            logger.debug(f"_process_zone_data called with zone_id: {zone_id}")
            logger.debug(
                f"Zone data keys: {list(zone_data.keys()) if isinstance(zone_data, dict) else 'not dict'}"
            )

            name = zone_data.get("display_name", "")
            logger.debug(f"Zone name: '{name}'")

            # Check zone filters
            if self.forbidden_zones and name in self.forbidden_zones:
                logger.debug(f"Zone {name} is forbidden")
                return False

            if self.allowed_zones and name not in self.allowed_zones:
                logger.debug(f"Zone {name} not in allowed list")
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
            logger.debug("_process_now_playing called")
            logger.debug(
                f"Current now_playing keys: {list(now_playing.keys()) if isinstance(now_playing, dict) else 'not dict'}"
            )

            # Skip duplicate events
            if now_playing == self.last_event:
                logger.debug("Ignoring duplicate event - same as last_event")
                logger.debug(f"Last event was: {self.last_event}")
                return False

            logger.debug("This is a new event, processing...")
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
                logger.debug("Same image already displayed")
                return False

            logger.info(f"New track with image key: {image_key}")
            self.last_image_key = image_key

            # Extract track info
            track_info = self._extract_track_info(now_playing)
            logger.info(f"Now Playing: {track_info}")

            # Update anniversary manager with track change
            if self.anniversary_manager:
                self.anniversary_manager.update_last_track_time()

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

            # Update viewer
            logger.debug("Updating viewer with new image")
            self.viewer.update(image_key, image_path, img, track_info)

        except Exception as e:
            logger.error(f"Error fetching/displaying album art: {e}")

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

    def _display_anniversary(self, anniversary):
        """Display anniversary message and image."""
        try:
            logger.info(f"Displaying anniversary: {anniversary['name']}")

            # Create anniversary display using shared logic
            img = self.anniversary_manager.create_anniversary_display(
                anniversary, self.image_processor
            )

            # Update viewer with anniversary image
            self.viewer.update(
                "anniversary", None, img, f"Anniversary: {anniversary['message']}"
            )

        except Exception as e:
            logger.error(f"Error displaying anniversary: {e}")


    def run(self):
        """Start the Roon client event loop."""
        self.subscribe_to_events()
        self.running = True

        # Start event loop in separate thread
        event_thread = threading.Thread(target=self._event_loop)
        event_thread.start()

        return event_thread

    def _event_loop(self):
        """Main event loop."""
        try:
            logger.info("Roon client event loop started")

            while self.running:
                # Check for anniversaries (only if date changed)
                if self.anniversary_manager:
                    anniversary = self.anniversary_manager.check_anniversary_if_date_changed()
                    if anniversary:
                        logger.info(
                            f"Anniversary triggered: {anniversary['name']} - {anniversary['message']}"
                        )
                        self._display_anniversary(anniversary)

                # Sleep for 10 minutes - Roon events come via callbacks independently
                time.sleep(600)
        except Exception as e:
            logger.error(f"Error in event loop: {e}")
        finally:
            self.cleanup()

    def stop(self):
        """Stop the client."""
        self.running = False

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up Roon client...")
        if hasattr(self, "roon") and self.roon:
            self.roon.stop()
