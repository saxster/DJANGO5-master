"""
Help Center Application

Django-native help system with AI-powered assistance, contextual widgets,
and ticket correlation analytics.

Features:
- Knowledge base with hybrid search (FTS + pgvector semantic search)
- RAG-powered AI assistant for conversational help
- Contextual help widgets (floating button, tooltips, guided tours)
- Help-to-ticket correlation for effectiveness tracking
"""

default_app_config = 'apps.help_center.apps.HelpCenterConfig'
