#!/usr/bin/env python
"""
Automated Multi-Tenancy Hardening Script

Purpose:
    Automatically add TenantAwareManager to all models that inherit from TenantAwareModel
    but don't yet have the manager declared.

Security Impact:
    - Fixes 226+ models vulnerable to cross-tenant data access
    - Prevents IDOR vulnerabilities
    - Ensures automatic tenant filtering on all queries

Usage:
    # Dry run (see what would be changed)
    python scripts/add_tenant_aware_managers.py --dry-run

    # Apply changes
    python scripts/add_tenant_aware_managers.py --apply

    # Apply to specific app only
    python scripts/add_tenant_aware_managers.py --apply --app peoples

Author: Automated Remediation System
Date: November 7, 2025
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

# Django setup
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')

import django
django.setup()

from django.apps import apps
from django.db import models


# Exclusion list: Core apps that don't need tenant isolation
EXCLUDED_APPS = [
    'admin',
    'auth',
    'contenttypes',
    'sessions',
    'messages',
    'staticfiles',
    'tenants',  # Tenant model itself doesn't need tenant manager
    'core',  # Some core models are system-wide
]

# Models that are intentionally global (don't need tenant filtering)
GLOBAL_MODELS = [
    'Tenant',
    'ContentType',
    'Permission',
    'Group',
    'Session',
]


class TenantManagerAdder:
    """Adds TenantAwareManager to models that need it."""

    def __init__(self, dry_run=True, target_app=None):
        self.dry_run = dry_run
        self.target_app = target_app
        self.changes = []
        self.skipped = []
        self.errors = []

    def should_process_model(self, model) -> bool:
        """Determine if model should have TenantAwareManager added."""
        # Skip if app is excluded
        if model._meta.app_label in EXCLUDED_APPS:
            return False

        # Skip if target app specified and doesn't match
        if self.target_app and model._meta.app_label != self.target_app:
            return False

        # Skip if model is in global list
        if model.__name__ in GLOBAL_MODELS:
            return False

        # Skip abstract models
        if model._meta.abstract:
            return False

        # Skip proxy models
        if model._meta.proxy:
            return False

        # Check if model has tenant field (either direct or inherited)
        has_tenant_field = any(
            field.name == 'tenant' for field in model._meta.get_fields()
        )

        if not has_tenant_field:
            return False

        # Check if model already has TenantAwareManager
        manager_class = model._default_manager.__class__.__name__
        if manager_class == 'TenantAwareManager':
            return False

        return True

    def find_model_file(self, model) -> Path:
        """Find the file where model is defined."""
        app_config = apps.get_app_config(model._meta.app_label)
        models_path = Path(app_config.path) / 'models'

        # Check if models.py exists
        models_file = Path(app_config.path) / 'models.py'
        if models_file.exists():
            return models_file

        # Check if models/ directory exists
        if models_path.exists() and models_path.is_dir():
            # Try to find the model in one of the files
            for py_file in models_path.glob('*.py'):
                if py_file.name == '__init__.py':
                    continue
                content = py_file.read_text()
                if f'class {model.__name__}' in content:
                    return py_file

        return None

    def add_manager_to_model(self, model) -> Tuple[bool, str]:
        """
        Add TenantAwareManager to a model class definition.

        Returns:
            (success, message)
        """
        model_file = self.find_model_file(model)
        if not model_file:
            return False, f"Could not find file for {model.__name__}"

        try:
            content = model_file.read_text()

            # Check if import already exists
            import_line = "from apps.tenants.managers import TenantAwareManager"
            has_import = import_line in content

            # Find the model class definition
            class_pattern = rf'^class {model.__name__}\([^)]+\):\s*$'
            class_match = re.search(class_pattern, content, re.MULTILINE)

            if not class_match:
                return False, f"Could not find class definition for {model.__name__}"

            class_start = class_match.end()

            # Find first non-comment, non-docstring line after class definition
            lines_after_class = content[class_start:].split('\n')
            insert_pos = class_start

            # Skip docstring if present
            in_docstring = False
            docstring_delimiter = None
            lines_to_skip = 0

            for i, line in enumerate(lines_after_class):
                stripped = line.strip()

                # Detect docstring start
                if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                    docstring_delimiter = '"""' if stripped.startswith('"""') else "'''"
                    in_docstring = True
                    if stripped.endswith(docstring_delimiter) and len(stripped) > 6:
                        # Single-line docstring
                        in_docstring = False
                        lines_to_skip = i + 1
                        continue

                # Detect docstring end
                if in_docstring and stripped.endswith(docstring_delimiter):
                    in_docstring = False
                    lines_to_skip = i + 1
                    continue

                # Found first real line after class definition/docstring
                if not in_docstring and stripped and not stripped.startswith('#'):
                    lines_to_skip = i
                    break

            # Calculate insertion point
            for i in range(lines_to_skip):
                insert_pos += len(lines_after_class[i]) + 1  # +1 for newline

            # Determine indentation (usually 4 spaces)
            indent = '    '

            # Create manager declaration
            manager_declaration = f"{indent}objects = TenantAwareManager()\n\n"

            # Build new content
            new_content = content[:insert_pos] + manager_declaration + content[insert_pos:]

            # Add import if needed
            if not has_import:
                # Find where to add import (after other imports)
                import_section_end = 0
                for line_num, line in enumerate(new_content.split('\n')):
                    if line.strip().startswith('import ') or line.strip().startswith('from '):
                        import_section_end = line_num
                    elif import_section_end > 0 and line.strip() == '':
                        break

                lines = new_content.split('\n')
                lines.insert(import_section_end + 1, import_line)
                new_content = '\n'.join(lines)

            if self.dry_run:
                return True, f"Would add TenantAwareManager to {model._meta.app_label}.{model.__name__}"
            else:
                # Write changes
                model_file.write_text(new_content)
                return True, f"Added TenantAwareManager to {model._meta.app_label}.{model.__name__}"

        except Exception as e:
            return False, f"Error processing {model.__name__}: {str(e)}"

    def process_all_models(self):
        """Process all models in the Django project."""
        all_models = apps.get_models()

        print(f"Scanning {len(all_models)} models...")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'APPLY CHANGES'}")
        if self.target_app:
            print(f"Target app: {self.target_app}")
        print("-" * 80)

        models_to_process = []

        for model in all_models:
            if self.should_process_model(model):
                models_to_process.append(model)

        print(f"\nFound {len(models_to_process)} models needing TenantAwareManager\n")

        for model in models_to_process:
            success, message = self.add_manager_to_model(model)

            if success:
                self.changes.append(message)
                print(f"✓ {message}")
            else:
                self.errors.append(message)
                print(f"✗ {message}")

        self.print_summary()

    def print_summary(self):
        """Print summary of changes."""
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Changes made: {len(self.changes)}")
        print(f"Errors: {len(self.errors)}")
        print()

        if self.errors:
            print("ERRORS:")
            for error in self.errors:
                print(f"  - {error}")
            print()

        if self.dry_run:
            print("*** DRY RUN MODE - No files were modified ***")
            print("Run with --apply to make changes")
        else:
            print("✓ Changes have been applied")
            print("\nNext steps:")
            print("1. Review changes: git diff")
            print("2. Run tests: python -m pytest tests/security/test_tenant_isolation.py")
            print("3. Check diagnostics: python manage.py check")
            print("4. Commit changes: git add . && git commit -m 'Add TenantAwareManager to models'")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Add TenantAwareManager to all tenant-aware models'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply changes (default is dry-run)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Dry run mode (default)'
    )
    parser.add_argument(
        '--app',
        type=str,
        help='Target specific app only'
    )

    args = parser.parse_args()

    dry_run = not args.apply

    adder = TenantManagerAdder(dry_run=dry_run, target_app=args.app)
    adder.process_all_models()


if __name__ == '__main__':
    main()
