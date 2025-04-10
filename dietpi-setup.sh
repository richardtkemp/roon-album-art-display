#!/bin/bash

##dietpi install 
#69 rpi.gpio
#70 wiringpi
#17 git
#58 tailscale
#130 pythgon3

apt install neovim python3-pil python3-requests python3-numpy
pip install roonapi

#wpa_passphrase ssid pass >> /etc/wpa_supplicant/wpa_supplicant.conf
#dropbearkey -t rsa -f ~/.ssh/id_dropbear
DATA=/mnt/dietpi_userdata
FRAME=$DATA/roon-album-art-display
mkdir -p $DATA

cd $DATA
#GIT_SSH="dbclient" GIT_SSH_COMMAND="dbclient -i ~/.ssh/id_dropbear" git clone git@github.com:richardtkemp/roon-album-art-display.git
GIT_SSH=dbclient git clone https://github.com/richardtkemp/roon-album-art-display.git

cp $FRAME/space-cleaner.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable space-cleaner.timer
systemctl start  space-cleaner.timer


## TODO
# display err when not connected, not auth'd
# tailscale login
# change hostname#
