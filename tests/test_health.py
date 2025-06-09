"""Tests for health monitoring functionality."""

import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from roon_display.health import HealthManager


class TestHealthManager:
    """Test cases for HealthManager."""

    def test_init_without_script(self):
        """Test initialization without health script."""
        health_manager = HealthManager()
        assert health_manager.health_script_path is None
        assert health_manager.last_status is None
        assert health_manager.last_timestamp is None
        assert health_manager.last_params is None
        assert health_manager.recheck_interval == timedelta(seconds=1800)

    def test_init_with_script_and_custom_interval(self):
        """Test initialization with health script and custom interval."""
        script_path = "/path/to/script.sh"
        interval = 3600  # 1 hour
        health_manager = HealthManager(script_path, interval)
        assert health_manager.health_script_path == script_path
        assert health_manager.recheck_interval == timedelta(seconds=interval)

    def test_call_health_script_no_script_configured(self):
        """Test calling health script when none configured."""
        health_manager = HealthManager()
        result = health_manager.call_health_script("good", "test info")
        assert result is False

    @patch("subprocess.run")
    def test_call_health_script_success(self, mock_run):
        """Test successful health script execution."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Script executed successfully"
        mock_run.return_value = mock_result

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            script_path = f.name
            f.write('#!/bin/bash\necho "Script executed successfully"')

        try:
            health_manager = HealthManager(script_path)
            result = health_manager.call_health_script("good", "test info")

            assert result is True
            assert health_manager.last_status == "good"
            assert health_manager.last_params == ("good", "test info")
            assert health_manager.last_timestamp is not None

            # Verify subprocess was called correctly
            mock_run.assert_called_once_with(
                [script_path, "good", "test info"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            Path(script_path).unlink()

    @patch("subprocess.run")
    def test_call_health_script_failure(self, mock_run):
        """Test health script execution failure."""
        # Setup mock for failed execution
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Script failed"
        mock_run.return_value = mock_result

        health_manager = HealthManager("/path/to/script.sh")
        result = health_manager.call_health_script("bad", "error info")

        assert result is False
        # Status should still be tracked even on failure
        assert health_manager.last_status == "bad"
        assert health_manager.last_params == ("bad", "error info")

    @patch("subprocess.run")
    def test_call_health_script_timeout(self, mock_run):
        """Test health script timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        health_manager = HealthManager("/path/to/script.sh")
        result = health_manager.call_health_script("good", "test info")

        assert result is False

    @patch("subprocess.run")
    def test_call_health_script_file_not_found(self, mock_run):
        """Test health script file not found."""
        mock_run.side_effect = FileNotFoundError()

        health_manager = HealthManager("/nonexistent/script.sh")
        result = health_manager.call_health_script("good", "test info")

        assert result is False

    def test_report_render_success(self):
        """Test reporting render success."""
        health_manager = HealthManager()
        with patch.object(health_manager, "call_health_script") as mock_call:
            mock_call.return_value = True
            result = health_manager.report_render_success("Custom success message")

            assert result is True
            mock_call.assert_called_once_with("good", "Custom success message")

    def test_report_render_failure(self):
        """Test reporting render failure."""
        health_manager = HealthManager()
        with patch.object(health_manager, "call_health_script") as mock_call:
            mock_call.return_value = True
            result = health_manager.report_render_failure("Custom failure message")

            assert result is True
            mock_call.assert_called_once_with("bad", "Custom failure message")

    def test_should_recheck_health_no_script(self):
        """Test should_recheck_health with no script configured."""
        health_manager = HealthManager()
        assert health_manager.should_recheck_health() is False

    def test_should_recheck_health_no_previous_call(self):
        """Test should_recheck_health with no previous call."""
        health_manager = HealthManager("/path/to/script.sh")
        assert health_manager.should_recheck_health() is False

    def test_should_recheck_health_too_soon(self):
        """Test should_recheck_health when called too soon."""
        health_manager = HealthManager("/path/to/script.sh", 3600)  # 1 hour
        health_manager.last_timestamp = datetime.now()
        assert health_manager.should_recheck_health() is False

    def test_should_recheck_health_time_passed(self):
        """Test should_recheck_health when enough time has passed."""
        health_manager = HealthManager("/path/to/script.sh", 60)  # 1 minute
        health_manager.last_timestamp = datetime.now() - timedelta(seconds=61)
        assert health_manager.should_recheck_health() is True

    def test_recheck_health_not_needed(self):
        """Test recheck_health when not needed."""
        health_manager = HealthManager()
        result = health_manager.recheck_health()
        assert result is False

    def test_recheck_health_success(self):
        """Test successful recheck_health."""
        health_manager = HealthManager("/path/to/script.sh", 60)
        health_manager.last_timestamp = datetime.now() - timedelta(seconds=61)
        health_manager.last_params = ("good", "previous message")

        with patch.object(health_manager, "call_health_script") as mock_call:
            mock_call.return_value = True
            result = health_manager.recheck_health()

            assert result is True
            mock_call.assert_called_once_with("good", "previous message")


class TestHealthManagerIntegration:
    """Integration tests for HealthManager."""

    def test_full_workflow(self):
        """Test complete health manager workflow."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            script_path = f.name
            f.write('#!/bin/bash\necho "Health check: $1 - $2"')

        try:
            # Make script executable
            Path(script_path).chmod(0o755)

            health_manager = HealthManager(script_path, 1)  # 1 second interval

            # First call
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result

                result = health_manager.report_render_success("First render")
                assert result is True
                assert health_manager.last_status == "good"

            # Wait a bit and check recheck
            time.sleep(1.1)
            assert health_manager.should_recheck_health() is True

            # Recheck
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result

                result = health_manager.recheck_health()
                assert result is True

        finally:
            Path(script_path).unlink()
