"""
External API health checks: AWS SES, Google Maps, LLM providers.
Follows Rule 11: Specific exception handling only.
Uses circuit breaker pattern to prevent cascading failures.
"""

import time
import logging
import smtplib
from typing import Dict, Any
from .utils import timeout_check, format_check_result, CircuitBreaker

logger = logging.getLogger(__name__)

__all__ = [
    'check_aws_ses',
    'check_google_maps_api',
    'check_openai_api',
    'check_anthropic_api',
]

ses_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
gmaps_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
openai_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
anthropic_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)


@timeout_check(timeout_seconds=5)
def check_aws_ses() -> Dict[str, Any]:
    """
    Check AWS SES SMTP connectivity without sending email.

    Returns:
        Health check result with AWS SES status.
    """
    start_time = time.time()

    def _ses_connectivity_test() -> Dict[str, Any]:
        try:
            from django.conf import settings

            email_host = getattr(settings, "EMAIL_HOST", None)
            email_port = getattr(settings, "EMAIL_PORT", 587)
            email_user = getattr(settings, "EMAIL_HOST_USER", None)
            email_password = getattr(settings, "EMAIL_HOST_PASSWORD", None)

            if not all([email_host, email_user, email_password]):
                return format_check_result(
                    status="degraded",
                    message="AWS SES not configured",
                    details={"note": "Email features unavailable"},
                    duration_ms=(time.time() - start_time) * 1000,
                )

            smtp = smtplib.SMTP(email_host, email_port, timeout=3)
            smtp.starttls()
            smtp.login(email_user, email_password)
            smtp.quit()

            duration = (time.time() - start_time) * 1000

            return format_check_result(
                status="healthy",
                message="AWS SES reachable",
                details={
                    "host": email_host,
                    "port": email_port,
                    "authentication": "successful",
                },
                duration_ms=duration,
            )

        except smtplib.SMTPAuthenticationError as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"AWS SES authentication failed: {e}",
                extra={"error_type": "SMTPAuthenticationError", "duration_ms": duration},
            )
            return format_check_result(
                status="error",
                message="AWS SES authentication failed",
                details={"error_type": "SMTPAuthenticationError"},
                duration_ms=duration,
            )

        except smtplib.SMTPConnectError as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"AWS SES connection error: {e}",
                extra={"error_type": "SMTPConnectError", "duration_ms": duration},
            )
            raise ConnectionError(f"AWS SES unreachable: {str(e)}")

        except (smtplib.SMTPException, OSError) as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"AWS SES error: {e}",
                extra={"error_type": type(e).__name__, "duration_ms": duration},
            )
            raise ConnectionError(f"AWS SES error: {str(e)}")

    return ses_circuit_breaker.call(_ses_connectivity_test)


@timeout_check(timeout_seconds=5)
def check_google_maps_api() -> Dict[str, Any]:
    """
    Check Google Maps API availability with lightweight request.

    Returns:
        Health check result with Google Maps API status.
    """
    start_time = time.time()

    def _gmaps_connectivity_test() -> Dict[str, Any]:
        try:
            from django.conf import settings
            import urllib.request
            import urllib.error
            import json

            api_key = getattr(settings, "GOOGLE_MAP_SECRET_KEY", None)

            if not api_key:
                return format_check_result(
                    status="degraded",
                    message="Google Maps API key not configured",
                    details={"note": "Geolocation features unavailable"},
                    duration_ms=(time.time() - start_time) * 1000,
                )

            test_url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng=0,0&key={api_key}"

            try:
                with urllib.request.urlopen(test_url, timeout=3) as response:
                    data = json.loads(response.read())
                    status_code = data.get("status")

                    if status_code in ["OK", "ZERO_RESULTS"]:
                        duration = (time.time() - start_time) * 1000
                        return format_check_result(
                            status="healthy",
                            message="Google Maps API reachable",
                            details={"api_status": status_code, "authentication": "valid"},
                            duration_ms=duration,
                        )
                    else:
                        duration = (time.time() - start_time) * 1000
                        return format_check_result(
                            status="error",
                            message=f"Google Maps API error: {status_code}",
                            details={"api_status": status_code},
                            duration_ms=duration,
                        )

            except urllib.error.HTTPError as e:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f"Google Maps API HTTP error: {e.code}",
                    extra={"error_type": "HTTPError", "status_code": e.code, "duration_ms": duration},
                )
                raise ConnectionError(f"Google Maps API error: HTTP {e.code}")

            except urllib.error.URLError as e:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f"Google Maps API URL error: {e}",
                    extra={"error_type": "URLError", "duration_ms": duration},
                )
                raise ConnectionError(f"Google Maps API unreachable: {str(e)}")

        except json.JSONDecodeError as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"Google Maps API response parsing error: {e}",
                extra={"error_type": "JSONDecodeError", "duration_ms": duration},
            )
            return format_check_result(
                status="error",
                message="Invalid response from Google Maps API",
                details={"error_type": "JSONDecodeError"},
                duration_ms=duration,
            )

    return gmaps_circuit_breaker.call(_gmaps_connectivity_test)


