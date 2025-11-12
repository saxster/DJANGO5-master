"""
Parlant Agent Service for Security & Facility Mentor.

Provides intelligent conversational AI with ensured rule compliance for
operational non-negotiables monitoring.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines (wrapper service - justified by complexity)
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling

IMPORTANT: This service provides sync wrapper methods for async Parlant operations.
Use these from Django sync views. For pure async views, use Parlant SDK directly.
"""

import logging
from typing import Dict, Any, Optional
import asyncio

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from asgiref.sync import async_to_sync
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS, PARSING_EXCEPTIONS
from apps.ontology import ontology

logger = logging.getLogger('helpbot.parlant')


@ontology(
    domain="help",
    purpose="Parlant 3.0 conversational AI agent for guided workflows and security scorecard reviews",
    inputs=[
        {"name": "session", "type": "HelpBotSession", "description": "Session context"},
        {"name": "journey", "type": "str", "description": "Journey type: scorecard_review, emergency_escalation, violation_resolution"},
    ],
    outputs=[
        {"name": "response", "type": "dict", "description": "Parlant agent response with guidance"}
    ],
    depends_on=[
        "parlant==3.0",
        "apps.helpbot.parlant.guidelines.non_negotiables_guidelines"
    ],
    tags=["help", "ai", "parlant", "security", "guided-workflows", "journeys"],
    criticality="high",
    business_value="Security Facility Mentor - guides compliance with 7 non-negotiables, multi-language support (en/hi/te)"
)
class ParlantAgentService:
    """
    Wrapper service for Parlant conversational AI framework.

    Integrates Parlant with existing HelpBot infrastructure for
    Security & Facility Mentor conversations.
    """

    def __init__(self):
        """Initialize Parlant agent service."""
        self.enabled = getattr(settings, 'ENABLE_PARLANT_AGENT', False)

        if not self.enabled:
            logger.info("Parlant agent disabled - using template-based responses")
            self.server = None
            self.agent = None
            return

        try:
            import parlant.sdk as p
            self.p = p
            logger.info("Parlant SDK imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import Parlant SDK: {e}")
            raise ImproperlyConfigured(
                "Parlant is enabled but not installed. Run: pip install parlant>=3.0"
            )

        # Initialize server and agent asynchronously
        self._server_initialized = False
        self.server = None
        self.agent = None

    async def initialize_agent(self, agent_name: str = "SecurityFacilityMentor"):
        """
        Initialize Parlant server and create agent.

        Args:
            agent_name: Name for the Parlant agent

        Raises:
            ImproperlyConfigured: If Parlant setup fails
        """
        if self._server_initialized:
            return

        try:
            # Start Parlant server
            self.server = self.p.Server()
            await self.server.__aenter__()

            # Create or get agent
            try:
                self.agent = await self.server.get_agent(name=agent_name)
                logger.info(f"Retrieved existing Parlant agent: {agent_name}")
            except (NETWORK_EXCEPTIONS, PARSING_EXCEPTIONS):
                # Agent doesn't exist, create it
                self.agent = await self.server.create_agent(name=agent_name)
                logger.info(f"Created new Parlant agent: {agent_name}")

                # Initialize with guidelines, tools, and journeys
                await self._initialize_guidelines()
                await self._initialize_tools()
                await self._initialize_journeys()

            self._server_initialized = True
            logger.info("Parlant agent initialized successfully")

        except (ImportError, AttributeError) as e:
            logger.error(f"Error initializing Parlant agent: {e}", exc_info=True)
            raise ImproperlyConfigured(f"Parlant initialization failed: {e}")

    async def _initialize_guidelines(self):
        """Load and register all 7 pillar guidelines."""
        try:
            from apps.helpbot.parlant.guidelines.non_negotiables_guidelines import (
                create_all_guidelines
            )

            guidelines = await create_all_guidelines(self.agent)
            logger.info(f"Loaded {len(guidelines)} guidelines for non-negotiables")

        except (ImportError, AttributeError) as e:
            logger.error(f"Error loading guidelines: {e}", exc_info=True)
            # Continue without guidelines (will use base LLM)

    async def _initialize_tools(self):
        """Register all tools with the agent."""
        try:
            from apps.helpbot.parlant.tools.scorecard_tools import ALL_TOOLS

            for tool in ALL_TOOLS:
                await self.agent.register_tool(tool)

            logger.info(f"Registered {len(ALL_TOOLS)} tools with Parlant agent")

        except (ImportError, AttributeError) as e:
            logger.error(f"Error registering tools: {e}", exc_info=True)
            # Continue without tools (limited functionality)

    async def _initialize_journeys(self):
        """Register all conversational journeys with the agent."""
        try:
            from apps.helpbot.parlant.journeys.emergency_escalation import create_all_journeys

            journeys = await create_all_journeys(self.agent)
            logger.info(f"Registered {len(journeys)} conversational journeys with Parlant agent")

        except (ImportError, AttributeError) as e:
            logger.error(f"Error registering journeys: {e}", exc_info=True)
            # Continue without journeys (basic conversation only)

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process user message through Parlant agent.

        Args:
            session_id: Unique session identifier
            user_message: User's message content
            session_data: Context data (tenant, client, user, etc.)

        Returns:
            Dict with agent response and metadata
        """
        if not self.enabled:
            raise RuntimeError("Parlant agent not enabled")

        try:
            # Ensure agent is initialized
            if not self._server_initialized:
                await self.initialize_agent()

            # Process message through Parlant
            response = await self.agent.respond(
                user_message=user_message,
                session_id=session_id,
                context=session_data
            )

            return {
                'success': True,
                'content': response.message,
                'confidence_score': response.confidence if hasattr(response, 'confidence') else 0.9,
                'tools_used': response.tools_called if hasattr(response, 'tools_called') else [],
                'guidelines_matched': response.guidelines_applied if hasattr(response, 'guidelines_applied') else [],
                'journey_state': response.journey_state if hasattr(response, 'journey_state') else None,
            }

        except (AttributeError, RuntimeError) as e:
            logger.error(f"Error processing message with Parlant: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'fallback_required': True
            }

    def process_message_sync(
        self,
        session_id: str,
        user_message: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sync wrapper for process_message (for use in sync Django views).

        Args:
            session_id: Unique session identifier
            user_message: User's message content
            session_data: Context data (tenant, client, user, etc.)

        Returns:
            Dict with agent response and metadata
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Parlant agent not enabled',
                'fallback_required': True
            }

        try:
            # Convert async to sync using asgiref
            return async_to_sync(self.process_message)(
                session_id, user_message, session_data
            )
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            # RuntimeError: asgiref conversion errors
            # ValueError: Invalid session data or message format
            # TypeError: Type mismatches in async/sync conversion
            # AttributeError: Missing required attributes
            logger.error(f"Error in sync wrapper: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'fallback_required': True
            }

    async def cleanup(self):
        """Cleanup Parlant server resources."""
        if self.server and self._server_initialized:
            try:
                await self.server.__aexit__(None, None, None)
                logger.info("Parlant server cleaned up successfully")
            except (RuntimeError, OSError, AttributeError) as e:
                # RuntimeError: Async context manager errors
                # OSError: I/O errors during cleanup
                # AttributeError: Server object state issues
                logger.error(f"Error cleaning up Parlant server: {e}")
