"""Timing configuration for e-ink display operations.

This module provides configurable timing parameters that can be adjusted
for testing vs production use.

USAGE:
======

Production (default values):
- EINK_SUCCESS_THRESHOLD=12.0   (renders < 12s = failed)
- EINK_MOCK_SUCCESS_DELAY=25.0  (mock successful render time)
- EINK_MOCK_FAILURE_DELAY=6.0   (mock failed render time)

Testing (set via environment or conftest.py):
- EINK_SUCCESS_THRESHOLD=0.5    (fast threshold for tests)
- EINK_MOCK_SUCCESS_DELAY=0.6   (fast successful render)
- EINK_MOCK_FAILURE_DELAY=0.1   (fast failed render)

RATIONALE:
==========
Real e-ink hardware:
- Successful renders: ~25 seconds
- Failed renders: ~6 seconds (hardware left in bad state)

The <12 second threshold detects hardware problems and logs LOUD errors
to help diagnose issues with the should_stop cancellation mechanism.
"""
import os


class TimingConfig:
    """Configuration for e-ink display timing parameters."""

    def __init__(self):
        # Default production values
        self._render_success_threshold = 12.0  # seconds
        self._mock_success_delay = 25.0  # seconds (real hardware timing)
        self._mock_failure_delay = 6.0  # seconds (failed render timing)

        # Override with environment variables if set
        self._load_from_environment()

    def _load_from_environment(self):
        """Load timing values from environment variables."""
        if "EINK_SUCCESS_THRESHOLD" in os.environ:
            self._render_success_threshold = float(os.environ["EINK_SUCCESS_THRESHOLD"])

        if "EINK_MOCK_SUCCESS_DELAY" in os.environ:
            self._mock_success_delay = float(os.environ["EINK_MOCK_SUCCESS_DELAY"])

        if "EINK_MOCK_FAILURE_DELAY" in os.environ:
            self._mock_failure_delay = float(os.environ["EINK_MOCK_FAILURE_DELAY"])

    @property
    def render_success_threshold(self):
        """Minimum seconds for a successful render (below this = failure)."""
        return self._render_success_threshold

    @property
    def mock_success_delay(self):
        """Mock delay for successful e-ink render."""
        return self._mock_success_delay

    @property
    def mock_failure_delay(self):
        """Mock delay for failed e-ink render."""
        return self._mock_failure_delay


# Global instance
timing_config = TimingConfig()
