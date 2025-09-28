#!/usr/bin/env python3
"""
Batch Exception Remediator - Automated Fix Generator

Intelligently fixes generic 'except Exception' patterns based on code context.
Uses AST analysis and pattern matching to suggest and apply specific exception types.

Usage:
    python scripts/batch_exception_remediator.py --category middleware
    python scripts/batch_exception_remediator.py --category background_tasks --auto-apply
    python scripts/batch_exception_remediator.py --file apps/reports/views.py --dry-run
"""

import ast
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExceptionContextAnalyzer:
    """Analyzes code context to determine appropriate specific exceptions."""

    CONTEXT_PATTERNS = {
        'database': {
            'keywords': ['save', 'delete', 'create', 'update', 'objects', 'query', 'filter', 'get'],
            'exceptions': ['DatabaseError', 'IntegrityError', 'OperationalError', 'ObjectDoesNotExist'],
            'imports': 'from django.db import DatabaseError, IntegrityError, OperationalError\nfrom django.core.exceptions import ObjectDoesNotExist'
        },
        'cache': {
            'keywords': ['cache.get', 'cache.set', 'cache.delete', 'redis'],
            'exceptions': ['ConnectionError'],
            'imports': ''
        },
        'validation': {
            'keywords': ['clean', 'validate', 'is_valid', 'form', 'ValidationError'],
            'exceptions': ['ValidationError', 'ValueError', 'TypeError'],
            'imports': 'from django.core.exceptions import ValidationError'
        },
        'file_ops': {
            'keywords': ['open(', 'read()', 'write(', 'file.', 'upload', 'download'],
            'exceptions': ['IOError', 'OSError', 'FileNotFoundError', 'PermissionError'],
            'imports': ''
        },
        'json': {
            'keywords': ['json.loads', 'json.dumps', 'JSONDecodeError'],
            'exceptions': ['json.JSONDecodeError', 'ValueError', 'TypeError'],
            'imports': ''
        },
        'websocket': {
            'keywords': ['await self.send', 'channel_layer', 'websocket', 'consumer'],
            'exceptions': ['ConnectionError', 'ValueError', 'TypeError'],
            'imports': ''
        },
        'graphql': {
            'keywords': ['GraphQLError', 'mutation', 'resolver', 'graphql'],
            'exceptions': ['ValidationError', 'DatabaseError', 'SecurityException'],
            'imports': 'from graphql import GraphQLError\nfrom apps.core.exceptions import SecurityException'
        },
        'background_task': {
            'keywords': ['@shared_task', 'celery', 'retry', 'task.retry'],
            'exceptions': ['DatabaseError', 'IntegrationException', 'ValueError'],
            'imports': 'from apps.core.exceptions import IntegrationException'
        }
    }

    @classmethod
    def analyze_context(cls, try_block_code: str) -> Tuple[List[str], str]:
        """
        Analyze code context to suggest specific exceptions.

        Returns:
            Tuple of (exception_list, import_statements)
        """
        exceptions_found = set()
        imports_needed = set()

        for category, config in cls.CONTEXT_PATTERNS.items():
            for keyword in config['keywords']:
                if keyword in try_block_code:
                    exceptions_found.update(config['exceptions'])
                    if config['imports']:
                        imports_needed.add(config['imports'])
                    break

        if not exceptions_found:
            exceptions_found = ['ValueError', 'TypeError', 'KeyError']

        return sorted(exceptions_found), '\n'.join(sorted(imports_needed))


