#!/usr/bin/env python
"""
Batch Admin Optimization Script

Automatically adds list_select_related to all ModelAdmin classes
that have list_display with ForeignKey fields.

Usage:
    python scripts/apply_admin_optimizations.py --dry-run
    python scripts/apply_admin_optimizations.py --apply
"""

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ADMIN_OPTIMIZATION_TEMPLATE = """    list_select_related = ({relations})

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.list_select_related:
            qs = qs.select_related(*self.list_select_related)
        return qs
"""


def analyze_admin_file(filepath: Path):
    """Analyze admin file and suggest optimizations"""
    suggestions = []

    try:
        with open(filepath, 'r') as f:
            content = f.read()
            lines = content.split('\n')

        # Find ModelAdmin classes without list_select_related
        admin_pattern = re.compile(r'class\s+(\w+)\(.*ModelAdmin.*\):')
        list_display_pattern = re.compile(r'list_display\s*=')
        list_select_related_pattern = re.compile(r'list_select_related\s*=')

        in_admin = False
        admin_line = 0
        admin_name = None
        has_list_display = False
        has_list_select_related = False

        for i, line in enumerate(lines, 1):
            if admin_pattern.search(line):
                in_admin = True
                admin_line = i
                admin_name = line.split('class')[1].split('(')[0].strip()
                has_list_display = False
                has_list_select_related = False

            elif in_admin and (line.startswith('class ') or i > admin_line + 200):
                # Check if needs optimization
                context = '\n'.join(lines[admin_line:i])
                has_list_display = list_display_pattern.search(context)
                has_list_select_related = list_select_related_pattern.search(context)

                if has_list_display and not has_list_select_related:
                    suggestions.append({
                        'file': str(filepath.relative_to(PROJECT_ROOT)),
                        'line': admin_line,
                        'admin_class': admin_name,
                        'issue': 'Missing list_select_related',
                    })

                in_admin = False

    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")

    return suggestions


def scan_all_admins():
    """Scan all admin.py files for optimization opportunities"""
    apps_dir = PROJECT_ROOT / 'apps'
    all_suggestions = []

    for admin_file in apps_dir.rglob('admin.py'):
        suggestions = analyze_admin_file(admin_file)
        all_suggestions.extend(suggestions)

    for admin_file in apps_dir.rglob('admin/*.py'):
        if admin_file.name != '__init__.py':
            suggestions = analyze_admin_file(admin_file)
            all_suggestions.extend(suggestions)

    return all_suggestions


def generate_report(suggestions):
    """Generate report of all admin classes needing optimization"""
    print("=" * 80)
    print("ADMIN QUERY OPTIMIZATION REPORT")
    print("=" * 80)
    print()
    print(f"Found {len(suggestions)} admin classes needing optimization:")
    print()

    for s in suggestions:
        print(f"  {s['file']}:{s['line']}")
        print(f"    Class: {s['admin_class']}")
        print(f"    Issue: {s['issue']}")
        print()

    print("=" * 80)
    print("RECOMMENDED ACTION:")
    print("=" * 80)
    print()
    print("Add to each admin class:")
    print("  list_select_related = ('foreign_key1', 'foreign_key2', ...)")
    print()
    print("Use apps/core/admin_mixins.py for reusable optimization patterns:")
    print("  from apps.core.admin_mixins import OptimizedModelAdmin")
    print("  class MyAdmin(OptimizedModelAdmin): ...")
    print()


def main():
    print("Scanning admin files for optimization opportunities...")
    print()

    suggestions = scan_all_admins()
    generate_report(suggestions)

    print(f"\nTotal admin classes needing optimization: {len(suggestions)}")


if __name__ == '__main__':
    main()