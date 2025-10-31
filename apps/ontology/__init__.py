"""
Ontology System for Django Codebase Analysis

A code-native ontology system that extracts, enriches, and maintains
semantic metadata about the Django codebase for LLM-assisted development.

Key Features:
- @ontology decorator for marking code with semantic metadata
- AST-based code extraction and analysis
- Automated documentation generation
- Semantic search and cross-referencing
- Business rule validation
- LLM query API for Claude Code
"""

__version__ = "1.0.0"

# Import main components for easy access
from apps.ontology.decorators import ontology
from apps.ontology.registry import OntologyRegistry

__all__ = ["ontology", "OntologyRegistry"]
