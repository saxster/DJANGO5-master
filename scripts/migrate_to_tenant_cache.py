#!/usr/bin/env python3
"""
Migrate Django Cache to Tenant-Aware Cache

This script replaces direct Django cache imports with tenant-aware cache wrapper
to prevent cross-tenant cache key collisions.

Changes:
    FROM: from django.core.cache import cache
    TO:   from apps.core.cache.tenant_aware import tenant_cache as cache

Usage:
    python scripts/migrate_to_tenant_cache.py --dry-run  # Preview changes
    python scripts/migrate_to_tenant_cache.py            # Apply changes
    python scripts/migrate_to_tenant_cache.py --verify   # Verify migration

Security Impact:
    - Prevents cross-tenant data leakage via cache
    - All cache keys automatically prefixed with tenant context
    - Maintains API compatibility (tenant_cache has same interface)

Author: Claude Code - Multi-Tenancy Security Hardening Phase 1
Date: 2025-11-03
"""

import os
import re
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Tuple
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
BACKUP_DIR = BASE_DIR / 'backups' / f'cache_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}"


# Files to skip (already using tenant_cache or not tenant-scoped)
SKIP_FILES = {
    'apps/core/cache/tenant_aware.py',  # The tenant_cache definition itself
    'apps/tenants/services/cache_service.py',  # Tenant-specific cache service
    'apps/core/management/commands/invalidate_caches.py',  # System-wide cache operations
}

# Patterns to detect and replace
IMPORT_PATTERNS = [
    # Pattern 1: from django.core.cache import cache
    (
        r'^from django\.core\.cache import cache$',
        'from apps.core.cache.tenant_aware import tenant_cache as cache'
    ),
    # Pattern 2: from django.core.cache import cache, <others>
    (
        r'^from django\.core\.cache import cache,(.+)$',
        r'from django.core.cache import\1\nfrom apps.core.cache.tenant_aware import tenant_cache as cache'
    ),
    # Pattern 3: from django.core.cache import <others>, cache
    (
        r'^from django\.core\.cache import (.+),\s*cache$',
        r'from django.core.cache import \1\nfrom apps.core.cache.tenant_aware import tenant_cache as cache'
    ),
]


