"""
HelpBot Conversation Service

Handles conversational interactions with users, integrating with existing LLM services
and the knowledge base for intelligent responses.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from django.conf import settings
from django.db import transaction, models
from django.utils import timezone
from django.core.cache import cache

from apps.helpbot.models import (
    HelpBotSession, HelpBotMessage, HelpBotContext, HelpBotFeedback
)
from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService
from apps.helpbot.services.context_service import HelpBotContextService
from django.core.exceptions import ValidationError
from apps.noc.security_intelligence.services import NonNegotiablesService

logger = logging.getLogger(__name__)


class HelpBotConversationService:
    """
    Core conversation management service for HelpBot.
    Integrates with existing LLM infrastructure and knowledge base.
    """

    def __init__(self):
        self.knowledge_service = HelpBotKnowledgeService()
        self.context_service = HelpBotContextService()
        self.non_negotiables_service = NonNegotiablesService()

        # Integration with existing LLM services
        self._init_llm_integration()

        # Parlant Agent Integration (NEW - Phase 3)
        self._init_parlant_integration()

        # Conversation configuration
        self.max_context_messages = getattr(settings, 'HELPBOT_MAX_CONTEXT_MESSAGES', 10)
        self.session_timeout_minutes = getattr(settings, 'HELPBOT_SESSION_TIMEOUT_MINUTES', 60)
        self.cache_timeout = getattr(settings, 'HELPBOT_CACHE_TIMEOUT', 3600)

    def _init_llm_integration(self):
        """Initialize integration with existing LLM services."""
        try:
            # Check if conversational AI services are available
            self.llm_enabled = getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False)

            if self.llm_enabled:
                # Import existing LLM services found in the codebase
                try:
                    from apps.onboarding_api.services.llm import get_llm_service
                    self.llm_service = get_llm_service()
                    logger.info("Integrated with existing LLM services")
                except ImportError:
                    logger.warning("Could not import existing LLM services, using fallback")
                    self.llm_service = None
            else:
                self.llm_service = None
                logger.info("LLM integration not enabled")

        except Exception as e:
            logger.error(f"Error initializing LLM integration: {e}")
            self.llm_service = None

    def _init_parlant_integration(self):
        """Initialize Parlant conversational AI agent (Phase 3)."""
        try:
            parlant_enabled = getattr(settings, 'ENABLE_PARLANT_AGENT', False)

            if parlant_enabled:
                try:
                    from apps.helpbot.services.parlant_agent_service import ParlantAgentService
                    self.parlant_service = ParlantAgentService()
                    logger.info("Parlant agent service initialized")
                except ImportError as e:
                    logger.warning(f"Could not import Parlant service: {e}")
                    logger.warning("Install Parlant: pip install parlant>=3.0")
                    self.parlant_service = None
            else:
                self.parlant_service = None
                logger.info("Parlant agent disabled (ENABLE_PARLANT_AGENT=False)")

        except Exception as e:
            logger.error(f"Error initializing Parlant integration: {e}")
            self.parlant_service = None

    def start_session(self, user, session_type: str = "general_help",
                     context_data: Dict[str, Any] = None, language: str = "en") -> HelpBotSession:
        """
        Start a new HelpBot conversation session.

        Args:
            user: Django user instance
            session_type: Type of help session
            context_data: Initial context data
            language: User's preferred language

        Returns:
            HelpBotSession instance
        """
        try:
            with transaction.atomic():
                # Check for existing active session
                active_session = self._get_active_session(user)
                if active_session:
                    logger.debug(f"Resuming existing session {active_session.session_id}")
                    return active_session

                # Create new session
                session = HelpBotSession.objects.create(
                    user=user,
                    session_type=session_type,
                    context_data=context_data or {},
                    language=language,
                    current_state=HelpBotSession.StateChoices.ACTIVE
                )

                # Add welcome message
                welcome_message = self._generate_welcome_message(session)
                self._add_message(
                    session=session,
                    message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
                    content=welcome_message['content'],
                    rich_content=welcome_message.get('rich_content', {}),
                    confidence_score=1.0
                )

                logger.info(f"Started HelpBot session {session.session_id} for user {user.email}")
                return session

        except Exception as e:
            logger.error(f"Error starting HelpBot session: {e}")
            raise

    def _get_active_session(self, user) -> Optional[HelpBotSession]:
        """Get active session for user if exists and not expired."""
        try:
            cutoff_time = timezone.now() - timedelta(minutes=self.session_timeout_minutes)

            return HelpBotSession.objects.filter(
                user=user,
                current_state__in=[
                    HelpBotSession.StateChoices.ACTIVE,
                    HelpBotSession.StateChoices.WAITING
                ],
                last_activity__gte=cutoff_time
            ).first()

        except Exception as e:
            logger.error(f"Error getting active session: {e}")
            return None

    def _generate_welcome_message(self, session: HelpBotSession) -> Dict[str, Any]:
        """Generate contextual welcome message based on session type and user context."""
        try:
            # Get user context
            context = self.context_service.get_current_context(session.user)

            # Base welcome message
            base_messages = {
                HelpBotSession.SessionTypeChoices.GENERAL_HELP:
                    "👋 Hi! I'm your AI assistant. I can help you with questions about using the platform, features, and troubleshooting.",

                HelpBotSession.SessionTypeChoices.FEATURE_GUIDE:
                    "🚀 Great! I'll help you learn about the platform features. What would you like to explore?",

                HelpBotSession.SessionTypeChoices.TROUBLESHOOTING:
                    "🔧 I'm here to help troubleshoot any issues you're experiencing. What problem can I help you solve?",

                HelpBotSession.SessionTypeChoices.API_DOCUMENTATION:
                    "📚 I can help you with API documentation, endpoints, and integration examples. What API information do you need?",

                HelpBotSession.SessionTypeChoices.TUTORIAL:
                    "📖 I'll guide you through tutorials step-by-step. What would you like to learn?",

                HelpBotSession.SessionTypeChoices.ONBOARDING:
                    "🌟 Welcome! I'll help you get started with the platform. Let's begin with the basics.",

                HelpBotSession.SessionTypeChoices.SECURITY_FACILITY:
                    "🛡️ Welcome to your Security & Facility Mentor! I monitor your 7 non-negotiables and help you maintain operational excellence. Let me show you today's scorecard."
            }

            welcome_content = base_messages.get(
                session.session_type,
                base_messages[HelpBotSession.SessionTypeChoices.GENERAL_HELP]
            )

            # Add context-specific information if available
            rich_content = {
                "suggestions": self._generate_contextual_suggestions(context, session.session_type),
                "quick_actions": self._generate_quick_actions(session.session_type, context),
            }

            return {
                "content": welcome_content,
                "rich_content": rich_content
            }

        except Exception as e:
            logger.error(f"Error generating welcome message: {e}")
            return {
                "content": "Hi! I'm here to help you. What can I assist you with today?",
                "rich_content": {}
            }

    def _generate_contextual_suggestions(self, context: Optional[HelpBotContext], session_type: str = None) -> List[str]:
        """Generate contextual suggestions based on user's current page/context."""
        suggestions = []

        # Security & Facility Mentor specific suggestions
        if session_type == HelpBotSession.SessionTypeChoices.SECURITY_FACILITY:
            return [
                "Show me today's scorecard",
                "Which pillars need attention?",
                "What violations occurred today?",
                "Generate client summary report"
            ]

        if not context:
            return [
                "How do I get started?",
                "Show me the main features",
                "I need help with navigation",
                "Common questions"
            ]

        # Context-based suggestions
        if context.app_name == 'activity':
            suggestions = [
                "How do I create a new task?",
                "Explain task scheduling",
                "Asset management help",
                "Tour management guide"
            ]
        elif context.app_name == 'peoples':
            suggestions = [
                "Managing user accounts",
                "Attendance tracking",
                "User permissions",
                "Employee directory"
            ]
        elif context.app_name == 'reports':
            suggestions = [
                "Generating reports",
                "Report scheduling",
                "Export options",
                "Custom report creation"
            ]
        elif context.app_name == 'y_helpdesk':
            suggestions = [
                "Creating support tickets",
                "Ticket escalation",
                "Status management",
                "Help desk workflow"
            ]

        # Add error-specific suggestions if there's an error context
        if context.error_context:
            suggestions.insert(0, "Help with this error")

        return suggestions[:4]  # Limit to 4 suggestions

    def _generate_quick_actions(self, session_type: str, context: Optional[HelpBotContext]) -> List[Dict[str, str]]:
        """Generate quick action buttons based on session type and context."""
        actions = []

        if session_type == HelpBotSession.SessionTypeChoices.GENERAL_HELP:
            actions = [
                {"label": "📋 Features Guide", "action": "show_features"},
                {"label": "🔧 Troubleshooting", "action": "troubleshooting"},
                {"label": "📚 Documentation", "action": "documentation"},
                {"label": "❓ FAQ", "action": "faq"}
            ]
        elif session_type == HelpBotSession.SessionTypeChoices.TROUBLESHOOTING:
            actions = [
                {"label": "🔍 Common Issues", "action": "common_issues"},
                {"label": "🚨 Error Help", "action": "error_help"},
                {"label": "⚙️ Settings", "action": "settings_help"},
                {"label": "📞 Contact Support", "action": "contact_support"}
            ]
        elif session_type == HelpBotSession.SessionTypeChoices.API_DOCUMENTATION:
            actions = [
                {"label": "🔗 API Endpoints", "action": "api_endpoints"},
                {"label": "🔑 Authentication", "action": "api_auth"},
                {"label": "📋 Examples", "action": "api_examples"},
                {"label": "📖 Reference", "action": "api_reference"}
            ]
        elif session_type == HelpBotSession.SessionTypeChoices.SECURITY_FACILITY:
            actions = [
                {"label": "📊 View Scorecard", "action": "show_scorecard"},
                {"label": "🚨 Critical Violations", "action": "show_violations"},
                {"label": "📈 7-Day Trends", "action": "show_trends"},
                {"label": "📄 Generate Report", "action": "generate_report"}
            ]

        return actions

    def process_message(self, session: HelpBotSession, user_message: str,
                       message_type: str = "user_text") -> Dict[str, Any]:
        """
        Process a user message and generate AI response.

        Args:
            session: HelpBot session
            user_message: User's message content
            message_type: Type of message (user_text, user_voice, etc.)

        Returns:
            Dictionary with bot response and metadata
        """
        try:
            start_time = datetime.now()

            with transaction.atomic():
                # Add user message
                user_msg = self._add_message(
                    session=session,
                    message_type=message_type,
                    content=user_message
                )

                # Update session state
                session.current_state = HelpBotSession.StateChoices.WAITING
                session.total_messages = models.F('total_messages') + 1
                session.save(update_fields=['current_state', 'total_messages'])

                # Generate AI response
                response = self._generate_ai_response(session, user_message)

                # Add bot response
                bot_msg = self._add_message(
                    session=session,
                    message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
                    content=response['content'],
                    rich_content=response.get('rich_content', {}),
                    knowledge_sources=response.get('knowledge_sources', []),
                    confidence_score=response.get('confidence_score', 0.5),
                    processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                )

                # Update session state
                session.current_state = HelpBotSession.StateChoices.ACTIVE
                session.save(update_fields=['current_state'])

                logger.info(f"Processed message in session {session.session_id}")

                return {
                    "success": True,
                    "response": {
                        "message_id": str(bot_msg.message_id),
                        "content": response['content'],
                        "rich_content": response.get('rich_content', {}),
                        "confidence_score": response.get('confidence_score', 0.5),
                        "knowledge_sources": response.get('knowledge_sources', []),
                        "suggestions": response.get('suggestions', [])
                    }
                }

        except Exception as e:
            logger.error(f"Error processing message: {e}")

            # Add error message
            error_response = self._generate_error_response(str(e))
            self._add_message(
                session=session,
                message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
                content=error_response['content']
            )

            return {
                "success": False,
                "error": str(e),
                "response": error_response
            }

    def _add_message(self, session: HelpBotSession, message_type: str, content: str,
                    rich_content: Dict = None, knowledge_sources: List = None,
                    confidence_score: float = None, processing_time_ms: int = None) -> HelpBotMessage:
        """Add a message to the conversation."""
        return HelpBotMessage.objects.create(
            session=session,
            message_type=message_type,
            content=content,
            rich_content=rich_content or {},
            knowledge_sources=knowledge_sources or [],
            confidence_score=confidence_score,
            processing_time_ms=processing_time_ms,
            metadata={}
        )

    def _generate_ai_response(self, session: HelpBotSession, user_message: str) -> Dict[str, Any]:
        """Generate AI response using Parlant, knowledge base, or LLM services."""
        try:
            # Try Parlant first for SECURITY_FACILITY sessions (Phase 3)
            if (self.parlant_service and
                session.session_type == HelpBotSession.SessionTypeChoices.SECURITY_FACILITY):
                try:
                    parlant_response = self.parlant_service.process_message_sync(
                        session_id=str(session.session_id),
                        user_message=user_message,
                        session_data={
                            'tenant': session.tenant,
                            'client': session.client or session.user.bu,
                            'user': session.user,
                        }
                    )

                    if parlant_response.get('success'):
                        logger.info("Using Parlant-powered response")
                        return {
                            'content': parlant_response['content'],
                            'confidence_score': parlant_response.get('confidence_score', 0.9),
                            'knowledge_sources': [],
                            'rich_content': {
                                'parlant_powered': True,
                                'tools_used': parlant_response.get('tools_used', []),
                                'guidelines_matched': parlant_response.get('guidelines_matched', []),
                                'journey_state': parlant_response.get('journey_state'),
                            }
                        }
                    else:
                        logger.warning(f"Parlant failed: {parlant_response.get('error')}, using fallback")
                except Exception as e:
                    logger.warning(f"Parlant processing error: {e}, using fallback")

            # Fallback to existing template/LLM approach
            # Analyze user intent
            intent_analysis = self._analyze_user_intent(user_message, session)

            # Search knowledge base
            knowledge_results = self.knowledge_service.search_knowledge(
                query=user_message,
                category=intent_analysis.get('category'),
                limit=5
            )

            # Get conversation context
            conversation_context = self._get_conversation_context(session)

            # Generate response using LLM if available
            if self.llm_service:
                response = self._generate_llm_response(
                    user_message, knowledge_results, conversation_context, session
                )
            else:
                response = self._generate_template_response(
                    user_message, knowledge_results, intent_analysis
                )

            # Add follow-up suggestions
            response['suggestions'] = self._generate_followup_suggestions(
                user_message, intent_analysis, knowledge_results
            )

            return response

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return self._generate_fallback_response(user_message)

    def _analyze_user_intent(self, message: str, session: HelpBotSession) -> Dict[str, Any]:
        """Analyze user intent from message content."""
        message_lower = message.lower()

        # Simple intent classification based on keywords
        intent_keywords = {
            'troubleshooting': ['error', 'problem', 'issue', 'not working', 'broken', 'bug', 'fix', 'trouble'],
            'how_to': ['how', 'how to', 'tutorial', 'guide', 'step', 'instructions'],
            'api': ['api', 'endpoint', 'rest', 'graphql', 'authentication', 'token'],
            'navigation': ['navigate', 'find', 'where', 'menu', 'page', 'section'],
            'features': ['feature', 'capability', 'function', 'what does', 'what can'],
        }

        category_keywords = {
            'operations': ['task', 'tour', 'schedule', 'work order', 'operation'],
            'assets': ['asset', 'inventory', 'equipment', 'maintenance'],
            'people': ['user', 'employee', 'people', 'attendance', 'staff'],
            'helpdesk': ['ticket', 'support', 'help desk', 'escalation'],
            'reports': ['report', 'analytics', 'dashboard', 'export', 'data'],
            'administration': ['admin', 'settings', 'configuration', 'setup'],
        }

        # Determine intent
        intent = 'general'
        for intent_type, keywords in intent_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                intent = intent_type
                break

        # Determine category
        category = None
        for cat, keywords in category_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                category = cat
                break

        # Determine urgency
        urgency_keywords = ['urgent', 'asap', 'immediately', 'critical', 'emergency']
        urgency = 'high' if any(keyword in message_lower for keyword in urgency_keywords) else 'normal'

        return {
            'intent': intent,
            'category': category,
            'urgency': urgency,
            'message_length': len(message),
            'has_question_mark': '?' in message,
        }

    def _get_conversation_context(self, session: HelpBotSession) -> List[Dict[str, Any]]:
        """Get recent conversation messages for context."""
        recent_messages = HelpBotMessage.objects.filter(
            session=session
        ).order_by('-cdtz')[:self.max_context_messages]

        context = []
        for msg in reversed(recent_messages):  # Reverse to get chronological order
            context.append({
                'type': msg.message_type,
                'content': msg.content,
                'timestamp': msg.cdtz.isoformat(),
            })

        return context

    def _generate_llm_response(self, user_message: str, knowledge_results: List[Dict],
                              context: List[Dict], session: HelpBotSession) -> Dict[str, Any]:
        """Generate response using existing LLM services."""
        try:
            # Prepare context for LLM
            llm_context = {
                'user_message': user_message,
                'knowledge_sources': knowledge_results,
                'conversation_history': context,
                'session_type': session.session_type,
                'user_context': session.context_data,
            }

            # Use existing LLM service
            llm_response = self.llm_service.process_conversation_step(
                session=session,
                user_input=user_message,
                context=llm_context
            )

            # Format response
            return {
                'content': llm_response.get('response', 'I apologize, but I could not generate a proper response.'),
                'confidence_score': llm_response.get('confidence_score', 0.5),
                'knowledge_sources': [{'id': kr['id'], 'title': kr['title']} for kr in knowledge_results],
                'rich_content': self._format_rich_content(knowledge_results),
            }

        except Exception as e:
            logger.error(f"Error with LLM response generation: {e}")
            return self._generate_template_response(user_message, knowledge_results, {})

    def _generate_template_response(self, user_message: str, knowledge_results: List[Dict],
                                   intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using template-based approach when LLM is not available."""
        try:
            if knowledge_results:
                # Use knowledge base results
                best_result = knowledge_results[0]

                response_content = f"Based on the documentation, here's what I found:\n\n"
                response_content += f"**{best_result['title']}**\n\n"
                response_content += best_result['content']

                if len(knowledge_results) > 1:
                    response_content += f"\n\nI also found {len(knowledge_results) - 1} other related articles that might help."

                return {
                    'content': response_content,
                    'confidence_score': 0.8,
                    'knowledge_sources': [{'id': kr['id'], 'title': kr['title']} for kr in knowledge_results],
                    'rich_content': self._format_rich_content(knowledge_results),
                }
            else:
                # No knowledge found, provide general response
                intent = intent_analysis.get('intent', 'general')

                template_responses = {
                    'troubleshooting': "I understand you're experiencing an issue. Let me help you troubleshoot. Can you provide more details about what's not working?",
                    'how_to': "I'd be happy to guide you through that process. Could you be more specific about what you'd like to learn?",
                    'api': "For API-related questions, I can help you with endpoints, authentication, and examples. What specific API information do you need?",
                    'navigation': "I can help you find your way around the platform. What specific section or feature are you looking for?",
                    'features': "I can explain the platform's features and capabilities. What particular functionality would you like to know about?",
                }

                content = template_responses.get(
                    intent,
                    "I'm here to help! Could you provide a bit more detail about what you're looking for? I can assist with features, troubleshooting, documentation, and more."
                )

                return {
                    'content': content,
                    'confidence_score': 0.3,
                    'knowledge_sources': [],
                    'rich_content': {},
                }

        except Exception as e:
            logger.error(f"Error generating template response: {e}")
            return self._generate_fallback_response(user_message)

    def _format_rich_content(self, knowledge_results: List[Dict]) -> Dict[str, Any]:
        """Format rich content from knowledge results."""
        rich_content = {}

        if knowledge_results:
            # Add related articles
            rich_content['related_articles'] = [
                {
                    'id': kr['id'],
                    'title': kr['title'],
                    'category': kr['category'],
                    'type': kr['knowledge_type'],
                }
                for kr in knowledge_results[:3]
            ]

            # Add relevant URLs if available
            all_urls = []
            for kr in knowledge_results:
                if 'related_urls' in kr:
                    all_urls.extend(kr['related_urls'])

            if all_urls:
                rich_content['helpful_links'] = list(set(all_urls))[:5]

        return rich_content

    def _generate_followup_suggestions(self, user_message: str, intent_analysis: Dict[str, Any],
                                     knowledge_results: List[Dict]) -> List[str]:
        """Generate follow-up suggestions based on the conversation."""
        suggestions = []

        # Intent-based suggestions
        intent = intent_analysis.get('intent', 'general')
        category = intent_analysis.get('category')

        if intent == 'troubleshooting':
            suggestions.extend([
                "Show me common solutions",
                "Contact support",
                "Try another approach",
            ])
        elif intent == 'how_to':
            suggestions.extend([
                "Show me a tutorial",
                "Step-by-step guide",
                "Related features",
            ])
        elif intent == 'api':
            suggestions.extend([
                "API examples",
                "Authentication help",
                "Endpoint reference",
            ])

        # Category-based suggestions
        if category:
            category_suggestions = {
                'operations': ["Task management", "Tour scheduling", "Work orders"],
                'assets': ["Asset tracking", "Maintenance logs", "Inventory"],
                'people': ["User management", "Attendance", "Permissions"],
                'helpdesk': ["Create ticket", "Track issues", "Escalations"],
                'reports': ["Generate report", "Export data", "Analytics"],
            }
            suggestions.extend(category_suggestions.get(category, []))

        # Knowledge-based suggestions
        if knowledge_results:
            for result in knowledge_results[:2]:
                suggestions.append(f"More about {result['title']}")

        return suggestions[:4]  # Limit to 4 suggestions

    def _generate_fallback_response(self, user_message: str) -> Dict[str, Any]:
        """Generate fallback response when other methods fail."""
        return {
            'content': "I apologize, but I'm having trouble understanding your question right now. Could you please rephrase it or try asking about a specific feature or topic?",
            'confidence_score': 0.1,
            'knowledge_sources': [],
            'rich_content': {
                'suggestions': [
                    "How do I get started?",
                    "Show me the main features",
                    "Common questions",
                    "Contact support"
                ]
            },
        }

    def _generate_error_response(self, error_message: str) -> Dict[str, Any]:
        """Generate error response for system errors."""
        return {
            'content': "I encountered an technical issue while processing your request. Please try again or contact support if the problem persists.",
            'confidence_score': 0.0,
            'knowledge_sources': [],
            'rich_content': {
                'error': True,
                'suggestions': [
                    "Try asking again",
                    "Rephrase your question",
                    "Contact support"
                ]
            },
        }

    def add_feedback(self, session: HelpBotSession, message_id: str,
                    feedback_type: str, rating: int = None, comment: str = None) -> bool:
        """Add user feedback for a specific message."""
        try:
            message = HelpBotMessage.objects.get(message_id=message_id, session=session)

            feedback = HelpBotFeedback.objects.create(
                session=session,
                message=message,
                user=session.user,
                feedback_type=feedback_type,
                rating=rating,
                comment=comment,
                context_data=session.context_data
            )

            # Update knowledge effectiveness if applicable
            if message.knowledge_sources and rating:
                for source in message.knowledge_sources:
                    if 'id' in source:
                        # Convert 1-5 rating to 0-1 effectiveness score
                        effectiveness_score = (rating - 1) / 4.0
                        self.knowledge_service.update_knowledge_effectiveness(
                            source['id'], effectiveness_score
                        )

            logger.info(f"Added feedback {feedback.feedback_id} for message {message_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding feedback: {e}")
            return False

    def end_session(self, session: HelpBotSession, satisfaction_rating: int = None) -> bool:
        """End a HelpBot session."""
        try:
            session.current_state = HelpBotSession.StateChoices.COMPLETED
            if satisfaction_rating:
                session.satisfaction_rating = satisfaction_rating
            session.save(update_fields=['current_state', 'satisfaction_rating'])

            logger.info(f"Ended session {session.session_id}")
            return True

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return False

    def get_session_history(self, session: HelpBotSession) -> List[Dict[str, Any]]:
        """Get complete session message history."""
        try:
            messages = HelpBotMessage.objects.filter(
                session=session
            ).order_by('cdtz')

            history = []
            for message in messages:
                history.append({
                    'id': str(message.message_id),
                    'type': message.message_type,
                    'content': message.content,
                    'rich_content': message.rich_content,
                    'timestamp': message.cdtz.isoformat(),
                    'confidence_score': message.confidence_score,
                    'knowledge_sources': message.knowledge_sources,
                })

            return history

        except Exception as e:
            logger.error(f"Error getting session history: {e}")
            return []

    def generate_security_scorecard(self, session: HelpBotSession, check_date=None) -> Dict[str, Any]:
        """
        Generate Security & Facility Mentor scorecard for current user's client.

        Args:
            session: HelpBot session
            check_date: Date to evaluate (defaults to today)

        Returns:
            Dictionary with scorecard data formatted for chat display
        """
        try:
            user = session.user
            tenant = session.tenant
            client = session.client or user.bu

            if not client:
                return {
                    'success': False,
                    'error': 'No client/business unit associated with user'
                }

            # Generate scorecard
            scorecard = self.non_negotiables_service.generate_scorecard(
                tenant=tenant,
                client=client,
                check_date=check_date
            )

            # Format for chat display
            pillar_data = [
                {
                    'pillar_id': 1,
                    'name': 'Right Guard at Right Post',
                    'score': scorecard.pillar_1_score,
                    'status': scorecard.pillar_1_status,
                    'violations': scorecard.violations_detail.get('pillar_1', [])
                },
                {
                    'pillar_id': 2,
                    'name': 'Supervise Relentlessly',
                    'score': scorecard.pillar_2_score,
                    'status': scorecard.pillar_2_status,
                    'violations': scorecard.violations_detail.get('pillar_2', [])
                },
                {
                    'pillar_id': 3,
                    'name': '24/7 Control Desk',
                    'score': scorecard.pillar_3_score,
                    'status': scorecard.pillar_3_status,
                    'violations': scorecard.violations_detail.get('pillar_3', [])
                },
                {
                    'pillar_id': 4,
                    'name': 'Legal & Professional',
                    'score': scorecard.pillar_4_score,
                    'status': scorecard.pillar_4_status,
                    'violations': scorecard.violations_detail.get('pillar_4', [])
                },
                {
                    'pillar_id': 5,
                    'name': 'Support the Field',
                    'score': scorecard.pillar_5_score,
                    'status': scorecard.pillar_5_status,
                    'violations': scorecard.violations_detail.get('pillar_5', [])
                },
                {
                    'pillar_id': 6,
                    'name': 'Record Everything',
                    'score': scorecard.pillar_6_score,
                    'status': scorecard.pillar_6_status,
                    'violations': scorecard.violations_detail.get('pillar_6', [])
                },
                {
                    'pillar_id': 7,
                    'name': 'Respond to Emergencies',
                    'score': scorecard.pillar_7_score,
                    'status': scorecard.pillar_7_status,
                    'violations': scorecard.violations_detail.get('pillar_7', [])
                },
            ]

            return {
                'success': True,
                'scorecard': {
                    'check_date': scorecard.check_date.isoformat(),
                    'client_name': client.buname,
                    'overall_health_status': scorecard.overall_health_status,
                    'overall_health_score': scorecard.overall_health_score,
                    'total_violations': scorecard.total_violations,
                    'critical_violations': scorecard.critical_violations,
                    'pillars': pillar_data,
                    'recommendations': scorecard.recommendations,
                    'auto_escalated_alerts': scorecard.auto_escalated_alerts,
                }
            }

        except Exception as e:
            logger.error(f"Error generating security scorecard: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }