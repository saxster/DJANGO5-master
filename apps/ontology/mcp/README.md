# Ontology MCP Server

Model Context Protocol (MCP) server implementation for the codebase ontology system.

## Overview

This MCP server exposes the ontology knowledge graph to LLM clients (Claude Desktop, Claude Code, etc.) following Anthropic's MCP specification: https://modelcontextprotocol.io/introduction

## Features

### Tools (Callable Operations)

1. **ontology_query** - Query by domain, tag, purpose, or component name
   - Input: `query` (string), `limit` (integer), `criticality` (enum)
   - Returns: List of matching components with metadata

2. **ontology_get** - Get specific component by module path
   - Input: `module_path` (string)
   - Returns: Complete component details with relationships

3. **ontology_stats** - Get coverage statistics
   - Input: `detailed` (boolean)
   - Returns: Component counts, domain/criticality breakdown

4. **ontology_relationships** - Query component relationships
   - Input: `component` (string), `relationship_type` (enum), `depth` (integer)
   - Returns: Relationship graph with configurable traversal depth

### Resources (Static/Dynamic Content)

1. **ontology://graph** - Complete knowledge graph (all components + relationships)
2. **ontology://domains** - List of domains with component counts
3. **ontology://critical** - All critical/high-criticality components
4. **ontology://domain/{name}** - Components in specific domain

## Installation

### For Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "ontology": {
      "command": "python",
      "args": [
        "/absolute/path/to/apps/ontology/mcp/run_server.py"
      ],
      "env": {
        "DJANGO_SETTINGS_MODULE": "intelliwiz_config.settings.development"
      }
    }
  }
}
```

### For Claude Code

Add to your workspace MCP configuration (`.claude/mcp_config.json`):

```json
{
  "mcpServers": {
    "ontology": {
      "command": "python",
      "args": [
        "./apps/ontology/mcp/run_server.py"
      ],
      "env": {
        "DJANGO_SETTINGS_MODULE": "intelliwiz_config.settings.development"
      }
    }
  }
}
```

## Usage Examples

### Query by Domain

```json
{
  "method": "tools/call",
  "params": {
    "name": "ontology_query",
    "arguments": {
      "query": "people",
      "limit": 10
    }
  }
}
```

### Get Specific Component

```json
{
  "method": "tools/call",
  "params": {
    "name": "ontology_get",
    "arguments": {
      "module_path": "apps.peoples.models.People"
    }
  }
}
```

### Get Coverage Stats

```json
{
  "method": "tools/call",
  "params": {
    "name": "ontology_stats",
    "arguments": {
      "detailed": true
    }
  }
}
```

### Query Relationships

```json
{
  "method": "tools/call",
  "params": {
    "name": "ontology_relationships",
    "arguments": {
      "component": "People",
      "relationship_type": "all",
      "depth": 2
    }
  }
}
```

### Read Resource

```json
{
  "method": "resources/read",
  "params": {
    "uri": "ontology://critical"
  }
}
```

## Running the Server

### Standalone Mode (for testing)

```bash
# From project root
python apps/ontology/mcp/run_server.py
```

The server will listen on stdin/stdout for JSON-RPC requests.

### With Claude Desktop

Once configured, the server will automatically start when Claude Desktop launches.

### With Claude Code

The server will be available as an MCP resource within Claude Code sessions.

## Development

### Testing the Server

```bash
# Test query tool
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ontology_query","arguments":{"query":"auth"}}}' | python apps/ontology/mcp/run_server.py

# Test resource read
echo '{"jsonrpc":"2.0","id":2,"method":"resources/read","params":{"uri":"ontology://domains"}}' | python apps/ontology/mcp/run_server.py
```

### Extending the Server

1. Add new tools in `OntologyMCPServer._register_tools()`
2. Add new resources in `OntologyMCPServer._register_resources()`
3. Implement handlers in `handle_tool_call()` or `handle_resource_read()`

## Protocol Compliance

This implementation follows the MCP specification:

- JSON-RPC 2.0 transport layer
- Standard MCP methods:
  - `initialize` - Server initialization
  - `tools/list` - List available tools
  - `tools/call` - Execute tool
  - `resources/list` - List available resources
  - `resources/read` - Read resource content
- Proper error handling with standard error codes
- Content types and MIME types

## Troubleshooting

### Server Won't Start

- Check Django settings are configured
- Ensure database is accessible
- Verify Python environment is correct

### No Results from Queries

- Run ontology extraction first: `python manage.py extract_ontology`
- Check database has ontology data
- Verify query syntax

### Claude Desktop Can't Connect

- Check absolute paths in configuration
- Verify Python executable path
- Check logs in Claude Desktop console

## See Also

- [MCP Specification](https://modelcontextprotocol.io/introduction)
- [Ontology System Documentation](../README.md)
- [Smart Context Injection](../claude/smart_injection.py)
- [Slash Command Integration](/.claude/commands/ontology.md)
