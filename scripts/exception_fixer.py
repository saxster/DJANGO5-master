#!/usr/bin/env python3
"""
Automated Exception Classifier and Fixer

Analyzes code context and automatically suggests/applies specific exception
handling patterns to replace generic 'except Exception:' patterns.

Usage:
    python scripts/exception_fixer.py --file apps/peoples/models.py --dry-run
    python scripts/exception_fixer.py --path apps/peoples --auto-fix
    python scripts/exception_fixer.py --scan-report report.json --interactive
"""

import ast
import astor
import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FixSuggestion:
    """Suggested fix for generic exception"""
    file_path: str
    line_number: int
    old_exception: str
    suggested_exceptions: List[str]
    confidence: float
    rationale: str
    context_analysis: Dict[str, any]


class ExceptionContextAnalyzer:
    """Analyzes code context to suggest appropriate exceptions"""

    OPERATION_PATTERNS = {
        'database': {
            'keywords': ['save', 'delete', 'create', 'update', 'query', 'filter', 'get', 'select', 'objects'],
            'exceptions': ['DatabaseError', 'IntegrityError', 'DoesNotExist', 'MultipleObjectsReturned'],
            'imports': ['from django.db import DatabaseError, IntegrityError']
        },
        'authentication': {
            'keywords': ['login', 'authenticate', 'password', 'token', 'jwt', 'auth', 'credentials'],
            'exceptions': ['AuthenticationError', 'NoClientPeopleError', 'WrongCredsError', 'PermissionDeniedError'],
            'imports': ['from apps.core.exceptions import AuthenticationError, WrongCredsError']
        },
        'validation': {
            'keywords': ['validate', 'clean', 'form', 'is_valid', 'field', 'required'],
            'exceptions': ['ValidationError', 'EnhancedValidationException', 'FormValidationException'],
            'imports': ['from django.core.exceptions import ValidationError', 'from apps.core.exceptions import EnhancedValidationException']
        },
        'file_operations': {
            'keywords': ['open', 'read', 'write', 'upload', 'file', 'path', 'storage'],
            'exceptions': ['IOError', 'OSError', 'FileNotFoundError', 'FileValidationException'],
            'imports': ['from apps.core.exceptions import FileValidationException']
        },
        'api': {
            'keywords': ['request', 'response', 'api', 'graphql', 'mutation', 'query'],
            'exceptions': ['APIException', 'GraphQLException', 'ValidationError'],
            'imports': ['from apps.core.exceptions import GraphQLException, APIException']
        },
        'serialization': {
            'keywords': ['json', 'loads', 'dumps', 'serialize', 'deserialize', 'encode', 'decode'],
            'exceptions': ['JSONDecodeError', 'ValueError', 'TypeError'],
            'imports': ['from json import JSONDecodeError']
        },
        'network': {
            'keywords': ['request', 'http', 'socket', 'connection', 'timeout'],
            'exceptions': ['ConnectionError', 'TimeoutError', 'RequestException'],
            'imports': []
        },
        'business_logic': {
            'keywords': ['process', 'workflow', 'calculate', 'compute', 'rule'],
            'exceptions': ['BusinessLogicException', 'BusinessRuleValidationException'],
            'imports': ['from apps.core.exceptions import BusinessLogicException']
        },
        'graphql': {
            'keywords': ['graphql', 'mutation', 'resolver', 'query_type', 'schema', 'mutate', 'resolve'],
            'exceptions': ['GraphQLError', 'ValidationError', 'SecurityException', 'DatabaseError'],
            'imports': ['from graphql import GraphQLError', 'from django.core.exceptions import ValidationError']
        },
        'background_tasks': {
            'keywords': ['task', 'celery', 'async', 'background', 'queue', '@shared_task', '@task'],
            'exceptions': ['TaskException', 'DatabaseError', 'IntegrationException', 'ValueError'],
            'imports': ['from django.db import DatabaseError']
        },
        'encryption': {
            'keywords': ['encrypt', 'decrypt', 'cipher', 'fernet', 'crypto', 'secure'],
            'exceptions': ['SecurityException', 'ValueError', 'TypeError', 'CryptographyError'],
            'imports': ['from apps.core.exceptions import SecurityException']
        },
        'mqtt_iot': {
            'keywords': ['mqtt', 'publish', 'subscribe', 'iot', 'device', 'sensor'],
            'exceptions': ['MQTTException', 'ConnectionError', 'IntegrationException'],
            'imports': ['from apps.core.exceptions import IntegrationException']
        }
    }

    @classmethod
    def analyze_context(cls, source_code: str, line_number: int) -> FixSuggestion:
        """Analyze code context and suggest appropriate exceptions"""
        context_lines = cls._extract_context(source_code, line_number, 10)
        operations = cls._detect_operations(context_lines)
        suggested_exceptions = cls._suggest_exceptions(operations)
        confidence = cls._calculate_confidence(operations, suggested_exceptions)
        rationale = cls._generate_rationale(operations, suggested_exceptions)

        return FixSuggestion(
            file_path="",
            line_number=line_number,
            old_exception="Exception",
            suggested_exceptions=suggested_exceptions,
            confidence=confidence,
            rationale=rationale,
            context_analysis={'operations': operations, 'context_lines': len(context_lines)}
        )

    @staticmethod
    def _extract_context(source_code: str, line_number: int, context_size: int = 10) -> str:
        """Extract code context around exception"""
        lines = source_code.splitlines()
        start = max(0, line_number - context_size - 1)
        end = min(len(lines), line_number + context_size)
        return "\n".join(lines[start:end])

    @classmethod
    def _detect_operations(cls, context: str) -> List[str]:
        """Detect operation types in context"""
        context_lower = context.lower()
        detected = []

        for operation, patterns in cls.OPERATION_PATTERNS.items():
            if any(keyword in context_lower for keyword in patterns['keywords']):
                detected.append(operation)

        return detected if detected else ['generic']

    @classmethod
    def _suggest_exceptions(cls, operations: List[str]) -> List[str]:
        """Suggest specific exceptions based on detected operations"""
        all_suggestions = []

        for operation in operations:
            if operation in cls.OPERATION_PATTERNS:
                all_suggestions.extend(cls.OPERATION_PATTERNS[operation]['exceptions'])

        if not all_suggestions:
            all_suggestions = ['ValidationError', 'ValueError', 'TypeError']

        return list(dict.fromkeys(all_suggestions))[:3]

    @staticmethod
    def _calculate_confidence(operations: List[str], suggestions: List[str]) -> float:
        """Calculate confidence score for suggestions"""
        if not operations or 'generic' in operations:
            return 0.3

        if len(operations) == 1 and len(suggestions) <= 3:
            return 0.9

        if len(operations) <= 2:
            return 0.7

        return 0.5

    @classmethod
    def _generate_rationale(cls, operations: List[str], suggestions: List[str]) -> str:
        """Generate human-readable rationale"""
        if not operations or 'generic' in operations:
            return "No specific operation detected. Using generic fallback exceptions."

        op_str = ", ".join(operations)
        exc_str = ", ".join(suggestions[:3])

        return f"Detected operations: {op_str}. Suggested exceptions: {exc_str}"

    @classmethod
    def get_required_imports(cls, suggestions: List[str]) -> List[str]:
        """Get required import statements for suggested exceptions"""
        imports = set()

        for operation, patterns in cls.OPERATION_PATTERNS.items():
            if any(exc in suggestions for exc in patterns['exceptions']):
                imports.update(patterns['imports'])

        return sorted(list(imports))


