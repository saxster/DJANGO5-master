"""
Y-Helpdesk Exception Patterns

Specific exception types for y_helpdesk app following .claude/rules.md Rule #11.
Replaces generic 'except Exception' patterns with targeted exception handling.

Usage:
    from apps.y_helpdesk.exceptions import (
        TRANSLATION_EXCEPTIONS,
        SENTIMENT_ANALYSIS_EXCEPTIONS,
        CACHE_EXCEPTIONS
    )

    try:
        result = translate_text(text)
    except TRANSLATION_EXCEPTIONS as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        raise TranslationServiceError("Translation failed") from e
"""

from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    VALIDATION_EXCEPTIONS
)
import redis
from json import JSONDecodeError
from requests.exceptions import ConnectionError, Timeout, HTTPError


# Translation Service Exceptions
TRANSLATION_EXCEPTIONS = (
    ConnectionError,
    Timeout,
    HTTPError,
    JSONDecodeError,
    KeyError,  # Missing translation keys
    ValueError,  # Invalid language codes
)

# Sentiment Analysis Exceptions
SENTIMENT_ANALYSIS_EXCEPTIONS = (
    ValueError,  # Invalid input text
    AttributeError,  # Missing model attributes
    RuntimeError,  # Model inference errors
    ImportError,  # Missing ML libraries
    *VALIDATION_EXCEPTIONS,
)

# Cache Exceptions
CACHE_EXCEPTIONS = (
    redis.ConnectionError,
    redis.TimeoutError,
    redis.RedisError,
    *DATABASE_EXCEPTIONS,
)

# API Exceptions
API_EXCEPTIONS = (
    *NETWORK_EXCEPTIONS,
    *VALIDATION_EXCEPTIONS,
    JSONDecodeError,
)


# Custom Exception Classes
class TicketServiceError(Exception):
    """Base exception for ticket service errors."""
    pass


class TranslationServiceError(TicketServiceError):
    """Translation service failure."""
    pass


class SentimentAnalysisError(TicketServiceError):
    """Sentiment analysis failure."""
    pass


class CacheServiceError(TicketServiceError):
    """Cache service failure."""
    pass
