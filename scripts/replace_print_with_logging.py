#!/usr/bin/env python
"""
Replace print statements with proper logging calls.
Automatically detects appropriate log level based on content.
"""

import os
import re
import argparse
from pathlib import Path
from typing import Tuple


def replace_prints_in_file(filepath: Path, dry_run: bool = True) -> Tuple[int, str]:
    """Replace print statements with logging calls."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Skip if no print statements
    if 'print(' not in content:
        return 0, content
    
    # Check existing logging setup
    has_logging_import = 'import logging' in content
    has_logger = re.search(r'logger\s*=\s*logging\.getLogger', content)
    
    # Find all print statements (multiline support)
    print_pattern = r'print\s*\(((?:[^()]|\([^)]*\))*)\)'
    prints_found = list(re.finditer(print_pattern, content, re.DOTALL))
    
    if not prints_found:
        return 0, content
    
    new_content = content
    
    # Add logging imports if needed
    if not has_logging_import or not has_logger:
        # Find first import statement
        import_match = re.search(r'^(from|import)\s+', new_content, re.MULTILINE)
        if import_match:
            # Find end of import block
            lines = new_content.split('\n')
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.strip() and not (line.startswith('from ') or line.startswith('import ') or 
                                        line.startswith('#') or line.startswith('"""') or 
                                        line.startswith("'''")):
                    insert_pos = i
                    break
            
            if not has_logging_import:
                lines.insert(insert_pos, 'import logging')
                insert_pos += 1
            if not has_logger:
                lines.insert(insert_pos, 'logger = logging.getLogger(__name__)')
                insert_pos += 1
            
            new_content = '\n'.join(lines)
    
    # Replace print statements with appropriate log level
    def replace_print(match):
        arg = match.group(1).strip()
        
        # Determine log level from content
        arg_lower = arg.lower()
        if any(word in arg_lower for word in ['error', 'exception', 'failed', 'failure']):
            return f'logger.error({arg})'
        elif any(word in arg_lower for word in ['warning', 'warn', 'deprecated']):
            return f'logger.warning({arg})'
        elif any(word in arg_lower for word in ['debug', 'trace']):
            return f'logger.debug({arg})'
        else:
            return f'logger.info({arg})'
    
    new_content = re.sub(print_pattern, replace_print, new_content, flags=re.DOTALL)
    
    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
    
    return len(prints_found), new_content


def main():
    parser = argparse.ArgumentParser(description='Replace print statements with logging')
    parser.add_argument('--app', required=True, help='App name (e.g., ml_training)')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default: dry-run)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    args = parser.parse_args()
    
    app_path = Path(f'apps/{args.app}')
    
    if not app_path.exists():
        print(f"Error: App path {app_path} does not exist")
        return 1
    
    total_replaced = 0
    files_modified = []
    
    for py_file in app_path.rglob('*.py'):
        # Skip pycache and migrations
        if '__pycache__' in str(py_file) or '/migrations/' in str(py_file):
            continue
        
        count, new_content = replace_prints_in_file(py_file, dry_run=not args.apply)
        
        if count > 0:
            status = 'REPLACED' if args.apply else 'FOUND'
            print(f"[{status}] {py_file.relative_to('apps')}: {count} print statement(s)")
            total_replaced += count
            files_modified.append(py_file)
            
            if args.verbose and not args.apply:
                print(f"  Preview of changes:")
                # Show first few lines of changes
                for line in new_content.split('\n')[:5]:
                    if 'logger.' in line:
                        print(f"    {line}")
    
    print(f"\n{'='*60}")
    print(f"Total: {total_replaced} print statement(s) {'replaced' if args.apply else 'found'}")
    print(f"Files affected: {len(files_modified)}")
    
    if not args.apply:
        print(f"\nRun with --apply to make changes")
    
    return 0


if __name__ == '__main__':
    exit(main())
