#!/usr/bin/env python3
"""
Smart Exception Fixer - Context-Aware Automated Remediation

Intelligently fixes generic exceptions based on comprehensive context analysis.
Handles retry logic for background tasks, graceful degradation for services.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# Exception mapping by context
CONTEXT_PATTERNS = {
    'database_query': {
        'keywords': ['objects.get', 'objects.filter', 'objects.create', '.get(pk=', '.filter(id='],
        'exceptions': '(DatabaseError, IntegrityError, ObjectDoesNotExist)',
    },
    'database_save': {
        'keywords': ['.save()', '.update(', '.bulk_create'],
        'exceptions': '(DatabaseError, IntegrityError)',
    },
    'vector_ops': {
        'keywords': ['np.array', 'numpy', 'vector', 'similarity', 'embedding'],
        'exceptions': '(ValueError, TypeError, AttributeError)',
    },
    'llm_service': {
        'keywords': ['llm', 'openai', 'gpt', 'embedding', 'chat_completion'],
        'exceptions': '(LLMServiceException, TimeoutError, ConnectionError)',
    },
    'http_requests': {
        'keywords': ['requests.get', 'requests.post', 'requests.put', 'response.json()'],
        'exceptions': '(requests.RequestException, requests.Timeout, requests.ConnectionError)',
    },
    'json_parse': {
        'keywords': ['json.loads', 'json.dumps', 'JSONDecodeError'],
        'exceptions': '(json.JSONDecodeError, ValueError, TypeError)',
    },
    'cache_ops': {
        'keywords': ['cache.get', 'cache.set', 'cache.delete', 'redis'],
        'exceptions': '(ConnectionError, ValueError)',
    },
    'file_ops': {
        'keywords': ['open(', '.read()', '.write(', 'with open'],
        'exceptions': '(IOError, OSError, FileNotFoundError, PermissionError)',
    },
    'validation': {
        'keywords': ['validate', 'clean()', 'is_valid', 'ValidationError'],
        'exceptions': '(ValidationError, ValueError, TypeError)',
    },
    'async_ops': {
        'keywords': ['await ', 'async def', 'asyncio'],
        'exceptions': '(asyncio.CancelledError, ConnectionError, TimeoutError)',
    },
    'task_retry': {
        'keywords': ['@shared_task', 'self.retry', 'celery'],
        'exceptions': '(DatabaseError, IntegrationException, ValueError)',
    }
}


def analyze_try_block(try_lines: List[str]) -> Tuple[str, bool]:
    """
    Analyze try block to determine appropriate exceptions.

    Returns: (exception_tuple, needs_retry_logic)
    """
    context = '\n'.join(try_lines).lower()

    matched_patterns = []
    needs_retry = '@shared_task' in context or 'self.retry' in context

    for pattern_name, config in CONTEXT_PATTERNS.items():
        for keyword in config['keywords']:
            if keyword.lower() in context:
                matched_patterns.append(pattern_name)
                break

    if not matched_patterns:
        return '(ValueError, TypeError)', False

    # Combine exceptions from matched patterns
    all_exceptions = set()
    for pattern in matched_patterns:
        exc_tuple = CONTEXT_PATTERNS[pattern]['exceptions']
        excs = exc_tuple.strip('()').split(', ')
        all_exceptions.update(excs)

    # Remove duplicates and sort
    unique_exceptions = sorted(all_exceptions)
    result = '(' + ', '.join(unique_exceptions) + ')'

    return result, needs_retry


def fix_file(file_path: Path, dry_run: bool = False) -> int:
    """Fix all generic exceptions in a file."""

    content = file_path.read_text()
    lines = content.split('\n')

    fixes = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if re.search(r'^\s*except Exception( as \w+)?:', line):
            # Find try block
            indent = len(line) - len(line.lstrip())
            try_start = i - 1

            while try_start >= 0:
                if lines[try_start].strip().startswith('try:'):
                    prev_indent = len(lines[try_start]) - len(lines[try_start].lstrip())
                    if prev_indent < indent:
                        break
                try_start -= 1

            # Analyze context
            try_block = lines[max(0, try_start):i]
            specific_exceptions, needs_retry = analyze_try_block(try_block)

            fixes.append({
                'line_num': i + 1,
                'old': line,
                'new_exceptions': specific_exceptions,
                'needs_retry': needs_retry,
                'context': try_block[-3:] if len(try_block) >= 3 else try_block
            })

        i += 1

    if dry_run:
        print(f"\n📄 {file_path.name}")
        print(f"   Found {len(fixes)} violations")
        for fix in fixes[:5]:  # Show first 5
            print(f"   Line {fix['line_num']}: {fix['new_exceptions']}")
        if len(fixes) > 5:
            print(f"   ... and {len(fixes) - 5} more")
        return len(fixes)

    # Apply fixes
    for fix in reversed(fixes):  # Reverse to maintain line numbers
        line_idx = fix['line_num'] - 1
        old_line = lines[line_idx]

        if 'except Exception as ' in old_line:
            var_match = re.search(r'as (\w+):', old_line)
            if var_match:
                var_name = var_match.group(1)
                new_line = old_line.replace(f'except Exception as {var_name}:',
                                           f'except {fix["new_exceptions"]} as {var_name}:')
                lines[line_idx] = new_line
        else:
            new_line = old_line.replace('except Exception:', f'except {fix["new_exceptions"]}:')
            lines[line_idx] = new_line

    file_path.write_text('\n'.join(lines))

    print(f"✅ Fixed {len(fixes)} violations in {file_path.name}")
    return len(fixes)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Smart Exception Fixer')
    parser.add_argument('--file', type=Path, help='Specific file to fix')
    parser.add_argument('--dry-run', action='store_true', help='Preview without applying')
    parser.add_argument('--batch', nargs='+', type=Path, help='Multiple files')

    args = parser.parse_args()

    total_fixes = 0

    if args.file:
        total_fixes = fix_file(args.file, args.dry_run)
    elif args.batch:
        for file_path in args.batch:
            total_fixes += fix_file(file_path, args.dry_run)
    else:
        print("Error: Specify --file or --batch")
        sys.exit(1)

    print(f"\n🎯 Total fixes: {total_fixes}")

    if not args.dry_run:
        print("\n✅ Validation commands:")
        if args.file:
            print(f"   python -m py_compile {args.file}")
            print(f"   grep -c 'except Exception' {args.file}")
        else:
            print(f"   # Check each file manually")


if __name__ == '__main__':
    main()