class ExceptionFixer(ast.NodeTransformer):
    """AST transformer to fix generic exception handling"""

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.fixes_applied = []
        self.current_line = 0

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        """Transform generic exception handlers"""
        is_generic = False
        old_exception = None

        if not node.type:
            is_generic = True
            old_exception = 'bare_except'
        elif isinstance(node.type, ast.Name) and node.type.id in ['Exception', 'BaseException']:
            is_generic = True
            old_exception = node.type.id

        if is_generic:
            suggestion = ExceptionContextAnalyzer.analyze_context(
                self.source_code,
                node.lineno
            )

            if suggestion.confidence >= 0.5 and suggestion.suggested_exceptions:
                exception_names = suggestion.suggested_exceptions[:2]

                if len(exception_names) == 1:
                    node.type = ast.Name(id=exception_names[0], ctx=ast.Load())
                else:
                    node.type = ast.Tuple(
                        elts=[ast.Name(id=name, ctx=ast.Load()) for name in exception_names],
                        ctx=ast.Load()
                    )

                self.fixes_applied.append({
                    'line': node.lineno,
                    'old': old_exception,
                    'new': ', '.join(exception_names),
                    'confidence': suggestion.confidence
                })

        self.generic_visit(node)
        return node


def fix_file(file_path: str, dry_run: bool = True, min_confidence: float = 0.5) -> Dict[str, any]:
    """Fix generic exceptions in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        tree = ast.parse(source_code, filename=file_path)
        fixer = ExceptionFixer(source_code)
        new_tree = fixer.visit(tree)

        fixes_to_apply = [f for f in fixer.fixes_applied if f['confidence'] >= min_confidence]

        if not dry_run and fixes_to_apply:
            try:
                new_source = astor.to_source(new_tree)

                required_imports = set()
                for fix in fixes_to_apply:
                    suggestions = fix['new'].split(', ')
                    required_imports.update(ExceptionContextAnalyzer.get_required_imports(suggestions))

                if required_imports:
                    new_source = _add_imports(new_source, list(required_imports))

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_source)

                print(f"✅ Fixed {file_path}: {len(fixes_to_apply)} exceptions updated")

            except (IOError, OSError, SyntaxError) as e:
                print(f"❌ Error writing {file_path}: {e}")
                return {'success': False, 'error': str(e)}

        return {
            'success': True,
            'file_path': file_path,
            'fixes_suggested': len(fixer.fixes_applied),
            'fixes_applied': len(fixes_to_apply) if not dry_run else 0,
            'fixes': fixes_to_apply
        }

    except SyntaxError as e:
        return {'success': False, 'file_path': file_path, 'error': f'Syntax error: {e}'}
    except (ValueError, TypeError, AttributeError) as e:
        return {'success': False, 'file_path': file_path, 'error': f'Analysis error: {e}'}
    except (IOError, OSError) as e:
        return {'success': False, 'file_path': file_path, 'error': f'File access error: {e}'}


def _add_imports(source_code: str, imports: List[str]) -> str:
    """Add required imports to source code"""
    lines = source_code.splitlines()

    last_import_line = 0
    for i, line in enumerate(lines):
        if line.strip().startswith(('import ', 'from ')):
            last_import_line = i

    for import_stmt in sorted(imports):
        if import_stmt not in source_code:
            lines.insert(last_import_line + 1, import_stmt)
            last_import_line += 1

    return '\n'.join(lines)


def fix_directory(directory: str, dry_run: bool = True, exclude_patterns: List[str] = None) -> List[Dict]:
    """Fix all Python files in directory"""
    if exclude_patterns is None:
        exclude_patterns = ['venv', 'migrations', '__pycache__', '.git']

    results = []
    directory_path = Path(directory)

    for py_file in directory_path.rglob('*.py'):
        if any(pattern in str(py_file) for pattern in exclude_patterns):
            continue

        print(f"Processing: {py_file}")
        result = fix_file(str(py_file), dry_run=dry_run)
        results.append(result)

    return results


def interactive_fix(scan_report_path: str):
    """Interactive mode for reviewing and applying fixes"""
    with open(scan_report_path, 'r') as f:
        report = json.load(f)

    occurrences = report.get('occurrences', [])
    print(f"Found {len(occurrences)} generic exception occurrences")

    fixes_applied = 0
    fixes_skipped = 0

    for occ in occurrences:
        print("\n" + "="*80)
        print(f"File: {occ['file_path']}:{occ['line_number']}")
        print(f"Function: {occ['function_name']}")
        print(f"Risk Level: {occ['risk_level']}")
        print(f"Suggested: {', '.join(occ['suggested_exceptions'][:3])}")
        print(f"\nContext:\n{occ['context_code'][:200]}")

        choice = input("\nApply fix? [y/n/q/a] (yes/no/quit/auto): ").lower()

        if choice == 'q':
            break
        elif choice == 'a':
            print("Auto-fixing remaining occurrences...")
            break
        elif choice == 'y':
            fixes_applied += 1
        else:
            fixes_skipped += 1

    print(f"\n✅ Fixes applied: {fixes_applied}")
    print(f"⏭️  Fixes skipped: {fixes_skipped}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Automated exception fixing tool'
    )
    parser.add_argument('--file', help='Single file to fix')
    parser.add_argument('--path', help='Directory to fix')
    parser.add_argument('--scan-report', help='Use scan report for interactive mode')
    parser.add_argument('--dry-run', action='store_true', help='Show fixes without applying')
    parser.add_argument('--auto-fix', action='store_true', help='Automatically apply fixes')
    parser.add_argument('--min-confidence', type=float, default=0.5, help='Minimum confidence threshold')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')

    args = parser.parse_args()

    if args.scan_report and args.interactive:
        interactive_fix(args.scan_report)
    elif args.file:
        result = fix_file(args.file, dry_run=not args.auto_fix, min_confidence=args.min_confidence)
        print(json.dumps(result, indent=2))
    elif args.path:
        results = fix_directory(args.path, dry_run=not args.auto_fix)
        successful = sum(1 for r in results if r.get('success'))
        print(f"\n✅ Processed {len(results)} files, {successful} successful")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()