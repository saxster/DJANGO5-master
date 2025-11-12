"""
Miscellaneous Onboarding Utilities

Cache utilities and client URL resolution for onboarding workflows.
"""

import logging
from pprint import pformat
from django.conf import settings

logger = logging.getLogger("django")


def get_appropriate_client_url(client_code):
    """
    Get the web URL for a client based on client code.

    Args:
        client_code: Client code to look up

    Returns:
        URL string for the client, or None if not found
    """
    return settings.CLIENT_DOMAINS.get(client_code)


def cache_it(key, val, time=1 * 60):
    """
    Store value in Django cache.

    Args:
        key: Cache key
        val: Value to cache
        time: Timeout in seconds (default: 1 minute)
    """
    from django.core.cache import cache

    cache.set(key, val, time)
    logger.info(f"saved in cache {pformat(val)}")


def get_from_cache(key):
    """
    Retrieve value from Django cache.

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found
    """
    from django.core.cache import cache

    if data := cache.get(key):
        logger.info(f"Got from cache {key}")
        return data
    logger.info("Not found in cache")
    return None


def save_msg(request):
    """Display a success message to user."""
    from django.contrib import messages as msg

    return msg.success(request, "Entry has been saved successfully!", "alert-success")


__all__ = [
    'get_appropriate_client_url',
    'cache_it',
    'get_from_cache',
    'save_msg',
]
