#!/usr/bin/env python3
"""
Environment setup script for the Roon Display project.
Works on both development (Mac with pyenv) and production (Raspberry Pi) environments.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def run_command(cmd: List[str], description: str, check: bool = True) -> bool:
    """Run a command and return success status."""
    print(f"📦 {description}")
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        if result.stdout.strip():
            print(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed: {e}")
        if e.stdout:
            print(f"   Stdout: {e.stdout}")
        if e.stderr:
            print(f"   Stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"   ❌ Command not found: {cmd[0]}")
        return False


def detect_environment() -> Dict[str, Any]:
    """Detect the current environment setup."""
    env_info: Dict[str, Any] = {
        "platform": platform.system(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "has_venv": Path("pyvenv.cfg").exists(),
        "in_venv": hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix),
        "venv_python": None,
        "venv_pip": None,
    }

    if env_info["has_venv"]:
        if platform.system() == "Windows":
            venv_python = Path("Scripts/python.exe")
            venv_pip = Path("Scripts/pip.exe")
        else:
            venv_python = Path("bin/python")
            venv_pip = Path("bin/pip")

        env_info["venv_python"] = str(venv_python) if venv_python.exists() else None
        env_info["venv_pip"] = str(venv_pip) if venv_pip.exists() else None

    return env_info


def get_python_pip() -> Tuple[str, str]:
    """Get the correct Python and pip executables."""
    env = detect_environment()

    if env["venv_python"] and env["venv_pip"]:
        return str(env["venv_python"]), str(env["venv_pip"])

    python_cmd = (
        "python3"
        if subprocess.run(["which", "python3"], capture_output=True).returncode == 0
        else "python"
    )
    pip_cmd = (
        "pip3"
        if subprocess.run(["which", "pip3"], capture_output=True).returncode == 0
        else "pip"
    )

    return python_cmd, pip_cmd


def main() -> int:
    """Main setup function."""
    print("🚀 Roon Display Environment Setup")
    print("=" * 50)

    env = detect_environment()
    print(f"🖥️  Platform: {env['platform']}")
    print(f"🐍 Python: {env['python_executable']}")
    print(f"📦 Virtual Environment: {'Yes' if env['has_venv'] else 'No'}")
    print(f"🔗 In Virtual Environment: {'Yes' if env['in_venv'] else 'No'}")
    print()

    python_cmd, pip_cmd = get_python_pip()
    print(f"🔧 Using Python: {python_cmd}")
    print(f"🔧 Using Pip: {pip_cmd}")
    print()

    if not run_command(
        [python_cmd, "-m", "pip", "install", "--upgrade", "pip"],
        "Upgrading pip",
        check=False,
    ):
        print("⚠️  Pip upgrade failed, continuing anyway...")

    if not run_command(
        [pip_cmd, "install", "-r", "requirements.txt"], "Installing dependencies"
    ):
        print("❌ Failed to install dependencies")
        return 1

    print("\n🧪 Verifying installation...")
    if run_command(
        [
            python_cmd,
            "-c",
            'import roon_display; print("✅ Package imports successfully")',
        ],
        "Testing package import",
        check=False,
    ):
        print("✅ Package verification successful")
    else:
        print("⚠️  Package import test failed - you may need to run with PYTHONPATH=.")

    if run_command(
        [python_cmd, "-m", "pytest", "--version"], "Checking pytest", check=False
    ):
        print("✅ Test framework ready")
    else:
        print("⚠️  pytest not available")

    print("\n🎉 Environment setup complete!")
    print("\nNext steps:")
    print("  make check-env     # Verify environment")
    print("  make test-quick    # Run quick tests")
    print("  make help          # See all available commands")

    return 0


if __name__ == "__main__":
    sys.exit(main())
