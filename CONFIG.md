# Configuration Manual

The `roon.cfg` file contains all configuration options for the Roon Album Art Display. A default configuration is created automatically on first run.

## Time Format

All time values support natural language formats:
- `"30 seconds"`, `"30s"`, `"30 secs"`
- `"5 minutes"`, `"5 mins"`, `"5m"`
- `"2 hours"`, `"2h"`, `"2 hrs"`
- Plain numbers are treated as the base unit (seconds for most, minutes for anniversaries)

## Configuration Sections

### [DISPLAY] - Display Hardware

| Setting | Default | Description |
|---------|---------|-------------|
| `display_name` | `Roon Display` | Name shown in Roon settings and web UI title — change if you have multiple displays |
| `type` | `epd13in3E` | Display type: `epd13in3E` or `system_display` |
| `tkinter_fullscreen` | `false` | Fullscreen mode (system_display only) |
| `interrupt_on_skip` | `false` | Cancel current render and start new one when track changes |

### [IMAGE_RENDER] - Image Enhancement

| Setting | Default | Description |
|---------|---------|-------------|
| `colour_balance_adjustment` | `1` | Color saturation (0.0-2.0) |
| `contrast_adjustment` | `1` | Contrast (0.0-2.0) |
| `sharpness_adjustment` | `1` | Sharpness (0.0-2.0) |
| `brightness_adjustment` | `1` | Brightness (0.0-2.0) |

### [IMAGE_POSITION] - Image Positioning

| Setting | Default | Description |
|---------|---------|-------------|
| `position_offset_x` | `0` | Horizontal offset in pixels |
| `position_offset_y` | `0` | Vertical offset in pixels |
| `scale_x` | `1` | Horizontal scale factor |
| `scale_y` | `1` | Vertical scale factor |
| `rotation` | `270` | Rotation in degrees (0, 90, 180, 270) |

Images are scaled from center. Zero offsets maintain center positioning.

### [ZONES] - Zone Filtering

| Setting | Default | Description |
|---------|---------|-------------|
| `allowed_zone_names` | `comma,separated,list` | Only show art from these zones |
| `forbidden_zone_names` | `comma,separated,list` | Never show art from these zones |

Use zone names exactly as they appear in Roon. Leave empty to allow all zones.

### [ANNIVERSARIES] - Special Occasion Display

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `false` | Enable anniversary feature |

**Anniversary Format:** `name = dd/mm/yyyy,message,wait_time`

**Example:**
```ini
birthday_john = 15/03/1990,Happy ${years} birthday John!,30 minutes
```

- **Date:** `dd/mm/yyyy` format
- **Message:** Text to display. Use `${years}` for age calculation
- **Wait time:** How long to wait after last track before showing
- **Images:** Place images in `extra_images/[name]/` directory

### [HEALTH] - Health Monitoring

| Setting | Default | Description |
|---------|---------|-------------|
| `health_script` | _(empty)_ | Path to health monitoring script |
| `health_recheck_interval` | `30 minutes` | How often to re-call script |

The health script receives two parameters:
- **param1:** `"good"` (successful render) or `"bad"` (failed render)
- **param2:** Additional information about the render

**Example:**
```bash
#!/bin/bash
if [[ "$1" == "good" ]]; then
    curl -X POST --data-raw "$2" "https://healthchecks.io/ping/your-uuid"
else
    curl -X POST --data-raw "$2" "https://healthchecks.io/ping/your-uuid/fail"
fi
```

## File Locations

- **Config:** `roon.cfg` (project root)
- **Images:** `album_art/` (downloaded album art)
- **Anniversary Images:** `extra_images/[anniversary_name]/`
- **Logs:** `logs/` (timestamped log files)

## Supported Image Formats

- **Standard:** JPEG, PNG, BMP, GIF, TIFF
- **Modern:** WebP, AVIF (requires system libraries)

Run `python3 check_image_formats.py` to verify format support.
