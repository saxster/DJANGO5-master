#!/usr/bin/env python
"""
Task Migration Script - Automated Conversion to IdempotentTask

Helps migrate existing Celery tasks to use the new idempotency framework.

Usage:
    # Dry run (preview changes)
    python scripts/migrate_to_idempotent_tasks.py --dry-run

    # Migrate specific task
    python scripts/migrate_to_idempotent_tasks.py --task auto_close_jobs

    # Migrate all critical tasks
    python scripts/migrate_to_idempotent_tasks.py --category critical

    # Show migration recommendations
    python scripts/migrate_to_idempotent_tasks.py --analyze

Features:
- Detects current task patterns
- Recommends migration strategy (IdempotentTask vs decorator)
- Generates updated code
- Validates imports
- Creates backup before changes
"""

import os
import sys
import ast
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional


# Task categories and recommended TTL
TASK_CATEGORIES = {
    'critical': {
        'tasks': ['auto_close_jobs', 'ticket_escalation', 'create_ppm_job'],
        'ttl': 14400,  # 4 hours
        'base_class': 'IdempotentTask',
        'queue': 'critical'
    },
    'high_priority': {
        'tasks': ['create_job', 'send_reminder_email'],
        'ttl': 7200,  # 2 hours
        'base_class': 'IdempotentTask',
        'queue': 'high_priority'
    },
    'reports': {
        'tasks': ['create_scheduled_reports', 'send_generated_report_on_mail'],
        'ttl': 86400,  # 24 hours
        'base_class': 'IdempotentTask',
        'queue': 'reports'
    },
    'email': {
        'tasks': ['send_notification_email', 'send_alert_email'],
        'ttl': 7200,  # 2 hours
        'base_class': 'IdempotentTask',
        'queue': 'email'
    },
    'maintenance': {
        'tasks': ['move_media_to_cloud_storage', 'cleanup_reports_which_are_12hrs_old'],
        'ttl': 43200,  # 12 hours
        'base_class': 'MaintenanceTask',  # Already has idempotency through extension
        'queue': 'maintenance'
    }
}


class TaskMigrationAnalyzer:
    """Analyzes tasks and recommends migration strategy"""

    def __init__(self, task_files: List[str]):
        self.task_files = task_files
        self.tasks_found = {}

    def analyze(self) -> Dict[str, any]:
        """Analyze all task files and categorize tasks"""
        print("🔍 Analyzing task files...")

        for file_path in self.task_files:
            if not os.path.exists(file_path):
                print(f"⚠️  File not found: {file_path}")
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            tasks = self._extract_tasks(content, file_path)
            self.tasks_found.update(tasks)

        return self._categorize_tasks()

    def _extract_tasks(self, content: str, file_path: str) -> Dict[str, Dict]:
        """Extract task definitions from file"""
        tasks = {}

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if function has task decorator
                    for decorator in node.decorator_list:
                        decorator_name = self._get_decorator_name(decorator)
                        if decorator_name in ['shared_task', 'app.task', 'task']:
                            tasks[node.name] = {
                                'name': node.name,
                                'file': file_path,
                                'decorator': decorator_name,
                                'has_bind': self._has_bind_param(decorator),
                                'lineno': node.lineno,
                                'current_base': self._extract_base_class(decorator)
                            }

        except SyntaxError as e:
            print(f"⚠️  Syntax error in {file_path}: {e}")

        return tasks

    def _get_decorator_name(self, decorator) -> str:
        """Extract decorator name"""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{decorator.value.id}.{decorator.attr}"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return f"{decorator.func.value.id}.{decorator.func.attr}"
        return ""

    def _has_bind_param(self, decorator) -> bool:
        """Check if decorator has bind=True"""
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if keyword.arg == 'bind' and isinstance(keyword.value, ast.Constant):
                    return keyword.value.value
        return False

    def _extract_base_class(self, decorator) -> Optional[str]:
        """Extract base class from decorator"""
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if keyword.arg == 'base':
                    if isinstance(keyword.value, ast.Name):
                        return keyword.value.id
        return None

    def _categorize_tasks(self) -> Dict[str, any]:
        """Categorize tasks by priority and recommend migration"""
        categorized = {
            'critical': [],
            'high_priority': [],
            'reports': [],
            'email': [],
            'mutations': [],
            'maintenance': [],
            'uncategorized': []
        }

        for task_name, task_info in self.tasks_found.items():
            categorized_flag = False

            for category, config in TASK_CATEGORIES.items():
                if task_name in config['tasks']:
                    task_info['category'] = category
                    task_info['recommended_ttl'] = config['ttl']
                    task_info['recommended_base'] = config.get('base_class')
                    task_info['use_decorator'] = config.get('decorator', False)
                    task_info['queue'] = config.get('queue')
                    categorized[category].append(task_info)
                    categorized_flag = True
                    break

            if not categorized_flag:
                categorized['uncategorized'].append(task_info)

        return categorized


