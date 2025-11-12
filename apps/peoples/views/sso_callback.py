"""SSO callback handlers for SAML and OIDC flows."""

import base64
import binascii
import logging
import zlib
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
import requests
from defusedxml import ElementTree as ET
from django.conf import settings
from django.contrib.auth import login
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
from jwt import PyJWKClient

try:  # Optional dependency for XML signature validation
    from signxml import InvalidSignature, XMLVerifier
    from lxml import etree
except ImportError:  # pragma: no cover - optional dependency
    XMLVerifier = None
    InvalidSignature = Exception
    etree = None

from apps.peoples.sso import OIDCBackend, SAML2Backend
from apps.peoples.services.audit_logging_service import AuditLoggingService

logger = logging.getLogger('peoples.sso.callback')

__all__ = ['saml_acs_view', 'oidc_callback_view']

SAML_CONFIG = getattr(settings, 'SAML_SSO', {})
OIDC_CONFIG = getattr(settings, 'OIDC_PROVIDER', {})
SAML_NAMESPACES = {
    'saml2': 'urn:oasis:names:tc:SAML:2.0:assertion',
    'samlp': 'urn:oasis:names:tc:SAML:2.0:protocol',
}


@csrf_exempt  # SAML POST binding requires CSRF exemption (protected by signature)
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@ratelimit(key='user_or_ip', rate='20/m', method='POST', block=True)
def saml_acs_view(request: HttpRequest) -> HttpResponse:
    """
    SAML Assertion Consumer Service (ACS) endpoint.
    
    Receives SAML response, validates, authenticates user.
    Rate limits: 10 req/min per IP, 20 req/min per user.
    """
    try:
        saml_response = request.POST.get('SAMLResponse')
        if not saml_response:
            raise ValidationError("Missing SAML response")
        
        assertion = _parse_saml_response(saml_response)
        backend = SAML2Backend()
        user = backend.authenticate(request, saml_assertion=assertion)
        
        if user:
            login(request, user, backend='apps.peoples.sso.saml_backend.SAML2Backend')
            AuditLoggingService.log_authentication(user, 'saml_sso', success=True)
            
            relay_state = request.POST.get('RelayState', '/')
            return redirect(relay_state)
        
        raise PermissionDenied("SAML authentication failed")
        
    except Ratelimited:
        logger.warning(
            f"SAML rate limit exceeded - IP: {_get_client_ip(request)}, "
            f"User: {getattr(request.user, 'username', 'anonymous')}"
        )
        AuditLoggingService.log_authentication(
            None, 'saml_sso', success=False, error='Rate limit exceeded'
        )
        return JsonResponse({'error': 'Too many requests. Please try again later.'}, status=429)
    except (ValidationError, PermissionDenied) as e:
        logger.error(f"SAML callback error: {e}")
        AuditLoggingService.log_authentication(None, 'saml_sso', success=False, error=str(e))
        return JsonResponse({'error': 'Authentication failed'}, status=403)


@require_http_methods(["GET"])
@ratelimit(key='ip', rate='10/m', method='GET', block=True)
@ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True)
def oidc_callback_view(request: HttpRequest) -> HttpResponse:
    """
    OIDC callback endpoint.
    
    Receives authorization code, exchanges for tokens, authenticates user.
    Rate limits: 10 req/min per IP, 20 req/min per user.
    """
    try:
        code = request.GET.get('code')
        if not code:
            raise ValidationError("Missing authorization code")
        
        id_token = _exchange_code_for_token(code)
        backend = OIDCBackend()
        user = backend.authenticate(request, id_token=id_token)
        
        if user:
            login(request, user, backend='apps.peoples.sso.oidc_backend.OIDCBackend')
            AuditLoggingService.log_authentication(user, 'oidc_sso', success=True)
            
            state = request.GET.get('state', '/')
            return redirect(state)
        
        raise PermissionDenied("OIDC authentication failed")
        
    except Ratelimited:
        logger.warning(
            f"OIDC rate limit exceeded - IP: {_get_client_ip(request)}, "
            f"User: {getattr(request.user, 'username', 'anonymous')}"
        )
        AuditLoggingService.log_authentication(
            None, 'oidc_sso', success=False, error='Rate limit exceeded'
        )
        return JsonResponse({'error': 'Too many requests. Please try again later.'}, status=429)
    except (ValidationError, PermissionDenied) as e:
        logger.error(f"OIDC callback error: {e}")
        AuditLoggingService.log_authentication(None, 'oidc_sso', success=False, error=str(e))
        return JsonResponse({'error': 'Authentication failed'}, status=403)


