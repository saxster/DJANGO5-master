#!/usr/bin/env python3
"""
Import Dependency Visualizer

This tool creates visual representations of import dependencies in the Django project.
It can generate:
- HTML interactive dependency graphs
- Text-based dependency trees
- JSON data for external visualization tools
- Circular dependency reports

Usage:
    python3 import_dependency_visualizer.py
    python3 import_dependency_visualizer.py --format html
    python3 import_dependency_visualizer.py --format json
    python3 import_dependency_visualizer.py --app-focus attendance
"""

import ast
import json
import argparse
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional


class DependencyVisualizer:
    """Create visual representations of import dependencies."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.apps_root = project_root / 'apps'
        self.dependencies = defaultdict(set)
        self.reverse_dependencies = defaultdict(set)
        self.app_dependencies = defaultdict(set)
        self.all_modules = set()

    def analyze_file(self, file_path: Path) -> Dict:
        """Analyze a single file for its import dependencies."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))

            module_name = self._get_module_name(file_path)
            dependencies = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.level > 0:  # Relative import
                        resolved = self._resolve_relative_import(module_name, node.module, node.level)
                        if resolved:
                            dependencies.add(resolved)
                    else:
                        dependencies.add(node.module)

            return {
                'module': module_name,
                'dependencies': dependencies,
                'app': self._get_app_name(module_name)
            }

        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            return {
                'module': self._get_module_name(file_path),
                'dependencies': set(),
                'app': None
            }

    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to Python module name."""
        try:
            rel_path = file_path.relative_to(self.project_root)
            parts = list(rel_path.parts)

            if parts[-1].endswith('.py'):
                parts[-1] = parts[-1][:-3]

            if parts[-1] == '__init__':
                parts = parts[:-1]

            return '.'.join(parts)
        except ValueError:
            return str(file_path)

    def _get_app_name(self, module_name: str) -> Optional[str]:
        """Extract app name from module name."""
        if module_name.startswith('apps.'):
            parts = module_name.split('.')
            return parts[1] if len(parts) > 1 else None
        return None

    def _resolve_relative_import(self, current_module: str, imported_module: str, level: int) -> str:
        """Resolve relative imports to absolute module names."""
        current_parts = current_module.split('.')
        base_parts = current_parts[:-level] if level < len(current_parts) else []

        if imported_module:
            return '.'.join(base_parts + [imported_module])
        else:
            return '.'.join(base_parts)

    def build_dependency_graph(self):
        """Build the complete dependency graph for the project."""
        print("🔍 Analyzing project dependencies...")

        python_files = list(self.apps_root.rglob('*.py'))
        print(f"📁 Found {len(python_files)} Python files")

        for i, file_path in enumerate(python_files):
            if i % 100 == 0:
                print(f"   Progress: {i}/{len(python_files)} files...")

            file_info = self.analyze_file(file_path)
            module = file_info['module']
            dependencies = file_info['dependencies']
            app = file_info['app']

            self.all_modules.add(module)

            # Build module-level dependencies
            for dep in dependencies:
                if dep.startswith('apps.'):
                    self.dependencies[module].add(dep)
                    self.reverse_dependencies[dep].add(module)

            # Build app-level dependencies
            if app:
                for dep in dependencies:
                    dep_app = self._get_app_name(dep)
                    if dep_app and dep_app != app:
                        self.app_dependencies[app].add(dep_app)

        print(f"✅ Analysis complete: {len(self.all_modules)} modules, {len(self.app_dependencies)} apps")

    def find_circular_dependencies(self) -> List[List[str]]:
        """Find circular dependencies using DFS."""
        def dfs(node, visited, rec_stack, path):
            visited[node] = True
            rec_stack[node] = True
            path.append(node)

            for neighbor in self.dependencies.get(node, []):
                if neighbor not in visited:
                    cycle = dfs(neighbor, visited, rec_stack, path[:])
                    if cycle:
                        return cycle
                elif rec_stack.get(neighbor, False):
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            rec_stack[node] = False
            return None

        visited = {}
        rec_stack = {}
        cycles = []

        for node in self.all_modules:
            if node not in visited:
                cycle = dfs(node, visited, rec_stack, [])
                if cycle:
                    cycles.append(cycle)

        return cycles

    def generate_html_visualization(self, output_path: Path, focus_app: str = None):
        """Generate an interactive HTML visualization."""
        # Prepare data for visualization
        nodes = []
        edges = []

        # Filter by app if requested
        if focus_app:
            modules_to_include = {m for m in self.all_modules if self._get_app_name(m) == focus_app}
            # Also include dependencies of these modules
            for module in list(modules_to_include):
                modules_to_include.update(self.dependencies.get(module, []))
                modules_to_include.update(self.reverse_dependencies.get(module, []))
        else:
            modules_to_include = self.all_modules

        # Create nodes
        app_colors = {
            'attendance': '#FF6B6B',
            'core': '#4ECDC4',
            'peoples': '#45B7D1',
            'activity': '#96CEB4',
            'journal': '#FFEAA7',
            'face_recognition': '#DDA0DD',
            'mentor': '#98D8C8',
            'onboarding': '#FDCB6E',
            'schedhuler': '#A8E6CF',
            'y_helpdesk': '#FFB3BA',
        }

        for module in modules_to_include:
            app = self._get_app_name(module)
            color = app_colors.get(app, '#BDC3C7')

            nodes.append({
                'id': module,
                'label': module.split('.')[-1] if '.' in module else module,
                'title': module,
                'color': color,
                'app': app or 'other'
            })

        # Create edges
        for module, deps in self.dependencies.items():
            if module in modules_to_include:
                for dep in deps:
                    if dep in modules_to_include:
                        edges.append({
                            'from': module,
                            'to': dep,
                            'arrows': 'to'
                        })

        # Generate HTML
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Import Dependencies - {focus_app or 'All Apps'}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        #visualization {{ width: 100%; height: 80vh; border: 1px solid #ccc; }}
        .controls {{ margin-bottom: 20px; }}
        .legend {{ margin-top: 20px; }}
        .legend-item {{ display: inline-block; margin-right: 20px; }}
        .legend-color {{ width: 20px; height: 20px; display: inline-block; margin-right: 5px; vertical-align: middle; }}
        .stats {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>Import Dependency Visualization - {focus_app or 'All Apps'}</h1>

    <div class="stats">
        <strong>Statistics:</strong>
        Modules: {len(nodes)} |
        Dependencies: {len(edges)} |
        Apps: {len(set(n['app'] for n in nodes))}
    </div>

    <div class="controls">
        <button onclick="resetView()">Reset View</button>
        <button onclick="hierarchicalLayout()">Hierarchical Layout</button>
        <button onclick="physicsLayout()">Physics Layout</button>
        <label>
            <input type="checkbox" id="showLabels" onchange="toggleLabels()" checked> Show Labels
        </label>
    </div>

    <div id="visualization"></div>

    <div class="legend">
        <h3>Legend (Apps):</h3>
        {self._generate_legend_html(app_colors, [n['app'] for n in nodes])}
    </div>

    <script type="text/javascript">
        const nodes = new vis.DataSet({json.dumps(nodes, indent=2)});
        const edges = new vis.DataSet({json.dumps(edges, indent=2)});

        const container = document.getElementById('visualization');
        const data = {{ nodes: nodes, edges: edges }};

        const options = {{
            physics: {{
                enabled: true,
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{ gravitationalConstant: -50 }}
            }},
            layout: {{ randomSeed: 2 }},
            nodes: {{
                shape: 'box',
                font: {{ size: 12 }},
                margin: 10,
                borderWidth: 2
            }},
            edges: {{
                arrows: 'to',
                smooth: {{ type: 'dynamic' }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 200
            }}
        }};

        const network = new vis.Network(container, data, options);

        function resetView() {{
            network.fit();
        }}

        function hierarchicalLayout() {{
            network.setOptions({{
                layout: {{
                    hierarchical: {{
                        direction: 'DU',
                        sortMethod: 'directed'
                    }}
                }},
                physics: false
            }});
        }}

        function physicsLayout() {{
            network.setOptions({{
                layout: {{ hierarchical: false }},
                physics: {{ enabled: true }}
            }});
        }}

        function toggleLabels() {{
            const showLabels = document.getElementById('showLabels').checked;
            network.setOptions({{
                nodes: {{ font: {{ size: showLabels ? 12 : 0 }} }}
            }});
        }}

        // Highlight connected nodes on click
        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const connectedNodes = network.getConnectedNodes(nodeId);
                const connectedEdges = network.getConnectedEdges(nodeId);

                // Highlight logic here
                console.log('Selected node:', nodeId);
                console.log('Connected nodes:', connectedNodes);
            }}
        }});
    </script>
</body>
</html>
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"📊 HTML visualization saved to: {output_path}")

    def _generate_legend_html(self, app_colors: Dict[str, str], apps_in_graph: List[str]) -> str:
        """Generate HTML legend for app colors."""
        unique_apps = sorted(set(apps_in_graph))
        legend_items = []

        for app in unique_apps:
            if app != 'other':
                color = app_colors.get(app, '#BDC3C7')
                legend_items.append(
                    f'<div class="legend-item">'
                    f'<span class="legend-color" style="background-color: {color};"></span>'
                    f'{app}</div>'
                )

        return '\n'.join(legend_items)

    def generate_text_report(self, output_path: Path, focus_app: str = None):
        """Generate a detailed text report of dependencies."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("📊 IMPORT DEPENDENCY ANALYSIS REPORT\n")
            f.write("=" * 80 + "\n\n")

            # Summary
            f.write("📋 SUMMARY:\n")
            f.write(f"   Total Modules: {len(self.all_modules)}\n")
            f.write(f"   Total Apps: {len(self.app_dependencies)}\n")
            f.write(f"   Total Dependencies: {sum(len(deps) for deps in self.dependencies.values())}\n\n")

            # App-level dependencies
            f.write("🏗️  APP-LEVEL DEPENDENCIES:\n")
            f.write("-" * 50 + "\n")
            for app, deps in sorted(self.app_dependencies.items()):
                if not focus_app or app == focus_app:
                    f.write(f"📦 {app}:\n")
                    if deps:
                        for dep in sorted(deps):
                            f.write(f"   → {dep}\n")
                    else:
                        f.write("   (no external app dependencies)\n")
                    f.write("\n")

            # Circular dependencies
            cycles = self.find_circular_dependencies()
            if cycles:
                f.write("🔄 CIRCULAR DEPENDENCIES DETECTED:\n")
                f.write("-" * 50 + "\n")
                for i, cycle in enumerate(cycles, 1):
                    f.write(f"Cycle {i}:\n")
                    for j, module in enumerate(cycle):
                        if j < len(cycle) - 1:
                            f.write(f"   {module} → {cycle[j + 1]}\n")
                    f.write("\n")
            else:
                f.write("✅ NO CIRCULAR DEPENDENCIES DETECTED\n\n")

            # Most imported modules
            import_counts = defaultdict(int)
            for deps in self.dependencies.values():
                for dep in deps:
                    import_counts[dep] += 1

            f.write("📈 MOST IMPORTED MODULES:\n")
            f.write("-" * 50 + "\n")
            top_imports = sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            for module, count in top_imports:
                f.write(f"   {module}: {count} imports\n")
            f.write("\n")

            # Modules with most dependencies
            dependency_counts = [(mod, len(deps)) for mod, deps in self.dependencies.items()]
            dependency_counts.sort(key=lambda x: x[1], reverse=True)

            f.write("📤 MODULES WITH MOST DEPENDENCIES:\n")
            f.write("-" * 50 + "\n")
            for module, count in dependency_counts[:10]:
                if count > 0:
                    f.write(f"   {module}: {count} dependencies\n")
            f.write("\n")

            # Recommendations
            f.write("💡 RECOMMENDATIONS:\n")
            f.write("-" * 50 + "\n")
            if cycles:
                f.write("   1. ⚠️  Resolve circular dependencies by refactoring shared code\n")
            else:
                f.write("   1. ✅ No circular dependencies - good architecture!\n")

            high_dep_modules = [mod for mod, count in dependency_counts[:5] if count > 10]
            if high_dep_modules:
                f.write("   2. 🔍 Consider splitting high-dependency modules:\n")
                for mod in high_dep_modules:
                    f.write(f"      - {mod}\n")

            f.write("   3. 📋 Regularly review and minimize cross-app dependencies\n")
            f.write("   4. 🏗️  Consider using dependency injection for better testability\n")

        print(f"📄 Text report saved to: {output_path}")

    def generate_json_data(self, output_path: Path):
        """Generate JSON data for external visualization tools."""
        data = {
            'metadata': {
                'total_modules': len(self.all_modules),
                'total_apps': len(self.app_dependencies),
                'timestamp': str(Path(output_path).stat().st_mtime)
            },
            'modules': list(self.all_modules),
            'dependencies': {k: list(v) for k, v in self.dependencies.items()},
            'app_dependencies': {k: list(v) for k, v in self.app_dependencies.items()},
            'circular_dependencies': self.find_circular_dependencies()
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"📊 JSON data saved to: {output_path}")


