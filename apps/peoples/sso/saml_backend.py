"""
SAML 2.0 Authentication Backend

Enterprise SSO integration using SAML 2.0 protocol.
Maps SAML assertions to People model fields.

Follows .claude/rules.md:
- Rule #7: File < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exceptions (no generic Exception)
"""

import logging
from typing import Dict, Optional, Any
from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import PermissionDenied, ValidationError
from apps.peoples.models import People
from apps.peoples.sso.jit_provisioning import JITProvisioningService

logger = logging.getLogger('peoples.sso.saml')

__all__ = ['SAML2Backend']


class SAML2Backend(BaseBackend):
    """SAML 2.0 authentication backend with JIT provisioning."""
    
    def authenticate(self, request, saml_assertion: Dict[str, Any] = None, **kwargs) -> Optional[People]:
        """
        Authenticate user via SAML assertion.
        
        Args:
            request: HTTP request
            saml_assertion: Parsed SAML assertion with user attributes
            
        Returns:
            People instance or None
        """
        if not saml_assertion:
            return None
            
        try:
            user_attributes = self._map_saml_attributes(saml_assertion)
            user = JITProvisioningService.provision_or_update_user(
                attributes=user_attributes,
                provider='saml'
            )
            
            logger.info(f"SAML authentication successful: {user.username}")
            return user
            
        except (ValidationError, PermissionDenied) as e:
            logger.error(f"SAML authentication failed: {e}")
            return None
    
    def _map_saml_attributes(self, assertion: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map SAML attributes to People model fields.
        
        Expected SAML attributes:
        - urn:oid:0.9.2342.19200300.100.1.1 (uid/username)
        - urn:oid:2.5.4.42 (givenName)
        - urn:oid:2.5.4.4 (sn/surname)
        - urn:oid:0.9.2342.19200300.100.1.3 (mail)
        - urn:oid:2.5.4.11 (ou/department)
        - groups (memberOf)
        """
        attrs = assertion.get('attributes', {})
        
        return {
            'username': attrs.get('urn:oid:0.9.2342.19200300.100.1.1', [''])[0],
            'email': attrs.get('urn:oid:0.9.2342.19200300.100.1.3', [''])[0],
            'first_name': attrs.get('urn:oid:2.5.4.42', [''])[0],
            'last_name': attrs.get('urn:oid:2.5.4.4', [''])[0],
            'department': attrs.get('urn:oid:2.5.4.11', [''])[0],
            'groups': attrs.get('groups', []),
            'name_id': assertion.get('name_id', ''),
            'session_index': assertion.get('session_index', ''),
        }
    
    def get_user(self, user_id: int) -> Optional[People]:
        """Retrieve user by ID."""
        try:
            return People.objects.get(pk=user_id)
        except People.DoesNotExist:
            return None
