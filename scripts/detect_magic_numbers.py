#!/usr/bin/env python3
"""
Detect magic numbers in Python files.
Magic numbers are numeric literals used without explanation in code.
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict


class MagicNumberDetector(ast.NodeVisitor):
    ALLOWED_NUMBERS = {0, 1, -1, 2, 100, 1000}  # Common acceptable numbers
    
    def __init__(self, filename: str):
        self.filename = filename
        self.magic_numbers: List[Tuple[int, int, str]] = []
        
    def visit_Num(self, node):
        if hasattr(node, 'n') and isinstance(node.n, (int, float)):
            if node.n not in self.ALLOWED_NUMBERS:
                self.magic_numbers.append((node.lineno, node.col_offset, str(node.n)))
        self.generic_visit(node)
    
    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            if node.value not in self.ALLOWED_NUMBERS:
                self.magic_numbers.append((node.lineno, node.col_offset, str(node.value)))
        self.generic_visit(node)


def detect_magic_numbers_in_file(filepath: Path) -> List[Tuple[int, int, str]]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(filepath))
        detector = MagicNumberDetector(str(filepath))
        detector.visit(tree)
        return detector.magic_numbers
    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return []


def categorize_magic_number(value: str, context: str = "") -> str:
    """Categorize magic number by type."""
    try:
        num = float(value)
        
        # Time-related
        if num in {60, 3600, 86400, 604800, 2592000, 31536000}:
            return "TIME"
        if num in {24, 7, 30, 365}:
            return "TIME_UNITS"
            
        # HTTP/Status codes
        if 200 <= num < 600:
            return "STATUS_CODE"
            
        # Percentages/rates
        if 0 < num <= 1 and '.' in value:
            return "RATE/PERCENTAGE"
            
        # Distances/coordinates
        if 'radius' in context.lower() or 'distance' in context.lower():
            return "SPATIAL"
            
        # Default
        return "BUSINESS_RULE"
    except:
        return "UNKNOWN"


def scan_directory(directory: Path) -> Dict[str, List]:
    results = defaultdict(list)
    
    for root, dirs, files in os.walk(directory):
        # Skip migrations, tests, __pycache__
        dirs[:] = [d for d in dirs if d not in {'migrations', '__pycache__', 'node_modules', '.git'}]
        
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                filepath = Path(root) / file
                magic_numbers = detect_magic_numbers_in_file(filepath)
                
                if magic_numbers:
                    for line, col, value in magic_numbers:
                        category = categorize_magic_number(value)
                        results[category].append({
                            'file': str(filepath.relative_to(directory.parent)),
                            'line': line,
                            'value': value
                        })
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python detect_magic_numbers.py <directory>")
        sys.exit(1)
    
    directory = Path(sys.argv[1])
    if not directory.exists():
        print(f"Directory not found: {directory}")
        sys.exit(1)
    
    print(f"Scanning {directory} for magic numbers...")
    print("=" * 80)
    
    results = scan_directory(directory)
    
    total_count = 0
    for category, items in sorted(results.items()):
        print(f"\n{category} ({len(items)} occurrences):")
        print("-" * 80)
        
        # Show first 10 examples
        for item in items[:10]:
            print(f"  {item['file']}:{item['line']} -> {item['value']}")
        
        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more")
        
        total_count += len(items)
    
    print("\n" + "=" * 80)
    print(f"Total magic numbers found: {total_count}")
    print("\nRecommendations:")
    print("1. TIME/TIME_UNITS -> apps/core/constants/datetime_constants.py")
    print("2. STATUS_CODE -> apps/core/constants/status_constants.py")
    print("3. SPATIAL -> apps/core/constants/spatial_constants.py")
    print("4. BUSINESS_RULE -> apps/{app}/constants.py")


if __name__ == '__main__':
    main()
