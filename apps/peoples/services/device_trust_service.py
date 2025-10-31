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
from apps.peoples.models import People, DeviceRegistration, DeviceRiskEvent
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
        Validate device trust for biometric enrollment.

        Args:
            user: User requesting enrollment
            user_agent: Browser user agent string
            ip_address: User's IP address
            fingerprint_data: Device fingerprint data (canvas, WebGL, etc.)

        Returns:
            Validation result with trust score and decision
        """
        try:
            result = {
                'passed': False,
                'trust_score': 0,
                'trust_factors': {},
                'device_id': None,
                'recommendation': '',
            }

            # Generate device ID
            if fingerprint_data:
                device_id = DeviceRegistration.generate_device_id(fingerprint_data)
            else:
                # Fallback to basic fingerprinting
                device_id = self._generate_basic_device_id(user_agent, ip_address)

            result['device_id'] = device_id

            # Check for existing device registration
            try:
                device = DeviceRegistration.objects.get(device_id=device_id)
                is_known_device = True
            except DeviceRegistration.DoesNotExist:
                device = None
                is_known_device = False

            # Calculate trust score
            trust_score = 0
            trust_factors = {}

            # Factor 1: Known device
            if is_known_device and not device.is_blocked:
                trust_score += self.KNOWN_DEVICE_POINTS
                trust_factors['known_device'] = self.KNOWN_DEVICE_POINTS
                logger.debug(f"Known device {device_id[:16]}... for user {user.id}")
            else:
                trust_factors['known_device'] = 0
                logger.debug(f"Unknown device {device_id[:16]}... for user {user.id}")

            # Factor 2: Corporate network
            if self._is_corporate_network(ip_address):
                trust_score += self.CORPORATE_NETWORK_POINTS
                trust_factors['corporate_network'] = self.CORPORATE_NETWORK_POINTS
            else:
                trust_factors['corporate_network'] = 0

            # Factor 3: Biometric already enrolled on this device
            if is_known_device and device.biometric_enrolled:
                trust_score += self.BIOMETRIC_ENROLLED_POINTS
                trust_factors['biometric_enrolled'] = self.BIOMETRIC_ENROLLED_POINTS
            else:
                trust_factors['biometric_enrolled'] = 0

            # Factor 4: Recent activity
            if is_known_device and self._has_recent_activity(device):
                trust_score += self.RECENT_ACTIVITY_POINTS
                trust_factors['recent_activity'] = self.RECENT_ACTIVITY_POINTS
            else:
                trust_factors['recent_activity'] = 0

            # Factor 5: Low risk events
            risk_score = self._calculate_risk_score(device, user)
            if risk_score < 20:  # Low risk threshold
                trust_score += self.LOW_RISK_POINTS
                trust_factors['low_risk'] = self.LOW_RISK_POINTS
            else:
                trust_factors['low_risk'] = 0

            trust_factors['risk_score'] = risk_score

            # Determine pass/fail
            passed = trust_score >= self.ENROLLMENT_THRESHOLD

            result.update({
                'passed': passed,
                'trust_score': trust_score,
                'trust_factors': trust_factors,
                'recommendation': self._get_recommendation(trust_score, is_known_device, risk_score)
            })

            # Register or update device
            if fingerprint_data:
                self._register_or_update_device(
                    user, device_id, fingerprint_data, user_agent,
                    ip_address, trust_score, trust_factors, passed
                )

            logger.info(
                f"Device trust validation for user {user.id}: "
                f"score={trust_score}, passed={passed}"
            )

            return result

        except (ValidationError, ValueError, TypeError) as e:
            logger.error(f"Validation error in device trust check: {str(e)}")
            return {
                'passed': False,
                'trust_score': 0,
                'trust_factors': {},
                'recommendation': f'Device validation error: {str(e)}'
            }
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in device trust check: {str(e)}", exc_info=True)
            # Fail securely - reject on database errors
            return {
                'passed': False,
                'trust_score': 0,
                'trust_factors': {},
                'recommendation': 'Device validation unavailable'
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

    def _has_recent_activity(self, device: DeviceRegistration) -> bool:
        """Check if device has recent activity (within 30 days)."""
        if not device:
            return False
        threshold = timezone.now() - timedelta(days=30)
        return device.last_seen >= threshold

    def _calculate_risk_score(self, device: Optional[DeviceRegistration], user: People) -> int:
        """Calculate risk score based on security events."""
        if not device:
            return 0  # No history = no risk (yet)

        # Count recent risk events (last 90 days)
        threshold = timezone.now() - timedelta(days=90)
        recent_events = DeviceRiskEvent.objects.filter(
            device=device,
            detected_at__gte=threshold,
            resolved=False
        )

        # Calculate aggregate risk score
        total_risk = sum(event.risk_score for event in recent_events)

        # Cap at 100
        return min(100, total_risk)

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
    ) -> DeviceRegistration:
        """Register new device or update existing."""
        try:
            device, created = DeviceRegistration.objects.update_or_create(
                device_id=device_id,
                defaults={
                    'user': user,
                    'device_fingerprint': fingerprint_data,
                    'user_agent': user_agent,
                    'ip_address': ip_address,
                    'trust_score': trust_score,
                    'trust_factors': trust_factors,
                    'is_trusted': is_trusted,
                    'last_seen': timezone.now(),
                }
            )

            if created:
                logger.info(f"Registered new device {device_id[:16]}... for user {user.id}")
            else:
                logger.info(f"Updated device {device_id[:16]}... for user {user.id}")

            return device

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error registering device: {str(e)}", exc_info=True)
            raise
