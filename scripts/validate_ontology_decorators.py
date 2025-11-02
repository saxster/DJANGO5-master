#!/usr/bin/env python
"""
Ontology Decorator Validation Script

Validates that @ontology decorators are complete and follow quality standards.

Usage:
    python scripts/validate_ontology_decorators.py --file path/to/file.py
    python scripts/validate_ontology_decorators.py --app peoples
    python scripts/validate_ontology_decorators.py --git-diff
    python scripts/validate_ontology_decorators.py --all

Requirements:
    - Run from project root directory
    - Python 3.8+
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import subprocess

# ANSI color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class OntologyValidator:
    """Validates @ontology decorator completeness and quality."""

    # Required fields for all decorators
    REQUIRED_FIELDS = [
        'domain',
        'concept',
        'purpose',
        'criticality',
        'security_boundary',
        'inputs',
        'outputs',
        'side_effects',
        'depends_on',
        'used_by',
        'tags',
        'security_notes',
        'performance_notes',
        'examples',
    ]

    # Valid criticality levels
    VALID_CRITICALITY = ['critical', 'high', 'medium', 'low']

    # Common domains (not exhaustive, but helps catch typos)
    COMMON_DOMAINS = [
        'people', 'operations', 'security', 'attendance', 'reports',
        'infrastructure', 'onboarding', 'assets', 'help_desk', 'wellness',
        'billing', 'scheduler', 'api',
    ]

    # PII-related keywords to check for in field names
    PII_KEYWORDS = [
        'name', 'email', 'phone', 'address', 'ssn', 'passport', 'license',
        'birth', 'gender', 'photo', 'image', 'biometric', 'fingerprint',
        'location', 'gps', 'latitude', 'longitude', 'ip_address', 'user_agent',
        'salary', 'wage', 'payment', 'medical', 'health', 'disability',
    ]

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.errors = []
        self.warnings = []
        self.tree = None

    def validate(self) -> Tuple[List[str], List[str]]:
        """
        Validate ontology decorators in file.

        Returns:
            Tuple of (errors, warnings)
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.tree = ast.parse(content, filename=str(self.file_path))
        except Exception as e:
            self.errors.append(f"Failed to parse file: {e}")
            return self.errors, self.warnings

        # Find @ontology decorators
        decorators = self._find_ontology_decorators()

        if not decorators:
            self.warnings.append("No @ontology decorators found in file")
            return self.errors, self.warnings

        # Validate each decorator
        for decorator, node_name in decorators:
            self._validate_decorator(decorator, node_name)

        return self.errors, self.warnings

    def _find_ontology_decorators(self) -> List[Tuple[ast.Call, str]]:
        """Find all @ontology decorator calls in the AST."""
        decorators = []

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name) and decorator.func.id == 'ontology':
                            decorators.append((decorator, node.name))
                        elif isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'ontology':
                            decorators.append((decorator, node.name))

        return decorators

    def _validate_decorator(self, decorator: ast.Call, node_name: str):
        """Validate a single @ontology decorator call."""
        # Extract keyword arguments
        kwargs = {kw.arg: kw.value for kw in decorator.keywords}

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in kwargs:
                self.errors.append(
                    f"{node_name}: Missing required field '{field}'"
                )

        # Validate domain
        if 'domain' in kwargs:
            domain = self._get_string_value(kwargs['domain'])
            if domain and domain not in self.COMMON_DOMAINS:
                self.warnings.append(
                    f"{node_name}: domain='{domain}' not in common domains. "
                    f"Common domains: {', '.join(self.COMMON_DOMAINS)}"
                )

        # Validate criticality
        if 'criticality' in kwargs:
            criticality = self._get_string_value(kwargs['criticality'])
            if criticality and criticality not in self.VALID_CRITICALITY:
                self.errors.append(
                    f"{node_name}: criticality='{criticality}' invalid. "
                    f"Must be one of: {', '.join(self.VALID_CRITICALITY)}"
                )

        # Validate purpose length (should be substantive)
        if 'purpose' in kwargs:
            purpose = self._get_string_value(kwargs['purpose'])
            if purpose and len(purpose) < 50:
                self.warnings.append(
                    f"{node_name}: purpose is very short ({len(purpose)} chars). "
                    f"Provide 2-3 sentences describing what and why."
                )

        # Validate inputs (check for PII marking)
        if 'inputs' in kwargs:
            inputs_list = self._get_list_value(kwargs['inputs'])
            if inputs_list:
                self._validate_inputs(inputs_list, node_name)

        # Validate security_notes
        if 'security_notes' in kwargs:
            sec_notes = self._get_string_value(kwargs['security_notes'])
            if sec_notes:
                self._validate_security_notes(sec_notes, node_name)

        # Validate tags (should have at least 3)
        if 'tags' in kwargs:
            tags = self._get_list_value(kwargs['tags'])
            if tags is not None and len(tags) < 3:
                self.warnings.append(
                    f"{node_name}: Only {len(tags)} tags. Recommend at least 5 tags."
                )

        # Validate examples (should have at least 2)
        if 'examples' in kwargs:
            examples = self._get_list_value(kwargs['examples'])
            if examples is not None and len(examples) < 2:
                self.warnings.append(
                    f"{node_name}: Only {len(examples)} examples. Recommend at least 2-3 examples."
                )

        # Check security_boundary for critical components
        if 'criticality' in kwargs and 'security_boundary' in kwargs:
            criticality = self._get_string_value(kwargs['criticality'])
            sec_boundary = self._get_bool_value(kwargs['security_boundary'])
            if criticality == 'critical' and not sec_boundary:
                self.warnings.append(
                    f"{node_name}: criticality='critical' but security_boundary=False. "
                    f"Consider setting security_boundary=True for critical components."
                )

    def _validate_inputs(self, inputs_list: List, node_name: str):
        """Validate inputs list for PII field marking."""
        for i, input_dict in enumerate(inputs_list):
            if not isinstance(input_dict, dict):
                continue

            field_name = input_dict.get('name', f'input_{i}')

            # Check if field name suggests PII
            is_potential_pii = any(
                keyword in field_name.lower()
                for keyword in self.PII_KEYWORDS
            )

            if is_potential_pii:
                sensitive = input_dict.get('sensitive', False)
                if not sensitive:
                    self.errors.append(
                        f"{node_name}: Field '{field_name}' appears to be PII "
                        f"but 'sensitive' is not set to True"
                    )

    def _validate_security_notes(self, sec_notes: str, node_name: str):
        """Validate security_notes content."""
        # Check for NEVER section
        if 'NEVER' not in sec_notes.upper():
            self.warnings.append(
                f"{node_name}: security_notes missing 'NEVER' section. "
                f"Document anti-patterns and security violations."
            )

        # Check for minimum content (at least 3 numbered sections)
        section_count = sec_notes.count('\n1.') + sec_notes.count('\n2.') + sec_notes.count('\n3.')
        if section_count < 2:  # Looking for at least sections 1, 2, 3
            self.warnings.append(
                f"{node_name}: security_notes appears incomplete. "
                f"Provide at least 3 security aspects + NEVER section."
            )

    def _get_string_value(self, node) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.JoinedStr):
            # f-string - try to reconstruct
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif isinstance(value, ast.Str):
                    parts.append(value.s)
            return ''.join(parts) if parts else None
        return None

    def _get_list_value(self, node) -> Optional[List]:
        """Extract list value from AST node (basic extraction)."""
        if isinstance(node, ast.List):
            elements = []
            for elt in node.elts:
                if isinstance(elt, (ast.Constant, ast.Str)):
                    val = self._get_string_value(elt)
                    if val:
                        elements.append(val)
                elif isinstance(elt, ast.Dict):
                    # Dictionary element (for inputs, outputs, etc.)
                    dict_val = {}
                    for key, value in zip(elt.keys, elt.values):
                        key_str = self._get_string_value(key)
                        if key_str == 'name':
                            dict_val['name'] = self._get_string_value(value)
                        elif key_str == 'sensitive':
                            dict_val['sensitive'] = self._get_bool_value(value)
                    if dict_val:
                        elements.append(dict_val)
            return elements
        return None

    def _get_bool_value(self, node) -> Optional[bool]:
        """Extract boolean value from AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return node.value
        elif isinstance(node, ast.NameConstant):
            return node.value
        return None


def get_git_diff_files() -> List[Path]:
    """Get list of modified Python files from git diff."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=ACMR', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        files = [
            Path(line.strip())
            for line in result.stdout.splitlines()
            if line.strip().endswith('.py')
        ]
        return files
    except subprocess.CalledProcessError:
        print(f"{RED}Error: Failed to get git diff{RESET}")
        return []


