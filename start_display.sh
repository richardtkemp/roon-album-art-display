#!/usr/bin/env bash

DIR="$(dirname "$(readlink -f "$0")")"
mkdir -p $DIR/logs

lib="$DIR/libs/epd13in3E.py"
if [[ ! -f "$lib" ]] ; then
	curl -o "$lib" https://raw.githubusercontent.com/waveshareteam/e-Paper/refs/heads/master/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib/epd13in3E.py
fi
python3 $DIR/display.py | tee -a $DIR/logs/$(date +%Y%m%d%H%M%S).log