class TaskMigrator:
    """Migrates tasks to use idempotency framework"""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.backup_dir = Path('backups') / datetime.now().strftime('%Y%m%d_%H%M%S')

    def migrate_task(self, task_info: Dict, strategy: str = 'auto') -> bool:
        """
        Migrate a single task to use idempotency.

        Args:
            task_info: Task information from analyzer
            strategy: 'auto', 'base_class', or 'decorator'

        Returns:
            True if successful
        """
        file_path = task_info['file']
        task_name = task_info['name']

        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Migrating: {task_name} in {file_path}")

        # Read current file
        with open(file_path, 'r') as f:
            content = f.read()

        # Determine migration strategy
        if strategy == 'auto':
            if task_info.get('use_decorator'):
                strategy = 'decorator'
            elif task_info.get('recommended_base'):
                strategy = 'base_class'
            else:
                strategy = 'decorator'

        # Create backup
        if not self.dry_run:
            self._create_backup(file_path, content)

        # Generate new content
        if strategy == 'base_class':
            new_content = self._migrate_to_base_class(content, task_info)
        else:
            new_content = self._migrate_to_decorator(content, task_info)

        # Show changes
        self._show_diff(task_name, content, new_content)

        # Write changes
        if not self.dry_run:
            with open(file_path, 'w') as f:
                f.write(new_content)
            print(f"✅ Migrated {task_name}")
        else:
            print(f"📋 Preview completed for {task_name}")

        return True

    def _migrate_to_base_class(self, content: str, task_info: Dict) -> str:
        """Migrate task to use IdempotentTask base class"""
        lines = content.split('\n')
        new_lines = []

        # Add imports if not present
        import_added = False
        for i, line in enumerate(lines):
            new_lines.append(line)

            # Add imports after existing imports
            if line.startswith('from celery import') and not import_added:
                if 'from apps.core.tasks.base import IdempotentTask' not in content:
                    new_lines.append('from apps.core.tasks.base import IdempotentTask')
                if 'from apps.core.tasks.utils import task_retry_policy' not in content:
                    new_lines.append('from apps.core.tasks.utils import task_retry_policy')
                import_added = True

            # Replace decorator
            if f"def {task_info['name']}" in line:
                # Find decorator above
                decorator_idx = i - 1
                while decorator_idx >= 0 and '@' in lines[decorator_idx]:
                    # Replace with new decorator
                    if '@shared_task' in lines[decorator_idx] or '@app.task' in lines[decorator_idx]:
                        category = task_info.get('category', 'default')
                        ttl = task_info.get('recommended_ttl', 3600)
                        queue = task_info.get('queue', 'default')

                        new_decorator = (
                            f"@shared_task(\n"
                            f"    base=IdempotentTask,\n"
                            f"    bind=True,\n"
                            f"    **task_retry_policy('{category}')\n"
                            f")\n"
                            f"# Idempotency: TTL={ttl}s, Queue={queue}"
                        )
                        new_lines[decorator_idx] = new_decorator
                    decorator_idx -= 1

        return '\n'.join(new_lines)

    def _migrate_to_decorator(self, content: str, task_info: Dict) -> str:
        """Migrate task to use @with_idempotency decorator"""
        lines = content.split('\n')
        new_lines = []

        # Add import if not present
        import_added = False
        for i, line in enumerate(lines):
            new_lines.append(line)

            # Add import after existing imports
            if line.startswith('from celery import') and not import_added:
                if 'from apps.core.tasks.idempotency_service import with_idempotency' not in content:
                    new_lines.append('from apps.core.tasks.idempotency_service import with_idempotency')
                import_added = True

            # Add decorator before function
            if f"def {task_info['name']}" in line:
                # Find existing decorator
                decorator_idx = i - 1
                if decorator_idx >= 0 and '@' in lines[decorator_idx]:
                    # Add idempotency decorator above existing decorator
                    ttl = task_info.get('recommended_ttl', 3600)
                    indent = len(lines[decorator_idx]) - len(lines[decorator_idx].lstrip())
                    new_decorator = f"{' ' * indent}@with_idempotency(ttl_seconds={ttl})"
                    new_lines.insert(decorator_idx, new_decorator)

        return '\n'.join(new_lines)

    def _create_backup(self, file_path: str, content: str):
        """Create backup of original file"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        backup_file = self.backup_dir / Path(file_path).name
        with open(backup_file, 'w') as f:
            f.write(content)

        print(f"📦 Backup created: {backup_file}")

    def _show_diff(self, task_name: str, old_content: str, new_content: str):
        """Show changes (simplified)"""
        print(f"\n📝 Changes for {task_name}:")
        print("─" * 60)

        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')

        # Show first 10 changed lines
        changes_shown = 0
        for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
            if old_line != new_line and changes_shown < 10:
                print(f"  - {old_line}")
                print(f"  + {new_line}")
                changes_shown += 1

        if changes_shown == 0:
            print("  (No changes)")

        print("─" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Celery tasks to use idempotency framework'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    parser.add_argument('--task', type=str,
                        help='Migrate specific task by name')
    parser.add_argument('--category', type=str,
                        help='Migrate all tasks in category (critical, high_priority, etc.)')
    parser.add_argument('--analyze', action='store_true',
                        help='Analyze tasks and show recommendations')
    parser.add_argument('--all', action='store_true',
                        help='Migrate all categorized tasks')

    args = parser.parse_args()

    # Task files to analyze
    task_files = [
        'background_tasks/tasks.py',
        'background_tasks/core_tasks_refactored.py',
        'background_tasks/email_tasks.py',
        'background_tasks/report_tasks.py',
        'background_tasks/maintenance_tasks.py',
    ]

    # Analyze tasks
    analyzer = TaskMigrationAnalyzer(task_files)
    categorized = analyzer.analyze()

    # Show analysis
    if args.analyze:
        print("\n" + "=" * 80)
        print("📊 TASK MIGRATION ANALYSIS")
        print("=" * 80)

        total_tasks = sum(len(tasks) for tasks in categorized.values())
        print(f"\nTotal tasks found: {total_tasks}\n")

        for category, tasks in categorized.items():
            if tasks:
                print(f"\n{category.upper()} ({len(tasks)} tasks):")
                for task in tasks:
                    print(f"  • {task['name']}")
                    print(f"    File: {task['file']}")
                    print(f"    Recommended: {task.get('recommended_base', 'decorator')}")
                    print(f"    TTL: {task.get('recommended_ttl', 'N/A')}s")

        return

    # Migration logic
    migrator = TaskMigrator(dry_run=args.dry_run)

    if args.task:
        # Migrate specific task
        task_info = None
        for category_tasks in categorized.values():
            for task in category_tasks:
                if task['name'] == args.task:
                    task_info = task
                    break

        if task_info:
            migrator.migrate_task(task_info)
        else:
            print(f"❌ Task not found: {args.task}")

    elif args.category:
        # Migrate category
        if args.category in categorized:
            for task in categorized[args.category]:
                migrator.migrate_task(task)
        else:
            print(f"❌ Category not found: {args.category}")

    elif args.all:
        # Migrate all categorized tasks
        for category in ['critical', 'high_priority', 'reports', 'email', 'mutations']:
            if categorized[category]:
                print(f"\n{'='*80}")
                print(f"Migrating {category.upper()} tasks")
                print(f"{'='*80}")
                for task in categorized[category]:
                    migrator.migrate_task(task)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