def get_app_files(app_name: str) -> List[Path]:
    """Get all Python files in an app."""
    app_path = Path('apps') / app_name
    if not app_path.exists():
        print(f"{RED}Error: App '{app_name}' not found at {app_path}{RESET}")
        return []

    files = list(app_path.rglob('*.py'))
    # Exclude migrations and __pycache__
    files = [
        f for f in files
        if 'migrations' not in f.parts and '__pycache__' not in f.parts
    ]
    return files


def get_all_files() -> List[Path]:
    """Get all Python files in apps directory."""
    apps_path = Path('apps')
    if not apps_path.exists():
        print(f"{RED}Error: 'apps' directory not found{RESET}")
        return []

    files = list(apps_path.rglob('*.py'))
    # Exclude migrations and __pycache__
    files = [
        f for f in files
        if 'migrations' not in f.parts and '__pycache__' not in f.parts
    ]
    return files


def validate_file(file_path: Path) -> Tuple[int, int]:
    """
    Validate a single file.

    Returns:
        Tuple of (error_count, warning_count)
    """
    print(f"\n{BOLD}Validating: {file_path}{RESET}")

    validator = OntologyValidator(file_path)
    errors, warnings = validator.validate()

    # Print errors
    if errors:
        print(f"{RED}✗ Errors:{RESET}")
        for error in errors:
            print(f"  {RED}• {error}{RESET}")

    # Print warnings
    if warnings:
        print(f"{YELLOW}⚠ Warnings:{RESET}")
        for warning in warnings:
            print(f"  {YELLOW}• {warning}{RESET}")

    # Print success
    if not errors and not warnings:
        print(f"{GREEN}✓ All checks passed{RESET}")

    return len(errors), len(warnings)


