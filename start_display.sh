#!/usr/bin/env bash

DIR="$(dirname "$(readlink -f "$0")")"
mkdir -p "$DIR/logs" "$DIR/libs"

# TODO fetch epaper repo
mkdir libs
cp ../e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib/* libs/

python3 $DIR/display.py | tee -a $DIR/logs/$(date +%Y%m%d%H%M%S).log
