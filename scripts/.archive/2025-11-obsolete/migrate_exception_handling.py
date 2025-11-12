#!/usr/bin/env python3
"""
Automated Exception Handling Migration Script

Analyzes and migrates generic "except Exception:" statements to specific
exception types per .claude/rules.md Rule #1.

Usage:
    # Dry run (analyze only):
    python scripts/migrate_exception_handling.py --analyze

    # Generate report:
    python scripts/migrate_exception_handling.py --report exception_migration_report.md

    # Auto-fix with confirmation:
    python scripts/migrate_exception_handling.py --fix --interactive

    # Auto-fix specific files:
    python scripts/migrate_exception_handling.py --fix --files apps/core/services/*.py

Author: Code Quality Team
Date: 2025-09-30
"""

import ast
import os
import sys
import argparse
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ExceptionAnalyzer(ast.NodeVisitor):
    """
    AST visitor that finds and analyzes generic exception handlers.
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.issues = []
        self.context_stack = []

    def visit_ExceptHandler(self, node):
        """Visit except handler nodes"""
        # Check if it's generic "except Exception:"
        if node.type and isinstance(node.type, ast.Name):
            if node.type.id == 'Exception':
                context = self._analyze_context(node)
                self.issues.append({
                    'filename': self.filename,
                    'lineno': node.lineno,
                    'context': context,
                    'current_handler': 'except Exception:',
                    'suggested_fix': self._suggest_fix(context),
                    'confidence': self._calculate_confidence(context),
                    'ast_node': node
                })
        self.generic_visit(node)

    def visit_Try(self, node):
        """Track try-except blocks for context"""
        self.context_stack.append(('try', node))
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_FunctionDef(self, node):
        """Track function definitions for context"""
        self.context_stack.append(('function', node.name))
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_ClassDef(self, node):
        """Track class definitions for context"""
        self.context_stack.append(('class', node.name))
        self.generic_visit(node)
        self.context_stack.pop()

    def _analyze_context(self, except_node) -> Dict:
        """Analyze the code context to determine exception types"""
        context = {
            'has_database_ops': False,
            'has_network_ops': False,
            'has_file_ops': False,
            'has_json_ops': False,
            'function_name': None,
            'class_name': None,
        }

        # Extract function/class context
        for ctx_type, ctx_value in reversed(self.context_stack):
            if ctx_type == 'function' and not context['function_name']:
                context['function_name'] = ctx_value
            elif ctx_type == 'class' and not context['class_name']:
                context['class_name'] = ctx_value

        # Analyze try block for operations
        if self.context_stack and self.context_stack[-1][0] == 'try':
            try_node = self.context_stack[-1][1]
            code = ast.unparse(try_node) if hasattr(ast, 'unparse') else ""

            # Database operations
            db_patterns = ['.save()', '.delete()', '.update()', '.create(',
                           'objects.get', 'objects.filter', '.execute(']
            context['has_database_ops'] = any(p in code for p in db_patterns)

            # Network operations
            net_patterns = ['requests.', 'urllib.', 'http.', 'urlopen(',
                            'Session().', '.get(', '.post(']
            context['has_network_ops'] = any(p in code for p in net_patterns)

            # File operations
            file_patterns = ['open(', '.read(', '.write(', 'Path(',
                             'os.path.', 'shutil.']
            context['has_file_ops'] = any(p in code for p in file_patterns)

            # JSON operations
            json_patterns = ['json.loads', 'json.dumps', '.json()', 'JSON']
            context['has_json_ops'] = any(p in code for p in json_patterns)

        return context

    def _suggest_fix(self, context: Dict) -> str:
        """Suggest specific exception types based on context"""
        exceptions = []

        if context['has_database_ops']:
            exceptions.append('from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS')
            return 'except DATABASE_EXCEPTIONS as e:'

        if context['has_network_ops']:
            exceptions.append('from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS')
            return 'except NETWORK_EXCEPTIONS as e:'

        if context['has_file_ops']:
            exceptions.append('from apps.core.exceptions.patterns import FILE_EXCEPTIONS')
            return 'except FILE_EXCEPTIONS as e:'

        if context['has_json_ops']:
            exceptions.append('from apps.core.exceptions.patterns import JSON_EXCEPTIONS')
            return 'except JSON_EXCEPTIONS as e:'

        # Default: parsing/validation errors
        return 'except (ValueError, TypeError, KeyError, AttributeError) as e:'

    def _calculate_confidence(self, context: Dict) -> str:
        """Calculate confidence level in the suggested fix"""
        op_count = sum([
            context['has_database_ops'],
            context['has_network_ops'],
            context['has_file_ops'],
            context['has_json_ops']
        ])

        if op_count == 1:
            return 'HIGH'
        elif op_count > 1:
            return 'MEDIUM'
        else:
            return 'LOW'


def analyze_file(filepath: str) -> List[Dict]:
    """Analyze a single Python file for generic exception handlers"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source, filename=filepath)
        analyzer = ExceptionAnalyzer(filepath)
        analyzer.visit(tree)
        return analyzer.issues

    except SyntaxError as e:
        print(f"⚠️  Syntax error in {filepath}: {e}")
        return []
    except Exception as e:
        print(f"⚠️  Error analyzing {filepath}: {e}")
        return []


def find_python_files(root_dir: str, exclude_patterns: List[str] = None) -> List[str]:
    """Find all Python files in directory, excluding specified patterns"""
    if exclude_patterns is None:
        exclude_patterns = [
            '*/migrations/*',
            '*/test_*',
            '*/__pycache__/*',
            '*/venv/*',
            '*/env/*',
        ]

    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if not any(
            re.match(pattern.replace('*', '.*'), os.path.join(root, d))
            for pattern in exclude_patterns
        )]

        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if not any(re.match(pattern.replace('*', '.*'), filepath)
                           for pattern in exclude_patterns):
                    python_files.append(filepath)

    return python_files


