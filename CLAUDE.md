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

### Testing Progress (Phase-by-Phase Approach)
- ✅ **Phase 1**: Utils (10/10 tests) - 100% coverage
- ✅ **Phase 2**: Config Manager (15/15 tests) - 100% coverage
- ✅ **Phase 3**: Image Processing (29/29 tests) - 95% coverage
- 🔄 **Phase 4**: Base Viewer Tests (next)
- ⏳ **Phase 5**: Individual Viewer Implementations
- ⏳ **Phase 6**: Roon Client (Most Complex)
- ⏳ **Phase 7**: Main Application & Integration

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
├── utils.py               # Common utilities
└── main.py                # Application entry point
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

## Important TODOs
- [ ] **Image Processing Optimization**: Remove potentially unnecessary `img.copy()` in `apply_enhancements()` method after testing complete (see TODO in processor.py line 144-146)
- [ ] Complete remaining test phases
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
