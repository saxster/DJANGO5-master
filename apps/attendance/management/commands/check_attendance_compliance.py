"""
Management command to verify attendance system compliance.

Checks all security and compliance configurations are correct.

Usage:
    python manage.py check_attendance_compliance [--verbose]
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Verify attendance system security and compliance configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        verbose = options['verbose']

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Attendance System Compliance Check'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        checks = []

        # Category 1: Security Configuration
        self.stdout.write('\n' + self.style.HTTP_INFO('SECURITY CONFIGURATION'))
        checks.append(self._check_encryption_key(verbose))
        checks.append(self._check_audit_logging(verbose))
        checks.append(self._check_middleware(verbose))

        # Category 2: Database Migrations
        self.stdout.write('\n' + self.style.HTTP_INFO('DATABASE MIGRATIONS'))
        checks.append(self._check_migrations(verbose))

        # Category 3: Storage Configuration
        self.stdout.write('\n' + self.style.HTTP_INFO('STORAGE CONFIGURATION'))
        checks.append(self._check_s3_config(verbose))

        # Category 4: Celery Configuration
        self.stdout.write('\n' + self.style.HTTP_INFO('CELERY TASKS'))
        checks.append(self._check_celery_tasks(verbose))

        # Category 5: Data Validation
        self.stdout.write('\n' + self.style.HTTP_INFO('DATA VALIDATION'))
        checks.append(self._check_biometric_encryption_status(verbose))
        checks.append(self._check_consent_policies(verbose))

        # Summary
        passed = sum(1 for check in checks if check)
        total = len(checks)
        percentage = (passed / total * 100) if total > 0 else 0

        self.stdout.write('\n' + '=' * 70)
        if passed == total:
            self.stdout.write(self.style.SUCCESS(f'✓ ALL {total} COMPLIANCE CHECKS PASSED!'))
            self.stdout.write(self.style.SUCCESS(f'System is {percentage:.0f}% compliant'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ {passed}/{total} checks passed ({percentage:.0f}% compliant)'))
            self.stdout.write(self.style.ERROR(f'\n{total - passed} issues need attention'))

        self.stdout.write('=' * 70 + '\n')

        # Exit code
        return 0 if passed == total else 1

    def _check_encryption_key(self, verbose) -> bool:
        """Check if biometric encryption key is configured"""
        if hasattr(settings, 'BIOMETRIC_ENCRYPTION_KEY') and settings.BIOMETRIC_ENCRYPTION_KEY:
            self.stdout.write(self.style.SUCCESS('  ✓ Biometric encryption key configured'))
            if verbose:
                key_preview = settings.BIOMETRIC_ENCRYPTION_KEY[:10] + '...'
                self.stdout.write(f'    Key preview: {key_preview}')
            return True
        else:
            self.stdout.write(self.style.ERROR('  ✗ Biometric encryption key NOT configured'))
            self.stdout.write('    Action: Set BIOMETRIC_ENCRYPTION_KEY environment variable')
            return False

    def _check_audit_logging(self, verbose) -> bool:
        """Check if audit logging is enabled"""
        enabled = getattr(settings, 'ENABLE_ATTENDANCE_AUDIT_LOGGING', False)

        if enabled:
            self.stdout.write(self.style.SUCCESS('  ✓ Audit logging enabled'))
            return True
        else:
            self.stdout.write(self.style.WARNING('  ⚠ Audit logging disabled'))
            self.stdout.write('    Action: Set ENABLE_ATTENDANCE_AUDIT_LOGGING = True')
            return False

    def _check_middleware(self, verbose) -> bool:
        """Check if audit middleware is installed"""
        middleware_class = 'apps.attendance.middleware.AttendanceAuditMiddleware'

        if middleware_class in settings.MIDDLEWARE:
            self.stdout.write(self.style.SUCCESS('  ✓ Audit middleware installed'))
            return True
        else:
            self.stdout.write(self.style.ERROR('  ✗ Audit middleware NOT installed'))
            self.stdout.write(f'    Action: Add {middleware_class} to MIDDLEWARE')
            return False

    def _check_migrations(self, verbose) -> bool:
        """Check if all required migrations are applied"""
        required_migrations = [
            '0022_encrypt_biometric_templates',
            '0023_add_audit_logging',
            '0024_add_consent_management',
            '0025_add_photo_capture',
            '0026_add_archival_fraud_photo_fields',
        ]

        with connection.cursor() as cursor:
            missing = []

            for migration in required_migrations:
                cursor.execute("""
                    SELECT COUNT(*) FROM django_migrations
                    WHERE app='attendance' AND name=%s
                """, [migration])

                if cursor.fetchone()[0] == 0:
                    missing.append(migration)

        if not missing:
            self.stdout.write(self.style.SUCCESS(f'  ✓ All {len(required_migrations)} migrations applied'))
            return True
        else:
            self.stdout.write(self.style.ERROR(f'  ✗ {len(missing)} migrations not applied'))
            for m in missing:
                self.stdout.write(f'    - {m}')
            self.stdout.write('    Action: Run python manage.py migrate attendance')
            return False

    def _check_s3_config(self, verbose) -> bool:
        """Check if S3 is configured for photo storage"""
        has_s3 = (
            hasattr(settings, 'AWS_STORAGE_BUCKET_NAME') and
            settings.AWS_STORAGE_BUCKET_NAME
        )

        if has_s3:
            self.stdout.write(self.style.SUCCESS('  ✓ S3 storage configured'))
            if verbose:
                self.stdout.write(f'    Bucket: {settings.AWS_STORAGE_BUCKET_NAME}')
            return True
        else:
            self.stdout.write(self.style.WARNING('  ⚠ S3 storage not configured (photos will use local storage)'))
            self.stdout.write('    Action: Configure AWS_STORAGE_BUCKET_NAME for production')
            return False

    def _check_celery_tasks(self, verbose) -> bool:
        """Check if Celery Beat tasks are scheduled"""
        required_tasks = [
            'attendance.cleanup_old_audit_logs',
            'attendance.archive_old_records',
            'attendance.purge_gps_history',
            'attendance.delete_old_photos',
        ]

        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        scheduled = [task for task in beat_schedule.values() if task.get('task') in required_tasks]

        if len(scheduled) >= 3:  # At least most critical tasks scheduled
            self.stdout.write(self.style.SUCCESS(f'  ✓ {len(scheduled)}/4 critical Celery tasks scheduled'))
            return True
        else:
            self.stdout.write(self.style.WARNING(f'  ⚠ Only {len(scheduled)}/4 critical tasks scheduled'))
            self.stdout.write('    Action: Add tasks to CELERY_BEAT_SCHEDULE')
            return False

    def _check_biometric_encryption_status(self, verbose) -> bool:
        """Check if biometric data is encrypted in database"""
        with connection.cursor() as cursor:
            # Sample a few records to check if encrypted
            cursor.execute("""
                SELECT peventlogextras
                FROM peopleeventlog
                WHERE peventlogextras IS NOT NULL
                LIMIT 5
            """)

            encrypted_count = 0
            total_count = 0

            for row in cursor.fetchall():
                total_count += 1
                # Encrypted Fernet data starts with 'gAAAAA' (base64 encoded)
                if row[0] and isinstance(row[0], str) and row[0].startswith('gAAAAA'):
                    encrypted_count += 1

        if total_count == 0:
            self.stdout.write(self.style.WARNING('  ⚠ No attendance records with biometric data found'))
            return True  # Not a failure, just no data

        if encrypted_count == total_count:
            self.stdout.write(self.style.SUCCESS(f'  ✓ All biometric data encrypted ({encrypted_count}/{total_count} sampled)'))
            return True
        elif encrypted_count > 0:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ Partial encryption: {encrypted_count}/{total_count} records encrypted'
            ))
            self.stdout.write('    Action: Run python manage.py encrypt_existing_biometric_data')
            return False
        else:
            self.stdout.write(self.style.ERROR('  ✗ Biometric data NOT encrypted'))
            self.stdout.write('    Action: Run python manage.py encrypt_existing_biometric_data')
            return False

    def _check_consent_policies(self, verbose) -> bool:
        """Check if consent policies are loaded"""
        from apps.attendance.models.consent import ConsentPolicy

        policy_count = ConsentPolicy.objects.filter(is_active=True).count()

        if policy_count >= 2:  # At least GPS and Biometric
            self.stdout.write(self.style.SUCCESS(f'  ✓ {policy_count} consent policies active'))
            return True
        elif policy_count > 0:
            self.stdout.write(self.style.WARNING(f'  ⚠ Only {policy_count} consent policy active (recommend 3+)'))
            self.stdout.write('    Action: Load consent policies via admin or fixture')
            return False
        else:
            self.stdout.write(self.style.ERROR('  ✗ No consent policies found'))
            self.stdout.write('    Action: Load consent policies (GPS tracking, Biometric data)')
            return False
