"""Single Sign-On (SSO) configuration for SAML and OIDC providers."""

import json
from pathlib import Path
import environ

env = environ.Env()

# ---------------------------------------------------------------------------
# SAML 2.0 CONFIGURATION
# ---------------------------------------------------------------------------

_default_cert_path = Path(env.str('SAML_CERTIFICATE_PATH', default='')).expanduser()
_inline_cert = env('SAML_CERTIFICATE', default='')

def _load_certificates():
    certificates = []
    if _inline_cert:
        certificates.append(_inline_cert.replace('\\n', '\n').strip())
    if _default_cert_path and _default_cert_path.exists():
        certificates.append(_default_cert_path.read_text().strip())
    return certificates

SAML_SSO = {
    'audience': env('SAML_AUDIENCE', default='intelliwiz'),
    'allowed_issuers': env.list('SAML_ALLOWED_ISSUERS', default=[]),
    'default_relay_state': env('SAML_DEFAULT_RELAY_STATE', default='/'),
    'clock_skew_tolerance_seconds': env.int('SAML_CLOCK_SKEW_TOLERANCE', default=120),
    'require_signed_assertions': env.bool('SAML_REQUIRE_SIGNED_ASSERTIONS', default=False),
    'certificates': _load_certificates(),
    'test_mode': env.bool('SAML_TEST_MODE', default=False),
}

_fingerprints_json = env('SAML_CERT_FINGERPRINTS_JSON', default='[]')
try:
    SAML_SSO['cert_fingerprints'] = json.loads(_fingerprints_json)
except json.JSONDecodeError:
    SAML_SSO['cert_fingerprints'] = []

# ---------------------------------------------------------------------------
# OIDC CONFIGURATION
# ---------------------------------------------------------------------------

OIDC_PROVIDER = {
    'issuer': env('OIDC_ISSUER', default=''),
    'client_id': env('OIDC_CLIENT_ID', default=''),
    'client_secret': env('OIDC_CLIENT_SECRET', default=''),
    'redirect_uri': env('OIDC_REDIRECT_URI', default=''),
    'scope': env('OIDC_SCOPE', default='openid profile email'),
    'timeout': env.int('OIDC_HTTP_TIMEOUT', default=10),
    'test_mode': env.bool('OIDC_TEST_MODE', default=False),
    'mock_tokens': {},
}

__all__ = ['SAML_SSO', 'OIDC_PROVIDER']
