"""
OpenAPI Preprocessing Hooks

Customizes OpenAPI schema generation before final output.

Compliance with .claude/rules.md:
- Rule #7: Functions < 50 lines
- Rule #11: Specific exception handling
"""

import logging
from typing import List, Tuple, Any

logger = logging.getLogger(__name__)


def add_v2_tags(endpoints: List[Tuple[str, str, str, Any]]) -> List[Tuple[str, str, str, Any]]:
    """
    Add 'Mobile Sync' tag to all v2 endpoints for better organization.

    Args:
        endpoints: List of (path, path_regex, method, callback) tuples

    Returns:
        Modified endpoints list with v2 tags

    Example:
        /api/v2/sync/voice/ → Tagged as "Mobile Sync"
    """
    processed = []

    for path, path_regex, method, callback in endpoints:
        # Add v2 tag to v2 endpoints
        if '/api/v2/' in path:
            # Inject tag metadata (drf-spectacular will pick this up)
            if hasattr(callback, 'cls') and hasattr(callback.cls, 'tags'):
                if 'Mobile Sync' not in callback.cls.tags:
                    callback.cls.tags = getattr(callback.cls, 'tags', []) + ['Mobile Sync']
            elif hasattr(callback, 'actions'):
                # DRF ViewSet
                pass

        processed.append((path, path_regex, method, callback))

    logger.info(f"Preprocessed {len(processed)} endpoints for OpenAPI schema")
    return processed


def filter_internal_endpoints(endpoints: List[Tuple[str, str, str, Any]]) -> List[Tuple[str, str, str, Any]]:
    """
    Filter out internal/admin-only endpoints from public OpenAPI schema.

    Args:
        endpoints: List of (path, path_regex, method, callback) tuples

    Returns:
        Filtered endpoints list

    Filters:
        - /admin/ paths (Django admin)
        - /__debug__/ paths (Debug toolbar)
        - Internal monitoring endpoints
    """
    filtered = []

    internal_prefixes = [
        '/admin/',
        '/__debug__/',
        '/monitoring/internal/',
        '/_internal/',
    ]

    for path, path_regex, method, callback in endpoints:
        # Skip internal paths
        if any(path.startswith(prefix) for prefix in internal_prefixes):
            continue

        filtered.append((path, path_regex, method, callback))

    filtered_count = len(endpoints) - len(filtered)
    if filtered_count > 0:
        logger.info(f"Filtered {filtered_count} internal endpoints from OpenAPI schema")

    return filtered


__all__ = [
    'add_v2_tags',
    'filter_internal_endpoints',
]
