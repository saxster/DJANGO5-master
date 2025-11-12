"""
Voice Script Manager Service.

Generates dynamic voice scripts from templates.
Leverages existing Google Cloud TTS service.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.core.cache import cache

logger = logging.getLogger('noc.security_intelligence.ivr')


class VoiceScriptManager:
    """Manages voice script generation and TTS."""

    @classmethod
    def generate_script(cls, tenant, anomaly_type, context, language='en'):
        """
        Generate voice script from template.

        Args:
            tenant: Tenant instance
            anomaly_type: Type of anomaly
            context: dict with variable values
            language: Script language

        Returns:
            tuple: (rendered_script, script_template) or (None, None)
        """
        from apps.noc.security_intelligence.ivr.models import VoiceScriptTemplate

        try:
            template = VoiceScriptTemplate.get_active_template(
                tenant, anomaly_type, language
            )

            if not template:
                template = cls._get_fallback_template(tenant, language)

            if not template:
                return None, None

            rendered_script = template.render_script(context)

            template.increment_usage()

            return rendered_script, template

        except (ValueError, AttributeError) as e:
            logger.error(f"Script generation error: {e}", exc_info=True)
            return None, None

    @classmethod
    def _get_fallback_template(cls, tenant, language):
        """Get generic fallback template."""
        from apps.noc.security_intelligence.ivr.models import VoiceScriptTemplate

        return VoiceScriptTemplate.get_active_template(
            tenant, 'GENERIC', language
        )

    @classmethod
    def generate_tts_audio(cls, script_text, language='en'):
        """
        Generate TTS audio using existing service.

        Args:
            script_text: Text to convert
            language: Language code

        Returns:
            dict: TTS result with audio_url
        """
        from apps.core_onboarding.services.tts_service import TTSService

        try:
            cache_key = f"tts_audio:{hash(script_text + language)}"
            cached_url = cache.get(cache_key)

            if cached_url:
                return {'success': True, 'audio_url': cached_url, 'cached': True}

            tts_service = TTSService()

            result = tts_service.speak_guidance(
                text_en=script_text,
                target_language=language,
                voice_gender='neutral'
            )

            if result.get('success') and result.get('audio_url'):
                cache.set(cache_key, result['audio_url'], timeout=86400)

            return result

        except (ValueError, AttributeError) as e:
            logger.error(f"TTS generation error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_response_options(cls, anomaly_type):
        """
        Get expected response options for anomaly type.

        Args:
            anomaly_type: Anomaly type

        Returns:
            dict: Response options
        """
        options_map = {
            'GUARD_INACTIVITY': {
                '1': 'confirmed_at_post',
                '2': 'need_assistance',
                '3': 'report_issue',
            },
            'WRONG_PERSON': {
                '1': 'confirmed_identity',
                '2': 'substitute_guard',
                '3': 'not_me',
            },
            'BUDDY_PUNCHING': {
                '1': 'at_site_a',
                '2': 'at_site_b',
                '3': 'did_not_mark_attendance',
            },
            'TASK_OVERDUE': {
                '1': 'handling_now',
                '2': 'need_help',
                '3': 'report_issue',
            },
        }

        return options_map.get(anomaly_type, {
            '1': 'confirmed',
            '2': 'assistance',
            '3': 'escalate',
        })