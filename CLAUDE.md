DONT TELL ME I'M RIGHT WHEN I'm JUST MAKING A VALUE JUDGEMENT
ALWAYS think about whether what I suggest or you choose to do is best practice. If I suggest bad practice, tell me and offer some other options.

# Claude Development Notes

## Project Overview
This is a Python application that displays full-screen album art from a Roon music server on e-ink displays or regular monitors.

## Essential Reading
**ALWAYS read these documents first when working on this project:**
- `README.md` - Project overview, installation, configuration, usage
- `TESTING.md` - Comprehensive testing guide, test structure, quality tools

**Important:** Update these documents whenever you make changes to:
- Project structure or architecture
- Installation procedures or dependencies
- Testing approach or tools
- Configuration options
- Usage instructions

## Current Development Status

### Test Suite (200 tests passing)
| File | Tests |
|---|---|
| test_utils.py | 10 |
| test_config_manager.py | 27 |
| test_image_processor.py | 29 |
| test_time_utils.py | 17 |
| test_health.py | 16 |
| test_viewers.py | 34 |
| test_roon_client.py | 41 |
| test_main.py | 15 |
| test_integration.py | 11 |

### Code Quality Setup
- **Environment Detection**: Makefile automatically detects virtual env vs system Python
- **Formatting**: Black (run before flake8)
- **Linting**: flake8 with Black compatibility
- **Type Checking**: mypy with strict settings
- **Security**: bandit vulnerability scanning
- **Pre-commit**: Automated quality checks

## Key Architectural Decisions

### Project Structure (Refactored from Monolithic)
```
roon_display/                 # Main package
├── config/                  # Configuration management
├── viewers/                 # Display implementations
├── roon_client/            # Roon API communication
├── image_processing/       # Image manipulation
├── web/                    # Web UI (Flask app, config handler, templates)
├── anniversary.py          # Anniversary tracking
├── health.py               # Health monitoring
├── internal_server.py      # Internal HTTP server
├── message_renderer.py     # On-screen message rendering
├── render_coordinator.py   # Coordinates display rendering
├── simulation.py           # Simulation/demo mode
├── standalone.py           # Standalone image display mode
├── time_utils.py           # Time/date utilities
├── utils.py                # Common utilities
├── web_config.py           # Web configuration bridge
└── main.py                 # Application entry point
```

### Testing Strategy
- **Isolated Testing**: Test each module independently
- **Comprehensive Mocking**: External dependencies (Roon API, hardware, file I/O)
- **Coverage Requirements**: 85% minimum, targeting 90%+
- **Quality Gates**: All tests + linting + type checking must pass

## Environment Setup
- **Development**: Mac with pyenv/venv (automatically detected)
- **Production**: Raspberry Pi with system Python
- **Commands**: `make setup`, `make check-env`, `make test-quick`
- **Local Development Python**: Always use `./bin/python` (not `python` or `python3`) to ensure virtual environment is used

## Important TODOs
- [ ] Validate all quality checks pass
- [ ] Performance testing on Raspberry Pi

## Development Workflow
1. Read README.md and TESTING.md for context
2. Use `make check-env` to verify environment
3. Run `make test-quick` for fast feedback
4. Use `make format` before `make lint` (auto-format first)
5. Update documentation when making structural changes

## Production Startup
- **start_display.sh**: Updated to use new modular code (`roon_display.main`)
- **Environment**: Sets `EINK_SUCCESS_THRESHOLD=12.0` for production hardware monitoring
- **Virtual Environment**: Automatically detects and uses `./bin/python` if available
- **Logging**: Continues to use timestamped log files in `logs/` directory

## Notes for Future Development
- The original monolithic `display.py` has been refactored into a modular architecture
- All tests use proper fixtures and mocking
- Environment detection works across Mac/Linux/Windows
- Pre-commit hooks enforce quality standards
- Type hints are comprehensive throughout
