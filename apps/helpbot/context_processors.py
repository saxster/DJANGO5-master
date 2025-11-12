"""
HelpBot Context Processor

Provides HelpBot configuration and status to all templates.
Enables template access to HelpBot settings and user-specific data.
"""

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist


def helpbot_context(request):
    """
    Add HelpBot configuration and status to template context.

    Args:
        request: Django request object

    Returns:
        Dictionary with HelpBot context data
    """
    context = {
        'helpbot': {
            'enabled': getattr(settings, 'HELPBOT_ENABLED', True),
            'voice_enabled': getattr(settings, 'HELPBOT_VOICE_ENABLED', False),
            'max_message_length': getattr(settings, 'HELPBOT_MAX_MESSAGE_LENGTH', 2000),
            'widget_position': getattr(settings, 'HELPBOT_WIDGET_POSITION', 'bottom-right'),
            'widget_theme': getattr(settings, 'HELPBOT_WIDGET_THEME', 'modern'),
            'show_typing_indicator': getattr(settings, 'HELPBOT_SHOW_TYPING_INDICATOR', True),
            'enable_quick_suggestions': getattr(settings, 'HELPBOT_ENABLE_QUICK_SUGGESTIONS', True),
            'languages': getattr(settings, 'HELPBOT_LANGUAGES', ['en']),
        }
    }

    # Add user-specific context if authenticated
    if request.user.is_authenticated:
        context['helpbot'].update({
            'user_authenticated': True,
            'can_access_analytics': request.user.is_staff or getattr(request.user, 'isadmin', False),
            'preferred_language': getattr(request.user, 'language', 'en'),
        })

        # Check for active HelpBot session
        try:
            from apps.helpbot.models import HelpBotSession
            active_session = HelpBotSession.objects.filter(
                user=request.user,
                current_state__in=['active', 'waiting']
            ).first()

            context['helpbot']['has_active_session'] = bool(active_session)
            if active_session:
                context['helpbot']['active_session_id'] = str(active_session.session_id)
                context['helpbot']['active_session_type'] = active_session.session_type

        except (ImportError, ObjectDoesNotExist):
            # Fail silently if HelpBot models aren't available yet
            context['helpbot']['has_active_session'] = False

    else:
        context['helpbot']['user_authenticated'] = False

    return context