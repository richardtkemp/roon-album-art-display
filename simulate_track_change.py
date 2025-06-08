#!/usr/bin/env python3
"""
Simple track change simulator trigger.

This script sends a track change trigger to a running Roon display application
and exits immediately. It rotates through 4 different tracks automatically.

Usage: python simulate_track_change.py

The display application must be running for this to work.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from roon_display.simulation import send_simulation_trigger


def main():
    """Send a single track change trigger and exit."""
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
