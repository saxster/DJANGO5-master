"""
Consent Management Service

Validates employee consent for BIOMETRIC data collection ONLY.

IMPORTANT: GPS/Location services are CORE APP FUNCTIONALITY.
Users do not need to consent to GPS - by using the app, GPS is enabled.
Users who don't want GPS tracked can choose not to use the app.

This service ONLY manages consent for:
- Biometric data (face recognition templates) - Required by IL BIPA, TX CUBI, WA HB 1493
- Photo capture - May be required by some jurisdictions

Features:
- Check if employee has given required biometric consent
- Manage consent grants and revocations
- Handle state-specific requirements (IL BIPA, TX CUBI, WA)
- Send consent notifications and reminders
- Track consent lifecycle

Usage:
    from apps.attendance.services.consent_service import ConsentValidationService

    # Check if user has biometric consent (if biometric features enabled)
    can_use_biometric, missing_consents = ConsentValidationService.can_user_use_biometric_features(user)
"""

from django.db.models import Q
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from typing import List, Dict, Any, Tuple, Optional
from datetime import timedelta

from apps.attendance.models.consent import (
    ConsentPolicy,
    EmployeeConsentLog,
    ConsentRequirement
)
from apps.attendance.exceptions import AttendancePermissionError
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS
import logging

logger = logging.getLogger(__name__)


