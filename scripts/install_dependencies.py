#!/usr/bin/env python3
"""
Smart Dependency Installer for IntelliWiz Platform
==================================================

Automatically detects your platform and installs the correct dependencies.

Usage:
    python scripts/install_dependencies.py              # Install all dependencies
    python scripts/install_dependencies.py --dry-run    # Preview what will be installed
    python scripts/install_dependencies.py --minimal    # Install only core dependencies
    python scripts/install_dependencies.py --help       # Show help

Requirements:
    - Python 3.11.9 (recommended) or 3.11.x
    - Active virtual environment (venv)

"""

import argparse
import platform
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# ANSI color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def detect_platform() -> str:
    """
    Detect the operating system platform.

    Returns:
        'macos' or 'linux'

    Raises:
        SystemExit: If platform is not supported
    """
    system = platform.system().lower()

    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    else:
        print_error(f"Unsupported platform: {system}")
        print_info("This script supports macOS and Linux only.")
        sys.exit(1)


def check_python_version() -> Tuple[bool, str]:
    """
    Check if Python version meets requirements.

    Returns:
        Tuple of (is_valid, version_string)
    """
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    # Check for Python 3.11.x (recommended)
    if version.major == 3 and version.minor == 11:
        if version.micro == 9:
            return True, version_str  # Perfect!
        else:
            return True, version_str  # Good enough
    elif version.major == 3 and version.minor in [12, 13]:
        # Supported but not recommended
        return True, version_str
    else:
        return False, version_str


def check_virtual_environment() -> bool:
    """
    Check if running inside a virtual environment.

    Returns:
        True if in venv, False otherwise
    """
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def get_requirements_files(detected_platform: str, minimal: bool = False) -> List[Path]:
    """
    Get the list of requirements files to install based on platform.

    Args:
        detected_platform: 'macos' or 'linux'
        minimal: If True, install only core dependencies

    Returns:
        List of Path objects for requirements files
    """
    project_root = Path(__file__).parent.parent
    requirements_dir = project_root / "requirements"

    # Core requirements (always installed)
    if detected_platform == "macos":
        files = [requirements_dir / "base-macos.txt"]
    else:  # linux
        files = [requirements_dir / "base-linux.txt"]

    if not minimal:
        # Additional requirements for full installation
        files.extend([
            requirements_dir / "observability.txt",
            requirements_dir / "encryption.txt",
            requirements_dir / "concurrency.txt",
            requirements_dir / "sentry.txt",
            requirements_dir / "feature_flags.txt",
        ])

    # Validate all files exist
    for file in files:
        if not file.exists():
            print_error(f"Requirements file not found: {file}")
            sys.exit(1)

    return files


def install_requirements(requirements_files: List[Path], dry_run: bool = False) -> bool:
    """
    Install requirements from the specified files.

    Args:
        requirements_files: List of requirements file paths
        dry_run: If True, only show what would be installed

    Returns:
        True if successful, False otherwise
    """
    for req_file in requirements_files:
        print_info(f"{'Would install' if dry_run else 'Installing'}: {req_file.name}")

        if dry_run:
            # Show what would be installed
            try:
                with open(req_file, 'r') as f:
                    print(f"  Contents:\n{f.read()[:500]}...")
            except Exception as e:
                print_warning(f"  Could not read file: {e}")
            continue

        # Actually install
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                check=True,
                capture_output=False,
            )
            print_success(f"Installed: {req_file.name}")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to install {req_file.name}")
            print_error(f"Error: {e}")
            return False

    return True


