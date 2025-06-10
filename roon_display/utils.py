"""Utility functions for file and path operations."""

import functools
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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


def set_last_track_time(timestamp: float) -> None:
    """Save the last track time to file."""
    path = get_saved_image_dir() / "last_track_time"
    path.parent.mkdir(exist_ok=True)
    path.write_text(str(timestamp))


def get_last_track_time() -> Optional[float]:
    """Get the last track time from file."""
    path = get_saved_image_dir() / "last_track_time"
    if path.exists():
        try:
            return float(path.read_text().strip())
        except (ValueError, OSError):
            logger.warning("Invalid last track time file, ignoring")
            return None
    return None


def ensure_image_dir_exists() -> Path:
    """Ensure the album art directory exists."""
    dir_path = get_saved_image_dir()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


def get_extra_images_dir() -> Path:
    """Get the directory for anniversary/extra images."""
    return get_root_dir() / "extra_images"


def ensure_extra_images_dir_exists() -> Path:
    """Ensure the extra images directory exists."""
    dir_path = get_extra_images_dir()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Created extra images directory: {dir_path}")
    return dir_path


def ensure_anniversary_dir_exists(anniversary_name: str) -> Path:
    """Ensure the directory for a specific anniversary exists."""
    anniversary_dir = get_extra_images_dir() / anniversary_name
    if not anniversary_dir.exists():
        anniversary_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created anniversary directory: {anniversary_dir}")
    return anniversary_dir


# Global flag for performance logging - set by main.py from config
_performance_logging_enabled = False


def set_performance_logging(level: str) -> None:
    """Set global performance logging level."""
    global _performance_logging_enabled
    _performance_logging_enabled = bool(level)  # Any non-empty string enables it


def log_performance(threshold: float = 0.5, description: str = None):
    """Decorator to log function execution time if performance logging is enabled.

    Args:
        threshold: Minimum time in seconds to log (default: 0.5s)
        description: Optional custom description for the operation
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not _performance_logging_enabled:
                return func(*args, **kwargs)

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed_time = time.time() - start_time
                if elapsed_time >= threshold:
                    operation_desc = description or f"{func.__module__}.{func.__name__}"
                    logger.info(f"⏱️  PERF: {operation_desc} took {elapsed_time:.2f}s")

        return wrapper

    return decorator
