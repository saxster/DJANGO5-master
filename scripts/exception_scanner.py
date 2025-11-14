#!/usr/bin/env python3
"""
Exception Handling Quality Scanner

Scans Python codebase for generic exception handling anti-patterns.
Detects violations of .claude/rules.md exception handling standards.

Forbidden patterns:
- except Exception:
- except BaseException:
- except:
- Generic catches without re-raising

Required patterns:
- Specific exception types from apps/core/exceptions/patterns.py
- Proper logging with exc_info=True
- Re-raising after logging (unless intentional suppression)

Usage:
    python scripts/exception_scanner.py
    python scripts/exception_scanner.py --json violations.json
    python scripts/exception_scanner.py --markdown report.md
    python scripts/exception_scanner.py --verbose
    python scripts/exception_scanner.py --ci

Exit codes:
    0: No violations found
    1: Violations found

Author: Quality Gates Engineer
Date: 2025-11-14
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Set
from collections import defaultdict


@dataclass
class ExceptionViolation:
    """Container for exception handling violation"""
    file_path: str
    line_number: int
    exception_type: str
    context: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    violation_type: str

    def __str__(self):
        return f"{self.file_path}:{self.line_number}: {self.violation_type} - {self.exception_type}"


class ExceptionVisitor(ast.NodeVisitor):
    """AST visitor to detect exception handling violations"""

    # Generic exceptions that should be avoided
    FORBIDDEN_EXCEPTIONS = {
        'Exception',
        'BaseException',
        'StandardError',  # Python 2 legacy
    }

    # Allowed generic patterns (with justification required)
    ALLOWED_CONTEXTS = {
        'tests',
        'test_',
        'migrations',
    }

    def __init__(self, file_path: str, source_code: str):
        self.file_path = file_path
        self.source_lines = source_code.split('\n')
        self.violations: List[ExceptionViolation] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        """Check exception handler for anti-patterns"""

        # Case 1: Bare except (no exception type)
        if node.type is None:
            self._add_violation(
                node,
                'bare except',
                'except:',
                'critical',
                'BARE_EXCEPT'
            )

        # Case 2: Generic Exception catch
        elif isinstance(node.type, ast.Name):
            if node.type.id in self.FORBIDDEN_EXCEPTIONS:
                self._add_violation(
                    node,
                    f'except {node.type.id}',
                    node.type.id,
                    'high',
                    'GENERIC_EXCEPTION'
                )

        # Case 3: Tuple of exceptions including generic ones
        elif isinstance(node.type, ast.Tuple):
            for exc in node.type.elts:
                if isinstance(exc, ast.Name) and exc.id in self.FORBIDDEN_EXCEPTIONS:
                    self._add_violation(
                        node,
                        f'except tuple with {exc.id}',
                        exc.id,
                        'high',
                        'GENERIC_EXCEPTION_IN_TUPLE'
                    )

        # Check exception handler body
        self._check_handler_body(node)

        self.generic_visit(node)

    def _check_handler_body(self, node: ast.ExceptHandler):
        """Check exception handler body for additional issues"""

        # Check if handler is empty (pass/continue/break only)
        if len(node.body) == 1:
            stmt = node.body[0]

            # Silent suppression
            if isinstance(stmt, ast.Pass):
                self._add_violation(
                    node,
                    'silent exception suppression',
                    'pass in except',
                    'medium',
                    'SILENT_SUPPRESSION'
                )

        # Check for missing logging
        has_logging = self._has_logging_call(node.body)
        has_reraise = self._has_reraise(node.body)

        if not has_logging and not has_reraise:
            # Exception caught but not logged or re-raised
            self._add_violation(
                node,
                'exception not logged or re-raised',
                'untracked exception',
                'medium',
                'UNTRACKED_EXCEPTION'
            )

    def _has_logging_call(self, body: List[ast.stmt]) -> bool:
        """Check if exception handler includes logging"""
        for stmt in ast.walk(ast.Module(body=body)):
            if isinstance(stmt, ast.Call):
                if isinstance(stmt.func, ast.Attribute):
                    # logger.error, logger.exception, etc.
                    if stmt.func.attr in {'error', 'exception', 'warning', 'critical'}:
                        return True
        return False

    def _has_reraise(self, body: List[ast.stmt]) -> bool:
        """Check if exception handler re-raises"""
        for stmt in body:
            if isinstance(stmt, ast.Raise):
                return True
        return False

    def _add_violation(
        self,
        node: ast.AST,
        context: str,
        exception_type: str,
        severity: str,
        violation_type: str
    ):
        """Add violation to list"""
        line_number = node.lineno

        # Get source context
        source_context = self._get_source_context(line_number)

        violation = ExceptionViolation(
            file_path=self.file_path,
            line_number=line_number,
            exception_type=exception_type,
            context=source_context,
            severity=severity,
            violation_type=violation_type
        )

        self.violations.append(violation)

    def _get_source_context(self, line_number: int, context_lines: int = 3) -> str:
        """Get source code context around violation"""
        start = max(0, line_number - context_lines)
        end = min(len(self.source_lines), line_number + context_lines)

        context = self.source_lines[start:end]
        return '\n'.join(context[:80] for context in context if context.strip())


class ExceptionScanner:
    """Scans codebase for exception handling violations"""

    def __init__(self, root_dir: str = '.', verbose: bool = False):
        self.root_dir = Path(root_dir).resolve()
        self.verbose = verbose
        self.violations: List[ExceptionViolation] = []

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

    def scan_file(self, filepath: Path) -> List[ExceptionViolation]:
        """Scan a single Python file for violations"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()

            # Parse AST
            tree = ast.parse(source_code, filename=str(filepath))

            # Visit and collect violations
            visitor = ExceptionVisitor(
                str(filepath.relative_to(self.root_dir)),
                source_code
            )
            visitor.visit(tree)

            return visitor.violations

        except SyntaxError as e:
            self.log(f"Syntax error in {filepath}: {e}", 'WARNING')
            return []
        except Exception as e:
            self.log(f"Error scanning {filepath}: {e}", 'WARNING')
            return []

    def scan_directory(self, exclude_dirs: Set[str] = None) -> List[ExceptionViolation]:
        """Scan directory for Python files"""
        if exclude_dirs is None:
            exclude_dirs = {
                'venv', 'env', '.venv',
                'migrations', 'node_modules',
                '__pycache__', '.git',
                'postgresql_migration',
            }

        self.log(f"Scanning {self.root_dir} for exception handling violations...")

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
            file_violations = self.scan_file(py_file)
            violations.extend(file_violations)

        return violations

    def generate_json_report(self, output_path: str):
        """Generate JSON report with violation metadata"""
        report = {
            'total_violations': len(self.violations),
            'by_severity': self._group_by_severity(),
            'by_type': self._group_by_type(),
            'by_file': self._group_by_file(),
            'violations': [asdict(v) for v in self.violations]
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        self.log(f"JSON report written to {output_path}", 'SUCCESS')

    def generate_markdown_report(self, output_path: str):
        """Generate markdown priority report"""
        with open(output_path, 'w') as f:
            f.write("# Exception Handling Violations Report\n\n")
            f.write(f"**Total Violations**: {len(self.violations)}\n\n")

            # By severity
            f.write("## Violations by Severity\n\n")
            by_severity = self._group_by_severity()
            for severity in ['critical', 'high', 'medium', 'low']:
                count = by_severity.get(severity, 0)
                f.write(f"- **{severity.upper()}**: {count}\n")

            f.write("\n## Violations by Type\n\n")
            by_type = self._group_by_type()
            for vtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
                f.write(f"- **{vtype}**: {count}\n")

            f.write("\n## Priority Files (Most Violations)\n\n")
            by_file = self._group_by_file()
            sorted_files = sorted(by_file.items(), key=lambda x: -len(x[1]))[:20]

            for filepath, violations in sorted_files:
                f.write(f"\n### {filepath} ({len(violations)} violations)\n\n")
                for v in violations[:5]:  # Top 5 per file
                    f.write(f"- Line {v.line_number}: {v.violation_type} - {v.exception_type}\n")

        self.log(f"Markdown report written to {output_path}", 'SUCCESS')

    def _group_by_severity(self) -> Dict[str, int]:
        """Group violations by severity"""
        by_severity = defaultdict(int)
        for v in self.violations:
            by_severity[v.severity] += 1
        return dict(by_severity)

    def _group_by_type(self) -> Dict[str, int]:
        """Group violations by type"""
        by_type = defaultdict(int)
        for v in self.violations:
            by_type[v.violation_type] += 1
        return dict(by_type)

    def _group_by_file(self) -> Dict[str, List[ExceptionViolation]]:
        """Group violations by file"""
        by_file = defaultdict(list)
        for v in self.violations:
            by_file[v.file_path].append(v)
        return dict(by_file)

    def run_scan(self) -> bool:
        """Run scan and report results"""
        self.log("=" * 70)
        self.log("EXCEPTION HANDLING QUALITY SCAN")
        self.log("=" * 70)

        self.violations = self.scan_directory()

        self.log("=" * 70)
        if self.violations:
            self.log(f"FOUND: {len(self.violations)} exception handling violations", 'WARNING')

            by_severity = self._group_by_severity()
            self.log(f"\nBy Severity:", 'INFO')
            for severity in ['critical', 'high', 'medium', 'low']:
                count = by_severity.get(severity, 0)
                if count > 0:
                    self.log(f"  {severity.upper()}: {count}", 'WARNING')

            by_type = self._group_by_type()
            self.log(f"\nBy Type:", 'INFO')
            for vtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
                self.log(f"  {vtype}: {count}", 'WARNING')

            return False
        else:
            self.log("SUCCESS: No exception handling violations found", 'SUCCESS')
            return True


def main():
    parser = argparse.ArgumentParser(
        description='Scan for exception handling violations'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--json', type=str,
                        help='Output JSON report to file')
    parser.add_argument('--markdown', type=str,
                        help='Output markdown report to file')
    parser.add_argument('--ci', action='store_true',
                        help='CI mode: strict exit codes')

    args = parser.parse_args()

    # Create scanner
    scanner = ExceptionScanner(verbose=args.verbose or args.ci)

    # Run scan
    passed = scanner.run_scan()

    # Generate reports
    if args.json:
        scanner.generate_json_report(args.json)

    if args.markdown:
        scanner.generate_markdown_report(args.markdown)

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
