#!/usr/bin/env python3
"""
Pre-commit hook for SQL injection vulnerability detection.

This script scans staged Python files for potential SQL injection vulnerabilities
and prevents commits if critical vulnerabilities are found.
"""

import sys
import subprocess
from pathlib import Path
from typing import List

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.core.services.sql_injection_scanner import SQLInjectionScanner, SQLInjectionVulnerability


def get_staged_python_files() -> List[Path]:
    """Get list of staged Python files."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=AM'],
            capture_output=True,
            text=True,
            check=True
        )
        files = []
        for line in result.stdout.strip().split('\n'):
            if line.endswith('.py') and line:
                file_path = Path(line)
                if file_path.exists():
                    files.append(file_path)
        return files
    except subprocess.CalledProcessError:
        return []


def main():
    """Main pre-commit hook function."""
    print("🔍 Scanning for SQL injection vulnerabilities...")

    # Get staged files
    staged_files = get_staged_python_files()

    if not staged_files:
        print("✅ No Python files to scan.")
        return 0

    # Initialize scanner
    scanner = SQLInjectionScanner()
    all_vulnerabilities = []

    # Scan each staged file
    for file_path in staged_files:
        vulnerabilities = scanner.scan_file(file_path)
        all_vulnerabilities.extend(vulnerabilities)

    # Check results
    critical_vulns = [v for v in all_vulnerabilities if v.severity == 'critical']
    high_vulns = [v for v in all_vulnerabilities if v.severity == 'high']

    if critical_vulns or high_vulns:
        print(f"❌ SQL injection vulnerabilities found!")
        print(f"   Critical: {len(critical_vulns)}")
        print(f"   High: {len(high_vulns)}")
        print()

        # Show details for critical vulnerabilities
        for vuln in critical_vulns:
            print(f"🚨 CRITICAL: {vuln.file_path}:{vuln.line_number}")
            print(f"   Type: {vuln.vulnerability_type}")
            print(f"   Code: {vuln.code_snippet}")
            print(f"   Fix: {vuln.recommendation}")
            print()

        # Show details for high vulnerabilities
        for vuln in high_vulns:
            print(f"⚠️  HIGH: {vuln.file_path}:{vuln.line_number}")
            print(f"   Type: {vuln.vulnerability_type}")
            print(f"   Code: {vuln.code_snippet}")
            print(f"   Fix: {vuln.recommendation}")
            print()

        print("🔧 Please fix these vulnerabilities before committing.")
        print("💡 Use SecureSQL utilities from apps.core.utils_new.sql_security")
        return 1

    print(f"✅ No SQL injection vulnerabilities found in {len(staged_files)} files.")
    return 0


if __name__ == '__main__':
    sys.exit(main())