"""
Wellness Constants Module

Centralized constants for wellness and journal analytics services
to eliminate duplication across multiple files.
"""

from .crisis_keywords import CRISIS_KEYWORDS, CRISIS_RISK_FACTORS, STRESS_TRIGGER_PATTERNS

__all__ = [
    'CRISIS_KEYWORDS',
    'CRISIS_RISK_FACTORS',
    'STRESS_TRIGGER_PATTERNS',
]
