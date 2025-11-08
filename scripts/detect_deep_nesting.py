#!/usr/bin/env python3
"""
Detect deep nesting in Python files.
"""
import ast
import argparse
from pathlib import Path
from typing import List, Tuple, Dict
import sys


class NestingAnalyzer(ast.NodeVisitor):
    """Analyze nesting depth in Python code."""
    
    def __init__(self):
        self.max_depth = 0
        self.current_depth = 0
        self.nesting_points = []
        
    def _enter_block(self, node):
        self.current_depth += 1
        if self.current_depth > self.max_depth:
            self.max_depth = self.current_depth
            self.nesting_points.append((node.lineno, self.current_depth, type(node).__name__))
    
    def _exit_block(self):
        self.current_depth -= 1
    
    def visit_If(self, node):
        self._enter_block(node)
        self.generic_visit(node)
        self._exit_block()
    
    def visit_For(self, node):
        self._enter_block(node)
        self.generic_visit(node)
        self._exit_block()
    
    def visit_While(self, node):
        self._enter_block(node)
        self.generic_visit(node)
        self._exit_block()
    
    def visit_With(self, node):
        self._enter_block(node)
        self.generic_visit(node)
        self._exit_block()
    
    def visit_Try(self, node):
        self._enter_block(node)
        self.generic_visit(node)
        self._exit_block()
    
    def visit_ExceptHandler(self, node):
        self._enter_block(node)
        self.generic_visit(node)
        self._exit_block()


def analyze_file(filepath: Path) -> Tuple[int, List]:
    """Analyze a single Python file for nesting depth."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        
        return analyzer.max_depth, analyzer.nesting_points
    except (SyntaxError, UnicodeDecodeError, Exception) as e:
        return 0, []


def main():
    parser = argparse.ArgumentParser(description='Detect deep nesting in Python files')
    parser.add_argument('--threshold', type=int, default=3, help='Nesting depth threshold')
    parser.add_argument('--sort-by-depth', action='store_true', help='Sort by nesting depth')
    parser.add_argument('--path', default='apps', help='Path to analyze')
    parser.add_argument('--limit', type=int, default=50, help='Limit results')
    
    args = parser.parse_args()
    
    base_path = Path(args.path)
    if not base_path.exists():
        print(f"Error: Path {base_path} does not exist")
        sys.exit(1)
    
    results = []
    
    for py_file in base_path.rglob('*.py'):
        if '__pycache__' in str(py_file) or 'migrations' in str(py_file):
            continue
        
        max_depth, nesting_points = analyze_file(py_file)
        
        if max_depth > args.threshold:
            results.append({
                'file': str(py_file),
                'max_depth': max_depth,
                'nesting_points': nesting_points
            })
    
    if args.sort_by_depth:
        results.sort(key=lambda x: x['max_depth'], reverse=True)
    
    print(f"\n{'='*80}")
    print(f"DEEP NESTING DETECTION REPORT")
    print(f"{'='*80}")
    print(f"Threshold: {args.threshold} levels")
    print(f"Files analyzed: {len(list(base_path.rglob('*.py')))}")
    print(f"Files with deep nesting: {len(results)}")
    print(f"{'='*80}\n")
    
    for i, result in enumerate(results[:args.limit], 1):
        print(f"{i}. {result['file']}")
        print(f"   Max depth: {result['max_depth']}")
        if result['nesting_points']:
            deepest = max(result['nesting_points'], key=lambda x: x[1])
            print(f"   Deepest point: Line {deepest[0]} ({deepest[2]}) - {deepest[1]} levels")
        print()
    
    if len(results) > args.limit:
        print(f"... and {len(results) - args.limit} more files")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY STATISTICS")
    print(f"{'='*80}")
    if results:
        depths = [r['max_depth'] for r in results]
        print(f"Average max depth: {sum(depths) / len(depths):.1f}")
        print(f"Worst case depth: {max(depths)}")
        print(f"Files with 4+ levels: {len([d for d in depths if d >= 4])}")
        print(f"Files with 5+ levels: {len([d for d in depths if d >= 5])}")
        print(f"Files with 6+ levels: {len([d for d in depths if d >= 6])}")
    
    return len(results)


if __name__ == '__main__':
    sys.exit(0 if main() == 0 else 1)
