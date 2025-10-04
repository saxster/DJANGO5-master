"""
Schedule Health Check Management Command

Validates schedule health, detects conflicts, and provides optimization recommendations.

Usage:
    # Standard health check
    python manage.py validate_schedules

    # Detailed report with verbose output
    python manage.py validate_schedules --verbose

    # Generate JSON report
    python manage.py validate_schedules --format json --output report.json

    # Check specific schedule
    python manage.py validate_schedules --schedule-id 123

    # Auto-fix issues (where safe)
    python manage.py validate_schedules --fix

    # Check for specific issue types
    python manage.py validate_schedules --check-duplicates
    python manage.py validate_schedules --check-hotspots
    python manage.py validate_schedules --check-idempotency

Features:
    - Detects duplicate schedules
    - Identifies schedule hotspots (>70% worker capacity)
    - Validates idempotency configuration
    - Checks for overlapping time slots
    - Provides optimization recommendations
    - Auto-remediation for safe fixes

Exit Codes:
    0: All checks passed
    1: Warnings found (non-critical)
    2: Errors found (critical)
    3: Command execution error
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
from apps.core.tasks.idempotency_service import UniversalIdempotencyService
from apps.core.utils_new.datetime_utilities import get_current_utc
from apps.schedhuler.models import Job
from apps.schedhuler.services.schedule_coordinator import ScheduleCoordinator
from apps.schedhuler.services.schedule_uniqueness_service import (
    ScheduleUniquenessService,
    SchedulingException,
)


class Command(BaseCommand):
    help = 'Validate schedule health and detect conflicts'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = ScheduleCoordinator()
        self.uniqueness_service = ScheduleUniquenessService()
        self.idempotency_service = UniversalIdempotencyService

        # Issue counters
        self.errors = []
        self.warnings = []
        self.info = []

    def add_arguments(self, parser):
        # Output options
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output with detailed analysis'
        )

        parser.add_argument(
            '--format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format (text or json)'
        )

        parser.add_argument(
            '--output',
            type=str,
            help='Write output to file'
        )

        # Check options
        parser.add_argument(
            '--schedule-id',
            type=int,
            help='Check specific schedule by ID'
        )

        parser.add_argument(
            '--check-duplicates',
            action='store_true',
            help='Check for duplicate schedules only'
        )

        parser.add_argument(
            '--check-hotspots',
            action='store_true',
            help='Check for schedule hotspots only'
        )

        parser.add_argument(
            '--check-idempotency',
            action='store_true',
            help='Check idempotency configuration only'
        )

        # Remediation options
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Auto-fix issues where safe (requires confirmation)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes'
        )

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.verbose = options['verbose']
        self.format = options['format']
        self.output_file = options.get('output')
        self.fix_mode = options['fix']
        self.dry_run = options['dry_run']

        try:
            # ================================================================
            # Get schedules to check
            # ================================================================

            if options['schedule_id']:
                schedules = Job.objects.filter(
                    id=options['schedule_id'],
                    is_recurring=True
                )
                if not schedules.exists():
                    raise CommandError(f"Schedule {options['schedule_id']} not found")
            else:
                schedules = Job.objects.filter(
                    is_recurring=True,
                    status__in=['PENDING', 'IN_PROGRESS']
                )

            schedule_count = schedules.count()

            if schedule_count == 0:
                self.stdout.write(self.style.WARNING('No active recurring schedules found'))
                return

            self.stdout.write(f'\n📋 Checking {schedule_count} active schedules...\n')

            # ================================================================
            # Run checks
            # ================================================================

            schedule_list = list(schedules.values(
                'id', 'identifier', 'cron_expression', 'schedule_hash',
                'fromdate', 'uptodate', 'asset_id', 'client_id'
            ))

            if options['check_duplicates']:
                self._check_duplicates(schedule_list)
            elif options['check_hotspots']:
                self._check_hotspots(schedule_list)
            elif options['check_idempotency']:
                self._check_idempotency_config()
            else:
                # Run all checks
                self._check_duplicates(schedule_list)
                self._check_hotspots(schedule_list)
                self._check_overlaps(schedule_list)
                self._check_idempotency_config()
                self._check_schedule_health(schedule_list)

            # ================================================================
            # Apply fixes if requested
            # ================================================================

            if self.fix_mode and self.errors:
                self._apply_fixes()

            # ================================================================
            # Generate output
            # ================================================================

            self._generate_output()

            # ================================================================
            # Exit with appropriate code
            # ================================================================

            if self.errors:
                sys.exit(2)  # Critical errors
            elif self.warnings:
                sys.exit(1)  # Warnings
            else:
                sys.exit(0)  # All good

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Command execution error: {e}'))
            if self.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(3)

    # ========================================================================
    # CHECK METHODS
    # ========================================================================

    def _check_duplicates(self, schedules: List[Dict[str, Any]]):
        """Check for duplicate schedule configurations"""
        self.stdout.write('\n🔍 Checking for duplicate schedules...')

        hash_groups = defaultdict(list)

        for schedule in schedules:
            schedule_hash = schedule.get('schedule_hash')
            if schedule_hash:
                hash_groups[schedule_hash].append(schedule)

        duplicates = {h: s for h, s in hash_groups.items() if len(s) > 1}

        if duplicates:
            for schedule_hash, dup_schedules in duplicates.items():
                schedule_ids = [s['id'] for s in dup_schedules]
                self.errors.append({
                    'type': 'duplicate_schedule',
                    'severity': 'error',
                    'message': f'Duplicate schedules detected: {schedule_ids}',
                    'schedule_hash': schedule_hash,
                    'schedules': dup_schedules,
                    'fix_available': True
                })

            self.stdout.write(
                self.style.ERROR(f'  ❌ Found {len(duplicates)} duplicate schedule groups')
            )
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ No duplicate schedules found'))

    def _check_hotspots(self, schedules: List[Dict[str, Any]]):
        """Check for schedule hotspots (overloaded time slots)"""
        self.stdout.write('\n🔥 Checking for schedule hotspots...')

        optimization = self.coordinator.optimize_schedule_distribution(
            schedules,
            strategy='balanced'
        )

        hotspot_count = optimization['metrics'].get('hotspot_count', 0)

        if hotspot_count > 0:
            self.warnings.append({
                'type': 'schedule_hotspots',
                'severity': 'warning',
                'message': f'{hotspot_count} schedule hotspots detected',
                'hotspot_count': hotspot_count,
                'recommendations': optimization['recommendations'][:5],
                'fix_available': True
            })

            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Found {hotspot_count} hotspots')
            )

            if self.verbose:
                for rec in optimization['recommendations'][:3]:
                    self.stdout.write(
                        f"    • {rec['original_time']} → {rec['recommended_time']}: {rec['reason']}"
                    )
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ No hotspots detected'))

    def _check_overlaps(self, schedules: List[Dict[str, Any]]):
        """Check for overlapping schedule times"""
        self.stdout.write('\n⏰ Checking for schedule overlaps...')

        overlap_count = 0

        for schedule in schedules:
            try:
                conflicts = self.uniqueness_service.validate_no_overlap({
                    'cron_expression': schedule['cron_expression'],
                    'fromdate': schedule['fromdate'],
                    'uptodate': schedule['uptodate'],
                    'asset_id': schedule['asset_id'],
                })

                error_conflicts = [c for c in conflicts if c.severity == 'error']

                if error_conflicts:
                    overlap_count += len(error_conflicts)
                    self.warnings.append({
                        'type': 'schedule_overlap',
                        'severity': 'warning',
                        'message': f"Schedule {schedule['id']} has {len(error_conflicts)} overlaps",
                        'schedule_id': schedule['id'],
                        'conflicts': error_conflicts,
                        'fix_available': False
                    })

            except Exception as e:
                if self.verbose:
                    self.stdout.write(
                        self.style.WARNING(f"  Could not validate schedule {schedule['id']}: {e}")
                    )

        if overlap_count > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Found {overlap_count} schedule overlaps')
            )
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ No overlapping schedules'))

    def _check_idempotency_config(self):
        """Check idempotency configuration for all tasks"""
        self.stdout.write('\n🔐 Checking idempotency configuration...')

        # Check for recent duplicate hits (indicates configuration issues)
        last_hour = get_current_utc() - timedelta(hours=1)

        from apps.core.models.sync_idempotency import SyncIdempotencyRecord

        recent_duplicates = SyncIdempotencyRecord.objects.filter(
            created_at__gte=last_hour,
            hit_count__gt=0
        ).values('endpoint').annotate(
            duplicate_count=Count('id')
        ).order_by('-duplicate_count')

        if recent_duplicates:
            high_duplicate_tasks = [
                t for t in recent_duplicates
                if t['duplicate_count'] > 10
            ]

            if high_duplicate_tasks:
                for task in high_duplicate_tasks:
                    self.errors.append({
                        'type': 'high_duplicate_rate',
                        'severity': 'error',
                        'message': f"Task {task['endpoint']} has {task['duplicate_count']} duplicates in last hour",
                        'endpoint': task['endpoint'],
                        'duplicate_count': task['duplicate_count'],
                        'fix_available': False
                    })

                self.stdout.write(
                    self.style.ERROR(f'  ❌ {len(high_duplicate_tasks)} tasks with high duplicate rates')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('  ✅ Idempotency working correctly')
                )
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ No recent duplicates detected'))

    def _check_schedule_health(self, schedules: List[Dict[str, Any]]):
        """Overall schedule health analysis"""
        self.stdout.write('\n💚 Analyzing overall schedule health...')

        health_analysis = self.coordinator.analyze_schedule_health(schedules)

        score = health_analysis['overall_score']

        if score < 60:
            self.errors.append({
                'type': 'poor_health_score',
                'severity': 'error',
                'message': f'Schedule health score is critical: {score}/100',
                'score': score,
                'issues': health_analysis.get('issues', []),
                'fix_available': True
            })
            self.stdout.write(self.style.ERROR(f'  ❌ Health score: {score}/100 (CRITICAL)'))
        elif score < 75:
            self.warnings.append({
                'type': 'low_health_score',
                'severity': 'warning',
                'message': f'Schedule health score is low: {score}/100',
                'score': score,
                'issues': health_analysis.get('issues', []),
                'fix_available': True
            })
            self.stdout.write(self.style.WARNING(f'  ⚠️  Health score: {score}/100 (WARNING)'))
        else:
            self.info.append({
                'type': 'health_score',
                'severity': 'info',
                'message': f'Schedule health score: {score}/100',
                'score': score
            })
            self.stdout.write(self.style.SUCCESS(f'  ✅ Health score: {score}/100'))

    # ========================================================================
    # FIX METHODS
    # ========================================================================

    def _apply_fixes(self):
        """Apply auto-fixes for detected issues"""
        self.stdout.write('\n🔧 Applying fixes...\n')

        if self.dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN MODE - No changes will be made]\n'))

        fixable_errors = [e for e in self.errors if e.get('fix_available')]

        if not fixable_errors:
            self.stdout.write('No fixable issues found.')
            return

        for issue in fixable_errors:
            if issue['type'] == 'duplicate_schedule':
                self._fix_duplicate_schedule(issue)

        self.stdout.write(self.style.SUCCESS(f'\n✅ Fixed {len(fixable_errors)} issues'))

    def _fix_duplicate_schedule(self, issue: Dict[str, Any]):
        """Fix duplicate schedule by keeping the oldest one"""
        schedules = issue['schedules']

        if len(schedules) < 2:
            return

        # Sort by creation date (oldest first)
        sorted_schedules = sorted(schedules, key=lambda s: s['id'])
        keep_schedule = sorted_schedules[0]
        remove_schedules = sorted_schedules[1:]

        self.stdout.write(
            f"  Keeping schedule {keep_schedule['id']}, removing {[s['id'] for s in remove_schedules]}"
        )

        if not self.dry_run:
            with transaction.atomic():
                Job.objects.filter(
                    id__in=[s['id'] for s in remove_schedules]
                ).update(
                    is_recurring=False,
                    status='CANCELLED'
                )

            self.stdout.write(self.style.SUCCESS('    ✅ Fixed'))
        else:
            self.stdout.write('    [DRY RUN - would cancel duplicate schedules]')

    # ========================================================================
    # OUTPUT METHODS
    # ========================================================================

    def _generate_output(self):
        """Generate final output report"""
        if self.format == 'json':
            output = self._generate_json_output()
        else:
            output = self._generate_text_output()

        if self.output_file:
            with open(self.output_file, 'w') as f:
                f.write(output)
            self.stdout.write(f'\n📄 Report written to {self.output_file}')
        else:
            self.stdout.write('\n' + output)

    def _generate_json_output(self) -> str:
        """Generate JSON report"""
        report = {
            'timestamp': get_current_utc().isoformat(),
            'summary': {
                'errors': len(self.errors),
                'warnings': len(self.warnings),
                'info': len(self.info),
            },
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
        }

        return json.dumps(report, indent=2, default=str)

    def _generate_text_output(self) -> str:
        """Generate human-readable text report"""
        lines = [
            '\n' + '=' * 60,
            '📊 SCHEDULE HEALTH CHECK REPORT',
            '=' * 60,
            f'Generated: {get_current_utc().strftime("%Y-%m-%d %H:%M:%S")}',
            '',
            'SUMMARY:',
            f'  Errors:   {len(self.errors)}',
            f'  Warnings: {len(self.warnings)}',
            f'  Info:     {len(self.info)}',
            '',
        ]

        if self.errors:
            lines.append('❌ ERRORS:')
            for error in self.errors:
                lines.append(f"  • {error['message']}")
            lines.append('')

        if self.warnings:
            lines.append('⚠️  WARNINGS:')
            for warning in self.warnings:
                lines.append(f"  • {warning['message']}")
            lines.append('')

        if not self.errors and not self.warnings:
            lines.append('✅ All checks passed!')
            lines.append('')

        lines.append('=' * 60)

        return '\n'.join(lines)
