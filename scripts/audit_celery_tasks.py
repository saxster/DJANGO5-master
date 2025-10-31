#!/usr/bin/env python
"""
Celery Task Inventory and Audit Script

Scans codebase for all Celery tasks and generates comprehensive audit report.

Features:
- Finds all @shared_task and @app.task decorators
- Detects duplicate task names
- Cross-references with beat schedule
- Identifies god file tasks vs modular tasks
- Reports decorator inconsistencies

Usage:
    python scripts/audit_celery_tasks.py --generate-report
    python scripts/audit_celery_tasks.py --duplicates-only
    python scripts/audit_celery_tasks.py --format markdown

Created: 2025-10-10
Purpose: Celery configuration refactoring (Sprint 3.1)
"""

import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class CeleryTaskAuditor:
    """Audits Celery tasks across the codebase"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tasks: Dict[str, List[Dict]] = defaultdict(list)
        self.beat_schedule_tasks: Set[str] = set()

        # Patterns for finding tasks
        self.shared_task_pattern = re.compile(
            r'@shared_task\s*\([^)]*name\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        self.app_task_pattern = re.compile(
            r'@app\.task\s*\([^)]*name\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        self.function_pattern = re.compile(
            r'def\s+(\w+)\s*\('
        )

    def scan_tasks(self):
        """Scan all Python files for Celery tasks"""
        print(f"🔍 Scanning {self.project_root} for Celery tasks...")

        # Scan background_tasks directory
        bg_tasks_dir = self.project_root / "background_tasks"
        if bg_tasks_dir.exists():
            self._scan_directory(bg_tasks_dir)

        # Scan apps/*/services directories
        apps_dir = self.project_root / "apps"
        if apps_dir.exists():
            for app_dir in apps_dir.iterdir():
                if app_dir.is_dir():
                    services_dir = app_dir / "services"
                    if services_dir.exists():
                        self._scan_directory(services_dir)

        print(f"✅ Found {sum(len(v) for v in self.tasks.values())} task definitions")

    def _scan_directory(self, directory: Path):
        """Scan a directory for task definitions"""
        for file_path in directory.rglob("*.py"):
            if file_path.name.startswith("__"):
                continue
            self._scan_file(file_path)

    def _scan_file(self, file_path: Path):
        """Scan a single file for task definitions"""
        try:
            content = file_path.read_text()

            # Find @shared_task decorators
            for match in self.shared_task_pattern.finditer(content):
                task_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                self._add_task(task_name, file_path, line_num, 'shared_task')

            # Find @app.task decorators
            for match in self.app_task_pattern.finditer(content):
                task_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                self._add_task(task_name, file_path, line_num, 'app.task')

            # Also find tasks without explicit name (use function name)
            if '@shared_task' in content or '@app.task' in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if '@shared_task' in line or '@app.task' in line:
                        # Check if name parameter exists
                        if 'name=' not in line:
                            # Look for function definition in next few lines
                            for j in range(i+1, min(i+5, len(lines))):
                                func_match = self.function_pattern.search(lines[j])
                                if func_match:
                                    func_name = func_match.group(1)
                                    decorator = 'shared_task' if '@shared_task' in line else 'app.task'
                                    self._add_task(func_name, file_path, i+1, decorator)
                                    break

        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}")

    def _add_task(self, task_name: str, file_path: Path, line_num: int, decorator: str):
        """Add a task to the inventory"""
        rel_path = file_path.relative_to(self.project_root)
        self.tasks[task_name].append({
            'file': str(rel_path),
            'line': line_num,
            'decorator': decorator
        })

    def load_beat_schedule(self):
        """Load beat schedule tasks from main Celery config"""
        print("📅 Loading beat schedule configuration...")
        celery_config = self.project_root / "intelliwiz_config" / "celery.py"

        if celery_config.exists():
            content = celery_config.read_text()

            # Find all task references in beat_schedule
            task_pattern = re.compile(r"'task'\s*:\s*'([^']+)'")
            for match in task_pattern.finditer(content):
                self.beat_schedule_tasks.add(match.group(1))

        print(f"✅ Found {len(self.beat_schedule_tasks)} beat schedule tasks")

    def find_duplicates(self) -> Dict[str, List[Dict]]:
        """Find tasks defined in multiple locations"""
        return {
            name: locations
            for name, locations in self.tasks.items()
            if len(locations) > 1
        }

    def find_decorator_inconsistencies(self) -> List[Tuple[str, str]]:
        """Find files mixing @app.task and @shared_task"""
        file_decorators = defaultdict(set)

        for task_name, locations in self.tasks.items():
            for loc in locations:
                file_decorators[loc['file']].add(loc['decorator'])

        # Return files with both decorators
        return [
            (file, decorators)
            for file, decorators in file_decorators.items()
            if len(decorators) > 1
        ]

    def find_orphaned_beat_tasks(self) -> Set[str]:
        """Find beat schedule tasks that aren't registered"""
        registered_tasks = set(self.tasks.keys())
        return self.beat_schedule_tasks - registered_tasks

    def generate_report(self, format: str = 'markdown') -> str:
        """Generate comprehensive audit report"""
        if format == 'markdown':
            return self._generate_markdown_report()
        else:
            return self._generate_text_report()

    def _generate_markdown_report(self) -> str:
        """Generate Markdown format report"""
        lines = [
            "# Celery Task Inventory Report",
            "",
            f"**Generated:** {self._get_timestamp()}",
            f"**Total Tasks:** {len(self.tasks)}",
            f"**Task Definitions:** {sum(len(v) for v in self.tasks.values())}",
            f"**Beat Schedule Tasks:** {len(self.beat_schedule_tasks)}",
            "",
            "---",
            ""
        ]

        # Duplicates section
        duplicates = self.find_duplicates()
        if duplicates:
            lines.extend([
                "## 🔴 Duplicate Task Definitions",
                "",
                f"Found **{len(duplicates)}** tasks with multiple definitions:",
                ""
            ])

            for task_name, locations in sorted(duplicates.items()):
                lines.append(f"### `{task_name}` ({len(locations)} definitions)")
                lines.append("")
                for loc in locations:
                    lines.append(f"- **{loc['file']}:{loc['line']}** - `@{loc['decorator']}`")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Decorator inconsistencies
        inconsistencies = self.find_decorator_inconsistencies()
        if inconsistencies:
            lines.extend([
                "## ⚠️  Decorator Inconsistencies",
                "",
                f"Found **{len(inconsistencies)}** files mixing decorators:",
                ""
            ])

            for file, decorators in sorted(inconsistencies):
                dec_list = ', '.join(f"`@{d}`" for d in sorted(decorators))
                lines.append(f"- **{file}** - Uses: {dec_list}")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Orphaned beat tasks
        orphaned = self.find_orphaned_beat_tasks()
        if orphaned:
            lines.extend([
                "## 🚨 Orphaned Beat Schedule Tasks",
                "",
                f"Found **{len(orphaned)}** beat tasks without registered implementation:",
                ""
            ])

            for task_name in sorted(orphaned):
                lines.append(f"- `{task_name}` - Referenced in beat schedule but NOT FOUND")

            lines.append("")
            lines.append("---")
            lines.append("")

        # God file analysis
        god_file = "background_tasks/tasks.py"
        god_file_tasks = [
            (name, locs) for name, locs in self.tasks.items()
            if any(loc['file'] == god_file for loc in locs)
        ]

        if god_file_tasks:
            lines.extend([
                "## 📦 God File Analysis",
                "",
                f"**File:** `{god_file}`",
                f"**Tasks Defined:** {len(god_file_tasks)}",
                ""
            ])

            # Categorize: unique vs duplicate
            unique = [name for name, locs in god_file_tasks if len(locs) == 1]
            dups = [name for name, locs in god_file_tasks if len(locs) > 1]

            lines.append(f"- **Unique to god file:** {len(unique)}")
            lines.append(f"- **Also defined elsewhere:** {len(dups)}")
            lines.append("")

            if dups:
                lines.append("### Tasks with duplicate implementations:")
                for name in sorted(dups):
                    lines.append(f"- `{name}`")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Full inventory
        lines.extend([
            "## 📋 Complete Task Inventory",
            "",
            f"All {len(self.tasks)} registered tasks:",
            ""
        ])

        for task_name in sorted(self.tasks.keys()):
            locations = self.tasks[task_name]
            in_beat = "📅" if task_name in self.beat_schedule_tasks else "  "
            dup_marker = "🔴" if len(locations) > 1 else "  "

            lines.append(f"### {in_beat} {dup_marker} `{task_name}`")
            for loc in locations:
                lines.append(f"- **{loc['file']}:{loc['line']}** - `@{loc['decorator']}`")
            lines.append("")

        # Summary statistics
        lines.extend([
            "---",
            "",
            "## 📊 Statistics",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Total unique tasks | {len(self.tasks)} |",
            f"| Total task definitions | {sum(len(v) for v in self.tasks.values())} |",
            f"| Duplicate tasks | {len(duplicates)} |",
            f"| Beat schedule tasks | {len(self.beat_schedule_tasks)} |",
            f"| Orphaned beat tasks | {len(orphaned)} |",
            f"| Files with mixed decorators | {len(inconsistencies)} |",
            f"| @shared_task usage | {self._count_decorator('shared_task')} |",
            f"| @app.task usage | {self._count_decorator('app.task')} |",
            ""
        ])

        return '\n'.join(lines)

    def _count_decorator(self, decorator: str) -> int:
        """Count usage of specific decorator"""
        count = 0
        for locations in self.tasks.values():
            count += sum(1 for loc in locations if loc['decorator'] == decorator)
        return count

    def _get_timestamp(self) -> str:
        """Get formatted timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _generate_text_report(self) -> str:
        """Generate plain text report"""
        lines = [
            "=" * 70,
            "CELERY TASK INVENTORY REPORT",
            "=" * 70,
            f"Generated: {self._get_timestamp()}",
            f"Total Tasks: {len(self.tasks)}",
            ""
        ]

        duplicates = self.find_duplicates()
        if duplicates:
            lines.append(f"\nDUPLICATE TASKS: {len(duplicates)}")
            for task_name, locations in sorted(duplicates.items()):
                lines.append(f"\n{task_name}:")
                for loc in locations:
                    lines.append(f"  - {loc['file']}:{loc['line']} (@{loc['decorator']})")

        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Audit Celery tasks in the codebase"
    )
    parser.add_argument(
        '--generate-report',
        action='store_true',
        help="Generate full audit report"
    )
    parser.add_argument(
        '--duplicates-only',
        action='store_true',
        help="Show only duplicate tasks"
    )
    parser.add_argument(
        '--format',
        choices=['markdown', 'text'],
        default='markdown',
        help="Output format"
    )
    parser.add_argument(
        '--output',
        type=str,
        help="Write report to file"
    )

    args = parser.parse_args()

    # Run audit
    auditor = CeleryTaskAuditor(PROJECT_ROOT)
    auditor.scan_tasks()
    auditor.load_beat_schedule()

    # Generate appropriate output
    if args.duplicates_only:
        duplicates = auditor.find_duplicates()
        if duplicates:
            print(f"\n🔴 Found {len(duplicates)} duplicate tasks:\n")
            for task_name, locations in sorted(duplicates.items()):
                print(f"  {task_name}:")
                for loc in locations:
                    print(f"    - {loc['file']}:{loc['line']} (@{loc['decorator']})")
        else:
            print("✅ No duplicate tasks found!")

    elif args.generate_report:
        report = auditor.generate_report(args.format)

        if args.output:
            output_path = PROJECT_ROOT / args.output
            output_path.write_text(report)
            print(f"✅ Report written to: {output_path}")
        else:
            print(report)

    else:
        # Default: show summary
        duplicates = auditor.find_duplicates()
        orphaned = auditor.find_orphaned_beat_tasks()
        inconsistencies = auditor.find_decorator_inconsistencies()

        print("\n📊 SUMMARY:")
        print(f"  Total tasks: {len(auditor.tasks)}")
        print(f"  Duplicate tasks: {len(duplicates)}")
        print(f"  Orphaned beat tasks: {len(orphaned)}")
        print(f"  Files with mixed decorators: {len(inconsistencies)}")
        print("\n💡 Use --generate-report for full details")


if __name__ == "__main__":
    main()
