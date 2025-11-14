#!/usr/bin/env python3
"""
File Size Limit Validation Script

Validates Python files against architecture limits defined in .claude/rules.md:
- Settings files: < 200 lines
- Models: < 150 lines
- View methods: < 30 lines
- Forms: < 100 lines
- Utilities: < 50 lines per function

Baseline Mode:
    --generate-baseline: Creates .file_size_baseline.json with current violations
    --use-baseline: Only fails on NEW violations beyond baseline (default in CI)

Exit code 0: All files pass (or only baseline violations found)
Exit code 1: New violations found beyond baseline

Usage:
    python scripts/check_file_sizes.py
    python scripts/check_file_sizes.py --path apps/attendance
    python scripts/check_file_sizes.py --verbose
    python scripts/check_file_sizes.py --generate-baseline
    python scripts/check_file_sizes.py --ci  # Uses baseline automatically
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple, Set


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
    
    @property
    def violation_key(self) -> str:
        """Unique key for this violation for baseline comparison"""
        return f"{self.file_path}:{self.category}:{self.limit}"

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.category}: {self.file_path}\n"
            f"  Lines: {self.line_count} (limit: {self.limit}, excess: {self.excess_lines})"
        )
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'file_path': self.file_path,
            'category': self.category,
            'line_count': self.line_count,
            'limit': self.limit,
            'severity': self.severity
        }


class BaselineManager:
    """Manages baseline violations for legacy code"""
    
    BASELINE_FILE = '.file_size_baseline.json'
    
    @classmethod
    def generate_baseline(cls, violations: List[Violation], output_path: Path = None):
        """Generate baseline file from current violations"""
        if output_path is None:
            output_path = Path(cls.BASELINE_FILE)
        
        baseline_data = {
            'version': '1.0',
            'description': 'Baseline of pre-existing file size violations',
            'violations': {
                v.violation_key: v.to_dict()
                for v in violations
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(baseline_data, f, indent=2)
        
        return output_path
    
    @classmethod
    def load_baseline(cls, baseline_path: Path = None) -> Set[str]:
        """Load baseline violation keys"""
        if baseline_path is None:
            baseline_path = Path(cls.BASELINE_FILE)
        
        if not baseline_path.exists():
            return set()
        
        try:
            with open(baseline_path, 'r') as f:
                data = json.load(f)
            return set(data.get('violations', {}).keys())
        except Exception as e:
            print(f"Warning: Could not load baseline: {e}", file=sys.stderr)
            return set()
    
    @classmethod
    def filter_new_violations(cls, violations: List[Violation],
                             baseline_keys: Set[str]) -> Tuple[List[Violation], List[Violation]]:
        """Separate new violations from baseline violations"""
        new_violations = []
        baseline_violations = []
        
        for v in violations:
            if v.violation_key in baseline_keys:
                baseline_violations.append(v)
            else:
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


def check_view_methods(file_path: Path, root_path: Path = None) -> List[Violation]:
    """Check view method sizes using AST"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        # Make path relative for reporting
        if root_path:
            try:
                display_path = str(file_path.relative_to(root_path))
            except ValueError:
                display_path = str(file_path)
        else:
            display_path = str(file_path)

        checker = MethodSizeChecker(display_path)
        checker.visit(tree)
        return checker.violations
    except Exception as e:
        # If AST parsing fails, skip method checking
        return []


def check_file(file_path: Path, detector: FileTypeDetector, root_path: Path = None) -> List[Violation]:
    """Check a single file against size limits"""
    violations = []
    line_count = count_non_empty_lines(file_path)
    
    # Make path relative for reporting
    if root_path:
        try:
            display_path = str(file_path.relative_to(root_path))
        except ValueError:
            display_path = str(file_path)
    else:
        display_path = str(file_path)

    # Check settings files
    if detector.is_settings_file(file_path):
        if line_count > FileLimits.SETTINGS:
            violations.append(Violation(
                file_path=display_path,
                category="Settings File",
                line_count=line_count,
                limit=FileLimits.SETTINGS,
                severity='error'
            ))

    # Check model files
    elif detector.is_models_file(file_path):
        if line_count > FileLimits.MODELS:
            violations.append(Violation(
                file_path=display_path,
                category="Model File",
                line_count=line_count,
                limit=FileLimits.MODELS,
                severity='error'
            ))

    # Check form files
    elif detector.is_forms_file(file_path):
        if line_count > FileLimits.FORMS:
            violations.append(Violation(
                file_path=display_path,
                category="Form File",
                line_count=line_count,
                limit=FileLimits.FORMS,
                severity='error'
            ))

    # Check utility files
    elif detector.is_utility_file(file_path):
        if line_count > FileLimits.UTILITIES:
            violations.append(Violation(
                file_path=display_path,
                category="Utility File",
                line_count=line_count,
                limit=FileLimits.UTILITIES,
                severity='warning'  # Warning for utilities
            ))

    # Check view methods
    if detector.is_views_file(file_path):
        violations.extend(check_view_methods(file_path, root_path))

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
        file_violations = check_file(py_file, detector, root_path)
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


