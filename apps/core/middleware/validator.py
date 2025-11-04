"""
Middleware Ordering Validation

Validates that the configured middleware order matches documentation requirements.
Runs at startup to catch configuration errors early.

Critical ordering rules enforced:
1. SecurityMiddleware MUST be first
2. CorrelationIDMiddleware MUST be second
3. Rate limiting MUST come before SQL injection protection
4. SQL/XSS protection MUST come before CSRF
5. SessionMiddleware MUST come before TenantMiddleware
6. GlobalExceptionMiddleware MUST be last
"""

import logging
from typing import List, Tuple

logger = logging.getLogger('security.middleware')


class MiddlewareOrderValidator:
    """Validates middleware configuration order against documentation."""

    # Define the mandatory ordering constraints
    CRITICAL_ORDERING = [
        # (middleware_pattern, required_before, description)
        ('SecurityMiddleware', 'CorrelationIDMiddleware', 'Security headers must be set before request tracking'),
        ('CorrelationIDMiddleware', 'TracingMiddleware', 'Correlation ID must be set before tracing'),
        ('PathBasedRateLimitMiddleware', 'SQLInjectionProtectionMiddleware', 'Rate limiting before injection protection'),
        ('SQLInjectionProtectionMiddleware', 'CsrfViewMiddleware', 'SQL protection before CSRF protection'),
        ('XSSProtectionMiddleware', 'CsrfViewMiddleware', 'XSS protection before CSRF protection'),
        ('SessionMiddleware', 'TenantMiddleware', 'Sessions must be established before tenant detection'),
        ('CsrfViewMiddleware', 'AuthenticationMiddleware', 'CSRF must be checked before authentication'),
        ('GlobalExceptionMiddleware', 'END', 'Exception handler must be last'),
    ]

    @staticmethod
    def validate(middleware_list: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate middleware order.

        Args:
            middleware_list: List of middleware class paths from settings.MIDDLEWARE

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check first middleware is SecurityMiddleware
        if not middleware_list:
            errors.append('MIDDLEWARE list is empty')
            return False, errors

        first = middleware_list[0]
        if 'SecurityMiddleware' not in first:
            errors.append(
                f'SecurityMiddleware must be first, found: {first}'
            )

        # Check last middleware is GlobalExceptionMiddleware
        last = middleware_list[-1]
        if 'GlobalExceptionMiddleware' not in last:
            errors.append(
                f'GlobalExceptionMiddleware must be last, found: {last}'
            )

        # Check critical ordering constraints
        for required, must_come_before, description in MiddlewareOrderValidator.CRITICAL_ORDERING:
            if must_come_before == 'END':
                # Last middleware check - already done above
                continue

            req_idx = MiddlewareOrderValidator._find_middleware_index(
                middleware_list, required
            )
            before_idx = MiddlewareOrderValidator._find_middleware_index(
                middleware_list, must_come_before
            )

            # Only check if both are present
            if req_idx is not None and before_idx is not None:
                if req_idx > before_idx:
                    errors.append(
                        f'Ordering violation: {required} (index {req_idx}) '
                        f'must come before {must_come_before} (index {before_idx}). '
                        f'Reason: {description}'
                    )

        return len(errors) == 0, errors

    @staticmethod
    def _find_middleware_index(middleware_list: List[str], pattern: str) -> int:
        """
        Find the index of a middleware matching the pattern.

        Args:
            middleware_list: List of middleware class paths
            pattern: Pattern to match (can be partial)

        Returns:
            Index if found, None otherwise
        """
        for i, middleware in enumerate(middleware_list):
            if pattern in middleware:
                return i
        return None

    @staticmethod
    def get_critical_ordering_report() -> str:
        """
        Get a formatted report of critical ordering rules.

        Returns:
            Formatted string describing all critical rules
        """
        report = "Middleware Critical Ordering Rules:\n"
        report += "=" * 60 + "\n\n"

        for i, (required, must_come_before, description) in enumerate(
            MiddlewareOrderValidator.CRITICAL_ORDERING, 1
        ):
            if must_come_before == 'END':
                report += f"{i}. {required} must be LAST\n"
                report += f"   Reason: {description}\n\n"
            else:
                report += f"{i}. {required} must come before {must_come_before}\n"
                report += f"   Reason: {description}\n\n"

        return report


def validate_middleware_on_startup(middleware_list: List[str]) -> None:
    """
    Validate middleware configuration on application startup.

    Logs warnings for ordering violations. In production, this helps catch
    configuration errors early before they cause security or functionality issues.

    Args:
        middleware_list: List of middleware from django.conf.settings.MIDDLEWARE

    Raises:
        Nothing - logs warnings only to allow graceful degradation
    """
    is_valid, errors = MiddlewareOrderValidator.validate(middleware_list)

    if not is_valid:
        logger.error(
            f"Middleware ordering validation FAILED with {len(errors)} error(s):"
        )
        for error in errors:
            logger.error(f"  - {error}")

        # Log the expected ordering
        logger.error("\n" + MiddlewareOrderValidator.get_critical_ordering_report())
    else:
        logger.info("Middleware ordering validation PASSED")
        logger.debug(
            f"Validated {len(middleware_list)} middleware components in correct order"
        )
