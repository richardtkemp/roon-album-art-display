"""Utility functions for file and path operations."""

import functools
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, FrozenSet, Optional, Tuple, TypeVar

SUPPORTED_IMAGE_EXTENSIONS: FrozenSet[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".avif"}
)

_F = TypeVar("_F", bound=Callable[..., Any])

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


def get_text_size(draw: Any, text: str, font: Any) -> Tuple[int, int]:
    """Get text dimensions using font metrics.

    Args:
        draw: PIL ImageDraw instance
        text: Text to measure
        font: PIL font instance (or None for estimate)

    Returns:
        (width, height) tuple
    """
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    else:
        # Estimate text size without font
        return len(text) * 10, 20


def scale_image_to_fit(
    img_width: int,
    img_height: int,
    area_width: int,
    area_height: int,
) -> Tuple[int, int]:
    """Calculate scaled dimensions to fit an image within an area, preserving aspect ratio.

    Returns:
        (scaled_width, scaled_height) tuple
    """
    img_ratio = img_width / img_height

    if img_width > img_height:
        scaled_width = area_width
        scaled_height = int(scaled_width / img_ratio)
        if scaled_height > area_height:
            scaled_height = area_height
            scaled_width = int(scaled_height * img_ratio)
    else:
        scaled_height = area_height
        scaled_width = int(scaled_height * img_ratio)
        if scaled_width > area_width:
            scaled_width = area_width
            scaled_height = int(scaled_width / img_ratio)

    return scaled_width, scaled_height


# Global flag for performance logging - set by main.py from config
_performance_logging_enabled = False


def set_performance_logging(level: str) -> None:
    """Set global performance logging level."""
    global _performance_logging_enabled
    _performance_logging_enabled = bool(level)  # Any non-empty string enables it


def log_performance(
    threshold: float = 0.5, description: Optional[str] = None
) -> Callable[[_F], _F]:
    """Decorator to log function execution time if performance logging is enabled.

    Args:
        threshold: Minimum time in seconds to log (default: 0.5s)
        description: Optional custom description for the operation
    """

    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
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

        return wrapper  # type: ignore[return-value]

    return decorator
