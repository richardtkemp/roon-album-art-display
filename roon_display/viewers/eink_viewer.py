"""E-ink display viewer for Waveshare displays.

CRITICAL E-INK HARDWARE CONSTRAINTS:
===================================

1. SLOW OPERATIONS: display() takes ~25 seconds to complete on real hardware.
2. HARDWARE BUSY STATE: Cannot accept new commands while rendering.
3. SILENT FAILURES: Sending commands during rendering fails silently — no errors!
4. SOLE CALLER: The coordinator's render worker is the only caller of render().
   No _render_lock is needed because the render loop is single-threaded.

CANCELLATION:
============
- cancel() sets _cancel_render event.
- EPD driver checks the event in ReadBusyH polls, SPI loops, and getbuffer().
- On RenderCancelledError: Reset() is called, render is NOT finalised.
- The exception is re-raised so the render loop can loop and pick up the next item.
- The next render() call clears _cancel_render before touching hardware.

TESTING NOTES:
=============
- Mock display() should include time.sleep() to simulate real hardware timing.
- Real hardware testing required to validate cancellation points work correctly.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ..exceptions import RenderCancelledError
from .base import BaseViewer

# Re-export so existing imports (e.g. from tests) keep working.
__all__ = ["EinkViewer", "RenderCancelledError"]

logger = logging.getLogger(__name__)


class EinkViewer(BaseViewer):
    """Viewer for E-ink displays (Waveshare)."""

    def __init__(self, config_manager: Any, eink_module: Any) -> None:
        """Initialize with e-ink hardware module."""
        super().__init__(config_manager)
        self.eink = eink_module
        self.set_screen_size(self.eink.EPD_WIDTH, self.eink.EPD_HEIGHT)

        import threading

        self._cancel_render = threading.Event()
        self._last_render_event_time: Optional[float] = None

        self.epd = eink_module.EPD()
        self.epd.Init()
        self.startup()

        logger.info("EinkViewer initialized")

    def cancel(self) -> None:
        """Signal any in-progress render to abort at its next cancellation checkpoint."""
        self._cancel_render.set()

    def render(
        self, image: Any, image_key: Optional[str], title: Optional[str]
    ) -> None:
        """Blocking render. Raises RenderCancelledError if cancelled.

        The coordinator's render worker is the sole caller; no lock is needed.
        """
        self._cancel_render.clear()
        self.epd.set_cancel_event(self._cancel_render)

        logger.info(f"Re-initialising display before render for {title}")
        start_time = time.time()

        try:
            self.epd.Init()
            self.epd.display(self.epd.getbuffer(image), title)
        except RenderCancelledError:
            elapsed = time.time() - start_time
            cancel_time = time.time()
            since_last = (
                f", {cancel_time - self._last_render_event_time:.1f}s since last render"
                if self._last_render_event_time is not None
                else ""
            )
            logger.info(
                f"Render cancelled for {title} after {elapsed:.1f}s{since_last} — calling Reset()"
            )
            self._last_render_event_time = cancel_time
            self.epd.set_cancel_event(None)
            self.epd.powered_on = False  # Force writePower(True) before next writeDRF
            self.epd.Reset()
            raise  # Re-raise so the render loop can loop
        except TimeoutError as e:
            logger.error(f"E-ink BUSY pin timeout for {title}: {e}")
            if self.health_manager:
                self.health_manager.report_render_failure(str(e))
            return
        except Exception as e:
            logger.error(f"Error during e-ink display: {e}")
            return
        finally:
            self.epd.set_cancel_event(None)

        elapsed = time.time() - start_time

        if elapsed < self.config_manager.get_display_timing_eink_success_threshold():
            logger.error("=" * 80)
            logger.error("🚨 CRITICAL: FAST DISPLAY RENDER DETECTED! 🚨")
            logger.error(f"Display took {elapsed:.2f} seconds (expected ~25s)")
            logger.error(f"Image: {title} (key: {image_key})")
            logger.error("This indicates a FAILED render, likely due to:")
            logger.error("- Hardware not connected or malfunctioning")
            logger.error("- E-ink display driver issues")
            logger.error("=" * 80)
            if self.health_manager:
                self.health_manager.report_render_failure(
                    f"Fast render detected: {elapsed:.2f}s for {title}"
                )
        else:
            success_time = time.time()
            since_last = (
                f", {success_time - self._last_render_event_time:.1f}s since last render"
                if self._last_render_event_time is not None
                else ""
            )
            logger.info(
                f"Finished displaying image for {title} ({elapsed:.1f}s{since_last})"
            )
            self._last_render_event_time = success_time
            if self.health_manager:
                self.health_manager.report_render_success(
                    f"Successful render: {elapsed:.1f}s for {title}"
                )

        self._finalize_successful_render(image_key)

    def cleanup(self) -> None:
        """Put display to sleep and cut power. Call on exit to avoid stuck-busy state."""
        try:
            self.epd.sleep()
        except Exception as e:
            logger.error(f"Error during e-ink cleanup: {e}")
