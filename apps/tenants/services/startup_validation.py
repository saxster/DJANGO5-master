"""
Startup Validation Service

Validates tenant configuration at Django startup to catch configuration
errors before they cause production issues.

Validations:
    - Tenant mappings loaded correctly
    - Database connectivity for all tenants
    - Middleware registration
    - Cache backend availability
    - Migration guard configuration

Usage:
    # In Django AppConfig.ready() method
    from apps.tenants.services import StartupValidationService

    validator = StartupValidationService()
    report = validator.validate_all()

    if not report['valid']:
        raise ImproperlyConfigured(report['summary'])
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.cache import cache
from django.db import connections, DatabaseError

logger = logging.getLogger('tenants.startup_validation')


class StartupValidationService:
    """
    Validates tenant configuration at startup.

    Performs comprehensive checks to ensure multi-tenant system is
    correctly configured before accepting traffic.
    """

    def __init__(self):
        """Initialize startup validation service."""
        self.validation_errors = []
        self.validation_warnings = []

    def validate_all(self) -> Dict[str, Any]:
        """
        Run all validation checks.

        Returns:
            Validation report dictionary with results

        Example:
            {
                'valid': True,
                'timestamp': '2025-10-01T12:00:00Z',
                'checks': {...},
                'errors': [],
                'warnings': []
            }
        """
        logger.info("Starting tenant configuration validation")

        checks = {
            'tenant_mappings': self._validate_tenant_mappings(),
            'database_connectivity': self._validate_database_connectivity(),
            'middleware_registration': self._validate_middleware(),
            'cache_backend': self._validate_cache_backend(),
            'migration_guard': self._validate_migration_guard(),
            'strict_mode': self._validate_strict_mode(),
        }

        report = {
            'valid': all(checks.values()),
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            'checks': checks,
            'errors': self.validation_errors,
            'warnings': self.validation_warnings,
            'summary': self._generate_summary(checks)
        }

        if report['valid']:
            logger.info("Tenant configuration validation: PASSED")
        else:
            logger.error(
                "Tenant configuration validation: FAILED",
                extra={'report': report}
            )

        return report

    def _validate_tenant_mappings(self) -> bool:
        """
        Validate tenant mappings are loaded correctly.

        Returns:
            True if valid, False otherwise
        """
        try:
            from intelliwiz_config.settings.tenants import TENANT_MAPPINGS

            if not TENANT_MAPPINGS:
                self.validation_errors.append(
                    "No tenant mappings configured (TENANT_MAPPINGS is empty)"
                )
                return False

            if not isinstance(TENANT_MAPPINGS, dict):
                self.validation_errors.append(
                    f"TENANT_MAPPINGS must be dict, got {type(TENANT_MAPPINGS)}"
                )
                return False

            # Validate each mapping
            for hostname, db_alias in TENANT_MAPPINGS.items():
                if not isinstance(hostname, str) or not isinstance(db_alias, str):
                    self.validation_errors.append(
                        f"Invalid mapping: {hostname} → {db_alias}"
                    )
                    return False

            logger.info(
                f"Tenant mappings validated: {len(TENANT_MAPPINGS)} tenants configured"
            )
            return True

        except (ImportError, AttributeError) as e:
            self.validation_errors.append(
                f"Failed to load TENANT_MAPPINGS: {e}"
            )
            return False

    def _validate_database_connectivity(self) -> bool:
        """
        Validate database connectivity for all tenants.

        Returns:
            True if all databases are accessible, False otherwise
        """
        try:
            from intelliwiz_config.settings.tenants import TENANT_MAPPINGS

            unique_databases = set(TENANT_MAPPINGS.values())
            failed_databases = []

            for db_alias in unique_databases:
                if not self._check_database_connection(db_alias):
                    failed_databases.append(db_alias)

            if failed_databases:
                self.validation_errors.append(
                    f"Database connectivity failed: {failed_databases}"
                )
                return False

            logger.info(
                f"Database connectivity validated: {len(unique_databases)} databases"
            )
            return True

        except (ImportError, AttributeError, DatabaseError) as e:
            self.validation_errors.append(
                f"Database connectivity validation failed: {e}"
            )
            return False

    def _check_database_connection(self, db_alias: str) -> bool:
        """
        Check if database connection is available.

        Args:
            db_alias: Database alias to check

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Validate database is configured
            if db_alias not in settings.DATABASES:
                self.validation_errors.append(
                    f"Database '{db_alias}' not found in settings.DATABASES"
                )
                return False

            # Try to connect
            conn = connections[db_alias]
            conn.ensure_connection()

            logger.debug(f"Database connection successful: {db_alias}")
            return True

        except (DatabaseError, KeyError) as e:
            logger.error(
                f"Database connection failed: {db_alias}",
                extra={'error': str(e)}
            )
            return False

    def _validate_middleware(self) -> bool:
        """
        Validate UnifiedTenantMiddleware is registered.

        Returns:
            True if middleware registered, False otherwise
        """
        middleware_classes = settings.MIDDLEWARE

        tenant_middleware = 'apps.tenants.middleware_unified.UnifiedTenantMiddleware'

        if tenant_middleware not in middleware_classes:
            self.validation_errors.append(
                f"UnifiedTenantMiddleware not registered in MIDDLEWARE"
            )
            return False

        # Check middleware ordering (should be early in chain)
        middleware_index = middleware_classes.index(tenant_middleware)
        if middleware_index > 5:
            self.validation_warnings.append(
                f"UnifiedTenantMiddleware is at position {middleware_index}. "
                f"Consider moving it earlier in MIDDLEWARE for better performance."
            )

        logger.info("UnifiedTenantMiddleware registration validated")
        return True

    def _validate_cache_backend(self) -> bool:
        """
        Validate cache backend is available.

        Returns:
            True if cache is accessible, False otherwise
        """
        try:
            # Try to set and get a test value
            test_key = 'tenant_startup_validation_test'
            test_value = 'test'

            cache.set(test_key, test_value, timeout=10)
            retrieved = cache.get(test_key)

            if retrieved != test_value:
                self.validation_errors.append(
                    "Cache backend not working correctly (set/get mismatch)"
                )
                return False

            # Clean up test key
            cache.delete(test_key)

            logger.info("Cache backend validated")
            return True

        except (ValueError, KeyError, TypeError) as e:
            self.validation_errors.append(
                f"Cache backend validation failed: {e}"
            )
            return False

    def _validate_migration_guard(self) -> bool:
        """
        Validate migration guard configuration.

        Returns:
            True if migration guard configured correctly, False otherwise
        """
        try:
            from intelliwiz_config.settings.tenants import TENANT_MIGRATION_DATABASES

            if not TENANT_MIGRATION_DATABASES:
                self.validation_warnings.append(
                    "TENANT_MIGRATION_DATABASES is empty - no databases allowed for migrations"
                )

            # Validate all migration databases exist
            for db_alias in TENANT_MIGRATION_DATABASES:
                if db_alias not in settings.DATABASES:
                    self.validation_errors.append(
                        f"Migration database '{db_alias}' not found in settings.DATABASES"
                    )
                    return False

            logger.info(
                f"Migration guard validated: {len(TENANT_MIGRATION_DATABASES)} "
                f"databases allowed for migrations"
            )
            return True

        except (ImportError, AttributeError) as e:
            self.validation_errors.append(
                f"Migration guard validation failed: {e}"
            )
            return False

    def _validate_strict_mode(self) -> bool:
        """
        Validate strict mode configuration.

        Returns:
            True (always passes, but logs warnings)
        """
        try:
            from intelliwiz_config.settings.tenants import (
                TENANT_STRICT_MODE,
                TENANT_UNKNOWN_HOST_ALLOWLIST
            )

            if not TENANT_STRICT_MODE and not settings.DEBUG:
                self.validation_warnings.append(
                    "TENANT_STRICT_MODE is disabled in production. "
                    "Consider enabling for better security."
                )

            if TENANT_UNKNOWN_HOST_ALLOWLIST and not settings.DEBUG:
                self.validation_warnings.append(
                    f"TENANT_UNKNOWN_HOST_ALLOWLIST has {len(TENANT_UNKNOWN_HOST_ALLOWLIST)} "
                    f"entries in production. This may be a security risk."
                )

            logger.info(
                f"Strict mode validated: enabled={TENANT_STRICT_MODE}, "
                f"allowlist_count={len(TENANT_UNKNOWN_HOST_ALLOWLIST)}"
            )
            return True

        except (ImportError, AttributeError) as e:
            self.validation_warnings.append(
                f"Strict mode validation warning: {e}"
            )
            return True  # Non-critical

    def _generate_summary(self, checks: Dict[str, bool]) -> str:
        """
        Generate human-readable validation summary.

        Args:
            checks: Dictionary of check results

        Returns:
            Summary string
        """
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)

        if passed == total:
            summary = f"All {total} validation checks passed"
        else:
            failed = total - passed
            summary = f"{failed} of {total} validation checks failed"

        if self.validation_errors:
            summary += f"\nErrors: {len(self.validation_errors)}"

        if self.validation_warnings:
            summary += f"\nWarnings: {len(self.validation_warnings)}"

        return summary
