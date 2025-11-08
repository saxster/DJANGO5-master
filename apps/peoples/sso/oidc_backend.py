"""
OpenID Connect (OIDC) Authentication Backend

Modern OAuth 2.0 + OIDC authentication for enterprise SSO.
Maps OIDC claims to People model fields.

Follows .claude/rules.md:
- Rule #7: File < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exceptions
"""

import logging
from typing import Dict, Optional, Any
from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import PermissionDenied, ValidationError
from apps.peoples.models import People
from apps.peoples.sso.jit_provisioning import JITProvisioningService

logger = logging.getLogger('peoples.sso.oidc')

__all__ = ['OIDCBackend']


class OIDCBackend(BaseBackend):
    """OpenID Connect authentication backend with JIT provisioning."""
    
    def authenticate(self, request, id_token: Dict[str, Any] = None, **kwargs) -> Optional[People]:
        """
        Authenticate user via OIDC ID token.
        
        Args:
            request: HTTP request
            id_token: Validated OIDC ID token with claims
            
        Returns:
            People instance or None
        """
        if not id_token:
            return None
            
        try:
            user_attributes = self._map_oidc_claims(id_token)
            user = JITProvisioningService.provision_or_update_user(
                attributes=user_attributes,
                provider='oidc'
            )
            
            logger.info(f"OIDC authentication successful: {user.username}")
            return user
            
        except (ValidationError, PermissionDenied) as e:
            logger.error(f"OIDC authentication failed: {e}")
            return None
    
    def _map_oidc_claims(self, token: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map OIDC standard claims to People model fields.
        
        Standard OIDC claims:
        - sub (subject identifier)
        - email
        - given_name, family_name
        - preferred_username
        - groups (custom claim)
        """
        return {
            'username': token.get('preferred_username') or token.get('sub'),
            'email': token.get('email', ''),
            'first_name': token.get('given_name', ''),
            'last_name': token.get('family_name', ''),
            'department': token.get('department', ''),
            'groups': token.get('groups', []),
            'sub': token.get('sub', ''),
            'iss': token.get('iss', ''),
        }
    
    def get_user(self, user_id: int) -> Optional[People]:
        """Retrieve user by ID."""
        try:
            return People.objects.get(pk=user_id)
        except People.DoesNotExist:
            return None
