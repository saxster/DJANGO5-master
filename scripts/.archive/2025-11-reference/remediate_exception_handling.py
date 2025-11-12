#!/usr/bin/env python
"""
Exception Handling Remediation Script - Part 3

Systematically remediates all remaining except Exception patterns
across the codebase with specific exception types.

Usage:
    python scripts/remediate_exception_handling.py --app core --dry-run
    python scripts/remediate_exception_handling.py --app noc
    python scripts/remediate_exception_handling.py --all
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Exception pattern mappings based on context
EXCEPTION_PATTERNS = {
    # Database operations
    'database': {
        'keywords': ['save(', 'update(', 'delete(', 'create(', 'get(', 'filter(', 
                     'objects.', 'transaction', 'commit(', 'rollback('],
        'import': 'from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS',
        'exception': 'DATABASE_EXCEPTIONS',
        'description': 'Database operations'
    },
    
    # Network/API calls
    'network': {
        'keywords': ['requests.', 'urllib', 'httplib', '.get(', '.post(', 
                     'api', 'webhook', 'http', 'fetch'],
        'import': 'from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS',
        'exception': 'NETWORK_EXCEPTIONS',
        'description': 'Network/API calls'
    },
    
    # File operations
    'file': {
        'keywords': ['open(', 'read(', 'write(', 'os.path', 'pathlib', 
                     'file', 'upload', 'download', 'storage'],
        'import': 'from apps.core.exceptions.patterns import FILE_EXCEPTIONS',
        'exception': 'FILE_EXCEPTIONS',
        'description': 'File operations'
    },
    
    # Encryption/Security
    'encryption': {
        'keywords': ['encrypt', 'decrypt', 'cipher', 'crypto', 'fernet', 
                     'hash', 'password', 'biometric'],
        'import': 'from apps.core.exceptions.patterns import ENCRYPTION_EXCEPTIONS',
        'exception': 'ENCRYPTION_EXCEPTIONS',
        'description': 'Encryption/Security'
    },
    
    # JSON/Serialization
    'serialization': {
        'keywords': ['json.', 'pickle', 'serialize', 'deserialize', 
                     'loads(', 'dumps(', 'JSONDecodeError'],
        'import': 'from apps.core.exceptions.patterns import SERIALIZATION_EXCEPTIONS',
        'exception': 'SERIALIZATION_EXCEPTIONS',
        'description': 'JSON/Serialization'
    },
    
    # Template rendering
    'template': {
        'keywords': ['render(', 'template', 'Template', 'TemplateDoesNotExist'],
        'import': 'from apps.core.exceptions.patterns import TEMPLATE_EXCEPTIONS',
        'exception': 'TEMPLATE_EXCEPTIONS',
        'description': 'Template rendering'
    },
    
    # Cache operations
    'cache': {
        'keywords': ['cache.', 'redis', 'memcached', 'get_cache', 'set_cache'],
        'import': 'from apps.core.exceptions.patterns import CACHE_EXCEPTIONS',
        'exception': 'CACHE_EXCEPTIONS',
        'description': 'Cache operations'
    },
    
    # Data processing/ML
    'data_processing': {
        'keywords': ['numpy', 'pandas', 'sklearn', 'model.predict', 
                     'dataframe', 'array', 'tensor'],
        'import': 'from apps.core.exceptions.patterns import DATA_PROCESSING_EXCEPTIONS',
        'exception': 'DATA_PROCESSING_EXCEPTIONS',
        'description': 'Data processing/ML'
    },
    
    # Celery/Task operations
    'celery': {
        'keywords': ['apply_async', 'delay(', 'retry(', 'task', 'celery'],
        'import': 'from apps.core.exceptions.patterns import CELERY_EXCEPTIONS',
        'exception': 'CELERY_EXCEPTIONS',
        'description': 'Celery task operations'
    }
}


class ExceptionRemediator:
    """Remediates exception handling patterns in Python files."""
    
    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.stats = defaultdict(int)
        self.changes = []
        
    def detect_exception_context(self, code_block: str) -> Optional[str]:
        """
        Detect the most appropriate exception type based on code context.
        
        Args:
            code_block: Code surrounding the exception handler
            
        Returns:
            Exception pattern key or None
        """
        # Check each pattern
        scores = {}
        for pattern_name, pattern_info in EXCEPTION_PATTERNS.items():
            score = 0
            for keyword in pattern_info['keywords']:
                score += code_block.lower().count(keyword.lower())
            if score > 0:
                scores[pattern_name] = score
        
        # Return pattern with highest score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        # Default to ValueError/TypeError for unknown contexts
        return None
    
    def extract_try_block(self, lines: List[str], except_line_num: int) -> str:
        """Extract the try block code before the except statement."""
        code_block = []
        indent = len(lines[except_line_num]) - len(lines[except_line_num].lstrip())
        
        # Go backwards to find try statement
        for i in range(except_line_num - 1, max(0, except_line_num - 50), -1):
            line = lines[i]
            line_indent = len(line) - len(line.lstrip())
            
            # Found the try statement
            if line_indent == indent and line.strip().startswith('try:'):
                # Collect all lines in try block
                for j in range(i + 1, except_line_num):
                    code_block.append(lines[j])
                break
        
        return '\n'.join(code_block)
    
    def get_import_section_end(self, lines: List[str]) -> int:
        """Find where imports section ends."""
        last_import = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                last_import = i
            elif stripped and not stripped.startswith('#') and last_import > 0:
                # First non-import, non-comment, non-empty line after imports
                return last_import + 1
        return last_import + 1 if last_import > 0 else 0
    
    def add_import_if_needed(self, lines: List[str], import_statement: str) -> List[str]:
        """Add import statement if not already present."""
        # Check if import already exists
        for line in lines:
            if import_statement in line:
                return lines
        
        # Find where to add import
        insert_pos = self.get_import_section_end(lines)
        
        # Add import
        lines.insert(insert_pos, import_statement + '\n')
        return lines
    
    def remediate_file(self, filepath: Path) -> Tuple[int, List[str]]:
        """
        Remediate all exception handlers in a file.
        
        Returns:
            (count of changes, list of change descriptions)
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return 0, []
        
        changes = []
        needed_imports = set()
        modified_lines = lines.copy()
        line_offset = 0  # Track line number changes due to imports
        
        # Find all except Exception patterns
        pattern = re.compile(r'^\s*except Exception( as \w+)?:\s*$')
        
        for i, line in enumerate(lines):
            if pattern.match(line) and '# OK:' not in line:
                # Extract context
                try_block = self.extract_try_block(lines, i)
                
                # Detect appropriate exception type
                pattern_key = self.detect_exception_context(try_block)
                
                if pattern_key:
                    pattern_info = EXCEPTION_PATTERNS[pattern_key]
                    
                    # Replace except Exception with specific exception
                    old_line = line
                    indent = len(line) - len(line.lstrip())
                    var_match = re.search(r'as (\w+)', line)
                    var_name = var_match.group(1) if var_match else 'e'
                    
                    new_line = ' ' * indent + f'except {pattern_info["exception"]} as {var_name}:'
                    
                    # Update modified lines (accounting for import offset)
                    modified_lines[i + line_offset] = new_line
                    
                    # Track needed import
                    needed_imports.add(pattern_info['import'])
                    
                    changes.append({
                        'line': i + 1,
                        'old': old_line.strip(),
                        'new': new_line.strip(),
                        'pattern': pattern_info['description']
                    })
                    
                    self.stats['patterns_remediated'] += 1
                else:
                    # Fallback to ValueError/TypeError
                    old_line = line
                    indent = len(line) - len(line.lstrip())
                    var_match = re.search(r'as (\w+)', line)
                    var_name = var_match.group(1) if var_match else 'e'
                    
                    new_line = ' ' * indent + f'except (ValueError, TypeError, AttributeError) as {var_name}:'
                    modified_lines[i + line_offset] = new_line
                    
                    changes.append({
                        'line': i + 1,
                        'old': old_line.strip(),
                        'new': new_line.strip(),
                        'pattern': 'Generic fallback'
                    })
                    
                    self.stats['fallback_patterns'] += 1
        
        # Add needed imports
        for import_stmt in sorted(needed_imports):
            modified_lines = self.add_import_if_needed(modified_lines, import_stmt)
            line_offset += 1
        
        # Write changes if not dry run
        if changes and not self.dry_run:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(modified_lines))
                self.stats['files_modified'] += 1
            except Exception as e:
                print(f"Error writing {filepath}: {e}")
                return 0, []
        
        return len(changes), changes
    
    def remediate_app(self, app_name: str) -> None:
        """Remediate all files in an app."""
        app_path = PROJECT_ROOT / 'apps' / app_name
        
        if not app_path.exists():
            print(f"App not found: {app_name}")
            return
        
        print(f"\n{'='*80}")
        print(f"Remediating app: {app_name}")
        print(f"{'='*80}\n")
        
        # Find all Python files
        python_files = list(app_path.rglob('*.py'))
        
        # Exclude tests and migrations
        python_files = [
            f for f in python_files 
            if 'tests' not in f.parts 
            and 'test_' not in f.name
            and '__pycache__' not in f.parts
        ]
        
        print(f"Found {len(python_files)} Python files\n")
        
        for filepath in sorted(python_files):
            count, file_changes = self.remediate_file(filepath)
            
            if count > 0:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                print(f"\n📄 {rel_path} ({count} changes)")
                
                if self.verbose:
                    for change in file_changes:
                        print(f"  Line {change['line']}: {change['pattern']}")
                        print(f"    - {change['old']}")
                        print(f"    + {change['new']}")
                
                self.changes.append({
                    'file': str(rel_path),
                    'count': count,
                    'changes': file_changes
                })
    
    def print_summary(self) -> None:
        """Print remediation summary."""
        print(f"\n{'='*80}")
        print("REMEDIATION SUMMARY")
        print(f"{'='*80}\n")
        
        print(f"Files modified: {self.stats['files_modified']}")
        print(f"Patterns remediated: {self.stats['patterns_remediated']}")
        print(f"Fallback patterns: {self.stats['fallback_patterns']}")
        print(f"Total changes: {self.stats['patterns_remediated'] + self.stats['fallback_patterns']}")
        
        if self.dry_run:
            print("\n⚠️  DRY RUN - No files were modified")
        else:
            print("\n✅ Changes written to files")


def main():
    parser = argparse.ArgumentParser(
        description='Remediate exception handling patterns'
    )
    parser.add_argument(
        '--app',
        help='App name to remediate (e.g., core, noc, activity)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Remediate all apps'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed changes'
    )
    
    args = parser.parse_args()
    
    remediator = ExceptionRemediator(
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    if args.all:
        # Get all apps
        apps_dir = PROJECT_ROOT / 'apps'
        app_names = [
            d.name for d in apps_dir.iterdir() 
            if d.is_dir() and not d.name.startswith('_')
        ]
        
        # Priority order
        priority_apps = [
            'core', 'noc', 'activity', 'reports', 'ml_training',
            'core_onboarding', 'onboarding_api', 'y_helpdesk',
            'scheduler', 'helpbot', 'journal', 'help_center'
        ]
        
        # Process in priority order, then remaining
        for app in priority_apps:
            if app in app_names:
                remediator.remediate_app(app)
        
        for app in app_names:
            if app not in priority_apps:
                remediator.remediate_app(app)
    
    elif args.app:
        remediator.remediate_app(args.app)
    
    else:
        parser.print_help()
        sys.exit(1)
    
    remediator.print_summary()


if __name__ == '__main__':
    main()
