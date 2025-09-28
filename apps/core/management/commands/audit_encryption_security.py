"""
Production Encryption Security Audit Command

Comprehensive security audit to detect and report insecure encryption usage
in the codebase. This command scans for deprecated encryption patterns and
validates compliance with .claude/rules.md Rule #2.

CRITICAL CHECKS:
- Detects usage of deprecated string_utils.encrypt/decrypt
- Identifies SecureString field usage (should be EnhancedSecureString)
- Validates all encrypted fields use approved implementations
- Generates compliance report with CVSS scoring

Usage:
    python manage.py audit_encryption_security
    python manage.py audit_encryption_security --fix
    python manage.py audit_encryption_security --report json
"""

import os
import re
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.services.secure_encryption_service import SecureEncryptionService

logger = logging.getLogger("encryption_audit")


class Command(BaseCommand):
    help = "Audit codebase for insecure encryption patterns (CVSS 7.5 vulnerability)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Generate automated fix suggestions'
        )
        parser.add_argument(
            '--report',
            type=str,
            choices=['text', 'json', 'html'],
            default='text',
            help='Output format for audit report'
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Fail with exit code 1 if any violations found'
        )

    def handle(self, *args, **options):
        self.fix_mode = options['fix']
        self.report_format = options['report']
        self.strict_mode = options['strict']

        self.stdout.write(self.style.WARNING("="*80))
        self.stdout.write(self.style.WARNING("🔒 ENCRYPTION SECURITY AUDIT"))
        self.stdout.write(self.style.WARNING("="*80))
        self.stdout.write(f"Timestamp: {datetime.now().isoformat()}")
        self.stdout.write(f"Base Path: {settings.BASE_DIR}")
        self.stdout.write("")

        audit_results = {
            'timestamp': datetime.now().isoformat(),
            'vulnerabilities': [],
            'warnings': [],
            'compliant_files': [],
            'summary': {}
        }

        self._scan_for_deprecated_imports(audit_results)
        self._scan_for_deprecated_fields(audit_results)
        self._scan_for_custom_encryption(audit_results)
        self._validate_migration_status(audit_results)
        self._generate_summary(audit_results)

        self._output_report(audit_results)

        if self.strict_mode and audit_results['vulnerabilities']:
            self.stdout.write(self.style.ERROR("\n❌ AUDIT FAILED - Vulnerabilities detected"))
            sys.exit(1)

    def _scan_for_deprecated_imports(self, results: Dict):
        """Scan for deprecated string_utils.encrypt/decrypt imports."""
        self.stdout.write("📋 Scanning for deprecated encryption imports...")

        apps_dir = Path(settings.BASE_DIR) / 'apps'
        py_files = list(apps_dir.rglob('*.py'))

        vulnerable_pattern = re.compile(
            r'from apps\.core\.utils_new\.string_utils import.*(?:encrypt|decrypt)'
        )

        for py_file in py_files:
            if 'migrations' in str(py_file) or '__pycache__' in str(py_file):
                continue

            try:
                content = py_file.read_text()
                matches = vulnerable_pattern.finditer(content)

                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    results['vulnerabilities'].append({
                        'type': 'CRITICAL',
                        'cvss_score': 7.5,
                        'rule': 'Rule #2',
                        'file': str(py_file.relative_to(settings.BASE_DIR)),
                        'line': line_num,
                        'pattern': match.group(0),
                        'message': 'Uses deprecated insecure encrypt/decrypt (zlib compression)',
                        'fix': 'Replace with: from apps.core.services.secure_encryption_service import SecureEncryptionService'
                    })
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read file {py_file}: {e}")

    def _scan_for_deprecated_fields(self, results: Dict):
        """Scan for deprecated SecureString field usage."""
        self.stdout.write("📋 Scanning for deprecated SecureString fields...")

        apps_dir = Path(settings.BASE_DIR) / 'apps'
        model_files = [
            f for f in apps_dir.rglob('*.py')
            if 'models' in str(f) and 'migrations' not in str(f)
        ]

        secure_string_pattern = re.compile(r'\b(?<!Enhanced)SecureString\(')

        for model_file in model_files:
            try:
                content = model_file.read_text()
                matches = secure_string_pattern.finditer(content)

                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    results['vulnerabilities'].append({
                        'type': 'HIGH',
                        'cvss_score': 6.5,
                        'rule': 'Rule #2',
                        'file': str(model_file.relative_to(settings.BASE_DIR)),
                        'line': line_num,
                        'pattern': 'SecureString(',
                        'message': 'Uses deprecated SecureString field (insecure zlib)',
                        'fix': 'Replace with: EnhancedSecureString (from apps.peoples.fields import EnhancedSecureString)'
                    })
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read file {model_file}: {e}")

    def _scan_for_custom_encryption(self, results: Dict):
        """Scan for custom encryption implementations without audit."""
        self.stdout.write("📋 Scanning for custom encryption implementations...")

        apps_dir = Path(settings.BASE_DIR) / 'apps'
        py_files = list(apps_dir.rglob('*.py'))

        approved_files = [
            'secure_encryption_service.py',
            'encryption_key_manager.py',
            'encryption_audit_logger.py'
        ]

        encryption_impl_pattern = re.compile(
            r'(class\s+\w*Encrypt\w*|def\s+(?:en|de)crypt\s*\()'
        )

        for py_file in py_files:
            if any(approved in str(py_file) for approved in approved_files):
                continue
            if 'test' in str(py_file) or 'migrations' in str(py_file):
                continue

            try:
                content = py_file.read_text()

                if encryption_impl_pattern.search(content):
                    if 'SECURITY AUDIT APPROVED' not in content:
                        line_num = content.count('\n', 0, encryption_impl_pattern.search(content).start()) + 1
                        results['warnings'].append({
                            'type': 'MEDIUM',
                            'rule': 'Rule #2',
                            'file': str(py_file.relative_to(settings.BASE_DIR)),
                            'line': line_num,
                            'message': 'Custom encryption implementation detected - requires security audit',
                            'action': 'Add comment: # SECURITY AUDIT APPROVED - [Date] [Auditor] or migrate to SecureEncryptionService'
                        })
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read file {py_file}: {e}")

    def _validate_migration_status(self, results: Dict):
        """Validate encrypted data migration status."""
        self.stdout.write("📋 Validating encrypted data migration status...")

        try:
            from apps.peoples.models import People
            from django.db import connection

            total_users = People.objects.count()
            if total_users == 0:
                results['summary']['migration_status'] = 'N/A - No users in database'
                return

            users_with_email = People.objects.exclude(email__isnull=True).exclude(email='').count()

            secure_count = 0
            legacy_count = 0
            plaintext_count = 0

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM people WHERE email LIKE 'FERNET_V1:%'"
                )
                secure_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM people WHERE email LIKE 'ENC_V1:%'"
                )
                legacy_count = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM people
                    WHERE email IS NOT NULL
                    AND email != ''
                    AND email NOT LIKE 'FERNET_V1:%'
                    AND email NOT LIKE 'ENC_V1:%'
                    """
                )
                plaintext_count = cursor.fetchone()[0]

            results['summary']['migration_status'] = {
                'total_users': total_users,
                'users_with_email': users_with_email,
                'secure_encrypted': secure_count,
                'legacy_encrypted': legacy_count,
                'plaintext': plaintext_count,
                'compliance_percentage': round((secure_count / users_with_email * 100) if users_with_email > 0 else 0, 2)
            }

            if legacy_count > 0 or plaintext_count > 0:
                results['warnings'].append({
                    'type': 'MEDIUM',
                    'message': f'{legacy_count + plaintext_count} records need encryption migration',
                    'action': 'Run: python manage.py migrate_secure_encryption'
                })

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Migration status validation failed: {e}")
            results['summary']['migration_status'] = f'Error: {str(e)}'

    def _generate_summary(self, results: Dict):
        """Generate summary statistics."""
        results['summary']['critical_vulnerabilities'] = len([
            v for v in results['vulnerabilities'] if v.get('type') == 'CRITICAL'
        ])
        results['summary']['high_vulnerabilities'] = len([
            v for v in results['vulnerabilities'] if v.get('type') == 'HIGH'
        ])
        results['summary']['warnings'] = len(results['warnings'])

        cvss_scores = [v.get('cvss_score', 0) for v in results['vulnerabilities']]
        results['summary']['max_cvss_score'] = max(cvss_scores) if cvss_scores else 0.0
        results['summary']['avg_cvss_score'] = round(
            sum(cvss_scores) / len(cvss_scores), 2
        ) if cvss_scores else 0.0

        total_issues = results['summary']['critical_vulnerabilities'] + \
                       results['summary']['high_vulnerabilities'] + \
                       results['summary']['warnings']

        results['summary']['overall_status'] = 'PASS' if total_issues == 0 else 'FAIL'
        results['summary']['compliance_status'] = '✅ COMPLIANT' if total_issues == 0 else '❌ NON-COMPLIANT'

    def _output_report(self, results: Dict):
        """Output audit report in requested format."""
        if self.report_format == 'json':
            self.stdout.write(json.dumps(results, indent=2))
        elif self.report_format == 'html':
            self._output_html_report(results)
        else:
            self._output_text_report(results)

    def _output_text_report(self, results: Dict):
        """Output human-readable text report."""
        self.stdout.write("\n" + "="*80)
        self.stdout.write("📊 AUDIT RESULTS SUMMARY")
        self.stdout.write("="*80)

        summary = results['summary']
        self.stdout.write(f"\n🎯 Overall Status: {summary.get('overall_status', 'UNKNOWN')}")
        self.stdout.write(f"🔒 Compliance: {summary.get('compliance_status', 'UNKNOWN')}")
        self.stdout.write(f"\n📈 Security Metrics:")
        self.stdout.write(f"   Critical Vulnerabilities: {summary.get('critical_vulnerabilities', 0)}")
        self.stdout.write(f"   High Vulnerabilities: {summary.get('high_vulnerabilities', 0)}")
        self.stdout.write(f"   Warnings: {summary.get('warnings', 0)}")
        self.stdout.write(f"   Max CVSS Score: {summary.get('max_cvss_score', 0)}")

        if results['vulnerabilities']:
            self.stdout.write(f"\n🚨 CRITICAL & HIGH VULNERABILITIES ({len(results['vulnerabilities'])})")
            self.stdout.write("="*80)
            for vuln in results['vulnerabilities']:
                self.stdout.write(f"\n[{vuln['type']}] CVSS {vuln.get('cvss_score', 'N/A')} - {vuln['file']}:{vuln['line']}")
                self.stdout.write(f"  ❌ Issue: {vuln['message']}")
                self.stdout.write(f"  📖 Rule: {vuln['rule']}")
                if self.fix_mode and 'fix' in vuln:
                    self.stdout.write(f"  ✅ Fix: {vuln['fix']}")

        if results['warnings']:
            self.stdout.write(f"\n⚠️  WARNINGS ({len(results['warnings'])})")
            self.stdout.write("="*80)
            for warning in results['warnings']:
                self.stdout.write(f"\n[{warning['type']}] {warning['message']}")
                if 'file' in warning:
                    self.stdout.write(f"  📁 File: {warning['file']}:{warning.get('line', 'N/A')}")
                if self.fix_mode and 'action' in warning:
                    self.stdout.write(f"  💡 Action: {warning['action']}")

        if 'migration_status' in summary and isinstance(summary['migration_status'], dict):
            ms = summary['migration_status']
            self.stdout.write(f"\n📊 DATA MIGRATION STATUS")
            self.stdout.write("="*80)
            self.stdout.write(f"Total Users: {ms['total_users']}")
            self.stdout.write(f"Users with Email: {ms['users_with_email']}")
            self.stdout.write(f"  ✅ Securely Encrypted: {ms['secure_encrypted']} ({ms['compliance_percentage']}%)")
            self.stdout.write(f"  ⚠️  Legacy Format: {ms['legacy_encrypted']}")
            self.stdout.write(f"  🚨 Plaintext: {ms['plaintext']}")

            if ms['compliance_percentage'] < 100:
                self.stdout.write(self.style.WARNING(
                    f"\n⚠️  Migration incomplete: {100 - ms['compliance_percentage']:.2f}% of records need migration"
                ))
                self.stdout.write("   Run: python manage.py migrate_secure_encryption")

        self.stdout.write("\n" + "="*80)
        if summary.get('overall_status') == 'PASS':
            self.stdout.write(self.style.SUCCESS("✅ AUDIT PASSED - No security violations detected"))
        else:
            self.stdout.write(self.style.ERROR("❌ AUDIT FAILED - Security violations require remediation"))
            self.stdout.write(f"\n📖 Review: .claude/rules.md Rule #2 - No Custom Encryption Without Audit")

        self.stdout.write("="*80)

    def _output_html_report(self, results: Dict):
        """Output HTML formatted report."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Encryption Security Audit Report</title>
    <style>
        body {{ font-family: monospace; margin: 20px; background: #1e1e1e; color: #d4d4d4; }}
        .header {{ background: #2d2d30; padding: 20px; border-left: 4px solid #007acc; }}
        .critical {{ color: #f48771; font-weight: bold; }}
        .high {{ color: #ff9800; }}
        .warning {{ color: #ffeb3b; }}
        .pass {{ color: #4caf50; }}
        .section {{ margin: 20px 0; padding: 15px; background: #2d2d30; }}
        .vuln {{ margin: 10px 0; padding: 10px; background: #3c1f1e; border-left: 3px solid #f48771; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Encryption Security Audit Report</h1>
        <p>Generated: {results['timestamp']}</p>
        <p>Status: <span class="{'pass' if results['summary']['overall_status'] == 'PASS' else 'critical'}">
            {results['summary']['compliance_status']}
        </span></p>
    </div>

    <div class="section">
        <h2>📊 Summary</h2>
        <p>Critical Vulnerabilities: <span class="critical">{results['summary'].get('critical_vulnerabilities', 0)}</span></p>
        <p>High Vulnerabilities: <span class="high">{results['summary'].get('high_vulnerabilities', 0)}</span></p>
        <p>Warnings: <span class="warning">{results['summary'].get('warnings', 0)}</span></p>
        <p>Max CVSS Score: {results['summary'].get('max_cvss_score', 0)}</p>
    </div>

    <div class="section">
        <h2>🚨 Vulnerabilities</h2>
        {''.join(f'<div class="vuln"><strong>[{v["type"]}]</strong> {v["file"]}:{v["line"]}<br/>Issue: {v["message"]}<br/>Fix: {v.get("fix", "See documentation")}</div>' for v in results['vulnerabilities'])}
    </div>
</body>
</html>
"""
        output_path = Path(settings.BASE_DIR) / 'encryption_audit_report.html'
        output_path.write_text(html_content)
        self.stdout.write(f"\n📄 HTML Report saved: {output_path}")