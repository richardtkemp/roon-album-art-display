"""Health monitoring and script execution for the Roon display application."""

import logging
import os
import stat
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HealthManager:
    """Manages health status tracking and script execution."""

    def __init__(
        self,
        config_manager,
        health_script_path: Optional[str] = None,
        recheck_interval_seconds: Optional[int] = None,
    ):
        """Initialize health manager with config manager and optional overrides."""
        self.config_manager = config_manager

        # Use provided path or get from config
        script_path = health_script_path or config_manager.get_health_script()
        self.health_script_path = self._resolve_script_path(script_path)

        # Use provided interval or get from config
        interval_seconds = (
            recheck_interval_seconds or config_manager.get_health_recheck_interval()
        )
        self.recheck_interval = timedelta(seconds=interval_seconds)

        self.last_timestamp = None
        self.last_params = None

        logger.info(
            f"HealthManager initialized with script: {self.health_script_path}, recheck interval: {interval_seconds}s"
        )

    def _resolve_script_path(self, script_path: Optional[str]) -> Optional[str]:
        """Resolve script path, making relative paths relative to project root."""
        if not script_path:
            return None

        path = Path(script_path)

        # If absolute path, use as-is
        if path.is_absolute():
            return str(path)

        # For relative paths, resolve relative to current working directory
        # This assumes the application is run from the project root
        resolved_path = Path.cwd() / path
        return str(resolved_path)

    def call_health_script(self, status: str, additional_info: str) -> bool:
        """Call the health script with status and additional info.

        Args:
            status: "good" or "bad"
            additional_info: Additional information about the health status

        Returns:
            True if script executed successfully, False otherwise
        """
        if not self.health_script_path:
            logger.debug("No health script configured, skipping health call")
            return False

        # Update tracked status
        self.last_timestamp = datetime.now()
        self.last_params = (status, additional_info)

        try:
            # Check if script exists and make it executable if needed
            script_path = Path(self.health_script_path)
            if not script_path.exists():
                logger.error(f"Health script not found: {self.health_script_path}")
                return False

            # Check if script is executable, make it executable if not
            if not os.access(script_path, os.X_OK):
                logger.info(
                    f"Health script is not executable, making it executable: {script_path}"
                )
                try:
                    # Add execute permission for owner, group, and others
                    current_permissions = script_path.stat().st_mode
                    new_permissions = (
                        current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                    )
                    script_path.chmod(new_permissions)
                    logger.info(f"Successfully made health script executable")
                except Exception as e:
                    logger.error(f"Failed to make health script executable: {e}")
                    return False

            # Execute the health script with the parameters
            cmd = [self.health_script_path, status, additional_info]

            timeout = self.config_manager.get_health_script_timeout()
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )

            if result.returncode == 0:
                logger.debug(
                    f"Health script executed successfully: {result.stdout.strip()}"
                )
                return True
            else:
                logger.warning(
                    f"Health script failed with return code {result.returncode}: {result.stderr.strip()}"
                )
                return False

        except subprocess.TimeoutExpired:
            timeout = self.config_manager.get_health_script_timeout()
            logger.error(f"Health script timed out after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error executing health script: {e}")
            return False

    def report_render_success(
        self, additional_info: str = "Display render completed successfully"
    ):
        """Report successful render to health script."""
        return self.call_health_script("good", additional_info)

    def report_render_failure(self, additional_info: str = "Display render failed"):
        """Report render failure to health script."""
        return self.call_health_script("bad", additional_info)

    def should_recheck_health(self) -> bool:
        """Check if it's time to re-call the health script (configurable interval)."""
        if not self.health_script_path or not self.last_timestamp:
            return False

        time_since_last = datetime.now() - self.last_timestamp
        return time_since_last >= self.recheck_interval

    def recheck_health(self) -> bool:
        """Re-call health script with the same parameters as last time."""
        if not self.should_recheck_health() or not self.last_params:
            return False

        interval_minutes = self.recheck_interval.total_seconds() / 60
        logger.info(
            f"Re-checking health status ({interval_minutes:.0f}+ minutes since last call)"
        )
        status, additional_info = self.last_params
        return self.call_health_script(status, additional_info)
