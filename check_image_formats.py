#!/usr/bin/env python3
"""
Image Format Support Checker for Roon Album Art Display

This script checks which image formats are supported by your PIL/Pillow installation.
Run this on your Raspberry Pi to verify anniversary image format support.

Usage: python3 check_image_formats.py
"""

import os
import tempfile
from PIL import Image


def check_format_support():
    """Check which image formats are supported by PIL/Pillow."""
    print("PIL/Pillow Image Format Support Check")
    print("=" * 50)
    print(f"Pillow version: {Image.__version__}")
    print()

    # Standard formats that should always work
    standard_formats = {
        'JPEG': ['.jpg', '.jpeg'],
        'PNG': ['.png'],
        'BMP': ['.bmp'],
        'GIF': ['.gif'],
        'TIFF': ['.tiff', '.tif']
    }

    # Modern formats that may need additional libraries
    modern_formats = {
        'WEBP': ['.webp'],
        'AVIF': ['.avif']
    }

    print("Standard formats (should always work):")
    print("-" * 40)
    for fmt, extensions in standard_formats.items():
        check_format(fmt, extensions[0])

    print("\nModern formats (may need additional libraries):")
    print("-" * 50)
    for fmt, extensions in modern_formats.items():
        check_format(fmt, extensions[0])

    print("\nInstallation instructions if formats are missing:")
    print("=" * 50)
    print("# For WebP support:")
    print("sudo apt update")
    print("sudo apt install libwebp-dev")
    print()
    print("# For AVIF support (Ubuntu 20.04+/Debian 11+):")
    print("sudo apt install libavif-dev")
    print()
    print("# After installing libraries, reinstall Pillow:")
    print("pip3 install --upgrade --force-reinstall Pillow")
    print()
    print("# Or for system-wide installation:")
    print("sudo pip3 install --upgrade --force-reinstall Pillow")


def check_format(format_name, extension):
    """Test if a specific format is supported by trying to save a test image."""
    try:
        # Create a small test image
        test_img = Image.new('RGB', (1, 1), color='white')
        
        # Try to save in the format
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp_file:
            test_img.save(tmp_file.name, format_name)
            tmp_path = tmp_file.name
        
        # Try to open it back
        with Image.open(tmp_path) as verify_img:
            verify_img.verify()
        
        # Clean up
        os.unlink(tmp_path)
        
        print(f"✅ {format_name:<6} ({extension}): Supported")
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "cannot write" in error_msg.lower():
            reason = "write support missing"
        elif "cannot identify" in error_msg.lower():
            reason = "format not recognized"
        elif "decoder" in error_msg.lower():
            reason = "decoder missing"
        else:
            reason = f"error: {error_msg}"
        
        print(f"❌ {format_name:<6} ({extension}): Not supported ({reason})")
        return False


def check_anniversary_directory():
    """Check what image formats are actually present in anniversary directories."""
    try:
        from pathlib import Path
        extra_images_dir = Path("extra_images")
        
        if not extra_images_dir.exists():
            print(f"\nNo extra_images directory found at: {extra_images_dir}")
            return
        
        print(f"\nChecking anniversary images in: {extra_images_dir}")
        print("-" * 50)
        
        found_images = False
        for anniversary_dir in extra_images_dir.iterdir():
            if anniversary_dir.is_dir():
                images = list(anniversary_dir.glob("*"))
                image_files = [f for f in images if f.is_file() and f.suffix.lower() in 
                              {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.avif'}]
                
                if image_files:
                    found_images = True
                    print(f"\n📁 {anniversary_dir.name}/:")
                    for img_file in sorted(image_files):
                        # Test if this specific file can be opened
                        try:
                            with Image.open(img_file) as test_img:
                                test_img.verify()
                            status = "✅"
                        except Exception as e:
                            status = f"❌ ({e})"
                        print(f"   {status} {img_file.name}")
        
        if not found_images:
            print("No anniversary image directories found with images.")
            print("Create directories like: extra_images/birthday_john/")
    
    except Exception as e:
        print(f"Error checking anniversary directory: {e}")


if __name__ == "__main__":
    check_format_support()
    check_anniversary_directory()