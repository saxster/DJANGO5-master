"""
Feature flags for gradual rollout.

Usage:
    from django.conf import settings
    if settings.FEATURES['HELPBOT_USE_ONTOLOGY']:
        # Use ontology
"""

FEATURES = {
    # Phase 2: HelpBot ontology integration
    'HELPBOT_USE_ONTOLOGY': False,  # Default: OFF (manual enable)

    # Phase 3: Article auto-generation
    'ENABLE_ARTICLE_AUTO_GENERATION': False,

    # Phase 4: Unified knowledge service
    'USE_UNIFIED_KNOWLEDGE': False,
}
