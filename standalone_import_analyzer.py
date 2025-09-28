#!/usr/bin/env python3
"""
Standalone import analyzer that can run without Django.

This script provides comprehensive analysis of:
- Unused imports
- Circular import dependencies
- Import style inconsistencies (relative vs absolute)
- Import dependency visualization

Usage:
    python3 standalone_import_analyzer.py
    python3 standalone_import_analyzer.py --fix-unused
"""

import ast
import os
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import json
import argparse

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not available. Circular import analysis will be limited.")


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract import information from Python files."""

    def __init__(self):
        self.imports = []
        self.from_imports = []
        self.used_names = set()

    def visit_Import(self, node):
        """Visit regular import statements."""
        for alias in node.names:
            import_info = {
                'type': 'import',
                'module': alias.name,
                'alias': alias.asname,
                'lineno': node.lineno,
                'end_lineno': getattr(node, 'end_lineno', node.lineno)
            }
            self.imports.append(import_info)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Visit from...import statements."""
        if node.module:
            for alias in node.names:
                import_info = {
                    'type': 'from_import',
                    'module': node.module,
                    'name': alias.name,
                    'alias': alias.asname,
                    'level': node.level,  # 0 = absolute, >0 = relative
                    'lineno': node.lineno,
                    'end_lineno': getattr(node, 'end_lineno', node.lineno)
                }
                self.from_imports.append(import_info)
        self.generic_visit(node)

    def visit_Name(self, node):
        """Visit name usage to track what's actually used."""
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        """Visit attribute access to track module usage."""
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)


