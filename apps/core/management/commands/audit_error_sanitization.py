"""
Error Sanitization Compliance Audit Command

Addresses Issue #19: Inconsistent Error Message Sanitization
Scans codebase for error response patterns and validates sanitization compliance.

Features:
- Detects error responses missing correlation IDs
- Identifies potential information disclosure in error messages
- Validates usage of ErrorResponseFactory
- Checks for DEBUG-dependent information exposure
- Generates compliance reports

Usage:
    python manage.py audit_error_sanitization
    python manage.py audit_error_sanitization --app peoples
    python manage.py audit_error_sanitization --export compliance_report.json
    python manage.py audit_error_sanitization --fix-auto

Complies with: .claude/rules.md Rule #5 (No Debug Information in Production)
"""

import re
import ast
import logging
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class ErrorSanitizationAuditor:
    """Audits code for error sanitization compliance."""

    VIOLATION_PATTERNS = [
        (r'settings\.DEBUG.*exception', 'DEBUG-dependent exception exposure'),
        (r'str\(e\)|str\(exception\).*return|response', 'Raw exception string in response'),
        (r'traceback\.format_exc\(\).*JsonResponse|HttpResponse', 'Stack trace in response'),
        (r'JsonResponse.*(?!correlation_id)', 'Missing correlation ID in error response'),
        (r'raise.*Exception\(', 'Generic Exception raised'),
        (r'exc_info=True.*(?!logger)', 'exc_info without proper logging'),
    ]

    REQUIRED_PATTERNS = [
        (r'correlation_id', 'Correlation ID usage'),
        (r'LogSanitizationService\.sanitize_message', 'Message sanitization'),
        (r'ErrorResponseFactory\.create_', 'ErrorResponseFactory usage'),
    ]

    def __init__(self):
        self.findings = defaultdict(list)
        self.stats = {
            'total_files': 0,
            'files_with_violations': 0,
            'total_violations': 0,
            'critical_violations': 0,
            'files_using_factory': 0,
            'files_with_correlation_ids': 0,
        }

    def audit_path(self, base_path: Path, app_label: str = None) -> Dict[str, Any]:
        """Audit path for error sanitization compliance."""
        if app_label:
            scan_path = base_path / 'apps' / app_label
        else:
            scan_path = base_path / 'apps'

        python_files = list(scan_path.rglob('*.py'))

        for file_path in python_files:
            if self._should_skip_file(file_path):
                continue

            self.stats['total_files'] += 1
            self._audit_file(file_path)

        return {
            'findings': dict(self.findings),
            'stats': self.stats,
            'timestamp': timezone.now().isoformat(),
        }

    def _should_skip_file(self, file_path: Path) -> bool:
        """Determine if file should be skipped."""
        skip_patterns = ['migrations/', 'tests/', '__pycache__', 'conftest.py']
        return any(pattern in str(file_path) for pattern in skip_patterns)

    def _audit_file(self, file_path: Path):
        """Audit a single file for error sanitization compliance."""
        try:
            content = file_path.read_text(encoding='utf-8')
        except (IOError, UnicodeDecodeError) as e:
            logger.warning(f"Could not read file {file_path}: {type(e).__name__}")
            return

        relative_path = str(file_path)
        file_violations = []

        for pattern, description in self.VIOLATION_PATTERNS:
            matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                file_violations.append({
                    'type': 'violation',
                    'severity': self._get_severity(description),
                    'line': line_num,
                    'pattern': description,
                    'code_snippet': self._get_code_snippet(content, line_num),
                })
                self.stats['total_violations'] += 1

                if 'DEBUG' in description or 'Stack trace' in description:
                    self.stats['critical_violations'] += 1

        if 'ErrorResponseFactory' in content:
            self.stats['files_using_factory'] += 1

        if 'correlation_id' in content:
            self.stats['files_with_correlation_ids'] += 1

        if file_violations:
            self.findings[relative_path] = file_violations
            self.stats['files_with_violations'] += 1

    def _get_severity(self, description: str) -> str:
        """Determine severity based on violation description."""
        critical_keywords = ['DEBUG', 'Stack trace', 'traceback']
        high_keywords = ['exception', 'Raw exception']
        medium_keywords = ['correlation_id', 'Generic']

        desc_lower = description.lower()

        if any(kw.lower() in desc_lower for kw in critical_keywords):
            return 'CRITICAL'
        elif any(kw.lower() in desc_lower for kw in high_keywords):
            return 'HIGH'
        elif any(kw.lower() in desc_lower for kw in medium_keywords):
            return 'MEDIUM'
        else:
            return 'LOW'

    def _get_code_snippet(self, content: str, line_num: int, context_lines: int = 2) -> str:
        """Extract code snippet around the violation line."""
        lines = content.split('\n')
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)

        snippet_lines = []
        for i in range(start, end):
            prefix = '>>>' if i == line_num - 1 else '   '
            snippet_lines.append(f"{prefix} {i+1:4d} | {lines[i]}")

        return '\n'.join(snippet_lines)


