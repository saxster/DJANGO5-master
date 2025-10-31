#!/usr/bin/env python3
"""
God File Detection and Tracking Script

Identifies files violating CLAUDE.md architecture limits and tracks refactoring progress.

Usage:
    python scripts/detect_god_files.py --report GOD_FILES.md
    python scripts/detect_god_files.py --check --threshold 150
    python scripts/detect_god_files.py --analyze --file apps/myapp/views.py
    python scripts/detect_god_files.py --burndown --chart burndown.png

Following .claude/rules.md:
- Rule #9: Specific exception handling
- Rule #11: No bare except blocks
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# CLAUDE.md Architecture Limits
LIMITS = {
    'views': 150,
    'services': 150,
    'models': 150,
    'forms': 100,
    'managers': 150,  # Django ORM managers can use composition
    'settings': 200,
    'admin': 150,
    'serializers': 150,
    'utils': 150,
    'middleware': 150,
    'tasks': 150,
}

# Severity thresholds
SEVERITY_LEVELS = {
    'CRITICAL': 1000,  # >1000 lines
    'HIGH': 500,       # 500-999 lines
    'MEDIUM': 300,     # 300-499 lines
    'LOW': 150,        # 150-299 lines (baseline violation)
}


def get_project_root() -> Path:
    """Get project root directory"""
    script_dir = Path(__file__).parent
    return script_dir.parent


def get_file_category(file_path: Path) -> str:
    """Determine file category based on name/path"""
    name = file_path.stem
    parent = file_path.parent.name

    if 'views' in name or parent == 'views':
        return 'views'
    elif 'service' in name or parent == 'services':
        return 'services'
    elif 'model' in name or parent == 'models':
        return 'models'
    elif 'form' in name or parent == 'forms':
        return 'forms'
    elif 'manager' in name or parent == 'managers':
        return 'managers'
    elif 'settings' in str(file_path):
        return 'settings'
    elif 'admin' in name:
        return 'admin'
    elif 'serializer' in name or parent == 'serializers':
        return 'serializers'
    elif 'utils' in name or 'util' in name:
        return 'utils'
    elif 'middleware' in name:
        return 'middleware'
    elif 'task' in name:
        return 'tasks'
    else:
        return 'other'


def get_severity(line_count: int) -> str:
    """Determine severity level"""
    for level, threshold in SEVERITY_LEVELS.items():
        if line_count >= threshold:
            return level
    return 'OK'


def count_lines(file_path: Path) -> int:
    """Count non-empty lines in file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # Count non-empty, non-comment-only lines
        return len([l for l in lines if l.strip() and not l.strip().startswith('#')])
    except (IOError, OSError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return 0


def find_god_files(
    root_dir: Path,
    threshold: int = 150,
    include_tests: bool = False
) -> List[Dict]:
    """
    Find all Python files exceeding threshold.

    Args:
        root_dir: Root directory to search
        threshold: Minimum line count to flag
        include_tests: Include test files in results

    Returns:
        List of god file dictionaries
    """
    god_files = []

    # Patterns to exclude
    exclude_patterns = [
        '**/migrations/**',
        '**/__pycache__/**',
        '**/venv/**',
        '**/env/**',
        '**/.git/**',
    ]

    if not include_tests:
        exclude_patterns.extend([
            '**/tests/**',
            '**/test_*.py',
        ])

    # Find all Python files
    apps_dir = root_dir / 'apps'
    background_tasks_dir = root_dir / 'background_tasks'
    config_dir = root_dir / 'intelliwiz_config'

    for search_dir in [apps_dir, background_tasks_dir, config_dir]:
        if not search_dir.exists():
            continue

        for py_file in search_dir.rglob('*.py'):
            # Skip excluded patterns
            if any(py_file.match(pattern) for pattern in exclude_patterns):
                continue

            line_count = count_lines(py_file)
            if line_count >= threshold:
                category = get_file_category(py_file)
                limit = LIMITS.get(category, 150)
                violation_pct = ((line_count - limit) / limit) * 100
                severity = get_severity(line_count)

                god_files.append({
                    'path': str(py_file.relative_to(root_dir)),
                    'lines': line_count,
                    'category': category,
                    'limit': limit,
                    'violation_pct': round(violation_pct, 1),
                    'severity': severity,
                })

    # Sort by line count (descending)
    god_files.sort(key=lambda x: x['lines'], reverse=True)
    return god_files


def generate_report(god_files: List[Dict], output_file: str = None) -> str:
    """Generate markdown report of God files"""
    report_lines = [
        "# God File Detection Report",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Total God Files**: {len(god_files)}",
        f"- **Critical (>1,000 lines)**: {len([f for f in god_files if f['severity'] == 'CRITICAL'])}",
        f"- **High (500-999 lines)**: {len([f for f in god_files if f['severity'] == 'HIGH'])}",
        f"- **Medium (300-499 lines)**: {len([f for f in god_files if f['severity'] == 'MEDIUM'])}",
        f"- **Low (150-299 lines)**: {len([f for f in god_files if f['severity'] == 'LOW'])}",
        "",
        "## God Files by Severity",
        "",
    ]

    # Group by severity
    for severity_level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        files_at_level = [f for f in god_files if f['severity'] == severity_level]
        if not files_at_level:
            continue

        report_lines.append(f"### {severity_level} Priority ({len(files_at_level)} files)")
        report_lines.append("")
        report_lines.append("| # | File | Lines | Category | Limit | Violation % |")
        report_lines.append("|---|------|-------|----------|-------|-------------|")

        for idx, file_info in enumerate(files_at_level, 1):
            report_lines.append(
                f"| {idx} | `{file_info['path']}` | {file_info['lines']} | "
                f"{file_info['category']} | {file_info['limit']} | "
                f"{file_info['violation_pct']}% |"
            )

        report_lines.append("")

    # Add category breakdown
    report_lines.extend([
        "## God Files by Category",
        "",
        "| Category | Count | Avg Lines | Max Lines | Files |",
        "|----------|-------|-----------|-----------|-------|",
    ])

    # Group by category
    by_category = {}
    for file_info in god_files:
        cat = file_info['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(file_info)

    for category in sorted(by_category.keys()):
        files_in_cat = by_category[category]
        avg_lines = sum(f['lines'] for f in files_in_cat) / len(files_in_cat)
        max_lines = max(f['lines'] for f in files_in_cat)

        file_list = ', '.join([f"`{Path(f['path']).name}`" for f in files_in_cat[:3]])
        if len(files_in_cat) > 3:
            file_list += f", ... (+{len(files_in_cat) - 3} more)"

        report_lines.append(
            f"| {category} | {len(files_in_cat)} | {avg_lines:.0f} | "
            f"{max_lines} | {file_list} |"
        )

    report = "\n".join(report_lines)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to {output_file}")

    return report


def analyze_file(file_path: str) -> Dict:
    """Analyze a specific file for refactoring"""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return {}

    line_count = count_lines(path)
    category = get_file_category(path)
    limit = LIMITS.get(category, 150)

    # Count classes and functions
    classes = []
    functions = []

    try:
        with open(path, 'r') as f:
            for line_no, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith('class '):
                    class_name = stripped.split('(')[0].replace('class ', '').strip(':')
                    classes.append((class_name, line_no))
                elif stripped.startswith('def ') and not stripped.startswith('def _'):
                    func_name = stripped.split('(')[0].replace('def ', '')
                    functions.append((func_name, line_no))
    except (IOError, OSError) as e:
        print(f"Warning: Could not analyze {file_path}: {e}", file=sys.stderr)
        return {}

    analysis = {
        'file': str(path),
        'lines': line_count,
        'category': category,
        'limit': limit,
        'violation_pct': round(((line_count - limit) / limit) * 100, 1),
        'classes': len(classes),
        'functions': len(functions),
        'suggested_modules': max(2, line_count // 300),
        'class_list': [c[0] for c in classes],
        'function_list': [f[0] for f in functions],
    }

    # Print analysis
    print(f"\n{'=' * 70}")
    print(f"God File Analysis: {path.name}")
    print(f"{'=' * 70}")
    print(f"Lines: {line_count} (limit: {limit}, violation: {analysis['violation_pct']}%)")
    print(f"Category: {category}")
    print(f"Classes: {len(classes)}")
    print(f"Functions: {len(functions)}")
    print(f"\nSuggested split: {analysis['suggested_modules']} modules (~{line_count // analysis['suggested_modules']} lines each)")

    print(f"\nClasses found ({len(classes)}):")
    for class_name, line_no in classes[:10]:
        print(f"  - {class_name} (line {line_no})")
    if len(classes) > 10:
        print(f"  ... and {len(classes) - 10} more")

    print(f"\nFunctions found ({len(functions)}):")
    for func_name, line_no in functions[:10]:
        print(f"  - {func_name} (line {line_no})")
    if len(functions) > 10:
        print(f"  ... and {len(functions) - 10} more")

    print(f"\n{'=' * 70}\n")

    return analysis


def check_staged_files(threshold: int = 150) -> bool:
    """
    Check if any staged files are God files.
    Used in pre-commit hooks.

    Returns:
        True if all files OK, False if God files detected
    """
    import subprocess

    try:
        # Get staged Python files
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=True
        )

        staged_files = [
            f for f in result.stdout.strip().split('\n')
            if f.endswith('.py') and f
        ]

        god_files_found = []

        for file_path in staged_files:
            if not os.path.exists(file_path):
                continue

            # Skip migrations, tests, etc.
            if any(x in file_path for x in ['migrations', '__pycache__', 'tests']):
                continue

            line_count = count_lines(Path(file_path))
            if line_count >= threshold:
                god_files_found.append((file_path, line_count))

        if god_files_found:
            print("\n❌ God File Detection - PRE-COMMIT HOOK FAILED")
            print(f"{'=' * 70}")
            print(f"The following files exceed {threshold} line limit:\n")
            for file_path, lines in god_files_found:
                print(f"  ⚠️  {file_path}: {lines} lines")
            print(f"\n{'=' * 70}")
            print("ACTIONS:")
            print("1. Refactor file into focused modules (<150 lines each)")
            print("2. See: GOD_FILE_QUICK_REFERENCE.md for refactoring guide")
            print("3. Or bypass (NOT RECOMMENDED): git commit --no-verify")
            print(f"{'=' * 70}\n")
            return False

        return True

    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not check staged files: {e}", file=sys.stderr)
        return True  # Don't block on errors
    except (IOError, OSError) as e:
        print(f"Warning: File system error: {e}", file=sys.stderr)
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Detect and track God files (files violating CLAUDE.md limits)'
    )
    parser.add_argument(
        '--report',
        help='Generate markdown report and save to file'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check for God files and exit with error code if found (for CI/CD)'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=150,
        help='Minimum line count to flag as God file (default: 150)'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze a specific file for refactoring'
    )
    parser.add_argument(
        '--file',
        help='File path to analyze (use with --analyze)'
    )
    parser.add_argument(
        '--staged-only',
        action='store_true',
        help='Check only staged files (for pre-commit hook)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--include-tests',
        action='store_true',
        help='Include test files in analysis'
    )

    args = parser.parse_args()

    # Handle staged-only check (pre-commit hook)
    if args.staged_only:
        success = check_staged_files(args.threshold)
        sys.exit(0 if success else 1)

    # Handle file analysis
    if args.analyze:
        if not args.file:
            print("❌ Error: --file required with --analyze")
            sys.exit(1)
        analyze_file(args.file)
        sys.exit(0)

    # Find God files
    root_dir = get_project_root()
    god_files = find_god_files(root_dir, args.threshold, args.include_tests)

    # Output as JSON
    if args.json:
        print(json.dumps(god_files, indent=2))
        sys.exit(0)

    # Generate report
    if args.report:
        generate_report(god_files, args.report)

    # Check mode (for CI/CD)
    if args.check:
        if god_files:
            print(f"\n❌ Found {len(god_files)} God files exceeding {args.threshold} lines")
            print("See report for details")
            sys.exit(1)
        else:
            print(f"✅ No God files found (threshold: {args.threshold} lines)")
            sys.exit(0)

    # Default: print summary
    if not args.report and not args.json:
        print(f"\n{'=' * 70}")
        print("God File Detection Summary")
        print(f"{'=' * 70}")
        print(f"Total God files found: {len(god_files)}")
        print(f"Threshold: {args.threshold} lines")
        print(f"\nTop 10 God files:")
        for idx, file_info in enumerate(god_files[:10], 1):
            severity_icon = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '⚪'}.get(
                file_info['severity'], '⚪'
            )
            print(f"{idx:2}. {severity_icon} {Path(file_info['path']).name}: {file_info['lines']} lines "
                  f"({file_info['violation_pct']}% over)")

        print(f"\n{'=' * 70}")
        print(f"Run with --report FILENAME.md to generate full report")
        print(f"Run with --analyze --file PATH to analyze specific file")
        print(f"{'=' * 70}\n")


if __name__ == '__main__':
    main()
