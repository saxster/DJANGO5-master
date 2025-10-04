"""
HelpBot GraphQL Schema

Provides GraphQL queries and mutations for HelpBot functionality.
Integrates with existing GraphQL infrastructure.
"""

import graphene
from graphene_django import DjangoObjectType
from graphql_jwt.decorators import login_required
from django.core.exceptions import ValidationError
from typing import List

from apps.helpbot.models import (
    HelpBotSession, HelpBotMessage, HelpBotKnowledge, HelpBotFeedback, HelpBotContext
)
from apps.helpbot.services import (
    HelpBotConversationService, HelpBotKnowledgeService, HelpBotContextService
)


# GraphQL Types
class HelpBotSessionType(DjangoObjectType):
    """GraphQL type for HelpBot sessions."""

    class Meta:
        model = HelpBotSession
        fields = (
            'session_id', 'session_type', 'current_state', 'language',
            'voice_enabled', 'total_messages', 'satisfaction_rating',
            'last_activity', 'cdtz'
        )


class HelpBotMessageType(DjangoObjectType):
    """GraphQL type for HelpBot messages."""

    class Meta:
        model = HelpBotMessage
        fields = (
            'message_id', 'message_type', 'content', 'rich_content',
            'confidence_score', 'processing_time_ms', 'cdtz'
        )


class HelpBotKnowledgeType(DjangoObjectType):
    """GraphQL type for HelpBot knowledge."""

    class Meta:
        model = HelpBotKnowledge
        fields = (
            'knowledge_id', 'title', 'content', 'knowledge_type', 'category',
            'tags', 'search_keywords', 'usage_count', 'effectiveness_score',
            'is_active', 'last_updated'
        )


class HelpBotContextType(DjangoObjectType):
    """GraphQL type for HelpBot context."""

    class Meta:
        model = HelpBotContext
        fields = (
            'context_id', 'current_url', 'page_title', 'app_name',
            'view_name', 'user_role', 'timestamp'
        )


# Input types for mutations
class StartHelpBotSessionInput(graphene.InputObjectType):
    """Input for starting a HelpBot session."""
    session_type = graphene.String(default_value="general_help")
    language = graphene.String(default_value="en")
    context_data = graphene.JSONString()


class SendHelpBotMessageInput(graphene.InputObjectType):
    """Input for sending a HelpBot message."""
    session_id = graphene.String(required=True)
    message = graphene.String(required=True)
    message_type = graphene.String(default_value="user_text")


class HelpBotFeedbackInput(graphene.InputObjectType):
    """Input for HelpBot feedback."""
    session_id = graphene.String(required=True)
    message_id = graphene.String()
    feedback_type = graphene.String(required=True)
    rating = graphene.Int()
    comment = graphene.String()


# Query responses
class HelpBotSessionResponse(graphene.ObjectType):
    """Response for HelpBot session operations."""
    success = graphene.Boolean()
    session = graphene.Field(HelpBotSessionType)
    messages = graphene.List(HelpBotMessageType)
    context_suggestions = graphene.List(graphene.String)
    error = graphene.String()


class HelpBotMessageResponse(graphene.ObjectType):
    """Response for HelpBot message operations."""
    success = graphene.Boolean()
    message = graphene.Field(HelpBotMessageType)
    bot_response = graphene.JSONString()
    suggestions = graphene.List(graphene.String)
    error = graphene.String()


class HelpBotKnowledgeSearchResponse(graphene.ObjectType):
    """Response for knowledge search."""
    results = graphene.List(HelpBotKnowledgeType)
    total = graphene.Int()
    query = graphene.String()
    error = graphene.String()


# Queries
class HelpBotQueries(graphene.ObjectType):
    """HelpBot GraphQL queries."""

    # Session queries
    helpbot_active_session = graphene.Field(
        HelpBotSessionType,
        description="Get user's active HelpBot session"
    )

    helpbot_session_history = graphene.List(
        HelpBotMessageType,
        session_id=graphene.String(required=True),
        description="Get message history for a session"
    )

    # Knowledge queries
    helpbot_search_knowledge = graphene.Field(
        HelpBotKnowledgeSearchResponse,
        query=graphene.String(required=True),
        category=graphene.String(),
        limit=graphene.Int(default_value=10),
        description="Search HelpBot knowledge base"
    )

    helpbot_knowledge_article = graphene.Field(
        HelpBotKnowledgeType,
        knowledge_id=graphene.String(required=True),
        description="Get specific knowledge article"
    )

    # Context queries
    helpbot_current_context = graphene.Field(
        HelpBotContextType,
        description="Get user's current context"
    )

    @login_required
    def resolve_helpbot_active_session(self, info):
        """Get user's active HelpBot session."""
        try:
            return HelpBotSession.objects.filter(
                user=info.context.user,
                current_state__in=['active', 'waiting']
            ).first()
        except Exception:
            return None

    @login_required
    def resolve_helpbot_session_history(self, info, session_id):
        """Get message history for a session."""
        try:
            session = HelpBotSession.objects.get(
                session_id=session_id,
                user=info.context.user
            )
            return session.messages.all().order_by('cdtz')
        except HelpBotSession.DoesNotExist:
            return []

    @login_required
    def resolve_helpbot_search_knowledge(self, info, query, category=None, limit=10):
        """Search HelpBot knowledge base."""
        try:
            knowledge_service = HelpBotKnowledgeService()
            results = knowledge_service.search_knowledge(query, category, limit)

            # Convert dict results to model instances for GraphQL
            knowledge_objects = []
            for result in results:
                try:
                    knowledge = HelpBotKnowledge.objects.get(knowledge_id=result['id'])
                    knowledge_objects.append(knowledge)
                except HelpBotKnowledge.DoesNotExist:
                    continue

            return HelpBotKnowledgeSearchResponse(
                results=knowledge_objects,
                total=len(knowledge_objects),
                query=query
            )

        except Exception as e:
            return HelpBotKnowledgeSearchResponse(
                results=[],
                total=0,
                query=query,
                error=str(e)
            )

    @login_required
    def resolve_helpbot_knowledge_article(self, info, knowledge_id):
        """Get specific knowledge article."""
        try:
            return HelpBotKnowledge.objects.get(
                knowledge_id=knowledge_id,
                is_active=True
            )
        except HelpBotKnowledge.DoesNotExist:
            return None

    @login_required
    def resolve_helpbot_current_context(self, info):
        """Get user's current context."""
        try:
            context_service = HelpBotContextService()
            return context_service.get_current_context(info.context.user)
        except Exception:
            return None