def main():
    """Main function for dependency visualization."""
    parser = argparse.ArgumentParser(description='Visualize import dependencies')
    parser.add_argument(
        '--format',
        choices=['html', 'text', 'json', 'all'],
        default='all',
        help='Output format'
    )
    parser.add_argument(
        '--app-focus',
        type=str,
        help='Focus visualization on specific app'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='dependency_visualizations',
        help='Output directory'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='Project root directory'
    )

    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"🚀 Starting dependency visualization for: {project_root}")

    if args.app_focus:
        print(f"🎯 Focusing on app: {args.app_focus}")

    visualizer = DependencyVisualizer(project_root)
    visualizer.build_dependency_graph()

    if args.format in ['html', 'all']:
        suffix = f"_{args.app_focus}" if args.app_focus else ""
        html_path = output_dir / f"dependencies{suffix}.html"
        visualizer.generate_html_visualization(html_path, args.app_focus)

    if args.format in ['text', 'all']:
        suffix = f"_{args.app_focus}" if args.app_focus else ""
        text_path = output_dir / f"dependency_report{suffix}.txt"
        visualizer.generate_text_report(text_path, args.app_focus)

    if args.format in ['json', 'all']:
        json_path = output_dir / "dependency_data.json"
        visualizer.generate_json_data(json_path)

    print("\n🎉 Dependency visualization complete!")
    print(f"📁 Files saved to: {output_dir}")

    if args.format in ['html', 'all']:
        print(f"🌐 Open the HTML file in your browser to explore the interactive visualization")


if __name__ == '__main__':
    main()