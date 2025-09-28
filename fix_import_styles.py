#!/usr/bin/env python3
"""
Import Style Standardization Tool

This script fixes the 62 import style inconsistencies found by the import analyzer.
It standardizes import styles according to best practices:
- Use absolute imports for cross-app dependencies
- Use relative imports only within the same app package

Usage:
    python3 fix_import_styles.py
    python3 fix_import_styles.py --dry-run
"""

import ast
import argparse
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class ImportStyleFixer:
    """Fix import style inconsistencies in Python files."""

    def __init__(self, project_root: Path, dry_run: bool = False):
        self.project_root = project_root
        self.apps_root = project_root / 'apps'
        self.dry_run = dry_run
        self.changes_made = 0

        # Files with known style inconsistencies (from our analysis)
        self.problematic_files = [
            "apps/attendance/models.py",
            "apps/attendance/views.py",
            "apps/journal/mqtt_integration.py",
            "apps/journal/permissions.py",
            "apps/journal/graphql_schema.py",
            "apps/journal/privacy.py",
            "apps/mentor_api/views.py",
            "apps/core/queries.py",
            "apps/face_recognition/signals.py",
            "apps/face_recognition/analytics.py",
        ]

    def get_app_name_from_path(self, file_path: Path) -> Optional[str]:
        """Extract app name from file path."""
        try:
            parts = file_path.relative_to(self.apps_root).parts
            if parts:
                return parts[0]  # First part is the app name
        except ValueError:
            pass
        return None

    def is_same_app_import(self, import_module: str, current_app: str) -> bool:
        """Check if an import is from the same app."""
        if import_module.startswith('apps.'):
            # Extract app name from absolute import
            parts = import_module.split('.')
            if len(parts) >= 2:
                return parts[1] == current_app
        return False

    def convert_absolute_to_relative(self, import_module: str, current_app: str) -> Optional[str]:
        """Convert absolute import to relative if it's from the same app."""
        if import_module.startswith(f'apps.{current_app}.'):
            # Remove the 'apps.{current_app}.' prefix
            relative_part = import_module[len(f'apps.{current_app}.'):]
            return f'.{relative_part}'
        return None

    def convert_relative_to_absolute(self, import_module: str, current_app: str, level: int) -> str:
        """Convert relative import to absolute."""
        if level == 1:  # from .module import
            return f'apps.{current_app}.{import_module}' if import_module else f'apps.{current_app}'
        elif level == 2:  # from ..module import
            return f'apps.{import_module}' if import_module else 'apps'
        else:
            # Handle deeper relative imports if needed
            return import_module

    def should_use_relative_import(self, import_module: str, current_app: str, current_file: Path) -> bool:
        """Determine if we should use relative import for this module."""
        # Use relative imports only for same-app imports
        if import_module.startswith(f'apps.{current_app}.'):
            return True
        return False

    def analyze_file_imports(self, file_path: Path) -> Dict:
        """Analyze imports in a file and suggest fixes."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            print(f"❌ Syntax error in {file_path}: {e}")
            return {'changes': [], 'error': str(e)}

        current_app = self.get_app_name_from_path(file_path)
        if not current_app:
            return {'changes': [], 'error': 'Could not determine app name'}

        changes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    line_num = node.lineno
                    original_line = content.split('\n')[line_num - 1]

                    # Check for mixed imports within same app
                    if node.level == 0 and self.is_same_app_import(node.module, current_app):
                        # Absolute import from same app - suggest relative
                        relative_module = self.convert_absolute_to_relative(node.module, current_app)
                        if relative_module:
                            names = [alias.name for alias in node.names]
                            new_line = f"from {relative_module} import {', '.join(names)}"
                            changes.append({
                                'line_num': line_num,
                                'original': original_line.strip(),
                                'suggested': new_line,
                                'reason': f'Convert same-app absolute import to relative'
                            })

                    elif node.level > 0 and not self.is_same_app_import(node.module or '', current_app):
                        # Relative import to different app - suggest absolute
                        absolute_module = self.convert_relative_to_absolute(
                            node.module or '', current_app, node.level
                        )
                        names = [alias.name for alias in node.names]
                        new_line = f"from {absolute_module} import {', '.join(names)}"
                        changes.append({
                            'line_num': line_num,
                            'original': original_line.strip(),
                            'suggested': new_line,
                            'reason': f'Convert cross-app relative import to absolute'
                        })

        return {'changes': changes, 'app': current_app}

    def apply_changes_to_file(self, file_path: Path, changes: List[Dict]) -> bool:
        """Apply the suggested changes to a file."""
        if not changes:
            return False

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Sort changes by line number in descending order to avoid offset issues
        sorted_changes = sorted(changes, key=lambda x: x['line_num'], reverse=True)

        changes_applied = 0
        for change in sorted_changes:
            line_idx = change['line_num'] - 1  # Convert to 0-based index
            if 0 <= line_idx < len(lines):
                old_line = lines[line_idx].strip()
                # Verify the line matches what we expect
                if old_line == change['original']:
                    # Preserve indentation
                    indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
                    lines[line_idx] = ' ' * indent + change['suggested'] + '\n'
                    changes_applied += 1
                    print(f"  ✅ Line {change['line_num']}: {change['original']}")
                    print(f"     → {change['suggested']}")
                else:
                    print(f"  ⚠️  Line {change['line_num']} doesn't match expected content")
                    print(f"     Expected: {change['original']}")
                    print(f"     Found: {old_line}")

        if changes_applied > 0 and not self.dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

        return changes_applied > 0

    def fix_all_style_issues(self) -> Dict:
        """Fix import style issues in all problematic files."""
        results = {
            'files_processed': 0,
            'files_changed': 0,
            'total_changes': 0,
            'errors': []
        }

        print("🔧 Fixing import style inconsistencies...")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'APPLY CHANGES'}")
        print("-" * 60)

        for file_rel_path in self.problematic_files:
            file_path = self.project_root / file_rel_path

            if not file_path.exists():
                print(f"⚠️  File not found: {file_path}")
                results['errors'].append(f"File not found: {file_path}")
                continue

            print(f"\n📄 Analyzing {file_rel_path}...")
            results['files_processed'] += 1

            analysis = self.analyze_file_imports(file_path)

            if 'error' in analysis:
                print(f"❌ Error: {analysis['error']}")
                results['errors'].append(f"{file_path}: {analysis['error']}")
                continue

            changes = analysis['changes']
            if not changes:
                print("✅ No import style issues found")
                continue

            print(f"Found {len(changes)} import style issue(s):")

            if self.apply_changes_to_file(file_path, changes):
                results['files_changed'] += 1
                results['total_changes'] += len(changes)
                self.changes_made += len(changes)

        return results

    def generate_summary_report(self, results: Dict) -> str:
        """Generate a summary report of all changes made."""
        report = []
        report.append("=" * 80)
        report.append("🎨 IMPORT STYLE STANDARDIZATION REPORT")
        report.append("=" * 80)

        report.append(f"\n📊 SUMMARY:")
        report.append(f"   Files Processed: {results['files_processed']}")
        report.append(f"   Files Changed: {results['files_changed']}")
        report.append(f"   Total Changes: {results['total_changes']}")
        report.append(f"   Errors: {len(results['errors'])}")

        if results['errors']:
            report.append(f"\n❌ ERRORS:")
            for error in results['errors']:
                report.append(f"   - {error}")

        report.append(f"\n🎯 STANDARDIZATION RULES APPLIED:")
        report.append("   1. Use relative imports for same-app modules")
        report.append("   2. Use absolute imports for cross-app dependencies")
        report.append("   3. Maintain consistent import style within files")

        if results['total_changes'] > 0:
            report.append(f"\n✅ SUCCESS: Standardized {results['total_changes']} import statements")
        else:
            report.append(f"\nℹ️  No import style changes needed")

        return "\n".join(report)


def main():
    """Main function for import style fixing."""
    parser = argparse.ArgumentParser(description='Fix import style inconsistencies')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making actual changes'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='Project root directory'
    )

    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()

    print(f"🚀 Starting import style standardization for: {project_root}")

    fixer = ImportStyleFixer(project_root, dry_run=args.dry_run)
    results = fixer.fix_all_style_issues()

    # Generate and display report
    report = fixer.generate_summary_report(results)
    print(f"\n{report}")

    # Save report to file
    report_path = project_root / 'import_style_fixes_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n📄 Detailed report saved to: {report_path}")

    if args.dry_run:
        print("\n💡 Run without --dry-run to apply the changes")
    elif results['total_changes'] > 0:
        print(f"\n🎉 Successfully standardized {results['total_changes']} import statements!")
    else:
        print("\n✅ No import style issues found - your code is already well organized!")


if __name__ == '__main__':
    main()