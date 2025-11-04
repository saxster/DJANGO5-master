"""
Views for conversational onboarding UI
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.conf import settings


@login_required
@require_http_methods(["GET"])
def conversational_onboarding_ui(request):
    """
    Serve the conversational onboarding UI
    """
    context = {
        'enable_sse': getattr(settings, 'ENABLE_ONBOARDING_SSE', False),
        'api_base': '/api/v1/onboarding',
        'user': request.user,
        'csrf_token': request.META.get('CSRF_COOKIE'),
    }

    return render(request, 'onboarding/conversational/index.html', context)


@login_required
@require_http_methods(["GET"])
def ui_config(request):
    """
    Return UI configuration as JSON including voice capabilities
    """
    # Check voice service availability
    from apps.core_onboarding.services.speech_service import OnboardingSpeechService
    speech_service = OnboardingSpeechService()

    config = {
        'api_base': '/api/v1/onboarding',
        'enable_sse': getattr(settings, 'ENABLE_ONBOARDING_SSE', False),
        'polling_interval': 2000,
        'max_retries': 3,
        'user': {
            'id': request.user.id,
            'name': getattr(request.user, 'peoplename', str(request.user)),
            'email': getattr(request.user, 'email', ''),
        },
        'voice': {
            'enabled': getattr(settings, 'ENABLE_ONBOARDING_VOICE_INPUT', True),
            'service_available': speech_service.is_service_available(),
            'supported_languages': speech_service.get_supported_languages(),
            'max_duration_seconds': getattr(
                settings,
                'ONBOARDING_VOICE_MAX_DURATION_SECONDS',
                60
            ),
            'max_file_size_mb': getattr(
                settings,
                'ONBOARDING_VOICE_MAX_FILE_SIZE_MB',
                10
            ),
            'default_language': getattr(
                settings,
                'ONBOARDING_VOICE_DEFAULT_LANGUAGE',
                'en-US'
            ),
            'supported_formats': [
                'audio/webm',
                'audio/wav',
                'audio/mp3',
                'audio/ogg',
                'audio/m4a'
            ]
        }
    }

    return JsonResponse(config)