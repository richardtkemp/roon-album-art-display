"""Tests for Roon client functionality."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from roon_display.roon_client.client import RoonClient


class TestRoonClient:
    """Test RoonClient class."""

    @pytest.fixture
    def mock_viewer(self):
        """Create mock viewer for testing."""
        viewer = Mock()
        viewer.image_processor = Mock()
        viewer.image_processor.image_size = 800
        viewer.update = Mock()
        return viewer

    @pytest.fixture
    def roon_client(self, config_manager, mock_viewer, temp_dir):
        """Create RoonClient instance for testing."""
        with patch("roon_display.roon_client.client.get_saved_image_dir") as mock_image_dir:
            mock_image_dir.return_value = temp_dir
            client = RoonClient(
                config_manager, mock_viewer, mock_viewer.image_processor
            )
            client.roon = None  # Prevent actual Roon connection attempts
            return client

    def test_initialization(self, config_manager, mock_viewer, temp_dir):
        """Test RoonClient initialization."""
        with patch("roon_display.roon_client.client.get_saved_image_dir") as mock_image_dir:
            mock_image_dir.return_value = temp_dir

            client = RoonClient(
                config_manager, mock_viewer, mock_viewer.image_processor
            )

            assert client.config_manager == config_manager
            assert client.viewer == mock_viewer
            assert client.image_processor == mock_viewer.image_processor
            assert client.allowed_zones == ["Living Room", "Kitchen"]
            assert client.forbidden_zones == ["Bedroom"]
            assert client.token_file == Path(".roon_album_display_token.txt")
            assert client.running is False

    @patch("roon_display.roon_client.client.RoonApi")
    def test_try_saved_connection_success(self, mock_roon_api, roon_client):
        """Test successful connection using saved server details."""
        # Setup mocks
        mock_api = Mock()
        mock_api.host = "192.168.1.100"
        mock_api.zones = {"zone1": {"name": "test"}}
        mock_roon_api.return_value = mock_api

        with patch.object(roon_client, "_get_token", return_value="test_token"):
            result = roon_client._try_saved_connection()

            assert result == mock_api
            mock_roon_api.assert_called_once_with(
                roon_client.app_info, "test_token", "192.168.1.100", 9330
            )

    def test_try_saved_connection_no_config(self, roon_client):
        """Test saved connection when no server config exists."""
        roon_client.config_manager.get_server_config = Mock(return_value=(None, None))

        result = roon_client._try_saved_connection()

        assert result is None

    @patch("roon_display.roon_client.client.RoonApi")
    def test_try_saved_connection_failure(self, mock_roon_api, roon_client):
        """Test saved connection failure."""
        mock_roon_api.side_effect = Exception("Connection failed")

        with patch.object(roon_client, "_get_token", return_value="test_token"):
            result = roon_client._try_saved_connection()

            assert result is None

    @patch("roon_display.roon_client.client.RoonDiscovery")
    @patch("roon_display.roon_client.client.RoonApi")
    def test_discover_and_connect_success(
        self, mock_roon_api, mock_discovery, roon_client
    ):
        """Test successful server discovery and connection."""
        # Setup discovery mock
        mock_discover = Mock()
        mock_discover.all.return_value = [("192.168.1.50", 9330)]
        mock_discover.stop = Mock()
        mock_discovery.return_value = mock_discover

        # Setup API mock
        mock_api = Mock()
        mock_api.token = "existing_token"
        mock_roon_api.return_value = mock_api

        with patch.object(roon_client, "_get_token", return_value="existing_token"), patch.object(
            roon_client.config_manager, "save_server_config"
        ) as mock_save:
            result = roon_client._discover_and_connect()

            assert result == mock_api
            mock_discover.stop.assert_called_once()
            mock_save.assert_called_once()

    @patch("roon_display.roon_client.client.RoonDiscovery")
    @patch("roon_display.roon_client.client.RoonApi")
    def test_discover_and_connect_authorization_flow(
        self, mock_roon_api, mock_discovery, roon_client
    ):
        """Test discovery with authorization flow."""
        # Setup discovery
        mock_discover = Mock()
        mock_discover.all.return_value = [("192.168.1.50", 9330)]
        mock_discover.stop = Mock()
        mock_discovery.return_value = mock_discover

        # Setup API mock for authorization flow
        mock_api = Mock()
        mock_api.token = None  # Initially no token
        mock_roon_api.return_value = mock_api

        mock_token_file = Mock()
        with patch.object(roon_client, "_get_token", return_value=None), patch(
            "time.sleep"
        ), patch.object(roon_client, "token_file", mock_token_file), patch.object(
            roon_client.config_manager, "save_server_config"
        ):
            # Simulate authorization success after one iteration
            def side_effect():
                mock_api.token = "new_token"

            # Mock the authorization loop
            _original_token = mock_api.token  # noqa: F841
            mock_api.token = "new_token"  # Simulate successful authorization

            result = roon_client._discover_and_connect()

            assert result == mock_api

    def test_get_token_exists(self, roon_client):
        """Test getting existing token."""
        mock_token_file = Mock()
        mock_token_file.exists.return_value = True
        mock_token_file.read_text.return_value = "  stored_token  "
        
        with patch.object(roon_client, 'token_file', mock_token_file):
            token = roon_client._get_token()

            assert token == "stored_token"

    def test_get_token_not_exists(self, roon_client):
        """Test getting token when file doesn't exist."""
        mock_token_file = Mock()
        mock_token_file.exists.return_value = False
        
        with patch.object(roon_client, 'token_file', mock_token_file):
            token = roon_client._get_token()

            assert token is None

    def test_validate_connection_success(self, roon_client, mock_roon_api):
        """Test successful connection validation."""
        mock_roon_api._roonsocket = Mock()
        mock_roon_api._roonsocket.failed_state = False
        roon_client.roon = mock_roon_api

        # Should not raise exception
        roon_client._validate_connection()

    def test_validate_connection_no_socket(self, roon_client):
        """Test validation failure when no socket."""
        roon_client.roon = Mock()
        delattr(roon_client.roon, "_roonsocket")

        with pytest.raises(ConnectionError, match="no socket"):
            roon_client._validate_connection()

    def test_validate_connection_failed_state(self, roon_client, mock_roon_api):
        """Test validation failure when connection in failed state."""
        mock_roon_api._roonsocket = Mock()
        mock_roon_api._roonsocket.failed_state = True
        roon_client.roon = mock_roon_api

        with pytest.raises(ConnectionError, match="failed state"):
            roon_client._validate_connection()

    def test_process_zone_data_forbidden_zone(self, roon_client):
        """Test processing zone data for forbidden zone."""
        zone_data = {"display_name": "Bedroom", "now_playing": {"image_key": "test"}}

        result = roon_client._process_zone_data("zone1", zone_data)

        assert result is False

    def test_process_zone_data_not_allowed_zone(self, roon_client):
        """Test processing zone data for non-allowed zone."""
        zone_data = {"display_name": "Office", "now_playing": {"image_key": "test"}}

        result = roon_client._process_zone_data("zone1", zone_data)

        assert result is False

    def test_process_zone_data_allowed_zone(self, roon_client):
        """Test processing zone data for allowed zone."""
        zone_data = {
            "display_name": "Living Room",
            "now_playing": {
                "image_key": "test_key_123",
                "three_line": {
                    "line1": "Test Song",
                    "line2": "Test Artist",
                    "line3": "Test Album",
                },
            },
        }

        with patch.object(
            roon_client, "_process_now_playing", return_value="test_key_123"
        ) as mock_process:
            result = roon_client._process_zone_data("zone1", zone_data)

            assert result == "test_key_123"
            mock_process.assert_called_once_with(zone_data["now_playing"])

    def test_extract_now_playing_direct(self, roon_client):
        """Test extracting now_playing data from direct structure."""
        zone_data = {"now_playing": {"image_key": "test_key"}}

        result = roon_client._extract_now_playing(zone_data)

        assert result == {"image_key": "test_key"}

    def test_extract_now_playing_nested_state(self, roon_client):
        """Test extracting now_playing from nested state structure."""
        zone_data = {"state": {"now_playing": {"image_key": "test_key"}}}

        result = roon_client._extract_now_playing(zone_data)

        assert result == {"image_key": "test_key"}

    def test_extract_now_playing_queue(self, roon_client):
        """Test extracting now_playing from queue structure."""
        zone_data = {"queue": {"now_playing": {"image_key": "test_key"}}}

        result = roon_client._extract_now_playing(zone_data)

        assert result == {"image_key": "test_key"}

    def test_extract_now_playing_not_found(self, roon_client):
        """Test extracting now_playing when not found."""
        zone_data = {"other_data": "value"}

        result = roon_client._extract_now_playing(zone_data)

        assert result is None

    def test_process_now_playing_duplicate_event(self, roon_client):
        """Test processing duplicate now_playing event."""
        now_playing = {"image_key": "test_key"}
        roon_client.last_event = now_playing

        result = roon_client._process_now_playing(now_playing)

        assert result is False

    def test_process_now_playing_no_image_key(self, roon_client):
        """Test processing now_playing without image key."""
        now_playing = {"other_data": "value"}

        result = roon_client._process_now_playing(now_playing)

        assert result is False

    def test_process_now_playing_same_image(self, roon_client):
        """Test processing now_playing with same image key."""
        now_playing = {"image_key": "test_key"}
        roon_client.last_image_key = "test_key"

        result = roon_client._process_now_playing(now_playing)

        assert result is False

    def test_process_now_playing_new_track(self, roon_client):
        """Test processing now_playing with new track."""
        now_playing = {
            "image_key": "new_key_123",
            "three_line": {
                "line1": "New Song",
                "line2": "New Artist",
                "line3": "New Album",
            },
        }

        with patch.object(roon_client, "_fetch_and_display_album_art") as mock_fetch:
            result = roon_client._process_now_playing(now_playing)

            assert result == "new_key_123"
            assert roon_client.last_image_key == "new_key_123"
            mock_fetch.assert_called_once_with(
                "new_key_123", "New Song - New Artist - New Album"
            )

    def test_extract_track_info_three_line(self, roon_client):
        """Test extracting track info from three_line structure."""
        now_playing = {
            "three_line": {
                "line1": "Song Title",
                "line2": "Artist Name",
                "line3": "Album Name",
            }
        }

        result = roon_client._extract_track_info(now_playing)

        assert result == "Song Title - Artist Name - Album Name"

    def test_extract_track_info_two_line(self, roon_client):
        """Test extracting track info from two_line structure."""
        now_playing = {"two_line": {"line1": "Song Title", "line2": "Artist Name"}}

        result = roon_client._extract_track_info(now_playing)

        assert result == "Song Title - Artist Name"

    def test_extract_track_info_one_line(self, roon_client):
        """Test extracting track info from one_line structure."""
        now_playing = {"one_line": {"line1": "Song Title"}}

        result = roon_client._extract_track_info(now_playing)

        assert result == "Song Title"

    def test_extract_track_info_unknown(self, roon_client):
        """Test extracting track info when no recognizable structure."""
        now_playing = {"other_data": "value"}

        result = roon_client._extract_track_info(now_playing)

        assert result == "Unknown Track"

    @patch("roon_display.roon_client.client.requests.get")
    @patch("roon_display.roon_client.client.Image.open")
    def test_download_album_art_success(
        self, mock_image_open, mock_requests, roon_client, temp_dir, sample_image
    ):
        """Test successful album art download."""
        # Setup mocks
        mock_response = Mock()
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status = Mock()
        mock_requests.return_value = mock_response
        mock_image_open.return_value = sample_image

        roon_client.roon = Mock()
        roon_client.roon.get_image.return_value = "http://test.com/image.jpg"
        roon_client.image_processor.needs_enhancement.return_value = False

        image_path = temp_dir / "test_album_art.jpg"

        result = roon_client._download_album_art("test_key", image_path)

        assert result == sample_image
        assert image_path.exists()
        mock_requests.assert_called_once_with("http://test.com/image.jpg", stream=True)

    @patch("roon_display.roon_client.client.requests.get")
    def test_download_album_art_request_error(
        self, mock_requests, roon_client, temp_dir
    ):
        """Test album art download with request error."""
        mock_requests.side_effect = Exception("Network error")

        roon_client.roon = Mock()
        roon_client.roon.get_image.return_value = "http://test.com/image.jpg"

        image_path = temp_dir / "test_album_art.jpg"

        result = roon_client._download_album_art("test_key", image_path)

        assert result is None

    def test_fetch_and_display_album_art_existing_file(
        self, roon_client, temp_dir, sample_image
    ):
        """Test fetch and display when image file already exists."""
        image_path = temp_dir / "album_art_existing_key.jpg"
        sample_image.save(image_path)

        with patch("roon_display.roon_client.client.get_saved_image_dir", return_value=temp_dir):
            roon_client._fetch_and_display_album_art("existing_key", "Test Track")

            roon_client.viewer.update.assert_called_once_with(
                "existing_key", image_path, None, "Test Track"
            )

    def test_fetch_and_display_album_art_new_download(
        self, roon_client, temp_dir, sample_image
    ):
        """Test fetch and display with new image download."""
        image_path = temp_dir / "album_art_new_key.jpg"

        with patch("roon_display.roon_client.client.get_saved_image_dir", return_value=temp_dir), patch.object(
            roon_client, "_download_album_art", return_value=sample_image
        ):
            roon_client._fetch_and_display_album_art("new_key", "New Track")

            roon_client.viewer.update.assert_called_once_with(
                "new_key", image_path, sample_image, "New Track"
            )

    def test_fetch_and_display_album_art_download_failure(self, roon_client, temp_dir):
        """Test fetch and display when download fails."""
        with patch.object(roon_client, "_download_album_art", return_value=None):
            roon_client._fetch_and_display_album_art("failed_key", "Failed Track")

            # Should not call viewer.update when download fails
            roon_client.viewer.update.assert_not_called()

    def test_zone_event_callback_list_data(self, roon_client):
        """Test zone event callback with list data."""
        roon_client.roon = Mock()
        roon_client.roon.zones = {
            "zone1": {
                "display_name": "Living Room",
                "now_playing": {"image_key": "test"},
            }
        }

        with patch.object(roon_client, "_process_zone_data") as mock_process:
            roon_client._zone_event_callback("zones_changed", ["zone1"])

            mock_process.assert_called_once_with(
                "zone1", roon_client.roon.zones["zone1"]
            )

    def test_zone_event_callback_invalid_data(self, roon_client):
        """Test zone event callback with invalid data format."""
        # Should handle gracefully without crashing
        roon_client._zone_event_callback("zones_changed", "invalid_data")

    def test_subscribe_to_events(self, roon_client):
        """Test subscribing to Roon events."""
        roon_client.roon = Mock()

        roon_client.subscribe_to_events()

        roon_client.roon.register_state_callback.assert_called_once_with(
            roon_client._zone_event_callback, "zones_changed"
        )

    def test_subscribe_to_events_error(self, roon_client):
        """Test error handling in subscribe_to_events."""
        roon_client.roon = Mock()
        roon_client.roon.register_state_callback.side_effect = Exception(
            "Subscription failed"
        )

        # Should handle error gracefully
        roon_client.subscribe_to_events()

    def test_run_starts_event_loop(self, roon_client):
        """Test that run starts event loop thread."""
        with patch.object(roon_client, "subscribe_to_events"), patch(
            "threading.Thread"
        ) as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance

            result = roon_client.run()

            assert roon_client.running is True
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()
            assert result == mock_thread_instance

    def test_stop(self, roon_client):
        """Test stopping the client."""
        roon_client.running = True

        roon_client.stop()

        assert roon_client.running is False

    def test_cleanup(self, roon_client):
        """Test cleanup of resources."""
        roon_client.roon = Mock()

        roon_client.cleanup()

        roon_client.roon.stop.assert_called_once()

    def test_cleanup_no_roon(self, roon_client):
        """Test cleanup when no roon connection."""
        roon_client.roon = None

        # Should not raise exception
        roon_client.cleanup()

    def test_event_loop_runs_until_stopped(self, roon_client):
        """Test that event loop runs until stopped."""
        roon_client.running = True

        with patch("time.sleep") as mock_sleep, patch.object(
            roon_client, "cleanup"
        ) as mock_cleanup:
            # Stop after a few iterations
            call_count = 0

            def sleep_side_effect(*args):
                nonlocal call_count
                call_count += 1
                if call_count >= 3:
                    roon_client.running = False

            mock_sleep.side_effect = sleep_side_effect

            roon_client._event_loop()

            # Should have called sleep multiple times and cleanup once
            assert mock_sleep.call_count >= 3
            mock_cleanup.assert_called_once()

    def test_event_loop_error_handling(self, roon_client):
        """Test event loop error handling."""
        roon_client.running = True

        with patch(
            "time.sleep", side_effect=Exception("Event loop error")
        ), patch.object(roon_client, "cleanup") as mock_cleanup:
            roon_client._event_loop()

            # Should still call cleanup even after error
            mock_cleanup.assert_called_once()
