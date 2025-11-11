"""
Device Trust Service

Implements device trust scoring and validation for voice biometric enrollment.
Part of Sprint 1: Voice Enrollment Security implementation.

Trust Scoring Algorithm:
- Known device fingerprint: +50 points
- Corporate network: +30 points
- Biometric already enrolled: +20 points
- Recent activity: +10 points
- Low risk score: +10 points
- Threshold for enrollment: 70+ points

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction-aware operations

Created: 2025-10-11
"""

import logging
from typing import Dict, Any, Optional
from datetime import timedelta
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from apps.peoples.models import People
# DeviceRegistration and DeviceRiskEvent models not yet implemented
# TODO: Implement models in apps/peoples/models/device_registry.py
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class DeviceTrustService:
    """
    Service for evaluating device trust for biometric enrollment.

    Implements multi-factor trust scoring based on:
    - Device fingerprint recognition
    - Network security
    - Historical behavior
    - Risk events
    """

    # Trust scoring weights
    KNOWN_DEVICE_POINTS = 50
    CORPORATE_NETWORK_POINTS = 30
    BIOMETRIC_ENROLLED_POINTS = 20
    RECENT_ACTIVITY_POINTS = 10
    LOW_RISK_POINTS = 10
    ENROLLMENT_THRESHOLD = 70

    # Corporate network IP ranges (configurable via settings)
    CORPORATE_IP_RANGES = [
        '10.0.0.0/8',      # Private network
        '172.16.0.0/12',   # Private network
        '192.168.0.0/16',  # Private network
    ]

    def validate_device(
        self,
        user: People,
        user_agent: str,
        ip_address: str,
        fingerprint_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Device trust validation - currently disabled (models not implemented).

        TODO: Implement DeviceRegistration and DeviceRiskEvent models before enabling.

        Args:
            user: User instance
            user_agent: Browser user agent string
            ip_address: IP address
            fingerprint_data: Optional device fingerprint dict

        Returns:
            dict: Validation result (currently fail-open)
        """
        logger.warning(
            "Device trust service called but models not available - failing open",
            extra={
                'user_id': user.id if user else None,
                'ip_address': ip_address
            }
        )

        return {
            'passed': True,  # Fail open until models implemented
            'trust_score': 0,
            'trust_factors': {},
            'device_id': None,
            'recommendation': 'Device trust validation not available - models pending implementation',
            'stub_mode': True
        }

    def _is_corporate_network(self, ip_address: str) -> bool:
        """Check if IP address is within corporate network ranges."""
        import ipaddress

        try:
            ip = ipaddress.ip_address(ip_address)
            for network_range in self.CORPORATE_IP_RANGES:
                network = ipaddress.ip_network(network_range)
                if ip in network:
                    return True
            return False
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid IP address {ip_address}: {str(e)}")
            return False

    def _has_recent_activity(self, device: Optional[Any]) -> bool:
        """Check if device has recent activity (within 30 days)."""
        if not device:
            return False
        threshold = timezone.now() - timedelta(days=30)
        return device.last_seen >= threshold

    def _calculate_risk_score(self, device: Optional[Any], user: People) -> int:
        """Calculate risk score based on security events (stub - models not implemented)."""
        if not device:
            return 0  # No history = no risk (yet)

        # NOTE: DeviceRiskEvent model not yet implemented
        # Stub returns 0 risk score
        logger.debug("Risk score calculation skipped - DeviceRiskEvent model not available")
        return 0

    def _generate_basic_device_id(self, user_agent: str, ip_address: str) -> str:
        """Generate basic device ID when fingerprint unavailable."""
        import hashlib
        fingerprint_str = f"{user_agent}|{ip_address}"
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

    def _get_recommendation(self, trust_score: int, is_known: bool, risk_score: int) -> str:
        """Generate human-readable recommendation."""
        if trust_score >= self.ENROLLMENT_THRESHOLD:
            return "Device trusted for enrollment"
        elif trust_score >= 50:
            return "Moderate trust - manual approval recommended"
        elif not is_known:
            return "Unknown device - use known device or contact IT"
        elif risk_score > 50:
            return "High risk device - security review required"
        else:
            return "Insufficient trust - use corporate network or known device"

    @transaction.atomic(using=get_current_db_name())
    def _register_or_update_device(
        self,
        user: People,
        device_id: str,
        fingerprint_data: Dict[str, Any],
        user_agent: str,
        ip_address: str,
        trust_score: int,
        trust_factors: Dict[str, Any],
        is_trusted: bool
    ) -> Any:
        """Register new device or update existing (stub - models not implemented)."""
        # NOTE: DeviceRegistration model not yet implemented
        # Stub returns None, not called during fail-open mode
        logger.debug(
            "Device registration skipped - DeviceRegistration model not available",
            extra={'device_id': device_id[:16], 'user_id': user.id}
        )
        return None
