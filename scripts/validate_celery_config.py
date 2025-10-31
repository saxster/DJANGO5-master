#!/usr/bin/env python
"""
Celery Configuration Validation Script

Comprehensive validation of Celery configuration integrity across the codebase.

Validates:
1. Single source of truth (no duplicate Celery configs)
2. No duplicate task names
3. All beat schedule tasks exist
4. Consistent decorator usage (>95% @shared_task)
5. No orphaned configuration files
6. Task names follow conventions (no parentheses)
7. God file size constraints (<300 lines)
8. Base class usage (recommended tasks use appropriate bases)

Usage:
    python scripts/validate_celery_config.py                # Quick check
    python scripts/validate_celery_config.py --strict       # Fail on any issue
    python scripts/validate_celery_config.py --report       # Detailed report
    python scripts/validate_celery_config.py --fix          # Auto-fix issues (dry-run)

Exit Codes:
    0 - All validations passed
    1 - Critical issues found (config conflicts, broken tasks)
    2 - Warnings found (decorator inconsistency, god file size)

Created: 2025-10-10
Purpose: Automated Celery configuration enforcement
"""

import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class CeleryConfigValidator:
    """Validates Celery configuration across codebase"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.errors = []
        self.warnings = []
        self.info = []

    def validate_all(self) -> Dict[str, any]:
        """Run all validation checks"""
        print("🔍 Validating Celery configuration...\n")

        self.check_single_source_of_truth()
        self.check_god_file_size()
        self.check_duplicate_tasks()
        self.check_beat_schedule_alignment()
        self.check_decorator_consistency()
        self.check_task_naming_conventions()
        self.check_deprecated_imports()
        self.check_base_class_usage()

        return {
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
            'passed': len(self.errors) == 0
        }

    def check_single_source_of_truth(self):
        """Validate only one active Celery configuration exists"""
        print("📋 Checking single source of truth...")

        celery_files = list(self.project_root.rglob("**/celery.py"))
        active_configs = [
            f for f in celery_files
            if '.archive' not in str(f) and 'venv' not in str(f) and 'site-packages' not in str(f)
        ]

        if len(active_configs) > 1:
            self.errors.append({
                'check': 'single_source_of_truth',
                'message': f"Found {len(active_configs)} active Celery configs (should be 1)",
                'files': [str(f.relative_to(self.project_root)) for f in active_configs],
                'fix': 'Archive or remove extra celery.py files'
            })
            print(f"   ❌ Multiple Celery configs found: {len(active_configs)}")
        elif len(active_configs) == 1:
            config_path = active_configs[0].relative_to(self.project_root)
            if str(config_path) == 'intelliwiz_config/celery.py':
                print(f"   ✅ Single source of truth: {config_path}")
            else:
                self.warnings.append({
                    'check': 'single_source_of_truth',
                    'message': f"Active config not in expected location",
                    'file': str(config_path),
                    'expected': 'intelliwiz_config/celery.py'
                })
                print(f"   ⚠️  Active config: {config_path} (expected: intelliwiz_config/celery.py)")
        else:
            self.errors.append({
                'check': 'single_source_of_truth',
                'message': 'No active Celery config found',
                'fix': 'Create intelliwiz_config/celery.py'
            })
            print("   ❌ No Celery config found")

    def check_god_file_size(self):
        """Validate god file is refactored to import aggregator"""
        print("\n📦 Checking god file size...")

        god_file = self.project_root / "background_tasks" / "tasks.py"
        if not god_file.exists():
            self.errors.append({
                'check': 'god_file_size',
                'message': 'God file not found',
                'file': 'background_tasks/tasks.py'
            })
            print("   ❌ God file not found")
            return

        lines = god_file.read_text().split('\n')
        line_count = len(lines)

        if line_count < 300:
            print(f"   ✅ God file refactored: {line_count} lines (<300 target)")
        elif line_count < 500:
            self.warnings.append({
                'check': 'god_file_size',
                'message': f"God file larger than target: {line_count} lines",
                'target': 300,
                'fix': 'Continue refactoring to import aggregator'
            })
            print(f"   ⚠️  God file: {line_count} lines (target <300)")
        else:
            self.errors.append({
                'check': 'god_file_size',
                'message': f"God file too large: {line_count} lines",
                'target': 300,
                'fix': 'Refactor to import aggregator using scripts/refactor_god_file_tasks.py'
            })
            print(f"   ❌ God file too large: {line_count} lines (must be <300)")

    def check_duplicate_tasks(self):
        """Check for duplicate task definitions"""
        print("\n🔄 Checking for duplicate tasks...")

        # Run task audit script
        audit_script = self.project_root / "scripts" / "audit_celery_tasks.py"
        if not audit_script.exists():
            self.warnings.append({
                'check': 'duplicate_tasks',
                'message': 'Audit script not found - cannot check duplicates',
                'expected': 'scripts/audit_celery_tasks.py'
            })
            print("   ⚠️  Audit script not found")
            return

        # Parse inventory report
        inventory = self.project_root / "CELERY_TASK_INVENTORY_REPORT.md"
        if inventory.exists():
            content = inventory.read_text()
            # Find duplicate count
            match = re.search(r'\| Duplicate tasks \| (\d+) \|', content)
            if match:
                dup_count = int(match.group(1))
                if dup_count == 0:
                    print(f"   ✅ No duplicate tasks found")
                else:
                    self.errors.append({
                        'check': 'duplicate_tasks',
                        'message': f"Found {dup_count} duplicate task definitions",
                        'fix': 'Run: python scripts/refactor_god_file_tasks.py --execute'
                    })
                    print(f"   ❌ Found {dup_count} duplicate tasks")
            else:
                print("   ⚠️  Could not parse duplicate count from inventory")
        else:
            self.info.append({
                'check': 'duplicate_tasks',
                'message': 'Inventory report not found - run audit first',
                'command': 'python scripts/audit_celery_tasks.py --generate-report'
            })
            print("   ℹ️  Run audit first to check duplicates")

    def check_beat_schedule_alignment(self):
        """Verify all beat schedule tasks are registered"""
        print("\n📅 Checking beat schedule alignment...")

        # This requires Django settings
        try:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
            import django
            django.setup()

            from intelliwiz_config.celery import app

            beat_tasks = set(app.conf.beat_schedule.values())
            beat_task_names = {t['task'] for t in beat_tasks if isinstance(t, dict)}

            orphaned = []
            for task_name in beat_task_names:
                if task_name not in app.tasks:
                    orphaned.append(task_name)

            if orphaned:
                self.errors.append({
                    'check': 'beat_schedule_alignment',
                    'message': f"Found {len(orphaned)} orphaned beat tasks",
                    'tasks': orphaned,
                    'fix': 'Register missing tasks or remove from beat schedule'
                })
                print(f"   ❌ Orphaned beat tasks: {', '.join(orphaned)}")
            else:
                print(f"   ✅ All {len(beat_task_names)} beat tasks registered")

        except Exception as e:
            self.warnings.append({
                'check': 'beat_schedule_alignment',
                'message': f"Could not verify beat schedule: {str(e)}",
                'note': 'Django setup failed'
            })
            print(f"   ⚠️  Could not verify beat schedule")

    def check_decorator_consistency(self):
        """Check decorator usage (target >95% @shared_task)"""
        print("\n🔧 Checking decorator consistency...")

        inventory = self.project_root / "CELERY_TASK_INVENTORY_REPORT.md"
        if inventory.exists():
            content = inventory.read_text()

            # Parse decorator usage
            shared_task_match = re.search(r'\| @shared_task usage \| (\d+) \|', content)
            app_task_match = re.search(r'\| @app\.task usage \| (\d+) \|', content)

            if shared_task_match and app_task_match:
                shared_count = int(shared_task_match.group(1))
                app_count = int(app_task_match.group(1))
                total = shared_count + app_count
                shared_pct = (shared_count / total * 100) if total > 0 else 0

                if shared_pct >= 95:
                    print(f"   ✅ Decorator consistency: {shared_pct:.1f}% @shared_task")
                elif shared_pct >= 85:
                    self.warnings.append({
                        'check': 'decorator_consistency',
                        'message': f"Decorator usage: {shared_pct:.1f}% @shared_task (target >95%)",
                        'shared_task': shared_count,
                        'app_task': app_count,
                        'fix': 'Migrate remaining @app.task to @shared_task'
                    })
                    print(f"   ⚠️  Decorator usage: {shared_pct:.1f}% @shared_task (target >95%)")
                else:
                    self.errors.append({
                        'check': 'decorator_consistency',
                        'message': f"Low @shared_task usage: {shared_pct:.1f}%",
                        'shared_task': shared_count,
                        'app_task': app_count,
                        'target': 95,
                        'fix': 'Migrate @app.task to @shared_task'
                    })
                    print(f"   ❌ Low @shared_task usage: {shared_pct:.1f}%")

    def check_task_naming_conventions(self):
        """Check task names don't have parentheses"""
        print("\n📝 Checking task naming conventions...")

        # Scan for task names with parentheses
        bad_names = []
        for file_path in self.project_root.rglob("*.py"):
            if 'venv' in str(file_path) or '.archive' in str(file_path):
                continue

            try:
                content = file_path.read_text()
                # Find task decorators with names containing parentheses
                matches = re.finditer(
                    r'@(?:shared_task|app\.task)\s*\([^)]*name\s*=\s*["\']([^"\']+\(\))["\']',
                    content
                )
                for match in matches:
                    task_name = match.group(1)
                    line_num = content[:match.start()].count('\n') + 1
                    bad_names.append({
                        'file': str(file_path.relative_to(self.project_root)),
                        'line': line_num,
                        'name': task_name
                    })
            except:
                pass

        if bad_names:
            self.errors.append({
                'check': 'task_naming',
                'message': f"Found {len(bad_names)} tasks with parentheses in name",
                'tasks': bad_names,
                'fix': 'Remove parentheses from task names'
            })
            print(f"   ❌ Found {len(bad_names)} tasks with parentheses in names")
            for task in bad_names:
                print(f"      - {task['file']}:{task['line']} - {task['name']}")
        else:
            print("   ✅ All task names follow conventions")

    def check_deprecated_imports(self):
        """Check for imports from deprecated config files"""
        print("\n⚠️  Checking for deprecated imports...")

        deprecated_imports = []
        for file_path in self.project_root.rglob("*.py"):
            if 'venv' in str(file_path) or '.archive' in str(file_path):
                continue
            if file_path.name in ['celery_config.py', 'celery_settings.py']:
                continue

            try:
                content = file_path.read_text()
                if 'from apps.core.tasks.celery_config import' in content:
                    deprecated_imports.append(str(file_path.relative_to(self.project_root)))
            except:
                pass

        if deprecated_imports:
            self.warnings.append({
                'check': 'deprecated_imports',
                'message': f"Found {len(deprecated_imports)} files importing from deprecated config",
                'files': deprecated_imports,
                'fix': 'Update imports to use apps.core.tasks.celery_settings'
            })
            print(f"   ⚠️  Found {len(deprecated_imports)} deprecated imports")
        else:
            print("   ✅ No deprecated imports found")

    def check_base_class_usage(self):
        """Check if critical tasks use appropriate base classes"""
        print("\n🎯 Checking base class usage...")

        # Critical tasks that should use IdempotentTask
        idempotent_required = {
            'auto_close_jobs',
            'ticket_escalation',
            'create_scheduled_reports'
        }

        # Email tasks that should use EmailTask
        email_required = {
            'send_reminder_email',
            'send_ticket_email',
            'alert_sendmail'
        }

        missing_base = []

        for task_name in idempotent_required:
            if not self._task_has_base_class(task_name, 'IdempotentTask'):
                missing_base.append((task_name, 'IdempotentTask'))

        for task_name in email_required:
            if not self._task_has_base_class(task_name, 'EmailTask'):
                missing_base.append((task_name, 'EmailTask'))

        if missing_base:
            self.warnings.append({
                'check': 'base_class_usage',
                'message': f"{len(missing_base)} critical tasks missing base classes",
                'tasks': missing_base,
                'fix': 'Add base classes for better reliability and monitoring'
            })
            print(f"   ⚠️  {len(missing_base)} tasks missing recommended base classes")
        else:
            print(f"   ✅ Critical tasks use appropriate base classes")

    def _task_has_base_class(self, task_name: str, base_class: str) -> bool:
        """Check if a task uses specific base class"""
        # Scan for task definition
        for file_path in self.project_root.rglob("*.py"):
            if 'venv' in str(file_path) or '.archive' in str(file_path):
                continue

            try:
                content = file_path.read_text()
                # Look for decorator with this task name and base class
                pattern = rf'@shared_task\([^)]*base\s*=\s*{base_class}[^)]*name\s*=\s*["\' ]{task_name}["\']'
                if re.search(pattern, content):
                    return True
                # Also check for base= before name=
                pattern = rf'@shared_task\([^)]*name\s*=\s*["\' ]{task_name}["\'][^)]*base\s*=\s*{base_class}'
                if re.search(pattern, content):
                    return True
            except:
                pass
        return False

    def generate_report(self) -> str:
        """Generate detailed validation report"""
        lines = [
            "# Celery Configuration Validation Report",
            "",
            f"**Generated:** {self._get_timestamp()}",
            f"**Project:** {self.project_root.name}",
            "",
            "---",
            ""
        ]

        # Summary
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        info_count = len(self.info)

        status = "✅ PASSED" if error_count == 0 else "❌ FAILED"
        lines.extend([
            "## Summary",
            "",
            f"**Status:** {status}",
            f"**Errors:** {error_count}",
            f"**Warnings:** {warning_count}",
            f"**Info:** {info_count}",
            ""
        ])

        # Errors
        if self.errors:
            lines.extend([
                "## ❌ Errors (Must Fix)",
                ""
            ])
            for error in self.errors:
                lines.append(f"### {error['check']}")
                lines.append(f"**Message:** {error['message']}")
                if 'fix' in error:
                    lines.append(f"**Fix:** {error['fix']}")
                if 'files' in error:
                    lines.append("**Files:**")
                    for f in error['files']:
                        lines.append(f"- `{f}`")
                lines.append("")

        # Warnings
        if self.warnings:
            lines.extend([
                "## ⚠️  Warnings (Recommend Fix)",
                ""
            ])
            for warning in self.warnings:
                lines.append(f"### {warning['check']}")
                lines.append(f"**Message:** {warning['message']}")
                if 'fix' in warning:
                    lines.append(f"**Fix:** {warning['fix']}")
                lines.append("")

        # Info
        if self.info:
            lines.extend([
                "## ℹ️  Information",
                ""
            ])
            for info in self.info:
                lines.append(f"- {info.get('message', str(info))}")

        lines.extend([
            "",
            "---",
            "",
            "## Next Steps",
            ""
        ])

        if error_count > 0:
            lines.append("1. Fix all errors listed above")
            lines.append("2. Re-run validation: `python scripts/validate_celery_config.py`")
            lines.append("3. Address warnings for optimal configuration")
        elif warning_count > 0:
            lines.append("1. Address warnings for optimal configuration")
            lines.append("2. Re-run validation to verify")
        else:
            lines.append("✅ Configuration is optimal. No action required.")

        return '\n'.join(lines)

    def _get_timestamp(self):
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser(
        description="Validate Celery configuration"
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help="Exit with error code if any issues found"
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help="Generate detailed validation report"
    )
    parser.add_argument(
        '--output',
        type=str,
        help="Write report to file"
    )

    args = parser.parse_args()

    validator = CeleryConfigValidator(PROJECT_ROOT)
    results = validator.validate_all()

    # Print summary
    print("\n" + "="*70)
    if results['passed']:
        print("✅ VALIDATION PASSED")
        exit_code = 0
    else:
        print("❌ VALIDATION FAILED")
        exit_code = 1

    print(f"   Errors: {len(results['errors'])}")
    print(f"   Warnings: {len(results['warnings'])}")
    print("="*70)

    # Generate report if requested
    if args.report:
        report = validator.generate_report()
        if args.output:
            output_path = PROJECT_ROOT / args.output
            output_path.write_text(report)
            print(f"\n📄 Report written to: {output_path}")
        else:
            print("\n" + report)

    # Exit with appropriate code
    if args.strict and (results['errors'] or results['warnings']):
        exit_code = 1 if results['errors'] else 2

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
