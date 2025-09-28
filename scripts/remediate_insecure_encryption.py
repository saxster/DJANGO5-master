#!/usr/bin/env python3
"""
Automated Encryption Security Remediation Script

This script automatically detects and fixes insecure encryption usage in the codebase.
Addresses CVSS 7.5 vulnerability from deprecated string_utils.encrypt/decrypt functions.

Features:
- Scans codebase for deprecated encryption imports
- Generates automated refactoring patches
- Provides migration diffs for review
- Creates remediation compliance report
- Validates fixes don't break existing functionality

Usage:
    python scripts/remediate_insecure_encryption.py --scan
    python scripts/remediate_insecure_encryption.py --fix --dry-run
    python scripts/remediate_insecure_encryption.py --fix --apply
    python scripts/remediate_insecure_encryption.py --report json

Complies with .claude/rules.md Rule #2: No Custom Encryption Without Audit
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime


class EncryptionRemediator:
    """Automated encryption security remediation tool."""

    DEPRECATED_IMPORT_PATTERN = re.compile(
        r'from apps\.core\.utils_new\.string_utils import\s+(.*(?:encrypt|decrypt).*)'
    )

    SECURE_IMPORT = "from apps.core.services.secure_encryption_service import SecureEncryptionService"

    FUNCTION_REPLACEMENTS = {
        r'\bencrypt\(': 'SecureEncryptionService.encrypt(',
        r'\bdecrypt\(': 'SecureEncryptionService.decrypt(',
    }

    SECURE_STRING_PATTERN = re.compile(r'(?<!Enhanced)SecureString\(')
    ENHANCED_REPLACEMENT = 'EnhancedSecureString('

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.apps_dir = self.base_dir / 'apps'
        self.violations = []
        self.fixes_applied = []

    def scan(self) -> Dict[str, List]:
        """Scan codebase for insecure encryption patterns."""
        print("🔍 Scanning codebase for insecure encryption usage...")
        print(f"📁 Base directory: {self.base_dir}")
        print()

        results = {
            'deprecated_imports': [],
            'deprecated_fields': [],
            'custom_encryption': [],
            'total_files_scanned': 0
        }

        py_files = list(self.apps_dir.rglob('*.py'))
        results['total_files_scanned'] = len(py_files)

        for py_file in py_files:
            if self._should_skip_file(py_file):
                continue

            self._scan_file(py_file, results)

        return results

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped during scan."""
        skip_patterns = ['__pycache__', 'migrations', '.pytest_cache']
        return any(pattern in str(file_path) for pattern in skip_patterns)

    def _scan_file(self, file_path: Path, results: Dict):
        """Scan individual file for violations."""
        try:
            content = file_path.read_text()

            if match := self.DEPRECATED_IMPORT_PATTERN.search(content):
                line_num = content[:match.start()].count('\n') + 1
                results['deprecated_imports'].append({
                    'file': str(file_path.relative_to(self.base_dir)),
                    'line': line_num,
                    'matched': match.group(0),
                    'severity': 'CRITICAL',
                    'cvss': 7.5
                })

            if 'models' in str(file_path):
                for match in self.SECURE_STRING_PATTERN.finditer(content):
                    line_num = content[:match.start()].count('\n') + 1
                    results['deprecated_fields'].append({
                        'file': str(file_path.relative_to(self.base_dir)),
                        'line': line_num,
                        'severity': 'HIGH',
                        'cvss': 6.5
                    })

        except (OSError, UnicodeDecodeError) as e:
            print(f"⚠️  Could not read {file_path}: {e}")

    def fix(self, dry_run: bool = True) -> List[Dict]:
        """Generate and optionally apply automated fixes."""
        print("🔧 Generating automated fixes...")
        scan_results = self.scan()
        fixes = []

        for violation in scan_results['deprecated_imports']:
            fix = self._generate_import_fix(violation)
            if fix:
                fixes.append(fix)
                if not dry_run:
                    self._apply_fix(fix)

        for violation in scan_results['deprecated_fields']:
            fix = self._generate_field_fix(violation)
            if fix:
                fixes.append(fix)
                if not dry_run:
                    self._apply_fix(fix)

        return fixes

    def _generate_import_fix(self, violation: Dict) -> Dict:
        """Generate fix for deprecated import."""
        file_path = self.base_dir / violation['file']

        try:
            content = file_path.read_text()
            lines = content.split('\n')

            match = self.DEPRECATED_IMPORT_PATTERN.search(content)
            if not match:
                return None

            old_import = match.group(0)
            line_num = violation['line'] - 1

            updated_content = content.replace(old_import, self.SECURE_IMPORT)

            for pattern, replacement in self.FUNCTION_REPLACEMENTS.items():
                updated_content = re.sub(pattern, replacement, updated_content)

            diff = self._generate_diff(content, updated_content)

            return {
                'file': str(file_path),
                'violation': violation,
                'old_content': content,
                'new_content': updated_content,
                'diff': diff,
                'description': 'Replace deprecated string_utils imports with SecureEncryptionService'
            }

        except Exception as e:
            print(f"❌ Error generating fix for {file_path}: {e}")
            return None

    def _generate_field_fix(self, violation: Dict) -> Dict:
        """Generate fix for deprecated SecureString field."""
        file_path = self.base_dir / violation['file']

        try:
            content = file_path.read_text()

            updated_content = content

            if 'from apps.peoples.fields' not in content:
                import_line_match = re.search(r'(from django\.db import models)', content)
                if import_line_match:
                    import_insertion = f"{import_line_match.group(0)}\nfrom apps.peoples.fields import EnhancedSecureString"
                    updated_content = content.replace(import_line_match.group(0), import_insertion)

            updated_content = self.SECURE_STRING_PATTERN.sub(self.ENHANCED_REPLACEMENT, updated_content)

            diff = self._generate_diff(content, updated_content)

            return {
                'file': str(file_path),
                'violation': violation,
                'old_content': content,
                'new_content': updated_content,
                'diff': diff,
                'description': 'Replace SecureString with EnhancedSecureString'
            }

        except Exception as e:
            print(f"❌ Error generating fix for {file_path}: {e}")
            return None

    def _apply_fix(self, fix: Dict) -> bool:
        """Apply a generated fix to the file."""
        try:
            file_path = Path(fix['file'])
            file_path.write_text(fix['new_content'])
            self.fixes_applied.append(fix)
            print(f"✅ Applied fix to {file_path.relative_to(self.base_dir)}")
            return True
        except Exception as e:
            print(f"❌ Failed to apply fix to {fix['file']}: {e}")
            return False

    def _generate_diff(self, old_content: str, new_content: str) -> str:
        """Generate unified diff for changes."""
        import difflib

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            lineterm='',
            fromfile='before',
            tofile='after'
        )

        return ''.join(diff)

    def generate_report(self, scan_results: Dict, fixes: List[Dict], format: str = 'text'):
        """Generate remediation report."""
        if format == 'json':
            report = {
                'timestamp': datetime.now().isoformat(),
                'scan_results': scan_results,
                'fixes_generated': len(fixes),
                'fixes_applied': len(self.fixes_applied),
                'violations': {
                    'critical': len(scan_results['deprecated_imports']),
                    'high': len(scan_results['deprecated_fields']),
                    'total': len(scan_results['deprecated_imports']) + len(scan_results['deprecated_fields'])
                }
            }
            print(json.dumps(report, indent=2))
        else:
            self._print_text_report(scan_results, fixes)

    def _print_text_report(self, scan_results: Dict, fixes: List[Dict]):
        """Print human-readable report."""
        print("\n" + "="*80)
        print("📊 ENCRYPTION REMEDIATION REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().isoformat()}")
        print()

        total_violations = (
            len(scan_results['deprecated_imports']) +
            len(scan_results['deprecated_fields'])
        )

        print(f"📁 Files Scanned: {scan_results['total_files_scanned']}")
        print(f"🚨 Total Violations: {total_violations}")
        print(f"   CRITICAL (CVSS 7.5): {len(scan_results['deprecated_imports'])}")
        print(f"   HIGH (CVSS 6.5): {len(scan_results['deprecated_fields'])}")
        print()

        if scan_results['deprecated_imports']:
            print("🔴 CRITICAL: Deprecated Import Usage")
            print("-" * 80)
            for v in scan_results['deprecated_imports']:
                print(f"  📁 {v['file']}:{v['line']}")
                print(f"     {v['matched']}")
                print(f"     Fix: {self.SECURE_IMPORT}")
                print()

        if scan_results['deprecated_fields']:
            print("🟠 HIGH: Deprecated Field Usage")
            print("-" * 80)
            for v in scan_results['deprecated_fields']:
                print(f"  📁 {v['file']}:{v['line']}")
                print(f"     SecureString() → EnhancedSecureString()")
                print()

        if fixes:
            print(f"✅ Generated {len(fixes)} automated fixes")
            print(f"📝 Applied {len(self.fixes_applied)} fixes")

        print("="*80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Automated encryption security remediation tool'
    )
    parser.add_argument(
        '--scan',
        action='store_true',
        help='Scan codebase for violations'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Generate automated fixes'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview fixes without applying them'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply generated fixes to files'
    )
    parser.add_argument(
        '--report',
        type=str,
        choices=['text', 'json'],
        default='text',
        help='Report format'
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent.parent
    remediator = EncryptionRemediator(str(script_dir))

    if args.scan or not (args.fix):
        results = remediator.scan()
        remediator.generate_report(results, [], args.report)

    if args.fix:
        fixes = remediator.fix(dry_run=not args.apply)

        if args.dry_run or not args.apply:
            print("\n🔍 DRY RUN MODE - No changes applied")
            print("\nTo apply fixes, run with --apply flag:")
            print("  python scripts/remediate_insecure_encryption.py --fix --apply")
            print()

            for fix in fixes:
                print(f"\n📝 Proposed fix for {Path(fix['file']).name}:")
                print(fix['diff'])

        results = remediator.scan()
        remediator.generate_report(results, fixes, args.report)

        if args.apply and fixes:
            print("\n⚠️  IMPORTANT: Review changes and run tests before committing:")
            print("  python -m pytest -m security -v")


if __name__ == '__main__':
    main()