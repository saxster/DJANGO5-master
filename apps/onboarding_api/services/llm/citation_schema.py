"""
Citation schema definitions for knowledge-grounded LLM responses.

Centralized citation format validation and requirements.
Extracted from: apps/onboarding_api/services/llm.py (lines 599-614, 1001-1006, 1490)
Date: 2025-10-10
"""
from typing import Dict, Any


# JSON Schema for citation format (used by CitationAwareMakerLLM)
CITATION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Document knowledge ID"
            },
            "chunk_index": {
                "type": "integer",
                "description": "Chunk index within document"
            },
            "page_start": {
                "type": "integer",
                "description": "Starting page number"
            },
            "page_end": {
                "type": "integer",
                "description": "Ending page number"
            },
            "quote": {
                "type": "string",
                "description": "Exact quote from source"
            },
            "relevance": {
                "type": "string",
                "enum": ["supporting", "contradicting", "contextual"],
                "description": "Citation relevance type"
            },
            "authority_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "official"],
                "description": "Source authority level"
            }
        },
        "required": ["doc_id", "chunk_index", "quote", "relevance"]
    }
}


# Citation requirements by claim type (used by CitationAwareCheckerLLM)
CITATION_REQUIREMENTS = {
    'security_claims': ['authority_level', 'quote', 'doc_id'],
    'policy_claims': ['authority_level', 'quote', 'doc_id', 'page_start'],
    'configuration_claims': ['quote', 'doc_id'],
    'compliance_claims': ['authority_level', 'quote', 'doc_id', 'page_start']
}


# Authority level weights for scoring (used by ConsensusEngine)
AUTHORITY_WEIGHTS = {
    'official': 1.0,  # Official documentation/policies
    'high': 0.8,      # Verified expert sources
    'medium': 0.6,    # Standard documentation
    'low': 0.3        # Community/informal sources
}
