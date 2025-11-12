#!/usr/bin/env python3
"""
Detect Oversized View Methods

Finds view methods exceeding 30-line limit for service layer refactoring.

Usage:
    python scripts/detect_oversized_methods.py --path apps/ --limit 30
    python scripts/detect_oversized_methods.py --path apps/ --limit 30 --top 100
"""
import argparse
import ast
import sys
from pathlib import Path
from typing import List, Dict


def count_method_lines(node: ast.FunctionDef, source_lines: List[str]) -> int:
    """Count actual lines in a method (excluding docstrings)"""
    if not hasattr(node, 'lineno') or not hasattr(node, 'end_lineno'):
        return 0
    
    start_line = node.lineno - 1
    end_line = node.end_lineno
    
    # Get method source
    method_lines = source_lines[start_line:end_line]
    
    # Skip docstring if present
    if node.body and isinstance(node.body[0], ast.Expr):
        if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
            # Find docstring end
            if hasattr(node.body[0], 'end_lineno'):
                docstring_end = node.body[0].end_lineno - node.lineno
                method_lines = method_lines[docstring_end + 1:]
    
    # Count non-empty, non-comment lines
    code_lines = [
        line for line in method_lines
        if line.strip() and not line.strip().startswith('#')
    ]
    
    return len(code_lines)


def analyze_file(file_path: Path, line_limit: int = 30) -> List[Dict]:
    """Analyze a Python file for oversized methods"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
            source_lines = source.splitlines()
        
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, IOError) as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return []
    
    oversized_methods = []
    
    # Find all function and method definitions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            line_count = count_method_lines(node, source_lines)
            
            if line_count > line_limit:
                # Determine if it's a view method
                is_view = (
                    'views.py' in str(file_path) or
                    'views/' in str(file_path) or
                    any(decorator.id == 'require_http_methods' if isinstance(decorator, ast.Name) else False 
                        for decorator in node.decorator_list if hasattr(decorator, 'id'))
                )
                
                oversized_methods.append({
                    'file': str(file_path),
                    'method': node.name,
                    'lines': line_count,
                    'start_line': node.lineno,
                    'end_line': node.end_lineno,
                    'is_view': is_view,
                    'violation_pct': round(((line_count - line_limit) / line_limit) * 100, 1)
                })
    
    return oversized_methods


def find_oversized_methods(
    root_path: Path,
    line_limit: int = 30,
    focus_views: bool = True
) -> List[Dict]:
    """Find all oversized methods in Python files"""
    all_methods = []
    
    # Search patterns
    if focus_views:
        patterns = ['**/views.py', '**/views/*.py']
    else:
        patterns = ['**/*.py']
    
    exclude_patterns = [
        '**/migrations/**',
        '**/tests/**',
        '**/test_*.py',
        '**/__pycache__/**',
        '**/venv/**',
        '**/env/**',
    ]
    
    for pattern in patterns:
        for py_file in root_path.rglob(pattern.replace('**/', '')):
            # Skip excluded paths
            if any(py_file.match(ex) for ex in exclude_patterns):
                continue
            
            methods = analyze_file(py_file, line_limit)
            all_methods.extend(methods)
    
    # Sort by line count (largest first)
    all_methods.sort(key=lambda x: x['lines'], reverse=True)
    
    return all_methods


def generate_report(methods: List[Dict], top_n: int = None) -> str:
    """Generate markdown report"""
    if top_n:
        methods = methods[:top_n]
    
    report_lines = [
        f"# Oversized View Methods Report",
        f"",
        f"**Total violations**: {len(methods)}",
        f"**Showing**: Top {len(methods)}",
        f"",
        "## Top Violations (Largest Methods)",
        "",
        "| # | File | Method | Lines | Violation % | Line Range |",
        "|---|------|--------|-------|-------------|------------|",
    ]
    
    for idx, method in enumerate(methods, 1):
        file_short = Path(method['file']).relative_to(Path.cwd()) if Path(method['file']).is_relative_to(Path.cwd()) else method['file']
        
        report_lines.append(
            f"| {idx} | `{file_short}` | `{method['method']}` | "
            f"{method['lines']} | {method['violation_pct']}% | "
            f"L{method['start_line']}-L{method['end_line']} |"
        )
    
    report_lines.extend([
        "",
        "## Refactoring Priority",
        "",
        "**High Priority (>100 lines)**:",
        f"- {len([m for m in methods if m['lines'] > 100])} methods",
        "",
        "**Medium Priority (60-100 lines)**:",
        f"- {len([m for m in methods if 60 < m['lines'] <= 100])} methods",
        "",
        "**Low Priority (30-60 lines)**:",
        f"- {len([m for m in methods if 30 < m['lines'] <= 60])} methods",
        "",
        "## Refactoring Pattern",
        "",
        "```python",
        "# BEFORE (oversized method)",
        "def create_work_order(request):",
        "    # 80+ lines of validation, business logic, notifications",
        "    pass",
        "",
        "# AFTER (refactored to service layer)",
        "def create_work_order(request):",
        "    form = WorkOrderForm(request.POST)",
        "    if not form.is_valid():",
        "        return render(request, 'form.html', {'form': form})",
        "    ",
        "    work_order = WorkOrderService.create_work_order(",
        "        data=form.cleaned_data,",
        "        user=request.user",
        "    )",
        "    ",
        "    NotificationService.notify_work_order_created(work_order)",
        "    return redirect('work_order_detail', pk=work_order.id)",
        "```",
    ])
    
    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(description='Detect oversized view methods')
    parser.add_argument('--path', default='apps/', help='Root path to analyze')
    parser.add_argument('--limit', type=int, default=30, help='Line limit for methods')
    parser.add_argument('--top', type=int, help='Show only top N violations')
    parser.add_argument('--all', action='store_true', help='Analyze all files, not just views')
    parser.add_argument('--output', help='Output report to file')
    
    args = parser.parse_args()
    
    root_path = Path(args.path)
    if not root_path.exists():
        print(f"❌ Path not found: {args.path}")
        sys.exit(1)
    
    print(f"🔍 Analyzing methods in {args.path}...")
    print(f"   Line limit: {args.limit}")
    print(f"   Focus: {'All files' if args.all else 'View files only'}")
    
    methods = find_oversized_methods(root_path, args.limit, focus_views=not args.all)
    
    if not methods:
        print("✅ No oversized methods found!")
        sys.exit(0)
    
    print(f"\n📊 Found {len(methods)} oversized methods")
    
    # Generate report
    report = generate_report(methods, args.top)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to {args.output}")
    else:
        print("\n" + report)
    
    # Show top 10 summary
    print(f"\n{'='*70}")
    print("Top 10 Largest Methods:")
    print(f"{'='*70}")
    for idx, method in enumerate(methods[:10], 1):
        file_name = Path(method['file']).name
        print(f"{idx:2}. {file_name}::{method['method']} - {method['lines']} lines "
              f"({method['violation_pct']}% over limit)")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
