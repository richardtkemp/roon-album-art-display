# Roon Full Art Display

A Python application that displays full-screen album art from your Roon music server on e-ink displays or regular monitors.

## Features

- **Multiple Display Types**: Supports both e-ink displays (Waveshare) and standard system displays
- **Real-time Updates**: Automatically updates when tracks change in Roon
- **Image Processing**: Configurable image enhancements (brightness, contrast, etc.)
- **Zone Filtering**: Support for allowed/forbidden zone lists
- **Robust Connection**: Automatic server discovery with fallback to saved connections

## Project Structure

```
roon_display/
├── config/             # Configuration management
├── viewers/            # Display implementations (e-ink, Tkinter)
├── roon_client/        # Roon API communication
├── image_processing/   # Image manipulation utilities
├── utils.py           # Common utility functions
└── main.py            # Application entry point

tests/                 # Comprehensive test suite
libs/                  # E-ink display drivers (Waveshare)
```

## Installation

### Quick Setup (Recommended)

```bash
# Automatic environment detection and setup
make setup

# Check environment is working
make check-env

# Run quick tests to verify everything works
make test-quick
```

### Manual Setup

#### Development (Mac with pyenv/venv)

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd roon-full-art-display
   ```

2. **The project automatically detects your environment:**
   - ✅ **Virtual Environment**: If `pyvenv.cfg` exists, uses `./bin/python` and `./bin/pip`
   - ✅ **System Python**: Falls back to `python3`/`pip3` or `python`/`pip`
   - ✅ **Cross-platform**: Works on Mac, Linux, and Windows

3. **Install dependencies:**
   ```bash
   # Automatic setup (detects environment)
   make install

   # Or with development tools
   make install-dev
   ```

4. **Verify setup:**
   ```bash
   make check-env
   ```

#### Production (Raspberry Pi)

```bash
# System Python setup
sudo apt update
sudo apt install python3-pip python3-venv
git clone <repository-url>
cd roon-full-art-display
make setup
```

### Environment Detection

The Makefile automatically detects your Python environment:

```bash
# Check what Python/pip will be used
make help
# Shows: Python: ./bin/python, Pip: ./bin/pip

# Detailed environment check
make check-env
```

### Pre-commit Hooks (Development)

```bash
make pre-commit-install
```

## Configuration

The application uses a `roon.cfg` file for configuration. On first run, a default config will be created.

Example configuration:
```ini
[DISPLAY]
type = epd13in3E  # or 'system_display'

[IMAGE_RENDER]
colour_balance_adjustment = 1.0
contrast_adjustment = 1.2
brightness_adjustment = 1.0
sharpness_adjustment = 1.0

[IMAGE_POSITION]
scale_x = 1.0
scale_y = 1.0
rotation = 270
position_offset_x = 0
position_offset_y = 0

[ZONES]
allowed_zone_names = Living Room,Kitchen
forbidden_zone_names = Bedroom
```

## Usage

### Running the Application

```bash
# Run with default configuration
make run

# Or run directly
python -m roon_display.main
```

### Development Commands

```bash
# Run all quality checks and tests
make all

# Individual commands
make test              # Run tests
make lint              # Check code style
make typecheck         # Run type checking
make security          # Security scan
make format            # Format code
make pre-commit        # Run all pre-commit checks
```

## Code Quality

This project uses modern Python development practices:

- **Type Checking**: Full mypy type coverage
- **Code Formatting**: Black for consistent formatting
- **Import Sorting**: isort for organized imports
- **Linting**: flake8 for style and error checking
- **Security**: bandit for vulnerability scanning
- **Testing**: pytest with coverage reporting
- **Pre-commit Hooks**: Automatic quality checks on commit

### Running Quality Checks

```bash
# Check code formatting
make format-check

# Run linting
make lint

# Type checking
make typecheck

# Security scan
make security

# All quality checks
make quality
```

## Testing

Comprehensive test suite with fixtures and mocking:

```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Run specific test file
pytest tests/test_utils.py -v
```

## Hardware Support

### E-ink Displays
- Waveshare 13.3" Spectra 6 (epd13in3E)
- Other Waveshare displays (extend `libs/` directory)

### System Displays
- Any monitor/TV connected to your computer
- Fullscreen Tkinter interface

## Roon Integration

The application connects to your Roon server via:
1. **Automatic Discovery**: Scans network for Roon servers
2. **Saved Configuration**: Remembers server details between runs
3. **Zone Filtering**: Only responds to specified zones
4. **Real-time Events**: Updates on track changes

## Troubleshooting

### Common Issues

1. **Connection Failed**: Ensure Roon server is running and accessible
2. **Authorization Required**: Approve the extension in Roon settings
3. **No Image Display**: Check zone configuration and track has album art
4. **E-ink Issues**: Verify hardware connections and driver installation

### Logging

The application provides detailed logging. Check console output for:
- Connection status
- Image processing steps
- Error messages
- Performance metrics

### Development

To contribute or modify:

1. **Install development dependencies:**
   ```bash
   make install-dev
   ```

2. **Set up pre-commit hooks:**
   ```bash
   make pre-commit-install
   ```

3. **Run quality checks before committing:**
   ```bash
   make all
   ```

4. **Add tests for new features:**
   ```bash
   # Create test file in tests/
   pytest tests/test_new_feature.py -v
   ```

## File Structure

- `roon_display/` - Main application package
- `tests/` - Test suite with fixtures and mocks
- `libs/` - Hardware drivers (excluded from linting/formatting)
- `logs/` - Application logs
- `album_art/` - Cached album art images
- Configuration files: `roon.cfg`, `pyproject.toml`, `.flake8`, etc.

## License

[Add your license information here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make all` to ensure quality
5. Submit a pull request

---

This project follows Python best practices and is suitable for both hobbyist and professional development.