def _parse_saml_response(saml_response: str) -> Dict[str, Any]:
    """Decode, validate, and normalize a SAML assertion."""
    if not SAML_CONFIG:
        raise ImproperlyConfigured('SAML_SSO settings are not configured')

    xml_bytes = _decode_saml_payload(saml_response)
    root = ET.fromstring(xml_bytes)

    if SAML_CONFIG.get('require_signed_assertions'):
        _verify_saml_signature(xml_bytes)

    assertion = root.find('.//saml2:Assertion', namespaces=SAML_NAMESPACES)
    if assertion is None:
        raise ValidationError('SAML assertion missing from response')

    issuer = assertion.findtext('.//saml2:Issuer', namespaces=SAML_NAMESPACES)
    allowed_issuers = SAML_CONFIG.get('allowed_issuers') or []
    if allowed_issuers and issuer not in allowed_issuers:
        raise ValidationError('SAML issuer not permitted')

    _validate_saml_conditions(assertion)
    attributes = _extract_saml_attributes(assertion)

    subject = assertion.find('.//saml2:Subject', namespaces=SAML_NAMESPACES)
    name_id = ''
    if subject is not None:
        name_id = subject.findtext('saml2:NameID', namespaces=SAML_NAMESPACES, default='')

    authn_statement = root.find('.//saml2:AuthnStatement', namespaces=SAML_NAMESPACES)
    session_index = ''
    if authn_statement is not None:
        session_index = authn_statement.get('SessionIndex', '')

    audience_values = [
        node.text for node in assertion.findall('.//saml2:Audience', namespaces=SAML_NAMESPACES)
        if node.text
    ]

    expected_audience = SAML_CONFIG.get('audience')
    if expected_audience and expected_audience not in audience_values:
        raise ValidationError('SAML audience mismatch')

    return {
        'attributes': attributes,
        'name_id': name_id,
        'session_index': session_index,
        'issuer': issuer,
        'audience': audience_values,
    }


def _exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Exchange an authorization code for a validated OIDC ID token."""
    if not OIDC_CONFIG:
        raise ImproperlyConfigured('OIDC_PROVIDER settings are not configured')

    if OIDC_CONFIG.get('test_mode'):
        mock_token = OIDC_CONFIG.get('mock_tokens', {}).get(code)
        if not mock_token:
            raise ValidationError('Invalid authorization code provided in test mode')
        return mock_token

    metadata = _load_oidc_metadata()
    token_endpoint = metadata.get('token_endpoint')
    if not token_endpoint:
        raise ImproperlyConfigured('OIDC token endpoint is not available')

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': OIDC_CONFIG.get('redirect_uri'),
    }
    auth = None
    if OIDC_CONFIG.get('client_secret'):
        auth = (OIDC_CONFIG.get('client_id'), OIDC_CONFIG.get('client_secret'))
    else:
        data['client_id'] = OIDC_CONFIG.get('client_id')

    try:
        response = requests.post(
            token_endpoint,
            data=data,
            auth=auth,
            timeout=OIDC_CONFIG.get('timeout', 10),
            headers={'Accept': 'application/json'},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValidationError('OIDC token request failed') from exc

    payload = response.json()
    id_token = payload.get('id_token')
    if not id_token:
        raise ValidationError('OIDC provider response did not include id_token')

    return _validate_id_token(id_token, metadata)


def _get_client_ip(request: HttpRequest) -> str:
    """Extract client IP from request for logging."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _decode_saml_payload(payload: str) -> bytes:
    """Base64 decode and deflate (if needed) a SAML payload."""
    try:
        decoded = base64.b64decode(payload)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError('Malformed SAML response encoding') from exc

    # HTTP-POST binding is usually plain XML; HTTP-Redirect is deflated
    try:
        return zlib.decompress(decoded, -15)
    except zlib.error:
        return decoded


