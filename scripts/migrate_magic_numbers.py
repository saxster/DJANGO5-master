#!/usr/bin/env python3
"""
Automated Magic Number Migration Script

Extracts magic numbers and replaces them with appropriate constants.
Focuses on high-impact categories: TIME, STATUS_CODE, SPATIAL, BUSINESS_RULE.

Usage:
    python scripts/migrate_magic_numbers.py --app attendance --category TIME --dry-run
    python scripts/migrate_magic_numbers.py --app attendance --category TIME --apply
    python scripts/migrate_magic_numbers.py --all --dry-run
"""

import argparse
import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict


# Mapping of magic numbers to constants
MAGIC_NUMBER_CONSTANTS = {
    # Time constants (seconds)
    '60': ('SECONDS_IN_MINUTE', 'apps.core.constants.datetime_constants'),
    '3600': ('SECONDS_IN_HOUR', 'apps.core.constants.datetime_constants'),
    '86400': ('SECONDS_IN_DAY', 'apps.core.constants.datetime_constants'),
    '604800': ('SECONDS_IN_WEEK', 'apps.core.constants.datetime_constants'),
    
    # Time units
    '24': ('HOURS_IN_DAY', 'apps.core.constants.datetime_constants'),
    '7': ('DAYS_IN_WEEK', 'apps.core.constants.datetime_constants'),
    '30': ('DAYS_IN_MONTH_APPROX', 'apps.core.constants.datetime_constants'),
    '365': ('DAYS_IN_YEAR', 'apps.core.constants.datetime_constants'),
    
    # HTTP status codes
    '200': ('HTTP_200_OK', 'apps.core.constants.status_constants'),
    '201': ('HTTP_201_CREATED', 'apps.core.constants.status_constants'),
    '204': ('HTTP_204_NO_CONTENT', 'apps.core.constants.status_constants'),
    '400': ('HTTP_400_BAD_REQUEST', 'apps.core.constants.status_constants'),
    '401': ('HTTP_401_UNAUTHORIZED', 'apps.core.constants.status_constants'),
    '403': ('HTTP_403_FORBIDDEN', 'apps.core.constants.status_constants'),
    '404': ('HTTP_404_NOT_FOUND', 'apps.core.constants.status_constants'),
    '500': ('HTTP_500_INTERNAL_SERVER_ERROR', 'apps.core.constants.status_constants'),
    
    # Image processing
    '512': ('IMAGE_MAX_DIMENSION', 'apps.core.constants.status_constants'),
    '255': ('JPEG_QUALITY_MAXIMUM', 'apps.core.constants.status_constants'),
    '85': ('IMAGE_QUALITY_DEFAULT', 'apps.core.constants.status_constants'),
    
    # Pagination
    '20': ('DEFAULT_PAGE_SIZE', 'apps.core.constants.status_constants'),
    '100': ('MAX_PAGE_SIZE', 'apps.core.constants.status_constants'),
    '50': ('DEFAULT_BATCH_SIZE', 'apps.core.constants.status_constants'),
}


class MagicNumberReplacer(ast.NodeTransformer):
    """AST transformer to replace magic numbers with constants."""
    
    def __init__(self, replacements: Dict[str, Tuple[str, str]]):
        self.replacements = replacements
        self.changes: List[Tuple[int, str, str]] = []  # (line, old, new)
        
    def visit_Num(self, node):
        if hasattr(node, 'n'):
            value_str = str(node.n)
            if value_str in self.replacements:
                const_name, _ = self.replacements[value_str]
                self.changes.append((node.lineno, value_str, const_name))
        return self.generic_visit(node)
    
    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            value_str = str(node.value)
            if value_str in self.replacements:
                const_name, _ = self.replacements[value_str]
                self.changes.append((node.lineno, value_str, const_name))
        return self.generic_visit(node)


def detect_required_imports(file_content: str, replacements: Dict[str, Tuple[str, str]]) -> Set[str]:
    """Detect which constant imports are needed for this file."""
    required_modules = set()
    
    try:
        tree = ast.parse(file_content)
        replacer = MagicNumberReplacer(replacements)
        replacer.visit(tree)
        
        for _, _, const_name in replacer.changes:
            # Find the module for this constant
            for value, (name, module) in replacements.items():
                if name == const_name:
                    required_modules.add(module)
                    break
    except:
        pass
    
    return required_modules


def add_imports_to_file(file_content: str, required_modules: Set[str]) -> str:
    """Add necessary imports to the file."""
    if not required_modules:
        return file_content
    
    lines = file_content.split('\n')
    
    # Find the last import line
    last_import_line = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import_line = i
    
    # Build import statements
    import_lines = []
    for module in sorted(required_modules):
        # Get constants from this module used in the file
        constants = []
        for value, (name, mod) in MAGIC_NUMBER_CONSTANTS.items():
            if mod == module and any(name in line for line in lines):
                constants.append(name)
        
        if constants:
            const_list = ', '.join(sorted(set(constants)))
            import_lines.append(f"from {module} import {const_list}")
    
    # Insert imports
    if import_lines:
        lines.insert(last_import_line + 1, '\n'.join(import_lines))
    
    return '\n'.join(lines)


