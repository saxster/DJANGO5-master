"""
MCP Server for Ontology System.

Implements Model Context Protocol (MCP) from Anthropic:
https://modelcontextprotocol.io/introduction

Provides tools and resources for LLM clients to query the ontology.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from django.core.management import call_command
from io import StringIO

from apps.ontology.models import OntologyComponent, OntologyRelationship

logger = logging.getLogger(__name__)


class MCPTool:
    """Represents an MCP tool definition."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPResource:
    """Represents an MCP resource definition."""

    def __init__(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str = "application/json",
    ):
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP resource format."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


class OntologyMCPServer:
    """
    MCP Server for Ontology System.

    Implements the Model Context Protocol specification to expose
    ontology data to LLM clients (Claude Desktop, Code, etc.).

    Protocol Specification:
    - Tools: Callable operations for querying ontology
    - Resources: Static/dynamic content accessible via URIs
    - Prompts: Pre-defined prompt templates (future)
    """

    def __init__(self):
        self.name = "ontology-server"
        self.version = "1.0.0"
        self.tools = self._register_tools()
        self.resources = self._register_resources()

    def _register_tools(self) -> List[MCPTool]:
        """Register available MCP tools."""
        return [
            MCPTool(
                name="ontology_query",
                description=(
                    "Query the codebase ontology by domain, tag, purpose, or component name. "
                    "Returns semantic metadata about code components including purpose, "
                    "dependencies, criticality, and relationships."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Search query. Can be domain name (e.g., 'people'), "
                                "tag (e.g., 'authentication'), component name, "
                                "or purpose keyword."
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 20,
                        },
                        "criticality": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Filter by criticality level",
                        },
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="ontology_get",
                description=(
                    "Get detailed metadata for a specific component by exact module path. "
                    "Returns complete component information including all relationships "
                    "and dependencies."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "module_path": {
                            "type": "string",
                            "description": (
                                "Exact module path (e.g., 'apps.peoples.models.People')"
                            ),
                        },
                    },
                    "required": ["module_path"],
                },
            ),
            MCPTool(
                name="ontology_stats",
                description=(
                    "Get ontology coverage statistics including component counts, "
                    "domain distribution, criticality breakdown, and relationship metrics."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "detailed": {
                            "type": "boolean",
                            "description": "Include detailed per-domain statistics",
                            "default": False,
                        },
                    },
                },
            ),
            MCPTool(
                name="ontology_relationships",
                description=(
                    "Query relationships between components. Find dependencies, "
                    "dependents, or related components."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component module path or name",
                        },
                        "relationship_type": {
                            "type": "string",
                            "enum": ["depends_on", "used_by", "related_to", "all"],
                            "description": "Type of relationship to query",
                            "default": "all",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Depth of relationship traversal (1-3)",
                            "default": 1,
                            "minimum": 1,
                            "maximum": 3,
                        },
                    },
                    "required": ["component"],
                },
            ),
        ]

    def _register_resources(self) -> List[MCPResource]:
        """Register available MCP resources."""
        return [
            MCPResource(
                uri="ontology://graph",
                name="Complete Knowledge Graph",
                description=(
                    "Complete ontology knowledge graph with all components, "
                    "relationships, and metadata. JSON format."
                ),
                mime_type="application/json",
            ),
            MCPResource(
                uri="ontology://domains",
                name="Domain List",
                description="List of all domains with component counts.",
                mime_type="application/json",
            ),
            MCPResource(
                uri="ontology://critical",
                name="Critical Components",
                description="All components marked as critical or high criticality.",
                mime_type="application/json",
            ),
            MCPResource(
                uri="ontology://domain/{domain}",
                name="Domain Components",
                description=(
                    "All components in a specific domain. "
                    "Replace {domain} with domain name (e.g., 'people')."
                ),
                mime_type="application/json",
            ),
        ]

    def handle_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle MCP tool call.

        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments

        Returns:
            Tool result in MCP format
        """
        try:
            if tool_name == "ontology_query":
                return self._handle_query(arguments)
            elif tool_name == "ontology_get":
                return self._handle_get(arguments)
            elif tool_name == "ontology_stats":
                return self._handle_stats(arguments)
            elif tool_name == "ontology_relationships":
                return self._handle_relationships(arguments)
            else:
                return {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": f"Unknown tool: {tool_name}",
                        }
                    ],
                }
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            logger.exception(f"Error handling tool call {tool_name}")
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing {tool_name}: {str(e)}",
                    }
                ],
            }

    def _handle_query(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ontology_query tool."""
        query = arguments["query"]
        limit = arguments.get("limit", 20)
        criticality = arguments.get("criticality")

        # Build queryset
        components = OntologyComponent.objects.all()

        # Try multiple search strategies
        filters = []

        # Component name match
        filters.append(components.filter(component_name__icontains=query))

        # Module path match
        filters.append(components.filter(module_path__icontains=query))

        # Purpose match
        filters.append(components.filter(purpose__icontains=query))

        # Domain match
        filters.append(components.filter(domain__icontains=query))

        # Tags match
        filters.append(components.filter(tags__contains=[query]))

        # Combine with OR logic
        results = None
        for queryset in filters:
            if results is None:
                results = queryset
            else:
                results = results | queryset

        # Apply criticality filter if specified
        if criticality:
            results = results.filter(criticality=criticality)

        # Deduplicate and limit
        results = results.distinct()[:limit]

        # Format results
        components_data = []
        for component in results:
            components_data.append({
                "module_path": component.module_path,
                "component_type": component.component_type,
                "component_name": component.component_name,
                "purpose": component.purpose,
                "domain": component.domain,
                "criticality": component.criticality,
                "tags": component.tags,
                "dependencies": component.dependencies,
                "file_path": component.file_path,
                "line_number": component.line_number,
                "last_analyzed": component.last_analyzed.isoformat() if component.last_analyzed else None,
            })

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "query": query,
                        "count": len(components_data),
                        "components": components_data,
                    }, indent=2),
                }
            ],
        }

    def _handle_get(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ontology_get tool."""
        module_path = arguments["module_path"]

        try:
            component = OntologyComponent.objects.get(module_path=module_path)
        except OntologyComponent.DoesNotExist:
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"Component not found: {module_path}",
                    }
                ],
            }

        # Get relationships
        outgoing = OntologyRelationship.objects.filter(source=component)
        incoming = OntologyRelationship.objects.filter(target=component)

        component_data = {
            "module_path": component.module_path,
            "component_type": component.component_type,
            "component_name": component.component_name,
            "purpose": component.purpose,
            "domain": component.domain,
            "criticality": component.criticality,
            "tags": component.tags,
            "dependencies": component.dependencies,
            "file_path": component.file_path,
            "line_number": component.line_number,
            "relationships": {
                "depends_on": [
                    {
                        "target": rel.target.module_path,
                        "type": rel.relationship_type,
                    }
                    for rel in outgoing
                ],
                "used_by": [
                    {
                        "source": rel.source.module_path,
                        "type": rel.relationship_type,
                    }
                    for rel in incoming
                ],
            },
            "last_analyzed": component.last_analyzed.isoformat() if component.last_analyzed else None,
        }

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(component_data, indent=2),
                }
            ],
        }

    def _handle_stats(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ontology_stats tool."""
        detailed = arguments.get("detailed", False)

        stats = {
            "total_components": OntologyComponent.objects.count(),
            "total_relationships": OntologyRelationship.objects.count(),
            "by_type": {},
            "by_criticality": {},
            "by_domain": {},
        }

        # Component type breakdown
        for component_type in ["class", "function", "method", "module"]:
            count = OntologyComponent.objects.filter(
                component_type=component_type
            ).count()
            stats["by_type"][component_type] = count

        # Criticality breakdown
        for criticality in ["critical", "high", "medium", "low"]:
            count = OntologyComponent.objects.filter(
                criticality=criticality
            ).count()
            stats["by_criticality"][criticality] = count

        # Domain breakdown
        domains = OntologyComponent.objects.values_list(
            "domain", flat=True
        ).distinct()
        for domain in domains:
            if domain:
                count = OntologyComponent.objects.filter(domain=domain).count()
                stats["by_domain"][domain] = count

        # Detailed stats per domain
        if detailed:
            stats["detailed_domains"] = {}
            for domain in domains:
                if domain:
                    domain_components = OntologyComponent.objects.filter(domain=domain)
                    stats["detailed_domains"][domain] = {
                        "total": domain_components.count(),
                        "by_type": {},
                        "by_criticality": {},
                    }
                    for component_type in ["class", "function", "method", "module"]:
                        count = domain_components.filter(
                            component_type=component_type
                        ).count()
                        stats["detailed_domains"][domain]["by_type"][component_type] = count

                    for criticality in ["critical", "high", "medium", "low"]:
                        count = domain_components.filter(
                            criticality=criticality
                        ).count()
                        stats["detailed_domains"][domain]["by_criticality"][criticality] = count

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(stats, indent=2),
                }
            ],
        }

    def _handle_relationships(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ontology_relationships tool."""
        component_name = arguments["component"]
        relationship_type = arguments.get("relationship_type", "all")
        depth = arguments.get("depth", 1)

        # Find component
        components = OntologyComponent.objects.filter(
            component_name__icontains=component_name
        ) | OntologyComponent.objects.filter(
            module_path__icontains=component_name
        )

        if not components.exists():
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"Component not found: {component_name}",
                    }
                ],
            }

        # Use first match
        component = components.first()

        # Traverse relationships
        relationships = self._traverse_relationships(
            component, relationship_type, depth
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "component": component.module_path,
                        "relationship_type": relationship_type,
                        "depth": depth,
                        "relationships": relationships,
                    }, indent=2),
                }
            ],
        }

    def _traverse_relationships(
        self,
        component: OntologyComponent,
        relationship_type: str,
        depth: int,
        visited: Optional[set] = None,
    ) -> Dict[str, Any]:
        """Recursively traverse relationships."""
        if visited is None:
            visited = set()

        if component.id in visited or depth <= 0:
            return {}

        visited.add(component.id)

        result = {
            "module_path": component.module_path,
            "component_name": component.component_name,
            "domain": component.domain,
            "criticality": component.criticality,
        }

        # Get relationships
        if relationship_type in ["depends_on", "all"]:
            depends_on = OntologyRelationship.objects.filter(source=component)
            result["depends_on"] = []
            for rel in depends_on:
                child = self._traverse_relationships(
                    rel.target, relationship_type, depth - 1, visited
                )
                if child:
                    result["depends_on"].append(child)

        if relationship_type in ["used_by", "all"]:
            used_by = OntologyRelationship.objects.filter(target=component)
            result["used_by"] = []
            for rel in used_by:
                child = self._traverse_relationships(
                    rel.source, relationship_type, depth - 1, visited
                )
                if child:
                    result["used_by"].append(child)

        return result

    def handle_resource_read(self, uri: str) -> Dict[str, Any]:
        """
        Handle MCP resource read.

        Args:
            uri: Resource URI to read

        Returns:
            Resource content in MCP format
        """
        try:
            if uri == "ontology://graph":
                return self._read_graph()
            elif uri == "ontology://domains":
                return self._read_domains()
            elif uri == "ontology://critical":
                return self._read_critical()
            elif uri.startswith("ontology://domain/"):
                domain = uri.split("/")[-1]
                return self._read_domain(domain)
            else:
                return {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": f"Unknown resource URI: {uri}",
                        }
                    ],
                }
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            logger.exception(f"Error reading resource {uri}")
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"Error reading resource: {str(e)}",
                    }
                ],
            }

    def _read_graph(self) -> Dict[str, Any]:
        """Read complete knowledge graph."""
        components = OntologyComponent.objects.all()
        relationships = OntologyRelationship.objects.all()

        graph = {
            "components": [
                {
                    "module_path": c.module_path,
                    "component_type": c.component_type,
                    "component_name": c.component_name,
                    "purpose": c.purpose,
                    "domain": c.domain,
                    "criticality": c.criticality,
                    "tags": c.tags,
                }
                for c in components
            ],
            "relationships": [
                {
                    "source": r.source.module_path,
                    "target": r.target.module_path,
                    "type": r.relationship_type,
                }
                for r in relationships
            ],
        }

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(graph, indent=2),
                }
            ],
        }

    def _read_domains(self) -> Dict[str, Any]:
        """Read domain list."""
        domains = {}
        for domain in OntologyComponent.objects.values_list("domain", flat=True).distinct():
            if domain:
                domains[domain] = OntologyComponent.objects.filter(domain=domain).count()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(domains, indent=2),
                }
            ],
        }

    def _read_critical(self) -> Dict[str, Any]:
        """Read critical components."""
        components = OntologyComponent.objects.filter(
            criticality__in=["critical", "high"]
        )

        critical_data = [
            {
                "module_path": c.module_path,
                "component_name": c.component_name,
                "purpose": c.purpose,
                "domain": c.domain,
                "criticality": c.criticality,
                "file_path": c.file_path,
            }
            for c in components
        ]

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(critical_data, indent=2),
                }
            ],
        }

    def _read_domain(self, domain: str) -> Dict[str, Any]:
        """Read domain-specific components."""
        components = OntologyComponent.objects.filter(domain__iexact=domain)

        domain_data = [
            {
                "module_path": c.module_path,
                "component_type": c.component_type,
                "component_name": c.component_name,
                "purpose": c.purpose,
                "criticality": c.criticality,
                "tags": c.tags,
                "file_path": c.file_path,
            }
            for c in components
        ]

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "domain": domain,
                        "count": len(domain_data),
                        "components": domain_data,
                    }, indent=2),
                }
            ],
        }

    def get_server_info(self) -> Dict[str, Any]:
        """Get MCP server information."""
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": {
                "tools": True,
                "resources": True,
                "prompts": False,  # Future feature
            },
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools in MCP format."""
        return [tool.to_dict() for tool in self.tools]

    def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources in MCP format."""
        return [resource.to_dict() for resource in self.resources]
