#!/usr/bin/env python
"""
Automated N+1 Query Optimization Script

Detects and reports N+1 query patterns across Django admin panels.
Provides recommendations for select_related and prefetch_related optimizations.

Usage:
    python scripts/apply_n1_optimizations.py --scan
    python scripts/apply_n1_optimizations.py --report

Author: Claude Code
Date: 2025-11-07
"""

import os
import re
import ast
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class N1OptimizationAnalyzer:
    """Analyzes Django admin files for N+1 query patterns."""
    
    def __init__(self, apps_dir: str = 'apps'):
        self.apps_dir = Path(apps_dir)
        self.recommendations = defaultdict(lambda: {
            'select_related': set(),
            'prefetch_related': set(),
            'existing_optimizations': [],
            'list_display_fields': [],
        })
    
    def scan_admin_files(self) -> Dict[str, Dict]:
        """Scan all admin.py files and detect optimization opportunities."""
        print("🔍 Scanning Django admin files for N+1 patterns...\n")
        
        admin_files = list(self.apps_dir.rglob('admin.py'))
        
        for admin_file in admin_files:
            if admin_file.is_file():
                self._analyze_admin_file(admin_file)
        
        return self.recommendations
    
    def _analyze_admin_file(self, file_path: Path):
        """Analyze a single admin.py file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse Python AST
            tree = ast.parse(content)
            
            # Find ModelAdmin classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if self._is_model_admin_class(node):
                        self._analyze_model_admin(node, file_path)
        
        except (SyntaxError, UnicodeDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not parse {file_path}: {e}")
    
    def _is_model_admin_class(self, node: ast.ClassDef) -> bool:
        """Check if class inherits from ModelAdmin."""
        for base in node.bases:
            if isinstance(base, ast.Name):
                if 'Admin' in base.id:
                    return True
            elif isinstance(base, ast.Attribute):
                if 'Admin' in base.attr:
                    return True
        return False
    
    def _analyze_model_admin(self, node: ast.ClassDef, file_path: Path):
        """Analyze ModelAdmin class for N+1 patterns."""
        app_name = file_path.parent.name
        class_name = node.name
        key = f"{app_name}.{class_name}"
        
        # Check for existing optimizations
        has_select_related = False
        has_prefetch_related = False
        has_get_queryset = False
        
        list_display_fields = []
        
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check for list_select_related
                        if target.id == 'list_select_related':
                            has_select_related = True
                            self.recommendations[key]['existing_optimizations'].append(
                                'list_select_related'
                            )
                        
                        # Check for list_prefetch_related
                        elif target.id == 'list_prefetch_related':
                            has_prefetch_related = True
                            self.recommendations[key]['existing_optimizations'].append(
                                'list_prefetch_related'
                            )
                        
                        # Extract list_display fields
                        elif target.id == 'list_display':
                            if isinstance(item.value, (ast.List, ast.Tuple)):
                                for elt in item.value.elts:
                                    if isinstance(elt, ast.Str):
                                        list_display_fields.append(elt.s)
                                    elif isinstance(elt, ast.Constant):
                                        list_display_fields.append(elt.value)
            
            # Check for get_queryset override
            elif isinstance(item, ast.FunctionDef):
                if item.name == 'get_queryset':
                    has_get_queryset = True
                    self.recommendations[key]['existing_optimizations'].append(
                        'get_queryset override'
                    )
        
        # Store analysis results
        self.recommendations[key]['list_display_fields'] = list_display_fields
        self.recommendations[key]['file_path'] = str(file_path)
        self.recommendations[key]['has_select_related'] = has_select_related
        self.recommendations[key]['has_prefetch_related'] = has_prefetch_related
        self.recommendations[key]['has_get_queryset'] = has_get_queryset
        
        # Recommend optimizations if missing
        if not has_select_related and not has_get_queryset:
            self.recommendations[key]['needs_optimization'] = True
            self.recommendations[key]['recommendation'] = (
                "Add list_select_related for foreign key relations in list_display"
            )
    
    def generate_report(self) -> str:
        """Generate comprehensive optimization report."""
        report = []
        report.append("=" * 80)
        report.append("N+1 QUERY OPTIMIZATION REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Summary statistics
        total_admins = len(self.recommendations)
        optimized = sum(1 for r in self.recommendations.values() 
                       if r.get('has_select_related') or r.get('has_get_queryset'))
        needs_optimization = total_admins - optimized
        
        report.append(f"📊 Summary:")
        report.append(f"   Total Admin Classes: {total_admins}")
        report.append(f"   ✅ Already Optimized: {optimized}")
        report.append(f"   ⚠️  Needs Optimization: {needs_optimization}")
        report.append("")
        
        # Priority recommendations
        report.append("=" * 80)
        report.append("🔴 HIGH PRIORITY - Missing N+1 Optimizations")
        report.append("=" * 80)
        report.append("")
        
        high_priority = {k: v for k, v in self.recommendations.items() 
                        if v.get('needs_optimization')}
        
        if high_priority:
            for key, data in sorted(high_priority.items()):
                report.append(f"📁 {key}")
                report.append(f"   File: {data['file_path']}")
                report.append(f"   List Display Fields: {', '.join(data['list_display_fields'][:10])}")
                if len(data['list_display_fields']) > 10:
                    report.append(f"   ... and {len(data['list_display_fields']) - 10} more")
                report.append(f"   💡 Recommendation: {data['recommendation']}")
                report.append("")
                report.append("   Suggested Fix:")
                report.append("   ```python")
                report.append("   # Add to your ModelAdmin class:")
                report.append("   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields")
                report.append("   list_prefetch_related = ['tags', 'attachments']  # M2M fields")
                report.append("   ```")
                report.append("")
        else:
            report.append("✅ All admin panels have N+1 optimizations!")
            report.append("")
        
        # Already optimized (showcase good examples)
        report.append("=" * 80)
        report.append("✅ WELL OPTIMIZED - Good Examples")
        report.append("=" * 80)
        report.append("")
        
        optimized_examples = {k: v for k, v in self.recommendations.items() 
                             if v.get('has_select_related') or v.get('has_get_queryset')}
        
        for key, data in sorted(list(optimized_examples.items())[:10]):
            report.append(f"📁 {key}")
            report.append(f"   File: {data['file_path']}")
            report.append(f"   Optimizations: {', '.join(data['existing_optimizations'])}")
            report.append("")
        
        return "\n".join(report)
    
    def get_models_needing_optimization(self) -> Dict[str, List[str]]:
        """Get list of models that need optimization by app."""
        needs_opt = defaultdict(list)
        
        for key, data in self.recommendations.items():
            if data.get('needs_optimization'):
                app, admin_class = key.split('.', 1)
                needs_opt[app].append(admin_class)
        
        return dict(needs_opt)


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze and optimize N+1 queries in Django admin panels'
    )
    parser.add_argument(
        '--scan',
        action='store_true',
        help='Scan all admin files and generate report'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate detailed optimization report'
    )
    parser.add_argument(
        '--apps',
        default='apps',
        help='Path to apps directory (default: apps)'
    )
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = N1OptimizationAnalyzer(apps_dir=args.apps)
    
    # Scan files
    if args.scan or args.report:
        recommendations = analyzer.scan_admin_files()
        
        # Generate report
        report = analyzer.generate_report()
        print(report)
        
        # Save report to file
        report_path = Path('N1_OPTIMIZATION_ADMIN_REPORT.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("\n" + "=" * 80)
        print(f"📝 Report saved to: {report_path}")
        print("=" * 80)
        
        # Show apps needing optimization
        needs_opt = analyzer.get_models_needing_optimization()
        if needs_opt:
            print("\n📋 Apps Needing Optimization:")
            for app, admins in sorted(needs_opt.items()):
                print(f"   - {app}: {len(admins)} admin classes")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
