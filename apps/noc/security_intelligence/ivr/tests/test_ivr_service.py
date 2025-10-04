"""
Unit Tests for IVR Service.

Tests IVR orchestration, providers, and response processing.
Follows .claude/rules.md testing standards.
"""

import pytest
from decimal import Decimal
from django.utils import timezone


@pytest.mark.django_db
class TestAIIVRService:
    """Test AI IVR service methods."""

    def test_initiate_guard_check_success(
        self, test_person, attendance_event, ivr_provider_config, voice_script_template, security_config
    ):
        """Test successful IVR call initiation."""
        from apps.noc.security_intelligence.ivr.services import AIIVRService
        from apps.noc.security_intelligence.models import AttendanceAnomalyLog

        anomaly = AttendanceAnomalyLog.objects.create(
            tenant=test_person.tenant,
            anomaly_type='GUARD_INACTIVITY',
            severity='HIGH',
            person=test_person,
            site=attendance_event.bu,
            detected_at=timezone.now(),
            confidence_score=0.85,
        )

        test_person.mobno = '+911234567890'
        test_person.save()

        call_log = AIIVRService.initiate_guard_check(
            person=test_person,
            anomaly=anomaly,
            anomaly_type='GUARD_INACTIVITY',
            language='en'
        )

        assert call_log is not None
        assert call_log.person == test_person
        assert call_log.provider == 'MOCK'
        assert call_log.call_status in ['QUEUED', 'RINGING']

    def test_rate_limiting_prevents_spam(self, test_person, ivr_provider_config):
        """Test that rate limiting prevents excessive calls."""
        from apps.noc.security_intelligence.ivr.models import IVRCallLog
        from apps.noc.security_intelligence.ivr.services import AIIVRService

        for i in range(3):
            IVRCallLog.objects.create(
                tenant=test_person.tenant,
                person=test_person,
                site=None,
                provider='MOCK',
                call_sid=f'MOCK_{i}',
                phone_number_masked='****1234',
            )

        can_call = AIIVRService._can_make_call(test_person)

        assert can_call is False

    def test_no_phone_number_skips_ivr(self, test_person, security_config):
        """Test that missing phone number skips IVR."""
        from apps.noc.security_intelligence.ivr.services import AIIVRService
        from apps.noc.security_intelligence.models import InactivityAlert

        test_person.mobno = None
        test_person.save()

        anomaly = InactivityAlert.objects.create(
            tenant=test_person.tenant,
            person=test_person,
            site=test_person.organizational.bu if hasattr(test_person, 'organizational') else None,
            activity_tracking=None,
            detected_at=timezone.now(),
            severity='HIGH',
            inactivity_score=0.85,
            inactivity_duration_minutes=120,
        )

        call_log = AIIVRService.initiate_guard_check(
            person=test_person,
            anomaly=anomaly,
            anomaly_type='GUARD_INACTIVITY'
        )

        assert call_log is None


@pytest.mark.django_db
class TestVoiceScriptManager:
    """Test voice script generation."""

    def test_generate_script_with_variables(self, tenant, voice_script_template):
        """Test script generation with variable replacement."""
        from apps.noc.security_intelligence.ivr.services import VoiceScriptManager

        script, template = VoiceScriptManager.generate_script(
            tenant=tenant,
            anomaly_type='GUARD_INACTIVITY',
            context={'guard_name': 'John Doe', 'site_name': 'Site A'},
            language='en'
        )

        assert script is not None
        assert 'John Doe' in script
        assert template == voice_script_template

    def test_get_response_options(self):
        """Test response options retrieval."""
        from apps.noc.security_intelligence.ivr.services import VoiceScriptManager

        options = VoiceScriptManager.get_response_options('GUARD_INACTIVITY')

        assert '1' in options
        assert '2' in options
        assert options['1'] == 'confirmed_at_post'


@pytest.mark.django_db
class TestResponseValidator:
    """Test response validation."""

    def test_validate_confirmed_response(self):
        """Test validation of confirmed response."""
        from apps.noc.security_intelligence.ivr.services import ResponseValidator

        result = ResponseValidator.validate_dtmf_response(
            dtmf_input='1',
            expected_options={'1': 'confirmed_at_post', '2': 'need_assistance'},
            anomaly_type='GUARD_INACTIVITY'
        )

        assert result['is_valid'] is True
        assert result['result'] == 'CONFIRMED'
        assert result['action'] == 'resolve'

    def test_validate_escalation_response(self):
        """Test validation of escalation response."""
        from apps.noc.security_intelligence.ivr.services import ResponseValidator

        result = ResponseValidator.validate_dtmf_response(
            dtmf_input='3',
            expected_options={'1': 'confirmed', '2': 'assistance', '3': 'report_issue'},
            anomaly_type='GENERIC'
        )

        assert result['is_valid'] is True
        assert result['result'] == 'DENIED'
        assert result['action'] == 'escalate'


@pytest.mark.django_db
class TestIVRCostMonitor:
    """Test cost monitoring."""

    def test_track_call_cost(self, ivr_call_log, ivr_provider_config):
        """Test call cost tracking."""
        from apps.noc.security_intelligence.ivr.services import IVRCostMonitor

        ivr_call_log.duration_seconds = 60
        ivr_call_log.save()

        cost = IVRCostMonitor.track_call_cost(ivr_call_log, ivr_provider_config)

        assert cost >= Decimal('0.00')

    def test_monthly_spending_calculation(self, tenant):
        """Test monthly spending calculation."""
        from apps.noc.security_intelligence.ivr.services import IVRCostMonitor

        spending = IVRCostMonitor.get_monthly_spending(tenant)

        assert 'total_calls' in spending
        assert 'total_cost' in spending
        assert 'success_rate' in spending