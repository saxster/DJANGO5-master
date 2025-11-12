"""
ML-Enhanced Baselines - Enumeration Types.

Centralized enum definitions for baseline types, statuses, and semantic analysis.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (enums in dedicated module)
"""


# Baseline type choices
BASELINE_TYPES = [
    ('visual', 'Visual/UI Baseline'),
    ('performance', 'Performance Baseline'),
    ('functional', 'Functional Baseline'),
    ('api', 'API Response Baseline'),
    ('accessibility', 'Accessibility Baseline'),
]

# Approval status choices
APPROVAL_STATUS = [
    ('auto_approved', 'Auto-Approved'),
    ('pending_review', 'Pending Review'),
    ('community_approved', 'Community Approved'),
    ('rejected', 'Rejected'),
    ('deprecated', 'Deprecated'),
]

# Semantic confidence levels
SEMANTIC_CONFIDENCE_LEVELS = [
    ('low', 'Low (0-40%)'),
    ('medium', 'Medium (40-70%)'),
    ('high', 'High (70-90%)'),
    ('very_high', 'Very High (90%+)'),
]

# Semantic element types
ELEMENT_TYPES = [
    ('button', 'Button'),
    ('text_field', 'Text Field'),
    ('label', 'Text Label'),
    ('image', 'Image'),
    ('icon', 'Icon'),
    ('container', 'Container/Layout'),
    ('navigation', 'Navigation Element'),
    ('form', 'Form Element'),
    ('list_item', 'List Item'),
    ('modal', 'Modal/Dialog'),
]

# Interaction types
INTERACTION_TYPES = [
    ('clickable', 'Clickable'),
    ('scrollable', 'Scrollable'),
    ('input', 'Input Field'),
    ('display_only', 'Display Only'),
    ('navigation', 'Navigation'),
]

# Comparison types
COMPARISON_TYPES = [
    ('visual_diff', 'Visual Difference'),
    ('functional_diff', 'Functional Difference'),
    ('performance_diff', 'Performance Difference'),
]

# Comparison results
COMPARISON_RESULTS = [
    ('identical', 'Identical'),
    ('acceptable_diff', 'Acceptable Difference'),
    ('significant_diff', 'Significant Difference'),
    ('regression', 'Regression Detected'),
]


__all__ = [
    'BASELINE_TYPES',
    'APPROVAL_STATUS',
    'SEMANTIC_CONFIDENCE_LEVELS',
    'ELEMENT_TYPES',
    'INTERACTION_TYPES',
    'COMPARISON_TYPES',
    'COMPARISON_RESULTS',
]
