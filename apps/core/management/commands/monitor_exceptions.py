"""
Django Management Command: Exception Monitoring Dashboard

Provides continuous monitoring of generic exception patterns in the codebase.
Tracks remediation progress and generates weekly reports.

Usage:
    python manage.py monitor_exceptions
    python manage.py monitor_exceptions --report weekly
    python manage.py monitor_exceptions --check-compliance
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = 'Monitor generic exception handling patterns in codebase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--report',
            type=str,
            choices=['daily', 'weekly', 'monthly'],
            help='Generate periodic report'
        )
        parser.add_argument(
            '--check-compliance',
            action='store_true',
            help='Check compliance with exception handling standards'
        )
        parser.add_argument(
            '--path',
            type=str,
            default='apps',
            help='Path to monitor (default: apps)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file for report'
        )

    def handle(self, *args, **options):
        """Main command handler"""
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('🔍 Exception Monitoring Dashboard'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')

        path = options.get('path', 'apps')
        project_root = settings.BASE_DIR

        # Run scanner
        scan_results = self._run_scanner(project_root, path)

        if options.get('check_compliance'):
            self._check_compliance(scan_results)
        elif options.get('report'):
            self._generate_report(scan_results, options['report'], options.get('output'))
        else:
            self._display_dashboard(scan_results)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Monitoring complete'))

    def _run_scanner(self, project_root: Path, path: str) -> dict:
        """Run exception scanner and return results"""
        scanner_path = project_root / 'scripts' / 'exception_scanner.py'

        if not scanner_path.exists():
            self.stdout.write(self.style.ERROR(f'❌ Scanner not found: {scanner_path}'))
            sys.exit(1)

        import subprocess

        scan_dir = project_root / path
        result = subprocess.run(
            [sys.executable, str(scanner_path), '--path', str(scan_dir), '--format', 'json'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0 and result.returncode != 1:
            self.stdout.write(self.style.ERROR(f'❌ Scanner failed: {result.stderr}'))
            sys.exit(1)

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR('❌ Failed to parse scanner output'))
            sys.exit(1)

    def _display_dashboard(self, scan_results: dict):
        """Display interactive dashboard"""
        metadata = scan_results.get('metadata', {})
        stats = scan_results.get('statistics', {})

        self.stdout.write('📊 CURRENT STATUS')
        self.stdout.write('-' * 80)
        self.stdout.write(f"Total occurrences: {metadata.get('total_occurrences', 0)}")
        self.stdout.write(f"Affected files: {metadata.get('affected_files', 0)}")
        self.stdout.write('')

        self.stdout.write('🚨 BY RISK LEVEL')
        self.stdout.write('-' * 80)
        by_risk = stats.get('by_risk_level', {})
        total = sum(by_risk.values())

        for risk_level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = by_risk.get(risk_level, 0)
            percentage = (count / total * 100) if total > 0 else 0
            style = self._get_risk_style(risk_level)
            self.stdout.write(style(f"{risk_level:10s}: {count:5d} ({percentage:5.1f}%)"))

        self.stdout.write('')

        self.stdout.write('🏆 TOP 5 OFFENDERS')
        self.stdout.write('-' * 80)
        top_offenders = stats.get('top_offenders', [])[:5]
        for i, (file_path, count) in enumerate(top_offenders, 1):
            self.stdout.write(f"{i}. {file_path} ({count} occurrences)")

        self.stdout.write('')

        self._display_progress_bar(scan_results)

    def _check_compliance(self, scan_results: dict):
        """Check compliance with exception handling standards"""
        self.stdout.write('✅ COMPLIANCE CHECK')
        self.stdout.write('-' * 80)

        metadata = scan_results.get('metadata', {})
        stats = scan_results.get('statistics', {})

        total = metadata.get('total_occurrences', 0)
        critical = stats.get('by_risk_level', {}).get('CRITICAL', 0)
        high = stats.get('by_risk_level', {}).get('HIGH', 0)

        checks = [
            {
                'name': 'Zero generic exceptions',
                'condition': total == 0,
                'message': f'{total} generic exceptions remaining'
            },
            {
                'name': 'No critical security issues',
                'condition': critical == 0,
                'message': f'{critical} critical security issues found'
            },
            {
                'name': 'High priority issues < 10',
                'condition': high < 10,
                'message': f'{high} high priority issues found'
            },
            {
                'name': 'Pre-commit hooks installed',
                'condition': self._check_hooks_installed(),
                'message': 'Pre-commit hooks not installed'
            }
        ]

        passed = 0
        failed = 0

        for check in checks:
            if check['condition']:
                self.stdout.write(self.style.SUCCESS(f"✅ {check['name']}"))
                passed += 1
            else:
                self.stdout.write(self.style.ERROR(f"❌ {check['name']}: {check['message']}"))
                failed += 1

        self.stdout.write('')
        self.stdout.write(f"Passed: {passed}/{len(checks)}")

        if failed > 0:
            self.stdout.write(self.style.ERROR(f'\n⚠️  Compliance check failed: {failed} issues found'))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ All compliance checks passed!'))

    def _generate_report(self, scan_results: dict, report_type: str, output_path: str = None):
        """Generate periodic report"""
        self.stdout.write(f'📋 GENERATING {report_type.upper()} REPORT')
        self.stdout.write('-' * 80)

        report = {
            'report_type': report_type,
            'generated_at': timezone.now().isoformat(),
            'scan_results': scan_results,
            'summary': self._generate_summary(scan_results),
            'recommendations': self._generate_recommendations(scan_results)
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f'✅ Report saved to: {output_path}'))
        else:
            self.stdout.write(json.dumps(report, indent=2))

    def _generate_summary(self, scan_results: dict) -> dict:
        """Generate report summary"""
        metadata = scan_results.get('metadata', {})
        stats = scan_results.get('statistics', {})

        return {
            'total_occurrences': metadata.get('total_occurrences', 0),
            'affected_files': metadata.get('affected_files', 0),
            'by_risk_level': stats.get('by_risk_level', {}),
            'top_offenders': stats.get('top_offenders', [])[:5],
            'compliance_status': self._calculate_compliance_status(scan_results)
        }

    def _generate_recommendations(self, scan_results: dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        stats = scan_results.get('statistics', {})
        by_risk = stats.get('by_risk_level', {})

        if by_risk.get('CRITICAL', 0) > 0:
            recommendations.append('🚨 URGENT: Fix critical security issues immediately')
            recommendations.append('Run: python scripts/exception_fixer.py --path apps/peoples --auto-fix')

        if by_risk.get('HIGH', 0) > 10:
            recommendations.append('⚠️  High priority: Schedule remediation of high-risk modules')
            recommendations.append('Focus on authentication, database, and legacy API modules')

        if not self._check_hooks_installed():
            recommendations.append('📋 Install pre-commit hooks to prevent new violations')
            recommendations.append('Run: scripts/setup-git-hooks.sh')

        total = sum(by_risk.values())
        if total > 100:
            recommendations.append('🤖 Use automated fixer for bulk remediation')
            recommendations.append('Run scanner weekly to track progress')

        return recommendations if recommendations else ['✅ No critical issues found']

    def _display_progress_bar(self, scan_results: dict):
        """Display remediation progress"""
        self.stdout.write('📈 REMEDIATION PROGRESS')
        self.stdout.write('-' * 80)

        # Assuming baseline of 2353 occurrences
        baseline = 2353
        current = scan_results.get('metadata', {}).get('total_occurrences', 0)

        progress = max(0, ((baseline - current) / baseline) * 100)

        bar_length = 50
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)

        self.stdout.write(f"Progress: [{bar}] {progress:.1f}%")
        self.stdout.write(f"Remaining: {current}/{baseline} occurrences")
        self.stdout.write(f"Fixed: {baseline - current} occurrences")

    def _calculate_compliance_status(self, scan_results: dict) -> str:
        """Calculate overall compliance status"""
        metadata = scan_results.get('metadata', {})
        stats = scan_results.get('statistics', {})

        total = metadata.get('total_occurrences', 0)
        critical = stats.get('by_risk_level', {}).get('CRITICAL', 0)

        if total == 0:
            return 'COMPLIANT'
        elif critical > 0:
            return 'NON_COMPLIANT_CRITICAL'
        elif total < 100:
            return 'MOSTLY_COMPLIANT'
        else:
            return 'NON_COMPLIANT'

    def _get_risk_style(self, risk_level: str):
        """Get console style for risk level"""
        styles = {
            'CRITICAL': self.style.ERROR,
            'HIGH': self.style.WARNING,
            'MEDIUM': self.style.NOTICE,
            'LOW': self.style.SUCCESS
        }
        return styles.get(risk_level, self.style.SUCCESS)

    def _check_hooks_installed(self) -> bool:
        """Check if pre-commit hooks are installed"""
        hooks_path = settings.BASE_DIR / '.githooks' / 'pre-commit'
        git_hooks_path = settings.BASE_DIR / '.git' / 'hooks' / 'pre-commit'

        return hooks_path.exists() and git_hooks_path.exists()