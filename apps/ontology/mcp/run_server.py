#!/usr/bin/env python
"""
MCP Server Entry Point.

Standalone script to run the Ontology MCP server.

Usage:
    python apps/ontology/mcp/run_server.py

Or with environment configuration:
    DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.development \\
        python apps/ontology/mcp/run_server.py
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings.development")

import django
django.setup()

from apps.ontology.mcp.server import OntologyMCPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def handle_stdio_request(request_line: str, server: OntologyMCPServer) -> dict:
    """
    Handle a single MCP request via stdio.

    Args:
        request_line: JSON-encoded request
        server: MCP server instance

    Returns:
        Response dictionary
    """
    try:
        request = json.loads(request_line)
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": server.get_server_info(),
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {"tools": server.list_tools()},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            result = server.handle_tool_call(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": result,
            }

        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {"resources": server.list_resources()},
            }

        elif method == "resources/read":
            uri = params.get("uri")
            result = server.handle_resource_read(uri)
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": result,
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error",
            },
        }
    except (KeyError, ValueError, TypeError) as e:
        logger.exception(f"Error handling request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id") if isinstance(request, dict) else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}",
            },
        }


def run_stdio_server():
    """
    Run MCP server in stdio mode.

    Reads JSON-RPC requests from stdin and writes responses to stdout.
    """
    logger.info("Starting Ontology MCP Server (stdio mode)")
    server = OntologyMCPServer()

    logger.info(f"Server info: {server.get_server_info()}")
    logger.info(f"Registered {len(server.tools)} tools")
    logger.info(f"Registered {len(server.resources)} resources")

    # Main request loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        logger.debug(f"Received request: {line[:100]}...")

        response = handle_stdio_request(line, server)
        response_json = json.dumps(response)

        print(response_json, flush=True)
        logger.debug(f"Sent response: {response_json[:100]}...")


def main():
    """Main entry point."""
    try:
        run_stdio_server()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except (OSError, IOError, RuntimeError) as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
