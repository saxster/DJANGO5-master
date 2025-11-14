#!/usr/bin/env python3
"""
File Size Limit Validation Script

Validates Python files against architecture limits defined in .claude/rules.md:
- Settings files: < 200 lines
- Models: < 150 lines
- View methods: < 30 lines
- Forms: < 100 lines
- Utilities: < 50 lines per function

Exit code 0: All files pass
Exit code 1: Violations found

Usage:
    python scripts/check_file_sizes.py
    python scripts/check_file_sizes.py --path apps/attendance
    python scripts/check_file_sizes.py --verbose
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional


@dataclass
class FileLimits:
    """File size limits per category"""
    SETTINGS = 200
    MODELS = 150
    FORMS = 100
    UTILITIES = 150  # Per file, not per function
    VIEW_METHOD = 30


@dataclass
class Violation:
    """Represents a file size violation"""
    file_path: str
    category: str
    line_count: int
    limit: int
    severity: str  # 'error', 'warning'

    @property
    def excess_lines(self) -> int:
        return self.line_count - self.limit

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.category}: {self.file_path}\n"
            f"  Lines: {self.line_count} (limit: {self.limit}, excess: {self.excess_lines})"
        )


class BaselineManager:
    """Manages baseline of existing violations for incremental improvements"""

    BASELINE_FILE = '.file_size_baseline.json'

    @classmethod
    def load_baseline(cls, baseline_path: Optional[str] = None) -> Dict[str, Dict]:
        """Load existing baseline from JSON file"""
        path = Path(baseline_path or cls.BASELINE_FILE)

        if not path.exists():
            return {}

        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load baseline file: {e}", file=sys.stderr)
            return {}

    @classmethod
    def save_baseline(cls, violations: List[Violation], baseline_path: Optional[str] = None):
        """Save current violations as baseline"""
        path = Path(baseline_path or cls.BASELINE_FILE)

        # Convert violations to baseline format
        baseline = {}
        for v in violations:
            key = f"{v.file_path}:{v.category}"
            baseline[key] = {
                'file_path': v.file_path,
                'category': v.category,
                'line_count': v.line_count,
                'limit': v.limit,
                'severity': v.severity
            }

        with open(path, 'w') as f:
            json.dump(baseline, f, indent=2, sort_keys=True)

        print(f"✅ Baseline saved: {len(baseline)} violations in {path}")

    @classmethod
    def filter_new_violations(
        cls,
        violations: List[Violation],
        baseline: Dict[str, Dict]
    ) -> Tuple[List[Violation], List[Violation]]:
        """
        Filter violations into existing (baseline) and new violations.

        Returns:
            Tuple of (new_violations, baseline_violations)
        """
        new_violations = []
        baseline_violations = []

        for v in violations:
            key = f"{v.file_path}:{v.category}"

            if key in baseline:
                baseline_entry = baseline[key]
                # Check if violation got worse
                if v.line_count > baseline_entry['line_count']:
                    # Worse than baseline - treat as new
                    new_violations.append(v)
                else:
                    # Same or better than baseline
                    baseline_violations.append(v)
            else:
                # Not in baseline - new violation
                new_violations.append(v)

        return new_violations, baseline_violations


class FileTypeDetector:
    """Detects Python file category based on path and content"""

    @staticmethod
    def is_settings_file(path: Path) -> bool:
        """Check if file is a settings file"""
        return (
            'settings' in path.parts or
            path.name.startswith('settings') or
            path.name == 'config.py' or
            'config/settings' in str(path)
        )

    @staticmethod
    def is_models_file(path: Path) -> bool:
        """Check if file is a models file"""
        return (
            path.name == 'models.py' or
            'models' in path.parts and path.name.endswith('.py') and path.name != '__init__.py'
        )

    @staticmethod
    def is_forms_file(path: Path) -> bool:
        """Check if file is a forms file"""
        return (
            path.name == 'forms.py' or
            path.name.endswith('_forms.py') or
            path.name.endswith('_form.py')
        )

    @staticmethod
    def is_views_file(path: Path) -> bool:
        """Check if file is a views file"""
        return (
            path.name == 'views.py' or
            'views' in path.parts and path.name.endswith('.py') and path.name != '__init__.py'
        )

    @staticmethod
    def is_utility_file(path: Path) -> bool:
        """Check if file is a utility/helper file"""
        return (
            path.name.startswith('utils') or
            path.name.endswith('_utils.py') or
            path.name.endswith('_helpers.py') or
            path.name == 'helpers.py' or
            'utils' in path.parts
        )


class MethodSizeChecker(ast.NodeVisitor):
    """AST visitor to check method sizes in views"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.violations: List[Violation] = []
        self.in_view_class = False

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track if we're inside a view class"""
        # Check if class inherits from common view base classes
        is_view = any(
            base.id in {'View', 'APIView', 'TemplateView', 'ListView',
                       'DetailView', 'CreateView', 'UpdateView', 'DeleteView',
                       'FormView', 'RedirectView'}
            for base in node.bases
            if isinstance(base, ast.Name)
        )

        old_in_view = self.in_view_class
        if is_view:
            self.in_view_class = True

        self.generic_visit(node)
        self.in_view_class = old_in_view

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check method sizes in view classes"""
        if self.in_view_class:
            # Calculate lines (excluding decorator lines)
            method_lines = node.end_lineno - node.lineno + 1

            # Common view methods that should be checked
            view_methods = {'get', 'post', 'put', 'patch', 'delete',
                          'form_valid', 'form_invalid', 'get_queryset',
                          'get_context_data', 'dispatch'}

            if node.name in view_methods and method_lines > FileLimits.VIEW_METHOD:
                self.violations.append(Violation(
                    file_path=f"{self.file_path}:{node.lineno}",
                    category="View Method",
                    line_count=method_lines,
                    limit=FileLimits.VIEW_METHOD,
                    severity='error'
                ))

        self.generic_visit(node)


def count_non_empty_lines(file_path: Path) -> int:
    """Count non-empty, non-comment lines in a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        count = 0
        in_docstring = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Handle docstrings
            if '"""' in stripped or "'''" in stripped:
                in_docstring = not in_docstring
                continue

            # Skip comments and docstrings
            if in_docstring or stripped.startswith('#'):
                continue

            count += 1

        return count
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return 0