def _validate_saml_conditions(assertion) -> None:
    """Validate temporal and audience conditions on the assertion."""
    conditions = assertion.find('.//saml2:Conditions', namespaces=SAML_NAMESPACES)
    if conditions is None:
        return

    skew = timedelta(seconds=SAML_CONFIG.get('clock_skew_tolerance_seconds', 120))
    now = timezone.now()

    not_before = _parse_saml_timestamp(conditions.get('NotBefore'))
    if not_before and now + skew < not_before:
        raise ValidationError('SAML assertion is not yet valid')

    not_on_or_after = _parse_saml_timestamp(conditions.get('NotOnOrAfter'))
    if not_on_or_after and now - skew >= not_on_or_after:
        raise ValidationError('SAML assertion has expired')


def _parse_saml_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValidationError('Invalid SAML timestamp format')


def _extract_saml_attributes(assertion) -> Dict[str, list]:
    attributes = {}
    for attribute in assertion.findall('.//saml2:Attribute', namespaces=SAML_NAMESPACES):
        name = attribute.get('Name') or attribute.get('FriendlyName')
        if not name:
            continue
        values = [
            node.text or ''
            for node in attribute.findall('saml2:AttributeValue', namespaces=SAML_NAMESPACES)
        ]
        attributes[name] = values or ['']
    return attributes


def _verify_saml_signature(xml_bytes: bytes) -> None:
    if not XMLVerifier or not etree:
        raise ImproperlyConfigured(
            'signxml and lxml are required for signed SAML assertions'
        )

    certificates = SAML_CONFIG.get('certificates') or []
    if not certificates:
        raise ImproperlyConfigured('SAML certificates must be configured for signed assertions')

    document = etree.fromstring(xml_bytes)
    last_error: Optional[Exception] = None
    for certificate in certificates:
        try:
            XMLVerifier().verify(document, x509_cert=certificate)
            return
        except InvalidSignature as exc:  # pragma: no cover - depends on cert setup
            last_error = exc
            continue

    raise ValidationError('SAML signature verification failed') from last_error


def _load_oidc_metadata() -> Dict[str, Any]:
    issuer = OIDC_CONFIG.get('issuer')
    if not issuer:
        raise ImproperlyConfigured('OIDC issuer is not configured')

    cache_key = f"oidc:metadata:{issuer}"
    metadata = cache.get(cache_key)
    if metadata:
        return metadata

    discovery_url = issuer.rstrip('/') + '/.well-known/openid-configuration'
    try:
        response = requests.get(discovery_url, timeout=OIDC_CONFIG.get('timeout', 10))
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValidationError('Failed to load OIDC discovery document') from exc

    metadata = response.json()
    cache.set(cache_key, metadata, timeout=3600)
    return metadata


def _validate_id_token(id_token: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    issuer = metadata.get('issuer')
    jwks_uri = metadata.get('jwks_uri')
    audience = OIDC_CONFIG.get('client_id')

    if not all([issuer, jwks_uri, audience]):
        raise ImproperlyConfigured('OIDC metadata is incomplete')

    try:
        jwk_client = PyJWKClient(jwks_uri, cache_keys=True)
        signing_key = jwk_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=[signing_key.algorithm],
            audience=audience,
            issuer=issuer,
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise ValidationError('OIDC token validation failed') from exc

    return claims
