"""
AI IVR Service.

Main orchestrator for IVR guard verification.
Coordinates providers, scripts, and response processing.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger('noc.security_intelligence.ivr')


class AIIVRService:
    """Main IVR orchestration service."""

    MAX_CALLS_PER_HOUR = 3

    @classmethod
    def initiate_guard_check(cls, person, anomaly, anomaly_type, language='en'):
        """
        Initiate IVR verification call to guard.

        Args:
            person: People instance
            anomaly: Anomaly log instance
            anomaly_type: Type of anomaly
            language: Script language

        Returns:
            IVRCallLog instance or None
        """
        from apps.noc.security_intelligence.ivr.models import IVRCallLog

        try:
            if not cls._can_make_call(person):
                logger.warning(f"Rate limit exceeded for {person.peoplename}")
                return None

            if not person.mobno:
                logger.warning(f"No phone number for {person.peoplename}")
                return None

            provider, provider_instance = cls._select_provider(person.tenant)
            if not provider:
                logger.error("No active IVR provider")
                return None

            script, script_context = cls._generate_script(person, anomaly, anomaly_type, language)
            if not script:
                logger.error(f"No script for anomaly type {anomaly_type}")
                return None

            call_result = provider_instance.make_call(
                phone_number=person.mobno,
                script_text=script,
                metadata=script_context
            )

            if not call_result['success']:
                logger.error(f"Call failed: {call_result.get('error')}")
                return None

            call_log = cls._create_call_log(person, anomaly, provider, call_result, script)

            return call_log

        except (ValueError, AttributeError) as e:
            logger.error(f"IVR initiation error: {e}", exc_info=True)
            return None

    @classmethod
    def _can_make_call(cls, person):
        """Check rate limiting."""
        from apps.noc.security_intelligence.ivr.models import IVRCallLog

        recent_calls = IVRCallLog.get_recent_calls_to_person(person, hours=1)
        return recent_calls < cls.MAX_CALLS_PER_HOUR

    @classmethod
    def _select_provider(cls, tenant):
        """Select active provider with failover."""
        from apps.noc.security_intelligence.ivr.models import IVRProviderConfig
        from apps.noc.security_intelligence.ivr.providers import (
            TwilioProvider, SMSProvider, MockProvider
        )

        providers = IVRProviderConfig.objects.filter(
            tenant=tenant,
            is_active=True,
            is_healthy=True
        ).order_by('priority')

        for provider_config in providers:
            if provider_config.provider_type == 'TWILIO':
                return provider_config, TwilioProvider(provider_config)
            elif provider_config.provider_type == 'SMS':
                return provider_config, SMSProvider(provider_config)
            elif provider_config.provider_type == 'MOCK':
                return provider_config, MockProvider(provider_config)

        return None, None

    @classmethod
    def _generate_script(cls, person, anomaly, anomaly_type, language):
        """Generate voice script for anomaly."""
        from apps.noc.security_intelligence.ivr.services import VoiceScriptManager

        return VoiceScriptManager.generate_script(
            tenant=person.tenant,
            anomaly_type=anomaly_type,
            context={
                'guard_name': person.peoplename,
                'site_name': anomaly.site.name if hasattr(anomaly, 'site') else 'your site',
            },
            language=language
        )

    @classmethod
    @transaction.atomic
    def _create_call_log(cls, person, anomaly, provider_config, call_result, script_template):
        """Create IVR call log."""
        from apps.noc.security_intelligence.ivr.models import IVRCallLog

        call_log = IVRCallLog.objects.create(
            tenant=person.tenant,
            person=person,
            site=anomaly.site if hasattr(anomaly, 'site') else None,
            anomaly_log=anomaly if anomaly.__class__.__name__ == 'AttendanceAnomalyLog' else None,
            inactivity_alert=anomaly if anomaly.__class__.__name__ == 'InactivityAlert' else None,
            provider=provider_config.provider_type,
            call_sid=call_result['call_sid'],
            phone_number_masked=provider_config.mask_phone_number(person.mobno) if hasattr(provider_config, 'mask_phone_number') else "****",
            call_status=call_result['status'],
            script_template=script_template,
        )

        return call_log

    @classmethod
    def process_call_callback(cls, call_sid, status_data):
        """Process call status callback from provider."""
        from apps.noc.security_intelligence.ivr.models import IVRCallLog

        try:
            call_log = IVRCallLog.objects.get(call_sid=call_sid)

            call_log.call_status = status_data.get('CallStatus', '').upper()

            if call_log.call_status == 'IN_PROGRESS' and not call_log.answered_at:
                call_log.mark_answered()

            if call_log.call_status == 'COMPLETED':
                duration = int(status_data.get('CallDuration', 0))
                call_log.mark_completed(duration)

            return True

        except IVRCallLog.DoesNotExist:
            logger.error(f"Call log not found for SID: {call_sid}")
            return False
        except (ValueError, AttributeError) as e:
            logger.error(f"Callback processing error: {e}", exc_info=True)
            return False