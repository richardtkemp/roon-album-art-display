# Testing Guide

This document describes the comprehensive testing setup for the Roon Full Art Display project.

## Test Structure

```
tests/
├── conftest.py           # Pytest fixtures and configuration
├── test_utils.py         # Utility function tests
├── test_config_manager.py # Configuration management tests
├── test_image_processor.py # Image processing tests
├── test_viewers.py       # Display viewer tests
├── test_roon_client.py   # Roon API client tests
├── test_main.py          # Main application tests
└── test_integration.py   # Integration tests
```

## Running Tests

### Quick Start

```bash
# Install dependencies and run all tests
make test-install

# Run all tests with coverage
make test

# Run quick tests only (no integration)
make test-quick

# Run comprehensive test suite
make test-runner
```

### Individual Test Commands

```bash
# Basic test run
pytest

# With coverage report
pytest --cov=roon_display --cov-report=html

# Specific test file
pytest tests/test_utils.py -v

# Specific test function
pytest tests/test_utils.py::TestUtilityFunctions::test_get_root_dir -v

# Run tests matching pattern
pytest -k "test_config" -v
```

## Code Quality Checks

### Automated Quality Checks

```bash
# Run all quality checks
make quality

# Individual checks
make lint          # flake8 linting
make typecheck     # mypy type checking
make security      # bandit security scan
make format-check  # black/isort formatting check
```

### Manual Code Formatting

```bash
# Auto-format code
make format

# Check formatting without changes
make format-check
```

## Test Categories

### Unit Tests
- **Utils Tests**: File operations, path handling
- **Config Tests**: Configuration loading, validation, persistence
- **Image Processor Tests**: Image manipulation, enhancement, positioning
- **Viewer Tests**: E-ink and Tkinter display handling
- **Roon Client Tests**: API communication, event handling, zone filtering

### Integration Tests
- Component interaction testing
- Configuration propagation
- Error handling across modules
- Threading behavior
- Memory management

## Test Fixtures

Located in `tests/conftest.py`:

- `temp_dir`: Temporary directory for file operations
- `sample_config`: Pre-configured test configuration
- `config_manager`: ConfigManager instance with test config
- `sample_image`: PIL Image for image processing tests
- `mock_roon_api`: Mock Roon API for client testing
- `mock_eink_module`: Mock e-ink hardware module

## Mocking Strategy

### External Dependencies
- **RoonAPI**: Mocked for client testing
- **PIL/Pillow**: Real implementation for image processing
- **File I/O**: Temporary files and directories
- **Threading**: Real threads with proper cleanup
- **Network Requests**: Mocked with realistic responses

### Hardware Dependencies
- **E-ink Displays**: Fully mocked hardware interfaces
- **Tkinter**: Mocked GUI components

## Coverage Requirements

- **Minimum Coverage**: 85%
- **Target Coverage**: 90%+
- **Critical Paths**: 100% (error handling, configuration)

Current coverage includes:
- All public methods and functions
- Error handling paths
- Configuration validation
- Image processing pipelines
- Threading scenarios

## Performance Testing

### Image Processing Performance
- Large image handling (2000x1500 pixels)
- Memory usage validation
- Processing time benchmarks

### Threading Performance
- Concurrent update handling
- Thread safety validation
- Resource cleanup verification

## Continuous Integration

### Pre-commit Hooks
```bash
# Install pre-commit hooks
make pre-commit-install

# Run manually
make pre-commit
```

Hooks include:
- Code formatting (black, isort)
- Linting (flake8)
- Type checking (mypy)
- Security scanning (bandit)
- Basic file checks

### Quality Gates
All of these must pass:
1. ✅ All tests pass
2. ✅ Code coverage > 85%
3. ✅ No linting errors
4. ✅ No type checking errors
5. ✅ No security vulnerabilities
6. ✅ Code is properly formatted

## Test Data

### Sample Images
- RGB images for processing tests
- Various sizes for scaling tests
- Different formats for compatibility tests

### Configuration Files
- Valid configurations for all components
- Invalid configurations for error testing
- Edge cases and boundary conditions

### Mock Responses
- Realistic Roon API responses
- Error scenarios and timeouts
- Various zone configurations

## Debugging Tests

### Verbose Output
```bash
# Detailed test output
pytest -v -s

# Show local variables on failure
pytest --tb=long

# Stop on first failure
pytest -x
```

### Test Isolation
```bash
# Run single test file
pytest tests/test_utils.py

# Run tests in parallel (if installed pytest-xdist)
pytest -n auto
```

### Mock Inspection
```bash
# Debug mode for understanding mock calls
pytest -v --capture=no tests/test_roon_client.py
```

## Adding New Tests

### Test File Template
```python
"""Tests for new_module."""
import pytest
from unittest.mock import Mock, patch

from roon_display.new_module import NewClass


class TestNewClass:
    """Test NewClass functionality."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        instance = NewClass()
        result = instance.method()
        assert result is not None
```

### Best Practices
1. **One test per behavior**
2. **Descriptive test names**
3. **Arrange-Act-Assert pattern**
4. **Proper mock cleanup**
5. **Edge case coverage**
6. **Error condition testing**

## Common Issues

### Import Errors
- Ensure `PYTHONPATH` includes project root
- Check virtual environment activation
- Verify all dependencies installed

### Mock Issues
- Use `patch` context managers for cleanup
- Mock at the right level (where imported, not defined)
- Reset mocks between tests

### Threading Issues
- Always join threads in tests
- Use timeouts to prevent hanging
- Proper cleanup in fixtures

### File System Issues
- Use `temp_dir` fixture for file operations
- Clean up created files/directories
- Handle permission errors gracefully

## Test Metrics

Run `make test-coverage` to see detailed coverage report:
- Line coverage by module
- Missing lines identification
- Branch coverage analysis
- HTML report generation

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure all quality checks pass
3. Update integration tests if needed
4. Document any new test patterns
5. Maintain or improve coverage percentage

For questions about testing, see the main README.md or create an issue.
