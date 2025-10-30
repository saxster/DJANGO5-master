"""
Tests for MCP Server.

Run with: pytest apps/ontology/mcp/test_server.py -v
"""

import json
import pytest
from unittest.mock import Mock, patch

from apps.ontology.mcp.server import (
    OntologyMCPServer,
    MCPTool,
    MCPResource,
)


class TestMCPServer:
    """Test MCP server initialization and configuration."""

    @pytest.fixture
    def server(self):
        """Create server instance."""
        return OntologyMCPServer()

    def test_server_initialization(self, server):
        """Test server initializes with correct metadata."""
        assert server.name == "ontology-server"
        assert server.version == "1.0.0"
        assert len(server.tools) > 0
        assert len(server.resources) > 0

    def test_get_server_info(self, server):
        """Test server info endpoint."""
        info = server.get_server_info()
        assert info["name"] == "ontology-server"
        assert info["version"] == "1.0.0"
        assert "capabilities" in info
        assert info["capabilities"]["tools"] is True
        assert info["capabilities"]["resources"] is True

    def test_list_tools(self, server):
        """Test tools listing."""
        tools = server.list_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 4  # ontology_query, get, stats, relationships

        # Check tool structure
        tool = tools[0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool

    def test_list_resources(self, server):
        """Test resources listing."""
        resources = server.list_resources()
        assert isinstance(resources, list)
        assert len(resources) >= 4  # graph, domains, critical, domain/*

        # Check resource structure
        resource = resources[0]
        assert "uri" in resource
        assert "name" in resource
        assert "description" in resource
        assert "mimeType" in resource


class TestMCPTools:
    """Test MCP tool definitions."""

    def test_tool_creation(self):
        """Test MCPTool creation."""
        tool = MCPTool(
            name="test_tool",
            description="Test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "param": {"type": "string"},
                },
            },
        )

        tool_dict = tool.to_dict()
        assert tool_dict["name"] == "test_tool"
        assert tool_dict["description"] == "Test tool"
        assert "inputSchema" in tool_dict


class TestMCPResources:
    """Test MCP resource definitions."""

    def test_resource_creation(self):
        """Test MCPResource creation."""
        resource = MCPResource(
            uri="test://resource",
            name="Test Resource",
            description="Test resource",
            mime_type="application/json",
        )

        resource_dict = resource.to_dict()
        assert resource_dict["uri"] == "test://resource"
        assert resource_dict["name"] == "Test Resource"
        assert resource_dict["mimeType"] == "application/json"


@pytest.mark.django_db
class TestToolHandlers:
    """Test tool execution handlers."""

    @pytest.fixture
    def server(self):
        """Create server instance."""
        return OntologyMCPServer()

    @pytest.fixture
    def sample_component(self):
        """Create sample ontology component."""
        from apps.ontology.models import OntologyComponent
        return OntologyComponent.objects.create(
            module_path="apps.test.module",
            component_type="class",
            component_name="TestClass",
            purpose="Test component",
            domain="test",
            criticality="medium",
            tags=["test", "sample"],
            file_path="apps/test/module.py",
            line_number=10,
        )

    def test_handle_query_tool(self, server, sample_component):
        """Test ontology_query tool handler."""
        result = server.handle_tool_call(
            "ontology_query",
            {"query": "test", "limit": 10},
        )

        assert "content" in result
        assert not result.get("isError")

        # Parse content
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert "components" in data
        assert data["count"] > 0

    def test_handle_get_tool(self, server, sample_component):
        """Test ontology_get tool handler."""
        result = server.handle_tool_call(
            "ontology_get",
            {"module_path": "apps.test.module"},
        )

        assert "content" in result
        assert not result.get("isError")

        # Parse content
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert data["module_path"] == "apps.test.module"
        assert data["component_name"] == "TestClass"

    def test_handle_get_tool_not_found(self, server):
        """Test ontology_get with non-existent component."""
        result = server.handle_tool_call(
            "ontology_get",
            {"module_path": "apps.nonexistent.module"},
        )

        assert result.get("isError") is True
        assert "not found" in result["content"][0]["text"].lower()

    def test_handle_stats_tool(self, server, sample_component):
        """Test ontology_stats tool handler."""
        result = server.handle_tool_call(
            "ontology_stats",
            {"detailed": False},
        )

        assert "content" in result
        assert not result.get("isError")

        # Parse content
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert "total_components" in data
        assert "by_type" in data
        assert "by_criticality" in data

    def test_handle_stats_tool_detailed(self, server, sample_component):
        """Test ontology_stats with detailed=True."""
        result = server.handle_tool_call(
            "ontology_stats",
            {"detailed": True},
        )

        assert "content" in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert "detailed_domains" in data

    def test_handle_relationships_tool(self, server, sample_component):
        """Test ontology_relationships tool handler."""
        result = server.handle_tool_call(
            "ontology_relationships",
            {
                "component": "TestClass",
                "relationship_type": "all",
                "depth": 1,
            },
        )

        assert "content" in result
        assert not result.get("isError")

        # Parse content
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert "component" in data
        assert "relationships" in data

    def test_handle_unknown_tool(self, server):
        """Test handling of unknown tool."""
        result = server.handle_tool_call(
            "unknown_tool",
            {},
        )

        assert result.get("isError") is True
        assert "Unknown tool" in result["content"][0]["text"]


