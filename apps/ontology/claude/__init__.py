"""
Claude Code integration for ontology system.

Provides smart context injection and query capabilities.
"""

from apps.ontology.claude.smart_injection import (
    OntologyContextInjector,
    detect_code_reference,
    inject_ontology_context,
)

__all__ = [
    "OntologyContextInjector",
    "detect_code_reference",
    "inject_ontology_context",
]