def main():
    parser = argparse.ArgumentParser(
        description='Validate @ontology decorator completeness and quality'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', type=Path, help='Validate single file')
    group.add_argument('--app', type=str, help='Validate all files in app')
    group.add_argument('--git-diff', action='store_true', help='Validate modified files (git diff)')
    group.add_argument('--all', action='store_true', help='Validate all files in apps/')

    args = parser.parse_args()

    # Get list of files to validate
    files = []
    if args.file:
        files = [args.file]
    elif args.app:
        files = get_app_files(args.app)
    elif args.git_diff:
        files = get_git_diff_files()
    elif args.all:
        files = get_all_files()

    if not files:
        print(f"{YELLOW}No files to validate{RESET}")
        return 0

    print(f"{BLUE}Validating {len(files)} file(s)...{RESET}")

    # Validate each file
    total_errors = 0
    total_warnings = 0
    files_with_errors = []
    files_with_warnings = []

    for file_path in files:
        if not file_path.exists():
            print(f"{RED}Error: File not found: {file_path}{RESET}")
            continue

        error_count, warning_count = validate_file(file_path)
        total_errors += error_count
        total_warnings += warning_count

        if error_count > 0:
            files_with_errors.append(file_path)
        if warning_count > 0:
            files_with_warnings.append(file_path)

    # Print summary
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}Summary{RESET}")
    print(f"{'=' * 60}")
    print(f"Files validated: {len(files)}")
    print(f"{RED}Errors: {total_errors}{RESET} (in {len(files_with_errors)} files)")
    print(f"{YELLOW}Warnings: {total_warnings}{RESET} (in {len(files_with_warnings)} files)")

    if total_errors == 0 and total_warnings == 0:
        print(f"\n{GREEN}{BOLD}✓ All validations passed!{RESET}")
        return 0
    elif total_errors == 0:
        print(f"\n{YELLOW}⚠ Validation passed with warnings{RESET}")
        return 0
    else:
        print(f"\n{RED}✗ Validation failed - fix errors before committing{RESET}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
