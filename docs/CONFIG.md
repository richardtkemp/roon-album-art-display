# Configuration Reference

All settings are stored in `roon.cfg` and can be edited via the web UI.

## Image Tab

### Image Render

Image enhancement applied to album art before display.

| Key | Default | Description |
|-----|---------|-------------|
| `color_enhance` | 1.0 | Color saturation factor. 1.0 = no change, >1 = more saturated. |
| `contrast` | 1.0 | Contrast factor. 1.0 = no change. |
| `brightness` | 1.0 | Brightness factor. 1.0 = no change. |
| `sharpness` | 1.0 | Sharpness factor. 1.0 = no change. |

### Image Position

How album art is sized and placed on the display canvas.

| Key | Default | Description |
|-----|---------|-------------|
| `scale_x` | 1.0 | Horizontal scale. 1.0 = fill the canvas width. Smaller values leave white borders. |
| `scale_y` | 1.0 | Vertical scale. 1.0 = fill the canvas height. |
| `rotation` | 0 | Rotation in degrees. Must be 0, 90, 180, or 270. |
| `image_offset_x` | 0 | Horizontal offset in pixels from centre. |
| `image_offset_y` | 0 | Vertical offset in pixels from centre. |

### Overlay

The overlay is a small badge shown in the bottom-right corner of the album art when the app needs to display a message (e.g. connection lost, searching for server). It is sized relative to the album art bounds, not the full display.

| Key | Default | Description |
|-----|---------|-------------|
| `size_x_percent` | 33 | Overlay width as percentage of art width. |
| `size_y_percent` | 15 | Overlay height as percentage of art height. |
| `font` | *(auto-detected)* | Font for overlay text. Discovered from system fonts. |
| `font_size` | 20 | Overlay font size in pixels. |
| `line_spacing` | 10 | Spacing between lines of overlay text in pixels. |
| `margin` | 20 | Inner margin/padding for overlay text in pixels. |

## Features Tab

### Zones

Control which Roon zones this display responds to.

| Key | Default | Description |
|-----|---------|-------------|
| `allowed_zone_names` | *(empty)* | Comma-separated zone names to respond to. Empty = all zones. |
| `forbidden_zone_names` | *(empty)* | Comma-separated zone names to ignore. |

### Anniversaries

Display special images and messages on configured dates.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | false | Enable anniversary notifications. |

Anniversary entries are added as freeform keys in the `[ANNIVERSARIES]` section:

```ini
name = dd/mm/yyyy,message,wait_time
```

Example:
```ini
birthday_john = 15/03/1990,Happy ${years} birthday John!,30 minutes
```

- `${years}` is replaced with `current_year - birth_year`
- `wait_time` is how long to wait with no new track before showing (e.g. "30 minutes", "2 hours")
- Place images in `extra_images/<name>/` (e.g. `extra_images/birthday_john/`)

### Anniversary Display

Visual settings for anniversary notifications.

| Key | Default | Description |
|-----|---------|-------------|
| `font` | *(auto-detected)* | Font for anniversary text. |
| `font_size` | 24 | Anniversary font size in pixels. |
| `border_percent` | 5 | Border around anniversary image as percentage of screen size. |
| `text_percent` | 15 | Height of the text area as percentage of screen height. |

### Thumbnails

| Key | Default | Description |
|-----|---------|-------------|
| `thumbnail_size` | 100 | Size of anniversary image thumbnails in the web UI (pixels). |

## System Tab

### Roon Server

Auto-discovered, read-only.

| Key | Description |
|-----|-------------|
| `ip` | Roon server IP address. |
| `port` | Roon server port. |

### Host System

Read-only system information (IP, WiFi, uptime, memory, disk).

### WiFi Networks

Manage saved WiFi networks on the Pi. Shows currently connected network, allows adding new networks and deleting unused ones. Backed by `/var/lib/dietpi/dietpi-wifi.db`.

## Advanced Tab

### Display

| Key | Default | Description |
|-----|---------|-------------|
| `display_name` | Roon Display | Name shown in Roon's Settings > Extensions. Useful if running multiple displays. |
| `type` | epd13in3E | Display type: `system_display` (tkinter window) or `epd13in3E` (Waveshare e-ink). |
| `tkinter_fullscreen` | false | Fullscreen mode for tkinter display. Ignored by e-ink. |
| `interrupt_on_skip` | true | Cancel an in-progress e-ink render when a new track arrives, instead of waiting for it to finish. |

### Network

| Key | Default | Description |
|-----|---------|-------------|
| `web_config_port` | 8080 | Port for the web configuration UI. |
| `web_config_host` | 0.0.0.0 | Host/IP to bind the web UI to. `0.0.0.0` = all interfaces. |
| `internal_server_port` | 5880 | Port for internal communication between the web UI and the display app. Must differ from `web_config_port`. |
| `internal_server_host` | 127.0.0.1 | Host for the internal server. Usually localhost. |
| `simulation_server_port` | 9999 | Port for the simulation/testing server. |

### Timeouts

| Key | Default | Description |
|-----|---------|-------------|
| `health_script_timeout` | 30 | Maximum time for health check script to run (seconds). |
| `reconnection_interval` | 60 | Base interval between Roon reconnection attempts (seconds). Uses exponential backoff up to 10 minutes. |
| `web_request_timeout` | 5 | Timeout for HTTP requests between the web UI and internal server (seconds). |

### Display Timing

| Key | Default | Description |
|-----|---------|-------------|
| `web_auto_refresh_seconds` | 10 | How often the web UI auto-refreshes the display image (seconds). |
| `anniversary_check_interval` | 60 | How often to check for anniversaries (seconds). |
| `eink_success_threshold` | 15.0 | Minimum expected e-ink render time (seconds). Renders faster than this are flagged as hardware failures. Real renders take ~25s. |
| `preview_debounce_ms` | 500 | Debounce delay before generating a preview after a form change (milliseconds). |
| `loop_time` | 2.5 | Main event loop interval (seconds). Controls how often the app checks for health updates. |

### Monitoring

| Key | Default | Description |
|-----|---------|-------------|
| `log_level` | INFO | Global log level: DEBUG, INFO, WARNING, or ERROR. |
| `performance_logging` | false | Log execution times for slow operations. |
| `health_script` | *(empty)* | Path to a script called on render success/failure. Receives status as arguments. |
| `health_recheck_interval` | 1800 | How often to re-run the health script (seconds). |
