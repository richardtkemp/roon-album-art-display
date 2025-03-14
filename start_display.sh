#!/usr/bin/env bash

set -e
DIR="$(dirname "$(readlink -f "$0")")"
for d in "$DIR/logs" "$DIR/libs" ; do
	if [[ ! -d $d ]] ; then
		mkdir -p $d
	fi
done


# TODO fetch epaper repo
cp ../e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib/* libs/

python3 $DIR/display.py | tee -a $DIR/logs/$(date +%Y%m%d%H%M%S).log