def replace_magic_numbers_in_file(filepath: Path, replacements: Dict[str, Tuple[str, str]], dry_run=True) -> Dict:
    """Replace magic numbers in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse and find replacements
        tree = ast.parse(content, filename=str(filepath))
        replacer = MagicNumberReplacer(replacements)
        replacer.visit(tree)
        
        if not replacer.changes:
            return {'file': str(filepath), 'changes': 0, 'details': []}
        
        # Apply replacements (simple regex approach)
        modified_content = content
        changes_applied = []
        
        for line_no, old_value, const_name in replacer.changes:
            # Context-aware replacement (avoid replacing in comments, strings)
            pattern = r'\b' + re.escape(old_value) + r'\b'
            
            # Get the line content
            lines = modified_content.split('\n')
            if line_no - 1 < len(lines):
                line = lines[line_no - 1]
                
                # Skip if in comment or string
                if '#' in line and line.index('#') < line.find(old_value):
                    continue
                if '"' in line or "'" in line:
                    # Simple check - improve for production
                    continue
                
                # Replace
                new_line = re.sub(pattern, const_name, line, count=1)
                lines[line_no - 1] = new_line
                modified_content = '\n'.join(lines)
                
                changes_applied.append({
                    'line': line_no,
                    'old': old_value,
                    'new': const_name,
                    'context': line.strip()
                })
        
        # Add imports
        required_modules = detect_required_imports(content, replacements)
        if required_modules and changes_applied:
            modified_content = add_imports_to_file(modified_content, required_modules)
        
        # Write changes
        if not dry_run and changes_applied:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(modified_content)
        
        return {
            'file': str(filepath),
            'changes': len(changes_applied),
            'details': changes_applied
        }
    
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def migrate_magic_numbers(app_path: Path, category: str = 'ALL', dry_run=True) -> Dict:
    """Migrate magic numbers in an app or directory."""
    results = {
        'total_files': 0,
        'modified_files': 0,
        'total_changes': 0,
        'files': []
    }
    
    # Filter replacements by category
    if category == 'TIME':
        replacements = {k: v for k, v in MAGIC_NUMBER_CONSTANTS.items() 
                       if 'datetime_constants' in v[1] and k in ['60', '3600', '86400', '604800']}
    elif category == 'STATUS_CODE':
        replacements = {k: v for k, v in MAGIC_NUMBER_CONSTANTS.items() 
                       if k in ['200', '201', '204', '400', '401', '403', '404', '500']}
    elif category == 'IMAGE':
        replacements = {k: v for k, v in MAGIC_NUMBER_CONSTANTS.items() 
                       if k in ['512', '255', '85']}
    else:
        replacements = MAGIC_NUMBER_CONSTANTS
    
    # Process files
    for root, dirs, files in os.walk(app_path):
        # Skip migrations, tests, __pycache__
        dirs[:] = [d for d in dirs if d not in {'migrations', '__pycache__', 'node_modules', '.git'}]
        
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                filepath = Path(root) / file
                results['total_files'] += 1
                
                file_result = replace_magic_numbers_in_file(filepath, replacements, dry_run)
                
                if file_result.get('changes', 0) > 0:
                    results['modified_files'] += 1
                    results['total_changes'] += file_result['changes']
                    results['files'].append(file_result)
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Migrate magic numbers to constants')
    parser.add_argument('--app', type=str, help='App directory (e.g., apps/attendance)')
    parser.add_argument('--all', action='store_true', help='Process all apps')
    parser.add_argument('--category', type=str, default='ALL', 
                       choices=['ALL', 'TIME', 'STATUS_CODE', 'IMAGE'],
                       help='Category of magic numbers to replace')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    parser.add_argument('--apply', action='store_true', help='Apply changes to files')
    
    args = parser.parse_args()
    
    if args.all:
        app_path = Path('apps')
    elif args.app:
        app_path = Path(args.app)
    else:
        print("Error: Specify --app or --all")
        return 1
    
    if not app_path.exists():
        print(f"Error: Path not found: {app_path}")
        return 1
    
    dry_run = not args.apply
    
    print(f"{'DRY RUN: ' if dry_run else ''}Migrating magic numbers...")
    print(f"Path: {app_path}")
    print(f"Category: {args.category}")
    print("=" * 80)
    
    results = migrate_magic_numbers(app_path, args.category, dry_run)
    
    print(f"\nResults:")
    print(f"  Total files scanned: {results['total_files']}")
    print(f"  Files modified: {results['modified_files']}")
    print(f"  Total changes: {results['total_changes']}")
    
    if results['files']:
        print(f"\nModified files:")
        for file_result in results['files'][:10]:  # Show first 10
            print(f"\n  {file_result['file']} ({file_result['changes']} changes)")
            for detail in file_result.get('details', [])[:3]:  # Show first 3 changes per file
                print(f"    Line {detail['line']}: {detail['old']} -> {detail['new']}")
                print(f"      {detail['context']}")
        
        if len(results['files']) > 10:
            print(f"\n  ... and {len(results['files']) - 10} more files")
    
    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - No changes applied. Use --apply to apply changes.")
    else:
        print("\n" + "=" * 80)
        print("Changes applied successfully!")
    
    return 0


if __name__ == '__main__':
    exit(main())
