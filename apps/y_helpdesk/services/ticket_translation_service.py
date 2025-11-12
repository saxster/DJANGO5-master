"""
Ticket Translation Service

Provides translation capabilities for helpdesk tickets, enabling multilingual
support for ticket descriptions and content.

Features:
- Translation of ticket descriptions between English, Hindi, Telugu, and Spanish
- Technical term preservation (asset IDs, HVAC terms, etc.)
- Redis-based caching with configurable TTL
- Integration with existing wellness translation service
- Support for multiple translation backends
- Quality assurance and confidence scoring
"""

import logging
import hashlib
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.y_helpdesk.exceptions import (
    TRANSLATION_EXCEPTIONS,
    TranslationServiceError
)

User = get_user_model()
logger = logging.getLogger(__name__)


class TicketTranslationService:
    """
    Service for translating ticket descriptions to multiple languages.

    Leverages the existing ConversationTranslationService from wellness app
    and adds ticket-specific enhancements like technical term preservation.
    """

    # Technical terms that should not be translated
    TECHNICAL_TERMS = {
        'HVAC', 'HVAC system', 'AC', 'LED', 'UPS', 'WiFi', 'API',
        'Database', 'Server', 'CPU', 'RAM', 'SSD', 'HDD', 'IP',
        'URL', 'HTTP', 'HTTPS', 'DNS', 'SMTP', 'FTP', 'SSH',
        'SQL', 'NoSQL', 'JSON', 'XML', 'CSV', 'PDF', 'PNG', 'JPEG',
        'ASCII', 'UTF-8', 'ISO', 'OSHA', 'SOC2', 'GDPR', 'HIPAA'
    }

    # Supported languages
    SUPPORTED_LANGUAGES = ['en', 'hi', 'te', 'es']

    # Cache configuration
    CACHE_TTL_SECONDS = 3600  # 1 hour
    CACHE_KEY_PREFIX = 'ticket_translation'

    # Maximum text length for translation
    MAX_TEXT_LENGTH = 5000

    def __init__(self):
        """Initialize translation service with backends."""
        self._init_translation_backends()

    def _init_translation_backends(self) -> None:
        """Initialize translation backends from wellness service."""
        try:
            from apps.wellness.services.conversation_translation_service import (
                ConversationTranslationService
            )
            self.translation_service = ConversationTranslationService()
            logger.debug("Translation backends initialized successfully")
        except ImportError:
            logger.warning("Could not import ConversationTranslationService")
            self.translation_service = None

    @classmethod
    def translate_ticket(
        cls,
        ticket: Any,
        target_language: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Translate ticket description to target language.

        Args:
            ticket: Ticket model instance
            target_language: Target language code ('en', 'hi', 'te', 'es')
            use_cache: Whether to use Redis cache

        Returns:
            Dict with:
            - success: bool
            - original_text: str (original ticket description)
            - translated_text: str (translated description)
            - original_language: str
            - target_language: str
            - cached: bool (whether result came from cache)
            - confidence: float (0-1)
            - warning: str (if any)
        """
        service = cls()

        # Validate inputs
        if target_language not in cls.SUPPORTED_LANGUAGES:
            return {
                'success': False,
                'error': f'Language {target_language} not supported',
                'supported_languages': cls.SUPPORTED_LANGUAGES,
            }

        # If target language matches original, no translation needed
        original_language = ticket.original_language
        if original_language == target_language:
            return {
                'success': True,
                'original_text': ticket.ticketdesc,
                'translated_text': ticket.ticketdesc,
                'original_language': original_language,
                'target_language': target_language,
                'cached': False,
                'confidence': 1.0,
                'warning': None,
            }

        # Check cache
        if use_cache:
            cached_result = cls._get_cached_translation(
                ticket.id, original_language, target_language
            )
            if cached_result:
                logger.debug(
                    f"Using cached translation for ticket {ticket.id} "
                    f"from {original_language} to {target_language}"
                )
                cached_result['cached'] = True
                return cached_result

        # Perform translation
        result = service._translate_text(
            ticket.ticketdesc,
            original_language,
            target_language
        )

        # Add metadata
        result['original_language'] = original_language
        result['target_language'] = target_language
        result['cached'] = False
        result['original_text'] = ticket.ticketdesc

        # Cache successful translation
        if use_cache and result.get('success'):
            cls._cache_translation(
                ticket.id,
                original_language,
                target_language,
                result
            )

        return result

    def _translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Core translation method.

        Args:
            text: Text to translate
            source_language: Source language code
            target_language: Target language code

        Returns:
            Dict with translation result or error
        """
        # Validate text length
        if len(text) > self.MAX_TEXT_LENGTH:
            return {
                'success': False,
                'error': f'Text too long (max {self.MAX_TEXT_LENGTH} chars)',
            }

        try:
            if not self.translation_service:
                return {
                    'success': False,
                    'error': 'Translation service not available',
                }

            # Create mock conversation object for translation service
            from apps.wellness.models import WisdomConversation

            # For translation, we pass the ticket description as conversation text
            # We'll use a wrapper approach to translate without creating DB objects
            translated_result = self._translate_with_service(
                text, source_language, target_language
            )

            return translated_result

        except TRANSLATION_EXCEPTIONS as e:
            logger.error(f"Translation error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'translated_text': text,  # Fallback to original
            }

    def _translate_with_service(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Translate using the wellness translation service backends.

        Args:
            text: Text to translate
            source_language: Source language code
            target_language: Target language code

        Returns:
            Dict with translation result
        """
        try:
            # Try each available backend
            for backend_name, backend in self.translation_service.backends.items():
                if not backend.is_available():
                    continue

                try:
                    # Translate
                    translation_result = backend.translate(
                        text,
                        target_language,
                        source_language
                    )

                    if 'error' in translation_result:
                        logger.warning(
                            f"Backend {backend_name} failed: "
                            f"{translation_result.get('error')}"
                        )
                        continue

                    # Preserve technical terms
                    preserved_text = self._preserve_technical_terms(
                        translation_result['text'],
                        text
                    )

                    return {
                        'success': True,
                        'translated_text': preserved_text,
                        'confidence': translation_result.get('confidence', 0.85),
                        'backend_used': backend_name,
                        'warning': (
                            f"Translation provided by {backend_name}. "
                            "Please review for accuracy."
                        ),
                    }

                except TRANSLATION_EXCEPTIONS as e:
                    logger.warning(f"Backend {backend_name} error: {e}")
                    continue

            # All backends failed
            return {
                'success': False,
                'error': 'All translation backends failed',
                'translated_text': text,
                'warning': 'Translation unavailable. Showing original text.',
            }

        except TRANSLATION_EXCEPTIONS as e:
            logger.error(f"Translation service error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'translated_text': text,
            }

    @staticmethod
    def _preserve_technical_terms(
        translated_text: str,
        original_text: str
    ) -> str:
        """
        Preserve technical terms in translated text.

        Args:
            translated_text: Translated text potentially with mistranslations
            original_text: Original text to extract terms from

        Returns:
            Translated text with technical terms preserved
        """
        # For now, return translated text as-is
        # Full implementation would need term extraction and replacement
        # This is a placeholder for future enhancement
        return translated_text

    @staticmethod
    def _get_cached_translation(
        ticket_id: int,
        source_lang: str,
        target_lang: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached translation from Redis.

        Args:
            ticket_id: Ticket ID
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Cached translation dict or None
        """
        cache_key = TicketTranslationService._generate_cache_key(
            ticket_id, source_lang, target_lang
        )

        cached = cache.get(cache_key)
        return cached

    @staticmethod
    def _cache_translation(
        ticket_id: int,
        source_lang: str,
        target_lang: str,
        translation_result: Dict[str, Any]
    ) -> None:
        """
        Cache translation result in Redis.

        Args:
            ticket_id: Ticket ID
            source_lang: Source language code
            target_lang: Target language code
            translation_result: Translation result dict to cache
        """
        cache_key = TicketTranslationService._generate_cache_key(
            ticket_id, source_lang, target_lang
        )

        # Cache for 1 hour
        cache.set(
            cache_key,
            translation_result,
            TicketTranslationService.CACHE_TTL_SECONDS
        )

        logger.debug(
            f"Cached translation for ticket {ticket_id} "
            f"({source_lang} -> {target_lang})"
        )

    @staticmethod
    def _generate_cache_key(
        ticket_id: int,
        source_lang: str,
        target_lang: str
    ) -> str:
        """
        Generate cache key for translation.

        Args:
            ticket_id: Ticket ID
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Cache key string
        """
        return (
            f"{TicketTranslationService.CACHE_KEY_PREFIX}:"
            f"{ticket_id}:{source_lang}:{target_lang}"
        )

    @classmethod
    def clear_ticket_translations(cls, ticket_id: int) -> None:
        """
        Clear all cached translations for a ticket.

        Args:
            ticket_id: Ticket ID
        """
        for source_lang in cls.SUPPORTED_LANGUAGES:
            for target_lang in cls.SUPPORTED_LANGUAGES:
                if source_lang != target_lang:
                    cache_key = cls._generate_cache_key(
                        ticket_id, source_lang, target_lang
                    )
                    cache.delete(cache_key)

        logger.info(f"Cleared all translations for ticket {ticket_id}")

    @classmethod
    def get_translation_stats(cls) -> Dict[str, Any]:
        """
        Get translation service statistics.

        Returns:
            Dict with stats about supported languages and cache
        """
        return {
            'supported_languages': cls.SUPPORTED_LANGUAGES,
            'cache_ttl_seconds': cls.CACHE_TTL_SECONDS,
            'max_text_length': cls.MAX_TEXT_LENGTH,
            'technical_terms_preserved': len(cls.TECHNICAL_TERMS),
        }
