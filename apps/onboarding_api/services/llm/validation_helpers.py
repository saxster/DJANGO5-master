"""
Shared validation utilities for LLM services.

Reusable validation logic across Maker and Checker implementations.
Extracted from: apps/onboarding_api/services/llm.py (multiple sections)
Date: 2025-10-10
"""
from typing import Dict, List, Any


def validate_citation_format(citation: Dict[str, Any]) -> bool:
    """
    Validate citation structure and required fields.

    Args:
        citation: Citation dictionary to validate

    Returns:
        True if citation is valid, False otherwise
    """
    required_fields = ['doc_id', 'chunk_index', 'quote', 'relevance']

    # Check required fields
    if not all(field in citation for field in required_fields):
        return False

    # Validate field types and values
    if not isinstance(citation.get('chunk_index'), int) or citation['chunk_index'] < 0:
        return False

    if citation.get('relevance') not in ['supporting', 'contradicting', 'contextual']:
        return False

    # Minimum quote length validation
    if len(citation.get('quote', '')) < 10:
        return False

    return True


def detect_contradictions(quotes: List[str]) -> List[Dict[str, Any]]:
    """
    Detect contradictory statements in quotes.

    Args:
        quotes: List of quote strings to analyze

    Returns:
        List of contradiction details
    """
    contradictions = []
    contradiction_patterns = [
        ('should', 'should not'),
        ('recommended', 'not recommended'),
        ('required', 'optional'),
        ('enable', 'disable')
    ]

    for i, quote1 in enumerate(quotes):
        for j, quote2 in enumerate(quotes[i+1:], i+1):
            quote1_lower = quote1.lower()
            quote2_lower = quote2.lower()

            for pos, neg in contradiction_patterns:
                if (pos in quote1_lower and neg in quote2_lower) or \
                   (neg in quote1_lower and pos in quote2_lower):
                    contradictions.append({
                        'index1': i,
                        'index2': j,
                        'pattern': (pos, neg),
                        'quote1_snippet': quote1[:100],
                        'quote2_snippet': quote2[:100]
                    })

    return contradictions


def extract_topics(text: str) -> List[str]:
    """
    Extract key topics from text for knowledge retrieval.

    Args:
        text: Input text to analyze

    Returns:
        List of identified topics
    """
    topics = []

    business_keywords = ['office', 'warehouse', 'retail', 'manufacturing', 'facility']
    security_keywords = ['security', 'access', 'authentication', 'monitoring']
    config_keywords = ['setup', 'configuration', 'system', 'users', 'permissions']

    text_lower = text.lower()

    if any(kw in text_lower for kw in business_keywords):
        topics.append('business_unit_types')
    if any(kw in text_lower for kw in security_keywords):
        topics.append('security_requirements')
    if any(kw in text_lower for kw in config_keywords):
        topics.append('system_configuration')

    return topics if topics else ['general_setup']


def should_ground_response(user_input: str) -> bool:
    """
    Determine if response requires knowledge grounding.

    Args:
        user_input: User's input text

    Returns:
        True if grounding required, False otherwise
    """
    grounding_keywords = [
        'policy', 'compliance', 'standard', 'requirement',
        'guideline', 'best practice'
    ]
    return any(keyword in user_input.lower() for keyword in grounding_keywords)
