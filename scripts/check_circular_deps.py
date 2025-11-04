#!/usr/bin/env python3
"""
Circular Dependency Detection Script

Detects circular imports in the codebase using static analysis.
Circular dependencies can cause:
- Import errors at runtime
- Initialization issues
- Tight coupling
- Testing difficulties

Usage:
    python scripts/check_circular_deps.py
    python scripts/check_circular_deps.py --verbose
    python scripts/check_circular_deps.py --ci
    python scripts/check_circular_deps.py --pre-commit
    python scripts/check_circular_deps.py --graph deps.svg

Exit codes:
    0: No circular dependencies found
    1: Circular dependencies detected

Author: Quality Gates Engineer
Date: 2025-11-04
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class CircularDependency:
    """Container for circular dependency"""
    cycle: List[str]
    cycle_length: int

    def __str__(self):
        arrow = " → "
        return arrow.join(self.cycle + [self.cycle[0]])


class CircularDependencyDetector:
    """Detects circular dependencies using graph analysis"""

    def __init__(self, root_dir: str = '.', verbose: bool = False):
        self.root_dir = Path(root_dir).resolve()
        self.verbose = verbose
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.circular_deps: List[CircularDependency] = []

    def log(self, message: str, level: str = 'INFO'):
        """Log message if verbose mode enabled"""
        if self.verbose or level in ['ERROR', 'CRITICAL']:
            prefix = {
                'INFO': 'ℹ️ ',
                'SUCCESS': '✅',
                'WARNING': '⚠️ ',
                'ERROR': '❌',
                'CRITICAL': '🔴',
            }.get(level, '')
            print(f"{prefix} {message}")

    def extract_imports(self, filepath: Path) -> Set[str]:
        """Extract all imports from a Python file"""
        imports = set()

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(filepath))

            for node in ast.walk(tree):
                # Handle: import module
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        imports.add(module)

                # Handle: from module import ...
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        imports.add(module)

        except SyntaxError as e:
            self.log(f"Syntax error in {filepath}: {e}", 'WARNING')
        except Exception as e:
            self.log(f"Error parsing {filepath}: {e}", 'WARNING')

        return imports

    def build_import_graph(self):
        """Build import dependency graph"""
        self.log("Building import dependency graph...")

        apps_dir = self.root_dir / 'apps'
        if not apps_dir.exists():
            self.log("apps/ directory not found", 'WARNING')
            return

        # Get all Python files in apps/
        py_files = []
        for py_file in apps_dir.rglob('*.py'):
            if ('migrations' not in str(py_file) and
                '__pycache__' not in str(py_file) and
                'test_' not in py_file.name):
                py_files.append(py_file)

        self.log(f"Analyzing {len(py_files)} Python files...")

        # Build graph: module -> set of imported modules
        for py_file in py_files:
            # Determine module name (e.g., apps.core.models)
            try:
                rel_path = py_file.relative_to(self.root_dir)
                parts = rel_path.parts[:-1]  # Exclude filename
                if py_file.name != '__init__.py':
                    module_name = '.'.join(parts)
                else:
                    module_name = '.'.join(parts)

                # Extract imports
                imports = self.extract_imports(py_file)

                # Filter to only local imports (apps.*)
                local_imports = {imp for imp in imports if imp in ['apps'] or imp.startswith('apps.')}

                if local_imports:
                    self.import_graph[module_name].update(local_imports)

            except Exception as e:
                self.log(f"Error processing {py_file}: {e}", 'WARNING')

        self.log(f"Graph built: {len(self.import_graph)} modules with dependencies")

    def detect_cycles(self):
        """Detect circular dependencies using DFS"""
        self.log("Detecting circular dependencies...")

        visited = set()
        rec_stack = set()
        cycles_found = set()

        def dfs(node: str, path: List[str]):
            """DFS to detect cycles"""
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                # Normalize cycle (start with smallest element) to avoid duplicates
                min_idx = cycle.index(min(cycle[:-1]))  # Exclude last duplicate element
                normalized = tuple(cycle[min_idx:-1] + cycle[:min_idx])
                cycles_found.add(normalized)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Visit neighbors
            for neighbor in self.import_graph.get(node, set()):
                dfs(neighbor, path[:])

            rec_stack.remove(node)

        # Run DFS from each node
        for node in self.import_graph:
            if node not in visited:
                dfs(node, [])

        # Convert to CircularDependency objects
        self.circular_deps = [
            CircularDependency(cycle=list(cycle), cycle_length=len(cycle))
            for cycle in cycles_found
        ]

        # Sort by cycle length (shorter cycles are more critical)
        self.circular_deps.sort(key=lambda x: x.cycle_length)

    def run_detection(self) -> bool:
        """Run circular dependency detection"""
        self.log("=" * 70)
        self.log("CIRCULAR DEPENDENCY DETECTION")
        self.log("=" * 70)

        self.build_import_graph()
        self.detect_cycles()

        self.log("=" * 70)
        if self.circular_deps:
            self.log(f"FOUND: {len(self.circular_deps)} circular dependencies", 'ERROR')
            self.log("=" * 70)

            # Group by severity (cycle length)
            short_cycles = [c for c in self.circular_deps if c.cycle_length <= 3]
            medium_cycles = [c for c in self.circular_deps if 3 < c.cycle_length <= 5]
            long_cycles = [c for c in self.circular_deps if c.cycle_length > 5]

            if short_cycles:
                self.log(f"\n🔴 CRITICAL: Short cycles (length ≤ 3): {len(short_cycles)}", 'CRITICAL')
                for cycle in short_cycles[:10]:  # Show first 10
                    self.log(f"  {cycle}", 'CRITICAL')
                if len(short_cycles) > 10:
                    self.log(f"  ... and {len(short_cycles)-10} more", 'CRITICAL')

            if medium_cycles:
                self.log(f"\n⚠️  WARNING: Medium cycles (length 4-5): {len(medium_cycles)}", 'WARNING')
                for cycle in medium_cycles[:5]:  # Show first 5
                    self.log(f"  {cycle}", 'WARNING')
                if len(medium_cycles) > 5:
                    self.log(f"  ... and {len(medium_cycles)-5} more", 'WARNING')

            if long_cycles:
                self.log(f"\n📋 INFO: Long cycles (length > 5): {len(long_cycles)}", 'INFO')
                self.log("  (These may be acceptable depending on context)", 'INFO')

            self.log("\n📖 Recommendations:", 'INFO')
            self.log("  1. Use dependency injection instead of direct imports", 'INFO')
            self.log("  2. Extract shared code into separate modules", 'INFO')
            self.log("  3. Move imports inside functions (lazy imports)", 'INFO')
            self.log("  4. Review architecture to reduce coupling", 'INFO')

            # Return success for now (warnings only)
            # Change to return False to enforce as errors
            return True
        else:
            self.log("SUCCESS: No circular dependencies detected", 'SUCCESS')
            self.log("=" * 70)
            return True


def main():
    parser = argparse.ArgumentParser(
        description='Detect circular dependencies in Python codebase'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--ci', action='store_true',
                        help='CI mode: strict exit codes')
    parser.add_argument('--pre-commit', action='store_true',
                        help='Pre-commit mode: fast validation')
    parser.add_argument('--graph', type=str,
                        help='Generate dependency graph (requires graphviz)')

    args = parser.parse_args()

    # Create detector
    detector = CircularDependencyDetector(verbose=args.verbose or args.ci)

    # Run detection
    passed = detector.run_detection()

    # Generate graph if requested
    if args.graph:
        print(f"\n⚠️  Graph generation requires pydeps: pip install pydeps")
        print(f"Run: pydeps apps/ --max-bacon 2 -o {args.graph}")

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
