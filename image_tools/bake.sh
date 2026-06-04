#!/bin/bash
#
# bake.sh — turn a fresh DietPi image into a self-installing roon-album-art-display
#           image, ready to flash to an SD card. macOS only (uses hdiutil/diskutil).
#
# By default bake flashes the result to an SD card — it lists the external cards
# and asks which one (never auto-selected) — and keeps no image file. Pass --out
# to keep a .img/.img.xz instead of flashing (or as well, if you also --flash).
#
# Usage:
#   image_tools/bake.sh --img fresh.img.xz --hostname frame3                  # bake + flash the card
#   image_tools/bake.sh --img fresh.img.xz --hostname frame3 --flash /dev/disk6
#   image_tools/bake.sh --img fresh.img.xz --hostname frame3 --out frame3.img.xz  # keep a file, no flash
#   image_tools/bake.sh --img fresh.img --hostname f2 --ssid Guest --key s3cret
#
# Options:
#   --img PATH         Fresh DietPi image (.img or .img.xz). Required. Left untouched.
#   --hostname NAME    Device hostname + Tailscale node name. Required.
#   --ssid SSID        Extra WiFi network (repeatable; follow each with --key).
#   --key KEY          WiFi passphrase or 64-hex PSK for the preceding --ssid.
#   --tskey-file PATH  File holding the Tailscale auth key (default: ./tailscale.key).
#                      Baked onto boot, used once, then shredded from the Pi on first boot.
#   --password PASS    Root/SSH password (default: dietpi — CHANGE THIS).
#   --ref GITREF       Git ref to bake (default: HEAD). Only committed files are baked.
#   --out PATH         Keep the baked image at PATH (.img or .img.xz) instead of
#                      only flashing. --out without --flash skips flashing.
#                      Default path when PATH omitted: <img-dir>/<hostname>.img.xz.
#   --no-compress      With --out, emit a raw .img rather than .img.xz.
#   --flash DEVICE     ERASE and flash to DEVICE (e.g. /dev/disk6). Only external
#                      removable disks are accepted. When neither --flash nor --out
#                      is given, bake lists the external SD cards and asks you to
#                      pick one — it never auto-selects a device.
#   --yes              Skip the typed ERASE confirmation. Requires an explicit
#                      --flash DEVICE (with --yes bake will not prompt or pick).
#   --git-branch NAME  Remote branch the frame tracks for `git pull` (default: main).
#   --git-remote URL   Remote URL to attach (default: HTTPS form of local origin,
#                      so a public repo needs no credentials on the frame).
#   --no-git           Don't wire the deployed tree to git (bootstrap tarball only).
#   -h, --help         This help.
#
# Default WiFi networks are read from the repo's (gitignored) wpa_supplicant.conf,
# so Frame/Hyperoptic/etc. are always included; --ssid/--key append to them.
set -euo pipefail

die() { echo "bake: $*" >&2; exit 1; }
[[ "$(uname)" == "Darwin" ]] || die "macOS only (needs hdiutil/diskutil)"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

IMG="" HOSTNAME_ARG="" TSKEY_FILE="$REPO/tailscale.key" PASSWORD="dietpi"
REF="HEAD" OUT="" OUT_EXPLICIT=0 COMPRESS=1 FLASH="" ASSUME_YES=0
GIT_REMOTE="" GIT_BRANCH="main" GIT_CONNECT=1
SUDO="${SUDO:-sudo}"
EXTRA_SSIDS=() EXTRA_KEYS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --img)         IMG="$2"; shift 2 ;;
        --hostname)    HOSTNAME_ARG="$2"; shift 2 ;;
        --ssid)        EXTRA_SSIDS+=("$2"); shift 2 ;;
        --key)         EXTRA_KEYS+=("$2"); shift 2 ;;
        --tskey-file)  TSKEY_FILE="$2"; shift 2 ;;
        --password)    PASSWORD="$2"; shift 2 ;;
        --ref)         REF="$2"; shift 2 ;;
        --out)         OUT="$2"; OUT_EXPLICIT=1; shift 2 ;;
        --no-compress) COMPRESS=0; shift ;;
        --flash)       FLASH="$2"; shift 2 ;;
        --yes)         ASSUME_YES=1; shift ;;
        --git-remote)  GIT_REMOTE="$2"; shift 2 ;;
        --git-branch)  GIT_BRANCH="$2"; shift 2 ;;
        --no-git)      GIT_CONNECT=0; shift ;;
        -h|--help)     awk 'NR>1 && /^set -/{exit} NR>1{sub(/^# ?/,""); print}' "${BASH_SOURCE[0]}"; exit 0 ;;
        *)             die "unknown option: $1 (try --help)" ;;
    esac
