"""
Parlant Guidelines for 7 Non-Negotiables (Multi-Lingual - Sprint 3)

Provides guidelines in multiple languages:
- English (en): non_negotiables_guidelines.py
- Hindi (hi): non_negotiables_guidelines_hi.py
- Telugu (te): non_negotiables_guidelines_te.py

All translations maintain functional parity with original English guidelines.
"""

from .non_negotiables_guidelines import create_all_guidelines as create_all_guidelines_en
from .non_negotiables_guidelines_hi import create_all_guidelines_hi
from .non_negotiables_guidelines_te import create_all_guidelines_te

__all__ = [
    'create_all_guidelines_en',  # English
    'create_all_guidelines_hi',  # Hindi
    'create_all_guidelines_te',  # Telugu
]
