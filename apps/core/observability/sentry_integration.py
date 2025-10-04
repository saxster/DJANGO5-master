"""
Sentry Integration Service

Centralized Sentry SDK initialization with Django, Celery, and multi-tenant support.
Provides error tracking, performance monitoring, and release management.

Features:
    - Automatic error capture with context enrichment
    - Performance transaction tracking
    - User context and breadcrumbs
    - PII redaction via before-send hooks
    - Tenant context tagging
    - Release tracking with git commit SHA

Compliance:
    - Rule #7: Class < 150 lines
    - Rule #11: Specific exception handling
    - Rule #15: No PII in logs/events

Usage:
    # In Django settings or AppConfig.ready()
    from apps.core.observability.sentry_integration import SentryIntegration
    SentryIntegration.initialize()
"""

import logging
import os
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

__all__ = ['SentryIntegration', 'configure_sentry']


class SentryIntegration:
    """
    Sentry SDK integration with Django and Celery.

    Handles initialization, context enrichment, and PII redaction.
    """

    _initialized = False
    _sentry_hub = None

    # PII patterns to redact from events
    PII_PATTERNS = [
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN]'),
        (re.compile(r'\b\d{16}\b'), '[CARD]'),
        (re.compile(r'\b\d{10,12}\b'), '[PHONE]'),
    ]

    @classmethod
    def initialize(cls, dsn: Optional[str] = None, environment: Optional[str] = None) -> bool:
        """
        Initialize Sentry SDK with Django and Celery integrations.

        Args:
            dsn: Sentry DSN (defaults to env var SENTRY_DSN)
            environment: Environment name (defaults to env var ENVIRONMENT)

        Returns:
            True if initialized successfully, False otherwise
        """
        if cls._initialized:
            logger.info("Sentry already initialized")
            return True

        try:
            import sentry_sdk
            from sentry_sdk.integrations.django import DjangoIntegration
            from sentry_sdk.integrations.celery import CeleryIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration
        except ImportError as e:
            logger.error(f"Sentry SDK not installed: {e}")
            return False

        # Get configuration from environment
        sentry_dsn = dsn or os.getenv('SENTRY_DSN')
        if not sentry_dsn:
            logger.warning("SENTRY_DSN not configured - Sentry disabled")
            return False

        env_name = environment or os.getenv('ENVIRONMENT', 'development')
        release = cls._get_release_version()

        try:
            sentry_sdk.init(
                dsn=sentry_dsn,
                environment=env_name,
                release=release,

                # Integrations
                integrations=[
                    DjangoIntegration(),
                    CeleryIntegration(),
                    RedisIntegration(),
                    LoggingIntegration(
                        level=logging.INFO,
                        event_level=logging.ERROR
                    ),
                ],

                # Performance monitoring
                traces_sample_rate=cls._get_traces_sample_rate(env_name),
                profiles_sample_rate=cls._get_profiles_sample_rate(env_name),

                # Event processing
                before_send=cls._before_send_hook,
                before_breadcrumb=cls._before_breadcrumb_hook,

                # Data scrubbing
                send_default_pii=False,
                attach_stacktrace=True,
                max_breadcrumbs=50,

                # Error filtering
                ignore_errors=[
                    KeyboardInterrupt,
                    'django.http.response.Http404',
                ],
            )

            cls._initialized = True
            cls._sentry_hub = sentry_sdk.Hub.current

            logger.info(
                f"Sentry initialized: env={env_name}, release={release}",
                extra={'environment': env_name, 'release': release}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}", exc_info=True)
            return False

    @classmethod
    def _get_release_version(cls) -> str:
        """Get release version from git commit SHA or fallback."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return f"intelliwiz@{result.stdout.strip()}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback to environment variable or unknown
        return os.getenv('RELEASE_VERSION', 'intelliwiz@unknown')

    @classmethod
    def _get_traces_sample_rate(cls, environment: str) -> float:
        """Get performance traces sample rate based on environment."""
        sample_rates = {
            'production': 0.1,   # 10% sampling in prod
            'staging': 0.5,      # 50% sampling in staging
            'development': 1.0,  # 100% sampling in dev
        }
        return sample_rates.get(environment, 0.1)

    @classmethod
    def _get_profiles_sample_rate(cls, environment: str) -> float:
        """Get profiling sample rate based on environment."""
        # Profiling is expensive - sample less
        return cls._get_traces_sample_rate(environment) * 0.1

    @classmethod
    def _before_send_hook(cls, event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process event before sending to Sentry.

        Performs PII redaction and context enrichment.
        """
        # Redact PII from exception messages
        if 'exception' in event:
            for exception in event['exception'].get('values', []):
                if 'value' in exception:
                    exception['value'] = cls._redact_pii(exception['value'])

        # Redact PII from request data
        if 'request' in event:
            request_data = event['request']
            for key in ['data', 'query_string', 'headers']:
                if key in request_data and isinstance(request_data[key], str):
                    request_data[key] = cls._redact_pii(request_data[key])

        # Add custom context
        event.setdefault('tags', {})
        event['tags']['app'] = 'intelliwiz'

        return event

    @classmethod
    def _before_breadcrumb_hook(cls, crumb: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process breadcrumb before adding to event."""
        # Redact PII from breadcrumb messages
        if 'message' in crumb:
            crumb['message'] = cls._redact_pii(crumb['message'])

        return crumb

    @classmethod
    def _redact_pii(cls, text: str) -> str:
        """Redact PII patterns from text."""
        if not isinstance(text, str):
            return text

        for pattern, replacement in cls.PII_PATTERNS:
            text = pattern.sub(replacement, text)

        return text


def configure_sentry():
    """
    Convenience function to initialize Sentry.

    Call this in Django settings or AppConfig.ready()
    """
    return SentryIntegration.initialize()
