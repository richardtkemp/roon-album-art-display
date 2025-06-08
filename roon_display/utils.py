"""Utility functions for file and path operations."""

import os
from pathlib import Path
from typing import Optional


def get_root_dir() -> Path:
    """Get the root directory of the project."""
    return Path(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def get_saved_image_dir() -> Path:
    """Get the directory where album art images are saved."""
    return get_root_dir() / "album_art"


def set_current_image_key(key: str) -> None:
    """Save the current image key to file."""
    if not key:
        raise ValueError("Image key cannot be empty")

    path = get_saved_image_dir() / "current_key"
    path.parent.mkdir(exist_ok=True)
    path.write_text(key)


def get_current_image_key() -> Optional[str]:
    """Get the current image key from file."""
    path = get_saved_image_dir() / "current_key"
    if path.exists():
        return path.read_text().strip()
    return None


def ensure_image_dir_exists() -> Path:
    """Ensure the album art directory exists."""
    dir_path = get_saved_image_dir()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    return dir_path
