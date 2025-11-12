"""
Crisis Escalation and Notification Tests

Tests for professional escalation logic, notification delivery, and fallback mechanisms.

Priority: P0 - CRITICAL (User Safety)
Coverage Target: 100% of escalation and notification paths
"""

import pytest
from unittest.mock import patch, MagicMock, call
from django.core.mail import EmailMultiAlternatives
from smtplib import SMTPException
from apps.wellness.services.crisis_prevention_system import CrisisPreventionSystem
from .conftest import create_journal_entry, create_intervention_log


@pytest.mark.django_db
class TestProfessionalEscalation:
    """Test professional escalation protocols (HR, EAP, healthcare)"""

    def test_level_4_escalation_notifies_all_channels(self, test_user, mock_notification_service):
        """
        Level 4 (critical) escalation MUST notify ALL professional channels:
        - HR department
        - EAP (Employee Assistance Program)
        - Healthcare provider
        - Emergency contacts
        """
        crisis_system = CrisisPreventionSystem()

        crisis_entry = create_journal_entry(
            test_user,
            mood=1,
            stress=5,
            content="Suicidal thoughts"
        )

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=4,
            crisis_assessment={'urgency_score': 9}
        )

        # Verify all channels notified
        assert result['escalation_level'] == 4
        assert 'hr_department' in result['notifications_sent']
        assert 'eap_provider' in result['notifications_sent']
        assert 'healthcare_provider' in result['notifications_sent']
        assert 'emergency_contacts' in result['notifications_sent']
        assert result['total_notifications_sent'] >= 4

    def test_level_3_escalation_notifies_hr_and_eap(self, test_user, mock_notification_service):
        """Level 3 escalation notifies HR and EAP (not healthcare yet)"""
        crisis_system = CrisisPreventionSystem()

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=3,
            crisis_assessment={'urgency_score': 6}
        )

        assert 'hr_department' in result['notifications_sent']
        assert 'eap_provider' in result['notifications_sent']
        assert 'healthcare_provider' not in result['notifications_sent']

    def test_level_2_escalation_notifies_supervisor_only(self, test_user, mock_notification_service):
        """Level 2 escalation notifies immediate supervisor only"""
        crisis_system = CrisisPreventionSystem()

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=2,
            crisis_assessment={'urgency_score': 4}
        )

        assert 'supervisor' in result['notifications_sent']
        assert 'hr_department' not in result['notifications_sent']
        assert result['escalation_level'] == 2


@pytest.mark.django_db
class TestNotificationFallback:
    """Test multi-channel notification fallback mechanisms"""

    def test_email_failure_triggers_sms_fallback(self, test_user, mocker):
        """
        CRITICAL: Email failure MUST trigger SMS fallback.

        Notification channels (priority order):
        1. Email (primary)
        2. SMS (fallback #1)
        3. Webhook (fallback #2)
        """
        crisis_system = CrisisPreventionSystem()

        # Mock email failure
        mock_email = mocker.patch('django.core.mail.send_mail')
        mock_email.side_effect = SMTPException("SMTP server unavailable")

        # Mock SMS success
        mock_sms = mocker.patch('apps.wellness.services.crisis_prevention_system.send_sms')
        mock_sms.return_value = True

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=4,
            crisis_assessment={'urgency_score': 9}
        )

        # Verify fallback was triggered
        assert result['notifications_sent'] > 0
        assert 'email' in result['notification_failures']
        assert 'sms' in result['notification_channels_used']
        mock_sms.assert_called()  # SMS was attempted

    def test_email_and_sms_failure_triggers_webhook(self, test_user, mocker):
        """All channels failed → Use webhook as last resort"""
        crisis_system = CrisisPreventionSystem()

        # Mock email failure
        mocker.patch('django.core.mail.send_mail', side_effect=SMTPException)

        # Mock SMS failure
        mocker.patch('apps.wellness.services.crisis_prevention_system.send_sms', side_effect=Exception("SMS API down"))

        # Mock webhook success
        mock_webhook = mocker.patch('apps.wellness.services.crisis_prevention_system.send_webhook')
        mock_webhook.return_value = True

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=4,
            crisis_assessment={'urgency_score': 9}
        )

        # Verify webhook was used
        assert 'webhook' in result['notification_channels_used']
        mock_webhook.assert_called()

    def test_all_notification_channels_fail_raises_alert(self, test_user, mocker):
        """
        CRITICAL: If ALL notification channels fail, system MUST:
        1. Log critical error
        2. Trigger manual admin alert
        3. NOT silently fail
        """
        crisis_system = CrisisPreventionSystem()

        # Mock all channels failing
        mocker.patch('django.core.mail.send_mail', side_effect=SMTPException)
        mocker.patch('apps.wellness.services.crisis_prevention_system.send_sms', side_effect=Exception)
        mocker.patch('apps.wellness.services.crisis_prevention_system.send_webhook', side_effect=Exception)

        # Mock admin alert
        mock_admin_alert = mocker.patch('apps.wellness.services.crisis_prevention_system.send_admin_alert')

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=4,
            crisis_assessment={'urgency_score': 9}
        )

        # Verify admin was alerted
        assert result['all_notifications_failed'] == True
        assert result['manual_intervention_required'] == True
        mock_admin_alert.assert_called_once()

    def test_notification_delivery_confirmation(self, test_user, mock_notification_service):
        """Notification delivery is confirmed and logged"""
        crisis_system = CrisisPreventionSystem()

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=3,
            crisis_assessment={'urgency_score': 6}
        )

        # Verify delivery confirmation
        assert result['delivery_confirmed'] == True
        assert result['confirmation_timestamp'] is not None
        assert result['notification_ids'] is not None  # Track message IDs


