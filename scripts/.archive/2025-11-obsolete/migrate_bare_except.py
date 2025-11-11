#!/usr/bin/env python3
"""
Automated Bare Except Migration Script

Systematically replaces bare except blocks with specific exception types based on
context analysis. Follows .claude/rules.md Rule #11 - Exception Handling Specificity.

Usage:
    python scripts/migrate_bare_except.py --dry-run           # Preview changes
    python scripts/migrate_bare_except.py --fix               # Apply changes
    python scripts/migrate_bare_except.py --report REPORT.md  # Generate report

Context-aware exception detection:
- Django model/database operations → DatabaseError, IntegrityError, ObjectDoesNotExist
- Settings access → AttributeError, ImportError
- File I/O → OSError, IOError, PermissionError
- JSON parsing → json.JSONDecodeError, ValueError
- Network calls → requests.RequestException, TimeoutError
- Python inspect module → OSError, TypeError, AttributeError
"""

import os
import re
import sys
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

# Context-specific exception mappings
EXCEPTION_PATTERNS = {
    # Django ORM operations
    'django_orm': {
        'patterns': [
            r'\.save\(',
            r'\.create\(',
            r'\.update\(',
            r'\.delete\(',
            r'\.filter\(',
            r'\.get\(',
            r'\.objects\.',
            r'ForeignKey',
            r'ManyToMany',
        ],
        'exceptions': '(DatabaseError, IntegrityError, ObjectDoesNotExist)',
        'imports': [
            'from django.db import DatabaseError, IntegrityError',
            'from django.core.exceptions import ObjectDoesNotExist',
        ]
    },

    # Settings access
    'settings_access': {
        'patterns': [
            r'getattr\(settings',
            r'settings\.',
            r'from django.conf import settings',
        ],
        'exceptions': '(AttributeError, ImportError)',
        'imports': []  # Built-in exceptions
    },

    # File I/O operations
    'file_io': {
        'patterns': [
            r'open\(',
            r'\.read\(',
            r'\.write\(',
            r'os\.path\.',
            r'Path\(',
            r'\.exists\(',
        ],
        'exceptions': '(OSError, IOError, PermissionError)',
        'imports': []  # Built-in exceptions
    },

    # JSON operations
    'json_ops': {
        'patterns': [
            r'json\.loads\(',
            r'json\.dumps\(',
            r'json\.load\(',
        ],
        'exceptions': '(json.JSONDecodeError, ValueError, TypeError)',
        'imports': ['import json']
    },

    # Network operations
    'network': {
        'patterns': [
            r'requests\.',
            r'urllib\.',
            r'http\.',
        ],
        'exceptions': '(requests.RequestException, TimeoutError, ConnectionError)',
        'imports': ['import requests']
    },

    # Python inspect module
    'inspect_module': {
        'patterns': [
            r'inspect\.',
            r'getsourcelines',
            r'getfile',
        ],
        'exceptions': '(OSError, TypeError, AttributeError)',
        'imports': ['import inspect']
    },

    # Cache operations
    'cache_ops': {
        'patterns': [
            r'cache\.get\(',
            r'cache\.set\(',
            r'from django.core.cache',
        ],
        'exceptions': '(ConnectionError, TimeoutError)',
        'imports': []
    },

    # Default fallback
    'generic': {
        'patterns': [],
        'exceptions': '(ValueError, TypeError, AttributeError)',
        'imports': []
    }
}


@dataclass
class BareExceptFix:
    """Represents a bare except fix"""
    file_path: str
    line_number: int
    original_line: str
    new_line: str
    detected_context: str
    confidence: str  # HIGH, MEDIUM, LOW


