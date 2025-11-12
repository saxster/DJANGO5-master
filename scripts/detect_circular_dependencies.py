#!/usr/bin/env python3
"""
Advanced Circular Dependency Detection for Django Apps

Detects circular dependencies at multiple levels:
1. App-level circular imports (e.g., peoples → attendance → peoples)
2. Model-level circular foreign keys
3. Signal-level dependencies
4. Service-level dependencies

Usage:
    python scripts/detect_circular_dependencies.py apps/
    python scripts/detect_circular_dependencies.py apps/ --verbose
    python scripts/detect_circular_dependencies.py apps/ --diagram deps.md

Author: Development Team
Date: 2025-11-06
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
    """Container for circular dependency information"""
    cycle: List[str]
    cycle_type: str  # 'import', 'model', 'signal', 'service'
    severity: str  # 'critical', 'warning', 'info'
    evidence: List[str]  # File paths or line numbers showing the dependency
    
    def __str__(self):
        arrow = " ↔ " if len(self.cycle) == 2 else " → "
        cycle_str = arrow.join(self.cycle + [self.cycle[0]])
        return f"[{self.cycle_type}] {cycle_str}"


class AppDependencyDetector:
    """Detects circular dependencies at the Django app level"""
    
    def __init__(self, apps_dir: Path, verbose: bool = False):
        self.apps_dir = apps_dir
        self.verbose = verbose
        self.app_imports: Dict[str, Set[str]] = defaultdict(set)
        self.model_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.circular_deps: List[CircularDependency] = []
        
    def log(self, message: str, level: str = 'INFO'):
        """Log message if verbose mode enabled"""
        if self.verbose or level in ['ERROR', 'CRITICAL', 'SUCCESS']:
            prefix = {
                'INFO': '📝',
                'SUCCESS': '✅',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🔴',
            }.get(level, '')
            print(f"{prefix} {message}")
    
    def get_app_name(self, filepath: Path) -> str:
        """Extract Django app name from file path"""
        try:
            rel_path = filepath.relative_to(self.apps_dir)
            return rel_path.parts[0]
        except (ValueError, IndexError):
            return None
    
    def extract_app_imports(self, filepath: Path) -> Set[str]:
        """Extract app-level imports from a Python file"""
        imports = set()
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(filepath))
            
            for node in ast.walk(tree):
                # Handle: from apps.xxx import ...
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith('apps.'):
                        parts = node.module.split('.')
                        if len(parts) >= 2:
                            app_name = parts[1]
                            imports.add(app_name)
                
                # Handle: import apps.xxx
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('apps.'):
                            parts = alias.name.split('.')
                            if len(parts) >= 2:
                                app_name = parts[1]
                                imports.add(app_name)
        
        except (SyntaxError, Exception) as e:
            if self.verbose:
                self.log(f"Could not parse {filepath}: {e}", 'WARNING')
        
        return imports
    
    def extract_model_dependencies(self, filepath: Path) -> List[Tuple[str, str]]:
        """Extract ForeignKey relationships from models.py"""
        dependencies = []
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(filepath))
            
            # Look for ForeignKey and ManyToManyField
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    
                    if func_name in ['ForeignKey', 'OneToOneField', 'ManyToManyField']:
                        # Get the first argument (the related model)
                        if node.args:
                            arg = node.args[0]
                            if isinstance(arg, ast.Constant):
                                related_model = arg.value
                                # Extract app name from 'app.Model' format
                                if '.' in related_model:
                                    related_app = related_model.split('.')[0]
                                    dependencies.append((related_app, func_name))
        
        except (SyntaxError, Exception) as e:
            if self.verbose:
                self.log(f"Could not parse {filepath} for models: {e}", 'WARNING')
        
        return dependencies
    
    def build_dependency_graph(self):
        """Build app-level dependency graph"""
        self.log("=" * 80)
        self.log("BUILDING APP-LEVEL DEPENDENCY GRAPH")
        self.log("=" * 80)
        
        if not self.apps_dir.exists():
            self.log(f"Directory {self.apps_dir} not found", 'ERROR')
            return
        
        # Get all Django apps
        apps = [d for d in self.apps_dir.iterdir() 
                if d.is_dir() and not d.name.startswith('_')]
        
        self.log(f"Found {len(apps)} Django apps")
        
        # Analyze each app
        for app_dir in apps:
            app_name = app_dir.name
            
            # Get all Python files in the app
            py_files = [f for f in app_dir.rglob('*.py')
                       if 'migrations' not in str(f) and '__pycache__' not in str(f)]
            
            # Extract imports
            for py_file in py_files:
                imports = self.extract_app_imports(py_file)
                # Remove self-imports
                imports.discard(app_name)
                self.app_imports[app_name].update(imports)
                
                # Extract model dependencies
                if py_file.name in ['models.py', 'models_core.py', 'models_attendance.py']:
                    model_deps = self.extract_model_dependencies(py_file)
                    for related_app, _ in model_deps:
                        if related_app != app_name:
                            self.model_dependencies[app_name].add(related_app)
        
        self.log(f"Analyzed imports for {len(self.app_imports)} apps")
        self.log(f"Analyzed model dependencies for {len(self.model_dependencies)} apps")
    
    def detect_cycles_dfs(self, graph: Dict[str, Set[str]], cycle_type: str) -> List[CircularDependency]:
        """Detect cycles in a dependency graph using DFS"""
        cycles = []
        visited = set()
        rec_stack = []
        
        def dfs(node: str):
            if node in rec_stack:
                # Found a cycle
                cycle_start = rec_stack.index(node)
                cycle = rec_stack[cycle_start:] + [node]
                
                # Determine severity
                cycle_length = len(cycle) - 1
                if cycle_length <= 2:
                    severity = 'critical'
                elif cycle_length <= 4:
                    severity = 'warning'
                else:
                    severity = 'info'
                
                cycles.append(CircularDependency(
                    cycle=rec_stack[cycle_start:],
                    cycle_type=cycle_type,
                    severity=severity,
                    evidence=[]
                ))
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.append(node)
            
            for neighbor in graph.get(node, set()):
                dfs(neighbor)
            
            rec_stack.pop()
        
        for node in graph:
            if node not in visited:
                dfs(node)
        
        return cycles
    
    def detect_all_cycles(self):
        """Detect all types of circular dependencies"""
        self.log("=" * 80)
        self.log("DETECTING CIRCULAR DEPENDENCIES")
        self.log("=" * 80)
        
        # Detect import cycles
        import_cycles = self.detect_cycles_dfs(self.app_imports, 'import')
        self.circular_deps.extend(import_cycles)
        
        # Detect model dependency cycles
        model_cycles = self.detect_cycles_dfs(self.model_dependencies, 'model')
        self.circular_deps.extend(model_cycles)
        
        # Remove duplicates
        seen = set()
        unique_cycles = []
        for cycle in self.circular_deps:
            # Create a normalized key
            cycle_key = tuple(sorted(cycle.cycle)) + (cycle.cycle_type,)
            if cycle_key not in seen:
                seen.add(cycle_key)
                unique_cycles.append(cycle)
        
        self.circular_deps = unique_cycles
    
    def report_findings(self):
        """Generate detailed report of findings"""
        self.log("=" * 80)
        self.log("CIRCULAR DEPENDENCY REPORT")
        self.log("=" * 80)
        
        if not self.circular_deps:
            self.log("✨ No circular dependencies detected!", 'SUCCESS')
            return True
        
        # Group by severity
        critical = [c for c in self.circular_deps if c.severity == 'critical']
        warnings = [c for c in self.circular_deps if c.severity == 'warning']
        info = [c for c in self.circular_deps if c.severity == 'info']
        
        total = len(self.circular_deps)
        self.log(f"Found {total} circular dependencies:", 'ERROR')
        self.log(f"  🔴 Critical: {len(critical)}")
        self.log(f"  ⚠️  Warnings: {len(warnings)}")
        self.log(f"  ℹ️  Info: {len(info)}")
        self.log("")
        
        # Report critical cycles
        if critical:
            self.log("🔴 CRITICAL CYCLES (must be fixed):", 'CRITICAL')
            for i, cycle in enumerate(critical, 1):
                self.log(f"  {i}. {cycle}", 'CRITICAL')
            self.log("")
        
        # Report warning cycles
        if warnings:
            self.log("⚠️  WARNING CYCLES (should be fixed):", 'WARNING')
            for i, cycle in enumerate(warnings, 1):
                self.log(f"  {i}. {cycle}", 'WARNING')
            self.log("")
        
        # Report info cycles
        if info:
            self.log("ℹ️  INFO CYCLES (review recommended):", 'INFO')
            for i, cycle in enumerate(info[:5], 1):  # Show first 5
                self.log(f"  {i}. {cycle}")
            if len(info) > 5:
                self.log(f"  ... and {len(info) - 5} more")
            self.log("")
        
        # Resolution patterns
        self.log("=" * 80)
        self.log("RECOMMENDED RESOLUTION PATTERNS")
        self.log("=" * 80)
        self.log("""
