"""
Django management command for Redis TLS/SSL certificate monitoring.

PCI DSS Level 1 Compliance:
- Requirement 4.2.1: Certificate inventory and validation (mandatory from April 1, 2025)
- Track expiration dates
- Alert on approaching expiration
- Validate certificate integrity

Usage:
    python manage.py check_redis_certificates
    python manage.py check_redis_certificates --alert-days 30
    python manage.py check_redis_certificates --output json
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.core.mail import mail_admins
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check Redis TLS/SSL certificates for expiration and validity (PCI DSS compliance)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--alert-days',
            type=int,
            default=30,
            help='Alert if certificate expires within this many days (default: 30)'
        )
        parser.add_argument(
            '--output',
            choices=['text', 'json'],
            default='text',
            help='Output format'
        )
        parser.add_argument(
            '--send-email',
            action='store_true',
            help='Send email alert if certificates expiring soon'
        )
        parser.add_argument(
            '--fail-on-expiring',
            action='store_true',
            help='Exit with error code if certificates expiring within alert window'
        )

    def handle(self, *args, **options):
        alert_days = options['alert_days']
        output_format = options['output']
        send_email = options['send_email']
        fail_on_expiring = options['fail_on_expiring']

        # Check if TLS is enabled
        redis_ssl_enabled = os.environ.get('REDIS_SSL_ENABLED', 'false').lower() == 'true'

        if not redis_ssl_enabled:
            if output_format == 'json':
                self.stdout.write(json.dumps({
                    'tls_enabled': False,
                    'message': 'Redis TLS/SSL is not enabled',
                    'warning': 'PCI DSS Level 1 requires TLS encryption in production'
                }))
            else:
                self.stdout.write(self.style.WARNING('Redis TLS/SSL is not enabled'))
                self.stdout.write(
                    self.style.WARNING(
                        'PCI DSS Level 1 requires TLS 1.2+ encryption for cardholder data transmission'
                    )
                )
                self.stdout.write(
                    self.style.WARNING('Set REDIS_SSL_ENABLED=true to enable encryption')
                )
            return

        # Get certificate paths
        ssl_ca_cert = os.environ.get('REDIS_SSL_CA_CERT', '/etc/redis/tls/ca-cert.pem')
        ssl_cert = os.environ.get('REDIS_SSL_CERT', '/etc/redis/tls/redis-cert.pem')
        ssl_key = os.environ.get('REDIS_SSL_KEY', '/etc/redis/tls/redis-key.pem')

        certificates = {
            'ca_certificate': ssl_ca_cert,
            'server_certificate': ssl_cert,
            'private_key': ssl_key
        }

        # Check each certificate
        results = []
        has_critical_issues = False
        has_warnings = False

        for cert_type, cert_path in certificates.items():
            cert_info = self._check_certificate(cert_path, cert_type, alert_days)
            results.append(cert_info)

            if cert_info['status'] == 'critical':
                has_critical_issues = True
            elif cert_info['status'] == 'warning':
                has_warnings = True

        # Output results
        if output_format == 'json':
            output_data = {
                'tls_enabled': True,
                'timestamp': timezone.now().isoformat(),
                'certificates': results,
                'has_critical_issues': has_critical_issues,
                'has_warnings': has_warnings,
                'alert_threshold_days': alert_days
            }
            self.stdout.write(json.dumps(output_data, indent=2))
        else:
            self._print_text_output(results, alert_days, has_critical_issues, has_warnings)

        # Send email if requested and issues found
        if send_email and (has_critical_issues or has_warnings):
            self._send_alert_email(results, alert_days)

        # Exit with error if requested and issues found
        if fail_on_expiring and (has_critical_issues or has_warnings):
            raise CommandError('Certificate expiration issues detected')

    def _check_certificate(
        self, cert_path: str, cert_type: str, alert_days: int
    ) -> Dict[str, Any]:
        """
        Check a single certificate for expiration and validity.

        Args:
            cert_path: Path to certificate file
            cert_type: Type of certificate (for logging)
            alert_days: Alert threshold in days

        Returns:
            Dictionary with certificate check results
        """
        cert_info = {
            'type': cert_type,
            'path': cert_path,
            'exists': os.path.exists(cert_path),
            'status': 'unknown',
            'message': '',
            'days_remaining': None,
            'expiration_date': None,
            'issued_date': None,
            'issuer': None,
            'subject': None
        }

        # Check if certificate file exists
        if not cert_info['exists']:
            cert_info['status'] = 'critical'
            cert_info['message'] = f'Certificate file not found: {cert_path}'
            return cert_info

        # For private keys, just check existence (can't parse with openssl x509)
        if 'key' in cert_type.lower():
            cert_info['status'] = 'healthy'
            cert_info['message'] = 'Private key file exists'
            return cert_info

        # Parse certificate using openssl
        try:
            # Get expiration date
            expiry_result = subprocess.run(
                ['openssl', 'x509', '-in', cert_path, '-noout', '-enddate'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if expiry_result.returncode != 0:
                cert_info['status'] = 'error'
                cert_info['message'] = f'Failed to read certificate: {expiry_result.stderr}'
                return cert_info

            # Parse expiration date
            # Format: notAfter=Dec 31 23:59:59 2025 GMT
            expiry_str = expiry_result.stdout.split('=')[1].strip()
            expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
            cert_info['expiration_date'] = expiry_date.isoformat()

            # Calculate days remaining
            days_remaining = (expiry_date - datetime.now()).days
            cert_info['days_remaining'] = days_remaining

            # Get issued date
            issued_result = subprocess.run(
                ['openssl', 'x509', '-in', cert_path, '-noout', '-startdate'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if issued_result.returncode == 0:
                issued_str = issued_result.stdout.split('=')[1].strip()
                issued_date = datetime.strptime(issued_str, '%b %d %H:%M:%S %Y %Z')
                cert_info['issued_date'] = issued_date.isoformat()

            # Get subject
            subject_result = subprocess.run(
                ['openssl', 'x509', '-in', cert_path, '-noout', '-subject'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if subject_result.returncode == 0:
                cert_info['subject'] = subject_result.stdout.split('=', 1)[1].strip()

            # Get issuer
            issuer_result = subprocess.run(
                ['openssl', 'x509', '-in', cert_path, '-noout', '-issuer'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if issuer_result.returncode == 0:
                cert_info['issuer'] = issuer_result.stdout.split('=', 1)[1].strip()

            # Determine status based on days remaining
            if days_remaining < 0:
                cert_info['status'] = 'critical'
                cert_info['message'] = f'EXPIRED {abs(days_remaining)} days ago!'
            elif days_remaining <= alert_days:
                cert_info['status'] = 'warning'
                cert_info['message'] = f'Expires in {days_remaining} days'
            else:
                cert_info['status'] = 'healthy'
                cert_info['message'] = f'Valid for {days_remaining} more days'

        except subprocess.TimeoutExpired:
            cert_info['status'] = 'error'
            cert_info['message'] = 'Certificate check timed out'
        except (ValueError, TypeError, AttributeError) as e:
            cert_info['status'] = 'error'
            cert_info['message'] = f'Certificate check failed: {str(e)}'

        return cert_info

    def _print_text_output(
        self,
        results: List[Dict[str, Any]],
        alert_days: int,
        has_critical: bool,
        has_warnings: bool
    ):
        """Print human-readable text output."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('REDIS TLS/SSL CERTIFICATE STATUS (PCI DSS Level 1 Compliance)')
        self.stdout.write('=' * 80)

        for cert_info in results:
            self.stdout.write(f"\n{cert_info['type'].upper().replace('_', ' ')}")
            self.stdout.write(f"  Path: {cert_info['path']}")

            if not cert_info['exists']:
                self.stdout.write(self.style.ERROR(f"  Status: NOT FOUND"))
                continue

            if 'key' in cert_info['type'].lower():
                self.stdout.write(self.style.SUCCESS(f"  Status: EXISTS"))
                continue

            # Certificate details
            self.stdout.write(f"  Subject: {cert_info.get('subject', 'N/A')}")
            self.stdout.write(f"  Issuer: {cert_info.get('issuer', 'N/A')}")
            self.stdout.write(f"  Issued: {cert_info.get('issued_date', 'N/A')}")
            self.stdout.write(f"  Expires: {cert_info.get('expiration_date', 'N/A')}")

            # Status with color coding
            if cert_info['status'] == 'critical':
                self.stdout.write(self.style.ERROR(f"  Status: {cert_info['message']}"))
            elif cert_info['status'] == 'warning':
                self.stdout.write(self.style.WARNING(f"  Status: {cert_info['message']}"))
            elif cert_info['status'] == 'healthy':
                self.stdout.write(self.style.SUCCESS(f"  Status: {cert_info['message']}"))
            else:
                self.stdout.write(f"  Status: {cert_info['message']}")

        # Summary
        self.stdout.write('\n' + '=' * 80)
        if has_critical:
            self.stdout.write(self.style.ERROR('❌ CRITICAL ISSUES DETECTED'))
            self.stdout.write('   Action required: Renew certificates immediately')
        elif has_warnings:
            self.stdout.write(self.style.WARNING(f'⚠️  WARNINGS: Certificates expiring within {alert_days} days'))
            self.stdout.write('   Action recommended: Schedule certificate renewal')
        else:
            self.stdout.write(self.style.SUCCESS('✅ ALL CERTIFICATES HEALTHY'))

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(f'PCI DSS 4.0.1 Certificate Management Compliance: April 1, 2025 deadline')
        self.stdout.write('=' * 80 + '\n')

    def _send_alert_email(self, results: List[Dict[str, Any]], alert_days: int):
        """Send email alert for certificate expiration issues."""
        try:
            critical_certs = [r for r in results if r['status'] == 'critical']
            warning_certs = [r for r in results if r['status'] == 'warning']

            if not (critical_certs or warning_certs):
                return

            subject = '[SECURITY] Redis TLS Certificate Expiration Alert'
            if critical_certs:
                subject = '[CRITICAL] Redis TLS Certificate EXPIRED or MISSING'

            message_parts = [
                'Redis TLS/SSL Certificate Status Alert',
                '',
                f'Alert Threshold: {alert_days} days',
                f'Check Time: {timezone.now()}',
                ''
            ]

            if critical_certs:
                message_parts.extend([
                    '🚨 CRITICAL ISSUES:',
                    ''
                ])
                for cert in critical_certs:
                    message_parts.extend([
                        f"Certificate: {cert['type']}",
                        f"  Path: {cert['path']}",
                        f"  Status: {cert['message']}",
                        f"  Action: IMMEDIATE RENEWAL REQUIRED",
                        ''
                    ])

            if warning_certs:
                message_parts.extend([
                    '⚠️  WARNINGS (Expiring Soon):',
                    ''
                ])
                for cert in warning_certs:
                    message_parts.extend([
                        f"Certificate: {cert['type']}",
                        f"  Path: {cert['path']}",
                        f"  Days Remaining: {cert['days_remaining']}",
                        f"  Expiration: {cert['expiration_date']}",
                        f"  Action: Schedule renewal within {alert_days} days",
                        ''
                    ])

            message_parts.extend([
                '═' * 60,
                'PCI DSS 4.0.1 Compliance Note:',
                'Certificate inventory and validation is MANDATORY from April 1, 2025',
                '',
                'Renewal Guide: docs/infrastructure/redis-tls-certificate-renewal.md',
                'Support: Contact infrastructure team',
                '═' * 60
            ])

            message = '\n'.join(message_parts)

            mail_admins(subject, message, fail_silently=False)
            self.stdout.write(self.style.SUCCESS('Email alert sent to administrators'))

        except (ValueError, TypeError, AttributeError) as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to send email alert: {e}')
            )


    def _check_redis_connectivity_with_tls(self) -> bool:
        """
        Test Redis connectivity with TLS enabled.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            from django.core.cache import cache

            test_key = 'tls_health_check_' + str(timezone.now().timestamp())
            test_value = 'certificate_validation_test'

            cache.set(test_key, test_value, timeout=60)
            result = cache.get(test_key)

            if result == test_value:
                cache.delete(test_key)
                return True
            else:
                return False

        except CACHE_EXCEPTIONS as e:
            logger.error(f'Redis TLS connectivity test failed: {e}')
            return False
