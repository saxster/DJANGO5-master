"""
ML-Enhanced Baselines Models.

Backward-compatible imports for refactored baseline models.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (split into focused models)
- Maintains backward compatibility for existing imports
"""

from .ml_baseline_enums import (
    BASELINE_TYPES,
    APPROVAL_STATUS,
    SEMANTIC_CONFIDENCE_LEVELS,
    ELEMENT_TYPES,
    INTERACTION_TYPES,
    COMPARISON_TYPES,
    COMPARISON_RESULTS,
)
from .baseline_config import MLBaseline
from .semantic_element import SemanticElement
from .baseline_comparison import BaselineComparison
from .baseline_metrics import BaselineMetrics

# Add analysis methods to MLBaseline for backward compatibility
MLBaseline.analyze_baseline_drift = classmethod(
    lambda cls, days=30: BaselineMetrics.analyze_baseline_drift(cls, days)
)
MLBaseline.analyze_visual_difference = BaselineMetrics.analyze_visual_difference
MLBaseline.detect_functional_changes = BaselineMetrics.detect_functional_changes

# Export all models for backward compatibility
__all__ = [
    # Models
    'MLBaseline',
    'SemanticElement',
    'BaselineComparison',
    # Helper
    'BaselineMetrics',
    # Enums
    'BASELINE_TYPES',
    'APPROVAL_STATUS',
    'SEMANTIC_CONFIDENCE_LEVELS',
    'ELEMENT_TYPES',
    'INTERACTION_TYPES',
    'COMPARISON_TYPES',
    'COMPARISON_RESULTS',
]
