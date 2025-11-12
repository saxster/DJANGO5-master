#!/usr/bin/env python3
"""
God File Refactoring Script

Identifies and provides refactoring recommendations for oversized files.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
import argparse


def analyze_file(filepath: Path) -> Dict:
    """Analyze a Python file for refactoring opportunities."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Find class definitions
    classes = []
    for i, line in enumerate(lines, 1):
        if match := re.match(r'^class\s+(\w+)', line):
            classes.append((match.group(1), i))
    
    # Find function definitions
    functions = []
    for i, line in enumerate(lines, 1):
        if match := re.match(r'^def\s+(\w+)', line):
            functions.append((match.group(1), i))
    
    # Find imports
    imports = []
    for i, line in enumerate(lines, 1):
        if line.startswith('from ') or line.startswith('import '):
            imports.append(line.strip())
    
    # Calculate complexity metrics
    total_lines = len(lines)
    code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
    
    return {
        'filepath': filepath,
        'total_lines': total_lines,
        'code_lines': code_lines,
        'classes': len(classes),
        'functions': len(functions),
        'imports': len(imports),
        'class_details': classes,
        'function_details': functions,
        'import_lines': imports,
    }


def suggest_splits(analysis: Dict) -> List[str]:
    """Suggest how to split a god file."""
    suggestions = []
    
    filepath = analysis['filepath']
    total_lines = analysis['total_lines']
    classes = analysis['class_details']
    functions = analysis['function_details']
    
    # If single class, split by methods
    if len(classes) == 1:
        suggestions.append(f"Single class file - consider splitting methods into service classes")
        suggestions.append(f"- Extract complex methods (>50 lines) to helper services")
        suggestions.append(f"- Separate data access from business logic")
        suggestions.append(f"- Extract utility functions to separate module")
    
    # If multiple classes, split by class
    elif len(classes) > 1:
        target_lines_per_file = 300
        classes_per_file = max(1, len(classes) // (total_lines // target_lines_per_file + 1))
        
        suggestions.append(f"Multiple classes detected - split into {len(classes)} files")
        for class_name, line_no in classes:
            suggestions.append(f"  - Extract '{class_name}' to separate file (line {line_no})")
    
    # If many functions, group by functionality
    elif len(functions) > 10:
        suggestions.append(f"Many functions ({len(functions)}) - group by functionality:")
        suggestions.append(f"  - Data processing functions")
        suggestions.append(f"  - Validation functions")
        suggestions.append(f"  - Helper/utility functions")
        suggestions.append(f"  - Business logic functions")
    
    return suggestions


def main():
    parser = argparse.ArgumentParser(description='Analyze and suggest refactoring for god files')
    parser.add_argument('--threshold', type=int, default=1000, help='Line count threshold for god files')
    parser.add_argument('--app', help='Specific app to analyze')
    parser.add_argument('--file', help='Specific file to analyze')
    args = parser.parse_args()
    
    # Find god files
    god_files = []
    
    if args.file:
        # Analyze specific file
        filepath = Path(args.file)
        if filepath.exists():
            god_files.append(filepath)
    elif args.app:
        # Analyze specific app
        app_path = Path(f'apps/{args.app}')
        for py_file in app_path.rglob('*.py'):
            if '__pycache__' in str(py_file) or '/migrations/' in str(py_file):
                continue
            line_count = len(open(py_file).readlines())
            if line_count >= args.threshold:
                god_files.append(py_file)
    else:
        # Analyze all apps
        for py_file in Path('apps').rglob('*.py'):
            if '__pycache__' in str(py_file) or '/migrations/' in str(py_file):
                continue
            line_count = len(open(py_file).readlines())
            if line_count >= args.threshold:
                god_files.append(py_file)
    
    if not god_files:
        logger.info(f"No files found with >= {args.threshold} lines")
        return
    
    # Sort by size
    god_files.sort(key=lambda f: len(open(f).readlines()), reverse=True)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"God File Refactoring Analysis (>= {args.threshold} lines)")
    logger.info(f"{'='*80}\n")
    
    for filepath in god_files:
        analysis = analyze_file(filepath)
        suggestions = suggest_splits(analysis)
        
        logger.info(f"\n📄 {filepath.relative_to('apps')}")
        logger.info(f"   Lines: {analysis['total_lines']} (code: {analysis['code_lines']})")
        logger.info(f"   Classes: {analysis['classes']}, Functions: {analysis['functions']}, Imports: {analysis['imports']}")
        
        if suggestions:
            logger.info(f"\n   💡 Refactoring Suggestions:")
            for suggestion in suggestions:
                logger.info(f"   {suggestion}")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Total god files found: {len(god_files)}")
    logger.info(f"{'='*80}\n")


if __name__ == '__main__':
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    main()
