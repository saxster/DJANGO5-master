#!/usr/bin/env python3
"""
Standalone Logging Security Audit Script.

Scans Python files for insecure logging patterns without requiring Django.
Can be run as a standalone script or integrated into CI/CD.

Usage:
    python3 scripts/audit_logging_security_standalone.py --path apps/
    python3 scripts/audit_logging_security_standalone.py --path apps/peoples/ --verbose
"""

import os
import re
import sys
import argparse
from typing import List, Dict, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LoggingViolation:
    """Represents a logging security violation."""
    file_path: str
    line_number: int
    line_content: str
    violation_type: str
    severity: str
    recommendation: str


class LoggingSecurityAuditor:
    """Audits Python code for insecure logging patterns."""

    INSECURE_PATTERNS = [
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\([^)]*password', re.IGNORECASE),
            'type': 'password_logging',
            'severity': 'CRITICAL',
            'recommendation': 'Never log passwords. Use correlation IDs for tracking.'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\([^)]*token', re.IGNORECASE),
            'type': 'token_logging',
            'severity': 'CRITICAL',
            'recommendation': 'Never log tokens. Use correlation IDs for tracking.'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\([^)]*secret', re.IGNORECASE),
            'type': 'secret_logging',
            'severity': 'CRITICAL',
            'recommendation': 'Never log secrets or encryption keys.'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\(.*f".*\{.*\.email', re.IGNORECASE),
            'type': 'email_logging',
            'severity': 'HIGH',
            'recommendation': 'Use user_id instead of email address, or use get_sanitized_logger().'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\(.*f".*\{.*mobno', re.IGNORECASE),
            'type': 'phone_logging',
            'severity': 'HIGH',
            'recommendation': 'Do not log mobile numbers. Use user_id instead.'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\([^)]*request\.POST\b'),
            'type': 'post_data_logging',
            'severity': 'HIGH',
            'recommendation': 'Do not log entire request.POST. Log specific fields or field count.'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\([^)]*request\.GET\s*[\)\,]'),
            'type': 'get_data_logging',
            'severity': 'MEDIUM',
            'recommendation': 'Do not log entire request.GET dictionary. Log specific parameters instead.'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\([^)]*credit.*card', re.IGNORECASE),
            'type': 'credit_card_logging',
            'severity': 'CRITICAL',
            'recommendation': 'Never log credit card information.'
        },
        {
            'pattern': re.compile(r'logger\.(info|debug|error|warning|critical)\([^)]*\bssn\b', re.IGNORECASE),
            'type': 'ssn_logging',
            'severity': 'CRITICAL',
            'recommendation': 'Never log Social Security Numbers.'
        },
    ]

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.violations = []

    def audit_file(self, file_path: str) -> List[LoggingViolation]:
        """Audit a single Python file for logging security issues."""
        file_violations = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for pattern_config in self.INSECURE_PATTERNS:
                    if pattern_config['pattern'].search(line):
                        violation = LoggingViolation(
                            file_path=file_path,
                            line_number=line_num,
                            line_content=line.strip(),
                            violation_type=pattern_config['type'],
                            severity=pattern_config['severity'],
                            recommendation=pattern_config['recommendation']
                        )
                        file_violations.append(violation)
                        self.violations.append(violation)

        except Exception as e:
            if self.verbose:
                print(f"Error auditing {file_path}: {e}")

        return file_violations

    def audit_directory(self, directory_path: str, exclude_dirs: List[str] = None) -> Dict:
        """Audit all Python files in a directory."""
        if exclude_dirs is None:
            exclude_dirs = ['migrations', '__pycache__', '.git', 'venv', 'env']

        python_files = []
        for root, dirs, files in os.walk(directory_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))

        total_files = len(python_files)
        files_with_violations = 0

        print(f"🔍 Scanning {total_files} Python files in {directory_path}...")

        for file_path in python_files:
            file_violations = self.audit_file(file_path)

            if file_violations:
                files_with_violations += 1
                self._print_file_violations(file_path, file_violations)

        return {
            'total_files_scanned': total_files,
            'files_with_violations': files_with_violations,
            'total_violations': len(self.violations),
            'violations_by_severity': self._group_by_severity(),
            'violations_by_type': self._group_by_type()
        }

    def _print_file_violations(self, file_path: str, violations: List[LoggingViolation]):
        """Print violations for a file."""
        print(f"\n📁 {file_path}")

        for violation in violations:
            severity_color = self._get_severity_color(violation.severity)
            print(f"  {severity_color}[{violation.severity}]{self._color_reset()} Line {violation.line_number}: {violation.violation_type}")
            if self.verbose:
                print(f"    Content: {violation.line_content[:100]}")
            print(f"    💡 Fix: {violation.recommendation}")

    def _group_by_severity(self) -> Dict[str, int]:
        """Group violations by severity."""
        grouped = {}
        for violation in self.violations:
            grouped[violation.severity] = grouped.get(violation.severity, 0) + 1
        return grouped

    def _group_by_type(self) -> Dict[str, int]:
        """Group violations by type."""
        grouped = {}
        for violation in self.violations:
            grouped[violation.violation_type] = grouped.get(violation.violation_type, 0) + 1
        return grouped

    def _get_severity_color(self, severity: str) -> str:
        """Get ANSI color code for severity."""
        colors = {
            'CRITICAL': '\033[0;31m',
            'HIGH': '\033[0;33m',
            'MEDIUM': '\033[0;36m',
            'LOW': '\033[0;32m'
        }
        return colors.get(severity, '')

    def _color_reset(self) -> str:
        """Get ANSI color reset code."""
        return '\033[0m'

    def print_summary(self, results: Dict):
        """Print audit summary."""
        print("\n" + "="*70)
        print("📊 LOGGING SECURITY AUDIT SUMMARY")
        print("="*70)
        print(f"Files scanned: {results['total_files_scanned']}")
        print(f"Files with violations: {results['files_with_violations']}")
        print(f"Total violations: {results['total_violations']}")
        print()

        if results['violations_by_severity']:
            print("Violations by Severity:")
            for severity, count in sorted(results['violations_by_severity'].items()):
                color = self._get_severity_color(severity)
                print(f"  {color}{severity}: {count}{self._color_reset()}")
            print()

        if results['violations_by_type']:
            print("Violations by Type:")
            for vtype, count in sorted(results['violations_by_type'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {vtype}: {count}")
            print()

        if results['total_violations'] > 0:
            print(f"\033[0;31m❌ {results['total_violations']} logging security violations found\033[0m")
            print()
            print("📚 NEXT STEPS:")
            print("  1. Review docs/security/LOGGING_SECURITY_MIGRATION_GUIDE.md")
            print("  2. Use: from apps.core.middleware import get_sanitized_logger")
            print("  3. Replace insecure logging with structured logging")
            print("  4. Run this audit again to verify fixes")
            print()
            return False
        else:
            print("\033[0;32m✅ No logging security violations found\033[0m")
            print()
            return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Audit Python code for insecure logging patterns'
    )
    parser.add_argument(
        '--path',
        type=str,
        default='apps',
        help='Path to audit (default: apps)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show verbose output including code snippets'
    )
    parser.add_argument(
        '--exclude',
        type=str,
        nargs='*',
        default=['migrations', '__pycache__', '.git', 'venv'],
        help='Directories to exclude'
    )

    args = parser.parse_args()

    auditor = LoggingSecurityAuditor(verbose=args.verbose)

    if not os.path.exists(args.path):
        print(f"❌ Error: Path '{args.path}' does not exist")
        sys.exit(1)

    results = auditor.audit_directory(args.path, exclude_dirs=args.exclude)

    success = auditor.print_summary(results)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()