"""
SSO Integration Tests

Test SAML and OIDC authentication backends with JIT provisioning.
"""

import pytest
from django.contrib.auth import authenticate
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational
from apps.peoples.sso import SAML2Backend, OIDCBackend, JITProvisioningService


@pytest.mark.django_db
class TestSAML2Backend:
    """Test SAML 2.0 authentication."""
    
    def test_saml_authentication_success(self, rf):
        """Test successful SAML authentication with JIT provisioning."""
        assertion = {
            'attributes': {
                'urn:oid:0.9.2342.19200300.100.1.1': ['testuser'],
                'urn:oid:0.9.2342.19200300.100.1.3': ['test@example.com'],
                'urn:oid:2.5.4.42': ['John'],
                'urn:oid:2.5.4.4': ['Doe'],
                'groups': ['SecurityTeam', 'Managers'],
            },
            'name_id': 'testuser@idp.example.com',
        }
        
        request = rf.get('/')
        backend = SAML2Backend()
        user = backend.authenticate(request, saml_assertion=assertion)
        
        assert user is not None
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'


@pytest.mark.django_db
class TestOIDCBackend:
    """Test OIDC authentication."""
    
    def test_oidc_authentication_success(self, rf):
        """Test successful OIDC authentication."""
        id_token = {
            'sub': 'user123',
            'email': 'oidc@example.com',
            'preferred_username': 'oidcuser',
            'given_name': 'Jane',
            'family_name': 'Smith',
            'groups': ['Engineers'],
        }
        
        request = rf.get('/')
        backend = OIDCBackend()
        user = backend.authenticate(request, id_token=id_token)
        
        assert user is not None
        assert user.username == 'oidcuser'
        assert user.email == 'oidc@example.com'


@pytest.mark.django_db
class TestJITProvisioning:
    """Test just-in-time user provisioning."""
    
    def test_create_new_user(self):
        """Test creating new user during JIT provisioning."""
        attributes = {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'department': 'IT',
            'groups': [],
        }
        
        user = JITProvisioningService.provision_or_update_user(attributes, 'saml')
        
        assert People.objects.filter(username='newuser').exists()
        assert user.email == 'new@example.com'
        assert PeopleProfile.objects.filter(user=user).exists()
        assert PeopleOrganizational.objects.filter(user=user).exists()
    
    def test_update_existing_user(self):
        """Test updating existing user during JIT provisioning."""
        user = People.objects.create(username='existinguser', email='old@example.com')
        
        attributes = {
            'username': 'existinguser',
            'email': 'updated@example.com',
            'first_name': 'Updated',
            'last_name': 'User',
        }
        
        updated_user = JITProvisioningService.provision_or_update_user(attributes, 'oidc')
        
        assert updated_user.id == user.id
        assert updated_user.email == 'updated@example.com'
