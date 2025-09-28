#!/usr/bin/env python3
"""
Intelligent Exception Fixer for knowledge.py

Analyzes context and applies appropriate specific exceptions based on operation type.
Handles 39 violations in 2,721 line file efficiently.
"""

import re
from pathlib import Path

KNOWLEDGE_FILE = Path(__file__).parent.parent / 'apps/onboarding_api/services/knowledge.py'

EXCEPTION_PATTERNS = {
    # Database operations
    'database': {
        'context_keywords': ['objects.get', 'objects.filter', 'objects.create', '.save()', '.delete()'],
        'exceptions': '(DatabaseError, IntegrityError, ObjectDoesNotExist)',
        'imports_needed': True
    },
    # Vector/numpy operations
    'vector': {
        'context_keywords': ['np.array', 'numpy', 'vector', 'similarity', 'cosine'],
        'exceptions': '(ValueError, TypeError, AttributeError)',
        'imports_needed': False
    },
    # LLM/API calls
    'llm': {
        'context_keywords': ['llm', 'openai', 'requests.', 'api_call', 'embedding'],
        'exceptions': '(LLMServiceException, TimeoutError, ConnectionError)',
        'imports_needed': True
    },
    # HTTP requests
    'http': {
        'context_keywords': ['requests.get', 'requests.post', 'http', 'url'],
        'exceptions': '(requests.RequestException, requests.Timeout, requests.ConnectionError)',
        'imports_needed': False
    },
    # File operations
    'file': {
        'context_keywords': ['open(', 'read()', 'write(', 'file.'],
        'exceptions': '(IOError, OSError, FileNotFoundError)',
        'imports_needed': False
    },
    # JSON operations
    'json': {
        'context_keywords': ['json.loads', 'json.dumps'],
        'exceptions': '(json.JSONDecodeError, ValueError)',
        'imports_needed': False
    },
    # Cache operations
    'cache': {
        'context_keywords': ['cache.get', 'cache.set', 'redis'],
        'exceptions': '(ConnectionError, ValueError)',
        'imports_needed': False
    }
}


def analyze_context(try_block_lines):
    """Determine appropriate exceptions based on try block content."""
    context_text = '\n'.join(try_block_lines).lower()

    matched_exceptions = set()

    for pattern_type, config in EXCEPTION_PATTERNS.items():
        for keyword in config['context_keywords']:
            if keyword.lower() in context_text:
                matched_exceptions.add(config['exceptions'])
                break

    if not matched_exceptions:
        return '(ValueError, TypeError)'

    if len(matched_exceptions) == 1:
        return list(matched_exceptions)[0]

    all_exceptions = set()
    for exc_tuple in matched_exceptions:
        exc_list = exc_tuple.strip('()').split(', ')
        all_exceptions.update(exc_list)

    return '(' + ', '.join(sorted(all_exceptions)) + ')'


def fix_exceptions():
    """Fix all generic exceptions in knowledge.py."""

    content = KNOWLEDGE_FILE.read_text()
    lines = content.split('\n')

    fixes_applied = 0
    i = 0
    new_lines = []

    while i < len(lines):
        line = lines[i]

        # Detect generic exception pattern
        if re.search(r'except Exception( as \w+)?:', line):
            # Extract try block (look backward)
            try_start = i - 1
            indent_level = len(line) - len(line.lstrip())

            # Find try statement
            while try_start >= 0:
                if 'try:' in lines[try_start]:
                    if len(lines[try_start]) - len(lines[try_start].lstrip()) < indent_level:
                        break
                try_start -= 1

            # Extract context
            try_block = lines[try_start:i]

            # Determine specific exceptions
            specific_exceptions = analyze_context(try_block)

            # Replace generic with specific
            if 'except Exception as ' in line:
                var_match = re.search(r'except Exception as (\w+):', line)
                if var_match:
                    var_name = var_match.group(1)
                    new_line = line.replace(f'except Exception as {var_name}:',
                                           f'except {specific_exceptions} as {var_name}:')
                    new_lines.append(new_line)
                    fixes_applied += 1
                else:
                    new_lines.append(line)
            elif 'except Exception:' in line:
                new_line = line.replace('except Exception:', f'except {specific_exceptions}:')
                new_lines.append(new_line)
                fixes_applied += 1
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

        i += 1

    # Write back
    KNOWLEDGE_FILE.write_text('\n'.join(new_lines))

    print(f"✅ Fixed {fixes_applied} violations in knowledge.py")
    print(f"📁 File: {KNOWLEDGE_FILE}")
    print(f"📊 Size: {len(new_lines)} lines")

    return fixes_applied


if __name__ == '__main__':
    fixes = fix_exceptions()
    print(f"\n🎯 Total fixes applied: {fixes}")
    print(f"\n✅ Run validation:")
    print(f"   python -m py_compile {KNOWLEDGE_FILE}")
    print(f"   grep -c 'except Exception' {KNOWLEDGE_FILE}")