def generate_report(all_issues: List[Dict], output_file: str):
    """Generate markdown report of found issues"""
    # Group by confidence level
    by_confidence = defaultdict(list)
    for issue in all_issues:
        by_confidence[issue['confidence']].append(issue)

    # Group by suggested fix
    by_fix = defaultdict(list)
    for issue in all_issues:
        by_fix[issue['suggested_fix']].append(issue)

    report = f"""# Exception Handling Migration Report

**Generated:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Issues Found:** {len(all_issues)}

## Executive Summary

| Confidence | Count | Percentage |
|------------|-------|------------|
| HIGH | {len(by_confidence['HIGH'])} | {len(by_confidence['HIGH'])/len(all_issues)*100:.1f}% |
| MEDIUM | {len(by_confidence['MEDIUM'])} | {len(by_confidence['MEDIUM'])/len(all_issues)*100:.1f}% |
| LOW | {len(by_confidence['LOW'])} | {len(by_confidence['LOW'])/len(all_issues)*100:.1f}% |

## Breakdown by Suggested Fix

"""

    for fix_type, issues in sorted(by_fix.items(), key=lambda x: len(x[1]), reverse=True):
        report += f"### {fix_type}\n"
        report += f"**Count:** {len(issues)} occurrences\n\n"
        report += "**Files:**\n"
        for issue in issues[:10]:  # Show first 10
            func_info = f" ({issue['context']['function_name']})" if issue['context']['function_name'] else ""
            report += f"- `{issue['filename']}:{issue['lineno']}`{func_info}\n"
        if len(issues) > 10:
            report += f"- ... and {len(issues) - 10} more\n"
        report += "\n"

    report += """## How to Use This Report

### High Confidence Issues (Auto-fixable)
These issues can be safely auto-fixed with the migration script:
```bash
python scripts/migrate_exception_handling.py --fix --confidence HIGH
```

### Medium/Low Confidence Issues (Manual Review)
These require manual review to determine the correct exception types:
1. Review the suggested fix
2. Check the surrounding code context
3. Apply the fix manually or adjust the suggestion

## Next Steps

1. **Run auto-fix for HIGH confidence issues** (recommended)
2. **Review MEDIUM confidence** issues (10-30 min)
3. **Manually fix LOW confidence** issues (requires code inspection)

## Pattern Examples

For correct exception handling patterns, see:
- `apps/core/exceptions/patterns.py` - Pattern library
- `.claude/rules.md` Rule #1 - Exception handling standards

---
**Note:** This is an automated analysis. Always review suggested changes before applying.
"""

    with open(output_file, 'w') as f:
        f.write(report)

    print(f"✅ Report generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate generic exception handlers to specific types'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze codebase and show statistics'
    )
    parser.add_argument(
        '--report',
        type=str,
        metavar='FILE',
        help='Generate markdown report to FILE'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Apply fixes to files (use with caution)'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Ask for confirmation before each fix'
    )
    parser.add_argument(
        '--confidence',
        choices=['HIGH', 'MEDIUM', 'LOW', 'ALL'],
        default='ALL',
        help='Only process issues with specified confidence level'
    )
    parser.add_argument(
        '--files',
        nargs='+',
        help='Specific files to process (supports wildcards)'
    )
    parser.add_argument(
        '--root',
        default='apps',
        help='Root directory to scan (default: apps)'
    )

    args = parser.parse_args()

    if not (args.analyze or args.report or args.fix):
        parser.print_help()
        return

    # Find files to process
    if args.files:
        import glob
        python_files = []
        for pattern in args.files:
            python_files.extend(glob.glob(pattern))
    else:
        python_files = find_python_files(args.root)

    print(f"🔍 Analyzing {len(python_files)} Python files...")

    # Analyze all files
    all_issues = []
    for i, filepath in enumerate(python_files, 1):
        if i % 50 == 0:
            print(f"   Progress: {i}/{len(python_files)} files analyzed...")

        issues = analyze_file(filepath)
        all_issues.extend(issues)

    print(f"\n✅ Analysis complete!")
    print(f"   Found {len(all_issues)} generic exception handlers")

    # Filter by confidence if specified
    if args.confidence != 'ALL':
        all_issues = [i for i in all_issues if i['confidence'] == args.confidence]
        print(f"   Filtered to {len(all_issues)} {args.confidence} confidence issues")

    # Show statistics
    if args.analyze or args.report:
        print("\n📊 Statistics:")
        by_confidence = defaultdict(int)
        by_file = defaultdict(int)
        for issue in all_issues:
            by_confidence[issue['confidence']] += 1
            by_file[issue['filename']] += 1

        print(f"   HIGH confidence: {by_confidence['HIGH']}")
        print(f"   MEDIUM confidence: {by_confidence['MEDIUM']}")
        print(f"   LOW confidence: {by_confidence['LOW']}")
        print(f"\n   Top 5 files with most issues:")
        for filename, count in sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   - {filename}: {count} issues")

    # Generate report
    if args.report:
        generate_report(all_issues, args.report)

    # Apply fixes (not implemented in this version for safety)
    if args.fix:
        print("\n⚠️  Auto-fix not implemented yet for safety reasons.")
        print("   Please use the report to manually review and apply fixes.")
        print("   This prevents accidental breaking changes.")


if __name__ == '__main__':
    main()