@pytest.mark.django_db
class TestResourceHandlers:
    """Test resource read handlers."""

    @pytest.fixture
    def server(self):
        """Create server instance."""
        return OntologyMCPServer()

    @pytest.fixture
    def sample_component(self):
        """Create sample ontology component."""
        from apps.ontology.models import OntologyComponent
        return OntologyComponent.objects.create(
            module_path="apps.test.module",
            component_type="class",
            component_name="TestClass",
            purpose="Test component",
            domain="test",
            criticality="critical",
            tags=["test"],
            file_path="apps/test/module.py",
            line_number=10,
        )

    def test_read_graph_resource(self, server, sample_component):
        """Test reading complete graph resource."""
        result = server.handle_resource_read("ontology://graph")

        assert "content" in result
        assert not result.get("isError")

        # Parse content
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert "components" in data
        assert "relationships" in data

    def test_read_domains_resource(self, server, sample_component):
        """Test reading domains resource."""
        result = server.handle_resource_read("ontology://domains")

        assert "content" in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert isinstance(data, dict)
        assert "test" in data  # Our sample component's domain

    def test_read_critical_resource(self, server, sample_component):
        """Test reading critical components resource."""
        result = server.handle_resource_read("ontology://critical")

        assert "content" in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert isinstance(data, list)
        # Should include our critical component
        assert any(c["module_path"] == "apps.test.module" for c in data)

    def test_read_domain_resource(self, server, sample_component):
        """Test reading domain-specific resource."""
        result = server.handle_resource_read("ontology://domain/test")

        assert "content" in result
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert data["domain"] == "test"
        assert data["count"] > 0
        assert isinstance(data["components"], list)

    def test_read_unknown_resource(self, server):
        """Test reading unknown resource."""
        result = server.handle_resource_read("ontology://unknown")

        assert result.get("isError") is True
        assert "Unknown resource" in result["content"][0]["text"]


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def server(self):
        """Create server instance."""
        return OntologyMCPServer()

    def test_query_with_criticality_filter(self, server):
        """Test query with criticality filter."""
        result = server.handle_tool_call(
            "ontology_query",
            {
                "query": "test",
                "limit": 10,
                "criticality": "critical",
            },
        )

        assert "content" in result

    def test_relationships_with_depth(self, server):
        """Test relationships with various depth values."""
        for depth in [1, 2, 3]:
            result = server.handle_tool_call(
                "ontology_relationships",
                {
                    "component": "test",
                    "relationship_type": "all",
                    "depth": depth,
                },
            )
            # Should not error even if component not found
            assert "content" in result

    def test_empty_query(self, server):
        """Test query with empty string."""
        result = server.handle_tool_call(
            "ontology_query",
            {"query": "", "limit": 10},
        )

        assert "content" in result
        # Empty query should still return valid response
        assert not result.get("isError")