class Command(BaseCommand):
    help = 'Audit error sanitization compliance across codebase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            help='Audit specific app only'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export report to JSON file'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed code snippets'
        )
        parser.add_argument(
            '--critical-only',
            action='store_true',
            help='Show only critical violations'
        )

    def handle(self, *args, **options):
        app_label = options.get('app')
        export_path = options.get('export')
        verbose = options.get('verbose')
        critical_only = options.get('critical_only')

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('🔒 ERROR SANITIZATION COMPLIANCE AUDIT'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')

        auditor = ErrorSanitizationAuditor()

        try:
            results = auditor.audit_path(Path(settings.BASE_DIR), app_label)
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f'❌ Audit failed: {type(e).__name__}: {str(e)}'))
            return

        self._display_summary(results['stats'])
        self._display_findings(results['findings'], verbose, critical_only)

        if export_path:
            self._export_results(results, export_path)

        self._display_recommendations(results)

        compliance_score = self._calculate_compliance_score(results['stats'])
        self.stdout.write('')
        self.stdout.write(self._get_compliance_status(compliance_score))

    def _display_summary(self, stats: Dict[str, int]):
        """Display audit statistics summary."""
        self.stdout.write(self.style.WARNING('📊 COMPLIANCE SUMMARY'))
        self.stdout.write('-' * 80)
        self.stdout.write(f"Files Analyzed:               {stats['total_files']}")
        self.stdout.write(f"Files with Violations:        {stats['files_with_violations']}")
        self.stdout.write(f"Total Violations:             {stats['total_violations']}")
        self.stdout.write(f"Critical Violations:          {stats['critical_violations']}")
        self.stdout.write(f"Files Using Factory:          {stats['files_using_factory']}")
        self.stdout.write(f"Files with Correlation IDs:   {stats['files_with_correlation_ids']}")
        self.stdout.write('')

    def _display_findings(self, findings: Dict[str, List], verbose: bool, critical_only: bool):
        """Display detailed findings."""
        if not findings:
            self.stdout.write(self.style.SUCCESS('✅ No violations found!'))
            return

        self.stdout.write(self.style.WARNING('🔎 VIOLATION DETAILS'))
        self.stdout.write('-' * 80)

        critical = []
        high = []
        medium = []
        low = []

        for file_path, violations in findings.items():
            for violation in violations:
                item = (file_path, violation)
                if violation['severity'] == 'CRITICAL':
                    critical.append(item)
                elif violation['severity'] == 'HIGH':
                    high.append(item)
                elif violation['severity'] == 'MEDIUM':
                    medium.append(item)
                else:
                    low.append(item)

        for severity_list, label, style_func in [
            (critical, '🔴 CRITICAL', self.style.ERROR),
            (high, '🟠 HIGH', self.style.WARNING),
            (medium, '🟡 MEDIUM', self.style.WARNING),
            (low, '⚪ LOW', self.style.NOTICE),
        ]:
            if critical_only and label != '🔴 CRITICAL':
                continue

            if severity_list:
                self.stdout.write('')
                self.stdout.write(style_func(f'{label} ({len(severity_list)} violations)'))
                for file_path, violation in severity_list[:10]:
                    self.stdout.write(f"\n{file_path}:{violation['line']}")
                    self.stdout.write(f"  {violation['pattern']}")
                    if verbose:
                        self.stdout.write(f"\n{violation['code_snippet']}\n")

                if len(severity_list) > 10:
                    self.stdout.write(f"\n... and {len(severity_list) - 10} more {label} violations")

    def _export_results(self, results: Dict, export_path: str):
        """Export results to JSON file."""
        import json
        with open(export_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        self.stdout.write(self.style.SUCCESS(f'✅ Results exported to {export_path}'))

    def _calculate_compliance_score(self, stats: Dict[str, int]) -> float:
        """Calculate compliance score (0-100)."""
        if stats['total_files'] == 0:
            return 100.0

        violations_penalty = (stats['total_violations'] / stats['total_files']) * 20
        critical_penalty = stats['critical_violations'] * 10
        factory_bonus = (stats['files_using_factory'] / stats['total_files']) * 30
        correlation_bonus = (stats['files_with_correlation_ids'] / stats['total_files']) * 20

        score = 100 - violations_penalty - critical_penalty + factory_bonus + correlation_bonus
        return max(0, min(100, score))

    def _get_compliance_status(self, score: float) -> str:
        """Get styled compliance status message."""
        if score >= 90:
            return self.style.SUCCESS(f'✅ COMPLIANCE STATUS: EXCELLENT ({score:.1f}/100)')
        elif score >= 70:
            return self.style.WARNING(f'⚠️  COMPLIANCE STATUS: GOOD ({score:.1f}/100)')
        elif score >= 50:
            return self.style.WARNING(f'🟡 COMPLIANCE STATUS: NEEDS IMPROVEMENT ({score:.1f}/100)')
        else:
            return self.style.ERROR(f'❌ COMPLIANCE STATUS: CRITICAL ({score:.1f}/100)')

    def _display_recommendations(self, results: Dict):
        """Display actionable recommendations."""
        stats = results['stats']

        self.stdout.write('')
        self.stdout.write(self.style.WARNING('💡 RECOMMENDATIONS'))
        self.stdout.write('-' * 80)

        if stats['critical_violations'] > 0:
            self.stdout.write(self.style.ERROR(
                f'🔴 URGENT: Fix {stats["critical_violations"]} critical violations immediately'
            ))
            self.stdout.write('   These expose internal system details and pose security risks')

        if stats['files_using_factory'] < stats['total_files'] * 0.5:
            self.stdout.write(self.style.WARNING(
                '🟡 Migrate error responses to ErrorResponseFactory for consistency'
            ))

        if stats['files_with_correlation_ids'] < stats['total_files'] * 0.7:
            self.stdout.write(self.style.WARNING(
                '🟡 Add correlation IDs to all error responses for better debugging'
            ))

        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('1. Review critical violations in detail with --verbose')
        self.stdout.write('2. Use ErrorResponseFactory for all new error responses')
        self.stdout.write('3. Ensure all error responses include correlation_id')
        self.stdout.write('4. Remove DEBUG-dependent information disclosure')