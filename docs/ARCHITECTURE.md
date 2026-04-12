# Architecture

## System Overview

The application runs as two separate processes on a Raspberry Pi (DietPi):

```
Browser ──> Web Config (Flask, port 8080) ──> Internal Server (Flask, port 5880) ──> Display App
                                                                                       │
                                                                          Roon Server <─┘
                                                                               │
                                                                          E-ink Display
```

**Display App** (`roon_display.main`) — connects to Roon, receives track events, renders album art to the e-ink display. Runs the internal server for communication with the web UI.

**Web Config** (`roon_display.web.app`) — serves the configuration web UI. Proxies image/preview/status requests to the display app's internal server.

Both are managed by systemd (`roon-album-art-display.service`, `roon-web-config.service`).

## Display App Internals

### Startup Sequence

1. Load config from `roon.cfg`
2. Create viewer (e-ink or tkinter)
3. Create render coordinator (starts prepare + render worker threads)
4. Initialize display state from disk (last-displayed image key)
5. Populate web image cache from disk
6. Start internal server (Flask, background thread)
7. Start simulation server (TCP, background thread)
8. Start Roon connection loop (background thread)

### Render Pipeline

Two-stage pipeline with dedup and cancellation:

```
set_art() ──> [incoming slot] ──> prepare-loop ──> [prepared slot] ──> render-loop ──> viewer.render()
                                      │                                    │
                                  prepare()                          _composite()
                                  (load, scale,                     (overlay badge)
                                   rotate, enhance)                      │
                                                                   _cache_for_web()
```

**Stage 1 — Prepare Loop** (`_prepare_loop`): Takes `RenderTarget` from the incoming slot, runs `ImageProcessor.prepare()` to produce a display-ready canvas. Stale targets (superseded before prepare completes) are discarded.

**Stage 2 — Render Loop** (`_render_loop`): Takes prepared images, composites any overlay, caches for the web UI, then sends to the viewer. Dedup skips re-rendering the same image unless forced.

Both stages use `LatestSlot` — a single-item buffer where new values overwrite old ones. This means rapid track changes only render the latest, not a queue.

### Dedup

`_displayed_key` tracks what's currently on the physical display. `_last_rendered_target` tracks the last art target for preview use. These are separate because overlay-only renders clear the display key (so the next art isn't skipped) but keep the target (so preview still works).

### Overlay System

When the app needs to show a message (connection lost, searching for server), it composites a small badge onto the bottom-right corner of the album art:

- `set_overlay(message)` — idempotent, only triggers render if message changes
- Overlay is sized relative to the album art bounds (not the full display canvas)
- `create_error_overlay()` renders text with configurable font, size, margin
- During preview, font errors raise to the web UI; during normal rendering, falls back to default font

### Connection Handling

`connect_loop()` handles both initial connection and reconnection with exponential backoff (configured interval, doubling up to 10 minutes). On connection loss, `_handle_connection_failure()` cleans up the dead Roon object and transitions to `connect_loop()`.

`_monitor_connection` runs every 10 seconds, checking socket state. On failure, it sets an overlay and triggers reconnection.

### Cancellation

When `interrupt_on_skip` is enabled and a new track arrives during an e-ink render (~25s), the current render is cancelled:

1. `set_art()` calls `viewer.cancel()` which sets a threading event
2. The EPD driver checks the event at cancellation points (BUSY pin polls, SPI loops, buffer packing)
3. `RenderCancelledError` is raised, caught by `render()`, which calls `Reset()` and re-raises
4. The render loop catches it and picks up the next prepared item

## Configuration

### Schema-Driven

`CONFIG_SCHEMA` in `config_manager.py` is the single source of truth. It defines:
- Default values and types
- Input constraints (min/max/step/options)
- Web UI metadata (input_type, comments)

### Auto-Generated Getters

Getters follow `get_{section}_{field}()` convention (e.g. `get_overlay_font_size()`). Generated at import time by `_generate_getter_methods()`. Fields with explicit `getter_name` override the default. Manual getters on `ConfigManager` are never overridden.

### Preview Overrides

`config_manager.preview_overrides(config_data)` is a context manager using `threading.local`. While active, all `get_X()` calls check the overrides dict before reading the config file. This means any code that reads config via getters automatically respects web form changes during preview — no explicit override plumbing needed.

## Web UI

### Architecture

The web config app is a separate Flask process. It communicates with the display app via HTTP:

| Web UI Route | Internal Server Route | Purpose |
|---|---|---|
| `/current-display-image` | `/current-image` | Current display image |
| `/display-status` | `/current-status` | Track info, connection state |
| `/preview-image` (POST) | `/preview` (POST) | Preview with config changes |
| `/apply` (POST) | `/update-config` (POST) | Save config changes |

### Preview Flow

1. User changes a form field
2. JS debounces, then POSTs form data to `/preview-image`
3. Web app parses form data, forwards to internal server `/preview`
4. `render_preview()` enters `preview_overrides()` context, re-prepares image with overrides
5. Returns image or error string
6. Browser shows the preview image (or error overlay on failure)

### WiFi Management

The web UI reads/writes `/var/lib/dietpi/dietpi-wifi.db` directly and applies changes via `/boot/dietpi/func/dietpi-wifidb`.

## Key Files

| File | Purpose |
|---|---|
| `roon_display/main.py` | Application entry point |
| `roon_display/config/config_manager.py` | Config schema, loading, getters |
| `roon_display/render_coordinator.py` | Two-stage render pipeline |
| `roon_display/image_processing/processor.py` | Image load, scale, rotate, enhance |
| `roon_display/message_renderer.py` | Overlay and text rendering |
| `roon_display/roon_client/client.py` | Roon API connection and events |
| `roon_display/viewers/eink_viewer.py` | E-ink display driver wrapper |
| `roon_display/viewers/tk_viewer.py` | Tkinter display for development |
| `roon_display/internal_server.py` | Flask server inside display app |
| `roon_display/web/app.py` | Web config UI (separate process) |
| `roon_display/web/wifi.py` | WiFi network management |
| `roon_display/anniversary.py` | Anniversary date tracking and display |
| `roon_display/health.py` | Health script integration |
| `roon_display/simulation.py` | Test server for simulating track changes |
| `libs/epd13in3E.py` | Waveshare EPD hardware driver |
