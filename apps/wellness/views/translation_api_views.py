"""
Translation API Views

REST API endpoints for wisdom conversation translation functionality.
Provides secure, authenticated access to translation services with proper
error handling and warning messages.
"""

import logging
from typing import Dict, Any
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models.wisdom_conversations import WisdomConversation
from ..models.conversation_translation import WisdomConversationTranslation, TranslationQualityFeedback
from ..services.conversation_translation_service import ConversationTranslationService

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def translate_conversation(request):
    """
    Translate a wisdom conversation to target language with warning messages

    POST /api/wellness/translate-conversation/
    {
        "conversation_id": "123",
        "target_language": "hi",
        "backend_preference": "openai"  // optional
    }
    """
    try:
        # Validate request data
        conversation_id = request.data.get('conversation_id')
        target_language = request.data.get('target_language')
        backend_preference = request.data.get('backend_preference')

        if not conversation_id or not target_language:
            return Response({
                'success': False,
                'error': 'conversation_id and target_language are required',
                'code': 'MISSING_PARAMETERS'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get conversation with tenant filtering
        conversation = get_object_or_404(
            WisdomConversation.objects.filter(tenant=request.user.tenant),
            id=conversation_id
        )

        # Perform translation
        translation_service = ConversationTranslationService()
        result = translation_service.translate_conversation(
            conversation=conversation,
            target_language=target_language,
            user=request.user,
            backend_preference=backend_preference
        )

        if result['success']:
            return Response({
                'success': True,
                'data': {
                    'conversation_id': str(conversation.id),
                    'original_text': result['original_text'],
                    'translated_text': result['translated_text'],
                    'target_language': result['language'],
                    'warning_message': result['warning'],
                    'quality_info': {
                        'confidence_score': result.get('confidence', 0.0),
                        'backend_used': result.get('backend_used', 'unknown'),
                        'cached': result.get('cached', False),
                        'database_cached': result.get('database_cached', False),
                        'quality_level': result.get('quality_level', 'unverified')
                    },
                    'metadata': {
                        'translation_date': result.get('translation_date'),
                        'cache_hits': result.get('cache_hits', 0),
                        'bridge_text': result.get('bridge_text', '')
                    }
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Translation failed'),
                'code': 'TRANSLATION_FAILED',
                'supported_languages': result.get('supported_languages', [])
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    except ValidationError as e:
        return Response({
            'success': False,
            'error': 'Validation error',
            'details': str(e),
            'code': 'VALIDATION_ERROR'
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Translation API error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_supported_languages(request):
    """
    Get list of supported translation languages

    GET /api/wellness/supported-languages/
    """
    try:
        translation_service = ConversationTranslationService()

        # Get supported languages with display names
        supported_languages = [
            {'code': 'hi', 'name': 'हिन्दी (Hindi)', 'native_name': 'हिन्दी'},
            {'code': 'te', 'name': 'తెలుగు (Telugu)', 'native_name': 'తెలుగు'},
            {'code': 'es', 'name': 'Español (Spanish)', 'native_name': 'Español'},
            {'code': 'fr', 'name': 'Français (French)', 'native_name': 'Français'},
            {'code': 'ar', 'name': 'العربية (Arabic)', 'native_name': 'العربية'},
            {'code': 'zh', 'name': '中文 (Chinese)', 'native_name': '中文'},
        ]

        # Get backend availability status
        available_backends = []
        for backend_name, backend in translation_service.backends.items():
            available_backends.append({
                'name': backend_name,
                'available': backend.is_available(),
                'supported_languages': backend.get_supported_languages() if backend.is_available() else []
            })

        return Response({
            'success': True,
            'data': {
                'supported_languages': supported_languages,
                'available_backends': available_backends,
                'default_warning': translation_service.warning_messages.get('en', ''),
                'service_status': 'operational' if any(b.is_available() for b in translation_service.backends.values()) else 'limited'
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Get supported languages API error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to get supported languages',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_translation_status(request, conversation_id):
    """
    Get translation status and available translations for a conversation

    GET /api/wellness/translation-status/{conversation_id}/
    """
    try:
        # Get conversation with tenant filtering
        conversation = get_object_or_404(
            WisdomConversation.objects.filter(tenant=request.user.tenant),
            id=conversation_id
        )

        # Get all translations for this conversation
        translations = WisdomConversationTranslation.objects.filter(
            original_conversation=conversation
        ).order_by('-created_at')

        translation_data = []
        for translation in translations:
            translation_data.append({
                'id': translation.id,
                'target_language': translation.target_language,
                'language_display': translation.get_target_language_display(),
                'status': translation.status,
                'quality_level': translation.quality_level,
                'quality_display': translation.get_quality_level_display(),
                'confidence_score': translation.confidence_score,
                'backend_used': translation.translation_backend,
                'word_count': translation.word_count_translated,
                'cache_hits': translation.cache_hit_count,
                'created_at': translation.created_at.isoformat(),
                'last_accessed': translation.last_accessed.isoformat() if translation.last_accessed else None,
                'is_expired': translation.is_expired,
                'warning_message': translation.warning_message
            })

        return Response({
            'success': True,
            'data': {
                'conversation_id': str(conversation.id),
                'conversation_title': getattr(conversation, 'title', 'Wisdom Conversation'),
                'conversation_date': conversation.conversation_date.isoformat(),
                'original_language': 'en',
                'available_translations': translation_data,
                'total_translations': len(translation_data),
                'has_translations': len(translation_data) > 0
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Get translation status API error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to get translation status',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_translation_feedback(request):
    """
    Submit quality feedback for a translation

    POST /api/wellness/translation-feedback/
    {
        "translation_id": "123",
        "feedback_type": "rating",
        "quality_rating": 4,
        "feedback_text": "Good translation but some cultural nuances lost",
        "suggested_translation": "Optional improved translation"
    }
    """
    try:
        # Validate request data
        translation_id = request.data.get('translation_id')
        feedback_type = request.data.get('feedback_type')
        quality_rating = request.data.get('quality_rating')
        feedback_text = request.data.get('feedback_text', '')
        suggested_translation = request.data.get('suggested_translation', '')

        if not translation_id or not feedback_type:
            return Response({
                'success': False,
                'error': 'translation_id and feedback_type are required',
                'code': 'MISSING_PARAMETERS'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get translation with tenant filtering
        translation = get_object_or_404(
            WisdomConversationTranslation.objects.filter(tenant=request.user.tenant),
            id=translation_id
        )

        # Create or update feedback
        feedback, created = TranslationQualityFeedback.objects.update_or_create(
            translation=translation,
            user=request.user,
            defaults={
                'feedback_type': feedback_type,
                'quality_rating': quality_rating,
                'feedback_text': feedback_text,
                'suggested_translation': suggested_translation,
                'tenant': request.user.tenant
            }
        )

        return Response({
            'success': True,
            'data': {
                'feedback_id': feedback.id,
                'created': created,
                'feedback_type': feedback.feedback_type,
                'quality_rating': feedback.quality_rating,
                'submission_date': feedback.created_at.isoformat(),
                'message': 'Thank you for your feedback! It helps improve translation quality.'
            }
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Submit translation feedback API error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to submit feedback',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_translation_analytics(request):
    """
    Get translation usage analytics and statistics

    GET /api/wellness/translation-analytics/?days=30
    """
    try:
        days = int(request.GET.get('days', 30))

        translation_service = ConversationTranslationService()
        stats = translation_service.get_translation_stats(days=days)

        # Add user-specific stats if needed
        user_translations = WisdomConversationTranslation.objects.filter(
            tenant=request.user.tenant
        ).count()

        stats['user_tenant_translations'] = user_translations
        stats['period_days'] = days

        return Response({
            'success': True,
            'data': stats
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Get translation analytics API error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to get analytics',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_translate_conversations(request):
    """
    Batch translate multiple conversations

    POST /api/wellness/batch-translate/
    {
        "conversation_ids": ["123", "456", "789"],
        "target_language": "hi",
        "max_translations": 50
    }
    """
    try:
        conversation_ids = request.data.get('conversation_ids', [])
        target_language = request.data.get('target_language')
        max_translations = request.data.get('max_translations', 50)

        if not conversation_ids or not target_language:
            return Response({
                'success': False,
                'error': 'conversation_ids and target_language are required',
                'code': 'MISSING_PARAMETERS'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get conversations with tenant filtering
        conversations = WisdomConversation.objects.filter(
            id__in=conversation_ids,
            tenant=request.user.tenant
        )

        if not conversations.exists():
            return Response({
                'success': False,
                'error': 'No valid conversations found',
                'code': 'NO_CONVERSATIONS'
            }, status=status.HTTP_404_NOT_FOUND)

        # Perform batch translation
        translation_service = ConversationTranslationService()
        result = translation_service.batch_translate_conversations(
            conversations=list(conversations),
            target_language=target_language,
            max_translations=max_translations
        )

        return Response({
            'success': True,
            'data': {
                'batch_result': result,
                'requested_conversations': len(conversation_ids),
                'found_conversations': conversations.count(),
                'target_language': target_language,
                'processing_summary': {
                    'successful': result['successful'],
                    'failed': result['failed'],
                    'skipped': result['skipped'],
                    'total_cost_estimate': result.get('cost_estimate', 0)
                },
                'errors': result.get('errors', [])
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Batch translate API error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Batch translation failed',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)