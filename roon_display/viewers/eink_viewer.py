"""E-ink display viewer for Waveshare displays.

CRITICAL E-INK HARDWARE CONSTRAINTS:
===================================

1. SLOW OPERATIONS: display() takes ~25 seconds to complete in real hardware
2. HARDWARE BUSY STATE: Cannot accept new commands while rendering
3. SILENT FAILURES: Sending commands during rendering fails silently - no errors!
4. THREAD SAFETY: Only one display operation can run at a time

THREADING IMPLEMENTATION:
========================

1. When new update() called while previous thread running:
   - partial_refresh=False: wait for previous thread to finish (legacy, safe)
   - partial_refresh=True: signal cancel and spawn new thread immediately;
     new thread blocks at _render_lock until old thread exits after Reset()
3. Thread completion ensures hardware is ready for next operation

CANCELLATION:
============
- cancel_current_render() sets _cancel_render event
- EPD driver checks the event in ReadBusyH polls, SPI loops, and getbuffer()
- On RenderCancelledError: Reset() is called, render is NOT finalised
- New render starts cleanly after acquiring _render_lock

TESTING NOTES:
=============
- Mock display() should include time.sleep() to simulate real hardware timing
- Real hardware testing required to validate cancellation points work correctly
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from ..utils import log_performance, set_current_image_key
from .base import BaseViewer

logger = logging.getLogger(__name__)


class RenderCancelledError(Exception):
    """Raised when a render is cancelled via cancel_current_render()."""

    pass


class EinkViewer(BaseViewer):
    """Viewer for E-ink displays (Waveshare)."""

    def __init__(self, config_manager: Any, eink_module: Any) -> None:
        """Initialize with e-ink hardware module."""
        super().__init__(config_manager)
        self.eink = eink_module
        self.set_screen_size(self.eink.EPD_WIDTH, self.eink.EPD_HEIGHT)
        self.update_thread: Optional[threading.Thread] = None

        self._cancel_render = threading.Event()
        self._render_lock = threading.Lock()

        self.epd = eink_module.EPD()
        self.epd.Init()
        self.startup()

        logger.info("EinkViewer initialized")

    def cancel_current_render(self) -> None:
        """Signal any in-progress render to abort at its next cancellation checkpoint."""
        self._cancel_render.set()

    def cleanup(self) -> None:
        """Put display to sleep and cut power. Call on exit to avoid stuck-busy state."""
        try:
            self.epd.sleep()
        except Exception as e:
            logger.error(f"Error during e-ink cleanup: {e}")

    def display_image(self, image_key: str, img: Any, title: str) -> None:
        """Display an image on the e-ink display."""
        with self._render_lock:
            self._cancel_render.clear()
            self.epd.set_cancel_event(self._cancel_render)

            thread_id = threading.current_thread().ident
            logger.debug(f"Starting display update for {title} (thread: {thread_id})")

            # Re-initialise the display before every render. The display can enter
            # a stuck-busy state after periods of inactivity; Init() resets the
            # hardware (via Reset()) and re-applies register configuration, clearing
            # the BUSY pin reliably. This is the same sequence that standalone mode
            # runs implicitly by constructing a fresh EinkViewer.
            logger.info(f"Re-initialising display before render for {title}")

            start_time = time.time()

            try:
                self.epd.Init()
                self.epd.display(self.epd.getbuffer(img), title)
            except RenderCancelledError:
                logger.info(f"Render cancelled for {title} — calling Reset()")
                self.epd.set_cancel_event(None)
                self.epd.Reset()
                return
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

            elapsed_time = time.time() - start_time

            if elapsed_time < self.config_manager.get_eink_success_threshold():
                logger.error("=" * 80)
                logger.error("🚨 CRITICAL: FAST DISPLAY RENDER DETECTED! 🚨")
                logger.error(f"Display took {elapsed_time:.2f} seconds (expected ~25s)")
                logger.error(f"Thread ID: {thread_id}")
                logger.error(f"Image: {title} (key: {image_key})")
                logger.error("This indicates a FAILED render, likely due to:")
                logger.error("- Hardware not connected or malfunctioning")
                logger.error("- E-ink display driver issues")
                logger.error("- Concurrent display() calls (HARDWARE UNSAFE!)")
                logger.error("=" * 80)

                if self.health_manager:
                    self.health_manager.report_render_failure(
                        f"Fast render detected: {elapsed_time:.2f}s for {title}"
                    )
            else:
                logger.info(
                    f"Finished displaying image for {title} ({elapsed_time:.1f}s, thread: {thread_id})"
                )

                if self.health_manager:
                    self.health_manager.report_render_success(
                        f"Successful render: {elapsed_time:.1f}s for {title}"
                    )

            self._finalize_successful_render(image_key)

    @log_performance(threshold=0.5, description="E-ink display update")
    def update(self, image_key: str, img: Any, title: str) -> None:
        """Update the display with new image (thread-safe)."""
        update_start = time.time()
        main_thread_id = threading.current_thread().ident

        logger.debug(
            f"UPDATE START: {title} (key: {image_key}, main_thread: {main_thread_id})"
        )

        if img is None:
            logger.warning(f"No image provided for display: {title}")
            return

        partial_refresh = self.config_manager.get_partial_refresh()

        previous_thread_id = None
        if self.update_thread is not None and self.update_thread.is_alive():
            previous_thread_id = self.update_thread.ident

        if self.update_thread is not None and self.update_thread.is_alive():
            if partial_refresh:
                logger.info(
                    f"Cancel signalled for thread {previous_thread_id}; "
                    f"starting {title} immediately"
                )
                self._cancel_render.set()
                # Don't wait — new thread will block at _render_lock until old exits
            else:
                wait_start = time.time()
                logger.debug(
                    f"Waiting for previous thread {previous_thread_id} to finish for {title}"
                )

                while self.update_thread.is_alive():
                    time.sleep(0.1)
                    wait_elapsed = time.time() - wait_start
                    if (
                        wait_elapsed > 60
                        and int(wait_elapsed) % 60 == 0
                        and (wait_elapsed - int(wait_elapsed)) < 0.1
                    ):
                        logger.warning(
                            f"Still waiting for thread {previous_thread_id} after {wait_elapsed:.0f}s"
                        )

                wait_elapsed = time.time() - wait_start
                logger.debug(
                    f"Previous thread {previous_thread_id} finished after {wait_elapsed:.1f}s"
                )

        if self.update_thread is not None and not self.update_thread.is_alive():
            self.update_thread = None

        logger.debug(f"Creating new update thread for {title}")
        self.update_thread = threading.Thread(
            target=self.display_image, args=(image_key, img, title)
        )
        self.update_thread.start()

        update_elapsed = time.time() - update_start
        new_thread_id = self.update_thread.ident
        logger.debug(
            f"UPDATE COMPLETE: {title} (new_thread: {new_thread_id}, setup_time: {update_elapsed:.2f}s)"
        )
