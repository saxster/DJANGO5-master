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
    # Workflow compatibility:
    python scripts/exception_scanner.py --path apps --format json --output scan_report.json
    python scripts/exception_scanner.py --path apps --priority-list --output PRIORITY_FIX_LIST.md

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
from typing import List, Dict, Set
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
        # ast.Module in Python 3.8+ requires type_ignores=[]
        module = ast.Module(body=body, type_ignores=[])
        for stmt in ast.walk(module):
            if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute):
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
        line_number = getattr(node, 'lineno', 0)

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
        lines = self.source_lines[start:end]
        return '\n'.join(line[:80] for line in lines if line.strip())


class ExceptionScanner:
    """Scans codebase for exception handling violations"""

    def __init__(self, root_dir: str = '.', verbose: bool = False, scan_path: str = 'apps'):
        self.root_dir = Path(root_dir).resolve()
        self.verbose = verbose
        self.scan_path = scan_path
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

        target_dir = self.root_dir / self.scan_path
        if not target_dir.exists():
            self.log(f"{self.scan_path}/ directory not found", 'WARNING')
            return []

        py_files = []
        for py_file in target_dir.rglob('*.py'):
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

    def _group_by_severity(self) -> Dict[str, int]:
        """Group violations by severity (lowercase keys)"""
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

    def _compute_statistics(self) -> Dict:
        """Compute statistics in the shape expected by the workflow"""
        total = len(self.violations)
        files = self._group_by_file()
        affected_files = len(files.keys())

        # Map lowercase severities to uppercase risk levels
        by_sev = self._group_by_severity()
        by_risk_level = {
            'CRITICAL': by_sev.get('critical', 0),
            'HIGH': by_sev.get('high', 0),
            'MEDIUM': by_sev.get('medium', 0),
            'LOW': by_sev.get('low', 0),
        }

        return {
            'total_occurrences': total,
            'affected_files': affected_files,
            'by_risk_level': by_risk_level,
        }

    def generate_json_report(self, output_path: str):
        """Generate JSON report with violation metadata (workflow-compatible)"""
        stats = self._compute_statistics()
        report = {
            'metadata': {
                'tool': 'exception_scanner',
                'version': '1.0.0',
                'total_occurrences': stats['total_occurrences'],
            },
            'statistics': stats,
            'by_type': self._group_by_type(),
            'by_file': {
                f: [asdict(v) for v in vs] for f, vs in self._group_by_file().items()
            },
            'violations': [asdict(v) for v in self.violations],
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        self.log(f"JSON report written to {output_path}", 'SUCCESS')

    def generate_markdown_report(self, output_path: str):
        """Generate markdown summary report"""
        stats = self._compute_statistics()
        with open(output_path, 'w') as f:
            f.write("# Exception Handling Violations Report\n\n")
            f.write(f"**Total Violations**: {stats['total_occurrences']}\n\n")
            f.write(f"**Affected Files**: {stats['affected_files']}\n\n")

            # By risk level
            f.write("## Violations by Risk Level\n\n")
            for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = stats['by_risk_level'].get(level, 0)
                f.write(f"- **{level}**: {count}\n")

            # Priority files
            f.write("\n## Priority Files (Most Violations)\n\n")
            by_file = self._group_by_file()
            sorted_files = sorted(by_file.items(), key=lambda x: -len(x[1]))[:20]
            for filepath, violations in sorted_files:
                f.write(f"\n### {filepath} ({len(violations)} violations)\n\n")
                for v in violations[:5]:  # Top 5 per file
                    f.write(f"- Line {v.line_number}: {v.violation_type} - {v.exception_type}\n")

        self.log(f"Markdown report written to {output_path}", 'SUCCESS')

    def generate_priority_list_markdown(self, output_path: str, top_files: int = 25):
        """Generate a prioritized fix list markdown"""
        stats = self._compute_statistics()
        by_file = self._group_by_file()
        # Sort files by number of violations, then by presence of higher severity
        def file_score(vs: List[ExceptionViolation]):
            sev_weight = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
            return sum(sev_weight.get(v.severity, 1) for v in vs)

        sorted_files = sorted(
            by_file.items(),
            key=lambda item: (file_score(item[1]), len(item[1])),
            reverse=True
        )[:top_files]

        with open(output_path, 'w') as f:
            f.write("# Priority Fix List: Exception Handling\n\n")
            f.write(f"- Total Violations: {stats['total_occurrences']}\n")
            f.write(f"- Affected Files: {stats['affected_files']}\n\n")
            f.write("## Top Files to Fix\n")
            rank = 1
            for filepath, violations in sorted_files:
                counts = defaultdict(int)
                for v in violations:
                    counts[v.severity] += 1
                f.write(
                    f"\n{rank}. {filepath} — {len(violations)} issues \
                    (critical: {counts.get('critical',0)}, high: {counts.get('high',0)}, \
                    medium: {counts.get('medium',0)}, low: {counts.get('low',0)})\n"
                )
                # Show a few concrete lines to start
                for v in violations[:5]:
                    f.write(f"   - L{v.line_number}: {v.violation_type} ({v.exception_type})\n")
                rank += 1

        self.log(f"Priority fix list written to {output_path}", 'SUCCESS')

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

    # Workflow compatibility flags
    parser.add_argument('--path', type=str, default='apps',
                        help='Directory to scan (relative to repo root). Default: apps')
    parser.add_argument('--format', type=str, choices=['json', 'markdown'],
                        help='Output format to use with --output')
    parser.add_argument('--output', type=str,
                        help='Output file path to use with --format')
    parser.add_argument('--priority-list', action='store_true',
                        help='Generate a prioritized fix list markdown to --output')

    args = parser.parse_args()

    # Create scanner
    scanner = ExceptionScanner(verbose=args.verbose or args.ci, scan_path=args.path)

    # Run scan
    passed = scanner.run_scan()

    # Generate reports (legacy flags)
    if args.json:
        scanner.generate_json_report(args.json)

    if args.markdown:
        scanner.generate_markdown_report(args.markdown)

    # Generate reports (workflow compatibility flags)
    if args.output:
        if args.priority_list:
            scanner.generate_priority_list_markdown(args.output)
        elif args.format == 'json':
            scanner.generate_json_report(args.output)
        elif args.format == 'markdown':
            scanner.generate_markdown_report(args.output)

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()