#!/usr/bin/env bash

set -e
DIR="$(dirname "$(readlink -f "$0")")"

python3 $DIR/display.py | tee -a $DIR/logs/$(date +%Y%m%d%H%M%S).log
