#!/bin/bash

##dietpi install 
#69 rpi.gpio
#70 wiringpi
#17 git
#58 tailscale
#130 python3

apt install neovim python3-pil python3-requests python3-numpy python3-psutil libavif-dev
pip install roonapi flask

#wpa_passphrase ssid pass >> /etc/wpa_supplicant/wpa_supplicant.conf
#dropbearkey -t rsa -f ~/.ssh/id_dropbear
DATA=/mnt/dietpi_userdata
PROJECT=roon-album-art-display
FRAME=$DATA/$PROJECT
mkdir -p $FRAME/logs

if [[ ! -d "$FRAME" ]] ; then
	cd $DATA
	GIT_SSH=dbclient git clone git@github.com:richardtkemp/roon-album-art-display.git
	cd $PROJECT
else
	cd $FRAME
	git pull
fi

cp $FRAME/space-cleaner.{service,timer}  /etc/systemd/system/
cp $FRAME/roon-album-art-display.service /etc/systemd/system/
cp $FRAME/roon-web-config.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable space-cleaner.timer
systemctl enable roon-album-art-display.service
systemctl enable roon-web-config.service
systemctl start  space-cleaner.timer
systemctl start  roon-album-art-display.service
systemctl start  roon-web-config.service

grep GIT_SSH /root/.bashrc || echo 'export GIT_SSH=dbclient' >> /root/.bashrc
## TODO
# tailscale login
# change hostname#

# wifi goes to /var/lib/dietpi/dietpi-wifi.db
# Seems that is used as source for /etc/wpa_supplicant/wpa_supplicant.conf when dietpi-config saves network settings

# Probably want to restart after..?
