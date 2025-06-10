"""E-ink display viewer for Waveshare displays.

CRITICAL E-INK HARDWARE CONSTRAINTS:
===================================

The e-ink display has strict hardware limitations that must be respected:

1. SLOW OPERATIONS: display() takes ~25 seconds to complete in real hardware
2. HARDWARE BUSY STATE: Cannot accept new commands while rendering
3. SILENT FAILURES: Sending commands during rendering fails silently - no errors!
4. THREAD SAFETY: Only one display operation can run at a time

SAFE CANCELLATION DESIGN:
========================

The e-ink library (libs/epd13in3E.py) has been modified to support safe cancellation:
- should_stop flag is checked at multiple safe points during display()
- Hardware is left in a safe state when cancelling

THREADING IMPLEMENTATION:
========================

This viewer uses the following thread safety approach:
1. When new update() called while previous thread running:
   - Set should_stop=True to request early exit of current operation
   - Wait for previous thread to complete safely (respects hardware constraints)
   - Start new thread only after hardware is idle
2. DO NOT reset should_stop flag in display_image() - let the e-ink library handle it
3. Thread completion ensures hardware is ready for next operation

TESTING NOTES:
=============
- Mock display() should include time.sleep() to simulate real hardware timing
- Tests verify that should_stop flag is properly set and handled
- Real hardware testing required to validate cancellation points work correctly
"""

import logging
import threading
import time

from timing_config import timing_config

from ..utils import log_performance, set_current_image_key
from .base import BaseViewer

logger = logging.getLogger(__name__)


class EinkViewer(BaseViewer):
    """Viewer for E-ink displays (Waveshare)."""

    def __init__(self, config_manager, eink_module):
        """Initialize with e-ink hardware module."""
        super().__init__(config_manager)
        self.eink = eink_module
        self.set_screen_size(self.eink.EPD_WIDTH, self.eink.EPD_HEIGHT)
        self.update_thread = None

        # Initialize e-ink display
        self.epd = eink_module.EPD()
        self.epd.Init()
        self.startup()

        logger.info("EinkViewer initialized")

    def display_image(self, image_key, image_path, img, title):
        """Display an image on the e-ink display."""
        thread_id = threading.current_thread().ident
        logger.debug(f"Starting display update for {title} (thread: {thread_id})")
        logger.debug(f"should_stop flag at start: {self.epd.should_stop}")

        start_time = time.time()

        # Send to e-ink display - don't reset should_stop flag here!
        self.epd.display(self.epd.getbuffer(img), title)

        elapsed_time = time.time() - start_time

        # Check for render timing issues
        if elapsed_time < timing_config.render_success_threshold:
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

            # Call health script for render failure
            if self.health_manager:
                additional_info = (
                    f"Fast render detected: {elapsed_time:.2f}s for {title}"
                )
                self.health_manager.report_render_failure(additional_info)
        else:
            logger.info(
                f"Finished displaying image for {title} ({elapsed_time:.1f}s, thread: {thread_id})"
            )

            # Call health script for successful render
            if self.health_manager:
                additional_info = f"Successful render: {elapsed_time:.1f}s for {title}"
                self.health_manager.report_render_success(additional_info)

        # Finalize successful render (update tracking and notify coordinator)
        self._finalize_successful_render(image_key)

    @log_performance(threshold=0.5, description="E-ink display update")
    def update(self, image_key, image_path, img, title):
        """Update the display with new image (thread-safe)."""
        update_start = time.time()
        main_thread_id = threading.current_thread().ident

        logger.debug(
            f"UPDATE START: {title} (key: {image_key}, main_thread: {main_thread_id})"
        )

        # Load and process image using common logic
        img = self._load_and_process_image(img, image_path, title)
        if img is None:
            return

        # Handle previous update - use smart render coordination
        previous_thread_id = None
        if self.update_thread is not None and self.update_thread.is_alive():
            previous_thread_id = self.update_thread.ident

            # Use should_stop mechanism for smart render cancellation
            logger.debug(
                f"Setting stop flag for previous update (prev_thread: {previous_thread_id})"
            )
            logger.debug(f"should_stop before setting: {self.epd.should_stop}")
            self.epd.should_stop = True
            logger.debug(f"should_stop after setting: {self.epd.should_stop}")

        # Image is already processed by _load_and_process_image()

        # Wait for previous thread to finish
        if self.update_thread is not None and self.update_thread.is_alive():
            wait_start = time.time()
            logger.debug(
                f"Waiting for previous thread {previous_thread_id} to finish for {title}"
            )

            while self.update_thread.is_alive():
                time.sleep(0.1)
                wait_elapsed = time.time() - wait_start
                # Log warning every 5 seconds after 30 seconds
                if (
                    wait_elapsed > 30
                    and int(wait_elapsed) % 5 == 0
                    and (wait_elapsed - int(wait_elapsed)) < 0.1
                ):
                    logger.warning(
                        f"Still waiting for thread {previous_thread_id} after {wait_elapsed:.1f}s"
                    )

            wait_elapsed = time.time() - wait_start
            logger.debug(
                f"Previous thread {previous_thread_id} finished after {wait_elapsed:.1f}s"
            )

        # Clear finished thread reference
        if self.update_thread is not None and not self.update_thread.is_alive():
            self.update_thread = None

        # Start new update thread
        logger.debug(f"Creating new update thread for {title}")
        self.update_thread = threading.Thread(
            target=self.display_image, args=(image_key, image_path, img, title)
        )
        self.update_thread.start()

        update_elapsed = time.time() - update_start
        new_thread_id = self.update_thread.ident
        logger.debug(
            f"UPDATE COMPLETE: {title} (new_thread: {new_thread_id}, setup_time: {update_elapsed:.2f}s)"
        )
