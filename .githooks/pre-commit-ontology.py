#!/usr/bin/env python3
"""
Pre-commit hook to enforce @ontology decorator usage on critical code paths.

This hook uses AST parsing to detect new/modified classes and functions in:
- apps/*/models/
- apps/*/services/
- apps/*/api/
- apps/*/middleware/

Exemptions: tests/, migrations/, management/commands/

Exit codes:
  0 - All critical code properly decorated
  1 - Missing decorators detected (commit blocked)
"""

import ast
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict


# Critical paths that require @ontology decorator
CRITICAL_PATHS = [
    "apps/*/models/",
    "apps/*/services/",
    "apps/*/api/",
    "apps/*/middleware/",
]

# Exempted paths
EXEMPT_PATHS = [
    "tests/",
    "migrations/",
    "management/commands/",
    "__init__.py",
]


class OntologyVisitor(ast.NodeVisitor):
    """AST visitor to find classes and functions without @ontology decorator."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.missing_decorators = []

    def visit_ClassDef(self, node: ast.ClassDef):
        """Check class definitions for @ontology decorator."""
        if not self._has_ontology_decorator(node):
            self.missing_decorators.append({
                'type': 'class',
                'name': node.name,
                'line': node.lineno,
            })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check function definitions for @ontology decorator."""
        # Skip private methods and dunder methods
        if node.name.startswith('_'):
            return

        # Skip if inside a class (handled by class check)
        if self._is_method(node):
            return

        if not self._has_ontology_decorator(node):
            self.missing_decorators.append({
                'type': 'function',
                'name': node.name,
                'line': node.lineno,
            })
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Check async function definitions for @ontology decorator."""
        # Skip private methods and dunder methods
        if node.name.startswith('_'):
            return

        # Skip if inside a class
        if self._is_method(node):
            return

        if not self._has_ontology_decorator(node):
            self.missing_decorators.append({
                'type': 'async function',
                'name': node.name,
                'line': node.lineno,
            })
        self.generic_visit(node)

    def _has_ontology_decorator(self, node) -> bool:
        """Check if node has @ontology decorator."""
        for decorator in node.decorator_list:
            # Handle simple decorator: @ontology
            if isinstance(decorator, ast.Name) and decorator.id == 'ontology':
                return True
            # Handle decorator with call: @ontology()
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == 'ontology':
                    return True
        return False

    def _is_method(self, node) -> bool:
        """Check if function node is inside a class (is a method)."""
        # This is a simplified check - in practice, we track context
        # For now, we'll allow methods to be checked at class level
        return False


def get_staged_python_files() -> List[str]:
    """Get list of staged Python files from git."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.strip().split('\n')
        return [f for f in files if f.endswith('.py') and f]
    except subprocess.CalledProcessError:
        return []


def is_critical_path(filepath: str) -> bool:
    """Check if file is in a critical path requiring @ontology decorator."""
    path = Path(filepath)
    path_str = str(path)

    # Check exemptions first
    for exempt in EXEMPT_PATHS:
        if exempt in path_str:
            return False

    # Check if in critical paths
    for critical_pattern in CRITICAL_PATHS:
        pattern_parts = critical_pattern.split('/')
        if len(pattern_parts) >= 2:
            # Check apps/*/models/ pattern
            if path_str.startswith('apps/'):
                parts = path.parts
                if len(parts) >= 3:
                    # parts[0] = 'apps', parts[1] = app_name, parts[2] = 'models'/'services'/etc
                    if parts[2] in ['models', 'services', 'api', 'middleware']:
                        return True

    return False


def check_ontology_decorators(filepath: str) -> List[Dict]:
    """
    Parse Python file with AST and check for @ontology decorators.

    Returns:
        List of missing decorator information (empty if all decorated)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source, filename=filepath)
        visitor = OntologyVisitor(filepath)
        visitor.visit(tree)

        return visitor.missing_decorators
    except SyntaxError as e:
        print(f"⚠️  Syntax error in {filepath}:{e.lineno}: {e.msg}")
        return []
    except (OSError, IOError, UnicodeDecodeError) as e:
        print(f"⚠️  Error reading or parsing {filepath}: {e}")
        return []


def get_decorator_template(item_type: str, item_name: str, filepath: str) -> str:
    """Generate copy-paste ready @ontology decorator template."""

    # Determine component type from path
    if '/models/' in filepath:
        component = 'model'
    elif '/services/' in filepath:
        component = 'service'
    elif '/api/' in filepath:
        component = 'api'
    elif '/middleware/' in filepath:
        component = 'middleware'
    else:
        component = 'component'

    template = f"""
# Copy-paste this above {item_type} '{item_name}':

@ontology(
    component_type="{component}",
    layer="{get_layer_suggestion(component)}",
    purpose="TODO: Brief description of what this {item_type} does",
    business_context="TODO: Business domain this serves",
    dependencies=[],  # TODO: List key dependencies
    complexity="medium",  # TODO: low/medium/high
    stability="stable"  # TODO: experimental/stable/deprecated
)
"""
    return template


def get_layer_suggestion(component: str) -> str:
    """Suggest architectural layer based on component type."""
    layer_map = {
        'model': 'data',
        'service': 'business',
        'api': 'presentation',
        'middleware': 'infrastructure',
    }
    return layer_map.get(component, 'business')


def format_violation_report(filepath: str, missing: List[Dict]) -> str:
    """Format a nice violation report for a file."""
    report = f"\n❌ {filepath}\n"
    report += "=" * 80 + "\n"

    for item in missing:
        report += f"  Line {item['line']}: {item['type']} '{item['name']}' missing @ontology\n"
        report += get_decorator_template(item['type'], item['name'], filepath)
        report += "\n"

    return report


def main():
    """Main pre-commit hook execution."""
    print("🔍 Checking for @ontology decorators on critical code paths...")

    staged_files = get_staged_python_files()
    if not staged_files:
        print("✅ No Python files to check")
        return 0

    violations = {}
    files_checked = 0

    for filepath in staged_files:
        if not Path(filepath).exists():
            continue

        if not is_critical_path(filepath):
            continue

        files_checked += 1
        missing = check_ontology_decorators(filepath)

        if missing:
            violations[filepath] = missing

    if not violations:
        print(f"✅ All {files_checked} critical files properly decorated")
        return 0

    # Print violations
    print("\n" + "=" * 80)
    print("🚫 COMMIT BLOCKED - Missing @ontology decorators")
    print("=" * 80)

    total_missing = sum(len(items) for items in violations.values())
    print(f"\nFound {total_missing} undocumented items across {len(violations)} files:\n")

    for filepath, missing in violations.items():
        print(format_violation_report(filepath, missing))

    print("=" * 80)
    print("📚 Documentation: .kiro/steering/ontology_system.md")
    print("🔧 Quick fix: Add @ontology decorator using templates above")
    print("⚠️  Critical paths require ontology documentation for:")
    print("   - Knowledge graph generation")
    print("   - Dependency tracking")
    print("   - Architecture compliance")
    print("=" * 80)

    return 1


if __name__ == '__main__':
    sys.exit(main())
