"""
SSO Integration Module

Provides enterprise SSO authentication backends:
- SAML 2.0
- OpenID Connect (OIDC)
- Just-in-time user provisioning
"""

from .saml_backend import SAML2Backend
from .oidc_backend import OIDCBackend
from .jit_provisioning import JITProvisioningService

__all__ = [
    'SAML2Backend',
    'OIDCBackend',
    'JITProvisioningService',
]