class ConsentValidationService:
    """
    Service for validating employee consent requirements.
    """

    @staticmethod
    def can_user_use_biometric_features(user) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if user has required consents for BIOMETRIC features only.

        NOTE: GPS consent is NOT required - GPS is core app functionality.
        By using the app, users implicitly accept GPS tracking.

        This ONLY checks for:
        - Biometric data collection consent (IL BIPA, TX CUBI, WA)
        - Photo capture consent (if required)
        - Face recognition consent

        Args:
            user: User attempting to use biometric features

        Returns:
            Tuple of (can_use_biometric: bool, missing_consents: list)
        """
        # Get all active requirements that apply to this user
        # Filter to BIOMETRIC-ONLY (not GPS)
        requirements = ConsentValidationService._get_user_requirements(user, biometric_only=True)

        missing_consents = []

        for requirement in requirements:
            # Check if user has active consent for this policy
            has_consent = ConsentValidationService.has_active_consent(
                user,
                requirement.policy
            )

            if not has_consent and requirement.is_mandatory:
                # Check if grace period applies
                if requirement.grace_period_days > 0:
                    # Check when user started (would need user start_date field)
                    # For now, assume grace period from policy effective date
                    grace_end = requirement.policy.effective_date + timedelta(
                        days=requirement.grace_period_days
                    )
                    if timezone.now().date() < grace_end:
                        # Still in grace period
                        continue

                # Consent is missing and mandatory
                missing_consents.append({
                    'policy_id': requirement.policy.id,
                    'policy_type': requirement.policy.policy_type,
                    'policy_title': requirement.policy.title,
                    'state': requirement.policy.state,
                    'blocks_clock_in': requirement.blocks_clock_in,
                    'requires_signature': requirement.policy.requires_signature,
                    'requires_written': requirement.policy.requires_written_consent,
                })

        # User can use biometric features only if no blocking consents are missing
        blocking_missing = [
            c for c in missing_consents if c['blocks_clock_in']
        ]

        can_use_biometric = len(blocking_missing) == 0

        return can_use_biometric, missing_consents

    @staticmethod
    def _get_user_requirements(user, biometric_only: bool = True) -> List[ConsentRequirement]:
        """
        Get all consent requirements that apply to a user.

        Args:
            user: User to check
            biometric_only: Only return biometric-related consents (default: True)

        Returns:
            List of applicable ConsentRequirement objects
        """
        # Get all active requirements
        queryset = ConsentRequirement.objects.filter(
            is_active=True,
            tenant=user.client_id if hasattr(user, 'client_id') else 'default'
        ).select_related('policy')

        # Filter to BIOMETRIC ONLY - GPS is core app functionality, no consent needed
        if biometric_only:
            queryset = queryset.exclude(
                policy__policy_type=ConsentPolicy.PolicyType.GPS_TRACKING
            )

        all_requirements = queryset

        # Filter to those that apply to this user
        applicable = [
            req for req in all_requirements
            if req.applies_to_user(user)
        ]

        return applicable

    @staticmethod
    def has_active_consent(user, policy: ConsentPolicy) -> bool:
        """
        Check if user has active consent for a policy.

        Args:
            user: User to check
            policy: ConsentPolicy to check

        Returns:
            True if user has active consent, False otherwise
        """
        try:
            consent = EmployeeConsentLog.objects.filter(
                employee=user,
                policy=policy,
                status=EmployeeConsentLog.ConsentStatus.GRANTED
            ).order_by('-granted_at').first()

            if not consent:
                return False

            # Check if consent is still active (not expired)
            return consent.is_active()

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error checking consent for user {user.id}: {e}", exc_info=True)
            return False
        except (AttributeError, TypeError) as e:
            logger.error(f"Data error checking consent for user {user.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def get_user_consents(user) -> List[EmployeeConsentLog]:
        """
        Get all consent logs for a user.

        Args:
            user: User to get consents for

        Returns:
            List of EmployeeConsentLog objects
        """
        return EmployeeConsentLog.objects.filter(
            employee=user
        ).select_related('policy').order_by('-granted_at')

    @staticmethod
    def get_pending_consents(user) -> List[Dict[str, Any]]:
        """
        Get all pending consents for a user.

        Args:
            user: User to check

        Returns:
            List of policies requiring consent
        """
        # Get requirements that apply to user
        requirements = ConsentValidationService._get_user_requirements(user)

        pending = []

        for requirement in requirements:
            # Check if user has granted consent
            if not ConsentValidationService.has_active_consent(user, requirement.policy):
                pending.append({
                    'policy': requirement.policy,
                    'requirement': requirement,
                    'is_mandatory': requirement.is_mandatory,
                    'blocks_clock_in': requirement.blocks_clock_in,
                })

        return pending


class ConsentManagementService:
    """
    Service for managing consent lifecycle.
    """

    @staticmethod
    def request_consent(user, policy: ConsentPolicy,
                       send_notification: bool = True) -> EmployeeConsentLog:
        """
        Request consent from an employee.

        Args:
            user: Employee to request consent from
            policy: Policy to request consent for
            send_notification: Whether to send email notification

        Returns:
            Created EmployeeConsentLog in PENDING status
        """
        # Check if pending consent already exists
        existing = EmployeeConsentLog.objects.filter(
            employee=user,
            policy=policy,
            status=EmployeeConsentLog.ConsentStatus.PENDING
        ).first()

        if existing:
            logger.info(f"Consent request already pending for {user.username} - {policy.policy_type}")
            return existing

        # Create new pending consent
        consent = EmployeeConsentLog.objects.create(
            employee=user,
            policy=policy,
            status=EmployeeConsentLog.ConsentStatus.PENDING,
            tenant=user.client_id if hasattr(user, 'client_id') else 'default'
        )

        logger.info(f"Consent requested from {user.username} for {policy.policy_type}")

        # Send notification
        if send_notification:
            ConsentNotificationService.send_consent_request(consent)

        return consent

    @staticmethod
    def grant_consent(
        consent_log: EmployeeConsentLog,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        signature_data: Optional[str] = None,
        signature_type: str = 'ELECTRONIC'
    ) -> EmployeeConsentLog:
        """
        Grant consent for a policy.

        Args:
            consent_log: EmployeeConsentLog to update
            ip_address: IP address where consent was granted
            user_agent: User agent string
            signature_data: Digital signature
            signature_type: Type of signature

        Returns:
            Updated EmployeeConsentLog
        """
        consent_log.grant_consent(
            ip_address=ip_address,
            user_agent=user_agent,
            signature_data=signature_data,
            signature_type=signature_type
        )

        # Send confirmation email
        ConsentNotificationService.send_consent_confirmation(consent_log)

        logger.info(f"Consent granted: {consent_log.employee.username} for {consent_log.policy.policy_type}")
        return consent_log

    @staticmethod
    def revoke_consent(
        consent_log: EmployeeConsentLog,
        reason: str,
        ip_address: Optional[str] = None
    ) -> EmployeeConsentLog:
        """
        Revoke consent.

        Args:
            consent_log: EmployeeConsentLog to revoke
            reason: Reason for revocation
            ip_address: IP address where revoked

        Returns:
            Updated EmployeeConsentLog
        """
        consent_log.revoke_consent(reason=reason, ip_address=ip_address)

        # Send revocation confirmation
        ConsentNotificationService.send_revocation_confirmation(consent_log)

        logger.info(f"Consent revoked: {consent_log.employee.username} for {consent_log.policy.policy_type}")
        return consent_log

    @staticmethod
    def check_expiring_consents(days_before: int = 30) -> List[EmployeeConsentLog]:
        """
        Find consents expiring soon.

        Args:
            days_before: Number of days before expiration to check

        Returns:
            List of consents expiring within the specified days
        """
        cutoff_date = timezone.now() + timedelta(days=days_before)

        expiring = EmployeeConsentLog.objects.filter(
            status=EmployeeConsentLog.ConsentStatus.GRANTED,
            expires_at__isnull=False,
            expires_at__lte=cutoff_date,
            expires_at__gte=timezone.now()
        ).select_related('employee', 'policy')

        return list(expiring)

    @staticmethod
    def send_expiration_reminders() -> int:
        """
        Send reminders for expiring consents.

        Returns:
            Number of reminders sent
        """
        expiring = ConsentManagementService.check_expiring_consents(days_before=30)
        sent = 0

        for consent in expiring:
            try:
                ConsentNotificationService.send_expiration_reminder(consent)
                consent.reminder_sent_at = timezone.now()
                consent.save()
                sent += 1
            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error sending expiration reminder for consent {consent.id}: {e}", exc_info=True)
            except (AttributeError, TypeError, ValueError) as e:
                logger.error(f"Data error sending expiration reminder for consent {consent.id}: {e}", exc_info=True)

        logger.info(f"Sent {sent} consent expiration reminders")
        return sent

    @staticmethod
    def expire_old_consents() -> int:
        """
        Mark expired consents as EXPIRED status.

        Returns:
            Number of consents expired
        """
        expired_count = EmployeeConsentLog.objects.filter(
            status=EmployeeConsentLog.ConsentStatus.GRANTED,
            expires_at__isnull=False,
            expires_at__lt=timezone.now()
        ).update(status=EmployeeConsentLog.ConsentStatus.EXPIRED)

        logger.info(f"Marked {expired_count} consents as expired")
        return expired_count


class ConsentNotificationService:
    """
    Service for sending consent-related notifications.
    """

    @staticmethod
    def send_consent_request(consent: EmployeeConsentLog) -> bool:
        """
        Send email requesting consent from employee.

        Args:
            consent: EmployeeConsentLog for the request

        Returns:
            True if email sent successfully
        """
        try:
            subject = f"Action Required: {consent.policy.title}"

            # Render email template
            html_message = render_to_string(
                'attendance/emails/consent_request.html',
                {
                    'employee': consent.employee,
                    'policy': consent.policy,
                    'consent_url': ConsentNotificationService._get_consent_url(consent),
                }
            )

            plain_message = render_to_string(
                'attendance/emails/consent_request.txt',
                {
                    'employee': consent.employee,
                    'policy': consent.policy,
                    'consent_url': ConsentNotificationService._get_consent_url(consent),
                }
            )

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[consent.employee.email],
                html_message=html_message,
                fail_silently=False,
            )

            consent.notification_sent_at = timezone.now()
            consent.save()

            logger.info(f"Sent consent request to {consent.employee.email}")
            return True

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error sending consent request: {e}", exc_info=True)
            return False
        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Data error sending consent request: {e}", exc_info=True)
            return False

    @staticmethod
    def send_consent_confirmation(consent: EmployeeConsentLog) -> bool:
        """Send confirmation email after consent granted"""
        try:
            subject = f"Consent Confirmed: {consent.policy.title}"

            html_message = render_to_string(
                'attendance/emails/consent_confirmation.html',
                {
                    'employee': consent.employee,
                    'policy': consent.policy,
                    'granted_at': consent.granted_at,
                }
            )

            send_mail(
                subject=subject,
                message=f"Your consent for {consent.policy.title} has been recorded.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[consent.employee.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Sent consent confirmation to {consent.employee.email}")
            return True

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error sending consent confirmation: {e}", exc_info=True)
            return False
        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Data error sending consent confirmation: {e}", exc_info=True)
            return False

    @staticmethod
    def send_revocation_confirmation(consent: EmployeeConsentLog) -> bool:
        """Send confirmation email after consent revoked"""
        try:
            subject = f"Consent Revoked: {consent.policy.title}"

            html_message = render_to_string(
                'attendance/emails/consent_revocation.html',
                {
                    'employee': consent.employee,
                    'policy': consent.policy,
                    'revoked_at': consent.revoked_at,
                    'reason': consent.revoked_reason,
                }
            )

            send_mail(
                subject=subject,
                message=f"Your consent for {consent.policy.title} has been revoked.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[consent.employee.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Sent revocation confirmation to {consent.employee.email}")
            return True

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error sending revocation confirmation: {e}", exc_info=True)
            return False
        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Data error sending revocation confirmation: {e}", exc_info=True)
            return False

    @staticmethod
    def send_expiration_reminder(consent: EmployeeConsentLog) -> bool:
        """Send reminder email for expiring consent"""
        try:
            days_remaining = consent.days_until_expiration

            subject = f"Reminder: Consent Expiring in {days_remaining} Days"

            html_message = render_to_string(
                'attendance/emails/consent_expiration_reminder.html',
                {
                    'employee': consent.employee,
                    'policy': consent.policy,
                    'days_remaining': days_remaining,
                    'expires_at': consent.expires_at,
                    'renewal_url': ConsentNotificationService._get_consent_url(consent),
                }
            )

            send_mail(
                subject=subject,
                message=f"Your consent for {consent.policy.title} expires in {days_remaining} days.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[consent.employee.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Sent expiration reminder to {consent.employee.email}")
            return True

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error sending expiration reminder: {e}", exc_info=True)
            return False
        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Data error sending expiration reminder: {e}", exc_info=True)
            return False

    @staticmethod
    def _get_consent_url(consent: EmployeeConsentLog) -> str:
        """Get URL for consent management page"""
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        return f"{base_url}/attendance/consent/{consent.uuid}/"


class StateSpecificConsentService:
    """
    Service for handling state-specific consent requirements.

    Different states have different laws around GPS tracking and biometric data.
    """

    # State-specific requirements
    # NOTE: GPS tracking requirements REMOVED - GPS is core app functionality
    STATE_REQUIREMENTS = {
        'CA': {  # California
            'biometric': {
                'requires_consent': True,
                'retention_after_termination_days': 0,  # Delete immediately
                'purpose_disclosure_required': True,
            },
        },
        'IL': {  # Illinois (BIPA)
            'biometric': {
                'requires_consent': True,
                'consent_type': 'written',  # BIPA requires written consent
                'retention_policy_disclosure': True,
                'destruction_timeline_disclosure': True,
                'no_profit_from_data': True,
            },
        },
        'TX': {  # Texas (CUBI)
            'biometric': {
                'requires_consent': True,
                'notice_required': True,
                'retention_disclosure_required': True,
            },
        },
        'WA': {  # Washington
            'biometric': {
                'requires_consent': True,
                'purpose_limitation': True,
                'notice_required': True,
            },
        },
    }

    @classmethod
    def get_state_requirements(cls, state: str, consent_type: str) -> Dict[str, Any]:
        """
        Get state-specific consent requirements.

        Args:
            state: State code (IL, TX, WA, CA)
            consent_type: Type of consent (biometric only - GPS removed)

        Returns:
            Dictionary with state requirements
        """
        state_reqs = cls.STATE_REQUIREMENTS.get(state, {})

        # GPS consent no longer required - core app functionality
        if consent_type == 'gps_tracking':
            return {'requires_consent': False}

        return state_reqs.get(consent_type, {
            'requires_consent': False,  # Federal default
        })

    @classmethod
    def validate_state_compliance(
        cls,
        user,
        consent_log: EmployeeConsentLog
    ) -> Tuple[bool, List[str]]:
        """
        Validate that consent meets state-specific requirements.

        Args:
            user: Employee
            consent_log: Consent log to validate

        Returns:
            Tuple of (is_compliant, list of issues)
        """
        issues = []

        # Determine user's state (would need user profile with state field)
        user_state = getattr(user, 'state', None)
        if not user_state:
            # No state info, use policy state
            user_state = consent_log.policy.state

        # Map policy type to requirement key
        # GPS_TRACKING removed - core app functionality, no consent needed
        consent_type_map = {
            ConsentPolicy.PolicyType.BIOMETRIC_DATA: 'biometric',
            ConsentPolicy.PolicyType.FACE_RECOGNITION: 'biometric',
            ConsentPolicy.PolicyType.PHOTO_CAPTURE: 'biometric',  # Treat as biometric
        }
        consent_type = consent_type_map.get(consent_log.policy.policy_type)

        if not consent_type:
            return True, []  # No specific requirements

        # Get state requirements
        requirements = cls.get_state_requirements(user_state, consent_type)

        # Check written consent requirement
        if requirements.get('consent_type') == 'written':
            if not consent_log.written_consent_document and not consent_log.signature_data:
                issues.append(
                    f"{user_state} requires written or signed consent for {consent_type}"
                )

        # Check explicit consent (not just implied)
        if requirements.get('consent_type') == 'explicit':
            if consent_log.status != EmployeeConsentLog.ConsentStatus.GRANTED:
                issues.append(
                    f"{user_state} requires explicit opt-in consent"
                )

        is_compliant = len(issues) == 0
        return is_compliant, issues

    @classmethod
    def get_required_policies_for_state(cls, state: str, user) -> List[ConsentPolicy]:
        """
        Get all policies required for a state.

        NOTE: GPS consent removed - GPS is core app functionality.
        Only returns BIOMETRIC consent policies.

        Args:
            state: State code
            user: User to get policies for

        Returns:
            List of required ConsentPolicy objects (biometric only)
        """
        # Get state requirements
        state_reqs = cls.STATE_REQUIREMENTS.get(state, {})

        required_policy_types = []

        # GPS consent REMOVED - core app functionality
        # Only check biometric requirements

        if state_reqs.get('biometric', {}).get('requires_consent'):
            required_policy_types.extend([
                ConsentPolicy.PolicyType.BIOMETRIC_DATA,
                ConsentPolicy.PolicyType.FACE_RECOGNITION,
                ConsentPolicy.PolicyType.PHOTO_CAPTURE,
            ])

        # Get active policies for these types
        policies = ConsentPolicy.objects.filter(
            state=state,
            policy_type__in=required_policy_types,
            is_active=True,
            effective_date__lte=timezone.now().date()
        ).filter(
            Q(expiration_date__isnull=True) | Q(expiration_date__gte=timezone.now().date())
        )

        return list(policies)
