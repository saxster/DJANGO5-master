"""
Monitor Encryption Health

Continuous monitoring command for encryption system health.

Checks:
- Encryption validation
- FIPS compliance
- Key rotation status
- Performance metrics
- Error rates

Usage:
    python manage.py monitor_encryption_health
    python manage.py monitor_encryption_health --alert
"""

import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.core.services.encryption_key_manager import EncryptionKeyManager
from apps.core.services.fips_validator import FIPSValidator


class Command(BaseCommand):
    help = "Monitor encryption system health"

    def add_arguments(self, parser):
        parser.add_argument(
            '--alert',
            action='store_true',
            help='Send alerts if issues detected'
        )

    def handle(self, *args, **options):
        send_alerts = options.get('alert', False)

        health_status = {
            'timestamp': timezone.now().isoformat(),
            'checks': {}
        }

        self.stdout.write("="*70)
        self.stdout.write("ENCRYPTION HEALTH MONITOR")
        self.stdout.write("="*70)
        self.stdout.write(f"Timestamp: {health_status['timestamp']}")
        self.stdout.write("")

        health_status['checks']['encryption_validation'] = \
            SecureEncryptionService.validate_encryption_setup()
        self._print_check_result('Encryption Validation', health_status['checks']['encryption_validation'])

        health_status['checks']['fips_validation'] = \
            FIPSValidator.validate_fips_mode()
        self._print_check_result('FIPS Validation', health_status['checks']['fips_validation'])

        EncryptionKeyManager.initialize()
        key_status = EncryptionKeyManager.get_key_status()
        health_status['checks']['key_rotation_needed'] = any(
            key.get('needs_rotation', False)
            for key in key_status.get('keys', [])
        )
        self._print_check_result(
            'Key Rotation Status',
            not health_status['checks']['key_rotation_needed'],
            message='OK' if not health_status['checks']['key_rotation_needed'] else 'ROTATION NEEDED'
        )

        test_data = "health_check_probe"
        start_time = time.time()
        try:
            encrypted = SecureEncryptionService.encrypt(test_data)
            decrypted = SecureEncryptionService.decrypt(encrypted)
            latency_ms = (time.time() - start_time) * 1000
            health_status['checks']['encryption_latency_ms'] = latency_ms

            latency_ok = latency_ms < 100
            self._print_check_result(
                'Encryption Performance',
                latency_ok,
                message=f'{latency_ms:.2f}ms {"(OK)" if latency_ok else "(SLOW)"}'
            )

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            health_status['checks']['encryption_latency_ms'] = None
            health_status['checks']['encryption_error'] = str(e)
            self._print_check_result('Encryption Performance', False, message=f'ERROR: {e}')

        self.stdout.write("")
        self.stdout.write("="*70)

        all_checks_passed = all(
            v for v in health_status['checks'].values()
            if isinstance(v, bool)
        )

        if all_checks_passed:
            self.stdout.write(self.style.SUCCESS("✅ ALL HEALTH CHECKS PASSED"))
        else:
            self.stdout.write(self.style.ERROR("❌ HEALTH CHECK FAILURES DETECTED"))

            if send_alerts:
                self._send_alert(health_status)

        self.stdout.write("="*70)

    def _print_check_result(self, check_name, passed, message=None):
        """Print formatted check result."""
        status_icon = '✅' if passed else '❌'
        status_text = 'PASS' if passed else 'FAIL'

        if message:
            output = f"{status_icon} {check_name}: {message}"
        else:
            output = f"{status_icon} {check_name}: {status_text}"

        if passed:
            self.stdout.write(self.style.SUCCESS(output))
        else:
            self.stdout.write(self.style.ERROR(output))

    def _send_alert(self, health_status):
        """Send alert for failed health checks."""
        import logging
        logger = logging.getLogger('django.security')

        logger.error(
            "Encryption health check failed",
            extra={'health_status': health_status}
        )

        self.stdout.write(self.style.WARNING("⚠️  Alert sent to security team"))