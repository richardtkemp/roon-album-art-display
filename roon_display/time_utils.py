"""Utilities for parsing natural language time expressions."""

import re
from typing import Union


def parse_time_to_seconds(time_str: Union[str, int]) -> int:
    """Parse natural language time expression to seconds.
    
    Supports formats like:
    - "5 mins", "5 minutes", "5min"
    - "30 secs", "30 seconds", "30sec", "30s" 
    - "2 hours", "2hrs", "2h"
    - "1 day", "1 days"
    - Plain numbers (treated as seconds): "600", 600
    
    Args:
        time_str: Time expression as string or integer
        
    Returns:
        Time in seconds as integer
        
    Raises:
        ValueError: If time expression cannot be parsed
    """
    # If already an integer, return as-is (assuming seconds)
    if isinstance(time_str, int):
        return time_str
    
    # If string representation of number, convert to int
    if isinstance(time_str, str) and time_str.strip().isdigit():
        return int(time_str.strip())
    
    if not isinstance(time_str, str):
        raise ValueError(f"Invalid time format: {time_str}")
    
    # Normalize the string
    time_str = time_str.strip().lower()
    
    # Define time unit multipliers (in seconds)
    units = {
        # Seconds
        's': 1,
        'sec': 1,
        'secs': 1,
        'second': 1,
        'seconds': 1,
        
        # Minutes  
        'm': 60,
        'min': 60,
        'mins': 60,
        'minute': 60,
        'minutes': 60,
        
        # Hours
        'h': 3600,
        'hr': 3600,
        'hrs': 3600,
        'hour': 3600,
        'hours': 3600,
        
        # Days
        'd': 86400,
        'day': 86400,
        'days': 86400,
    }
    
    # Try to match patterns like "5 mins", "30 seconds", "2h", etc.
    # Pattern: optional number, optional space, unit
    pattern = r'^(\d+(?:\.\d+)?)\s*([a-z]+)$'
    match = re.match(pattern, time_str)
    
    if not match:
        raise ValueError(f"Invalid time format: '{time_str}'. Expected formats: '5 mins', '30 seconds', '2h', etc.")
    
    number_str, unit = match.groups()
    
    try:
        number = float(number_str)
    except ValueError:
        raise ValueError(f"Invalid number in time expression: '{number_str}'")
    
    if unit not in units:
        available_units = sorted(set(units.keys()))
        raise ValueError(f"Unknown time unit: '{unit}'. Available units: {', '.join(available_units)}")
    
    # Calculate seconds
    seconds = number * units[unit]
    
    # Return as integer
    return int(seconds)


def parse_time_to_minutes(time_str: Union[str, int]) -> int:
    """Parse natural language time expression to minutes.
    
    Convenience function that converts to seconds first, then to minutes.
    
    Args:
        time_str: Time expression as string or integer
        
    Returns:
        Time in minutes as integer
    """
    seconds = parse_time_to_seconds(time_str)
    return int(seconds / 60)