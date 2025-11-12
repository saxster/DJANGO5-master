"""
NOC Query Result Formatter.

Formats query results into natural language responses with LLM-generated insights.
Follows .claude/rules.md Rule #7 (<150 lines) and Rule #11 (specific exceptions).
"""

import logging
from typing import Dict, Any, List
from django.conf import settings
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

__all__ = ['ResultFormatter']

logger = logging.getLogger('noc.nl_query')


class ResultFormatter:
    """
    Format query results as natural language responses.

    Supports multiple output formats:
    - summary: Brief overview with key statistics
    - detailed: Full information with descriptions
    - table: Structured tabular data
    - json: Raw JSON data
    """

    @staticmethod
    def format_results(results: Dict[str, Any], output_format: str = 'summary') -> Dict[str, Any]:
        """
        Format query results based on desired output format.

        Args:
            results: Raw query results from QueryExecutor
            output_format: Desired format (summary, detailed, table, json)

        Returns:
            Dict with keys: summary (str), data (list), insights (str), format (str)

        Raises:
            ValueError: If output_format is invalid
        """
        if output_format not in ['summary', 'detailed', 'table', 'json']:
            raise ValueError(f"Invalid output format: {output_format}")

        if output_format == 'json':
            return ResultFormatter._format_json(results)

        # Generate summary text
        summary = ResultFormatter._generate_summary(results)

        # Format data based on requested format
        if output_format == 'summary':
            data = ResultFormatter._format_summary_data(results)
        elif output_format == 'detailed':
            data = ResultFormatter._format_detailed_data(results)
        else:  # table
            data = ResultFormatter._format_table_data(results)

        # Generate insights using LLM (optional, falls back to rule-based)
        insights = ResultFormatter._generate_insights(results)

        return {
            'summary': summary,
            'data': data,
            'insights': insights,
            'format': output_format,
            'metadata': results.get('metadata', {}),
        }

    @staticmethod
    def _generate_summary(results: Dict[str, Any]) -> str:
        """
        Generate natural language summary of results.

        Args:
            results: Query results dict

        Returns:
            Summary text string
        """
        metadata = results.get('metadata', {})
        query_type = metadata.get('query_type', 'unknown')
        count = metadata.get('returned_count', 0)
        total = metadata.get('total_count', 0)

        if count == 0:
            return f"No {query_type} found matching your query criteria."

        summary_parts = [
            f"Found {count} {query_type}",
        ]

        if count < total:
            summary_parts.append(f"(showing {count} of {total} total)")

        # Add query-specific details
        if query_type == 'alerts':
            severity_counts = ResultFormatter._count_by_field(results.get('results', []), 'severity')
            if severity_counts:
                top_severity = max(severity_counts.items(), key=lambda x: x[1])
                summary_parts.append(f"Most common severity: {top_severity[0]} ({top_severity[1]} alerts)")

        elif query_type == 'incidents':
            state_counts = ResultFormatter._count_by_field(results.get('results', []), 'state')
            if state_counts:
                summary_parts.append(f"Statuses: {', '.join(f'{k}={v}' for k, v in state_counts.items())}")

        elif query_type == 'trends':
            grouped_by = metadata.get('grouped_by', [])
            if grouped_by:
                summary_parts.append(f"Grouped by: {', '.join(grouped_by)}")

        return '. '.join(summary_parts) + '.'

    @staticmethod
    def _generate_insights(results: Dict[str, Any]) -> str:
        """
        Generate insights from results using LLM or rule-based logic.

        Args:
            results: Query results dict

        Returns:
            Insights text string
        """
        # Try LLM-based insights first
        llm_insights = ResultFormatter._generate_llm_insights(results)
        if llm_insights:
            return llm_insights

        # Fallback to rule-based insights
        return ResultFormatter._generate_rule_based_insights(results)

    @staticmethod
    def _generate_llm_insights(results: Dict[str, Any]) -> str:
        """
        Generate insights using Claude (optional enhancement).

        Args:
            results: Query results dict

        Returns:
            Insights text or empty string if LLM unavailable
        """
        try:
            import anthropic
        except ImportError:
            return ""

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            return ""

        metadata = results.get('metadata', {})
        summary = ResultFormatter._generate_summary(results)

        try:
            client = anthropic.Anthropic(api_key=api_key)

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": f"Analyze this NOC query result and provide 1-2 actionable insights in 1-2 sentences:\n\n{summary}\n\nQuery type: {metadata.get('query_type')}\nTotal results: {metadata.get('total_count')}"
                }],
                timeout=(5, 15)
            )

            if message.content and len(message.content) > 0:
                return message.content[0].text.strip()

        except NETWORK_EXCEPTIONS as e:
            logger.warning(f"Failed to generate LLM insights: {e}")
        except NETWORK_EXCEPTIONS as e:
            logger.warning(f"Unexpected error generating insights: {e}")

        return ""

    @staticmethod
    def _generate_rule_based_insights(results: Dict[str, Any]) -> str:
        """
        Generate insights using rule-based logic.

        Args:
            results: Query results dict

        Returns:
            Insights text string
        """
        metadata = results.get('metadata', {})
        query_type = metadata.get('query_type')
        data = results.get('results', [])

        if not data:
            return "No data available for analysis. Try adjusting your query filters or time range."

        insights = []

        if query_type == 'alerts':
            # Check for concentration in specific sites
            site_counts = ResultFormatter._count_by_field(data, 'bu_id')
            if site_counts and len(site_counts) > 0:
                total_sites = len(site_counts)
                if total_sites == 1:
                    insights.append("All alerts concentrated in a single site - investigate site-specific issues")
                elif total_sites <= 3:
                    insights.append(f"Alerts concentrated in {total_sites} sites - may indicate localized problems")

            # Check severity distribution
            severity_counts = ResultFormatter._count_by_field(data, 'severity')
            critical_count = severity_counts.get('CRITICAL', 0)
            high_count = severity_counts.get('HIGH', 0)
            if critical_count > 0:
                insights.append(f"{critical_count} CRITICAL alerts require immediate attention")
            elif high_count > len(data) * 0.5:
                insights.append(f"High proportion of HIGH severity alerts ({high_count}/{len(data)}) - review escalation thresholds")

        elif query_type == 'incidents':
            # Check for unresolved incidents
            state_counts = ResultFormatter._count_by_field(data, 'state')
            unresolved = sum(state_counts.get(state, 0) for state in ['NEW', 'ACKNOWLEDGED', 'ASSIGNED', 'IN_PROGRESS'])
            if unresolved > 0:
                insights.append(f"{unresolved} incidents still open - consider prioritizing resolution")

        elif query_type == 'trends':
            if len(data) > 0:
                top_item = data[0]
                count_key = 'count' if isinstance(top_item, dict) else None
                if count_key and count_key in top_item:
                    insights.append(f"Top result has {top_item[count_key]} occurrences - dominant pattern identified")

        return ' '.join(insights) if insights else "No significant patterns detected in the data."

    @staticmethod
    def _format_summary_data(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format data for summary output."""
        data = results.get('results', [])
        metadata = results.get('metadata', {})
        query_type = metadata.get('query_type')

        if query_type == 'trends':
            # Trends already aggregated
            return data[:10]  # Top 10 items

        # For other types, return simplified records
        formatted = []
        for item in data[:10]:  # Top 10 items
            if hasattr(item, '__dict__'):
                formatted.append(ResultFormatter._simplify_model_instance(item))
            else:
                formatted.append(item)

        return formatted

    @staticmethod
    def _format_detailed_data(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format data for detailed output."""
        data = results.get('results', [])
        formatted = []

        for item in data:
            if hasattr(item, '__dict__'):
                formatted.append(ResultFormatter._serialize_model_instance(item))
            else:
                formatted.append(item)

        return formatted

    @staticmethod
    def _format_table_data(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format data for table output."""
        # Similar to detailed but with consistent column structure
        return ResultFormatter._format_detailed_data(results)

    @staticmethod
    def _format_json(results: Dict[str, Any]) -> Dict[str, Any]:
        """Format as raw JSON."""
        return {
            'summary': 'Raw JSON output',
            'data': ResultFormatter._format_detailed_data(results),
            'insights': '',
            'format': 'json',
            'metadata': results.get('metadata', {}),
        }

    @staticmethod
    def _count_by_field(data: List, field: str) -> Dict[str, int]:
        """Count occurrences of field values."""
        counts = {}
        for item in data:
            if hasattr(item, field):
                value = getattr(item, field)
            elif isinstance(item, dict) and field in item:
                value = item[field]
            else:
                continue

            counts[value] = counts.get(value, 0) + 1

        return counts

    @staticmethod
    def _simplify_model_instance(instance) -> Dict[str, Any]:
        """Simplify model instance to essential fields."""
        from apps.noc.models import NOCAlertEvent, NOCIncident

        if isinstance(instance, NOCAlertEvent):
            return {
                'id': instance.id,
                'type': instance.alert_type,
                'severity': instance.severity,
                'status': instance.status,
                'message': instance.message[:100] if hasattr(instance, 'message') else '',
                'created_at': instance.created_at.isoformat() if hasattr(instance, 'created_at') else None,
            }
        elif isinstance(instance, NOCIncident):
            return {
                'id': instance.id,
                'title': instance.title,
                'severity': instance.severity,
                'state': instance.state if hasattr(instance, 'state') else '',
                'alert_count': instance.alerts.count() if hasattr(instance, 'alerts') else 0,
                'created_at': instance.created_at.isoformat() if hasattr(instance, 'created_at') else None,
            }
        else:
            # Generic simplification
            return {
                'id': getattr(instance, 'id', None),
                'type': instance.__class__.__name__,
                'created_at': getattr(instance, 'created_at', None),
            }

    @staticmethod
    def _serialize_model_instance(instance) -> Dict[str, Any]:
        """Serialize model instance to full dict."""
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            # Convert datetime to ISO format
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            data[field.name] = value
        return data
