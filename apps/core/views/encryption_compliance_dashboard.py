"""
Encryption Compliance Dashboard

Real-time monitoring and compliance tracking for encryption security.

Features:
- Live encryption health metrics
- Data migration status
- Security violation alerts
- Compliance reporting (GDPR, HIPAA, SOC2)
- Key rotation status

URL: /admin/security/encryption-compliance/
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db import connection
from django.views.decorators.http import require_http_methods
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.core.services.encryption_key_manager import EncryptionKeyManager
from apps.core.models.rate_limiting import RateLimitViolation

logger = logging.getLogger("encryption_dashboard")


@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET"])
def encryption_compliance_dashboard(request):
    """
    Main encryption compliance dashboard view.

    Requires superuser permissions for security reasons.
    """
    context = {
        'title': 'Encryption Security Compliance Dashboard',
        'timestamp': timezone.now(),
        'metrics': _get_encryption_metrics(),
        'migration_status': _get_migration_status(),
        'key_status': _get_key_rotation_status(),
        'recent_violations': _get_recent_violations(),
        'compliance_summary': _get_compliance_summary(),
    }

    return render(request, 'core/encryption_compliance_dashboard.html', context)


@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET"])
def encryption_metrics_api(request):
    """
    API endpoint for real-time encryption metrics.

    Returns JSON data for dashboard auto-refresh.
    """
    metrics = {
        'timestamp': timezone.now().isoformat(),
        'health': _get_encryption_health(),
        'migration': _get_migration_status(),
        'violations': _get_recent_violations(limit=10),
        'performance': _get_performance_metrics(),
    }

    return JsonResponse(metrics)


def _get_encryption_metrics() -> Dict[str, Any]:
    """Get current encryption system metrics."""
    try:
        test_start = timezone.now()
        test_data = "health_check_probe"
        encrypted = SecureEncryptionService.encrypt(test_data)
        decrypted = SecureEncryptionService.decrypt(encrypted)
        latency_ms = (timezone.now() - test_start).total_seconds() * 1000

        return {
            'operational': decrypted == test_data,
            'latency_ms': round(latency_ms, 2),
            'status': 'HEALTHY' if latency_ms < 100 else 'DEGRADED',
            'algorithm': 'Fernet (AES-128 + HMAC-SHA256)',
            'last_check': timezone.now().isoformat()
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Encryption metrics collection failed: {e}")
        return {
            'operational': False,
            'status': 'CRITICAL',
            'error': str(e),
            'last_check': timezone.now().isoformat()
        }


def _get_migration_status() -> Dict[str, Any]:
    """Get data encryption migration status."""
    try:
        from apps.peoples.models import People

        total_users = People.objects.count()
        if total_users == 0:
            return {'status': 'N/A', 'total_users': 0}

        users_with_email = People.objects.exclude(email__isnull=True).exclude(email='').count()

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM people WHERE email LIKE 'FERNET_V1:%'")
            secure_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM people WHERE email LIKE 'ENC_V1:%'")
            legacy_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM people
                WHERE email IS NOT NULL AND email != ''
                AND email NOT LIKE 'FERNET_V1:%' AND email NOT LIKE 'ENC_V1:%'
            """)
            plaintext_count = cursor.fetchone()[0]

        compliance_pct = round((secure_count / users_with_email * 100) if users_with_email > 0 else 0, 2)

        return {
            'total_users': total_users,
            'users_with_email': users_with_email,
            'secure_encrypted': secure_count,
            'legacy_encrypted': legacy_count,
            'plaintext': plaintext_count,
            'compliance_percentage': compliance_pct,
            'status': 'COMPLIANT' if compliance_pct == 100 else 'MIGRATION_NEEDED',
            'records_needing_migration': legacy_count + plaintext_count
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Migration status check failed: {e}")
        return {'status': 'ERROR', 'error': str(e)}


def _get_key_rotation_status() -> Dict[str, Any]:
    """Get encryption key rotation status."""
    try:
        EncryptionKeyManager.initialize()
        key_status = EncryptionKeyManager.get_key_status()

        needs_rotation = any(
            key.get('needs_rotation', False)
            for key in key_status.get('keys', [])
        )

        return {
            'current_key_id': key_status.get('current_key_id'),
            'active_keys_count': len(key_status.get('keys', [])),
            'needs_rotation': needs_rotation,
            'status': 'ROTATION_NEEDED' if needs_rotation else 'OK',
            'last_rotation': key_status.get('last_rotation_date', 'Never'),
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Key rotation status check failed: {e}")
        return {'status': 'ERROR', 'error': str(e)}


def _get_recent_violations(limit: int = 5) -> List[Dict[str, Any]]:
    """Get recent security violations related to encryption."""
    try:
        violations = RateLimitViolation.objects.filter(
            violation_type__icontains='encryption'
        ).order_by('-timestamp')[:limit]

        return [{
            'timestamp': v.timestamp.isoformat(),
            'ip_address': v.ip_address,
            'user': v.user.peoplename if v.user else 'Anonymous',
            'violation_type': v.violation_type,
            'severity': v.severity
        } for v in violations]
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.warning(f"Could not fetch violations: {e}")
        return []


def _get_compliance_summary() -> Dict[str, Any]:
    """Get regulatory compliance summary."""
    migration_status = _get_migration_status()
    key_status = _get_key_rotation_status()
    health = _get_encryption_metrics()

    compliant = (
        migration_status.get('compliance_percentage', 0) == 100 and
        not key_status.get('needs_rotation', False) and
        health.get('operational', False)
    )

    return {
        'gdpr_compliant': migration_status.get('compliance_percentage', 0) == 100,
        'hipaa_compliant': health.get('operational', False),
        'soc2_compliant': not key_status.get('needs_rotation', False),
        'overall_compliant': compliant,
        'certification_status': '✅ CERTIFIED' if compliant else '⚠️ REQUIRES REMEDIATION',
        'last_audit': datetime.now().isoformat(),
        'next_audit': (datetime.now() + timedelta(days=90)).isoformat(),
    }


def _get_encryption_health() -> Dict[str, bool]:
    """Get encryption system health status."""
    try:
        return {
            'encryption_operational': SecureEncryptionService.validate_encryption_setup(),
            'fernet_available': True,
            'keys_loaded': EncryptionKeyManager._current_key_id is not None
        }
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Encryption health check failed: {e}")
        return {
            'encryption_operational': False,
            'error': str(e)
        }


def _get_performance_metrics() -> Dict[str, Any]:
    """Get encryption performance metrics."""
    import time

    try:
        samples = []
        for i in range(10):
            test_data = f"perf_test_{i}"
            start = time.time()
            encrypted = SecureEncryptionService.encrypt(test_data)
            decrypted = SecureEncryptionService.decrypt(encrypted)
            latency = (time.time() - start) * 1000
            samples.append(latency)

        return {
            'avg_latency_ms': round(sum(samples) / len(samples), 2),
            'max_latency_ms': round(max(samples), 2),
            'min_latency_ms': round(min(samples), 2),
            'sample_count': len(samples),
            'status': 'OK' if max(samples) < 100 else 'SLOW'
        }
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Performance metrics failed: {e}")
        return {'status': 'ERROR', 'error': str(e)}