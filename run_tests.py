#!/usr/bin/env python3
"""
Test runner script for the Roon Display project.
Provides comprehensive testing with various options.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def run_command(cmd: List[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    except FileNotFoundError:
        print(f"❌ {description} - COMMAND NOT FOUND")
        print(f"Please install the required tool: {cmd[0]}")
        return False


def main() -> int:
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run tests and code quality checks")
    parser.add_argument("--quick", action="store_true", help="Run only basic tests")
    parser.add_argument(
        "--no-coverage", action="store_true", help="Skip coverage reporting"
    )
    parser.add_argument(
        "--no-quality", action="store_true", help="Skip code quality checks"
    )
    parser.add_argument(
        "--install", action="store_true", help="Install dependencies first"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print("🚀 Roon Display Test Runner")
    print(f"📁 Working directory: {Path.cwd()}")

    success_count = 0
    total_count = 0

    if args.install:
        total_count += 1
        if run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            "Installing dependencies",
        ):
            success_count += 1

    test_cmd = [sys.executable, "-m", "pytest", "tests/"]
    if args.verbose:
        test_cmd.append("-v")
    if not args.no_coverage:
        test_cmd.extend(["--cov=roon_display", "--cov-report=term-missing"])
    if args.quick:
        test_cmd.extend(["-k", "not integration"])

    total_count += 1
    if run_command(test_cmd, "Running tests"):
        success_count += 1

    if not args.no_quality and not args.quick:
        total_count += 1
        if run_command(
            [sys.executable, "-m", "black", "--check", "roon_display", "tests"],
            "Checking code formatting",
        ):
            success_count += 1

        total_count += 1
        if run_command(
            [sys.executable, "-m", "isort", "--check-only", "roon_display", "tests"],
            "Checking import sorting",
        ):
            success_count += 1

        total_count += 1
        if run_command(
            [sys.executable, "-m", "flake8", "roon_display", "tests"], "Running linter"
        ):
            success_count += 1

        total_count += 1
        if run_command(
            [sys.executable, "-m", "mypy", "roon_display"], "Running type checker"
        ):
            success_count += 1

        total_count += 1
        if run_command(
            [sys.executable, "-m", "bandit", "-r", "roon_display"],
            "Running security scan",
        ):
            success_count += 1

    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {success_count}/{total_count}")
    print(f"❌ Failed: {total_count - success_count}/{total_count}")

    if success_count == total_count:
        print("\n🎉 All checks passed! Your code is ready for production.")
        return 0
    else:
        print(
            f"\n💥 {total_count - success_count} check(s) failed. Please fix the issues above."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
