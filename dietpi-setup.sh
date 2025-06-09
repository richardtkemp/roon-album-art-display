#!/bin/bash

##dietpi install 
#69 rpi.gpio
#70 wiringpi
#17 git
#58 tailscale
#130 python3

apt install neovim python3-pil python3-requests python3-numpy libavif-dev
pip install roonapi

#wpa_passphrase ssid pass >> /etc/wpa_supplicant/wpa_supplicant.conf
#dropbearkey -t rsa -f ~/.ssh/id_dropbear
DATA=/mnt/dietpi_userdata
FRAME=$DATA/roon-album-art-display
mkdir -p $FRAME/logs

cd $DATA
#GIT_SSH="dbclient" GIT_SSH_COMMAND="dbclient -i ~/.ssh/id_dropbear" git clone git@github.com:richardtkemp/roon-album-art-display.git
GIT_SSH=dbclient git clone git@github.com:richardtkemp/roon-album-art-display.git
#GIT_SSH=dbclient git clone https://github.com/richardtkemp/roon-album-art-display.git

cp $FRAME/space-cleaner.{service,timer}  /etc/systemd/system/
cp $FRAME/roon-album-art-display.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable space-cleaner.timer
systemctl enable roon-album-art-display.service
systemctl start  space-cleaner.timer
systemctl start  roon-album-art-display.service

echo 'export GIT_SSH=dbclient' >> /root/.bashrc
## TODO
# display err when not connected, not auth'd
# tailscale login
# change hostname#

# wifi goes to /var/lib/dietpi/dietpi-wifi.db
# Seems that is used as source for /etc/wpa_supplicant/wpa_supplicant.conf when dietpi-config saves network settings


# Probably want to restart after..?
