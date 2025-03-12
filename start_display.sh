#!/usr/bin/env bash

DIR="$(dirname "$(readlink -f "$0")")"
mkdir -p "$DIR/logs" "$DIR/libs"

for l in __init__.py epd13in3E.py epdconfig.py ; do
	libfile="$DIR/libs/$l"
        if [[ ! -f "$libfile" ]] ; then
		curl -o "$libfile" "https://raw.githubusercontent.com/waveshareteam/e-Paper/refs/heads/master/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib/$l"
	fi
done

python3 $DIR/display.py | tee -a $DIR/logs/$(date +%Y%m%d%H%M%S).log
