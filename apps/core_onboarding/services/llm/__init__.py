"""
LLM service module for conversational onboarding.

Provides base abstractions and implementations for Maker/Checker LLM pattern.

This module maintains backward compatibility with the original monolithic llm.py file.
All imports that previously worked continue to work without code changes.

Refactored: 2025-10-10 (1,720 lines → 11 focused modules)
"""

# Base classes
from .base import MakerLLM, CheckerLLM

# Phase 1 MVP implementations
from .dummy_implementations import DummyMakerLLM, DummyCheckerLLM

# Phase 2 implementations
from .enhanced_checker import EnhancedCheckerLLM

# Production implementations
from .citation_aware_maker import CitationAwareMakerLLM
from .citation_aware_checker import CitationAwareCheckerLLM

# Consensus engine
from .consensus_engine import ConsensusEngine

# Factory functions
from .factories import get_llm_service, get_checker_service, get_consensus_engine

# Exceptions
from .exceptions import (
    LLMServiceException,
    LLMValidationError,
    LLMKnowledgeError,
    LLMConsensusError
)

__all__ = [
    # Base classes
    'MakerLLM',
    'CheckerLLM',
    # Phase 1 implementations
    'DummyMakerLLM',
    'DummyCheckerLLM',
    # Phase 2 implementations
    'EnhancedCheckerLLM',
    # Production implementations
    'CitationAwareMakerLLM',
    'CitationAwareCheckerLLM',
    # Consensus
    'ConsensusEngine',
    # Factories
    'get_llm_service',
    'get_checker_service',
    'get_consensus_engine',
    # Exceptions
    'LLMServiceException',
    'LLMValidationError',
    'LLMKnowledgeError',
    'LLMConsensusError',
]
