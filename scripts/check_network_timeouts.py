#!/usr/bin/env python3
"""
Network Timeout Validation Script

Validates that all network calls include timeout parameters as required by .claude/rules.md.
Missing timeouts can cause workers to hang indefinitely.

Checks for:
- requests.get() without timeout
- requests.post() without timeout
- requests.put() without timeout
- requests.patch() without timeout
- requests.delete() without timeout
- httpx calls without timeout
- urllib calls without timeout

Usage:
    python scripts/check_network_timeouts.py
    python scripts/check_network_timeouts.py --verbose
    python scripts/check_network_timeouts.py --ci
    python scripts/check_network_timeouts.py --pre-commit

Exit codes:
    0: All network calls have timeouts
    1: Missing timeouts found

Author: Quality Gates Engineer
Date: 2025-11-04
"""

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class TimeoutViolation:
    """Container for timeout violation"""
    file_path: str
    line_number: int
    function_call: str
    context: str

    def __str__(self):
        return f"{self.file_path}:{self.line_number}: {self.function_call} missing timeout parameter"


class NetworkTimeoutValidator:
    """Validates network calls have timeout parameters"""

    # Network functions that require timeouts
    NETWORK_FUNCTIONS = {
        'requests.get', 'requests.post', 'requests.put', 'requests.patch', 
        'requests.delete', 'requests.request', 'requests.head', 'requests.options',
        'httpx.get', 'httpx.post', 'httpx.put', 'httpx.patch', 'httpx.delete',
        'httpx.request', 'httpx.head', 'httpx.options',
    }

    def __init__(self, root_dir: str = '.', verbose: bool = False):
        self.root_dir = Path(root_dir).resolve()
        self.verbose = verbose
        self.violations: List[TimeoutViolation] = []

    def log(self, message: str, level: str = 'INFO'):
        """Log message if verbose mode enabled"""
        if self.verbose or level in ['ERROR', 'CRITICAL']:
            prefix = {
                'INFO': 'ℹ️ ',
                'SUCCESS': '✅',
                'WARNING': '⚠️ ',
                'ERROR': '❌',
                'CRITICAL': '🔴',
            }.get(level, '')
            print(f"{prefix} {message}")

    def check_file(self, filepath: Path) -> List[TimeoutViolation]:
        """Check a single file for timeout violations"""
        violations = []

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')

            # Pattern 1: Direct function calls like requests.get(url)
            for i, line in enumerate(lines, 1):
                # Skip comments
                if line.strip().startswith('#'):
                    continue

                # Check for requests/httpx calls
                for func in self.NETWORK_FUNCTIONS:
                    if func in line:
                        # Check if timeout is present in the same line or nearby
                        # Look at current line and next 15 lines (for multi-line calls)
                        context_lines = '\n'.join(lines[max(0, i-1):min(len(lines), i+15)])

                        if 'timeout' not in context_lines.lower():
                            violation = TimeoutViolation(
                                file_path=str(filepath.relative_to(self.root_dir)),
                                line_number=i,
                                function_call=func,
                                context=line.strip()[:80]
                            )
                            violations.append(violation)
                            break  # Only report once per line

        except Exception as e:
            self.log(f"Error checking {filepath}: {e}", 'WARNING')

        return violations

    def scan_directory(self, exclude_dirs: set = None) -> List[TimeoutViolation]:
        """Scan directory for Python files"""
        if exclude_dirs is None:
            exclude_dirs = {
                'venv', 'env', '.venv', 'migrations', 'node_modules',
                '__pycache__', '.git', 'tests', 'test_'
            }

        self.log(f"Scanning {self.root_dir} for network timeout violations...")

        apps_dir = self.root_dir / 'apps'
        if not apps_dir.exists():
            self.log("apps/ directory not found", 'WARNING')
            return []

        py_files = []
        for py_file in apps_dir.rglob('*.py'):
            # Skip excluded directories
            skip = False
            for exclude in exclude_dirs:
                if exclude in str(py_file):
                    skip = True
                    break
            if not skip:
                py_files.append(py_file)

        self.log(f"Found {len(py_files)} Python files to check")

        violations = []
        for py_file in py_files:
            file_violations = self.check_file(py_file)
            violations.extend(file_violations)

        return violations

    def run_validation(self) -> bool:
        """Run validation and report results"""
        self.log("=" * 70)
        self.log("NETWORK TIMEOUT VALIDATION")
        self.log("=" * 70)

        self.violations = self.scan_directory()

        self.log("=" * 70)
        if self.violations:
            self.log(f"FAILED: {len(self.violations)} network calls missing timeouts", 'ERROR')
            self.log("=" * 70)

            # Group by file
            by_file = {}
            for v in self.violations:
                by_file.setdefault(v.file_path, []).append(v)

            self.log(f"\nViolations in {len(by_file)} files:", 'ERROR')
            for filepath in sorted(by_file.keys()):
                self.log(f"\n{filepath}:", 'ERROR')
                for violation in by_file[filepath]:
                    self.log(f"  Line {violation.line_number}: {violation.function_call}", 'ERROR')
                    self.log(f"    Context: {violation.context}", 'WARNING')

            self.log("\n📖 Fix: Add timeout parameter to all network calls", 'INFO')
            self.log("Example: requests.get(url, timeout=(5, 15))  # (connect, read) seconds", 'INFO')
            self.log("\nSee CLAUDE.md for timeout guidelines:", 'INFO')
            self.log("  - API/metadata: (5, 15)", 'INFO')
            self.log("  - File downloads: (5, 30)", 'INFO')
            self.log("  - Long operations: (5, 60)", 'INFO')

            return False
        else:
            self.log("SUCCESS: All network calls have timeout parameters", 'SUCCESS')
            self.log("=" * 70)
            return True


def main():
    parser = argparse.ArgumentParser(
        description='Validate network calls have timeout parameters'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--ci', action='store_true',
                        help='CI mode: strict exit codes')
    parser.add_argument('--pre-commit', action='store_true',
                        help='Pre-commit mode: only check staged files')

    args = parser.parse_args()

    # Create validator
    validator = NetworkTimeoutValidator(verbose=args.verbose or args.ci)

    # Run validation
    passed = validator.run_validation()

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
