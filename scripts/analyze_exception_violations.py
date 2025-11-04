#!/usr/bin/env python3
"""
Exception Handling Violation Analysis

Scans codebase for generic exception handlers and generates migration report.

Usage:
    python scripts/analyze_exception_violations.py
    python scripts/analyze_exception_violations.py --top 20
    python scripts/analyze_exception_violations.py --file apps/ml_training/services/

Relates to: Ultrathink Code Review Phase 4 - CRIT-002 (336 violations)
Rule: .claude/rules.md Rule #11
"""

import os
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent

# Exception context hints
CONTEXT_MAP = {
    'database': 'DATABASE_EXCEPTIONS',
    'save()': 'DATABASE_EXCEPTIONS',
    'objects.': 'DATABASE_EXCEPTIONS',
    'requests.': 'NETWORK_EXCEPTIONS',
    'json.': 'PARSING_EXCEPTIONS',
    'open(': 'FILE_EXCEPTIONS',
    'cache.': 'CACHE_EXCEPTIONS',
}

def find_violations(file_path):
    """Find generic exception handlers."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return []

    violations = []
    for i, line in enumerate(lines, 1):
        if re.search(r'except\s+Exception(\s+as\s+\w+)?:', line):
            # Get context
            start = max(0, i - 11)
            context = ''.join(lines[start:i])

            # Suggest pattern
            suggested = 'BUSINESS_LOGIC_EXCEPTIONS'
            for hint, pattern in CONTEXT_MAP.items():
                if hint in context.lower():
                    suggested = pattern
                    break

            violations.append({
                'file': str(file_path),
                'line': i,
                'code': line.strip(),
                'suggested': suggested
            })

    return violations

def scan_codebase(path=None):
    """Scan for violations."""
    if path is None:
        path = BASE_DIR / 'apps'

    all_violations = []
    for py_file in Path(path).rglob('*.py'):
        if any(skip in str(py_file) for skip in ['__pycache__', '.pyc']):
            continue
        violations = find_violations(py_file)
        all_violations.extend(violations)

    return all_violations

def generate_report(violations, top_n=None):
    """Generate report."""
    # Group by file
    by_file = defaultdict(list)
    for v in violations:
        by_file[v['file']].append(v)

    # Sort by count
    sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)

    print("=" * 80)
    print("GENERIC EXCEPTION HANDLING VIOLATIONS REPORT")
    print("=" * 80)
    print(f"\nTotal: {len(violations)} violations across {len(by_file)} files\n")

    print(f"Top {top_n or 20} Violators:")
    print("-" * 80)
    print(f"{'Rank':<6} {'Count':<8} {'File'}")
    print("-" * 80)

    for rank, (file, file_viol) in enumerate(sorted_files[:(top_n or 20)], 1):
        short = file.replace(str(BASE_DIR) + '/', '')
        print(f"{rank:<6} {len(file_viol):<8} {short}")

    print("\n" + "=" * 80)
    print("RECOMMENDED FIXES")
    print("=" * 80)

    for file, file_viol in sorted_files[:5]:
        short = file.replace(str(BASE_DIR) + '/', '')
        print(f"\n📁 {short} ({len(file_viol)} violations)")
        print("-" * 60)

        for v in file_viol[:3]:
            print(f"\nLine {v['line']}: {v['code']}")
            print(f"  Suggested: {v['suggested']}")
            print(f"  Fix: from apps.core.exceptions.patterns import {v['suggested']}")

if __name__ == '__main__':
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else None
    violations = scan_codebase(path)
    generate_report(violations, top_n=20)
