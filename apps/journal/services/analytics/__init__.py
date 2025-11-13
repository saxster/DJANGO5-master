"""
Journal Analytics Module

Modular analytics services for journal pattern recognition and wellness interventions.

REFACTORED FROM:
- apps/journal/services/analytics_service.py (1,144 lines)
- apps/journal/services/pattern_analyzer.py (1,058 lines)

ARCHITECTURE:
- urgency_analyzer.py - Real-time urgency scoring and crisis detection
- pattern_detection_service.py - Long-term pattern algorithms
- Main analytics_service.py delegates to these specialized services

ELIMINATES 650+ LINES OF DUPLICATE CODE
"""

from .urgency_analyzer import UrgencyAnalyzer
from .pattern_detection_service import PatternDetectionService

__all__ = [
    'UrgencyAnalyzer',
    'PatternDetectionService',
]