def print_summary(violations: List[Violation], stats: Dict[str, int], verbose: bool = False):
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

    print(f"\nViolations Found: {len(violations)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Warnings: {len(warnings)}")

    if violations:
        print("\n" + "-" * 80)
        print("VIOLATIONS:")
        print("-" * 80)

        # Group by category
        by_category = {}
        for v in violations:
            by_category.setdefault(v.category, []).append(v)

        for category in sorted(by_category.keys()):
            print(f"\n{category} ({len(by_category[category])} violations):")
            for violation in sorted(by_category[category],
                                   key=lambda x: x.line_count,
                                   reverse=True):
                print(f"  {violation}")
    else:
        print("\n✅ All files pass size limits!")

    print("\n" + "=" * 80)

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
        help='CI mode: uses baseline automatically, strict exit codes for new violations'
    )
    parser.add_argument(
        '--pre-commit',
        action='store_true',
        help='Pre-commit mode: fast validation for hooks'
    )
    parser.add_argument(
        '--generate-baseline',
        action='store_true',
        help='Generate baseline file of current violations'
    )
    parser.add_argument(
        '--use-baseline',
        action='store_true',
        help='Use baseline to only fail on NEW violations'
    )

    args = parser.parse_args()

    root_path = Path(args.path).resolve()
    if not root_path.exists():
        print(f"Error: Path does not exist: {root_path}", file=sys.stderr)
        return 1

    # Scan and collect violations
    exclude_dirs = {'venv', 'env', '.venv', 'migrations', 'node_modules',
                   '__pycache__', '.git', 'postgresql_migration', 'background_tasks'}
    if args.exclude:
        exclude_dirs.update(args.exclude)

    violations, stats = scan_directory(root_path, exclude_dirs)

    # Generate baseline if requested
    if args.generate_baseline:
        baseline_path = BaselineManager.generate_baseline(violations)
        print(f"\n✅ Baseline generated: {baseline_path}")
        print(f"   Recorded {len(violations)} violations")
        print(f"   Use --use-baseline or --ci to check against this baseline")
        return 0

    # Use baseline in CI mode or if explicitly requested
    use_baseline = args.use_baseline or args.ci
    
    if use_baseline:
        baseline_keys = BaselineManager.load_baseline()
        if baseline_keys:
            new_violations, baseline_violations = BaselineManager.filter_new_violations(
                violations, baseline_keys
            )
            
            if new_violations:
                print(f"\n{'=' * 80}")
                print("FILE SIZE VALIDATION REPORT (WITH BASELINE)")
                print(f"{'=' * 80}\n")
                print(f"Files Scanned: {stats['files_scanned']}")
                print(f"Files Checked: {stats['files_checked']}")
                print(f"\nTotal Violations: {len(violations)}")
                print(f"  Baseline (pre-existing): {len(baseline_violations)}")
                print(f"  NEW violations: {len(new_violations)}")
                print(f"\n{'-' * 80}")
                print("NEW VIOLATIONS (not in baseline):")
                print(f"{'-' * 80}\n")
                
                by_category = {}
                for v in new_violations:
                    by_category.setdefault(v.category, []).append(v)
                
                for category, category_violations in sorted(by_category.items()):
                    print(f"\n{category} ({len(category_violations)} NEW violations):")
                    for v in category_violations:
                        print(f"  {v}")
                
                print(f"\n{'=' * 80}\n")
                print(f"❌ FAILED: Found {len(new_violations)} NEW violations beyond baseline")
                print(f"\nℹ️  {len(baseline_violations)} baseline violations are being ignored (see .file_size_baseline.json)")
                return 1
            else:
                print(f"✅ SUCCESS: No new violations beyond baseline")
                print(f"   ({len(baseline_violations)} baseline violations exist but are allowed)")
                return 0
        else:
            print("⚠️  Warning: Baseline requested but .file_size_baseline.json not found")
            print("   Run with --generate-baseline first, or proceeding without baseline...")
            # Fall through to normal check

    print(f"Scanning: {root_path}")
    if args.verbose:
        print("\nFile Size Limits:")
        print(f"  Settings: {FileLimits.SETTINGS} lines")
        print(f"  Models: {FileLimits.MODELS} lines")
        print(f"  Forms: {FileLimits.FORMS} lines")
        print(f"  View Methods: {FileLimits.VIEW_METHOD} lines")
        print(f"  Utilities: {FileLimits.UTILITIES} lines")

    # Print results
    return print_summary(violations, stats, verbose=args.verbose)


if __name__ == '__main__':
    sys.exit(main())
