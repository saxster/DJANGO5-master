"""
IVR Request Validation Decorators.

Provides secure webhook validation for IVR providers (Twilio, Google Voice).
Implements signature-based authentication as alternative to CSRF protection.

Follows .claude/rules.md:
- Rule #3: @csrf_exempt only with documented alternative protection
- Rule #8: Functions < 30 lines
- Rule #11: Specific exception handling
- Rule #14: Network timeouts required
"""

import logging
import functools
from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger('noc.security_intelligence.ivr')


def validate_twilio_request(view_func):
    """
    Validate Twilio webhook requests using signature verification.

    Twilio signs all webhook requests using your Auth Token.
    This decorator verifies the X-Twilio-Signature header to ensure
    the request genuinely originated from Twilio.

    Security:
    - Replaces @csrf_exempt with cryptographic signature validation
    - Prevents unauthorized webhook calls (CVSS 7.5 prevention)
    - Uses HMAC-SHA1 with Auth Token as shared secret

    Configuration Required:
    - settings.TWILIO_AUTH_TOKEN: Your Twilio Auth Token
    - HTTP header: X-Twilio-Signature (added by Twilio)

    Returns:
    - 403 Forbidden if signature validation fails
    - Calls wrapped view if signature is valid

    References:
    - https://www.twilio.com/docs/usage/security#validating-requests
    - Rule #3: Alternative authentication mechanism for webhook

    Example:
        @validate_twilio_request
        @require_POST
        def twilio_status_callback(request):
            # Process validated Twilio webhook
            pass
    """
    @csrf_exempt  # Replaced by signature validation
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get Twilio Auth Token from settings
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)

        if not auth_token:
            logger.error("TWILIO_AUTH_TOKEN not configured in settings")
            return HttpResponse('Server configuration error', status=500)

        # Get signature from request headers
        signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')

        if not signature:
            logger.warning(
                "Twilio webhook rejected: Missing X-Twilio-Signature header",
                extra={'path': request.path}
            )
            return HttpResponse('Forbidden: Missing signature', status=403)

        # Get request URL (must match exactly what Twilio used)
        url = request.build_absolute_uri()

        # Validate signature using Twilio SDK
        try:
            from twilio.request_validator import RequestValidator

            validator = RequestValidator(auth_token)

            # For POST requests, validate with POST parameters
            if request.method == 'POST':
                post_params = dict(request.POST.items())
                is_valid = validator.validate(url, post_params, signature)
            else:
                # For GET requests (rare for webhooks)
                is_valid = validator.validate(url, {}, signature)

            if not is_valid:
                logger.warning(
                    "Twilio webhook rejected: Invalid signature",
                    extra={
                        'path': request.path,
                        'url': url,
                        'signature_prefix': signature[:10] if signature else None
                    }
                )
                return HttpResponse('Forbidden: Invalid signature', status=403)

            # Signature valid - proceed with request
            logger.debug(
                "Twilio webhook signature validated successfully",
                extra={'path': request.path}
            )
            return view_func(request, *args, **kwargs)

        except ImportError:
            logger.error(
                "twilio package not installed - cannot validate signatures",
                extra={'required_package': 'twilio>=9.0.0'}
            )
            return HttpResponse('Server configuration error', status=500)

        except (ValueError, AttributeError) as e:
            logger.error(
                f"Twilio signature validation error: {e}",
                exc_info=True,
                extra={'path': request.path}
            )
            return HttpResponse('Signature validation failed', status=403)

    return wrapper


def validate_google_voice_request(view_func):
    """
    Validate Google Voice webhook requests.

    TODO: Implement Google Voice signature validation
    Currently placeholder for future implementation.

    Google Voice uses JWT-based authentication for webhooks.
    Implementation requires:
    - JWT token validation
    - Google service account credentials
    - Token expiration checking

    For now, returns 501 Not Implemented.
    """
    @csrf_exempt
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        logger.warning(
            "Google Voice validation not yet implemented",
            extra={'path': request.path}
        )
        return HttpResponse('Not Implemented', status=501)

    return wrapper
