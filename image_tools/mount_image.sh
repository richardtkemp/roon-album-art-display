#!/bin/bash

img="$1"

parts="$(hdiutil attach -nomount $img | tail -n2 | awk '{print $1}')"
boot=$(echo "$parts" | head -1)
root=$(echo "$parts" | tail -1)

# Mount the partitions
sudo mkdir -p /tmp/dietpi_boot #/tmp/dietpi_root
sudo mount -t msdos $boot /tmp/dietpi_boot
#sudo mount -t ext4  $root /tmp/dietpi_root
