"""
Ontology Registrations Package

This package contains all ontology registrations organized by theme:
- november_2025_improvements.py - Security, reliability, analytics, premium features
- security_patterns_nov_2025.py - Comprehensive security knowledge base
- complete_features_nov_2025.py - Complete feature set
- november_2025_strategic_features.py - Strategic business features

All registrations are auto-loaded on module import.
"""

from .november_2025_improvements import register_november_2025_improvements
from .security_patterns_nov_2025 import register_security_patterns

__all__ = [
    'register_november_2025_improvements',
    'register_security_patterns',
]


def load_all_registrations():
    """
    Load all ontology registrations into the registry.
    
    Returns:
        dict: Count of components registered by module
    """
    counts = {
        'november_2025_improvements': register_november_2025_improvements(),
        'security_patterns_nov_2025': register_security_patterns(),
    }
    
    return counts


# Auto-load all registrations
_registration_counts = load_all_registrations()
