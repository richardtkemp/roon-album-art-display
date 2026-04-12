"""Tests for simulation module."""

from unittest.mock import MagicMock, patch

import pytest

from roon_display.simulation import (
    SAMPLE_TRACKS,
    SimulationServer,
    get_next_track_index,
)


@pytest.fixture
def sim_server(config_manager):
    """Create a SimulationServer with mocked roon_client."""
    mock_client = MagicMock()
    return SimulationServer(mock_client, config_manager)


class TestSimulationServer:
    """Tests for SimulationServer."""

    def test_init(self, sim_server):
        """Server initializes with correct state."""
        assert sim_server.server is None
        assert sim_server.running is False

    def test_simulate_track_change(self, sim_server):
        """Simulating a track calls _process_zone_data on the client."""
        sim_server._simulate_track_change(0)
        sim_server.roon_client._process_zone_data.assert_called_once()

        # Verify the zone data contains expected track info
        call_args = sim_server.roon_client._process_zone_data.call_args
        zone_data = call_args[0][1]
        assert zone_data["now_playing"]["image_key"] == SAMPLE_TRACKS[0]["image_key"]

    def test_simulate_wraps_index(self, sim_server):
        """Track index wraps around SAMPLE_TRACKS length."""
        sim_server._simulate_track_change(len(SAMPLE_TRACKS) + 1)
        call_args = sim_server.roon_client._process_zone_data.call_args
        zone_data = call_args[0][1]
        expected_track = SAMPLE_TRACKS[1 % len(SAMPLE_TRACKS)]
        assert zone_data["now_playing"]["image_key"] == expected_track["image_key"]

    def test_start_and_stop(self, sim_server, config_manager):
        """Server can start and stop cleanly."""
        config_manager.get_simulation_server_port = MagicMock(
            return_value=0
        )  # OS-assigned port
        sim_server.start()
        assert sim_server.running is True
        assert sim_server.server is not None
        sim_server.stop()
        assert sim_server.running is False

    def test_stop(self, sim_server):
        """Stop sets running to False."""
        sim_server.running = True
        sim_server.stop()
        assert sim_server.running is False


class TestGetNextTrackIndex:
    """Tests for track index management."""

    def test_returns_valid_index(self, tmp_path):
        """Returns an index within SAMPLE_TRACKS range."""
        with patch("roon_display.simulation.TRACK_INDEX_FILE", tmp_path / "idx.txt"):
            idx = get_next_track_index()
            assert 0 <= idx < len(SAMPLE_TRACKS)

    def test_increments(self, tmp_path):
        """Each call increments the index."""
        idx_file = tmp_path / "idx.txt"
        with patch("roon_display.simulation.TRACK_INDEX_FILE", idx_file):
            first = get_next_track_index()
            second = get_next_track_index()
            assert second == (first + 1) % len(SAMPLE_TRACKS)
