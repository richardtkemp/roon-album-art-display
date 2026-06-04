"""Tests for the connection clock (shows the time while Roon is disconnected)."""

from unittest.mock import MagicMock

from roon_display.connection_clock import ConnectionClock


def _make_clock(running=True, connected=False):
    roon_client = MagicMock()
    roon_client.running = running
    roon_client.is_connected = connected
    coordinator = MagicMock()
    renderer = MagicMock()
    return ConnectionClock(roon_client, coordinator, renderer), coordinator, renderer


class TestConnectionClock:
    """Tests for ConnectionClock decision logic."""

    def test_renders_time_when_disconnected(self):
        """Running but not connected -> renders the time as 'time' content."""
        clock, coordinator, renderer = _make_clock(running=True, connected=False)
        assert clock._should_show_clock() is True
        assert clock._tick() is True
        renderer.create_text_message.assert_called_once()
        coordinator.set_art.assert_called_once()
        assert coordinator.set_art.call_args.kwargs["content_type"] == "time"

    def test_silent_when_connected(self):
        """Connected -> no clock render."""
        clock, coordinator, _ = _make_clock(running=True, connected=True)
        assert clock._should_show_clock() is False
        assert clock._tick() is False
        coordinator.set_art.assert_not_called()

    def test_silent_when_not_running(self):
        """Not running -> no clock render."""
        clock, coordinator, _ = _make_clock(running=False, connected=False)
        assert clock._should_show_clock() is False
        assert clock._tick() is False
        coordinator.set_art.assert_not_called()
