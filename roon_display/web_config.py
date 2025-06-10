"""
Compatibility wrapper for the refactored web configuration module.
This file maintains backward compatibility with existing imports and service files.
"""

# Re-export the main function from the new modular structure
from .web.app import main

# For backward compatibility, also expose the main classes
from .web.app import InternalAppClient, create_app
from .web.config_handler import WebConfigHandler
from .web.utils import (
    create_placeholder_image,
    create_thumbnail,
    delete_anniversary_image,
    get_anniversary_images,
    validate_image_format,
)

# Maintain backward compatibility for any direct imports
__all__ = [
    "main",
    "InternalAppClient", 
    "WebConfigHandler",
    "create_app",
    "validate_image_format",
    "get_anniversary_images", 
    "create_thumbnail",
    "delete_anniversary_image",
    "create_placeholder_image"
]

if __name__ == "__main__":
    main()