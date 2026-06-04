#!/usr/bin/env python3
"""
Simple display trigger for a running Roon display application.

By default sends a track change trigger (rotating through 4 sample tracks).
With ``--time`` it instead tells the running app to render the current
date/time — handy for testing the display when no Roon server is available.

Usage:
    python simulate_track_change.py
    python simulate_track_change.py --time

The display application must be running for this to work.
"""

import argparse
import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from roon_display.simulation import (  # noqa: E402
    send_simulation_trigger,
    send_time_trigger,
)


def main():
    """Send a single trigger to the running display and exit."""
    parser = argparse.ArgumentParser(
        description="Trigger a render on a running Roon display application"
    )
    parser.add_argument(
        "--time",
        action="store_true",
        help="Render the current date/time instead of a sample track change",
    )
    args = parser.parse_args()

    if args.time:
        print("Sending time render trigger...")
        if send_time_trigger():
            print("✓ Time render trigger sent successfully")
            return 0
        print("✗ Failed to send time render trigger")
        print("Make sure the Roon display application is running.")
        return 1

    print("Sending simulation track change trigger...")
    if send_simulation_trigger():
        print("✓ Track change trigger sent successfully")
        return 0
    else:
        print("✗ Failed to send track change trigger")
        print("Make sure the Roon display application is running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
