"""
AI HelpBot Application

Provides intelligent, context-aware help and support using RAG (Retrieval Augmented Generation)
and the existing AI infrastructure including txtai, semantic search, and knowledge management.

Features:
- Conversational help interface with natural language processing
- Context-aware assistance based on current page/feature
- Multi-modal support (text, voice, visual)
- Integration with existing knowledge base and documentation
- Real-time chat with WebSocket support
- Multi-language support using existing localization
- Analytics and continuous improvement through user feedback
"""

default_app_config = 'apps.helpbot.apps.HelpBotConfig'

__version__ = '1.0.0'