@pytest.mark.django_db
class TestEscalationRateLimiting:
    """Test escalation rate limiting and bypass for crises"""

    def test_escalation_rate_limited_for_non_crisis(self, test_user):
        """Normal escalation is rate-limited (prevent spam)"""
        crisis_system = CrisisPreventionSystem()

        # Escalate yesterday
        create_intervention_log(test_user, intervention_type='escalation', urgency='medium', days_ago=1)

        # Try to escalate again today (should be rate-limited)
        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=2,
            crisis_assessment={'urgency_score': 4}  # Medium urgency
        )

        assert result['rate_limited'] == True
        assert result['next_eligible_escalation'] is not None

    def test_crisis_bypasses_rate_limiting(self, test_user):
        """
        CRITICAL: Crisis-level escalation (urgency ≥6) MUST bypass rate limits.

        User safety takes precedence over spam prevention.
        """
        crisis_system = CrisisPreventionSystem()

        # Escalated yesterday (would normally block)
        create_intervention_log(test_user, intervention_type='escalation', urgency='low', days_ago=1)

        # Crisis today (should bypass rate limit)
        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=4,
            crisis_assessment={'urgency_score': 9, 'crisis_detected': True}
        )

        assert result['rate_limited'] == False
        assert result['rate_limit_bypassed'] == True
        assert result['bypass_reason'] == 'crisis_override'


@pytest.mark.django_db
class TestAuditTrail:
    """Test audit trail completeness for crisis interventions"""

    def test_all_crisis_events_logged(self, test_user, mock_notification_service):
        """Every crisis event MUST be logged for clinical review"""
        crisis_system = CrisisPreventionSystem()

        entry = create_journal_entry(test_user, mood=1, stress=5)
        result = crisis_system.assess_crisis_risk(test_user, entry)

        # Verify audit log created
        from apps.wellness.models import CrisisEventLog
        audit_logs = CrisisEventLog.objects.filter(user=test_user)

        assert audit_logs.exists()
        assert audit_logs.latest('created_at').event_type == 'crisis_detected'
        assert audit_logs.latest('created_at').urgency_score == result['urgency_score']

    def test_escalation_logged_with_full_context(self, test_user, mock_notification_service):
        """Escalation events include full context for review"""
        crisis_system = CrisisPreventionSystem()

        result = crisis_system.initiate_professional_escalation(
            user=test_user,
            escalation_level=4,
            crisis_assessment={'urgency_score': 9}
        )

        from apps.wellness.models import CrisisEventLog
        escalation_log = CrisisEventLog.objects.filter(
            user=test_user,
            event_type='escalation'
        ).latest('created_at')

        assert escalation_log.escalation_level == 4
        assert escalation_log.notifications_sent is not None
        assert escalation_log.crisis_assessment is not None
