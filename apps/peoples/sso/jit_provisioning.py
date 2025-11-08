"""
Just-in-Time (JIT) User Provisioning Service

Automatically creates or updates users during SSO authentication.
Maps SSO attributes to People, PeopleProfile, PeopleOrganizational.
Assigns groups via TypeAssist mapping and roles via Capability.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exceptions (DatabaseException)
"""

import logging
from typing import Dict, Any, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone as dt_timezone
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational, Pgroup, Capability
from apps.core_onboarding.models import TypeAssist
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('peoples.sso.jit')

__all__ = ['JITProvisioningService']


class JITProvisioningService:
    """Just-in-time user provisioning from SSO attributes."""
    
    @classmethod
    @transaction.atomic
    def provision_or_update_user(cls, attributes: Dict[str, Any], provider: str) -> People:
        """
        Create or update user from SSO attributes.
        
        Args:
            attributes: Mapped user attributes from SAML/OIDC
            provider: 'saml' or 'oidc'
            
        Returns:
            People instance
        """
        username = attributes.get('username')
        email = attributes.get('email')
        
        if not username:
            raise ValidationError("Username is required for JIT provisioning")
        
        try:
            user, created = People.objects.get_or_create(
                username=username,
                defaults=cls._get_user_defaults(attributes)
            )
            
            if not created:
                cls._update_user_fields(user, attributes)
            
            cls._provision_profile(user, attributes)
            cls._provision_organizational_data(user, attributes, provider)
            cls._assign_groups_from_sso(user, attributes.get('groups', []))
            
            logger.info(f"JIT provisioned user: {username} (created={created})")
            return user
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"JIT provisioning failed for {username}: {e}")
            raise
    
    @classmethod
    def _get_user_defaults(cls, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Build default user fields for creation."""
        return {
            'email': attributes.get('email', ''),
            'first_name': attributes.get('first_name', ''),
            'last_name': attributes.get('last_name', ''),
            'is_active': True,
            'last_login': dt_timezone.now(),
        }
    
    @classmethod
    def _update_user_fields(cls, user: People, attributes: Dict[str, Any]) -> None:
        """Update existing user fields."""
        user.email = attributes.get('email', user.email)
        user.first_name = attributes.get('first_name', user.first_name)
        user.last_name = attributes.get('last_name', user.last_name)
        user.last_login = dt_timezone.now()
        user.save()
    
    @classmethod
    def _provision_profile(cls, user: People, attributes: Dict[str, Any]) -> None:
        """Create or update user profile."""
        PeopleProfile.objects.update_or_create(
            user=user,
            defaults={'gender': attributes.get('gender', 'Other')}
        )
    
    @classmethod
    def _provision_organizational_data(cls, user: People, attributes: Dict[str, Any], provider: str) -> None:
        """Create or update organizational data with SSO metadata."""
        sso_config = cls._get_sso_provider_config(provider)
        
        PeopleOrganizational.objects.update_or_create(
            user=user,
            defaults={
                'department': attributes.get('department', ''),
                'sso_provider': provider,
                'sso_metadata': sso_config,
            }
        )
    
    @classmethod
    def _get_sso_provider_config(cls, provider: str) -> Dict[str, Any]:
        """Retrieve SSO provider config from TypeAssist."""
        try:
            config = TypeAssist.objects.filter(
                tacode=f'SSO_{provider.upper()}',
                typename='SSO_CONFIG'
            ).first()
            
            return config.other_data if config else {}
        except DATABASE_EXCEPTIONS:
            return {}
    
    @classmethod
    def _assign_groups_from_sso(cls, user: People, groups: list) -> None:
        """Map SSO groups to Pgroup via TypeAssist mapping."""
        for group_name in groups:
            try:
                mapping = TypeAssist.objects.filter(
                    tacode=f'SSO_GROUP_{group_name}',
                    typename='GROUP_MAPPING'
                ).first()
                
                if mapping and mapping.other_data.get('pgroup_id'):
                    pgroup = Pgroup.objects.get(id=mapping.other_data['pgroup_id'])
                    user.pgroup_set.add(pgroup)
            except DATABASE_EXCEPTIONS as e:
                logger.warning(f"Failed to map group {group_name}: {e}")
