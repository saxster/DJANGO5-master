"""
Wellness Views Package

Modular view organization for the wellness application.
Exports views from both the package modules and the main views module.
"""

# Defer main views import to avoid circular dependencies
# Import statement will be at the end of this file

from .wisdom_conversation_views import (
    conversations_with_wisdom_view,
    toggle_conversation_bookmark,
    track_conversation_engagement,
    conversation_reflection_view,
    conversation_export_view,
    conversation_analytics_api,
    conversation_search_api,
)

from .translation_api_views import (
    translate_conversation,
    get_supported_languages,
    get_translation_status,
    submit_translation_feedback,
    get_translation_analytics,
    batch_translate_conversations,
)

# Create lazy import wrapper for main views
def _get_main_views_module():
    """Lazy load main views to avoid circular import"""
    import importlib
    return importlib.import_module('apps.wellness.views')

# Create module-level attributes that lazily load from main views
class _LazyViewProxy:
    """Proxy that lazily loads views from main views module"""
    def __init__(self, view_name):
        self.view_name = view_name
        self._view = None

    def __call__(self, *args, **kwargs):
        if self._view is None:
            main_views = _get_main_views_module()
            self._view = getattr(main_views, self.view_name)
        return self._view(*args, **kwargs)

    def as_view(self):
        if self._view is None:
            main_views = _get_main_views_module()
            self._view = getattr(main_views, self.view_name)
        return self._view.as_view()

# Export main viewsets using lazy proxies
WellnessContentViewSet = _LazyViewProxy('WellnessContentViewSet')
DailyWellnessTipView = _LazyViewProxy('DailyWellnessTipView')
ContextualWellnessContentView = _LazyViewProxy('ContextualWellnessContentView')
PersonalizedWellnessContentView = _LazyViewProxy('PersonalizedWellnessContentView')
WellnessProgressView = _LazyViewProxy('WellnessProgressView')
WellnessAnalyticsView = _LazyViewProxy('WellnessAnalyticsView')

__all__ = [
    # Main ViewSets from views.py
    'WellnessContentViewSet',
    'DailyWellnessTipView',
    'ContextualWellnessContentView',
    'PersonalizedWellnessContentView',
    'WellnessProgressView',
    'WellnessAnalyticsView',

    # Wisdom Conversation Views
    'conversations_with_wisdom_view',
    'toggle_conversation_bookmark',
    'track_conversation_engagement',
    'conversation_reflection_view',
    'conversation_export_view',
    'conversation_analytics_api',
    'conversation_search_api',

    # Translation API Views
    'translate_conversation',
    'get_supported_languages',
    'get_translation_status',
    'submit_translation_feedback',
    'get_translation_analytics',
    'batch_translate_conversations',
]