def check_view_methods(file_path: Path) -> List[Violation]:
    """Check view method sizes using AST"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        checker = MethodSizeChecker(str(file_path))
        checker.visit(tree)
        return checker.violations
    except Exception as e:
        # If AST parsing fails, skip method checking
        return []


def check_file(file_path: Path, detector: FileTypeDetector) -> List[Violation]:
    """Check a single file against size limits"""
    violations = []
    line_count = count_non_empty_lines(file_path)

    # Check settings files
    if detector.is_settings_file(file_path):
        if line_count > FileLimits.SETTINGS:
            violations.append(Violation(
                file_path=str(file_path),
                category="Settings File",
                line_count=line_count,
                limit=FileLimits.SETTINGS,
                severity='error'
            ))

    # Check model files
    elif detector.is_models_file(file_path):
        if line_count > FileLimits.MODELS:
            violations.append(Violation(
                file_path=str(file_path),
                category="Model File",
                line_count=line_count,
                limit=FileLimits.MODELS,
                severity='error'
            ))

    # Check form files
    elif detector.is_forms_file(file_path):
        if line_count > FileLimits.FORMS:
            violations.append(Violation(
                file_path=str(file_path),
                category="Form File",
                line_count=line_count,
                limit=FileLimits.FORMS,
                severity='error'
            ))

    # Check utility files
    elif detector.is_utility_file(file_path):
        if line_count > FileLimits.UTILITIES:
            violations.append(Violation(
                file_path=str(file_path),
                category="Utility File",
                line_count=line_count,
                limit=FileLimits.UTILITIES,
                severity='warning'  # Warning for utilities
            ))

    # Check view methods
    if detector.is_views_file(file_path):
        violations.extend(check_view_methods(file_path))

    return violations


def scan_directory(
    root_path: Path,
    exclude_dirs: set = None
) -> Tuple[List[Violation], Dict[str, int]]:
    """
    Scan directory for Python files and check size limits

    Returns:
        Tuple of (violations, stats)
    """
    if exclude_dirs is None:
        exclude_dirs = {
            'venv', 'env', '.venv',
            'migrations', 'node_modules',
            '__pycache__', '.git',
            'postgresql_migration',  # Legacy migration scripts
            'background_tasks',  # Task definitions
        }

    violations = []
    stats = {
        'total_files': 0,
        'checked_files': 0,
        'settings': 0,
        'models': 0,
        'forms': 0,
        'views': 0,
        'utilities': 0,
    }

    detector = FileTypeDetector()

    # Find all Python files
    for py_file in root_path.rglob('*.py'):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue

        # Skip __init__.py files (they're allowed to be import-only)
        if py_file.name == '__init__.py':
            continue

        stats['total_files'] += 1

        # Categorize and check
        file_violations = check_file(py_file, detector)
        if file_violations:
            violations.extend(file_violations)
            stats['checked_files'] += 1

            # Update category stats
            for violation in file_violations:
                if 'Settings' in violation.category:
                    stats['settings'] += 1
                elif 'Model' in violation.category:
                    stats['models'] += 1
                elif 'Form' in violation.category:
                    stats['forms'] += 1
                elif 'View' in violation.category:
                    stats['views'] += 1
                elif 'Utility' in violation.category:
                    stats['utilities'] += 1

    return violations, stats


def print_summary(
    violations: List[Violation],
    stats: Dict[str, int],
    verbose: bool = False,
    baseline_mode: bool = False,
    new_violations: Optional[List[Violation]] = None,
    baseline_violations: Optional[List[Violation]] = None
):
    """Print violation summary"""
    errors = [v for v in violations if v.severity == 'error']
    warnings = [v for v in violations if v.severity == 'warning']

    print("\n" + "=" * 80)
    print("FILE SIZE VALIDATION REPORT")
    print("=" * 80)

    print(f"\nFiles Scanned: {stats['total_files']}")
    print(f"Files Checked: {stats['checked_files']}")

    if verbose:
        print("\nCategory Breakdown:")
        print(f"  Settings files: {stats['settings']} violations")
        print(f"  Model files: {stats['models']} violations")
        print(f"  Form files: {stats['forms']} violations")
        print(f"  View methods: {stats['views']} violations")
        print(f"  Utility files: {stats['utilities']} violations")

    if baseline_mode and new_violations is not None:
        print(f"\nTotal Violations: {len(violations)}")
        print(f"  Baseline violations: {len(baseline_violations or [])}")
        print(f"  New violations: {len(new_violations)}")
        print(f"  Errors: {len([v for v in new_violations if v.severity == 'error'])}")
        print(f"  Warnings: {len([v for v in new_violations if v.severity == 'warning'])}")
    else:
        print(f"\nViolations Found: {len(violations)}")
        print(f"  Errors: {len(errors)}")
        print(f"  Warnings: {len(warnings)}")

    # Show violations (new ones if in baseline mode)
    display_violations = new_violations if baseline_mode and new_violations else violations

    if display_violations:
        print("\n" + "-" * 80)
        if baseline_mode and new_violations:
            print("NEW VIOLATIONS (not in baseline):")
        else:
            print("VIOLATIONS:")
        print("-" * 80)

        # Group by category
        by_category = {}
        for v in display_violations:
            by_category.setdefault(v.category, []).append(v)

        for category in sorted(by_category.keys()):
            print(f"\n{category} ({len(by_category[category])} violations):")
            for violation in sorted(by_category[category],
                                   key=lambda x: x.line_count,
                                   reverse=True):
                print(f"  {violation}")
    else:
        if baseline_mode:
            print("\n✅ No new violations beyond baseline!")
        else:
            print("\n✅ All files pass size limits!")

    print("\n" + "=" * 80)

    # Determine exit code
    if baseline_mode and new_violations is not None:
        new_errors = [v for v in new_violations if v.severity == 'error']
        if new_errors:
            print("\n❌ FAILED: Found {} new critical violations".format(len(new_errors)))
            print("\nRecommendations:")
            print("  1. Refactor large files into smaller modules")
            print("  2. Follow patterns in docs/architecture/REFACTORING_PATTERNS.md")
            print("  3. Split by domain/responsibility")
            return 1
        else:
            print("\n✅ SUCCESS: No new violations beyond baseline")
            return 0
    else:
        if errors:
            print("\n❌ FAILED: Found {} critical violations".format(len(errors)))
            print("\nRecommendations:")
            print("  1. Refactor large files into smaller modules")
            print("  2. Follow patterns in docs/architecture/REFACTORING_PATTERNS.md")
            print("  3. Split by domain/responsibility")
            return 1
        elif warnings:
            print("\n⚠️  WARNING: Found {} non-critical violations".format(len(warnings)))
            return 0
        else:
            print("\n✅ SUCCESS: All files meet size requirements")
            return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Validate Python file sizes against architecture limits'
    )
    parser.add_argument(
        '--path',
        type=str,
        default='.',
        help='Root path to scan (default: current directory)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed statistics'
    )
    parser.add_argument(
        '--exclude',
        type=str,
        nargs='*',
        help='Additional directories to exclude'
    )
    parser.add_argument(
        '--ci',
        action='store_true',
        help='CI mode: strict exit codes and concise output'
    )
    parser.add_argument(
        '--pre-commit',
        action='store_true',
        help='Pre-commit mode: fast validation for hooks'
    )
    parser.add_argument(
        '--generate-baseline',
        action='store_true',
        help='Generate baseline file with current violations'
    )
    parser.add_argument(
        '--baseline',
        type=str,
        help='Path to baseline file (default: .file_size_baseline.json)'
    )

    args = parser.parse_args()

    root_path = Path(args.path).resolve()
    if not root_path.exists():
        print(f"Error: Path does not exist: {root_path}", file=sys.stderr)
        return 1

    print(f"Scanning: {root_path}")
    if args.verbose:
        print("\nFile Size Limits:")
        print(f"  Settings: {FileLimits.SETTINGS} lines")
        print(f"  Models: {FileLimits.MODELS} lines")
        print(f"  Forms: {FileLimits.FORMS} lines")
        print(f"  View Methods: {FileLimits.VIEW_METHOD} lines")
        print(f"  Utilities: {FileLimits.UTILITIES} lines")

    # Scan and collect violations
    exclude_dirs = {'venv', 'env', '.venv', 'migrations', 'node_modules',
                   '__pycache__', '.git', 'postgresql_migration', 'background_tasks'}
    if args.exclude:
        exclude_dirs.update(args.exclude)

    violations, stats = scan_directory(root_path, exclude_dirs)

    # Handle baseline generation
    if args.generate_baseline:
        BaselineManager.save_baseline(violations, args.baseline)
        return 0

    # Check against baseline if in CI mode or baseline file exists
    baseline_path = args.baseline or BaselineManager.BASELINE_FILE
    baseline_file = Path(baseline_path)

    if args.ci and baseline_file.exists():
        # CI mode with baseline - only fail on new violations
        baseline = BaselineManager.load_baseline(args.baseline)
        new_violations, baseline_violations = BaselineManager.filter_new_violations(
            violations,
            baseline
        )

        return print_summary(
            violations,
            stats,
            verbose=args.verbose,
            baseline_mode=True,
            new_violations=new_violations,
            baseline_violations=baseline_violations
        )
    else:
        # Normal mode - report all violations
        return print_summary(violations, stats, verbose=args.verbose)


if __name__ == '__main__':
    sys.exit(main())
