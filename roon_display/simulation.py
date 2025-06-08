"""Simulation support for testing track changes."""

import json
import logging
import socket
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Sample track data from logs
SAMPLE_TRACKS = [
    {
        "title": "Pink Pony Club",
        "artist": "Chappell Roan",
        "album": "The Rise and Fall of a Midwest Princess",
        "image_key": "82ce9f584bb953714e2500a5946f5064",
    },
    {
        "title": "Cry For Me",
        "artist": "The Weeknd",
        "album": "Hurry Up Tomorrow",
        "image_key": "8b0f35677345e77e976e536bc65b4ab2",
    },
    {
        "title": "Come on In",
        "artist": "R.L. Burnside",
        "album": "1st Recordings",
        "image_key": "6416ec7233fd9891679b02e339ef0372",
    },
    {
        "title": "Pink Pony Club",
        "artist": "Chappell Roan",
        "album": "The Rise and Fall of a Midwest Princess",
        "image_key": "82ce9f584bb953714e2500a5946f5064",
    },
]

SIMULATION_PORT = 9999
TRACK_INDEX_FILE = Path("simulation_track_index.txt")


class SimulationServer:
    """Simple TCP server to receive simulation triggers."""

    def __init__(self, roon_client):
        self.roon_client = roon_client
        self.server = None
        self.running = False

    def start(self):
        """Start the simulation server."""
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind(("localhost", SIMULATION_PORT))
            self.server.listen(1)
            self.running = True

            logger.info(f"Simulation server started on port {SIMULATION_PORT}")

            # Start server thread
            server_thread = threading.Thread(target=self._server_loop, daemon=True)
            server_thread.start()

        except Exception as e:
            logger.error(f"Failed to start simulation server: {e}")

    def _server_loop(self):
        """Main server loop."""
        while self.running:
            try:
                self.server.settimeout(1.0)  # Add timeout to prevent hanging
                client, addr = self.server.accept()
                logger.debug(f"Simulation trigger received from {addr}")

                try:
                    # Read the track index with timeout
                    client.settimeout(2.0)
                    logger.debug("Reading data from client...")
                    data = client.recv(1024).decode().strip()
                    logger.debug(f"Received data: '{data}'")

                    if data.isdigit():
                        track_index = int(data)
                        logger.debug(f"Parsed track_index: {track_index}")
                        logger.debug("About to call _simulate_track_change...")
                        self._simulate_track_change(track_index)
                        logger.debug("_simulate_track_change completed")
                    else:
                        logger.warning(f"Invalid data received: '{data}'")

                    # Send response
                    logger.debug("Sending OK response...")
                    client.send(b"OK")
                    logger.debug("Response sent successfully")
                except Exception as e:
                    logger.error(f"Error handling client: {e}")
                    import traceback

                    logger.error(f"Traceback: {traceback.format_exc()}")
                finally:
                    try:
                        client.close()
                    except Exception:
                        pass

            except socket.timeout:
                continue  # Continue loop on timeout
            except Exception as e:
                if self.running:
                    logger.error(f"Simulation server error: {e}")

    def _simulate_track_change(self, track_index):
        """Simulate a track change with the given track using exact log data structure."""
        track_data = SAMPLE_TRACKS[track_index % len(SAMPLE_TRACKS)]

        logger.info(
            f"Simulating track change: {track_data['title']} by {track_data['artist']}"
        )

        # Use the exact zone data structure from your logs
        mock_zone_data = {
            "zone_id": "1601e4d6660c81a5eed2399191df1a3d21b4",
            "display_name": "System Output",
            "outputs": [
                {
                    "output_id": "1701e4d6660c81a5eed2399191df1a3d21b4",
                    "zone_id": "1601e4d6660c81a5eed2399191df1a3d21b4",
                    "can_group_with_output_ids": [
                        "1701e4d6660c81a5eed2399191df1a3d21b4"
                    ],
                    "display_name": "System Output",
                    "volume": {
                        "type": "number",
                        "min": 0,
                        "max": 100,
                        "value": 100,
                        "step": 1,
                        "is_muted": False,
                        "hard_limit_min": 0,
                        "hard_limit_max": 100,
                        "soft_limit": 100,
                    },
                    "source_controls": [
                        {
                            "control_key": "1",
                            "display_name": "System Output",
                            "supports_standby": False,
                            "status": "indeterminate",
                        }
                    ],
                }
            ],
            "state": "playing",
            "is_next_allowed": True,
            "is_previous_allowed": True,
            "is_pause_allowed": False,
            "is_play_allowed": True,
            "is_seek_allowed": True,
            "queue_items_remaining": 1,
            "queue_time_remaining": 102,
            "settings": {"loop": "disabled", "shuffle": False, "auto_radio": True},
            "now_playing": {
                "seek_position": 7,
                "length": 109,
                "one_line": {
                    "line1": f"{track_data['title']} - {track_data['artist']}"
                },
                "two_line": {
                    "line1": track_data["title"],
                    "line2": track_data["artist"],
                },
                "three_line": {
                    "line1": track_data["title"],
                    "line2": track_data["artist"],
                    "line3": track_data["album"],
                },
                "image_key": track_data["image_key"],
                "artist_image_keys": ["ca566e30bf02ef6ac7990a619ddf4335"],
            },
        }

        try:
            logger.debug("About to call _process_zone_data...")
            logger.debug("Zone ID: '1601e4d6660c81a5eed2399191df1a3d21b4'")
            logger.debug(f"Mock zone data keys: {list(mock_zone_data.keys())}")

            # Call _process_zone_data directly with exact log structure
            result = self.roon_client._process_zone_data(
                "1601e4d6660c81a5eed2399191df1a3d21b4", mock_zone_data
            )
            logger.info(
                f"Simulation track change sent via _process_zone_data, result: {result}"
            )
        except Exception as e:
            logger.error(f"Error sending simulation update: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    def stop(self):
        """Stop the simulation server."""
        self.running = False
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass


def get_next_track_index():
    """Get the next track index to use."""
    try:
        if TRACK_INDEX_FILE.exists():
            with open(TRACK_INDEX_FILE, "r") as f:
                current_index = int(f.read().strip())
        else:
            current_index = -1

        next_index = (current_index + 1) % len(SAMPLE_TRACKS)

        with open(TRACK_INDEX_FILE, "w") as f:
            f.write(str(next_index))

        return next_index

    except Exception as e:
        logger.error(f"Error managing track index: {e}")
        return 0


def send_simulation_trigger():
    """Send a simulation trigger to the running display."""
    track_index = get_next_track_index()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)  # 5 second timeout
        sock.connect(("localhost", SIMULATION_PORT))
        sock.send(str(track_index).encode())

        # Try to receive response but don't hang if it fails
        try:
            _response = sock.recv(1024).decode()  # noqa: F841
        except socket.timeout:
            logger.warning("Timeout waiting for server response, but trigger was sent")

        sock.close()

        track_data = SAMPLE_TRACKS[track_index]
        print(
            f"Sent simulation trigger for track {track_index + 1}: {track_data['title']} by {track_data['artist']}"
        )
        return True

    except Exception as e:
        print(f"Error sending simulation trigger: {e}")
        print("Make sure the display application is running.")
        return False
