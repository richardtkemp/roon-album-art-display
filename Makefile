.PHONY: help install test lint format typecheck security clean all pre-commit

# Auto-detect Python environment
# Check for virtual environment first, then fall back to system python
PYTHON := $(shell \
	if [ -f pyvenv.cfg ] && [ -f bin/python ]; then \
		echo "./bin/python"; \
	elif [ -f pyvenv.cfg ] && [ -f Scripts/python.exe ]; then \
		echo "./Scripts/python.exe"; \
	elif command -v python3 >/dev/null 2>&1; then \
		echo "python3"; \
	else \
		echo "python"; \
	fi)

PIP := $(shell \
	if [ -f pyvenv.cfg ] && [ -f bin/pip ]; then \
		echo "./bin/pip"; \
	elif [ -f pyvenv.cfg ] && [ -f Scripts/pip.exe ]; then \
		echo "./Scripts/pip.exe"; \
	elif command -v pip3 >/dev/null 2>&1; then \
		echo "pip3"; \
	else \
		echo "pip"; \
	fi)

help:  ## Show this help message
	@echo "Available commands:"
	@echo "Python: $(PYTHON)"
	@echo "Pip: $(PIP)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## Set up development environment automatically
	$(PYTHON) setup_env.py

check-env:  ## Check Python environment
	@echo "🐍 Python Environment Check"
	@echo "=========================="
	@echo "Python executable: $(PYTHON)"
	@echo "Pip executable: $(PIP)"
	@echo "Python version: $$($(PYTHON) --version)"
	@echo "Pip version: $$($(PIP) --version)"
	@echo "Virtual env: $$(if [ -f pyvenv.cfg ]; then echo 'Yes (pyvenv.cfg found)'; else echo 'No'; fi)"
	@echo "Working directory: $$(pwd)"

install:  ## Install dependencies
	$(PIP) install -r requirements.txt

install-dev:  ## Install development dependencies
	$(PIP) install -e ".[dev]"

test:  ## Run tests
	$(PYTHON) -m pytest

test-verbose:  ## Run tests with verbose output
	$(PYTHON) -m pytest -v

test-coverage:  ## Run tests with coverage report
	$(PYTHON) -m pytest --cov=roon_display --cov-report=html --cov-report=term

lint:  ## Run linting (flake8)
	$(PYTHON) -m flake8 roon_display tests

format:  ## Format code with black and isort
	$(PYTHON) -m black roon_display tests
	$(PYTHON) -m isort roon_display tests

format-check:  ## Check if code is formatted correctly
	$(PYTHON) -m black --check roon_display tests
	$(PYTHON) -m isort --check-only roon_display tests

typecheck:  ## Run type checking with mypy
	$(PYTHON) -m mypy roon_display

security:  ## Run security scan with bandit
	$(PYTHON) -m bandit -r roon_display

quality: lint typecheck security  ## Run all quality checks

pre-commit-install:  ## Install pre-commit hooks
	$(PYTHON) -m pre_commit install

pre-commit:  ## Run pre-commit on all files
	$(PYTHON) -m pre_commit run --all-files

clean:  ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/

all: format quality test  ## Run formatting, quality checks, and tests

run:  ## Run the application
	$(PYTHON) -m roon_display.main

run-test-config:  ## Run with test configuration
	PYTHONPATH=. $(PYTHON) -m roon_display.main

test-runner:  ## Run comprehensive test suite with quality checks
	$(PYTHON) run_tests.py

test-quick:  ## Run quick tests only
	$(PYTHON) run_tests.py --quick

test-install:  ## Install dependencies and run all tests
	$(PYTHON) run_tests.py --install
