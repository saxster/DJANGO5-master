"""
Conversation Translation Service

Provides translation capabilities for wisdom conversations, supporting multiple
translation backends with caching, quality assurance, and proper error handling.

Features:
- Multiple translation backends (Google Translate, Azure Translator, OpenAI)
- Intelligent caching to avoid repeated API calls
- Translation quality scoring and confidence indicators
- Cultural adaptation for different languages
- Fallback mechanisms when primary services fail
- Rate limiting and cost optimization
"""

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from ..models.wisdom_conversations import WisdomConversation
from ..models.conversation_translation import WisdomConversationTranslation, TranslationQualityFeedback
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

User = get_user_model()
logger = logging.getLogger(__name__)


class TranslationBackend:
    """Base class for translation backends"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.rate_limit_calls = 0
        self.rate_limit_reset = time.time() + 3600  # Reset hourly

    def translate(self, text: str, target_language: str, source_language: str = 'en') -> Dict:
        """
        Translate text from source to target language

        Returns:
            Dict with 'text', 'confidence', 'detected_language', 'backend' keys
        """
        raise NotImplementedError

    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Check if backend is available and configured"""
        return bool(self.api_key)


class GoogleTranslateBackend(TranslationBackend):
    """Google Translate API backend"""

    def translate(self, text: str, target_language: str, source_language: str = 'en') -> Dict:
        if not self.api_key:
            return {'error': 'Google Translate API key missing', 'backend': 'google'}

        payload = {
            'q': text,
            'target': target_language,
            'format': 'text',
        }
        if source_language:
            payload['source'] = source_language

        try:
            response = requests.post(
                'https://translation.googleapis.com/language/translate/v2',
                params={'key': self.api_key},
                data=payload,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            translation = data['data']['translations'][0]
            translated_text = translation['translatedText']
            detected_language = translation.get('detectedSourceLanguage', source_language)
            return {
                'text': translated_text,
                'confidence': 0.95,
                'detected_language': detected_language,
                'backend': 'google',
                'cost_estimate': len(text) * 0.00002,
            }
        except requests.RequestException as exc:
            logger.error('Google Translate request failed: %s', exc, exc_info=True)
            return {'error': str(exc), 'backend': 'google'}

    def get_supported_languages(self) -> List[str]:
        return ['hi', 'te', 'es', 'fr', 'ar', 'zh', 'de', 'it', 'pt', 'ru', 'ja', 'ko']


class AzureTranslatorBackend(TranslationBackend):
    """Azure Translator API backend"""

    def __init__(self, api_key: str = None, region: str = None, endpoint: str = None):
        super().__init__(api_key)
        self.region = region or getattr(settings, 'AZURE_TRANSLATOR_REGION', None)
        self.endpoint = (endpoint or getattr(
            settings,
            'AZURE_TRANSLATOR_ENDPOINT',
            'https://api.cognitive.microsofttranslator.com'
        )).rstrip('/')

    def is_available(self) -> bool:
        return bool(self.api_key and self.region)

    def translate(self, text: str, target_language: str, source_language: str = 'en') -> Dict:
        if not self.is_available():
            return {'error': 'Azure Translator credentials missing', 'backend': 'azure'}

        url = f"{self.endpoint}/translate?api-version=3.0"
        params = {'to': target_language}
        if source_language:
            params['from'] = source_language

        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Ocp-Apim-Subscription-Region': self.region,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4()),
        }

        body = [{'text': text}]

        try:
            response = requests.post(url, params=params, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()
            translation = data[0]['translations'][0]
            return {
                'text': translation['text'],
                'confidence': 0.9,
                'detected_language': data[0].get('detectedLanguage', {}).get('language', source_language),
                'backend': 'azure',
                'cost_estimate': len(text) * 0.00001,
            }
        except requests.RequestException as exc:
            logger.error('Azure Translator request failed: %s', exc, exc_info=True)
            return {'error': str(exc), 'backend': 'azure'}

    def get_supported_languages(self) -> List[str]:
        return ['hi', 'te', 'es', 'fr', 'ar', 'zh', 'de', 'it', 'pt', 'ru', 'ja', 'ko']


class OpenAITranslationBackend(TranslationBackend):
    """OpenAI-based translation backend for high-quality cultural adaptation"""

    def __init__(self, api_key: str = None, model: Optional[str] = None):
        super().__init__(api_key)
        self.model = model or getattr(settings, 'OPENAI_TRANSLATION_MODEL', 'gpt-4o-mini')

    def translate(self, text: str, target_language: str, source_language: str = 'en') -> Dict:
        if not self.api_key:
            return {'error': 'OpenAI API key missing', 'backend': 'openai'}

        system_prompt = (
            'You are a professional translator. Translate the provided text '
            f'from {source_language} to {target_language} while preserving tone, '
            'intent, and cultural nuances. Respond with translation only.'
        )

        payload = {
            'model': self.model,
            'temperature': 0.2,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': text},
            ],
        }

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                json=payload,
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            translated = data['choices'][0]['message']['content'].strip()
            return {
                'text': translated,
                'confidence': 0.98,
                'detected_language': source_language,
                'backend': 'openai',
                'cost_estimate': len(text) * 0.00006,
                'cultural_adaptation': True,
            }
        except requests.RequestException as exc:
            logger.error('OpenAI Translation API error: %s', exc, exc_info=True)
            return {'error': str(exc), 'backend': 'openai'}

    def get_supported_languages(self) -> List[str]:
        return ['hi', 'te', 'es', 'fr', 'ar', 'zh']


