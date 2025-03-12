#!/usr/bin/env bash

DIR="$(dirname "$(readlink -f "$0")")"
mkdir -p $DIR/logs

python3 $DIR/display.py | tee -a $DIR/logs/$(date +%Y%m%d%H%M%S).log
