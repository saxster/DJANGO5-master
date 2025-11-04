"""
LLM Service Base Classes for Conversational Onboarding

Abstract base classes for Maker and Checker LLM implementations.
Following .claude/rules.md Rule #7 (Single Responsibility) and CLAUDE.md limits.

Extracted from: apps/onboarding_api/services/llm.py (lines 27-89)
Date: 2025-10-10
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, TYPE_CHECKING

# TYPE_CHECKING import to prevent circular dependency
if TYPE_CHECKING:
    from apps.client_onboarding.models.conversational_ai import ConversationSession


class MakerLLM(ABC):
    """
    Abstract base class for Maker LLM - responsible for generating initial recommendations

    The Maker LLM is the first stage in the maker-checker pattern:
    1. Analyzes user input and context
    2. Generates questions for guided conversations
    3. Processes user responses
    4. Creates initial recommendations

    Implementations:
    - DummyMakerLLM: Simple rule-based for development/testing
    - CitationAwareMakerLLM: Production-grade with knowledge base grounding
    """

    @abstractmethod
    def enhance_context(self, user_input: str, context: Dict[str, Any], user) -> Dict[str, Any]:
        """
        Enhance the initial context with LLM understanding

        Args:
            user_input: Raw user input text
            context: Existing context dictionary
            user: User instance for personalization

        Returns:
            Enhanced context with analysis and enrichment
        """
        pass

    @abstractmethod
    def generate_questions(self, context: Dict[str, Any], conversation_type: str) -> List[Dict[str, Any]]:
        """
        Generate initial questions based on context

        Args:
            context: Enhanced context dictionary
            conversation_type: Type of conversation (e.g., "initial_setup", "configuration")

        Returns:
            List of question dictionaries with metadata
        """
        pass

    @abstractmethod
    def process_conversation_step(self, session, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a conversation step and generate recommendations

        Args:
            session: ConversationSession instance
            user_input: User's response/input for this step
            context: Current context dictionary

        Returns:
            Response dict with recommendations, confidence, next steps
        """
        pass

    @abstractmethod
    def generate_recommendations(self, session, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate final recommendations based on collected data

        Args:
            session: ConversationSession instance
            collected_data: All data collected during conversation

        Returns:
            Final recommendations dict with confidence and reasoning
        """
        pass

    def process_voice_input(
        self,
        transcript: str,
        session,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process voice transcript as text input.

        Default implementation delegates to existing text processing method.
        Subclasses can override to add voice-specific processing logic.

        Args:
            transcript: Transcribed text from voice input
            session: ConversationSession instance
            context: Additional context data

        Returns:
            Response dict with same structure as process_conversation_step
        """
        return self.process_conversation_step(session, transcript, context)


class CheckerLLM(ABC):
    """
    Abstract base class for Checker LLM - responsible for validating maker recommendations

    The Checker LLM is the second stage in the maker-checker pattern:
    1. Validates maker's recommendations against policies and knowledge
    2. Checks for consistency and compliance
    3. Suggests improvements or corrections
    4. Provides confidence adjustments

    Implementations:
    - DummyCheckerLLM: Simple validation for development/testing
    - EnhancedCheckerLLM: Template-based validation
    - CitationAwareCheckerLLM: Production-grade with knowledge verification
    """

    @abstractmethod
    def validate_recommendations(self, maker_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and improve maker recommendations

        Args:
            maker_output: Output from MakerLLM including recommendations
            context: Current context dictionary

        Returns:
            Validation result with confidence adjustments and improvements
        """
        pass

    @abstractmethod
    def check_consistency(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check consistency across multiple recommendations

        Args:
            recommendations: List of recommendation dictionaries

        Returns:
            Consistency analysis with conflicts and suggestions
        """
        pass
