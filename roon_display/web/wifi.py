"""WiFi network management for DietPi systems."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WIFI_DB_PATH = Path("/var/lib/dietpi/dietpi-wifi.db")
WIFIDB_APPLY_CMD = "/boot/dietpi/func/dietpi-wifidb"
MAX_SLOTS = 5


def get_current_ssid() -> Optional[str]:
    """Get the currently connected WiFi SSID."""
    try:
        result = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def get_saved_networks() -> List[Dict[str, Any]]:
    """Read saved WiFi networks from dietpi-wifi.db."""
    if not WIFI_DB_PATH.exists():
        return []

    content = WIFI_DB_PATH.read_text()
    networks = []

    for slot in range(MAX_SLOTS):
        ssid = _extract_value(content, "aWIFI_SSID", slot)
        if not ssid:
            continue
        networks.append(
            {
                "slot": slot,
                "ssid": ssid,
                "key_mgmt": _extract_value(content, "aWIFI_KEYMGR", slot) or "WPA-PSK",
                "has_key": bool(_extract_value(content, "aWIFI_KEY", slot)),
            }
        )

    return networks


def add_network(ssid: str, password: str) -> str:
    """Add a WiFi network to the database and apply.

    Returns empty string on success, error message on failure.
    """
    if not WIFI_DB_PATH.exists():
        return "dietpi-wifi.db not found — not a DietPi system?"

    content = WIFI_DB_PATH.read_text()

    # Find first empty slot
    slot = None
    for i in range(MAX_SLOTS):
        if not _extract_value(content, "aWIFI_SSID", i):
            slot = i
            break

    if slot is None:
        return f"All {MAX_SLOTS} WiFi slots are full. Delete one first."

    # Generate hashed PSK
    psk = _hash_password(ssid, password)
    if psk is None:
        return "Failed to hash WiFi password"

    # Write to the slot
    _set_slot(slot, ssid, psk)

    # Apply
    return _apply_db()


def delete_network(slot: int) -> str:
    """Delete a WiFi network by slot index.

    Returns empty string on success, error message on failure.
    """
    if not WIFI_DB_PATH.exists():
        return "dietpi-wifi.db not found"

    if slot < 0 or slot >= MAX_SLOTS:
        return f"Invalid slot {slot}"

    content = WIFI_DB_PATH.read_text()
    ssid = _extract_value(content, "aWIFI_SSID", slot)
    if not ssid:
        return f"Slot {slot} is already empty"

    # Check if this is the active network
    current = get_current_ssid()
    if current and current == ssid:
        return f"Cannot delete '{ssid}' — currently connected"

    _set_slot(slot, "", "")

    return _apply_db()


def _extract_value(content: str, key: str, slot: int) -> Optional[str]:
    """Extract a value like aWIFI_SSID[0]='value' from the DB content."""
    pattern = rf"^{re.escape(key)}\[{slot}\]='(.*)'$"
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def _hash_password(ssid: str, password: str) -> Optional[str]:
    """Hash a WiFi password using wpa_passphrase."""
    try:
        result = subprocess.run(
            ["wpa_passphrase", ssid, password], capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(f"wpa_passphrase failed: {result.stderr}")
            return None
        # Extract the hex PSK (not the commented plaintext one)
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("psk=") and "#" not in line:
                return line.split("=", 1)[1]
    except FileNotFoundError:
        logger.error("wpa_passphrase not found")
    return None


def _set_slot(slot: int, ssid: str, psk: str) -> None:
    """Write a WiFi slot in the database file."""
    content = WIFI_DB_PATH.read_text()

    fields = {
        "aWIFI_SSID": ssid,
        "aWIFI_KEY": psk,
        "aWIFI_KEYMGR": "WPA-PSK" if ssid else "",
        "aWIFI_PROTO": "",
        "aWIFI_PAIRWISE": "",
        "aWIFI_AUTH_ALG": "",
        "aWIFI_EAP": "",
        "aWIFI_IDENTITY": "",
        "aWIFI_PASSWORD": "",
        "aWIFI_PHASE1": "",
        "aWIFI_PHASE2": "",
        "aWIFI_CERT": "",
    }

    for key, value in fields.items():
        pattern = rf"^{re.escape(key)}\[{slot}\]='.*'$"
        replacement = f"{key}[{slot}]='{value}'"
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    WIFI_DB_PATH.write_text(content)


def _apply_db() -> str:
    """Run dietpi-wifidb to apply the database to the system.

    Returns empty string on success, error message on failure.
    """
    try:
        result = subprocess.run(
            [WIFIDB_APPLY_CMD, "1"], capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.error(f"dietpi-wifidb failed: {msg}")
            return f"Failed to apply WiFi config: {msg}"
        logger.info("WiFi database applied successfully")
        return ""
    except FileNotFoundError:
        return "dietpi-wifidb not found — not a DietPi system?"
    except subprocess.TimeoutExpired:
        return "dietpi-wifidb timed out"
