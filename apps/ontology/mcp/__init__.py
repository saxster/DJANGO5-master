"""
Model Context Protocol (MCP) server for ontology system.

Exposes ontology as queryable resource following Anthropic's MCP specification.
"""

from apps.ontology.mcp.server import OntologyMCPServer

__all__ = ["OntologyMCPServer"]