class StandaloneImportAnalyzer:
    """Standalone version of the import analyzer."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.apps_root = project_root / 'apps'
        self.issues = {
            'unused_imports': [],
            'circular_imports': [],
            'style_inconsistencies': [],
            'potential_issues': []
        }
        if HAS_NETWORKX:
            self.dependency_graph = nx.DiGraph()
        else:
            self.dependency_graph = None

    def analyze_file(self, file_path: Path) -> Dict:
        """Analyze a single Python file for import issues."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))
            visitor = ImportVisitor()
            visitor.visit(tree)

            return {
                'file_path': file_path,
                'imports': visitor.imports,
                'from_imports': visitor.from_imports,
                'used_names': visitor.used_names,
                'content': content
            }

        except (SyntaxError, UnicodeDecodeError) as e:
            return {
                'file_path': file_path,
                'error': str(e),
                'imports': [],
                'from_imports': [],
                'used_names': set()
            }

    def find_unused_imports(self, file_info: Dict) -> List[Dict]:
        """Find imports that are never used in the file."""
        unused = []
        used_names = file_info['used_names']

        # Check regular imports
        for imp in file_info['imports']:
            import_name = imp['alias'] if imp['alias'] else imp['module'].split('.')[0]
            if import_name not in used_names:
                unused.append({
                    'type': 'unused_import',
                    'file': str(file_info['file_path']),
                    'line': imp['lineno'],
                    'import_statement': f"import {imp['module']}" + (f" as {imp['alias']}" if imp['alias'] else ""),
                    'suggested_fix': 'Remove this import'
                })

        # Check from imports
        for imp in file_info['from_imports']:
            import_name = imp['alias'] if imp['alias'] else imp['name']
            if import_name not in used_names and imp['name'] != '*':
                unused.append({
                    'type': 'unused_from_import',
                    'file': str(file_info['file_path']),
                    'line': imp['lineno'],
                    'import_statement': f"from {imp['module']} import {imp['name']}" + (f" as {imp['alias']}" if imp['alias'] else ""),
                    'suggested_fix': 'Remove this import'
                })

        return unused

    def find_style_inconsistencies(self, file_info: Dict) -> List[Dict]:
        """Find inconsistencies between relative and absolute imports."""
        inconsistencies = []
        has_relative = False
        has_absolute_app = False

        for imp in file_info['from_imports']:
            if imp['level'] > 0:  # Relative import
                has_relative = True
            elif imp['module'] and imp['module'].startswith('apps.'):
                has_absolute_app = True

        if has_relative and has_absolute_app:
            inconsistencies.append({
                'type': 'mixed_import_styles',
                'file': str(file_info['file_path']),
                'issue': 'File mixes relative and absolute imports for app modules',
                'suggested_fix': 'Use consistent import style (prefer absolute for cross-app, relative within app)'
            })

        return inconsistencies

    def build_dependency_graph(self, all_file_info: List[Dict]):
        """Build a directed graph of module dependencies."""
        if not HAS_NETWORKX:
            return

        for file_info in all_file_info:
            if 'error' in file_info:
                continue

            file_path = file_info['file_path']
            module_name = self._get_module_name(file_path)

            # Add all imported modules as dependencies
            for imp in file_info['imports'] + file_info['from_imports']:
                if imp.get('module'):
                    # Resolve relative imports
                    if imp.get('level', 0) > 0:
                        imported_module = self._resolve_relative_import(
                            module_name, imp['module'], imp['level']
                        )
                    else:
                        imported_module = imp['module']

                    if imported_module and imported_module.startswith('apps.'):
                        self.dependency_graph.add_edge(module_name, imported_module)

    def find_circular_imports(self) -> List[Dict]:
        """Find circular import dependencies using the dependency graph."""
        if not HAS_NETWORKX or not self.dependency_graph:
            return [{
                'type': 'analysis_limitation',
                'message': 'Circular import analysis requires networkx package'
            }]

        cycles = []
        try:
            # Find strongly connected components (cycles)
            strongly_connected = list(nx.strongly_connected_components(self.dependency_graph))

            for component in strongly_connected:
                if len(component) > 1:  # Only cycles with more than one node
                    cycle_nodes = list(component)
                    cycles.append({
                        'type': 'circular_import',
                        'modules': cycle_nodes,
                        'severity': 'high' if len(cycle_nodes) > 2 else 'medium',
                        'suggested_fix': 'Refactor to remove circular dependency by moving shared code to a common module'
                    })
        except Exception as e:
            cycles.append({
                'type': 'analysis_error',
                'error': f"Error analyzing circular imports: {str(e)}"
            })

        return cycles

    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to Python module name."""
        try:
            rel_path = file_path.relative_to(self.project_root)
            parts = list(rel_path.parts)

            # Remove .py extension
            if parts[-1].endswith('.py'):
                parts[-1] = parts[-1][:-3]

            # Remove __init__ if present
            if parts[-1] == '__init__':
                parts = parts[:-1]

            return '.'.join(parts)
        except ValueError:
            return str(file_path)

    def _resolve_relative_import(self, current_module: str, imported_module: str, level: int) -> str:
        """Resolve relative imports to absolute module names."""
        current_parts = current_module.split('.')

        # Go up 'level' number of directories
        base_parts = current_parts[:-level] if level < len(current_parts) else []

        if imported_module:
            return '.'.join(base_parts + [imported_module])
        else:
            return '.'.join(base_parts)

    def analyze_all_files(self) -> Dict:
        """Analyze all Python files in the apps directory."""
        print("🔍 Analyzing Python files for import issues...")

        if not self.apps_root.exists():
            print(f"❌ Apps directory not found: {self.apps_root}")
            return self.issues

        python_files = list(self.apps_root.rglob('*.py'))
        print(f"📁 Found {len(python_files)} Python files to analyze")

        all_file_info = []

        for i, file_path in enumerate(python_files):
            if i % 50 == 0:
                print(f"   Progress: {i}/{len(python_files)} files...")

            file_info = self.analyze_file(file_path)
            all_file_info.append(file_info)

            # Collect unused imports
            if 'error' not in file_info:
                unused = self.find_unused_imports(file_info)
                self.issues['unused_imports'].extend(unused)

                # Collect style inconsistencies
                style_issues = self.find_style_inconsistencies(file_info)
                self.issues['style_inconsistencies'].extend(style_issues)

        # Build dependency graph and find circular imports
        if HAS_NETWORKX:
            print("🔗 Building dependency graph...")
            self.build_dependency_graph(all_file_info)

            print("🔄 Analyzing circular dependencies...")
            circular_imports = self.find_circular_imports()
            self.issues['circular_imports'].extend(circular_imports)

        return self.issues

    def generate_report(self, issues: Dict) -> str:
        """Generate a comprehensive report of all import issues."""
        report = []
        report.append("=" * 80)
        report.append("🔍 COMPREHENSIVE IMPORT ANALYSIS REPORT")
        report.append("=" * 80)

        # Summary
        total_issues = sum(len(issues[key]) for key in issues if isinstance(issues[key], list))
        report.append(f"\n📊 SUMMARY:")
        report.append(f"   Total Issues Found: {total_issues}")
        report.append(f"   - Unused Imports: {len(issues['unused_imports'])}")
        report.append(f"   - Circular Imports: {len(issues['circular_imports'])}")
        report.append(f"   - Style Inconsistencies: {len(issues['style_inconsistencies'])}")

        # Unused Imports (show top 20)
        if issues['unused_imports']:
            unused_count = len(issues['unused_imports'])
            report.append(f"\n🗑️  UNUSED IMPORTS ({unused_count} found):")
            report.append("-" * 50)

            # Show top 20 to avoid overwhelming output
            for i, issue in enumerate(issues['unused_imports'][:20]):
                report.append(f"   📄 {issue['file']}")
                report.append(f"      Line {issue['line']}: {issue['import_statement']}")
                report.append(f"      💡 {issue['suggested_fix']}")
                report.append("")

            if unused_count > 20:
                report.append(f"   ... and {unused_count - 20} more unused imports")
                report.append("")

        # Circular Imports
        if issues['circular_imports']:
            report.append(f"\n🔄 CIRCULAR IMPORTS ({len(issues['circular_imports'])} found):")
            report.append("-" * 50)
            for issue in issues['circular_imports']:
                if 'modules' in issue:
                    report.append(f"   ⚠️  {issue['severity'].upper()} severity circular dependency:")
                    report.append(f"      Modules: {' -> '.join(issue['modules'])}")
                    report.append(f"      💡 {issue['suggested_fix']}")
                    report.append("")

        # Style Inconsistencies (show top 10)
        if issues['style_inconsistencies']:
            style_count = len(issues['style_inconsistencies'])
            report.append(f"\n🎨 IMPORT STYLE INCONSISTENCIES ({style_count} found):")
            report.append("-" * 50)
            for i, issue in enumerate(issues['style_inconsistencies'][:10]):
                report.append(f"   📄 {issue['file']}")
                report.append(f"      Issue: {issue['issue']}")
                report.append(f"      💡 {issue['suggested_fix']}")
                report.append("")

            if style_count > 10:
                report.append(f"   ... and {style_count - 10} more style inconsistencies")
                report.append("")

        # Recommendations
        report.append("\n🎯 RECOMMENDATIONS:")
        report.append("-" * 50)
        if issues['unused_imports']:
            report.append("   1. Remove unused imports to reduce code clutter")
        if issues['circular_imports']:
            report.append("   2. Refactor circular dependencies by extracting shared code")
        if issues['style_inconsistencies']:
            report.append("   3. Standardize import styles across the codebase")
        report.append("   4. Add pre-commit hooks to prevent future import issues")
        report.append("   5. Use absolute imports for cross-app dependencies")

        return "\n".join(report)

    def fix_unused_imports(self, issues: Dict) -> int:
        """Automatically fix unused imports by removing them."""
        fixed_count = 0
        files_to_fix = defaultdict(list)

        # Group issues by file
        for issue in issues['unused_imports']:
            files_to_fix[issue['file']].append(issue)

        for file_path, file_issues in files_to_fix.items():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Sort by line number in descending order to avoid line number shifts
                file_issues.sort(key=lambda x: x['line'], reverse=True)

                for issue in file_issues:
                    line_idx = issue['line'] - 1  # Convert to 0-based index
                    if 0 <= line_idx < len(lines):
                        lines.pop(line_idx)
                        fixed_count += 1
                        print(f"✅ Fixed: {issue['import_statement']} in {file_path}:{issue['line']}")

                # Write back the modified file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)

            except Exception as e:
                print(f"❌ Error fixing {file_path}: {str(e)}")

        return fixed_count


def main():
    """Main function for standalone execution."""
    parser = argparse.ArgumentParser(description='Analyze import organization issues in the codebase')
    parser.add_argument(
        '--fix-unused',
        action='store_true',
        help='Automatically fix unused imports by removing them'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='import_analysis_reports',
        help='Directory to save analysis reports'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='Project root directory'
    )

    args = parser.parse_args()

    # Determine project root
    project_root = Path(args.project_root).resolve()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"🚀 Starting import analysis for project: {project_root}")

    # Initialize analyzer
    analyzer = StandaloneImportAnalyzer(project_root)

    # Run analysis
    issues = analyzer.analyze_all_files()

    # Generate and save report
    report = analyzer.generate_report(issues)
    report_path = output_dir / 'import_analysis_report.txt'

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    # Display summary
    print(report)
    print(f"\n📄 Full report saved to: {report_path}")

    # Save detailed JSON data
    json_path = output_dir / 'import_issues_detailed.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(issues, f, indent=2, default=str)

    print(f"📊 Detailed JSON data saved to: {json_path}")

    # Fix unused imports if requested
    if args.fix_unused:
        print("\n🔧 Automatically fixing unused imports...")
        fixed_count = analyzer.fix_unused_imports(issues)
        print(f"✅ Fixed {fixed_count} unused imports")

    # Final summary
    total_issues = sum(len(issues[key]) for key in issues if isinstance(issues[key], list))
    if total_issues == 0:
        print("\n🎉 No import issues found! Your codebase is clean.")
    else:
        print(f"\n⚠️  Found {total_issues} import issues that need attention.")
        if not args.fix_unused:
            print("💡 Run with --fix-unused to automatically fix unused imports")


if __name__ == '__main__':
    main()