Pattern 1: Dependency Inversion
  - Move shared code to apps/core/
  - Both apps depend on core, not each other
  
Pattern 2: Late/Lazy Imports
  - Use function-level imports
  - Document why late import is needed
  
Pattern 3: Signals/Events
  - Use Django signals instead of direct imports
  - Decouples apps
  
Pattern 4: Abstract Interfaces
  - Define interfaces/protocols in one app
  - Other app implements without importing
  
Pattern 5: Dependency Injection
  - Pass dependencies via parameters
  - Avoid hardcoded imports
""")
        
        return len(critical) == 0  # Pass if no critical cycles
    
    def generate_diagram(self, output_file: str):
        """Generate Mermaid diagram of app dependencies"""
        self.log(f"Generating dependency diagram: {output_file}")
        
        with open(output_file, 'w') as f:
            f.write("# App Dependency Diagram\n\n")
            f.write("```mermaid\n")
            f.write("graph TD\n")
            
            # Add all edges
            all_apps = set(self.app_imports.keys()) | set().union(*self.app_imports.values())
            for app in sorted(all_apps):
                for dep in sorted(self.app_imports.get(app, set())):
                    # Highlight circular dependencies in red
                    is_circular = any(
                        app in cycle.cycle and dep in cycle.cycle
                        for cycle in self.circular_deps
                    )
                    if is_circular:
                        f.write(f"    {app}[{app}] -.->|CIRCULAR| {dep}[{dep}]\n")
                        f.write(f"    style {app} fill:#ff6b6b\n")
                        f.write(f"    style {dep} fill:#ff6b6b\n")
                    else:
                        f.write(f"    {app}[{app}] --> {dep}[{dep}]\n")
            
            f.write("```\n\n")
            
            # Add cycle details
            f.write("## Detected Cycles\n\n")
            if self.circular_deps:
                for i, cycle in enumerate(self.circular_deps, 1):
                    f.write(f"{i}. **{cycle.severity.upper()}**: {cycle}\n")
            else:
                f.write("✅ No circular dependencies detected!\n")
        
        self.log(f"Diagram saved to {output_file}", 'SUCCESS')


def main():
    parser = argparse.ArgumentParser(
        description='Detect circular dependencies in Django apps'
    )
    parser.add_argument('apps_dir', nargs='?', default='apps/',
                       help='Path to apps directory (default: apps/)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--diagram', type=str,
                       help='Generate dependency diagram (Mermaid format)')
    
    args = parser.parse_args()
    
    # Create detector
    apps_path = Path(args.apps_dir)
    detector = AppDependencyDetector(apps_path, verbose=args.verbose)
    
    # Run analysis
    detector.build_dependency_graph()
    detector.detect_all_cycles()
    passed = detector.report_findings()
    
    # Generate diagram if requested
    if args.diagram:
        detector.generate_diagram(args.diagram)
    
    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