class CacheMigrator:
    """Migrate Django cache usage to tenant-aware cache."""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.modified_files = []
        self.skipped_files = []
        self.error_files = []
        self.unchanged_files = []

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        rel_path = str(file_path.relative_to(BASE_DIR))

        # Skip explicitly listed files
        if rel_path in SKIP_FILES:
            return True

        # Skip test files (they may intentionally test cache behavior)
        if '/tests/' in rel_path or file_path.name.startswith('test_'):
            logger.debug(f"⏭️  Skipping test file: {rel_path}")
            return True

        # Skip migration files
        if '/migrations/' in rel_path:
            return True

        return False

    def find_cache_import_files(self) -> List[Path]:
        """Find all Python files that import Django cache."""
        cache_files = []

        for file_path in APPS_DIR.rglob('*.py'):
            if self.should_skip_file(file_path):
                continue

            try:
                content = file_path.read_text()

                # Check if already using tenant_cache
                if 'from apps.core.cache.tenant_aware import tenant_cache' in content:
                    logger.debug(f"✅ Already migrated: {file_path.relative_to(BASE_DIR)}")
                    continue

                # Check if imports Django cache
                if re.search(r'from django\.core\.cache import.*cache', content):
                    cache_files.append(file_path)
                    logger.debug(f"🔍 Found cache import in {file_path.relative_to(BASE_DIR)}")

            except Exception as e:
                logger.error(f"❌ Error reading {file_path}: {e}")

        return cache_files

    def migrate_imports(self, content: str) -> Tuple[str, bool]:
        """Migrate cache imports in file content."""
        original_content = content
        lines = content.split('\n')
        modified = False

        for idx, line in enumerate(lines):
            # Try each import pattern
            for pattern, replacement in IMPORT_PATTERNS:
                if re.match(pattern, line.strip()):
                    # Found a match
                    old_line = line
                    new_line = re.sub(pattern, replacement, line.strip())

                    # Preserve original indentation
                    indent = line[:len(line) - len(line.lstrip())]
                    lines[idx] = indent + new_line

                    logger.debug(f"  🔄 Line {idx + 1}:")
                    logger.debug(f"    - {old_line.strip()}")
                    logger.debug(f"    + {new_line}")

                    modified = True
                    break

        if modified:
            return '\n'.join(lines), True
        return original_content, False

    def validate_changes(self, original: str, modified: str, file_path: Path) -> bool:
        """Validate that changes are safe."""
        # Check that cache usage patterns still work
        # tenant_cache has same API as cache, so this should be safe

        # Ensure we didn't accidentally break imports
        if modified.count('import') < original.count('import') - 1:
            logger.error(f"  ❌ Import count mismatch - may have broken imports")
            return False

        # Ensure tenant_cache import was added
        if 'tenant_cache' not in modified:
            logger.error(f"  ❌ Failed to add tenant_cache import")
            return False

        return True

    def backup_file(self, file_path: Path):
        """Create backup of file before modification."""
        if not self.dry_run:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            backup_path = BACKUP_DIR / file_path.relative_to(BASE_DIR)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_path)
            logger.debug(f"  💾 Backed up to {backup_path.relative_to(BASE_DIR)}")

    def process_file(self, file_path: Path) -> bool:
        """Process a single file to migrate cache imports."""
        try:
            logger.info(f"\n📄 Processing {file_path.relative_to(BASE_DIR)}")

            # Read file
            content = file_path.read_text()

            # Migrate imports
            modified_content, changed = self.migrate_imports(content)

            if not changed:
                logger.info(f"  ⏭️  No changes needed")
                self.unchanged_files.append(str(file_path))
                return False

            # Validate changes
            if not self.validate_changes(content, modified_content, file_path):
                logger.error(f"  ❌ Validation failed - skipping")
                self.error_files.append(str(file_path))
                return False

            # Write changes
            if not self.dry_run:
                self.backup_file(file_path)
                file_path.write_text(modified_content)
                logger.info(f"  ✅ Successfully migrated")
            else:
                logger.info(f"  🔍 [DRY RUN] Would migrate this file")

            self.modified_files.append(str(file_path))
            return True

        except Exception as e:
            logger.error(f"  ❌ Error processing file: {e}")
            self.error_files.append(str(file_path))
            return False

    def run(self):
        """Run the migration process."""
        logger.info("=" * 80)
        logger.info("Django Cache → Tenant-Aware Cache Migration")
        logger.info("=" * 80)

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No files will be modified")

        # Find all candidate files
        logger.info("\n🔍 Scanning for cache imports...")
        cache_files = self.find_cache_import_files()
        logger.info(f"\n📊 Found {len(cache_files)} files to process\n")

        # Process each file
        for file_path in cache_files:
            self.process_file(file_path)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print execution summary."""
        logger.info("\n" + "=" * 80)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Migrated:  {len(self.modified_files)}")
        logger.info(f"⏭️  Unchanged: {len(self.unchanged_files)}")
        logger.info(f"❌ Errors:    {len(self.error_files)}")

        if self.modified_files:
            logger.info("\n📝 Migrated files:")
            for file_path in self.modified_files[:20]:  # Show first 20
                logger.info(f"  - {Path(file_path).relative_to(BASE_DIR)}")
            if len(self.modified_files) > 20:
                logger.info(f"  ... and {len(self.modified_files) - 20} more")

        if self.error_files:
            logger.info("\n❌ Files with errors:")
            for file_path in self.error_files:
                logger.info(f"  - {Path(file_path).relative_to(BASE_DIR)}")

        if not self.dry_run and self.modified_files:
            logger.info(f"\n💾 Backups saved to: {BACKUP_DIR.relative_to(BASE_DIR)}")
            logger.info("\n⚠️  IMPORTANT: Run tests to verify changes!")
            logger.info("   pytest apps/core/tests/test_cache_security_comprehensive.py -v")
            logger.info("   pytest apps/tenants/tests/ -v")

    def verify(self):
        """Verify all cache imports use tenant_cache."""
        logger.info("=" * 80)
        logger.info("VERIFICATION MODE")
        logger.info("=" * 80)

        all_python_files = list(APPS_DIR.rglob('*.py'))
        direct_cache_imports = []

        for file_path in all_python_files:
            if self.should_skip_file(file_path):
                continue

            try:
                content = file_path.read_text()

                # Check for direct Django cache import
                if re.search(r'from django\.core\.cache import.*\bcache\b', content):
                    # Make sure it's not also importing tenant_cache (that's OK)
                    if 'from apps.core.cache.tenant_aware import tenant_cache' not in content:
                        direct_cache_imports.append(file_path)

            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        logger.info(f"\n📊 Total Python files scanned: {len(all_python_files)}")
        logger.info(f"❌ Files with direct cache imports: {len(direct_cache_imports)}")

        if direct_cache_imports:
            logger.info("\n❌ Files still using direct Django cache:")
            for file_path in direct_cache_imports:
                logger.info(f"  - {file_path.relative_to(BASE_DIR)}")
            return False
        else:
            logger.info("\n✅ All cache usage is tenant-aware!")
            return True


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Django cache to tenant-aware cache'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify all cache usage is tenant-aware (no modifications)'
    )
    args = parser.parse_args()

    migrator = CacheMigrator(dry_run=args.dry_run)

    if args.verify:
        success = migrator.verify()
        sys.exit(0 if success else 1)
    else:
        migrator.run()
        sys.exit(0 if not migrator.error_files else 1)


if __name__ == '__main__':
    main()
