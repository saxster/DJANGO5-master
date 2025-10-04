"""
NOC Log Sanitization Utilities

Provides PII and sensitive data redaction for logging.
Ensures compliance with .claude/rules.md Rule #15 (logging data sanitization).

Security Features:
- SHA256 hashing for identifiers (irreversible, consistent)
- IP address subnet masking
- Permission list truncation
- Correlation ID preservation for debugging

Usage:
    from apps.noc.utils import sanitize_api_key_log

    sanitized = sanitize_api_key_log(
        api_key_id=key.id,
        api_key_name=key.name,
        allowed_ips=key.allowed_ips,
        permissions=key.permissions
    )
"""

import hashlib
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger('noc.sanitization')

__all__ = [
    'sanitize_api_key_log',
    'sanitize_ip_addresses',
    'sanitize_permissions_list',
    'hash_identifier',
]


def hash_identifier(value: Any, prefix: str = "hash") -> str:
    """
    Create irreversible hash of identifier for logging.

    Args:
        value: Value to hash (will be converted to string)
        prefix: Prefix for hashed value

    Returns:
        Hashed identifier in format: prefix_<first_8_chars_of_sha256>

    Example:
        >>> hash_identifier(12345, "api_key")
        'api_key_5994471a'
    """
    if value is None:
        return f"{prefix}_none"

    try:
        value_str = str(value)
        hash_obj = hashlib.sha256(value_str.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()[:8]  # First 8 chars for readability
        return f"{prefix}_{hash_hex}"
    except (ValueError, TypeError) as e:
        logger.error(
            f"Failed to hash identifier: {e}",
            extra={'prefix': prefix}
        )
        return f"{prefix}_error"


def sanitize_ip_addresses(ip_list: Optional[List[str]]) -> Dict[str, Any]:
    """
    Sanitize IP addresses for logging.

    Converts IP addresses to subnet notation to prevent exposure of exact IPs.

    Args:
        ip_list: List of IP addresses

    Returns:
        Dict with sanitized information:
        - count: Number of IPs
        - subnets: List of /24 subnets (e.g., 192.168.1.0/24)
        - has_whitelist: Boolean indicating if whitelist exists

    Example:
        >>> sanitize_ip_addresses(['192.168.1.100', '192.168.1.200'])
        {'count': 2, 'subnets': ['192.168.1.0/24'], 'has_whitelist': True}
    """
    if not ip_list:
        return {
            'count': 0,
            'subnets': [],
            'has_whitelist': False
        }

    try:
        # Extract /24 subnets (mask last octet)
        subnets = set()
        for ip in ip_list:
            # Simple subnet extraction (IPv4 only for now)
            parts = ip.split('.')
            if len(parts) == 4:
                subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                subnets.add(subnet)

        return {
            'count': len(ip_list),
            'subnets': sorted(list(subnets)),
            'has_whitelist': True
        }
    except (ValueError, AttributeError) as e:
        logger.warning(
            f"Failed to sanitize IP addresses: {e}",
            extra={'ip_count': len(ip_list) if ip_list else 0}
        )
        return {
            'count': len(ip_list) if ip_list else 0,
            'subnets': [],
            'has_whitelist': True
        }


def sanitize_permissions_list(permissions: Optional[List[str]]) -> Dict[str, Any]:
    """
    Sanitize permissions list for logging.

    Truncates long permission lists and categorizes them.

    Args:
        permissions: List of permission strings

    Returns:
        Dict with sanitized permission info:
        - count: Total number of permissions
        - categories: Unique permission categories (e.g., 'health', 'metrics')
        - has_admin: Boolean if admin permission exists

    Example:
        >>> sanitize_permissions_list(['health', 'metrics', 'alerts', 'admin'])
        {'count': 4, 'categories': ['admin', 'alerts', 'health', 'metrics'], 'has_admin': True}
    """
    if not permissions:
        return {
            'count': 0,
            'categories': [],
            'has_admin': False
        }

    try:
        return {
            'count': len(permissions),
            'categories': sorted(list(set(permissions)))[:10],  # Max 10 for readability
            'has_admin': 'admin' in permissions
        }
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Failed to sanitize permissions: {e}",
            extra={'perm_count': len(permissions) if permissions else 0}
        )
        return {
            'count': len(permissions) if permissions else 0,
            'categories': [],
            'has_admin': False
        }


def sanitize_api_key_log(
    api_key_id: Optional[int] = None,
    api_key_name: Optional[str] = None,
    allowed_ips: Optional[List[str]] = None,
    permissions: Optional[List[str]] = None,
    client_ip: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sanitize API key information for secure logging.

    Applies all sanitization strategies to prepare safe log data.

    Args:
        api_key_id: Database ID of API key
        api_key_name: Human-readable name of API key
        allowed_ips: List of whitelisted IP addresses
        permissions: List of permissions
        client_ip: Client IP address making the request
        correlation_id: Request correlation ID (preserved for tracing)

    Returns:
        Dict with sanitized information safe for logging:
        - api_key_hash: Hashed identifier
        - api_key_name_hash: Hashed name
        - ip_whitelist: Sanitized IP information
        - permissions: Sanitized permissions
        - client_subnet: Client IP subnet (not exact IP)
        - correlation_id: Preserved correlation ID

    Example:
        >>> sanitize_api_key_log(
        ...     api_key_id=123,
        ...     api_key_name="Production Monitor",
        ...     allowed_ips=['10.0.1.100'],
        ...     permissions=['health', 'metrics'],
        ...     client_ip='10.0.1.100'
        ... )
        {
            'api_key_hash': 'api_key_a665a45e',
            'api_key_name_hash': 'name_5e884898',
            'ip_whitelist': {'count': 1, 'subnets': ['10.0.1.0/24'], 'has_whitelist': True},
            'permissions': {'count': 2, 'categories': ['health', 'metrics'], 'has_admin': False},
            'client_subnet': '10.0.1.0/24',
            'correlation_id': None
        }
    """
    sanitized = {}

    # Hash identifiers (irreversible)
    if api_key_id is not None:
        sanitized['api_key_hash'] = hash_identifier(api_key_id, 'api_key')

    if api_key_name:
        sanitized['api_key_name_hash'] = hash_identifier(api_key_name, 'name')

    # Sanitize IP addresses
    if allowed_ips:
        sanitized['ip_whitelist'] = sanitize_ip_addresses(allowed_ips)

    # Sanitize permissions
    if permissions:
        sanitized['permissions'] = sanitize_permissions_list(permissions)

    # Sanitize client IP (subnet only)
    if client_ip:
        parts = client_ip.split('.')
        if len(parts) == 4:
            sanitized['client_subnet'] = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        else:
            sanitized['client_subnet'] = 'unknown'

    # Preserve correlation ID for debugging
    if correlation_id:
        sanitized['correlation_id'] = correlation_id

    return sanitized
