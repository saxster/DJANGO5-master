#!/usr/bin/env python3
"""
Check Python files for syntax errors.

This script helps identify files with existing syntax errors that need
to be fixed before running automated refactoring tools like remove_production_prints.py

Usage:
    python scripts/check_syntax_errors.py
    python scripts/check_syntax_errors.py --verbose
"""

import ast
import argparse
import logging
import sys
from pathlib import Path
from collections import defaultdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_file_syntax(filepath: Path) -> tuple[bool, str]:
    """
    Check if a Python file has valid syntax.

    Returns:
        (is_valid, error_message)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        ast.parse(source, filename=str(filepath))
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def scan_directory(directory: Path, skip_patterns: list = None) -> dict:
    """
    Scan directory for Python files and check syntax.

    Returns:
        Dictionary with statistics and error details
    """
    if skip_patterns is None:
        skip_patterns = [
            'venv',
            '.venv',
            '__pycache__',
            '.git',
            'node_modules',
            '.pytest_cache',
            'htmlcov',
            'coverage_reports'
        ]

    stats = {
        'total_files': 0,
        'valid_files': 0,
        'error_files': 0,
        'skipped_files': 0
    }

    errors_by_file = {}

    for py_file in directory.rglob('*.py'):
        # Check if should skip
        should_skip = False
        for pattern in skip_patterns:
            if pattern in str(py_file):
                should_skip = True
                break

        if should_skip:
            stats['skipped_files'] += 1
            continue

        stats['total_files'] += 1

        is_valid, error_msg = check_file_syntax(py_file)

        if is_valid:
            stats['valid_files'] += 1
            logger.debug(f"✓ {py_file}")
        else:
            stats['error_files'] += 1
            errors_by_file[str(py_file)] = error_msg
            logger.warning(f"✗ {py_file}: {error_msg}")

    return {
        'stats': stats,
        'errors': errors_by_file
    }


def generate_report(results: dict):
    """Generate a human-readable report."""
    stats = results['stats']
    errors = results['errors']

    print("=" * 80)
    print("PYTHON SYNTAX ERROR REPORT")
    print("=" * 80)
    print()
    print("STATISTICS")
    print("-" * 80)
    print(f"Total files scanned:  {stats['total_files']}")
    print(f"Files skipped:        {stats['skipped_files']}")
    print(f"Valid files:          {stats['valid_files']}")
    print(f"Files with errors:    {stats['error_files']}")
    print()

    if errors:
        print("FILES WITH SYNTAX ERRORS")
        print("-" * 80)

        # Group by error type for easier triage
        error_types = defaultdict(list)
        for filepath, error_msg in errors.items():
            # Extract error type from message
            if "invalid syntax" in error_msg.lower():
                error_type = "Invalid Syntax"
            elif "unexpected indent" in error_msg.lower():
                error_type = "Indentation Error"
            elif "f-string" in error_msg.lower():
                error_type = "F-string Error"
            elif "expected" in error_msg.lower():
                error_type = "Expected Token Missing"
            else:
                error_type = "Other Error"

            error_types[error_type].append((filepath, error_msg))

        for error_type, file_errors in sorted(error_types.items()):
            print(f"\n{error_type} ({len(file_errors)} files):")
            print("-" * 80)
            for filepath, error_msg in sorted(file_errors):
                print(f"  {filepath}")
                print(f"    {error_msg}")

        print()
        print("=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print()
        print("1. Fix syntax errors in the files listed above")
        print("2. Re-run this script to verify fixes")
        print("3. After all syntax errors are fixed, you can safely run:")
        print("   python scripts/remove_production_prints.py --dry-run")
        print()
    else:
        print("✓ No syntax errors found! All files are valid.")
        print()
        print("You can safely run:")
        print("  python scripts/remove_production_prints.py --dry-run")
        print()

    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Check Python files for syntax errors'
    )
    parser.add_argument(
        '--directory',
        type=str,
        default='apps',
        help='Directory to scan (default: apps)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine project root
    script_dir = Path(__file__).parent.parent
    project_root = script_dir

    scan_dir = project_root / args.directory
    if not scan_dir.exists():
        logger.error(f"Directory does not exist: {scan_dir}")
        return 1

    logger.info(f"Scanning directory: {scan_dir}")
    results = scan_directory(scan_dir)

    generate_report(results)

    # Return appropriate exit code
    if results['stats']['error_files'] > 0:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
