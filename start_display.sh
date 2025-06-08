#!/usr/bin/env bash

set -e
DIR="$(dirname "$(readlink -f "$0")")"

# Set production threshold for e-ink render failure detection
export EINK_SUCCESS_THRESHOLD=12.0

# Ensure logs directory exists
mkdir -p "$DIR/logs"

# Use virtual environment if available, otherwise system python
if [ -f "$DIR/bin/python" ]; then
    PYTHON="$DIR/bin/python"
else
    PYTHON="python3"
fi

# Run the new modular application
$PYTHON -m roon_display.main | tee -a "$DIR/logs/$(date +%Y%m%d%H%M%S).log"