class LocalRuleBasedBackend(TranslationBackend):
    """Deterministic fallback translator for offline/test environments."""

    def __init__(self, language_maps: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None):
        super().__init__(api_key='local')
        self.language_maps = language_maps or self._build_default_maps()

    def is_available(self) -> bool:
        return True

    def translate(self, text: str, target_language: str, source_language: str = 'en') -> Dict:
        source_language = source_language or 'en'
        detected_language = self._detect_language(text)

        if source_language == target_language:
            return {
                'text': text,
                'confidence': 0.99,
                'detected_language': detected_language,
                'backend': 'local',
            }

        mapping = self.language_maps.get(source_language, {}).get(target_language)
        if not mapping:
            # When we have no mapping, fall back to returning original text tagged
            return {
                'text': f'[{target_language}] {text}',
                'confidence': 0.4,
                'detected_language': detected_language,
                'backend': 'local',
            }

        translated_tokens = []
        for token in text.split():
            normalized = token.strip().lower().strip('.,!?:;')
            translated = mapping.get(normalized)
            if translated:
                # Preserve trailing punctuation/case approximately
                suffix = ''
                if token[-1:] in '.,!?:;':
                    suffix = token[-1]
                translated_tokens.append(translated + suffix)
            else:
                translated_tokens.append(token)

        return {
            'text': ' '.join(translated_tokens),
            'confidence': 0.55,
            'detected_language': detected_language,
            'backend': 'local',
        }

    def get_supported_languages(self) -> List[str]:
        languages = set()
        for source, targets in self.language_maps.items():
            languages.add(source)
            languages.update(targets.keys())
        return sorted(languages)

    def _build_default_maps(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        # Minimal dictionaries focused on support use-cases
        en_hi = {
            'server': 'सर्वर',
            'down': 'डाउन',
            'database': 'डेटाबेस',
            'connection': 'कनेक्शन',
            'failed': 'विफल',
            'please': 'कृपया',
            'help': 'मदद',
            'immediately': 'तुरंत',
        }

        en_te = {
            'server': 'సర్వర్',
            'down': 'డౌన్',
            'database': 'డేటాబేస్',
            'connection': 'కనెక్షన్',
            'failed': 'విఫలమైంది',
            'please': 'దయచేసి',
            'help': 'సాయం',
            'immediately': 'వెంటనే',
        }

        en_es = {
            'server': 'servidor',
            'down': 'caído',
            'database': 'base de datos',
            'connection': 'conexión',
            'failed': 'falló',
            'please': 'por favor',
            'help': 'ayuda',
            'immediately': 'inmediatamente',
        }

        base_map = {
            'en': {
                'hi': en_hi,
                'te': en_te,
                'es': en_es,
            }
        }

        # Provide basic reverse mappings for returning to English
        for target_lang, mapping in [('hi', en_hi), ('te', en_te), ('es', en_es)]:
            reverse = {v: k for k, v in mapping.items()}
            base_map.setdefault(target_lang, {})['en'] = reverse

        return base_map

    @staticmethod
    def _detect_language(text: str) -> str:
        for character in text:
            code_point = ord(character)
            if 0x0900 <= code_point <= 0x097F:
                return 'hi'
            if 0x0C00 <= code_point <= 0x0C7F:
                return 'te'
        # Very naive detection for Spanish (presence of ñ or á etc.)
        if any(ch in text for ch in 'ñáéíóúü'):
            return 'es'
        return 'en'


class ConversationTranslationService:
    """
    Main translation service for wisdom conversations with caching and quality assurance
    """

    def __init__(self):
        # Initialize translation backends in priority order
        self.backends = {
            'openai': OpenAITranslationBackend(
                api_key=getattr(settings, 'OPENAI_API_KEY', None),
                model=getattr(settings, 'OPENAI_TRANSLATION_MODEL', None),
            ),
            'google': GoogleTranslateBackend(
                api_key=getattr(settings, 'GOOGLE_TRANSLATE_API_KEY', None)
                or getattr(settings, 'GOOGLE_API_KEY', None)
            ),
            'azure': AzureTranslatorBackend(
                api_key=getattr(settings, 'AZURE_TRANSLATOR_API_KEY', None),
                region=getattr(settings, 'AZURE_TRANSLATOR_REGION', None),
                endpoint=getattr(settings, 'AZURE_TRANSLATOR_ENDPOINT', None),
            ),
            'local': LocalRuleBasedBackend(),
        }

        self.test_mode = getattr(settings, 'TRANSLATION_TEST_MODE', False)

        # Translation settings
        self.cache_timeout = 86400 * 7  # 7 days
        self.min_confidence_threshold = 0.7
        self.max_text_length = 10000  # Limit translation size

        # Warning messages for different languages
        self.warning_messages = {
            'en': "⚠️ This conversation was translated from English. Translation may contain errors or cultural nuances may be lost.",
            'hi': "⚠️ यह बातचीत अंग्रेजी से अनुवादित की गई है। अनुवाद में त्रुटियां हो सकती हैं या सांस्कृतिक बारीकियां छूट सकती हैं।",
            'te': "⚠️ ఈ సంభాషణ ఇంగ్లీషు నుండి అనువదించబడింది. అనువాదంలో దోషాలు ఉండవచ్చు లేదా సాంస్కృతిక సూక్ష్మతలు కోల్పోవచ్చు.",
            'es': "⚠️ Esta conversación fue traducida del inglés. La traducción puede contener errores o perderse matices culturales.",
            'fr': "⚠️ Cette conversation a été traduite de l'anglais. La traduction peut contenir des erreurs ou perdre des nuances culturelles.",
            'ar': "⚠️ تمت ترجمة هذه المحادثة من الإنجليزية. قد تحتوي الترجمة على أخطاء أو قد تفقد الفروق الثقافية الدقيقة.",
            'zh': "⚠️ 此对话从英语翻译而来。翻译可能包含错误或丢失文化细节。"
        }

    def translate_conversation(
        self,
        conversation: WisdomConversation,
        target_language: str,
        user: User = None,
        backend_preference: str = None
    ) -> Dict:
        """
        Translate a wisdom conversation to target language

        Args:
            conversation: WisdomConversation instance
            target_language: Target language code (e.g., 'hi', 'te')
            user: User requesting translation (for analytics)
            backend_preference: Preferred translation backend

        Returns:
            Dict with translated content and metadata
        """

        # Validate inputs
        if target_language == 'en':
            return {
                'success': True,
                'original_text': conversation.conversation_text,
                'translated_text': conversation.conversation_text,
                'bridge_text': conversation.contextual_bridge_text,
                'language': 'en',
                'warning': None,
                'cached': False
            }

        if not self._is_language_supported(target_language):
            return {
                'success': False,
                'error': f'Language {target_language} is not supported',
                'supported_languages': self._get_all_supported_languages()
            }

        # Check database cache first (more persistent)
        db_cached_translation = self._get_cached_translation_from_db(conversation, target_language)
        if db_cached_translation:
            logger.debug(f"Using database cached translation for conversation {conversation.id} to {target_language}")
            return db_cached_translation

        # Check Redis cache second (faster but less persistent)
        cache_key = self._generate_cache_key(conversation.id, target_language)
        cached_result = cache.get(cache_key)

        if cached_result:
            logger.debug(f"Using Redis cached translation for conversation {conversation.id} to {target_language}")
            cached_result['cached'] = True
            return cached_result

        # Perform translation
        translation_result = self._perform_translation(
            conversation, target_language, backend_preference
        )

        # Cache successful translation
        if translation_result['success']:
            cache.set(cache_key, translation_result, self.cache_timeout)

            # Store in database for permanent caching
            self._store_translation_in_db(conversation, target_language, translation_result)

        # Track translation analytics
        self._track_translation_usage(conversation, target_language, user, translation_result)

        return translation_result

    def _perform_translation(
        self,
        conversation: WisdomConversation,
        target_language: str,
        backend_preference: str = None
    ) -> Dict:
        """Perform the actual translation using available backends"""

        text_to_translate = conversation.conversation_text
        bridge_to_translate = conversation.contextual_bridge_text

        # Validate text length
        if len(text_to_translate) > self.max_text_length:
            return {
                'success': False,
                'error': f'Text too long for translation (max {self.max_text_length} characters)'
            }

        # Try backends in priority order
        backend_order = self._get_backend_order(target_language, backend_preference)

        for backend_name in backend_order:
            backend = self.backends[backend_name]

            if not backend.is_available():
                logger.debug(f"Backend {backend_name} not available, trying next")
                continue

            try:
                # Translate main conversation text
                main_translation = backend.translate(text_to_translate, target_language)

                if 'error' in main_translation:
                    logger.warning(f"Translation failed with backend {backend_name}: {main_translation['error']}")
                    continue

                # Translate bridge text if exists
                bridge_translation = None
                if bridge_to_translate:
                    bridge_translation = backend.translate(bridge_to_translate, target_language)
                    if 'error' in bridge_translation:
                        bridge_translation = None

                # Check translation quality
                if main_translation['confidence'] < self.min_confidence_threshold:
                    logger.warning(f"Translation confidence too low: {main_translation['confidence']}")
                    continue

                # Success!
                result = {
                    'success': True,
                    'original_text': text_to_translate,
                    'translated_text': main_translation['text'],
                    'bridge_text': bridge_translation['text'] if bridge_translation else bridge_to_translate,
                    'language': target_language,
                    'warning': self.warning_messages.get(target_language, self.warning_messages['en']),
                    'confidence': main_translation['confidence'],
                    'backend_used': backend_name,
                    'cost_estimate': main_translation.get('cost_estimate', 0),
                    'cultural_adaptation': main_translation.get('cultural_adaptation', False),
                    'cached': False,
                    'translation_date': timezone.now().isoformat()
                }

                logger.info(f"Successfully translated conversation {conversation.id} to {target_language} using {backend_name}")
                return result

            except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
                logger.error(f"Error with backend {backend_name}: {e}", exc_info=True)
                continue

        # All backends failed
        return {
            'success': False,
            'error': 'All translation backends failed',
            'fallback_text': text_to_translate,
            'warning': 'Translation service temporarily unavailable. Showing original English text.'
        }

    def _get_backend_order(self, target_language: str, preference: str = None) -> List[str]:
        """Get backends in priority order for given language and preference"""

        # If user has preference and it's available, use it first
        if preference and preference in self.backends and self.backends[preference].is_available():
            backends = [preference]
            backends.extend([b for b in ['openai', 'google', 'azure', 'local'] if b not in backends])
            return backends

        if getattr(self, 'test_mode', False):
            return ['local', 'google', 'azure', 'openai']

        # Default priority: highest quality providers first, deterministic local fallback last
        order = ['openai', 'google', 'azure', 'local']
        return order

    def _is_language_supported(self, language_code: str) -> bool:
        """Check if language is supported by any backend"""
        return any(
            language_code in backend.get_supported_languages()
            for backend in self.backends.values()
            if backend.is_available()
        )

    def _get_all_supported_languages(self) -> List[str]:
        """Get all languages supported by available backends"""
        supported = set()
        for backend in self.backends.values():
            if backend.is_available():
                supported.update(backend.get_supported_languages())
        return list(supported)

    def _generate_cache_key(self, conversation_id: str, language: str) -> str:
        """Generate cache key for translation"""
        return f"wisdom_translation:{conversation_id}:{language}"

    def _get_cached_translation_from_db(
        self,
        conversation: WisdomConversation,
        target_language: str
    ) -> Optional[Dict]:
        """Check database for existing valid translation"""
        try:
            translation = WisdomConversationTranslation.objects.filter(
                original_conversation=conversation,
                target_language=target_language,
                status='completed'
            ).order_by('-created_at').first()

            if not translation:
                return None

            # Check if translation is expired
            if translation.is_expired:
                logger.debug(f"Database cached translation expired for conversation {conversation.id}")
                return None

            # Update access tracking
            translation.mark_accessed()

            # Return translation in expected format
            return {
                'success': True,
                'original_text': conversation.conversation_text,
                'translated_text': translation.translated_text,
                'bridge_text': '',  # Not stored in new model
                'language': target_language,
                'warning': translation.warning_message,
                'cached': True,
                'database_cached': True,
                'confidence': translation.confidence_score or 0.0,
                'backend_used': translation.translation_backend,
                'quality_level': translation.quality_level,
                'cache_hits': translation.cache_hit_count,
                'translation_date': translation.created_at.isoformat(),
            }

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error retrieving cached translation from database: {e}", exc_info=True)
            return None

    def _store_translation_in_db(
        self,
        conversation: WisdomConversation,
        language: str,
        translation_result: Dict
    ):
        """Store successful translation in database for permanent caching"""
        try:
            # Generate content hash for version tracking
            content_hash = hashlib.sha256(
                conversation.conversation_text.encode('utf-8')
            ).hexdigest()

            # Calculate translation metrics
            original_words = len(conversation.conversation_text.split())
            translated_words = len(translation_result['translated_text'].split())

            WisdomConversationTranslation.objects.update_or_create(
                original_conversation=conversation,
                target_language=language,
                translation_version='1.0',
                defaults={
                    'translated_text': translation_result['translated_text'],
                    'warning_message': translation_result['warning'],
                    'translation_backend': translation_result['backend_used'],
                    'quality_level': 'unverified',
                    'status': 'completed',
                    'confidence_score': translation_result.get('confidence', 0.0),
                    'word_count_original': original_words,
                    'word_count_translated': translated_words,
                    'translation_time_ms': translation_result.get('translation_time_ms', 0),
                    'source_content_hash': content_hash,
                    'expires_at': timezone.now() + timedelta(days=30),  # 30 day cache
                    'tenant': conversation.tenant,
                }
            )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to store translation in database: {e}", exc_info=True)

    def _track_translation_usage(
        self,
        conversation: WisdomConversation,
        language: str,
        user: User,
        result: Dict
    ):
        """Track translation usage for analytics"""
        try:
            # Create analytics record
            analytics_data = {
                'conversation_id': str(conversation.id),
                'target_language': language,
                'user_id': user.id if user else None,
                'success': result['success'],
                'backend_used': result.get('backend_used'),
                'confidence': result.get('confidence'),
                'cost_estimate': result.get('cost_estimate', 0),
                'cached': result.get('cached', False),
                'timestamp': timezone.now().isoformat()
            }

            # Store in cache for batch processing
            analytics_key = f"translation_analytics:{timezone.now().strftime('%Y%m%d')}"
            analytics_list = cache.get(analytics_key, [])
            analytics_list.append(analytics_data)
            cache.set(analytics_key, analytics_list, 86400)  # 24 hours

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to track translation analytics: {e}", exc_info=True)

    def get_translation_stats(self, days: int = 30) -> Dict:
        """Get translation usage statistics"""
        try:
            # Get translations from last N days
            since_date = timezone.now() - timedelta(days=days)

            translations = WisdomConversationTranslation.objects.filter(
                created_at__gte=since_date
            )

            stats = {
                'total_translations': translations.count(),
                'by_language': {},
                'by_backend': {},
                'avg_confidence': 0,
                'total_cost_estimate': 0
            }

            for translation in translations:
                # Count by language
                lang = translation.target_language
                stats['by_language'][lang] = stats['by_language'].get(lang, 0) + 1

                # Count by backend
                backend = translation.translation_backend
                stats['by_backend'][backend] = stats['by_backend'].get(backend, 0) + 1

                # Note: cost_estimate not implemented in new model
                # Future enhancement: add cost tracking

            # Calculate average confidence
            if translations.exists():
                from django.db.models import Avg
                stats['avg_confidence'] = translations.aggregate(
                    avg_conf=Avg('confidence_score')
                )['avg_conf']

            return stats

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to get translation stats: {e}", exc_info=True)
            return {'error': str(e)}

    def batch_translate_conversations(
        self,
        conversations: List[WisdomConversation],
        target_language: str,
        max_translations: int = 100
    ) -> Dict:
        """Batch translate multiple conversations with rate limiting"""

        results = {
            'total_requested': len(conversations),
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'cost_estimate': 0
        }

        processed = 0
        for conversation in conversations:
            if processed >= max_translations:
                results['skipped'] = len(conversations) - processed
                break

            try:
                # Check if already translated
                cache_key = self._generate_cache_key(conversation.id, target_language)
                if cache.get(cache_key):
                    results['skipped'] += 1
                    continue

                # Translate
                translation_result = self.translate_conversation(
                    conversation, target_language
                )

                if translation_result['success']:
                    results['successful'] += 1
                    results['cost_estimate'] += translation_result.get('cost_estimate', 0)
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'conversation_id': str(conversation.id),
                        'error': translation_result.get('error', 'Unknown error')
                    })

                processed += 1

                # NOTE: Rate limiting removed - this method should be called from Celery task
                # For synchronous batch operations, use individual translate_conversation() calls
                # REMOVED: time.sleep(0.1) - violates Rule #14 (no blocking I/O in request paths)

            except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
                results['failed'] += 1
                results['errors'].append({
                    'conversation_id': str(conversation.id),
                    'error': str(e)
                })
                processed += 1

        logger.info(f"Batch translation complete: {results}")
        return results