def validate_installation(detected_platform: str) -> bool:
    """
    Validate that installation was successful.

    Args:
        detected_platform: 'macos' or 'linux'

    Returns:
        True if validation passes, False otherwise
    """
    print_header("Validating Installation")

    all_valid = True

    # Check critical packages
    critical_packages = [
        ("django", "Django framework"),
        ("rest_framework", "Django REST Framework"),
        ("celery", "Celery task queue"),
        ("psycopg", "PostgreSQL adapter (psycopg3)"),
    ]

    for package, description in critical_packages:
        try:
            __import__(package)
            print_success(f"{description}: OK")
        except ImportError:
            print_error(f"{description}: MISSING")
            all_valid = False

    # Platform-specific validation
    if detected_platform == "macos":
        # Ensure no CUDA packages on macOS
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list"],
                capture_output=True,
                text=True,
                check=True,
            )

            cuda_packages = [line for line in result.stdout.split('\n') if 'nvidia' in line.lower()]

            if cuda_packages:
                print_error("CUDA packages detected on macOS (should not be present):")
                for pkg in cuda_packages:
                    print(f"  - {pkg}")
                all_valid = False
            else:
                print_success("No CUDA packages (correct for macOS)")
        except subprocess.CalledProcessError:
            print_warning("Could not verify CUDA packages")

    # Check PyTorch
    try:
        import torch
        print_success(f"PyTorch: OK (version {torch.__version__})")

        if detected_platform == "macos":
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                print_success("Apple Metal Performance Shaders (MPS): Available")
            else:
                print_warning("MPS not available (requires Apple Silicon)")
    except ImportError:
        print_warning("PyTorch not installed (required for ML features)")

    return all_valid


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Smart dependency installer for IntelliWiz platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/install_dependencies.py              # Full installation
  python scripts/install_dependencies.py --dry-run    # Preview only
  python scripts/install_dependencies.py --minimal    # Core deps only

For more information, see: docs/workflows/COMMON_COMMANDS.md
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without actually installing"
    )
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Install only core dependencies (skip observability, encryption, etc.)"
    )

    args = parser.parse_args()

    print_header("IntelliWiz Dependency Installer")

    # Step 1: Check Python version
    print_info("Checking Python version...")
    is_valid, version_str = check_python_version()

    if not is_valid:
        print_error(f"Python version {version_str} is not supported")
        print_info("Please use Python 3.11.9 (recommended) or 3.11.x")
        print_info("\nTo install Python 3.11.9 with pyenv:")
        print("  pyenv install 3.11.9")
        print("  pyenv local 3.11.9")
        print("  ~/.pyenv/versions/3.11.9/bin/python -m venv venv")
        print("  source venv/bin/activate")
        sys.exit(1)

    if version_str == "3.11.9":
        print_success(f"Python version: {version_str} (perfect!)")
    else:
        print_success(f"Python version: {version_str}")
        if sys.version_info.minor != 11:
            print_warning("Python 3.11.9 is recommended for best stability")

    # Step 2: Check virtual environment
    print_info("Checking virtual environment...")
    if not check_virtual_environment():
        print_error("Not running in a virtual environment!")
        print_info("Please create and activate a venv first:")
        print("  python -m venv venv")
        print("  source venv/bin/activate  # On macOS/Linux")
        print("  venv\\Scripts\\activate     # On Windows")
        sys.exit(1)
    print_success("Virtual environment: Active")

    # Step 3: Detect platform
    print_info("Detecting platform...")
    detected_platform = detect_platform()
    print_success(f"Platform detected: {detected_platform.upper()}")

    if detected_platform == "macos":
        print_info("Will use macOS-optimized dependencies (no CUDA)")
    else:
        print_info("Will use Linux dependencies (with CUDA support)")

    # Step 4: Get requirements files
    print_info(f"Preparing requirements files ({'minimal' if args.minimal else 'full'} install)...")
    requirements_files = get_requirements_files(detected_platform, args.minimal)

    print_info(f"Will install {len(requirements_files)} requirements file(s):")
    for req_file in requirements_files:
        print(f"  - {req_file.name}")

    # Step 5: Install (or dry-run)
    if args.dry_run:
        print_header("Dry Run Mode (No Installation)")
        install_requirements(requirements_files, dry_run=True)
        print_info("\nThis was a dry run. No packages were installed.")
        print_info("Run without --dry-run to actually install.")
        sys.exit(0)

    print_header("Installing Dependencies")
    print_info("This may take several minutes...")

    success = install_requirements(requirements_files, dry_run=False)

    if not success:
        print_error("\nInstallation failed!")
        print_info("Please check the error messages above and try again.")
        sys.exit(1)

    print_success("\nAll requirements installed successfully!")

    # Step 6: Validate
    if validate_installation(detected_platform):
        print_header("Installation Complete!")
        print_success("All validation checks passed")
        print_info("\nNext steps:")
        print("  1. Run migrations: python manage.py migrate")
        print("  2. Initialize database: python manage.py init_intelliwiz default")
        print("  3. Start dev server: python manage.py runserver")
        print("\nFor more commands, see: docs/workflows/COMMON_COMMANDS.md")
    else:
        print_warning("\nSome validation checks failed")
        print_info("Installation may still work, but please review the warnings above")
        sys.exit(1)


if __name__ == "__main__":
    main()
