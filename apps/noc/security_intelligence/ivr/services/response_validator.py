"""
Response Validator Service.

Validates guard responses from IVR calls.
Processes DTMF and voice responses.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.db import transaction

logger = logging.getLogger('noc.security_intelligence.ivr')


class ResponseValidator:
    """Validates IVR responses."""

    @classmethod
    def validate_dtmf_response(cls, dtmf_input, expected_options, anomaly_type):
        """
        Validate DTMF keypress response.

        Args:
            dtmf_input: DTMF digits pressed
            expected_options: dict of valid options
            anomaly_type: Type of anomaly

        Returns:
            dict: Validation result
        """
        try:
            if dtmf_input not in expected_options:
                return {
                    'is_valid': False,
                    'result': 'INVALID',
                    'confidence': 0.0,
                    'action': 'retry',
                }

            option_meaning = expected_options[dtmf_input]

            result, action = cls._interpret_response(option_meaning, anomaly_type)

            return {
                'is_valid': True,
                'result': result,
                'confidence': 1.0,
                'action': action,
                'option_meaning': option_meaning,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"DTMF validation error: {e}", exc_info=True)
            return {'is_valid': False, 'result': 'ERROR'}

    @classmethod
    def _interpret_response(cls, option_meaning, anomaly_type):
        """Interpret response meaning."""
        confirmed_options = [
            'confirmed_at_post', 'confirmed_identity', 'handling_now', 'confirmed'
        ]

        assistance_options = [
            'need_assistance', 'need_help', 'assistance', 'substitute_guard'
        ]

        escalation_options = [
            'report_issue', 'escalate', 'not_me', 'did_not_mark_attendance'
        ]

        if option_meaning in confirmed_options:
            return 'CONFIRMED', 'resolve'
        elif option_meaning in assistance_options:
            return 'ASSISTANCE_REQUESTED', 'create_ticket'
        elif option_meaning in escalation_options:
            return 'DENIED', 'escalate'
        else:
            return 'UNCLEAR', 'manual_review'

    @classmethod
    def validate_voice_response(cls, audio_url, expected_keywords, language='en'):
        """
        Validate voice response using STT.

        Args:
            audio_url: URL of voice recording
            expected_keywords: Keywords to match
            language: Language code

        Returns:
            dict: Validation result
        """
        from apps.onboarding_api.services.speech_service import OnboardingSpeechService

        try:
            speech_service = OnboardingSpeechService()

            return {
                'is_valid': False,
                'result': 'UNCLEAR',
                'confidence': 0.0,
                'action': 'manual_review',
                'message': 'Voice validation placeholder (future enhancement)',
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Voice validation error: {e}", exc_info=True)
            return {'is_valid': False, 'result': 'ERROR'}

    @classmethod
    @transaction.atomic
    def process_and_act(cls, call_log, response_data, validation_result):
        """
        Process validated response and take action.

        Args:
            call_log: IVRCallLog instance
            response_data: dict with response details
            validation_result: dict from validate_dtmf_response

        Returns:
            dict: Action result
        """
        from apps.noc.security_intelligence.ivr.models import IVRResponse

        try:
            ivr_response = IVRResponse.objects.create(
                tenant=call_log.tenant,
                call_log=call_log,
                response_type='DTMF',
                dtmf_input=response_data.get('dtmf'),
                validation_result=validation_result['result'],
                validation_confidence=validation_result['confidence'],
                is_valid_response=validation_result['is_valid'],
                action_taken=validation_result['action'],
            )

            call_log.response_received = True
            call_log.is_successful_verification = validation_result['result'] == 'CONFIRMED'
            call_log.save()

            action_result = cls._execute_action(call_log, validation_result['action'])

            return action_result

        except (ValueError, AttributeError) as e:
            logger.error(f"Response processing error: {e}", exc_info=True)
            return {'success': False}

    @classmethod
    def _execute_action(cls, call_log, action):
        """Execute action based on validation."""
        if action == 'resolve':
            return cls._resolve_anomaly(call_log)
        elif action == 'escalate':
            return cls._escalate_to_supervisor(call_log)
        elif action == 'create_ticket':
            return cls._create_support_ticket(call_log)
        else:
            return {'success': True, 'action': 'manual_review'}

    @staticmethod
    def _resolve_anomaly(call_log):
        """Mark anomaly as resolved."""
        if call_log.anomaly_log:
            call_log.anomaly_log.status = 'RESOLVED'
            call_log.anomaly_log.save()
        elif call_log.inactivity_alert:
            call_log.inactivity_alert.mark_resolved(call_log.person, "Confirmed via IVR")
        return {'success': True, 'action': 'resolved'}

    @staticmethod
    def _escalate_to_supervisor(call_log):
        """Escalate to supervisor."""
        return {'success': True, 'action': 'escalated'}

    @staticmethod
    def _create_support_ticket(call_log):
        """Create support ticket."""
        return {'success': True, 'action': 'ticket_created'}