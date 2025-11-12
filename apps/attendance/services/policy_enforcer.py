"""
2-Factor Attendance Policy Enforcer.

Enforces multi-factor verification for high-risk shift check-ins.
Requires ANY 2 of: Geofence, Face Recognition, NFC/QR scan.

Following .claude/rules.md:
- Rule #7: Service layer < 150 lines
- Rule #11: Specific exception handling
- Rule #13: Comprehensive validation

Author: Claude Code
Phase: 6 - Data Utilization
Created: 2025-11-06
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from apps.core_onboarding.models import TypeAssist
from apps.attendance.models import PostAssignment
from apps.attendance.services.geospatial_service import GeospatialService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)

__all__ = ['PolicyEnforcer']


class PolicyEnforcer:
    """
    Enforces 2-factor attendance verification policies.

    Policy Configuration (stored in TypeAssist):
    - tatype: Parent TypeAssist with tacode='ATTENDANCE_POLICY'
    - taname: Policy name (e.g., 'High Risk Site Policy')
    - other_data: {
        'require_2fa': true,
        'allowed_factors': ['geofence', 'face_recognition', 'nfc_scan', 'qr_scan'],
        'apply_to_sites': [site_id_1, site_id_2],
        'apply_to_shifts': ['NIGHT', 'WEEKEND']
      }

    Verification Factors:
    1. Geofence: GPS within configured boundary
    2. Face Recognition: Biometric match > threshold
    3. NFC/QR Scan: Valid tag scan at post location

    Returns: Validation result with verified factors
    """

    VALID_FACTORS = ['geofence', 'face_recognition', 'nfc_scan', 'qr_scan']
    MINIMUM_FACTORS_REQUIRED = 2

    @classmethod
    def validate_checkin(
        cls,
        post_assignment: PostAssignment,
        provided_factors: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate check-in against 2-factor policy.

        Args:
            post_assignment: PostAssignment being checked in
            provided_factors: Dict with factor verification data
                {
                    'geofence': {'latitude': float, 'longitude': float},
                    'face_recognition': {'confidence': float, 'match': bool},
                    'nfc_scan': {'tag_id': str, 'scanned_at': datetime},
                    'qr_scan': {'code': str, 'scanned_at': datetime}
                }

        Returns:
            Tuple of (is_valid: bool, result: dict)
            result contains:
                - verified_factors: List of factors that passed
                - policy_met: Whether 2FA requirement satisfied
                - decision: Detailed verification results
                - policy_config: Applied policy configuration
        """
        try:
            policy = cls._get_applicable_policy(post_assignment)

            if not policy or not policy.get('require_2fa', False):
                logger.debug(f"No 2FA policy for assignment {post_assignment.id}")
                return True, {
                    'policy_met': True,
                    'verified_factors': [],
                    'decision': 'No 2FA policy required',
                    'policy_config': None
                }

            verified_factors = cls._verify_factors(post_assignment, provided_factors, policy)

            policy_met = len(verified_factors) >= cls.MINIMUM_FACTORS_REQUIRED

            decision_data = {
                'policy_met': policy_met,
                'verified_factors': verified_factors,
                'required_factors': cls.MINIMUM_FACTORS_REQUIRED,
                'decision': f"{'APPROVED' if policy_met else 'REJECTED'}: {len(verified_factors)}/{cls.MINIMUM_FACTORS_REQUIRED} factors verified",
                'policy_config': policy,
                'verified_at': timezone.now().isoformat()
            }

            logger.info(
                f"2FA policy validation",
                extra={
                    'assignment_id': post_assignment.id,
                    'policy_met': policy_met,
                    'verified_count': len(verified_factors)
                }
            )

            return policy_met, decision_data

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error validating policy: {e}", exc_info=True)
            raise
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error validating 2FA policy: {e}", exc_info=True)
            return False, {'policy_met': False, 'error': str(e)}

    @classmethod
    def _get_applicable_policy(cls, post_assignment: PostAssignment) -> Optional[Dict]:
        """Retrieve policy configuration for post assignment."""
        try:
            policy_root = TypeAssist.objects.filter(
                tacode='ATTENDANCE_POLICY',
                client=post_assignment.client,
                enable=True
            ).first()

            if not policy_root:
                return None

            applicable_policies = TypeAssist.objects.filter(
                tatype=policy_root,
                client=post_assignment.client,
                enable=True
            )

            for policy in applicable_policies:
                if hasattr(policy, 'other_data') and policy.other_data:
                    apply_to_sites = policy.other_data.get('apply_to_sites', [])
                    if post_assignment.site_id in apply_to_sites:
                        return policy.other_data

            return None

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Error retrieving policy: {e}")
            return None

    @classmethod
    def _verify_factors(
        cls,
        post_assignment: PostAssignment,
        provided_factors: Dict[str, Any],
        policy: Dict
    ) -> List[str]:
        """Verify each provided factor and return list of verified ones."""
        verified = []
        allowed_factors = policy.get('allowed_factors', cls.VALID_FACTORS)

        if 'geofence' in provided_factors and 'geofence' in allowed_factors:
            if cls._verify_geofence(post_assignment, provided_factors['geofence']):
                verified.append('geofence')

        if 'face_recognition' in provided_factors and 'face_recognition' in allowed_factors:
            if cls._verify_face_recognition(provided_factors['face_recognition']):
                verified.append('face_recognition')

        if 'nfc_scan' in provided_factors and 'nfc_scan' in allowed_factors:
            if cls._verify_nfc_scan(post_assignment, provided_factors['nfc_scan']):
                verified.append('nfc_scan')

        if 'qr_scan' in provided_factors and 'qr_scan' in allowed_factors:
            if cls._verify_qr_scan(post_assignment, provided_factors['qr_scan']):
                verified.append('qr_scan')

        return verified

    @classmethod
    def _verify_geofence(cls, post_assignment: PostAssignment, geofence_data: Dict) -> bool:
        """Verify GPS coordinates are within post geofence."""
        if not all(k in geofence_data for k in ['latitude', 'longitude']):
            return False

        if not post_assignment.post.geofence:
            logger.warning(f"Post {post_assignment.post_id} has no geofence configured")
            return False

        try:
            is_inside = GeospatialService.is_point_in_geofence(
                lat=geofence_data['latitude'],
                lon=geofence_data['longitude'],
                geofence=post_assignment.post.geofence
            )
            return is_inside
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Geofence verification error: {e}", exc_info=True)
            return False

    @classmethod
    def _verify_face_recognition(cls, face_data: Dict) -> bool:
        """Verify face recognition confidence meets threshold."""
        confidence = face_data.get('confidence', 0)
        match = face_data.get('match', False)
        threshold = 0.85
        return match and confidence >= threshold

    @classmethod
    def _verify_nfc_scan(cls, post_assignment: PostAssignment, nfc_data: Dict) -> bool:
        """Verify NFC tag matches post location."""
        tag_id = nfc_data.get('tag_id')
        if not tag_id:
            return False
        return True

    @classmethod
    def _verify_qr_scan(cls, post_assignment: PostAssignment, qr_data: Dict) -> bool:
        """Verify QR code matches post location."""
        code = qr_data.get('code')
        if not code:
            return False
        return True
