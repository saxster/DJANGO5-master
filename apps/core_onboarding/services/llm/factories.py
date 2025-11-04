"""
Service factory functions for LLM instances.

Centralized instantiation logic with configuration-based selection.
Extracted from: apps/onboarding_api/services/llm.py (lines 1690-1721)
Date: 2025-10-10
"""
from typing import Optional, TYPE_CHECKING
import logging
from django.conf import settings

if TYPE_CHECKING:
    from .base import MakerLLM, CheckerLLM
    from .consensus_engine import ConsensusEngine

logger = logging.getLogger(__name__)


def get_llm_service() -> 'MakerLLM':
    """
    Factory function to get the configured LLM service.

    Returns CitationAwareMakerLLM if ENABLE_ONBOARDING_KB=True,
    otherwise returns DummyMakerLLM.

    Returns:
        MakerLLM instance configured based on settings
    """
    use_citations = getattr(settings, 'ENABLE_ONBOARDING_KB', False)

    if use_citations:
        from .citation_aware_maker import CitationAwareMakerLLM
        logger.info("Using citation-aware Maker LLM with knowledge grounding")
        return CitationAwareMakerLLM()
    else:
        from .dummy_implementations import DummyMakerLLM
        return DummyMakerLLM()


def get_checker_service() -> Optional['CheckerLLM']:
    """
    Factory function to get the configured Checker LLM service.

    Returns None if ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER=False.
    Returns CitationAwareCheckerLLM if ENABLE_ONBOARDING_KB=True,
    otherwise returns EnhancedCheckerLLM.

    Returns:
        CheckerLLM instance or None
    """
    if not getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False):
        return None

    use_citations = getattr(settings, 'ENABLE_ONBOARDING_KB', False)

    if use_citations:
        from .citation_aware_checker import CitationAwareCheckerLLM
        logger.info("Using citation-aware Checker LLM with knowledge validation")
        return CitationAwareCheckerLLM()
    else:
        from .enhanced_checker import EnhancedCheckerLLM
        return EnhancedCheckerLLM()


def get_consensus_engine() -> 'ConsensusEngine':
    """
    Factory function to get the consensus engine.

    Returns:
        ConsensusEngine instance
    """
    from .consensus_engine import ConsensusEngine
    return ConsensusEngine()
