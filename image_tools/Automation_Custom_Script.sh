#!/bin/bash
# DietPi first-boot custom script for roon-album-art-display.
# Copied onto the boot partition by image_tools/bake.sh and run ONCE as root by
# DietPi, after dietpi-software installs (git, python3, rpi.gpio, wiringpi,
# tailscale) and with networking up. DietPi reboots automatically when the
# automated first run completes, so services are `enable`d for a clean cold start.
#
# NOTE: no `set -x` on purpose — it would echo the Tailscale auth key into
# /var/tmp/dietpi/logs. Keep secret handling quiet.

# Locate the FAT boot partition (Trixie: /boot/firmware, older: /boot)
BOOT=/boot/firmware
[[ -f "$BOOT/roon-album-art-display.tar.gz" ]] || BOOT=/boot

DATA=/mnt/dietpi_userdata
PROJECT=roon-album-art-display
FRAME="$DATA/$PROJECT"

# --- Python deps not covered by dietpi-software ---
# NB: DietPi's python3 ships without pip, so install python3-pip and invoke pip
# as `python3 -m pip` (there is no bare `pip`/`pip3` on PATH otherwise).
apt-get install -y python3-pip python3-pil python3-requests python3-numpy python3-psutil \
                   libavif-dev fonts-dejavu-core neovim
# Trixie is PEP 668 externally-managed; roonapi/flask are only on PyPI
python3 -m pip install --break-system-packages roonapi flask

# Fail loudly in the first-run log if any dep is missing. Without this a silent
# pip/apt failure is invisible until the service crashloops after reboot.
python3 -c 'import roonapi, flask, PIL, numpy, psutil' \
    || echo 'bake: FATAL — Python deps missing (roonapi/flask/PIL/numpy/psutil); the app will not start'

# --- Deploy the baked project ---
mkdir -p "$FRAME/logs"
tar -xzf "$BOOT/roon-album-art-display.tar.gz" -C "$FRAME"

# --- systemd services (enabled now; started clean on DietPi's post-install reboot) ---
cp "$FRAME"/space-cleaner.{service,timer}  /etc/systemd/system/
cp "$FRAME"/roon-album-art-display.service /etc/systemd/system/
cp "$FRAME"/roon-web-config.service        /etc/systemd/system/
systemctl daemon-reload
systemctl enable space-cleaner.timer
systemctl enable roon-album-art-display.service
systemctl enable roon-web-config.service

# --- Tailscale: read key from boot, join tailnet, then PURGE the key ---
if [[ -f "$BOOT/tailscale.key" ]]; then
    systemctl start tailscaled 2>/dev/null || true
    tailscale up --hostname="$(hostname)" --auth-key="$(cat "$BOOT/tailscale.key")" || true
    # Purge so the key never lingers on the device's SD card.
    shred -u "$BOOT/tailscale.key" 2>/dev/null || rm -f "$BOOT/tailscale.key"
fi

# --- Convenience: GIT_SSH so a future `git pull` uses dropbear ---
grep -q GIT_SSH /root/.bashrc || echo 'export GIT_SSH=dbclient' >> /root/.bashrc

exit 0
