"""
NOC Natural Language Query Parser.

LLM-powered parsing using Anthropic Claude to extract structured query parameters
from natural language text. Follows .claude/rules.md Rule #7 (<150 lines) and
Rule #11 (specific exception handling).
"""

import logging
from typing import Dict, Any, Optional
from django.conf import settings
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

__all__ = ['QueryParser']

logger = logging.getLogger('noc.nl_query')


class QueryParser:
    """
    Parse natural language queries into structured parameters using Claude.

    Uses Anthropic's function calling API to extract:
    - query_type: Type of query (alerts, incidents, metrics, fraud, trends, predictions)
    - filters: Structured filters (severity, site, person, status, etc.)
    - time_range: Temporal scope (hours, days, date ranges)
    - output_format: Desired response format (summary, detailed, table)
    """

    QUERY_SCHEMA = {
        "name": "extract_query_parameters",
        "description": "Extract query parameters from natural language for NOC monitoring and Help Desk ticketing",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["alerts", "incidents", "metrics", "fraud", "trends", "predictions", "tickets"],
                    "description": "Type of data to query: alerts (real-time issues), incidents (grouped alerts), metrics (telemetry), fraud (security anomalies), trends (patterns), predictions (ML forecasts), tickets (help desk tickets)"
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]},
                            "description": "Alert severity levels to include"
                        },
                        "status": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["NEW", "ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "CLOSED", "OPEN", "ONHOLD", "CANCELLED"]},
                            "description": "Alert/incident/ticket status"
                        },
                        "priority": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
                            "description": "Priority levels for tickets"
                        },
                        "assignment_type": {
                            "type": "string",
                            "enum": ["my_tickets", "my_groups", "unassigned"],
                            "description": "Assignment filter: my_tickets (assigned to me), my_groups (assigned to my groups), unassigned (no assignment)"
                        },
                        "escalation": {
                            "type": "object",
                            "properties": {
                                "is_escalated": {"type": "boolean"},
                                "level": {"type": "integer"},
                                "min_level": {"type": "integer"}
                            },
                            "description": "Escalation filters for tickets"
                        },
                        "sla_status": {
                            "type": "string",
                            "enum": ["overdue", "approaching", "compliant"],
                            "description": "SLA compliance status: overdue (past SLA), approaching (< 2 hours), compliant (on track)"
                        },
                        "source": {
                            "type": "string",
                            "enum": ["SYSTEMGENERATED", "USERDEFINED"],
                            "description": "Ticket source type"
                        },
                        "category_id": {
                            "type": "integer",
                            "description": "Ticket category ID"
                        },
                        "category_name": {
                            "type": "string",
                            "description": "Ticket category name (partial match)"
                        },
                        "site_id": {
                            "type": "integer",
                            "description": "Specific site/location ID"
                        },
                        "site_name": {
                            "type": "string",
                            "description": "Site/location name (will be resolved to ID)"
                        },
                        "person_id": {
                            "type": "integer",
                            "description": "Specific person ID"
                        },
                        "person_name": {
                            "type": "string",
                            "description": "Person name (will be resolved to ID)"
                        },
                        "alert_type": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Alert types (e.g., SLA_BREACH, ATTENDANCE_ANOMALY, DEVICE_OFFLINE)"
                        },
                        "client_id": {
                            "type": "integer",
                            "description": "Client organization ID"
                        }
                    },
                    "description": "Query filters to narrow down results"
                },
                "time_range": {
                    "type": "object",
                    "properties": {
                        "hours": {
                            "type": "integer",
                            "description": "Number of hours to look back (e.g., 24 for last day)"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back"
                        },
                        "start_date": {
                            "type": "string",
                            "format": "date",
                            "description": "Start date for range query (YYYY-MM-DD)"
                        },
                        "end_date": {
                            "type": "string",
                            "format": "date",
                            "description": "End date for range query (YYYY-MM-DD)"
                        }
                    },
                    "description": "Temporal scope of the query"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["summary", "detailed", "table", "json"],
                    "description": "Desired response format: summary (brief overview), detailed (full info), table (structured data), json (raw data)"
                },
                "aggregation": {
                    "type": "object",
                    "properties": {
                        "group_by": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["site", "person", "severity", "status", "alert_type", "hour", "day"]},
                            "description": "Fields to group results by"
                        },
                        "order_by": {
                            "type": "string",
                            "enum": ["count", "severity", "timestamp", "priority"],
                            "description": "Sort order for results"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "minimum": 1,
                            "maximum": 1000
                        }
                    },
                    "description": "Aggregation and sorting options"
                }
            },
            "required": ["query_type"]
        }
    }

    @staticmethod
    def parse_query(query_text: str) -> Dict[str, Any]:
        """
        Parse natural language query into structured parameters.

        Args:
            query_text: Natural language query string

        Returns:
            Dict with keys: query_type, filters, time_range, output_format, aggregation

        Raises:
            ValueError: If query text is invalid or parsing fails
            ImportError: If anthropic library not installed
            ConnectionError: If API call fails
        """
        if not query_text or not query_text.strip():
            raise ValueError("Query text cannot be empty")

        if len(query_text) > 1000:
            raise ValueError("Query text exceeds maximum length of 1000 characters")

        try:
            import anthropic
        except ImportError:
            logger.error("Anthropic library not installed")
            raise ImportError(
                "anthropic library required. Install with: pip install anthropic"
            )

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured in settings. "
                "Set environment variable or update settings/llm_providers.py"
            )

        try:
            client = anthropic.Anthropic(api_key=api_key)

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                tools=[QueryParser.QUERY_SCHEMA],
                messages=[{
                    "role": "user",
                    "content": f"Parse this NOC query and extract parameters: {query_text}"
                }],
                timeout=(5, 30)  # Rule #18: Network timeouts required
            )

            # Extract tool use from response
            if not message.content or message.stop_reason != "tool_use":
                logger.warning(f"No tool use in Claude response: {message.stop_reason}")
                return QueryParser._create_default_response(query_text)

            tool_use = None
            for block in message.content:
                if block.type == "tool_use":
                    tool_use = block
                    break

            if not tool_use:
                logger.warning("No tool_use block found in response")
                return QueryParser._create_default_response(query_text)

            # Validate and normalize extracted parameters
            params = tool_use.input
            normalized = QueryParser._normalize_parameters(params)

            logger.info(
                f"Parsed query successfully",
                extra={
                    'query_length': len(query_text),
                    'query_type': normalized.get('query_type'),
                    'has_filters': bool(normalized.get('filters')),
                }
            )

            return normalized

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error calling Anthropic API: {e}", exc_info=True)
            raise ConnectionError(f"Failed to connect to Claude API: {e}")
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}", exc_info=True)
            raise ValueError(f"Claude API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing query: {e}", exc_info=True)
            raise ValueError(f"Failed to parse query: {e}")

    @staticmethod
    def _normalize_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and validate extracted parameters.

        Args:
            params: Raw parameters from Claude

        Returns:
            Normalized parameter dict with defaults
        """
        normalized = {
            'query_type': params.get('query_type', 'alerts'),
            'filters': params.get('filters', {}),
            'time_range': params.get('time_range', {'hours': 24}),
            'output_format': params.get('output_format', 'summary'),
            'aggregation': params.get('aggregation', {}),
        }

        # Set defaults for aggregation
        if 'limit' not in normalized['aggregation']:
            normalized['aggregation']['limit'] = 100

        # Ensure limit is within bounds
        limit = normalized['aggregation']['limit']
        normalized['aggregation']['limit'] = max(1, min(limit, 1000))

        return normalized

    @staticmethod
    def _create_default_response(query_text: str) -> Dict[str, Any]:
        """
        Create default response when parsing fails.

        Args:
            query_text: Original query text

        Returns:
            Default parameter dict (general alerts query)
        """
        return {
            'query_type': 'alerts',
            'filters': {},
            'time_range': {'hours': 24},
            'output_format': 'summary',
            'aggregation': {'limit': 100},
            'parse_fallback': True,
            'original_query': query_text,
        }
