#!/usr/bin/env python3
"""
Add TenantAwareManager to All TenantAwareModel Subclasses

This script automatically adds `objects = TenantAwareManager()` to all models
that inherit from TenantAwareModel but don't have the manager declared.

Usage:
    python scripts/add_tenant_managers.py --dry-run  # Preview changes
    python scripts/add_tenant_managers.py            # Apply changes
    python scripts/add_tenant_managers.py --verify   # Verify all models have manager

Security:
    - Creates backups before modifying files
    - Validates Python syntax after modifications
    - Logs all changes for audit trail

Author: Claude Code - Multi-Tenancy Security Hardening Phase 1
Date: 2025-11-03
"""

import os
import re
import ast
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Dict
import shutil
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = Path(__file__).parent.parent
APPS_DIR = BASE_DIR / 'apps'
BACKUP_DIR = BASE_DIR / 'backups' / f'tenant_managers_{datetime.now().strftime("%Y%m%d_%H%M%S")}'


class TenantManagerInjector:
    """Inject TenantAwareManager into model files."""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.modified_files = []
        self.skipped_files = []
        self.error_files = []

    def find_tenant_aware_models(self) -> List[Path]:
        """Find all Python files with TenantAwareModel subclasses."""
        model_files = []

        for file_path in APPS_DIR.rglob('*.py'):
            try:
                content = file_path.read_text()
                # Skip if file already has TenantAwareManager objects declaration
                if 'objects = TenantAwareManager()' in content or 'objects=TenantAwareManager()' in content:
                    logger.debug(f"✅ Skipping {file_path.relative_to(BASE_DIR)} - already has manager")
                    continue

                # Check if file has class inheriting from TenantAwareModel
                if re.search(r'class\s+\w+\([^)]*TenantAwareModel[^)]*\):', content):
                    model_files.append(file_path)
                    logger.debug(f"🔍 Found TenantAwareModel in {file_path.relative_to(BASE_DIR)}")

            except Exception as e:
                logger.error(f"❌ Error reading {file_path}: {e}")

        return model_files

    def parse_file(self, file_path: Path) -> Tuple[str, ast.Module]:
        """Parse Python file and return content + AST."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content, filename=str(file_path))
            return content, tree
        except SyntaxError as e:
            logger.error(f"❌ Syntax error in {file_path}: {e}")
            raise

    def find_class_definitions(self, tree: ast.Module, content: str) -> List[Dict]:
        """Find all class definitions that inherit from TenantAwareModel."""
        tenant_aware_classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from TenantAwareModel
                for base in node.bases:
                    base_name = self._get_base_name(base)
                    if 'TenantAwareModel' in base_name:
                        tenant_aware_classes.append({
                            'name': node.name,
                            'lineno': node.lineno,
                            'col_offset': node.col_offset,
                            'node': node
                        })
                        logger.debug(f"  📦 Found class {node.name} at line {node.lineno}")
                        break

        return tenant_aware_classes

    def _get_base_name(self, base) -> str:
        """Extract base class name from AST node."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
        return ''

    def check_has_objects_manager(self, class_node: ast.ClassDef) -> bool:
        """Check if class already has an 'objects' attribute."""
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'objects':
                        return True
        return False

    def inject_manager(self, file_path: Path, classes: List[Dict], content: str) -> str:
        """Inject TenantAwareManager into classes that need it."""
        lines = content.split('\n')
        modified = False

        # Check if import already exists
        has_manager_import = 'from apps.tenants.managers import TenantAwareManager' in content

        # Add import if missing (after other imports)
        if not has_manager_import:
            import_line_idx = self._find_import_insertion_point(lines)
            lines.insert(import_line_idx, 'from apps.tenants.managers import TenantAwareManager')
            modified = True
            logger.info(f"  ➕ Added TenantAwareManager import at line {import_line_idx}")

        # Add manager to each class
        for class_info in classes:
            class_node = class_info['node']

            # Skip if class already has objects manager
            if self.check_has_objects_manager(class_node):
                logger.debug(f"  ⏭️  Class {class_info['name']} already has objects manager")
                continue

            # Find the line after class definition (skip docstring if present)
            class_line_idx = class_info['lineno'] - 1
            insertion_idx = self._find_manager_insertion_point(lines, class_line_idx, class_node)

            # Detect indentation
            indent = self._detect_class_body_indent(lines, class_line_idx)

            # Insert manager declaration
            manager_line = f"{indent}objects = TenantAwareManager()"
            lines.insert(insertion_idx, manager_line)
            modified = True
            logger.info(f"  ➕ Added TenantAwareManager to {class_info['name']} at line {insertion_idx + 1}")

        if modified:
            return '\n'.join(lines)
        return content

    def _find_import_insertion_point(self, lines: List[str]) -> int:
        """Find where to insert the TenantAwareManager import."""
        last_import_idx = 0

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                last_import_idx = idx + 1
            elif stripped and not stripped.startswith('#'):
                # Found first non-import, non-comment line
                break

        return last_import_idx

    def _find_manager_insertion_point(self, lines: List[str], class_line_idx: int, class_node: ast.ClassDef) -> int:
        """Find where to insert objects manager in class body."""
        # Start right after class definition
        insertion_idx = class_line_idx + 1

        # Skip docstring if present
        if class_node.body and isinstance(class_node.body[0], ast.Expr):
            if isinstance(class_node.body[0].value, (ast.Str, ast.Constant)):
                # Find end of docstring
                for idx in range(class_line_idx + 1, len(lines)):
                    if '"""' in lines[idx] or "'''" in lines[idx]:
                        insertion_idx = idx + 1
                        break

        return insertion_idx

    def _detect_class_body_indent(self, lines: List[str], class_line_idx: int) -> str:
        """Detect indentation used in class body."""
        # Look at next non-empty line after class definition
        for idx in range(class_line_idx + 1, min(class_line_idx + 10, len(lines))):
            line = lines[idx]
            if line.strip():
                # Count leading whitespace
                indent = line[:len(line) - len(line.lstrip())]
                return indent

        # Default to 4 spaces
        return '    '

    def backup_file(self, file_path: Path):
        """Create backup of file before modification."""
        if not self.dry_run:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            backup_path = BACKUP_DIR / file_path.relative_to(BASE_DIR)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_path)
            logger.debug(f"  💾 Backed up to {backup_path.relative_to(BASE_DIR)}")

    def validate_syntax(self, content: str, file_path: Path) -> bool:
        """Validate Python syntax of modified content."""
        try:
            ast.parse(content, filename=str(file_path))
            return True
        except SyntaxError as e:
            logger.error(f"❌ Syntax error after modification: {e}")
            return False

    def process_file(self, file_path: Path) -> bool:
        """Process a single file to add TenantAwareManager."""
        try:
            logger.info(f"\n📄 Processing {file_path.relative_to(BASE_DIR)}")

            # Parse file
            content, tree = self.parse_file(file_path)

            # Find TenantAwareModel classes
            classes = self.find_class_definitions(tree, content)

            if not classes:
                logger.warning(f"  ⚠️  No TenantAwareModel classes found (false positive)")
                self.skipped_files.append(str(file_path))
                return False

            # Inject manager
            modified_content = self.inject_manager(file_path, classes, content)

            if modified_content == content:
                logger.info(f"  ⏭️  No changes needed")
                self.skipped_files.append(str(file_path))
                return False

            # Validate syntax
            if not self.validate_syntax(modified_content, file_path):
                logger.error(f"  ❌ Validation failed - skipping")
                self.error_files.append(str(file_path))
                return False

            # Write changes
            if not self.dry_run:
                self.backup_file(file_path)
                file_path.write_text(modified_content)
                logger.info(f"  ✅ Successfully modified")
            else:
                logger.info(f"  🔍 [DRY RUN] Would modify this file")

            self.modified_files.append(str(file_path))
            return True

        except Exception as e:
            logger.error(f"  ❌ Error processing file: {e}")
            self.error_files.append(str(file_path))
            return False

    def run(self):
        """Run the injection process."""
        logger.info("=" * 80)
        logger.info("TenantAwareManager Injection Script")
        logger.info("=" * 80)

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No files will be modified")

        # Find all candidate files
        logger.info("\n🔍 Scanning for TenantAwareModel subclasses...")
        model_files = self.find_tenant_aware_models()
        logger.info(f"\n📊 Found {len(model_files)} files to process\n")

        # Process each file
        for file_path in model_files:
            self.process_file(file_path)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print execution summary."""
        logger.info("\n" + "=" * 80)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Modified: {len(self.modified_files)}")
        logger.info(f"⏭️  Skipped:  {len(self.skipped_files)}")
        logger.info(f"❌ Errors:   {len(self.error_files)}")

        if self.modified_files:
            logger.info("\n📝 Modified files:")
            for file_path in self.modified_files[:10]:  # Show first 10
                logger.info(f"  - {Path(file_path).relative_to(BASE_DIR)}")
            if len(self.modified_files) > 10:
                logger.info(f"  ... and {len(self.modified_files) - 10} more")

        if self.error_files:
            logger.info("\n❌ Files with errors:")
            for file_path in self.error_files:
                logger.info(f"  - {Path(file_path).relative_to(BASE_DIR)}")

        if not self.dry_run and self.modified_files:
            logger.info(f"\n💾 Backups saved to: {BACKUP_DIR.relative_to(BASE_DIR)}")
            logger.info("\n⚠️  IMPORTANT: Run tests to verify changes!")
            logger.info("   pytest apps/ -k tenant -v")

    def verify(self):
        """Verify all TenantAwareModel subclasses have TenantAwareManager."""
        logger.info("=" * 80)
        logger.info("VERIFICATION MODE")
        logger.info("=" * 80)

        all_model_files = list(APPS_DIR.rglob('*.py'))
        tenant_model_files = []
        missing_manager_files = []

        for file_path in all_model_files:
            try:
                content = file_path.read_text()

                # Check if file has TenantAwareModel class
                if re.search(r'class\s+\w+\([^)]*TenantAwareModel[^)]*\):', content):
                    tenant_model_files.append(file_path)

                    # Check if has manager
                    if 'objects = TenantAwareManager()' not in content and 'objects=TenantAwareManager()' not in content:
                        missing_manager_files.append(file_path)

            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        logger.info(f"\n📊 Total files with TenantAwareModel: {len(tenant_model_files)}")
        logger.info(f"✅ Files with TenantAwareManager: {len(tenant_model_files) - len(missing_manager_files)}")
        logger.info(f"❌ Files MISSING TenantAwareManager: {len(missing_manager_files)}")

        if missing_manager_files:
            logger.info("\n❌ Files still missing manager:")
            for file_path in missing_manager_files:
                logger.info(f"  - {file_path.relative_to(BASE_DIR)}")
            return False
        else:
            logger.info("\n✅ All TenantAwareModel subclasses have TenantAwareManager!")
            return True


def main():
    parser = argparse.ArgumentParser(
        description='Add TenantAwareManager to all TenantAwareModel subclasses'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify all models have TenantAwareManager (no modifications)'
    )
    args = parser.parse_args()

    injector = TenantManagerInjector(dry_run=args.dry_run)

    if args.verify:
        success = injector.verify()
        sys.exit(0 if success else 1)
    else:
        injector.run()
        sys.exit(0 if not injector.error_files else 1)


if __name__ == '__main__':
    main()