class BatchExceptionFixer:
    """Batch processor for fixing generic exceptions."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.fixes_applied = 0
        self.files_modified = []

    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single file and fix generic exceptions."""
        logger.info(f"Processing: {file_path}")

        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            fixes = self._find_generic_exceptions(tree, content)

            if not fixes:
                logger.info(f"  No generic exceptions found")
                return {'status': 'clean', 'fixes': 0}

            logger.info(f"  Found {len(fixes)} generic exception(s)")

            if not self.dry_run:
                new_content = self._apply_fixes(content, fixes)
                file_path.write_text(new_content)
                self.files_modified.append(str(file_path))
                self.fixes_applied += len(fixes)
                logger.info(f"  ✅ Applied {len(fixes)} fix(es)")
            else:
                logger.info(f"  [DRY RUN] Would fix {len(fixes)} exception(s)")
                for fix in fixes:
                    logger.info(f"    Line {fix['line']}: {fix['suggested_exceptions']}")

            return {'status': 'fixed', 'fixes': len(fixes)}

        except SyntaxError as e:
            logger.error(f"  Syntax error: {e}")
            return {'status': 'error', 'error': str(e)}
        except Exception as e:
            logger.error(f"  Processing error: {e}")
            return {'status': 'error', 'error': str(e)}

    def _find_generic_exceptions(self, tree: ast.AST, content: str) -> List[Dict]:
        """Find all generic exception patterns in AST."""
        fixes = []

        class ExceptionVisitor(ast.NodeVisitor):
            def visit_ExceptHandler(self, node):
                if node.type:
                    exc_name = self._get_exc_name(node.type)
                    if exc_name == 'Exception':
                        try_code = self._extract_try_block(node)
                        suggested_exceptions, imports = ExceptionContextAnalyzer.analyze_context(try_code)

                        fixes.append({
                            'line': node.lineno,
                            'current': 'Exception',
                            'suggested_exceptions': suggested_exceptions,
                            'imports': imports,
                            'context': try_code[:100]
                        })

                self.generic_visit(node)

            def _get_exc_name(self, node):
                if isinstance(node, ast.Name):
                    return node.id
                elif isinstance(node, ast.Attribute):
                    return node.attr
                return 'Unknown'

            def _extract_try_block(self, node):
                parent = node
                while parent and not isinstance(parent, ast.Try):
                    parent = getattr(parent, 'parent', None)
                if parent:
                    return ast.unparse(parent.body) if hasattr(ast, 'unparse') else ''
                return ''

        visitor = ExceptionVisitor()
        visitor.visit(tree)
        return fixes

    def _apply_fixes(self, content: str, fixes: List[Dict]) -> str:
        """Apply fixes to file content."""
        lines = content.split('\n')

        for fix in reversed(fixes):
            line_idx = fix['line'] - 1
            if line_idx < len(lines):
                old_line = lines[line_idx]

                if 'except Exception:' in old_line:
                    new_exceptions = ', '.join(fix['suggested_exceptions'])
                    new_line = old_line.replace('except Exception:', f'except ({new_exceptions}):')
                    lines[line_idx] = new_line
                elif 'except Exception as' in old_line:
                    new_exceptions = ', '.join(fix['suggested_exceptions'])
                    var_match = re.search(r'as\s+(\w+)', old_line)
                    if var_match:
                        var_name = var_match.group(1)
                        new_line = old_line.replace(f'except Exception as {var_name}', f'except ({new_exceptions}) as {var_name}')
                        lines[line_idx] = new_line

        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Batch Exception Remediator')
    parser.add_argument('--category', choices=['middleware', 'background_tasks', 'views', 'services'], help='Category to process')
    parser.add_argument('--file', type=Path, help='Specific file to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without modifying files')
    parser.add_argument('--auto-apply', action='store_true', help='Automatically apply fixes')

    args = parser.parse_args()

    fixer = BatchExceptionFixer(dry_run=not args.auto_apply or args.dry_run)

    if args.file:
        files_to_process = [args.file]
    elif args.category:
        base_path = Path(__file__).parent.parent
        if args.category == 'middleware':
            files_to_process = list((base_path / 'apps/core/middleware').glob('*.py'))
        elif args.category == 'background_tasks':
            files_to_process = list((base_path / 'background_tasks').glob('*.py'))
        elif args.category == 'views':
            files_to_process = list(base_path.glob('apps/*/views.py'))
        elif args.category == 'services':
            files_to_process = list(base_path.glob('apps/*/services/*.py'))
    else:
        logger.error("Must specify --category or --file")
        return

    logger.info(f"Processing {len(files_to_process)} file(s)...")

    results = {}
    for file_path in files_to_process:
        result = fixer.process_file(file_path)
        results[str(file_path)] = result

    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    logger.info(f"Files processed: {len(files_to_process)}")
    logger.info(f"Files modified: {len(fixer.files_modified)}")
    logger.info(f"Total fixes applied: {fixer.fixes_applied}")
    logger.info(f"Mode: {'DRY RUN' if fixer.dry_run else 'APPLIED'}")


if __name__ == '__main__':
    main()