done

[[ -n "$IMG" ]]          || die "--img is required"
[[ -f "$IMG" ]]          || die "image not found: $IMG"
[[ -n "$HOSTNAME_ARG" ]] || die "--hostname is required"
[[ ${#EXTRA_SSIDS[@]} -eq ${#EXTRA_KEYS[@]} ]] || die "each --ssid needs a matching --key"
command -v xz >/dev/null || die "xz not found (brew install xz)"

# --- Fail fast on a stale Tailscale key (auth keys expire, 90 days max) ---
if [[ -f "$TSKEY_FILE" ]]; then
    age_days=$(( ( $(date +%s) - $(stat -f %m "$TSKEY_FILE") ) / 86400 ))
    [[ $age_days -le 90 ]] || die "Tailscale key $TSKEY_FILE is ${age_days}d old (>90d) — it has likely expired; regenerate it and update the file"
fi

# --- Flashing (only ever touches an external, removable disk) ---
list_external_disks() {  # -> one /dev/diskN per line (external + removable only)
    local d
    while IFS= read -r d; do
        [[ -n "$d" ]] || continue
        diskutil info "$d" 2>/dev/null | grep -q "Removable Media:.*Removable" && echo "$d"
    done < <(diskutil list external physical 2>/dev/null | awk '/^\/dev\/disk/{print $1}')
}

disk_label() {  # /dev/diskN -> "/dev/diskN  SIZE  (NAME)"
    local d="$1" name size
    name="$(diskutil info "$d" | awk -F': +' '/Device \/ Media Name/{print $2; exit}')"
    size="$(diskutil info "$d" | awk -F': +' '/Disk Size/{print $2; exit}')"
    printf '%s  %s  (%s)' "$d" "${size%% (*}" "$name"
}

resolve_flash_target() {  # /dev/diskN -> validated, or die. No autodetect.
    local dev="$1"
    diskutil list external physical 2>/dev/null | grep -qE "^${dev} \(external" \
        || die "refusing to flash $dev: not an external physical disk"
    diskutil info "$dev" 2>/dev/null | grep -q "Removable Media:.*Removable" \
        || die "refusing to flash $dev: media is not removable"
    echo "$dev"
}

select_flash_target() {  # interactive pick from a list (never auto-selected)
    local devs=() d choice
    while IFS= read -r d; do devs+=("$d"); done < <(list_external_disks)
    [[ ${#devs[@]} -gt 0 ]] || die "no external removable disk found — insert a card, name one with --flash /dev/diskN, or write a file with --out"
    [[ $ASSUME_YES -ne 1 ]] || die "with --yes you must name the device explicitly: --flash /dev/diskN (bake never auto-selects)"
    echo "bake: select the SD card to flash:" >&2
    local i
    for i in "${!devs[@]}"; do
        printf '   [%d] %s\n' "$((i + 1))" "$(disk_label "${devs[$i]}")" >&2
    done
    read -r -p "bake: number (or q to abort): " choice
    [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#devs[@]} )) \
        || die "flash aborted"
    echo "${devs[$((choice - 1))]}"
}

flash_device() {  # device image
    local dev="$1" img="$2" name size raw ans
    name="$(diskutil info "$dev" | awk -F': +' '/Device \/ Media Name/{print $2; exit}')"
    size="$(diskutil info "$dev" | awk -F': +' '/Disk Size/{print $2; exit}')"
    echo
    echo "bake: *** ERASE and flash $dev  ($name, $size) ***"
    if [[ $ASSUME_YES -ne 1 ]]; then
        read -r -p "bake: type ERASE to proceed (anything else aborts): " ans
        [[ "$ans" == "ERASE" ]] || die "flash aborted by user"
    fi
    diskutil unmountDisk "$dev" >/dev/null
    raw="/dev/r${dev#/dev/}"   # raw node is much faster
    echo "bake: writing image to $raw ..."
    $SUDO dd if="$img" of="$raw" bs=4m status=progress
    sync
    diskutil eject "$dev" >/dev/null 2>&1 || true
    echo "bake: flashed and ejected $dev — safe to remove"
}

# Decide what happens to the result, and resolve the flash target NOW (before the
# long bake) so a bad disk or empty selection fails fast:
#   --flash DEVICE      -> flash that device
#   --out (no --flash)  -> keep an image file, don't flash
#   neither             -> list the external SD cards and ask which to flash
WRITE_OUT=$OUT_EXPLICIT
FLASH_DEV=""
if [[ -n "$FLASH" ]]; then
    FLASH_DEV="$(resolve_flash_target "$FLASH")"
elif [[ $OUT_EXPLICIT -eq 0 ]]; then
    FLASH_DEV="$(select_flash_target)"
fi

# --- Build the WiFi list: defaults from wpa_supplicant.conf, then extras ---
WIFI_SSIDS=() WIFI_KEYS=()
if [[ -f "$REPO/wpa_supplicant.conf" ]]; then
    while IFS=$'\t' read -r s k; do
        [[ -n "$s" ]] && { WIFI_SSIDS+=("$s"); WIFI_KEYS+=("$k"); }
    done < <(awk '
        /ssid="/   { s=$0; sub(/.*ssid="/,"",s); sub(/".*/,"",s) }
        /[ \t]psk=/{ k=$0; sub(/.*psk=/,"",k); gsub(/"/,"",k); print s "\t" k }
    ' "$REPO/wpa_supplicant.conf")
fi
for i in "${!EXTRA_SSIDS[@]}"; do
    WIFI_SSIDS+=("${EXTRA_SSIDS[$i]}"); WIFI_KEYS+=("${EXTRA_KEYS[$i]}")
done
[[ ${#WIFI_SSIDS[@]} -gt 0 ]] || die "no WiFi networks (Pi Zero 2 W needs WiFi at first boot)"

# --- Resolve git connection so the deployed tree can `git pull` later ---
# Frames track a real remote branch; the tarball is just the offline bootstrap.
GIT_COMMIT=""
if [[ $GIT_CONNECT -eq 1 ]]; then
    if [[ -z "$GIT_REMOTE" ]]; then
        # Derive an HTTPS (credential-free) URL from the local origin.
        GIT_REMOTE="$(git -C "$REPO" remote get-url origin 2>/dev/null \
            | sed -E 's#^git@([^:]+):#https://\1/#; s#^ssh://git@([^/]+)/#https://\1/#')"
    fi
    [[ -n "$GIT_REMOTE" ]] || die "no git remote (set --git-remote, or pass --no-git)"
    GIT_COMMIT="$(git -C "$REPO" rev-parse "$REF")"
    if ! git -C "$REPO" merge-base --is-ancestor \
        "$GIT_COMMIT" "origin/$GIT_BRANCH" 2>/dev/null; then
        echo "bake: WARNING — baked commit ${GIT_COMMIT:0:9} is not on origin/$GIT_BRANCH;"
        echo "bake:           push it (and fetch) or the frame cannot 'git pull' to this code."
    fi
fi

# --- Output path (only when keeping an image) ---
if [[ $WRITE_OUT -eq 1 && -z "$OUT" ]]; then
    OUT="$(dirname "$IMG")/${HOSTNAME_ARG}.img$([[ $COMPRESS -eq 1 ]] && echo .xz)"
fi

echo "bake: image      $IMG"
echo "bake: hostname   $HOSTNAME_ARG"
echo "bake: wifi       ${WIFI_SSIDS[*]}"
echo "bake: tailscale  $([[ -f "$TSKEY_FILE" ]] && echo "$TSKEY_FILE" || echo "(none — skipping)")"
echo "bake: git ref    $REF"
echo "bake: git remote $([[ $GIT_CONNECT -eq 1 ]] && echo "$GIT_REMOTE @ $GIT_BRANCH" || echo "(disabled)")"
echo "bake: output     $([[ $WRITE_OUT -eq 1 ]] && echo "$OUT" || echo "(none)")"
echo "bake: flash      ${FLASH_DEV:-(none)}"

# --- Decompress / copy to a scratch working image (source stays clean) ---
WORK="$(mktemp -d)/work.img"
DISK="" MNT=""
cleanup() {
    [[ -n "$MNT"  && -d "$MNT" ]] && diskutil unmount "$MNT" >/dev/null 2>&1 || true
    [[ -n "$DISK" ]] && hdiutil detach "$DISK" >/dev/null 2>&1 || true
    rm -rf "$(dirname "$WORK")"
}
trap cleanup EXIT

echo "bake: preparing working image..."
case "$IMG" in
    *.xz) xz -dc "$IMG" > "$WORK" ;;
    *)    cp "$IMG" "$WORK" ;;
esac

# --- Attach and locate the FAT boot partition's mountpoint ---
ATTACH="$(hdiutil attach "$WORK")"
DISK="$(awk '/FDisk_partition_scheme/{print $1; exit}' <<<"$ATTACH")"
FATDEV="$(awk '/Windows_FAT_32/{print $1; exit}' <<<"$ATTACH")"
[[ -n "$FATDEV" ]] || die "no FAT boot partition found in image"
MNT="$(diskutil info "$FATDEV" | awk -F': +' '/Mount Point/{print $2; exit}')"
[[ -n "$MNT" && -d "$MNT" ]] || die "boot partition did not mount"
echo "bake: boot partition mounted at $MNT"

# --- Validate this is a DietPi automation image before editing ---
[[ -f "$MNT/dietpi.txt" && -f "$MNT/dietpi-wifi.txt" ]] || die "not a DietPi image (no dietpi.txt)"

# --- Edit dietpi.txt automation switches ---
set_key() {  # file key value   (handles existing, commented, or missing keys)
    local f="$1" k="$2" v="$3"
    if grep -qE "^${k}=" "$f"; then
        sed -i '' -E "s|^${k}=.*|${k}=${v}|" "$f"
    elif grep -qE "^#${k}=" "$f"; then
        sed -i '' -E "s|^#${k}=.*|${k}=${v}|" "$f"
    else
        printf '%s=%s\n' "$k" "$v" >> "$f"
    fi
}
DT="$MNT/dietpi.txt"
set_key "$DT" AUTO_SETUP_AUTOMATED            1
set_key "$DT" AUTO_SETUP_CUSTOM_SCRIPT_EXEC   1
set_key "$DT" AUTO_SETUP_NET_WIFI_ENABLED     1
set_key "$DT" AUTO_SETUP_SSH_SERVER_INDEX     -1
set_key "$DT" AUTO_SETUP_GLOBAL_PASSWORD      "$PASSWORD"
set_key "$DT" AUTO_SETUP_NET_HOSTNAME         "$HOSTNAME_ARG"
# git(17) python3(130) rpi.gpio(69) wiringpi(70) tailscale(58)
set_key "$DT" AUTO_SETUP_INSTALL_SOFTWARE_ID  "17 130 69 70 58"

# --- Write WiFi entries into dietpi-wifi.txt ---
WT="$MNT/dietpi-wifi.txt"
for i in "${!WIFI_SSIDS[@]}"; do
    s="${WIFI_SSIDS[$i]}" k="${WIFI_KEYS[$i]}"
    mgr="WPA-PSK"; [[ -z "$k" ]] && mgr="NONE"
    if grep -q "aWIFI_SSID\[$i\]=" "$WT"; then
        sed -i '' -E "s|^aWIFI_SSID\[$i\]=.*|aWIFI_SSID[$i]='$s'|"   "$WT"
        sed -i '' -E "s|^aWIFI_KEY\[$i\]=.*|aWIFI_KEY[$i]='$k'|"     "$WT"
        sed -i '' -E "s|^aWIFI_KEYMGR\[$i\]=.*|aWIFI_KEYMGR[$i]='$mgr'|" "$WT"
    else
        printf "aWIFI_SSID[%s]='%s'\naWIFI_KEY[%s]='%s'\naWIFI_KEYMGR[%s]='%s'\n" \
            "$i" "$s" "$i" "$k" "$i" "$mgr" >> "$WT"
    fi
done

# --- Custom script + project tarball + tailscale key onto the boot partition ---
cp "$REPO/image_tools/Automation_Custom_Script.sh" "$MNT/Automation_Custom_Script.sh"
git -C "$REPO" archive --format=tar.gz -o "$MNT/roon-album-art-display.tar.gz" "$REF"
if [[ -f "$TSKEY_FILE" ]]; then
    cp "$TSKEY_FILE" "$MNT/tailscale.key"
else
    echo "bake: WARNING — no Tailscale key ($TSKEY_FILE); image will not join the tailnet"
fi
# git-remote.env tells the first-boot script how to wire the deployed tree to git.
if [[ $GIT_CONNECT -eq 1 ]]; then
    printf 'GIT_REMOTE=%s\nGIT_BRANCH=%s\nGIT_COMMIT=%s\n' \
        "$GIT_REMOTE" "$GIT_BRANCH" "$GIT_COMMIT" > "$MNT/git-remote.env"
fi

# --- Seal: unmount, detach, emit flashable image ---
echo "bake: sealing image..."
sync
diskutil unmount "$MNT" >/dev/null; MNT=""
hdiutil detach "$DISK" >/dev/null; DISK=""

if [[ $WRITE_OUT -eq 1 ]]; then
    mkdir -p "$(dirname "$OUT")"
    if [[ $COMPRESS -eq 1 ]]; then
        xz -T0 -c "$WORK" > "$OUT"
    else
        cp "$WORK" "$OUT"
    fi
    echo "bake: image -> $OUT"
    ls -lh "$OUT"
fi

# Flash from the raw working image (no recompress/redecompress needed)
[[ -n "$FLASH_DEV" ]] && flash_device "$FLASH_DEV" "$WORK"

echo "bake: done"