# Mutations
class StartHelpBotSession(graphene.Mutation):
    """Start a new HelpBot conversation session."""

    class Arguments:
        input = StartHelpBotSessionInput(required=True)

    Output = HelpBotSessionResponse

    @login_required
    def mutate(self, info, input):
        """Start HelpBot session."""
        try:
            conversation_service = HelpBotConversationService()
            context_service = HelpBotContextService()

            # Capture context
            context = context_service.capture_context(
                user=info.context.user,
                request=info.context,
                additional_context=input.context_data or {}
            )

            # Start session
            session = conversation_service.start_session(
                user=info.context.user,
                session_type=input.session_type,
                context_data=input.context_data or {},
                language=input.language
            )

            # Get session history
            messages = session.messages.all().order_by('cdtz')

            # Get context suggestions
            suggestions = context_service.get_context_suggestions(
                info.context.user, context
            )

            return HelpBotSessionResponse(
                success=True,
                session=session,
                messages=messages,
                context_suggestions=[s['text'] for s in suggestions]
            )

        except Exception as e:
            return HelpBotSessionResponse(
                success=False,
                error=str(e)
            )


class SendHelpBotMessage(graphene.Mutation):
    """Send a message to HelpBot."""

    class Arguments:
        input = SendHelpBotMessageInput(required=True)

    Output = HelpBotMessageResponse

    @login_required
    def mutate(self, info, input):
        """Send message to HelpBot."""
        try:
            conversation_service = HelpBotConversationService()

            # Get session
            session = HelpBotSession.objects.get(
                session_id=input.session_id,
                user=info.context.user
            )

            # Process message
            result = conversation_service.process_message(
                session=session,
                user_message=input.message,
                message_type=input.message_type
            )

            if result['success']:
                # Get the bot message
                bot_message = HelpBotMessage.objects.get(
                    message_id=result['response']['message_id']
                )

                return HelpBotMessageResponse(
                    success=True,
                    message=bot_message,
                    bot_response=result['response'],
                    suggestions=result['response'].get('suggestions', [])
                )
            else:
                return HelpBotMessageResponse(
                    success=False,
                    error=result.get('error', 'Unknown error')
                )

        except HelpBotSession.DoesNotExist:
            return HelpBotMessageResponse(
                success=False,
                error="Session not found"
            )
        except Exception as e:
            return HelpBotMessageResponse(
                success=False,
                error=str(e)
            )


class SubmitHelpBotFeedback(graphene.Mutation):
    """Submit feedback for HelpBot interaction."""

    class Arguments:
        input = HelpBotFeedbackInput(required=True)

    success = graphene.Boolean()
    error = graphene.String()

    @login_required
    def mutate(self, info, input):
        """Submit HelpBot feedback."""
        try:
            conversation_service = HelpBotConversationService()

            # Get session
            session = HelpBotSession.objects.get(
                session_id=input.session_id,
                user=info.context.user
            )

            # Submit feedback
            success = conversation_service.add_feedback(
                session=session,
                message_id=input.message_id or '',
                feedback_type=input.feedback_type,
                rating=input.rating,
                comment=input.comment
            )

            return SubmitHelpBotFeedback(success=success)

        except HelpBotSession.DoesNotExist:
            return SubmitHelpBotFeedback(
                success=False,
                error="Session not found"
            )
        except Exception as e:
            return SubmitHelpBotFeedback(
                success=False,
                error=str(e)
            )


# HelpBot Mutations
class HelpBotMutations(graphene.ObjectType):
    """HelpBot GraphQL mutations."""

    start_helpbot_session = StartHelpBotSession.Field()
    send_helpbot_message = SendHelpBotMessage.Field()
    submit_helpbot_feedback = SubmitHelpBotFeedback.Field()