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
- returnFunc() method raises EarlyExit when should_stop=True
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

from ..utils import set_current_image_key
from .base import BaseViewer

logger = logging.getLogger(__name__)


class EinkViewer(BaseViewer):
    """Viewer for E-ink displays (Waveshare)."""

    def __init__(self, config, eink_module):
        """Initialize with e-ink hardware module."""
        super().__init__(config)
        self.eink = eink_module
        self.set_screen_size(self.eink.EPD_WIDTH, self.eink.EPD_HEIGHT)
        self.update_thread = None

        # Initialize e-ink display
        self.epd = eink_module.EPD()
        self.epd.Init()
        self.startup()

    def display_image(self, image_key, img, title):
        """Display an image on the e-ink display."""
        thread_id = threading.current_thread().ident
        logger.debug(f"Starting display update for {title} (thread: {thread_id})")
        logger.debug(f"should_stop flag at start: {self.epd.should_stop}")

        start_time = time.time()

        try:
            # Send to e-ink display - don't reset should_stop flag here!
            self.epd.display(self.epd.getbuffer(img), title)

            elapsed_time = time.time() - start_time

            # CRITICAL: Detect failed renders by timing
            # Successful renders: ~25 seconds, Failed renders: ~6 seconds
            if elapsed_time < timing_config.render_success_threshold:
                logger.error("=" * 80)
                logger.error("🚨 CRITICAL: FAST DISPLAY RENDER DETECTED! 🚨")
                logger.error(f"Display took {elapsed_time:.2f} seconds (expected ~25s)")
                logger.error(f"Thread ID: {thread_id}")
                logger.error(f"should_stop at start: {self.epd.should_stop}")
                logger.error(f"Image: {title} (key: {image_key})")
                logger.error("This indicates a FAILED render, likely due to:")
                logger.error("- Hardware in bad state from improper interruption")
                logger.error("- should_stop mechanism not working correctly")
                logger.error("- Concurrent display() calls (HARDWARE UNSAFE!)")
                logger.error("- Previous render left hardware in invalid state")
                logger.error("Check logs above for thread conflicts or timing issues")
                logger.error("=" * 80)
            else:
                logger.info(
                    f"Finished displaying image for {title} ({elapsed_time:.1f}s, thread: {thread_id})"
                )

            # Update current image key after successful display
            set_current_image_key(image_key)

        except Exception as e:
            elapsed_time = time.time() - start_time
            thread_id = threading.current_thread().ident
            logger.error(
                f"Error displaying image after {elapsed_time:.2f}s (thread: {thread_id}): {e}"
            )

    def update(self, image_key, image_path, img, title):
        """Update the display with new image (thread-safe)."""
        update_start = time.time()
        main_thread_id = threading.current_thread().ident

        logger.info(
            f"UPDATE START: {title} (key: {image_key}, main_thread: {main_thread_id})"
        )

        # Load image if not provided
        if img is None:
            img = self.image_processor.fetch_image(image_path)
        if img is None:
            logger.warning(f"Could not load image for {title}")
            return

        # Stop any current update
        previous_thread_id = None
        if self.update_thread is not None:
            previous_thread_id = self.update_thread.ident
            logger.info(
                f"Setting stop flag for previous update (prev_thread: {previous_thread_id})"
            )
            logger.debug(f"should_stop before setting: {self.epd.should_stop}")
            self.epd.should_stop = True
            logger.debug(f"should_stop after setting: {self.epd.should_stop}")

        # Process image while waiting for thread to stop
        img = self.image_processor.process_image_position(img)

        # Wait for previous thread to finish
        if self.update_thread is not None:
            wait_start = time.time()
            logger.info(
                f"Waiting for previous thread {previous_thread_id} to finish for {title}"
            )

            while self.update_thread.is_alive():
                time.sleep(0.1)
                wait_elapsed = time.time() - wait_start
                if wait_elapsed > 30:  # Log if waiting too long
                    logger.warning(
                        f"Still waiting for thread {previous_thread_id} after {wait_elapsed:.1f}s"
                    )

            wait_elapsed = time.time() - wait_start
            logger.info(
                f"Previous thread {previous_thread_id} finished after {wait_elapsed:.1f}s"
            )

        # Start new update thread
        logger.info(f"Creating new update thread for {title}")
        self.update_thread = threading.Thread(
            target=self.display_image, args=(image_key, img, title)
        )
        self.update_thread.start()

        update_elapsed = time.time() - update_start
        new_thread_id = self.update_thread.ident
        logger.info(
            f"UPDATE COMPLETE: {title} (new_thread: {new_thread_id}, setup_time: {update_elapsed:.2f}s)"
        )
