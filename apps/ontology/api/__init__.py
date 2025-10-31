"""
API endpoints for querying ontology metadata.

Provides REST API and Python API for Claude Code and other tools
to query the ontology system.
"""

from apps.ontology.api.query_api import OntologyQueryAPI

__all__ = ["OntologyQueryAPI"]