@timeout_check(timeout_seconds=5)
def check_openai_api() -> Dict[str, Any]:
    """
    Check OpenAI API availability.

    Returns:
        Health check result with OpenAI API status.
    """
    start_time = time.time()

    def _openai_connectivity_test() -> Dict[str, Any]:
        try:
            from django.conf import settings
            import urllib.request
            import urllib.error
            import json

            llm_providers = getattr(settings, "LLM_PROVIDERS", {})
            openai_config = llm_providers.get("openai", {})
            api_key = openai_config.get("api_key")

            if not api_key:
                return format_check_result(
                    status="degraded",
                    message="OpenAI API key not configured",
                    details={"note": "OpenAI LLM features unavailable"},
                    duration_ms=(time.time() - start_time) * 1000,
                )

            request = urllib.request.Request("https://api.openai.com/v1/models")
            request.add_header("Authorization", f"Bearer {api_key}")

            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.loads(response.read())

                    if "data" in data:
                        duration = (time.time() - start_time) * 1000
                        return format_check_result(
                            status="healthy",
                            message="OpenAI API reachable",
                            details={
                                "models_available": len(data.get("data", [])),
                                "authentication": "valid",
                            },
                            duration_ms=duration,
                        )

            except urllib.error.HTTPError as e:
                if e.code == 401:
                    duration = (time.time() - start_time) * 1000
                    logger.error(
                        "OpenAI API authentication failed",
                        extra={"error_type": "HTTPError", "status_code": 401, "duration_ms": duration},
                    )
                    return format_check_result(
                        status="error",
                        message="OpenAI API authentication invalid",
                        details={"error_type": "AuthenticationError"},
                        duration_ms=duration,
                    )
                raise ConnectionError(f"OpenAI API error: HTTP {e.code}")

            except urllib.error.URLError as e:
                raise ConnectionError(f"OpenAI API unreachable: {str(e)}")

        except json.JSONDecodeError as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"OpenAI API response parsing error: {e}",
                extra={"error_type": "JSONDecodeError", "duration_ms": duration},
            )
            return format_check_result(
                status="error",
                message="Invalid response from OpenAI API",
                details={"error_type": "JSONDecodeError"},
                duration_ms=duration,
            )

    return openai_circuit_breaker.call(_openai_connectivity_test)


@timeout_check(timeout_seconds=5)
def check_anthropic_api() -> Dict[str, Any]:
    """
    Check Anthropic API availability.

    Returns:
        Health check result with Anthropic API status.
    """
    start_time = time.time()

    def _anthropic_connectivity_test() -> Dict[str, Any]:
        try:
            from django.conf import settings
            import urllib.request
            import urllib.error
            import json

            llm_providers = getattr(settings, "LLM_PROVIDERS", {})
            anthropic_config = llm_providers.get("anthropic", {})
            api_key = anthropic_config.get("api_key")

            if not api_key:
                return format_check_result(
                    status="degraded",
                    message="Anthropic API key not configured",
                    details={"note": "Anthropic LLM features unavailable"},
                    duration_ms=(time.time() - start_time) * 1000,
                )

            request = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )

            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    response_code = response.getcode()

                    if response_code == 200:
                        duration = (time.time() - start_time) * 1000
                        return format_check_result(
                            status="healthy",
                            message="Anthropic API reachable",
                            details={"authentication": "valid"},
                            duration_ms=duration,
                        )

            except urllib.error.HTTPError as e:
                if e.code == 401:
                    duration = (time.time() - start_time) * 1000
                    logger.error(
                        "Anthropic API authentication failed",
                        extra={"error_type": "HTTPError", "status_code": 401, "duration_ms": duration},
                    )
                    return format_check_result(
                        status="error",
                        message="Anthropic API authentication invalid",
                        details={"error_type": "AuthenticationError"},
                        duration_ms=duration,
                    )
                raise ConnectionError(f"Anthropic API error: HTTP {e.code}")

            except urllib.error.URLError as e:
                raise ConnectionError(f"Anthropic API unreachable: {str(e)}")

        except json.JSONDecodeError as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"Anthropic API response parsing error: {e}",
                extra={"error_type": "JSONDecodeError", "duration_ms": duration},
            )
            return format_check_result(
                status="error",
                message="Invalid response from Anthropic API",
                details={"error_type": "JSONDecodeError"},
                duration_ms=duration,
            )

    return anthropic_circuit_breaker.call(_anthropic_connectivity_test)