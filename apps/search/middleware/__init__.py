"""
Search middleware components

Rate limiting and security middleware for search endpoints
"""

from .rate_limiting import SearchRateLimitMiddleware

__all__ = ['SearchRateLimitMiddleware']
