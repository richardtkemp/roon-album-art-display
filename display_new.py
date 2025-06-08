#!/usr/bin/env python3
"""
Wrapper script to run the new modular Roon display application.
This replaces the old monolithic display.py with the new structured version.
"""

if __name__ == "__main__":
    from roon_display.main import main

    main()