class BareExceptMigrator:
    """Migrates bare except blocks to specific exception types"""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.fixes: List[BareExceptFix] = []

    def detect_context(self, file_content: str, except_line_num: int) -> Tuple[str, str]:
        """
        Detect the context around a bare except block to determine appropriate exceptions.

        Returns: (context_type, exception_string)
        """
        lines = file_content.split('\n')

        # Get try block content (lines before the except)
        try_block_start = except_line_num - 1
        while try_block_start > 0:
            line = lines[try_block_start].strip()
            if line.startswith('try:'):
                break
            try_block_start -= 1

        # Extract try block content
        try_block = '\n'.join(lines[try_block_start:except_line_num])

        # Check patterns in order of specificity
        matched_contexts = []

        for context_name, config in EXCEPTION_PATTERNS.items():
            if context_name == 'generic':
                continue  # Skip generic, use as fallback

            for pattern in config['patterns']:
                if re.search(pattern, try_block, re.IGNORECASE):
                    matched_contexts.append(context_name)
                    break

        # Determine best match
        if matched_contexts:
            # Combine exception types for multiple contexts
            if len(matched_contexts) == 1:
                context = matched_contexts[0]
                return context, EXCEPTION_PATTERNS[context]['exceptions']
            else:
                # Multiple contexts - combine exceptions
                all_exceptions = set()
                for ctx in matched_contexts:
                    exc_str = EXCEPTION_PATTERNS[ctx]['exceptions']
                    # Extract exception names
                    exc_names = re.findall(r'(\w+Error|\w+Exception)', exc_str)
                    all_exceptions.update(exc_names)

                combined = '(' + ', '.join(sorted(all_exceptions)) + ')'
                return '+'.join(matched_contexts), combined
        else:
            # Fallback to generic
            return 'generic', EXCEPTION_PATTERNS['generic']['exceptions']

    def analyze_file(self, file_path: Path) -> List[BareExceptFix]:
        """Analyze a single file for bare except blocks"""
        fixes = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # Find bare except blocks
            for i, line in enumerate(lines):
                if re.match(r'^\s*except\s*:\s*$', line):
                    # Detect context
                    context_type, exceptions = self.detect_context(content, i)

                    # Determine confidence
                    confidence = "HIGH" if context_type != 'generic' else "MEDIUM"

                    # Generate new line with same indentation
                    indent = re.match(r'^(\s*)', line).group(1)
                    new_line = f"{indent}except {exceptions} as e:"

                    # Add logger line after except (if not already present)
                    next_line = lines[i + 1] if i + 1 < len(lines) else ""

                    # Check if next line is already a logger call
                    has_logger = 'logger.' in next_line

                    fixes.append(BareExceptFix(
                        file_path=str(file_path.relative_to(BASE_DIR)),
                        line_number=i + 1,
                        original_line=line,
                        new_line=new_line,
                        detected_context=context_type,
                        confidence=confidence
                    ))

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

        return fixes

    def apply_fix(self, file_path: Path, fixes: List[BareExceptFix]) -> bool:
        """Apply fixes to a file"""
        if not fixes:
            return True

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Sort fixes by line number (descending) to avoid offset issues
            sorted_fixes = sorted(fixes, key=lambda x: x.line_number, reverse=True)

            # Apply each fix
            lines = content.split('\n')
            for fix in sorted_fixes:
                line_idx = fix.line_number - 1
                if line_idx < len(lines):
                    lines[line_idx] = fix.new_line

            # Write back
            new_content = '\n'.join(lines)

            if self.dry_run:
                print(f"[DRY RUN] Would update {file_path}")
                return True
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"✓ Updated {file_path}")
                return True

        except Exception as e:
            logger.error(f"Error applying fix to {file_path}: {e}")
            return False

    def migrate_directory(self, directory: Path) -> List[BareExceptFix]:
        """Migrate all Python files in directory"""
        all_fixes = []

        for file_path in directory.rglob('*.py'):
            # Skip test files (they can have bare except for testing)
            if '/tests/' in str(file_path) or str(file_path).endswith('_test.py'):
                continue

            # Skip migrations
            if '/migrations/' in str(file_path):
                continue

            fixes = self.analyze_file(file_path)
            if fixes:
                all_fixes.extend(fixes)

                # Apply fixes if not dry run
                if not self.dry_run:
                    self.apply_fix(file_path, fixes)

        return all_fixes


def generate_report(fixes: List[BareExceptFix], output_path: Optional[Path] = None) -> str:
    """Generate migration report"""
    lines = []

    lines.append("# Bare Except Migration Report\n")
    lines.append(f"**Total Fixes**: {len(fixes)}\n")

    # Group by file
    by_file = {}
    for fix in fixes:
        if fix.file_path not in by_file:
            by_file[fix.file_path] = []
        by_file[fix.file_path].append(fix)

    lines.append(f"**Files Modified**: {len(by_file)}\n")
    lines.append("## Fixes by File\n")

    for file_path, file_fixes in sorted(by_file.items()):
        lines.append(f"\n### `{file_path}` ({len(file_fixes)} fixes)\n")

        for fix in sorted(file_fixes, key=lambda x: x.line_number):
            lines.append(f"**Line {fix.line_number}**: {fix.confidence} confidence ({fix.detected_context})")
            lines.append(f"```python")
            lines.append(f"# Before:")
            lines.append(f"{fix.original_line}")
            lines.append(f"")
            lines.append(f"# After:")
            lines.append(f"{fix.new_line}")
            lines.append(f"```\n")

    report_content = '\n'.join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\n✓ Report saved to: {output_path}")

    return report_content


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate bare except blocks to specific exception types")
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--fix', action='store_true', help='Apply fixes to files')
    parser.add_argument('--report', type=str, help='Generate migration report')
    parser.add_argument('--paths', nargs='*', help='Specific paths to migrate (default: apps/ background_tasks/)')

    args = parser.parse_args()

    # Determine mode
    dry_run = not args.fix

    # Paths to scan
    if args.paths:
        scan_paths = [BASE_DIR / p for p in args.paths]
    else:
        scan_paths = [BASE_DIR / 'apps', BASE_DIR / 'background_tasks']

    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating bare except blocks...")
    print(f"Scanning: {[str(p) for p in scan_paths]}\n")

    # Run migration
    migrator = BareExceptMigrator(dry_run=dry_run)

    all_fixes = []
    for path in scan_paths:
        fixes = migrator.migrate_directory(path)
        all_fixes.extend(fixes)

    print(f"\n{'='*60}")
    print(f"Migration Complete: {len(all_fixes)} fixes identified")
    print(f"{'='*60}\n")

    # Generate report
    if args.report or dry_run:
        output_path = Path(args.report) if args.report else None
        report = generate_report(all_fixes, output_path)

        if not args.report and dry_run:
            print(report)

    return 0 if all_fixes else 1


if __name__ == "__main__":
    sys.exit(main())
