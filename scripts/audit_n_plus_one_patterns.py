#!/usr/bin/env python
"""
N+1 Query Pattern Audit Script.

Scans the codebase for potential N+1 query patterns and generates a detailed report.
This script helps identify remaining optimization opportunities after the initial fixes.

Usage:
    python scripts/audit_n_plus_one_patterns.py
    python scripts/audit_n_plus_one_patterns.py --app activity
    python scripts/audit_n_plus_one_patterns.py --fix

"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


class N1PatternDetector:
    """Detect N+1 query patterns in Python files."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.violations = []
        self.stats = {
            'files_scanned': 0,
            'violations_found': 0,
            'high_priority': 0,
            'medium_priority': 0,
            'low_priority': 0
        }

    N1_PATTERNS = [
        {
            'name': 'Naked .get(id=) in Views',
            'pattern': r'\.objects\.get\(id=',
            'priority': 'HIGH',
            'fix': 'Use manager.optimized_get_with_relations()',
            'check': lambda line: 'optimized' not in line and 'select_related' not in line
        },
        {
            'name': 'Naked .filter(id=).delete() in Views',
            'pattern': r'\.objects\.filter\(id=.*\)\.delete\(',
            'priority': 'HIGH',
            'fix': 'Use manager.optimized_delete_by_id()',
            'check': lambda line: 'optimized' not in line and 'select_related' not in line
        },
        {
            'name': '.values() with FK Fields',
            'pattern': r'\.values\([^)]*__[^)]*\)',
            'priority': 'MEDIUM',
            'fix': 'Add select_related() before .values()',
            'check': lambda context: 'select_related' not in context
        },
        {
            'name': 'Loop with .objects.get()',
            'pattern': r'for .* in .*:.*\.objects\.get\(',
            'priority': 'CRITICAL',
            'fix': 'Use .select_related() and fetch all at once, or use DataLoaders',
            'check': lambda line: True
        },
        {
            'name': '.all() without optimization in Views',
            'pattern': r'\.objects\.all\(\)',
            'priority': 'MEDIUM',
            'fix': 'Use select_related()/prefetch_related()',
            'check': lambda context: 'select_related' not in context and 'prefetch_related' not in context
        }
    ]

    def scan_file(self, file_path: Path) -> List[Dict]:
        """Scan a single file for N+1 patterns."""
        violations = []

        if not file_path.suffix == '.py':
            return violations

        if file_path.name.startswith('test_') or '/tests/' in str(file_path):
            return violations

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                for pattern_def in self.N1_PATTERNS:
                    if re.search(pattern_def['pattern'], line):
                        context_start = max(0, i - 3)
                        context_end = min(len(lines), i + 3)
                        context = ''.join(lines[context_start:context_end])

                        if pattern_def['check'](context):
                            violations.append({
                                'file': str(file_path.relative_to(self.base_dir)),
                                'line': i,
                                'pattern_name': pattern_def['name'],
                                'priority': pattern_def['priority'],
                                'code_snippet': line.strip(),
                                'fix': pattern_def['fix']
                            })
                            self.stats['violations_found'] += 1

                            priority_key = f"{pattern_def['priority'].lower()}_priority"
                            if priority_key in self.stats:
                                self.stats[priority_key] += 1

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

        return violations

    def scan_directory(self, directory: Path, exclude_dirs: List[str] = None) -> None:
        """Recursively scan directory for N+1 patterns."""
        exclude_dirs = exclude_dirs or [
            'migrations', '__pycache__', '.git', 'tests',
            'venv', 'env', 'node_modules', '.pytest_cache'
        ]

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    self.stats['files_scanned'] += 1

                    file_violations = self.scan_file(file_path)
                    self.violations.extend(file_violations)

    def generate_report(self) -> str:
        """Generate comprehensive audit report."""
        report = []
        report.append("=" * 80)
        report.append("N+1 QUERY PATTERN AUDIT REPORT")
        report.append("=" * 80)
        report.append("")

        report.append("📊 STATISTICS:")
        report.append(f"   Files scanned: {self.stats['files_scanned']}")
        report.append(f"   Total violations: {self.stats['violations_found']}")
        report.append(f"   🔴 Critical priority: {self.stats.get('critical_priority', 0)}")
        report.append(f"   🔴 High priority: {self.stats['high_priority']}")
        report.append(f"   🟡 Medium priority: {self.stats['medium_priority']}")
        report.append(f"   🟢 Low priority: {self.stats.get('low_priority', 0)}")
        report.append("")

        if not self.violations:
            report.append("✅ NO N+1 QUERY PATTERNS DETECTED")
            report.append("")
            report.append("Your codebase follows query optimization best practices!")
            return "\n".join(report)

        violations_by_priority = {
            'CRITICAL': [],
            'HIGH': [],
            'MEDIUM': [],
            'LOW': []
        }

        for v in self.violations:
            priority = v['priority']
            if priority in violations_by_priority:
                violations_by_priority[priority].append(v)

        for priority in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            if violations_by_priority[priority]:
                report.append(f"\n{priority} PRIORITY VIOLATIONS:")
                report.append("-" * 80)

                for v in violations_by_priority[priority]:
                    report.append(f"\n📁 {v['file']}:{v['line']}")
                    report.append(f"   Pattern: {v['pattern_name']}")
                    report.append(f"   Code: {v['code_snippet']}")
                    report.append(f"   Fix: {v['fix']}")

        report.append("\n" + "=" * 80)
        report.append("RECOMMENDATIONS:")
        report.append("=" * 80)
        report.append("")
        report.append("1. Fix CRITICAL and HIGH priority violations immediately")
        report.append("2. Use manager optimized methods: optimized_get_with_relations()")
        report.append("3. Add select_related()/prefetch_related() to querysets")
        report.append("4. Review QueryOptimizer service in apps/core/services/")
        report.append("5. Run tests with @assert_max_queries decorator")
        report.append("6. Enable QueryPerformanceMonitoringMiddleware in development")
        report.append("")

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description='Audit codebase for N+1 query patterns'
    )
    parser.add_argument(
        '--app',
        type=str,
        help='Scan specific app only (e.g., activity, peoples)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='n_plus_one_audit_report.txt',
        help='Output report file path'
    )
    parser.add_argument(
        '--views-only',
        action='store_true',
        help='Scan only view files'
    )

    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent

    if args.app:
        scan_dir = base_dir / 'apps' / args.app
        if not scan_dir.exists():
            print(f"Error: App directory not found: {scan_dir}")
            sys.exit(1)
    else:
        scan_dir = base_dir / 'apps'

    if args.views_only:
        exclude_dirs = ['migrations', '__pycache__', '.git', 'tests',
                       'models', 'forms', 'managers', 'services']
    else:
        exclude_dirs = ['migrations', '__pycache__', '.git', 'tests']

    print(f"🔍 Scanning: {scan_dir}")
    print(f"📋 Excluding: {', '.join(exclude_dirs)}")
    print("")

    detector = N1PatternDetector(base_dir)
    detector.scan_directory(scan_dir, exclude_dirs)

    report = detector.generate_report()
    print(report)

    with open(base_dir / args.output, 'w') as f:
        f.write(report)

    print(f"\n📝 Report saved to: {args.output}")

    if detector.stats['violations_found'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()