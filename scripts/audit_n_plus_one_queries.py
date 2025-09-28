#!/usr/bin/env python
"""
N+1 Query Detection and Audit Script

This script analyzes the codebase to detect N+1 query patterns and generate
a comprehensive report of optimization opportunities.

Complies with Rule #12 (Database Query Optimization)

Usage:
    python scripts/audit_n_plus_one_queries.py
    python scripts/audit_n_plus_one_queries.py --fix --dry-run
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class N1QueryAuditor:
    """Detects and reports N+1 query patterns in Django codebase"""

    def __init__(self, apps_dir: Path):
        self.apps_dir = apps_dir
        self.violations = defaultdict(list)
        self.optimized_patterns = []
        self.stats = {
            'total_files_scanned': 0,
            'files_with_violations': 0,
            'total_violations': 0,
            'optimized_queries': 0,
        }

    def scan_file(self, filepath: Path) -> List[Dict]:
        """Scan a single Python file for N+1 query patterns"""
        violations = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # Pattern 1: .all() without select_related/prefetch_related in same method
            all_pattern = re.compile(r'\.objects\.all\(\)')
            filter_pattern = re.compile(r'\.objects\.filter\(')
            select_related_pattern = re.compile(r'select_related\(')
            prefetch_related_pattern = re.compile(r'prefetch_related\(')

            for i, line in enumerate(lines, 1):
                # Check for .all() or .filter() calls
                if all_pattern.search(line) or filter_pattern.search(line):
                    # Check if next 5 lines have optimization
                    context_lines = '\n'.join(lines[max(0, i-1):min(len(lines), i+5)])

                    has_select_related = select_related_pattern.search(context_lines)
                    has_prefetch_related = prefetch_related_pattern.search(context_lines)

                    if not has_select_related and not has_prefetch_related:
                        violations.append({
                            'file': str(filepath.relative_to(PROJECT_ROOT)),
                            'line': i,
                            'code': line.strip(),
                            'type': 'missing_optimization',
                            'severity': 'high' if '.all()' in line else 'medium',
                        })

            # Pattern 2: ListView without get_queryset optimization
            listview_pattern = re.compile(r'class\s+\w+\(.*ListView.*\):')
            get_queryset_pattern = re.compile(r'def get_queryset\(')

            in_listview = False
            listview_name = None
            listview_line = 0

            for i, line in enumerate(lines, 1):
                if listview_pattern.search(line):
                    in_listview = True
                    listview_name = line.split('class')[1].split('(')[0].strip()
                    listview_line = i
                elif in_listview and (line.startswith('class ') or i > listview_line + 50):
                    # Check if we found get_queryset
                    context = '\n'.join(lines[listview_line:i])
                    if not get_queryset_pattern.search(context):
                        violations.append({
                            'file': str(filepath.relative_to(PROJECT_ROOT)),
                            'line': listview_line,
                            'code': listview_name,
                            'type': 'listview_without_queryset',
                            'severity': 'critical',
                        })
                    in_listview = False

            # Pattern 3: Admin list_display without list_select_related
            admin_pattern = re.compile(r'class\s+\w+\(.*ModelAdmin.*\):')
            list_display_pattern = re.compile(r'list_display\s*=')
            list_select_related_pattern = re.compile(r'list_select_related\s*=')

            in_admin = False
            admin_line = 0
            admin_name = None

            for i, line in enumerate(lines, 1):
                if admin_pattern.search(line):
                    in_admin = True
                    admin_line = i
                    admin_name = line.split('class')[1].split('(')[0].strip()
                elif in_admin and (line.startswith('class ') or i > admin_line + 100):
                    context = '\n'.join(lines[admin_line:i])
                    if list_display_pattern.search(context) and not list_select_related_pattern.search(context):
                        violations.append({
                            'file': str(filepath.relative_to(PROJECT_ROOT)),
                            'line': admin_line,
                            'code': admin_name,
                            'type': 'admin_without_select_related',
                            'severity': 'high',
                        })
                    in_admin = False

            # Check for optimized patterns (for positive reporting)
            if select_related_pattern.search(content) or prefetch_related_pattern.search(content):
                self.stats['optimized_queries'] += 1

        except (UnicodeDecodeError, IOError) as e:
            print(f"Error reading {filepath}: {e}")

        return violations

    def scan_directory(self):
        """Scan all Python files in apps directory"""
        for root, dirs, files in os.walk(self.apps_dir):
            # Skip migrations, tests, and __pycache__
            dirs[:] = [d for d in dirs if d not in ['migrations', '__pycache__', 'node_modules', '.git']]

            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    filepath = Path(root) / file
                    self.stats['total_files_scanned'] += 1

                    violations = self.scan_file(filepath)
                    if violations:
                        self.violations[str(filepath)] = violations
                        self.stats['files_with_violations'] += 1
                        self.stats['total_violations'] += len(violations)

    def generate_report(self) -> str:
        """Generate comprehensive audit report"""
        report = []
        report.append("=" * 80)
        report.append("N+1 QUERY AUDIT REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary statistics
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Files scanned: {self.stats['total_files_scanned']}")
        report.append(f"Files with violations: {self.stats['files_with_violations']}")
        report.append(f"Total violations found: {self.stats['total_violations']}")
        report.append(f"Optimized queries found: {self.stats['optimized_queries']}")
        report.append("")

        # Violations by severity
        severity_counts = defaultdict(int)
        for violations in self.violations.values():
            for v in violations:
                severity_counts[v['severity']] += 1

        report.append("VIOLATIONS BY SEVERITY")
        report.append("-" * 80)
        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in severity_counts:
                report.append(f"{severity.upper()}: {severity_counts[severity]}")
        report.append("")

        # Detailed violations
        report.append("DETAILED VIOLATIONS")
        report.append("-" * 80)

        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        sorted_violations = []

        for filepath, violations in self.violations.items():
            for v in violations:
                sorted_violations.append((filepath, v))

        sorted_violations.sort(key=lambda x: (severity_order.get(x[1]['severity'], 999), x[0], x[1]['line']))

        for filepath, violation in sorted_violations:
            report.append(f"\n[{violation['severity'].upper()}] {filepath}:{violation['line']}")
            report.append(f"Type: {violation['type']}")
            report.append(f"Code: {violation['code']}")

        report.append("")
        report.append("=" * 80)
        report.append("RECOMMENDATIONS")
        report.append("=" * 80)
        report.append("")
        report.append("1. Add select_related() for ForeignKey fields accessed in templates")
        report.append("2. Add prefetch_related() for reverse ForeignKey and ManyToMany fields")
        report.append("3. Implement get_queryset() in all ListView classes")
        report.append("4. Add list_select_related in ModelAdmin classes with list_display")
        report.append("5. Use Django Debug Toolbar or django-silk to verify query counts")
        report.append("")

        return "\n".join(report)

    def save_report(self, output_file: Path):
        """Save report to file"""
        report = self.generate_report()
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_file}")


def main():
    """Main execution function"""
    apps_dir = PROJECT_ROOT / 'apps'

    if not apps_dir.exists():
        print(f"Error: Apps directory not found at {apps_dir}")
        sys.exit(1)

    print("Starting N+1 Query Audit...")
    print(f"Scanning: {apps_dir}")
    print()

    auditor = N1QueryAuditor(apps_dir)
    auditor.scan_directory()

    # Print report to console
    print(auditor.generate_report())

    # Save to file
    output_file = PROJECT_ROOT / 'N_PLUS_ONE_AUDIT_REPORT.md'
    auditor.save_report(output_file)


if __name__ == '__main__':
    main()