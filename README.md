# Roon Full Art Display

Displays full-screen album art from a Roon music server on a Waveshare e-ink display (or a regular monitor for development).

## What It Does

- Connects to your Roon server and shows the currently playing album art
- Configurable image processing (brightness, contrast, colour, sharpness, scaling, rotation)
- Web UI for configuration with live preview
- Overlay messages when connection is lost or the server is down
- Anniversary notifications with custom images and messages
- WiFi network management from the web UI (DietPi)
- Health monitoring with external script integration
- Simulation server for testing without Roon

## Hardware

- Raspberry Pi (tested on Pi Zero 2 W with DietPi)
- Waveshare 13.3" Spectra 6 e-ink display (epd13in3E)
- Any monitor/TV via Tkinter for development

## Setup

### DietPi (Production)

```bash
# Clone
cd /mnt/dietpi_userdata
GIT_SSH=dbclient git clone git@github.com:richardtkemp/roon-album-art-display.git
cd roon-album-art-display

# Install dependencies and configure services
bash dietpi-setup.sh
```

This installs system packages, sets up systemd services, and starts the application. After starting, approve the "Album Art Display" extension in Roon Settings > Extensions.

The web UI is available at `http://<pi-ip>:8080`.

### Development (Mac/Linux)

```bash
git clone git@github.com:richardtkemp/roon-album-art-display.git
cd roon-full-art-display
make setup
make check-env
make test-quick
```

Run with `make run` or `python -m roon_display.main`. Uses a Tkinter window instead of e-ink.

### Standalone Image Display

Display a single image without Roon:

```bash
python -m roon_display.main --image /path/to/image.jpg
python -m roon_display.main --image /path/to/images/  # random from directory
```

## Configuration

All settings are in `roon.cfg` (auto-created on first run) and editable via the web UI at `http://<pi-ip>:8080`.

See [docs/CONFIG.md](docs/CONFIG.md) for the full configuration reference.

## Architecture

Two processes run on the Pi:

- **Display app** — connects to Roon, processes images, drives the e-ink display
- **Web config** — serves the configuration UI, proxies to the display app

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details on the render pipeline, overlay system, connection handling, and preview mechanism.

## Project Structure

```
roon_display/
├── config/              # Configuration schema and management
├── viewers/             # Display drivers (e-ink, Tkinter)
├── roon_client/         # Roon API connection and events
├── image_processing/    # Image load, scale, rotate, enhance
├── web/                 # Web UI (Flask app, config handler, WiFi, templates)
├── main.py              # Application entry point
├── render_coordinator.py # Two-stage prepare/render pipeline
├── message_renderer.py  # Overlay and text rendering
├── anniversary.py       # Anniversary tracking and display
├── health.py            # Health script integration
├── internal_server.py   # HTTP server for web UI communication
└── simulation.py        # Test server for simulating tracks

tests/                   # Test suite (pytest)
libs/                    # E-ink display drivers (Waveshare)
docs/                    # Configuration and architecture docs
```

## Development

```bash
make format        # Format code (Black + isort)
make lint          # Lint (flake8)
make typecheck     # Type check (mypy)
make security      # Security scan (bandit)
make test-quick    # Run tests + lint + typecheck + security
make all           # Everything
```

Pre-commit hooks enforce formatting, linting, type checking, and security scanning on every commit.

## Services

| Service | Description |
|---|---|
| `roon-album-art-display` | Main display application |
| `roon-web-config` | Web configuration UI |
| `space-cleaner` | Periodic disk cleanup (timer) |

```bash
systemctl restart roon-album-art-display
systemctl restart roon-web-config
journalctl -u roon-album-art-display -f  # follow logs
```
