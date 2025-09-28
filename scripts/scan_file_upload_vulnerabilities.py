#!/usr/bin/env python
"""
File Upload Vulnerability Scanner

Automated scanner for detecting insecure file upload patterns across the codebase.
Enforces Rule #14 from .claude/rules.md - File Upload Security.

Usage:
    python scripts/scan_file_upload_vulnerabilities.py
    python scripts/scan_file_upload_vulnerabilities.py --detailed
    python scripts/scan_file_upload_vulnerabilities.py --json > report.json

Exit Codes:
    0: No vulnerabilities found
    1: Vulnerabilities detected
    2: Scanner error
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class Vulnerability:
    file_path: str
    line_number: int
    line_content: str
    vulnerability_type: str
    severity: str
    description: str
    remediation: str


class FileUploadVulnerabilityScanner:
    """
    Scanner for detecting insecure file upload patterns.

    Detects:
    - Hardcoded upload_to paths without callables
    - Missing filename sanitization
    - Direct request.FILES access without validation
    - Path traversal vulnerabilities
    - Missing file extension validation
    - Unsafe file write operations
    """

    VULNERABILITY_PATTERNS = {
        'hardcoded_upload_path': {
            'pattern': r"upload_to\s*=\s*['\"][^)]*['\"]",
            'exclude_pattern': r"upload_to\s*=\s*upload_|upload_to\s*=\s*.*\.generate_secure",
            'severity': 'CRITICAL',
            'description': 'Hardcoded upload_to path without sanitization callable',
            'remediation': 'Replace with secure callable: upload_to=upload_<model_name>'
        },
        'unsafe_upload_callable': {
            'pattern': r"def\s+upload[_\w]*\s*\([^)]*filename[^)]*\)",
            'check_content': r"get_valid_filename|sanitize",
            'severity': 'HIGH',
            'description': 'Upload callable missing filename sanitization',
            'remediation': 'Add: safe_filename = get_valid_filename(filename)'
        },
        'direct_files_access': {
            'pattern': r"request\.FILES\[",
            'check_content': r"SecureFileUploadService|utils\.upload|get_valid_filename",
            'severity': 'HIGH',
            'description': 'Direct request.FILES access without validation',
            'remediation': 'Use SecureFileUploadService.validate_and_process_upload()'
        },
        'unsafe_file_write': {
            'pattern': r"open\s*\([^)]*['\"]wb['\"][^)]*\)",
            'check_content': r"get_valid_filename|secure.*path|validation",
            'severity': 'CRITICAL',
            'description': 'File write operation without path validation',
            'remediation': 'Validate path with SecureFileUploadService before writing'
        },
        'path_concatenation': {
            'pattern': r"['\"][^'\"]*\/['\"].*\+.*filename|filename.*\+.*['\"][^'\"]*\/['\"]",
            'severity': 'CRITICAL',
            'description': 'Unsafe path concatenation enables path traversal',
            'remediation': 'Use os.path.join() with sanitized components'
        },
        'missing_extension_check': {
            'pattern': r"def\s+upload[_\w]*\s*\([^)]*filename[^)]*\)",
            'check_content': r"ALLOWED.*EXTENSIONS|splitext.*lower\(\)|endswith\(",
            'severity': 'MEDIUM',
            'description': 'Upload function missing file extension validation',
            'remediation': 'Add extension whitelist validation'
        }
    }

    EXCLUDE_PATTERNS = [
        r'/migrations/',
        r'/tests/',
        r'test_.*\.py$',
        r'\.git/',
        r'__pycache__',
        r'\.pyc$',
        r'/docs/',
        r'.*\.md$',
        r'/env/',
        r'/venv/',
        r'# SECURE|# ✅|SECURITY:'
    ]

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.vulnerabilities: List[Vulnerability] = []
        self.scanned_files = 0
        self.stats = defaultdict(int)

    def should_exclude(self, file_path: str) -> bool:
        """Check if file should be excluded from scanning."""
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, file_path):
                return True
        return False

    def scan_file(self, file_path: Path) -> List[Vulnerability]:
        """Scan a single file for vulnerabilities."""
        file_vulns = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for vuln_type, config in self.VULNERABILITY_PATTERNS.items():
                file_vulns.extend(
                    self._check_pattern(file_path, lines, vuln_type, config)
                )

        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: Could not scan {file_path}: {e}", file=sys.stderr)

        return file_vulns

    def _check_pattern(
        self, file_path: Path, lines: List[str], vuln_type: str, config: Dict
    ) -> List[Vulnerability]:
        """Check for specific vulnerability pattern in file."""
        vulns = []
        pattern = re.compile(config['pattern'])

        for line_num, line in enumerate(lines, 1):
            if pattern.search(line):
                if 'exclude_pattern' in config:
                    if re.search(config['exclude_pattern'], line):
                        continue

                is_vuln = True
                if 'check_content' in config:
                    context_start = max(0, line_num - 10)
                    context_end = min(len(lines), line_num + 10)
                    context = ''.join(lines[context_start:context_end])

                    if re.search(config['check_content'], context):
                        is_vuln = False

                if is_vuln:
                    self.stats[vuln_type] += 1
                    self.stats[f"severity_{config['severity']}"] += 1

                    vulns.append(Vulnerability(
                        file_path=str(file_path.relative_to(self.project_root)),
                        line_number=line_num,
                        line_content=line.strip()[:100],
                        vulnerability_type=vuln_type,
                        severity=config['severity'],
                        description=config['description'],
                        remediation=config['remediation']
                    ))

        return vulns

    def scan_project(self) -> List[Vulnerability]:
        """Scan entire project for file upload vulnerabilities."""
        print(f"🔍 Scanning project: {self.project_root}")
        print(f"📁 Searching for Python files...")

        for py_file in self.project_root.rglob('*.py'):
            if self.should_exclude(str(py_file)):
                continue

            self.scanned_files += 1
            file_vulns = self.scan_file(py_file)
            self.vulnerabilities.extend(file_vulns)

        return self.vulnerabilities

    def generate_report(self, detailed: bool = False) -> str:
        """Generate human-readable vulnerability report."""
        report_lines = []

        report_lines.append("=" * 80)
        report_lines.append("FILE UPLOAD VULNERABILITY SCAN REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Project: {self.project_root}")
        report_lines.append(f"Files Scanned: {self.scanned_files}")
        report_lines.append(f"Vulnerabilities Found: {len(self.vulnerabilities)}")
        report_lines.append("")

        if self.vulnerabilities:
            report_lines.append("SEVERITY BREAKDOWN:")
            report_lines.append(f"  🔴 CRITICAL: {self.stats.get('severity_CRITICAL', 0)}")
            report_lines.append(f"  🟠 HIGH:     {self.stats.get('severity_HIGH', 0)}")
            report_lines.append(f"  🟡 MEDIUM:   {self.stats.get('severity_MEDIUM', 0)}")
            report_lines.append(f"  🟢 LOW:      {self.stats.get('severity_LOW', 0)}")
            report_lines.append("")

            vuln_by_severity = defaultdict(list)
            for vuln in self.vulnerabilities:
                vuln_by_severity[vuln.severity].append(vuln)

            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                if severity in vuln_by_severity:
                    report_lines.append(f"\n{'=' * 80}")
                    report_lines.append(f"{severity} SEVERITY VULNERABILITIES")
                    report_lines.append(f"{'=' * 80}\n")

                    for vuln in vuln_by_severity[severity]:
                        report_lines.append(f"📍 {vuln.file_path}:{vuln.line_number}")
                        report_lines.append(f"   Type: {vuln.vulnerability_type}")
                        report_lines.append(f"   Issue: {vuln.description}")

                        if detailed:
                            report_lines.append(f"   Code: {vuln.line_content}")
                            report_lines.append(f"   Fix: {vuln.remediation}")

                        report_lines.append("")

        else:
            report_lines.append("✅ No vulnerabilities detected!")
            report_lines.append("")
            report_lines.append("All file upload patterns follow Rule #14 security guidelines.")

        report_lines.append("=" * 80)
        report_lines.append("COMPLIANCE STATUS")
        report_lines.append("=" * 80)

        if len(self.vulnerabilities) == 0:
            report_lines.append("✅ COMPLIANT with Rule #14 - File Upload Security")
        else:
            report_lines.append("❌ NON-COMPLIANT with Rule #14 - File Upload Security")
            report_lines.append(f"   {len(self.vulnerabilities)} violations must be fixed")

        return '\n'.join(report_lines)

    def generate_json_report(self) -> str:
        """Generate JSON vulnerability report for CI/CD integration."""
        return json.dumps({
            'project_root': str(self.project_root),
            'scan_timestamp': self._get_timestamp(),
            'files_scanned': self.scanned_files,
            'total_vulnerabilities': len(self.vulnerabilities),
            'severity_breakdown': {
                'critical': self.stats.get('severity_CRITICAL', 0),
                'high': self.stats.get('severity_HIGH', 0),
                'medium': self.stats.get('severity_MEDIUM', 0),
                'low': self.stats.get('severity_LOW', 0)
            },
            'vulnerabilities': [asdict(v) for v in self.vulnerabilities],
            'compliance_status': 'COMPLIANT' if len(self.vulnerabilities) == 0 else 'NON_COMPLIANT'
        }, indent=2)

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()


def main():
    parser = argparse.ArgumentParser(
        description='Scan codebase for file upload security vulnerabilities'
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed vulnerability information including code snippets'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format for CI/CD integration'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='Project root directory (default: current directory)'
    )

    args = parser.parse_args()

    try:
        project_root = Path(args.project_root).resolve()
        if not project_root.exists():
            print(f"Error: Project root does not exist: {project_root}", file=sys.stderr)
            sys.exit(2)

        scanner = FileUploadVulnerabilityScanner(project_root)

        print("🚀 Starting File Upload Security Scan...", file=sys.stderr)
        scanner.scan_project()

        if args.json:
            print(scanner.generate_json_report())
        else:
            print(scanner.generate_report(detailed=args.detailed))

        if len(scanner.vulnerabilities) > 0:
            print(f"\n⚠️  Found {len(scanner.vulnerabilities)} vulnerabilities", file=sys.stderr)
            sys.exit(1)
        else:
            print("\n✅ Security scan passed - no vulnerabilities found", file=sys.stderr)
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"\n❌ Scanner error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()