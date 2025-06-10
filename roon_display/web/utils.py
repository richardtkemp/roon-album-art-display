"""Utility functions for the web interface."""

import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image
from werkzeug.utils import secure_filename

from ..utils import get_extra_images_dir

logger = logging.getLogger(__name__)


def validate_image_format(file_data: bytes, filename: str) -> bool:
    """Validate that uploaded file is a supported image format."""
    try:
        # Create a test image from the uploaded data
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(file_data)
            tmp_file.flush()

            # Try to open and verify the image
            with Image.open(tmp_file.name) as img:
                img.verify()

        # Additional check: ensure it has a valid image extension
        valid_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tiff",
            ".tif",
            ".webp",
            ".avif",
        }
        file_ext = Path(filename).suffix.lower()
        return file_ext in valid_extensions

    except Exception as e:
        logger.warning(f"Image validation failed for {filename}: {e}")
        return False


def get_anniversary_images() -> Dict[str, List[str]]:
    """Get existing anniversary images organized by anniversary name."""
    anniversary_images = {}
    extra_images_dir = get_extra_images_dir()

    if extra_images_dir.exists():
        for anniversary_dir in extra_images_dir.iterdir():
            if anniversary_dir.is_dir():
                image_files = []
                valid_extensions = {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".bmp",
                    ".gif",
                    ".tiff",
                    ".tif",
                    ".webp",
                    ".avif",
                }

                for file_path in anniversary_dir.iterdir():
                    if (
                        file_path.is_file()
                        and file_path.suffix.lower() in valid_extensions
                    ):
                        image_files.append(file_path.name)

                if image_files:
                    anniversary_images[anniversary_dir.name] = sorted(image_files)

    return anniversary_images


def create_thumbnail(
    image_path: Path, max_size: Tuple[int, int] = (150, 150), jpeg_quality: int = 85
) -> bytes:
    """Create a thumbnail from an image file."""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for transparency handling)
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                rgb_img.paste(
                    img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
                )
                img = rgb_img

            # Create thumbnail
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to bytes
            import io

            thumb_io = io.BytesIO()
            img.save(thumb_io, format="JPEG", quality=jpeg_quality)
            thumb_io.seek(0)
            return thumb_io.getvalue()

    except Exception as e:
        logger.warning(f"Failed to create thumbnail for {image_path}: {e}")
        return None


def delete_anniversary_image(anniversary_name: str, filename: str) -> bool:
    """Delete a specific anniversary image file."""
    try:
        anniversary_dir = get_extra_images_dir() / anniversary_name
        image_path = anniversary_dir / filename

        if image_path.exists() and image_path.is_file():
            image_path.unlink()
            logger.info(f"Deleted anniversary image: {image_path}")

            # Remove directory if it's now empty
            if anniversary_dir.exists() and not any(anniversary_dir.iterdir()):
                anniversary_dir.rmdir()
                logger.info(f"Removed empty anniversary directory: {anniversary_dir}")

            return True
        else:
            logger.warning(f"Image file not found: {image_path}")
            return False

    except Exception as e:
        logger.error(
            f"Error deleting anniversary image {anniversary_name}/{filename}: {e}"
        )
        return False


def create_placeholder_image(jpeg_quality: int = 85) -> bytes:
    """Create placeholder image when main app not available."""
    try:
        # Create simple placeholder image
        placeholder = Image.new("RGB", (400, 300), color=(200, 200, 200))

        # Convert to bytes
        import io
        img_io = io.BytesIO()
        placeholder.save(img_io, "JPEG", quality=jpeg_quality)
        img_io.seek(0)
        return img_io.getvalue()

    except Exception as e:
        logger.error(f"Error creating placeholder: {e}")
        return None