#!/usr/bin/env python3
"""
Comprehensive Code Quality Validation Script

Validates that all code quality and security fixes are properly applied.
This script ensures compliance with .claude/rules.md standards.

Usage:
    python scripts/validate_code_quality.py
    python scripts/validate_code_quality.py --verbose
    python scripts/validate_code_quality.py --report quality_report.md

Exit codes:
    0: All checks passed
    1: One or more checks failed

Author: Code Quality Team
Date: 2025-09-30
"""

import os
import re
import sys
import argparse
import ast
from pathlib import Path
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ValidationIssue:
    """Container for validation issue"""
    check_name: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    file_path: str
    line_number: int
    issue: str
    suggestion: str


class CodeQualityValidator:
    """
    Comprehensive validator for code quality and security standards.
    """

    def __init__(self, root_dir: str = '.', verbose: bool = False):
        self.root_dir = Path(root_dir).resolve()
        self.verbose = verbose
        self.issues: List[ValidationIssue] = []
        self.stats = defaultdict(int)

        # Patterns to exclude
        self.exclude_patterns = [
            '*/migrations/*',
            '*/test_*',
            '*/__pycache__/*',
            '*/venv/*',
            '*/env/*',
            '*/.git/*',
            '*/node_modules/*',
        ]

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

    def should_exclude(self, filepath: Path) -> bool:
        """Check if file should be excluded"""
        filepath_str = str(filepath)
        for pattern in self.exclude_patterns:
            pattern_re = pattern.replace('*', '.*')
            if re.search(pattern_re, filepath_str):
                return True
        return False

    def find_python_files(self) -> List[Path]:
        """Find all Python files to validate"""
        python_files = []
        apps_dir = self.root_dir / 'apps'

        for py_file in apps_dir.rglob('*.py'):
            if not self.should_exclude(py_file):
                python_files.append(py_file)

        self.log(f"Found {len(python_files)} Python files to validate")
        return python_files

    def validate_wildcard_imports(self, filepath: Path) -> int:
        """
        Validate that wildcard imports are not used (except Django settings pattern).

        RULE: No wildcard imports except in Django settings files.
        """
        issues_count = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if this is a Django settings file (allowed exception)
            is_settings_file = 'settings' in str(filepath) and 'intelliwiz_config' in str(filepath)

            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                # Skip comments
                if line.strip().startswith('#'):
                    continue

                # Find wildcard imports
                if 'from' in line and 'import *' in line:
                    # Check for noqa comment
                    if 'noqa' in line:
                        continue

                    # Settings files are allowed if documented
                    if is_settings_file and 'Django settings pattern' in content:
                        continue

                    self.issues.append(ValidationIssue(
                        check_name='wildcard_imports',
                        severity='high',
                        file_path=str(filepath.relative_to(self.root_dir)),
                        line_number=line_num,
                        issue=f"Wildcard import found: {line.strip()}",
                        suggestion="Replace with explicit imports listing each symbol"
                    ))
                    issues_count += 1

        except Exception as e:
            self.log(f"Error validating wildcard imports in {filepath}: {e}", 'ERROR')

        return issues_count

    def validate_exception_handling(self, filepath: Path) -> int:
        """
        Validate that specific exception types are used instead of generic Exception.

        RULE: Use specific exception types from apps.core.exceptions.patterns
        """
        issues_count = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content, filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    # Check if it's generic "except Exception:"
                    if node.type and isinstance(node.type, ast.Name):
                        if node.type.id == 'Exception':
                            self.issues.append(ValidationIssue(
                                check_name='generic_exception',
                                severity='medium',
                                file_path=str(filepath.relative_to(self.root_dir)),
                                line_number=node.lineno,
                                issue="Generic 'except Exception:' handler found",
                                suggestion="Use specific exception types from apps.core.exceptions.patterns (DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS, etc.)"
                            ))
                            issues_count += 1

        except SyntaxError:
            # Skip files with syntax errors (might be templates)
            pass
        except Exception as e:
            self.log(f"Error validating exceptions in {filepath}: {e}", 'ERROR')

        return issues_count

    def validate_network_timeouts(self, filepath: Path) -> int:
        """
        Validate that all network calls have timeout parameters.

        RULE: All requests.get/post/put/delete/patch must have timeout=(connect, read)
        """
        issues_count = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all requests method calls
            pattern = r'requests\.(get|post|put|delete|patch)\s*\('
            matches = list(re.finditer(pattern, content))

            for match in matches:
                start_pos = match.start()

                # Check if this is a comment
                line_start = content.rfind('\n', 0, start_pos)
                line = content[line_start:start_pos]
                if '#' in line:
                    continue

                # Look ahead to find if timeout is specified
                snippet = content[start_pos:start_pos+300]

                if 'timeout' not in snippet:
                    line_num = content[:start_pos].count('\n') + 1

                    self.issues.append(ValidationIssue(
                        check_name='network_timeout',
                        severity='critical',
                        file_path=str(filepath.relative_to(self.root_dir)),
                        line_number=line_num,
                        issue=f"Network call without timeout: {match.group()}",
                        suggestion="Add timeout=(connect_seconds, read_seconds) parameter, e.g., timeout=(5, 15)"
                    ))
                    issues_count += 1

        except Exception as e:
            self.log(f"Error validating network timeouts in {filepath}: {e}", 'ERROR')

        return issues_count

    def validate_code_injection(self, filepath: Path) -> int:
        """
        Validate that no eval() or exec() calls exist.

        RULE: Never use eval() or exec() - code injection vulnerability
        """
        issues_count = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                # Skip comments and strings
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                if '"""' in line or "'''" in line:
                    continue
                if stripped.startswith('"') or stripped.startswith("'"):
                    continue

                # Check for eval() or exec()
                if re.search(r'\beval\s*\(', line):
                    self.issues.append(ValidationIssue(
                        check_name='code_injection',
                        severity='critical',
                        file_path=str(filepath.relative_to(self.root_dir)),
                        line_number=line_num,
                        issue="eval() call found - code injection risk",
                        suggestion="Replace with explicit function calls or configuration-based approach"
                    ))
                    issues_count += 1

                if re.search(r'\bexec\s*\(', line):
                    self.issues.append(ValidationIssue(
                        check_name='code_injection',
                        severity='critical',
                        file_path=str(filepath.relative_to(self.root_dir)),
                        line_number=line_num,
                        issue="exec() call found - code injection risk",
                        suggestion="Replace with explicit function calls or importlib"
                    ))
                    issues_count += 1

        except Exception as e:
            self.log(f"Error validating code injection in {filepath}: {e}", 'ERROR')

        return issues_count

    def validate_blocking_io(self, filepath: Path) -> int:
        """
        Validate that time.sleep() is not used in request paths.

        RULE: Use exponential backoff with jitter instead of fixed sleep
        """
        issues_count = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Check if this file is in request paths (views, decorators, middleware)
            is_request_path = any(keyword in str(filepath) for keyword in
                                 ['views', 'decorators', 'middleware', 'api'])

            if not is_request_path:
                return 0

            for line_num, line in enumerate(lines, 1):
                if 'time.sleep' in line and not line.strip().startswith('#'):
                    self.issues.append(ValidationIssue(
                        check_name='blocking_io',
                        severity='high',
                        file_path=str(filepath.relative_to(self.root_dir)),
                        line_number=line_num,
                        issue="time.sleep() in request path - blocking I/O",
                        suggestion="Use apps.core.utils_new.retry_mechanism with exponential backoff"
                    ))
                    issues_count += 1

        except Exception as e:
            self.log(f"Error validating blocking I/O in {filepath}: {e}", 'ERROR')

        return issues_count

    def validate_sys_path_manipulation(self, filepath: Path) -> int:
        """
        Validate that sys.path is not manipulated.

        RULE: Use importlib.util instead of sys.path manipulation
        """
        issues_count = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                if 'sys.path' in line and not line.strip().startswith('#'):
                    # Allow sys.path.insert(0, ...) in root-level scripts
                    if 'scripts/' in str(filepath) and 'sys.path.insert(0' in line:
                        continue

                    self.issues.append(ValidationIssue(
                        check_name='sys_path_manipulation',
                        severity='medium',
                        file_path=str(filepath.relative_to(self.root_dir)),
                        line_number=line_num,
                        issue="sys.path manipulation found",
                        suggestion="Use importlib.util.spec_from_file_location() instead"
                    ))
                    issues_count += 1

        except Exception as e:
            self.log(f"Error validating sys.path in {filepath}: {e}", 'ERROR')

        return issues_count

    def validate_production_prints(self, filepath: Path) -> int:
        """
        Validate that print() is not used in production code.

        RULE: Use logger.info/warning/error instead of print()
        """
        issues_count = 0

        try:
            # Skip scripts directory (print is OK there)
            if 'scripts/' in str(filepath):
                return 0

            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                # Look for print statements
                if re.search(r'\bprint\s*\(', line) and not line.strip().startswith('#'):
                    # Check if it's in a settings file (migration output is OK)
                    if 'settings' in str(filepath) and 'SETTINGS]' in line:
                        continue

                    self.issues.append(ValidationIssue(
                        check_name='production_print',
                        severity='low',
                        file_path=str(filepath.relative_to(self.root_dir)),
                        line_number=line_num,
                        issue="print() statement in production code",
                        suggestion="Use logger.info() or logger.debug() instead"
                    ))
                    issues_count += 1

        except Exception as e:
            self.log(f"Error validating prints in {filepath}: {e}", 'ERROR')

        return issues_count

    def run_all_validations(self) -> Dict[str, int]:
        """Run all validation checks"""
        python_files = self.find_python_files()

        validation_checks = [
            ('wildcard_imports', self.validate_wildcard_imports),
            ('exception_handling', self.validate_exception_handling),
            ('network_timeouts', self.validate_network_timeouts),
            ('code_injection', self.validate_code_injection),
            ('blocking_io', self.validate_blocking_io),
            ('sys_path_manipulation', self.validate_sys_path_manipulation),
            ('production_prints', self.validate_production_prints),
        ]

        results = {}

        for check_name, check_func in validation_checks:
            self.log(f"Running check: {check_name}")
            total_issues = 0

            for filepath in python_files:
                issues = check_func(filepath)
                total_issues += issues

            results[check_name] = total_issues
            self.stats[check_name] = total_issues

            if total_issues == 0:
                self.log(f"✅ {check_name}: PASSED (0 issues)", 'SUCCESS')
            else:
                self.log(f"❌ {check_name}: FAILED ({total_issues} issues)", 'ERROR')

        return results

    def generate_report(self, output_file: str):
        """Generate markdown report of validation results"""
        # Group issues by severity
        by_severity = defaultdict(list)
        for issue in self.issues:
            by_severity[issue.severity].append(issue)

        # Group issues by check
        by_check = defaultdict(list)
        for issue in self.issues:
            by_check[issue.check_name].append(issue)

        total_issues = len(self.issues)

        report = f"""# Code Quality Validation Report

**Generated:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Issues:** {total_issues}
**Files Scanned:** {self.stats.get('files_scanned', 'N/A')}

## Executive Summary

| Check | Issues Found | Status |
|-------|--------------|--------|
"""

        for check_name, count in self.stats.items():
            status = '✅ PASS' if count == 0 else '❌ FAIL'
            report += f"| {check_name.replace('_', ' ').title()} | {count} | {status} |\n"

        report += "\n## Issues by Severity\n\n"

        for severity in ['critical', 'high', 'medium', 'low']:
            issues = by_severity.get(severity, [])
            if issues:
                report += f"### {severity.upper()} ({len(issues)} issues)\n\n"

                for issue in issues[:10]:  # Show first 10
                    report += f"**{issue.file_path}:{issue.line_number}**\n"
                    report += f"- Issue: {issue.issue}\n"
                    report += f"- Suggestion: {issue.suggestion}\n\n"

                if len(issues) > 10:
                    report += f"... and {len(issues) - 10} more\n\n"

        report += "\n## Issues by Check\n\n"

        for check_name, issues in by_check.items():
            report += f"### {check_name.replace('_', ' ').title()} ({len(issues)} issues)\n\n"

            # Show first 5 issues
            for issue in issues[:5]:
                report += f"- `{issue.file_path}:{issue.line_number}` - {issue.issue}\n"

            if len(issues) > 5:
                report += f"- ... and {len(issues) - 5} more\n"

            report += "\n"

        report += """## Remediation Guide

### Critical Issues (Fix Immediately)
- **Code Injection**: Remove all eval()/exec() calls
- **Network Timeouts**: Add timeout parameters to all requests calls

### High Priority Issues (Fix This Sprint)
- **Wildcard Imports**: Replace with explicit imports
- **Blocking I/O**: Replace time.sleep() with exponential backoff

### Medium Priority Issues (Fix Next Sprint)
- **Generic Exceptions**: Use specific exception types
- **sys.path Manipulation**: Use importlib.util instead

### Low Priority Issues (Technical Debt)
- **Print Statements**: Replace with logger calls

## References
- `.claude/rules.md` - Complete coding standards
- `apps/core/exceptions/patterns.py` - Exception handling patterns
- `scripts/migrate_exception_handling.py` - Automated migration tool
- `CODE_QUALITY_REMEDIATION_COMPLETE.md` - Complete remediation guide
"""

        with open(output_file, 'w') as f:
            f.write(report)

        self.log(f"Report generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Comprehensive code quality validation'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--report', '-r',
        type=str,
        metavar='FILE',
        help='Generate markdown report to FILE'
    )
    parser.add_argument(
        '--root',
        default='.',
        help='Root directory to scan (default: current directory)'
    )

    args = parser.parse_args()

    # Run validation
    validator = CodeQualityValidator(root_dir=args.root, verbose=args.verbose)

    print("\n" + "="*70)
    print("  CODE QUALITY VALIDATION")
    print("="*70 + "\n")

    results = validator.run_all_validations()

    # Print summary
    print("\n" + "="*70)
    print("  VALIDATION SUMMARY")
    print("="*70 + "\n")

    total_issues = sum(results.values())

    if total_issues == 0:
        print("✅ ALL CHECKS PASSED - No issues found!\n")
        exit_code = 0
    else:
        print(f"❌ VALIDATION FAILED - {total_issues} issues found\n")

        # Show breakdown
        for check_name, count in sorted(results.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"  • {check_name.replace('_', ' ').title()}: {count} issues")

        print()
        exit_code = 1

    # Generate report if requested
    if args.report:
        validator.generate_report(args.report)
        print(f"\n📄 Detailed report: {args.report}\n")

    sys.exit(exit_code)


if __name__ == '__main__':
    main()