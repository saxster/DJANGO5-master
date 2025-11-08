"""
Text-to-Speech Service for Site Onboarding (Optional).

This service provides voice guidance capabilities to help operators through
the audit process in their native language. Uses Google Cloud Text-to-Speech.

Features:
- Multilingual voice guidance (10+ languages)
- Contextual prompts and instructions
- Audio caching for common phrases
- Optional feature (disabled by default)

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
import hashlib
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


class TTSService:
    """
    Text-to-Speech service for voice guidance.

    Optional feature for providing audio guidance to operators during audits.
    """

    # Supported languages (matching STT service)
    SUPPORTED_LANGUAGES = {
        'en': 'en-US',
        'hi': 'hi-IN',
        'mr': 'mr-IN',
        'ta': 'ta-IN',
        'te': 'te-IN',
        'kn': 'kn-IN',
        'gu': 'gu-IN',
        'bn': 'bn-IN',
        'ml': 'ml-IN',
        'or': 'or-IN'
    }

    # Cache TTL for audio (7 days)
    CACHE_TTL = 60 * 60 * 24 * 7

    def __init__(self):
        """Initialize TTS service with Google Cloud client."""
        self.tts_client = None
        self._initialize_tts_client()

    def _initialize_tts_client(self):
        """Initialize Google Cloud Text-to-Speech client."""
        if not getattr(settings, 'ENABLE_ONBOARDING_TTS', False):
            logger.info("TTS service disabled (ENABLE_ONBOARDING_TTS=False)")
            return

        try:
            from google.cloud import texttospeech
            self.tts_client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud TTS client initialized successfully")
        except ImportError:
            logger.warning("google-cloud-texttospeech not installed, TTS disabled")
            self.tts_client = None
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to initialize TTS client: {str(e)}")
            self.tts_client = None

    def speak_guidance(
        self,
        text_en: str,
        target_language: str,
        voice_gender: str = 'neutral'
    ) -> Dict[str, Any]:
        """
        Generate voice guidance audio.

        Args:
            text_en: English text to speak
            target_language: Target language code (e.g., 'hi', 'mr')
            voice_gender: Voice gender (neutral/male/female)

        Returns:
            {
                'success': bool,
                'audio_url': str | None,
                'audio_content': bytes | None,
                'duration_seconds': float,
                'cached': bool,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'audio_url': None,
            'audio_content': None,
            'duration_seconds': 0.0,
            'cached': False,
            'error': None
        }

        if not self.tts_client:
            result['error'] = "TTS service not available"
            logger.warning("TTS service called but not initialized")
            return result

        try:
            # Check cache first
            cache_key = self._get_cache_key(text_en, target_language, voice_gender)
            cached_audio = cache.get(cache_key)

            if cached_audio:
                result['success'] = True
                result['audio_content'] = cached_audio['content']
                result['duration_seconds'] = cached_audio['duration']
                result['cached'] = True
                logger.info(f"Returned cached TTS audio for {target_language}")
                return result

            # Translate text if needed
            if target_language != 'en':
                from apps.core_onboarding.services.translation import get_translation_service
                translation_service = get_translation_service()
                text_to_speak = translation_service.translate_text(
                    text_en,
                    target_language,
                    'en'
                )
            else:
                text_to_speak = text_en

            # Generate audio
            language_code = self.SUPPORTED_LANGUAGES.get(
                target_language,
                'en-US'
            )

            audio_content = self._generate_audio(
                text_to_speak,
                language_code,
                voice_gender
            )

            if audio_content:
                # Estimate duration (rough estimate: 150 words per minute)
                word_count = len(text_to_speak.split())
                duration = (word_count / 150.0) * 60.0

                # Cache the audio
                cache.set(
                    cache_key,
                    {
                        'content': audio_content,
                        'duration': duration
                    },
                    self.CACHE_TTL
                )

                result['success'] = True
                result['audio_content'] = audio_content
                result['duration_seconds'] = duration
                result['cached'] = False

                logger.info(
                    f"Generated TTS audio: {len(audio_content)} bytes, "
                    f"~{duration:.1f}s, language={target_language}"
                )
            else:
                result['error'] = "Audio generation failed"
                logger.error("TTS generation returned empty audio")

        except (IOError, ValueError) as e:
            logger.error(f"Error in TTS generation: {str(e)}")
            result['error'] = f"TTS failed: {str(e)}"
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Unexpected error in TTS: {str(e)}", exc_info=True)
            result['error'] = f"TTS failed: {str(e)}"

        return result

    def get_contextual_guidance(
        self,
        context: str,
        zone_type: str,
        language: str
    ) -> Optional[str]:
        """
        Get contextual guidance text for specific situations.

        Args:
            context: Situation context (e.g., 'zone_entry', 'photo_prompt')
            zone_type: Type of zone
            language: Target language

        Returns:
            Guidance text in English (will be translated by speak_guidance)
        """
        guidance_templates = {
            'zone_entry': {
                'vault': "Entering vault zone. Please describe security measures, camera positions, and access controls.",
                'gate': "At main gate. Please describe entry controls, guard post, and visitor management.",
                'atm': "At ATM location. Please check lighting, cameras, and anti-skimming devices.",
                'cash_counter': "At cash counter. Please observe security barriers, camera coverage, and time-delay locks."
            },
            'photo_prompt': {
                'vault': "Please take a photo of the vault door showing time lock and access controls.",
                'gate': "Please photograph the gate entrance, metal detector, and guard post.",
                'atm': "Please capture ATM unit, surrounding lighting, and camera positions.",
                'default': "Please take a photo of this area for documentation."
            },
            'observation_prompt': {
                'default': "Please describe what you observe in this zone. Mention security equipment, condition, and any concerns."
            },
            'completion': {
                'default': "Zone audit complete. Thank you. Moving to next zone."
            }
        }

        template_category = guidance_templates.get(context, {})
        guidance = template_category.get(zone_type, template_category.get('default', ''))

        return guidance if guidance else None

    def _generate_audio(
        self,
        text: str,
        language_code: str,
        voice_gender: str
    ) -> Optional[bytes]:
        """Generate audio using Google Cloud TTS."""
        if not self.tts_client:
            return None

        try:
            from google.cloud import texttospeech

            # Set the text input
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Select voice parameters
            voice_gender_map = {
                'neutral': texttospeech.SsmlVoiceGender.NEUTRAL,
                'male': texttospeech.SsmlVoiceGender.MALE,
                'female': texttospeech.SsmlVoiceGender.FEMALE
            }

            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                ssml_gender=voice_gender_map.get(voice_gender, texttospeech.SsmlVoiceGender.NEUTRAL)
            )

            # Select audio format
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,  # Normal speed
                pitch=0.0  # Normal pitch
            )

            # Perform TTS request
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            return response.audio_content

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error in Google TTS generation: {str(e)}", exc_info=True)
            return None

    def _get_cache_key(
        self,
        text: str,
        language: str,
        voice_gender: str
    ) -> str:
        """Generate cache key for TTS audio."""
        content = f"{text}:{language}:{voice_gender}"
        hash_value = hashlib.md5(content.encode()).hexdigest()
        return f"tts_audio:{hash_value}"

    def is_service_available(self) -> bool:
        """Check if TTS service is available."""
        return self.tts_client is not None

    def get_supported_languages(self) -> Dict[str, str]:
        """Get supported languages for TTS."""
        return self.SUPPORTED_LANGUAGES.copy()


# Factory function
def get_tts_service() -> TTSService:
    """Factory function to get TTS service instance."""
    return TTSService()