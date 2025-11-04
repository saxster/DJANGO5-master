"""
Helpdesk API Rate Limiting (Throttling)

Implements rate limiting for helpdesk API endpoints to prevent abuse,
DoS attacks, and ensure fair resource allocation across tenants.

Following .claude/rules.md:
- Rule #1: Security-first approach
- DoS protection through rate limiting
- Multi-tenant resource isolation
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class HelpDeskUserRateThrottle(UserRateThrottle):
    """
    Rate limiting for authenticated helpdesk API users.

    Limits: 100 requests per minute per user
    Scope: All helpdesk API endpoints
    """
    scope = 'helpdesk_user'
    rate = '100/minute'


class HelpDeskTicketCreateThrottle(UserRateThrottle):
    """
    Stricter rate limiting for ticket creation to prevent spam.

    Limits: 10 requests per hour per user
    Scope: Ticket creation endpoint only
    """
    scope = 'helpdesk_create'
    rate = '10/hour'


class HelpDeskTicketBulkThrottle(UserRateThrottle):
    """
    Rate limiting for bulk operations to prevent resource exhaustion.

    Limits: 20 requests per hour per user
    Scope: Bulk update/delete endpoints
    """
    scope = 'helpdesk_bulk'
    rate = '20/hour'


class HelpDeskAnonRateThrottle(AnonRateThrottle):
    """
    Rate limiting for anonymous/unauthenticated requests.

    Limits: 10 requests per hour per IP
    Scope: Public helpdesk endpoints (if any)
    """
    scope = 'helpdesk_anon'
    rate = '10/hour'


__all__ = [
    'HelpDeskUserRateThrottle',
    'HelpDeskTicketCreateThrottle',
    'HelpDeskTicketBulkThrottle',
    'HelpDeskAnonRateThrottle',
]
