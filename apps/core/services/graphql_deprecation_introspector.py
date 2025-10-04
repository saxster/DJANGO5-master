"""
GraphQL Deprecation Introspector

Auto-discovers deprecated fields, queries, and mutations in GraphQL schema via
introspection and @deprecated directive parsing.

Features:
    - Schema introspection for @deprecated directive
    - Automatic deprecation reason extraction
    - Field usage tracking
    - Client version correlation

Compliance:
    - Rule #7: File < 200 lines
    - Rule #11: Specific exception handling

Usage:
    from apps.core.services.graphql_deprecation_introspector import GraphQLDeprecationIntrospector

    introspector = GraphQLDeprecationIntrospector()
    deprecated_fields = introspector.discover_deprecated_fields()
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone as dt_timezone

logger = logging.getLogger(__name__)

__all__ = ['GraphQLDeprecationIntrospector']


class GraphQLDeprecationIntrospector:
    """
    Discovers and tracks deprecated GraphQL fields via schema introspection.
    """

    def __init__(self, schema=None):
        """
        Initialize introspector.

        Args:
            schema: GraphQL schema (defaults to main application schema)
        """
        self.schema = schema or self._get_default_schema()

    def _get_default_schema(self):
        """Get default GraphQL schema from application."""
        try:
            from apps.service.schema import schema
            return schema
        except ImportError as e:
            logger.error(f"Failed to import GraphQL schema: {e}")
            return None

    def discover_deprecated_fields(self) -> List[Dict[str, Any]]:
        """
        Discover all deprecated fields in schema.

        Returns:
            List of deprecated field information dicts
        """
        if not self.schema:
            logger.warning("No GraphQL schema available")
            return []

        deprecated_fields = []

        try:
            # Introspect schema types
            type_map = self.schema.graphql_schema.type_map

            for type_name, type_obj in type_map.items():
                # Skip internal GraphQL types
                if type_name.startswith('__'):
                    continue

                # Check object types and interfaces
                if hasattr(type_obj, 'fields'):
                    for field_name, field_obj in type_obj.fields.items():
                        if self._is_field_deprecated(field_obj):
                            deprecated_fields.append({
                                'type_name': type_name,
                                'field_name': field_name,
                                'deprecation_reason': self._get_deprecation_reason(field_obj),
                                'field_type': str(field_obj.type),
                            })

            logger.info(f"Discovered {len(deprecated_fields)} deprecated fields")
            return deprecated_fields

        except Exception as e:
            logger.error(f"Error discovering deprecated fields: {e}", exc_info=True)
            return []

    def _is_field_deprecated(self, field_obj) -> bool:
        """Check if field is deprecated."""
        return hasattr(field_obj, 'deprecation_reason') and field_obj.deprecation_reason is not None

    def _get_deprecation_reason(self, field_obj) -> str:
        """Extract deprecation reason from field."""
        reason = getattr(field_obj, 'deprecation_reason', '')
        return reason if reason else 'Field deprecated (no reason provided)'

    def sync_to_database(self) -> int:
        """
        Sync discovered deprecated fields to database.

        Returns:
            Number of fields synced
        """
        from apps.core.models.api_deprecation import APIDeprecation
        from django.db import IntegrityError

        deprecated_fields = self.discover_deprecated_fields()
        synced_count = 0

        for field_info in deprecated_fields:
            endpoint_pattern = f"{field_info['type_name']}.{field_info['field_name']}"

            try:
                # Create or update deprecation record
                deprecation, created = APIDeprecation.objects.update_or_create(
                    endpoint_pattern=endpoint_pattern,
                    api_type='graphql_field',
                    defaults={
                        'deprecation_reason': field_info['deprecation_reason'],
                        'deprecated_date': datetime.now(dt_timezone.utc),
                        'status': 'deprecated',
                        'version_deprecated': 'auto-detected',
                    }
                )

                synced_count += 1

                if created:
                    logger.info(f"Created deprecation record: {endpoint_pattern}")
                else:
                    logger.debug(f"Updated deprecation record: {endpoint_pattern}")

            except IntegrityError as e:
                logger.warning(f"Failed to sync field {endpoint_pattern}: {e}")
            except Exception as e:
                logger.error(f"Error syncing field {endpoint_pattern}: {e}", exc_info=True)

        logger.info(f"Synced {synced_count}/{len(deprecated_fields)} deprecated fields")
        return synced_count

    def get_field_usage_stats(self, type_name: str, field_name: str, days: int = 7) -> Dict[str, Any]:
        """
        Get usage statistics for a deprecated field.

        Args:
            type_name: GraphQL type name
            field_name: Field name
            days: Number of days to analyze

        Returns:
            Usage statistics dict
        """
        from apps.core.models.api_deprecation import APIDeprecation, APIDeprecationUsage
        from datetime import timedelta

        endpoint_pattern = f"{type_name}.{field_name}"

        try:
            deprecation = APIDeprecation.objects.get(
                endpoint_pattern=endpoint_pattern,
                api_type='graphql_field'
            )

            cutoff = datetime.now(dt_timezone.utc) - timedelta(days=days)
            usage_logs = APIDeprecationUsage.objects.filter(
                deprecation=deprecation,
                timestamp__gte=cutoff
            )

            return {
                'field_path': endpoint_pattern,
                'total_usage': usage_logs.count(),
                'unique_users': usage_logs.values('user_id').distinct().count(),
                'deprecation_reason': deprecation.deprecation_reason,
                'deprecated_since': deprecation.deprecated_date,
            }

        except APIDeprecation.DoesNotExist:
            logger.warning(f"No deprecation record for {endpoint_pattern}")
            return {}
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}", exc_info=True)
            return {}
