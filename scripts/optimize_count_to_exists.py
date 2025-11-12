#!/usr/bin/env python
"""
Script to replace inefficient .count() > 0 patterns with .exists()

This optimization improves query performance by stopping at the first match
instead of counting all rows.

Usage:
    python scripts/optimize_count_to_exists.py --dry-run  # Preview changes
    python scripts/optimize_count_to_exists.py            # Apply changes
    python scripts/optimize_count_to_exists.py --path apps/reports  # Specific app

Created: 2025-11-07
"""

import os
import re
import argparse
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class CountToExistsOptimizer:
    """Optimizer to replace count() > 0 patterns with exists()."""
    
    # Patterns to replace
    PATTERNS = [
        # Pattern 1: .count() > 0
        (
            r'(\w+)\.count\(\)\s*>\s*0',
            r'\1.exists()'
        ),
        # Pattern 2: .count() == 0 (becomes not exists())
        (
            r'(\w+)\.count\(\)\s*==\s*0',
            r'not \1.exists()'
        ),
        # Pattern 3: if queryset.count():
        (
            r'if\s+(\w+)\.count\(\):',
            r'if \1.exists():'
        ),
        # Pattern 4: while queryset.count() > 0:
        (
            r'while\s+(\w+)\.count\(\)\s*>\s*0:',
            r'while \1.exists():'
        ),
    ]
    
    # Files/patterns to skip (legitimate count() usage)
    SKIP_PATTERNS = [
        r'\.count\(\)\s*[+\-*/]',  # Mathematical operations
        r'\.count\(\)\s*>=\s*[2-9]',  # Threshold checks > 1
        r'total.*=.*\.count\(\)',  # Total count assignments
        r'#.*OK.*\.count\(\)',  # Explicitly marked as OK
        r'assert.*\.count\(\)',  # Test assertions
        r'\.count\(\).*!=',  # Not equal comparisons
    ]
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize optimizer.
        
        Args:
            dry_run: If True, only preview changes without applying
        """
        self.dry_run = dry_run
        self.files_changed = 0
        self.total_replacements = 0
    
    def should_skip_line(self, line: str) -> bool:
        """
        Check if line should be skipped (legitimate count() usage).
        
        Args:
            line: Line of code
            
        Returns:
            True if line should be skipped
        """
        for pattern in self.SKIP_PATTERNS:
            if re.search(pattern, line):
                return True
        return False
    
    def optimize_file(self, filepath: Path) -> List[Tuple[int, str, str]]:
        """
        Optimize a single file.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            List of (line_number, old_line, new_line) tuples
        """
        changes = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return changes
        
        new_lines = []
        for i, line in enumerate(lines, start=1):
            new_line = line
            
            # Skip if this is legitimate count() usage
            if self.should_skip_line(line):
                new_lines.append(line)
                continue
            
            # Apply patterns
            for pattern, replacement in self.PATTERNS:
                if re.search(pattern, new_line):
                    replaced_line = re.sub(pattern, replacement, new_line)
                    if replaced_line != new_line:
                        changes.append((i, line.rstrip(), replaced_line.rstrip()))
                        new_line = replaced_line
            
            new_lines.append(new_line)
        
        # Write changes if not dry run
        if changes and not self.dry_run:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                self.files_changed += 1
            except Exception as e:
                print(f"Error writing {filepath}: {e}")
        
        self.total_replacements += len(changes)
        return changes
    
    def optimize_directory(self, directory: Path) -> None:
        """
        Recursively optimize all Python files in directory.
        
        Args:
            directory: Directory to optimize
        """
        python_files = directory.rglob('*.py')
        
        for filepath in python_files:
            # Skip migrations and test files for now
            if 'migrations' in str(filepath) or '__pycache__' in str(filepath):
                continue
            
            changes = self.optimize_file(filepath)
            
            if changes:
                print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Changes in {filepath}:")
                for line_num, old, new in changes:
                    print(f"  Line {line_num}:")
                    print(f"    - {old}")
                    print(f"    + {new}")
    
    def print_summary(self) -> None:
        """Print optimization summary."""
        print("\n" + "="*60)
        if self.dry_run:
            print("DRY RUN SUMMARY")
        else:
            print("OPTIMIZATION SUMMARY")
        print("="*60)
        print(f"Files changed: {self.files_changed}")
        print(f"Total replacements: {self.total_replacements}")
        print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Optimize .count() > 0 to .exists()'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    parser.add_argument(
        '--path',
        type=str,
        default='apps',
        help='Path to optimize (default: apps/)'
    )
    
    args = parser.parse_args()
    
    # Get target directory
    target_path = PROJECT_ROOT / args.path
    if not target_path.exists():
        print(f"Error: Path {target_path} does not exist")
        sys.exit(1)
    
    # Run optimizer
    optimizer = CountToExistsOptimizer(dry_run=args.dry_run)
    
    print(f"Optimizing Python files in: {target_path}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print("="*60)
    
    optimizer.optimize_directory(target_path)
    optimizer.print_summary()
    
    if args.dry_run:
        print("\nTo apply these changes, run without --dry-run flag")


if __name__ == '__main__':
    main()
