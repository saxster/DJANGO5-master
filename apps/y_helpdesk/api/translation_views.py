"""
Ticket Translation API Views

Endpoints for translating helpdesk tickets between multiple languages.

Features:
- GET /api/v1/help-desk/tickets/<id>/translate/ - Translate ticket
- Query parameter: lang (en, hi, te, es)
- Cached responses for performance
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from apps.api.permissions import TenantIsolationPermission
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.services.ticket_translation_service import TicketTranslationService
from apps.y_helpdesk.exceptions import TRANSLATION_EXCEPTIONS, API_EXCEPTIONS
from apps.ontology.decorators import ontology

logger = logging.getLogger(__name__)


@ontology(
    domain="helpdesk",
    purpose="Translate ticket descriptions to multiple languages (English, Hindi, Telugu, Spanish)",
    api_endpoint=True,
    http_methods=["POST"],
    authentication_required=True,
    permissions=["IsAuthenticated", "TenantIsolationPermission"],
    rate_limit="50/minute",
    request_schema={
        "body_params": {
            "lang": "str (en|hi|te|es) - target language code",
            "use_cache": "bool (optional) - whether to use cached translations, default: true"
        }
    },
    response_schema={
        "success": "bool",
        "original_text": "str",
        "translated_text": "str",
        "original_language": "str",
        "target_language": "str",
        "cached": "bool",
        "confidence": "float",
        "warning": "str|null"
    },
    error_codes=[400, 401, 403, 404, 500],
    criticality="medium",
    tags=["api", "rest", "helpdesk", "translation", "multilingual"],
    security_notes="Tenant isolation via ticket permission check. Changed from GET to POST for CSRF protection and REST compliance.",
    endpoints={
        "translate": "POST /api/v1/help-desk/tickets/{id}/translate/ - Translate ticket to target language"
    },
    examples=[
        "curl -X POST 'https://api.example.com/api/v1/help-desk/tickets/123/translate/' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{\"lang\": \"hi\"}'",
        "curl -X POST 'https://api.example.com/api/v1/help-desk/tickets/456/translate/' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{\"lang\": \"te\", \"use_cache\": false}'"
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, TenantIsolationPermission])
def ticket_translation_view(request, ticket_id):
    """
    Translate a ticket description to target language.

    POST /api/v1/help-desk/tickets/<id>/translate/

    Request Body:
        {
            "lang": "hi",  // Target language code (en, hi, te, es)
            "use_cache": true  // Optional: whether to use cached translations
        }

    Response:
        {
            "success": true,
            "ticket_id": 123,
            "original_language": "en",
            "target_language": "hi",
            "original_text": "Server is down",
            "translated_text": "सर्वर डाउन है",
            "cached": false,
            "confidence": 0.95,
            "warning": "Translation provided by google. Please review for accuracy."
        }

    Security Note:
        Changed from GET to POST to enforce CSRF protection and comply with REST
        principles (cache writes are side effects, inappropriate for GET).
    """
    try:
        # Get target language from request body
        target_lang = request.data.get('lang', 'en').lower()
        use_cache = request.data.get('use_cache', True)

        # Validate language
        if target_lang not in TicketTranslationService.SUPPORTED_LANGUAGES:
            return Response(
                {
                    'success': False,
                    'error': f'Unsupported language: {target_lang}',
                    'supported_languages': TicketTranslationService.SUPPORTED_LANGUAGES,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get ticket with tenant isolation check
        ticket = get_object_or_404(
            Ticket.objects.filter(tenant=request.user.tenant),
            id=ticket_id
        )

        # Translate ticket
        translation_result = TicketTranslationService.translate_ticket(
            ticket=ticket,
            target_language=target_lang,
            use_cache=use_cache
        )

        # Add ticket_id to response
        translation_result['ticket_id'] = ticket_id

        # Return appropriate status based on success
        response_status = (
            status.HTTP_200_OK if translation_result.get('success')
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        logger.info(
            f"Translation requested for ticket {ticket_id} to {target_lang} "
            f"by user {request.user.username}. "
            f"Success: {translation_result.get('success')}"
        )

        return Response(translation_result, status=response_status)

    except Ticket.DoesNotExist:
        logger.warning(
            f"Translation requested for non-existent ticket {ticket_id} "
            f"by user {request.user.username}"
        )
        return Response(
            {'success': False, 'error': 'Ticket not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    except TRANSLATION_EXCEPTIONS as e:
        logger.error(
            f"Translation error for ticket {ticket_id}: {e}",
            exc_info=True
        )
        return Response(
            {
                'success': False,
                'error': 'Translation service error',
                'detail': str(e) if request.user.is_staff else None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def translation_stats_view(request):
    """
    Get translation service statistics.

    GET /api/v1/help-desk/translation/stats/

    Response:
        {
            "supported_languages": ["en", "hi", "te", "es"],
            "cache_ttl_seconds": 3600,
            "max_text_length": 5000,
            "technical_terms_preserved": 45
        }
    """
    try:
        stats = TicketTranslationService.get_translation_stats()
        return Response(stats, status=status.HTTP_200_OK)

    except API_EXCEPTIONS as e:
        logger.error(f"Error getting translation stats: {e}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Failed to get stats'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
