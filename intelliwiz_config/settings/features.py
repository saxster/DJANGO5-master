"""
Feature flags for gradual rollout.

Usage:
    from django.conf import settings
    if settings.FEATURES['HELPBOT_USE_ONTOLOGY']:
        # Use ontology
"""

FEATURES = {
    # Phase 2: HelpBot ontology integration
    # ✅ ENABLED after passing Phase 2 performance gate (2025-11-12)
    # Performance: P95 latency 0.26ms (500x under 500ms threshold)
    # See: PHASE2_GATE_RESULTS.md for full test results
    'HELPBOT_USE_ONTOLOGY': True,

    # Phase 3: Article auto-generation
    # ✅ ENABLED after passing Phase 3 performance gate (2025-11-12)
    # Performance: Duration 1.76 minutes (6x under 10 min threshold)
    #              Memory delta -143.62 MB (well under 200 MB threshold)
    #              106 components processed, 94 articles created, 11 updated, 1 error
    # See: tests/performance/test_phase3_gate.py for full test results
    'ENABLE_ARTICLE_AUTO_GENERATION': True,

    # Phase 4: Unified knowledge service
    'USE_UNIFIED_KNOWLEDGE': False,
}
