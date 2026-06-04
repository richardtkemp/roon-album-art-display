"""Show the current time on the display while Roon is not connected.

When the Roon server is unreachable, or the extension is still awaiting approval
in Roon's settings, the app would otherwise sit on a stale or blank screen
indefinitely. This background thread renders a clock instead, refreshing once a
minute, until a connection is established — at which point album art (or the
normal connected behaviour) takes over.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Optional

from .time_utils import current_time_message

if TYPE_CHECKING:
    from .message_renderer import MessageRenderer

logger = logging.getLogger(__name__)


class ConnectionClock:
    """Renders the time whenever the Roon client is running but not connected."""

    def __init__(
        self,
        roon_client: Any,
        render_coordinator: Any,
        message_renderer: "MessageRenderer",
    ) -> None:
        self.roon_client = roon_client
        self.render_coordinator = render_coordinator
        self.message_renderer = message_renderer
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background clock thread."""
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="connection-clock"
        )
        self._thread.start()
        logger.info("Connection clock started")

    def stop(self) -> None:
        """Signal the clock thread to stop."""
        self._stop.set()

    def _should_show_clock(self) -> bool:
        """True when the app is running but not connected to Roon."""
        return bool(self.roon_client.running) and not bool(
            self.roon_client.is_connected
        )

    def _tick(self) -> bool:
        """Render the current time if disconnected. Returns True if rendered."""
        if not self._should_show_clock():
            return False
        message = current_time_message()
        logger.info(f"Rendering connection clock: {message!r}")
        image = self.message_renderer.create_text_message(message)
        # content_type != "art" so this doesn't disturb anniversary tracking.
        # force=True is required: the time image has no image_key, so the render
        # loop's dedup (target.image_key == displayed_key, i.e. None == None)
        # would otherwise skip it as "already on screen" and never draw.
        self.render_coordinator.set_art(
            content_type="time", img=image, track_info=message, force=True
        )
        return True

    def _loop(self) -> None:
        """Re-render the clock once a minute while disconnected, until stopped."""
        last_minute: Optional[str] = None
        # Poll often so we react quickly to (dis)connection, but only re-render
        # when the displayed minute actually changes (e-ink refreshes are slow).
        while not self._stop.wait(2):
            minute = time.strftime("%Y%m%d%H%M")
            if minute == last_minute:
                continue
            try:
                if self._tick():
                    last_minute = minute
            except Exception as e:
                logger.error(f"Connection clock render failed: {e}")
