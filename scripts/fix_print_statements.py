#!/usr/bin/env python3
"""
Production Print Statement Remediation Script

Finds and replaces all print() statements in the codebase with proper logging.
Categorizes by purpose and applies appropriate logging levels.

Usage:
    python scripts/fix_print_statements.py --dry-run  # Preview changes
    python scripts/fix_print_statements.py --fix      # Apply changes
    python scripts/fix_print_statements.py --stats    # Show statistics only
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent
APPS_DIR = BASE_DIR / 'apps'

# Exclude patterns
EXCLUDE_DIRS = {
    '__pycache__', '.git', 'migrations', 'fixtures', 
    'examples', 'tests', 'static', 'media'
}

EXCLUDE_FILES = {
    '.md', '.json', '.txt', '.yaml', '.yml', '.rst', 
    '.sh', '.sql', '.ini', '.cfg'
}

# Patterns for categorization
DEBUG_PATTERNS = [
    r'print\(.*(debug|DEBUG|qset|query|DEBUG\])',
    r'print\(f?"[^\"]*(After|Before|Checkpoint).*"',
    r'print\(.*(\.count\(\)|queries)',
]

INFO_PATTERNS = [
    r'print\(f?"(Created|Updated|Deleted|Success|✅)',
    r'print\(f?".*completed.*"',
    r'print\(f?".*improvement.*"',
    r'print\(f?".*registered.*"',
]

ERROR_PATTERNS = [
    r'print\(f?"(Error|Failed|⚠️|❌)',
    r'print\(.*(error|exception|fail)',
]

# Temporary/example patterns to remove
REMOVE_PATTERNS = [
    r'print\(.*(example|Example|EXAMPLE)',
    r'print\(f?"={60,}"\)',  # Separator lines in examples
]


class PrintStatementFixer:
    def __init__(self):
        self.stats = defaultdict(lambda: {
            'debug': 0, 'info': 0, 'error': 0, 
            'remove': 0, 'total': 0
        })
        self.changes = []
        
    def categorize_print(self, line: str) -> str:
        """Categorize print statement by its content."""
        line_lower = line.lower()
        
        # Check for removal patterns first
        for pattern in REMOVE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return 'remove'
        
        # Check error patterns
        for pattern in ERROR_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return 'error'
        
        # Check info patterns
        for pattern in INFO_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return 'info'
        
        # Check debug patterns
        for pattern in DEBUG_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return 'debug'
        
        # Default to info for migrations
        if 'migration' in line_lower or 'populate' in line_lower:
            return 'info'
            
        # Default to debug for everything else
        return 'debug'
    
    def extract_print_content(self, line: str) -> str:
        """Extract content from print statement."""
        match = re.search(r'print\((.*)\)', line)
        if match:
            return match.group(1).strip()
        return line
    
    def convert_to_logger(self, line: str, category: str, indent: str) -> str:
        """Convert print statement to logger call."""
        if category == 'remove':
            return ''
        
        content = self.extract_print_content(line)
        
        # Handle f-strings
        if content.startswith('f"') or content.startswith("f'"):
            # Already an f-string
            log_content = content
        else:
            # Regular string or variable
            log_content = content
        
        return f'{indent}logger.{category}({log_content})'
    
    def add_logger_import(self, content: str, filepath: str) -> str:
        """Add logger import if not present."""
        if 'import logging' not in content or 'logger = logging.getLogger' not in content:
            # Find first import statement
            lines = content.split('\n')
            import_idx = 0
            
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    import_idx = i + 1
                elif import_idx > 0 and not line.strip().startswith(('import ', 'from ')):
                    break
            
            # Add logger setup after imports
            logger_setup = [
                '',
                'import logging',
                f'logger = logging.getLogger(__name__)',
                ''
            ]
            
            lines.insert(import_idx, '\n'.join(logger_setup))
            return '\n'.join(lines)
        
        return content
    
    def process_file(self, filepath: Path) -> Tuple[str, Dict[str, int]]:
        """Process a single file and return modified content."""
        try:
            content = filepath.read_text(encoding='utf-8')
            original_content = content
            lines = content.split('\n')
            modified = False
            file_stats = defaultdict(int)
            
            new_lines = []
            for line in lines:
                # Match print statements
                match = re.match(r'^(\s*)print\(', line)
                if match:
                    indent = match.group(1)
                    category = self.categorize_print(line)
                    file_stats[category] += 1
                    file_stats['total'] += 1
                    
                    new_line = self.convert_to_logger(line, category, indent)
                    if new_line:
                        new_lines.append(new_line)
                        self.changes.append({
                            'file': str(filepath.relative_to(BASE_DIR)),
                            'old': line.strip(),
                            'new': new_line.strip(),
                            'category': category
                        })
                    modified = True
                else:
                    new_lines.append(line)
            
            if modified:
                content = '\n'.join(new_lines)
                content = self.add_logger_import(content, str(filepath))
                return content, file_stats
            
            return original_content, file_stats
            
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            return None, {}
    
    def scan_directory(self, directory: Path) -> None:
        """Scan directory for Python files with print statements."""
        for filepath in directory.rglob('*.py'):
            # Skip excluded directories
            if any(exclude in filepath.parts for exclude in EXCLUDE_DIRS):
                continue
            
            # Skip excluded file types
            if filepath.suffix in EXCLUDE_FILES:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8')
                if 'print(' in content:
                    app_name = filepath.parts[filepath.parts.index('apps') + 1] if 'apps' in filepath.parts else 'other'
                    
                    # Count prints
                    for line in content.split('\n'):
                        if re.match(r'^\s*print\(', line):
                            category = self.categorize_print(line)
                            self.stats[app_name][category] += 1
                            self.stats[app_name]['total'] += 1
                            
            except Exception as e:
                continue
    
    def fix_files(self, dry_run: bool = True) -> None:
        """Fix all files with print statements."""
        for filepath in APPS_DIR.rglob('*.py'):
            # Skip excluded
            if any(exclude in filepath.parts for exclude in EXCLUDE_DIRS):
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8')
                if 'print(' in content and re.search(r'^\s*print\(', content, re.MULTILINE):
                    new_content, file_stats = self.process_file(filepath)
                    
                    if new_content and new_content != content:
                        app_name = filepath.parts[filepath.parts.index('apps') + 1]
                        
                        for category, count in file_stats.items():
                            self.stats[app_name][category] += count
                        
                        if not dry_run:
                            filepath.write_text(new_content, encoding='utf-8')
                            print(f"✅ Fixed {filepath.relative_to(BASE_DIR)}")
                        else:
                            print(f"🔍 Would fix {filepath.relative_to(BASE_DIR)}")
                            
            except Exception as e:
                print(f"❌ Error fixing {filepath}: {e}")
    
    def print_stats(self) -> None:
        """Print statistics."""
        print("\n" + "=" * 80)
        print("PRINT STATEMENT REMEDIATION STATISTICS")
        print("=" * 80)
        
        total_all = sum(app['total'] for app in self.stats.values())
        
        # Sort by total count
        sorted_apps = sorted(self.stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        print(f"\nTotal print statements found: {total_all}")
        print(f"\nBreakdown by app:\n")
        
        for app_name, counts in sorted_apps:
            if counts['total'] > 0:
                print(f"\n📁 {app_name}: {counts['total']} total")
                if counts['debug'] > 0:
                    print(f"   🔍 Debug:  {counts['debug']}")
                if counts['info'] > 0:
                    print(f"   ℹ️  Info:   {counts['info']}")
                if counts['error'] > 0:
                    print(f"   ❌ Error:  {counts['error']}")
                if counts['remove'] > 0:
                    print(f"   🗑️  Remove: {counts['remove']}")
        
        # Category totals
        total_debug = sum(app['debug'] for app in self.stats.values())
        total_info = sum(app['info'] for app in self.stats.values())
        total_error = sum(app['error'] for app in self.stats.values())
        total_remove = sum(app['remove'] for app in self.stats.values())
        
        print("\n" + "=" * 80)
        print("CATEGORY TOTALS:")
        print("=" * 80)
        print(f"🔍 Debug:  {total_debug} ({total_debug/total_all*100:.1f}%)")
        print(f"ℹ️  Info:   {total_info} ({total_info/total_all*100:.1f}%)")
        print(f"❌ Error:  {total_error} ({total_error/total_all*100:.1f}%)")
        print(f"🗑️  Remove: {total_remove} ({total_remove/total_all*100:.1f}%)")
        print("=" * 80)
        
        # Sample changes
        if self.changes:
            print("\n" + "=" * 80)
            print("SAMPLE CONVERSIONS:")
            print("=" * 80)
            
            for i, change in enumerate(self.changes[:10], 1):
                print(f"\n{i}. {change['file']} [{change['category']}]")
                print(f"   BEFORE: {change['old']}")
                print(f"   AFTER:  {change['new']}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix production print statements')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--fix', action='store_true', help='Apply fixes to files')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    
    args = parser.parse_args()
    
    fixer = PrintStatementFixer()
    
    if args.stats:
        print("🔍 Scanning for print statements...")
        fixer.scan_directory(APPS_DIR)
        fixer.print_stats()
    elif args.fix:
        print("🔧 Fixing print statements...")
        fixer.fix_files(dry_run=False)
        fixer.print_stats()
        print("\n✅ All fixes applied!")
    else:
        # Default: dry run
        print("🔍 Dry run - preview changes...")
        fixer.fix_files(dry_run=True)
        fixer.print_stats()
        print("\n💡 Run with --fix to apply changes")


if __name__ == '__main__':
    main()
