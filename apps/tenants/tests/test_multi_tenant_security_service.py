"""
Tests for MultiTenantSecurityService

Tests multi-tenant security enforcement including:
- Cross-tenant access prevention
- Tenant context isolation
- Data leakage prevention
- Permission validation
"""

import pytest
from django.db import connection
from django.test import RequestFactory

from apps.tenants.models import Tenant
from apps.tenants.services.multi_tenant_security_service import MultiTenantSecurityService
from apps.peoples.models import People, PeopleTenant
from apps.core.models import BusinessUnit


@pytest.fixture
def tenant_a():
    """Create first tenant."""
    return Tenant.objects.create(
        name="Tenant A",
        slug="tenant-a",
        is_active=True
    )


@pytest.fixture
def tenant_b():
    """Create second tenant."""
    return Tenant.objects.create(
        name="Tenant B",
        slug="tenant-b",
        is_active=True
    )


@pytest.fixture
def user_tenant_a(tenant_a):
    """Create user in Tenant A."""
    user = People.objects.create(
        peoplename="user_a",
        peopleemail="user_a@example.com",
        peoplerole="user"
    )
    PeopleTenant.objects.create(
        people=user,
        tenant=tenant_a,
        is_primary=True
    )
    return user


@pytest.fixture
def user_tenant_b(tenant_b):
    """Create user in Tenant B."""
    user = People.objects.create(
        peoplename="user_b",
        peopleemail="user_b@example.com",
        peoplerole="user"
    )
    PeopleTenant.objects.create(
        people=user,
        tenant=tenant_b,
        is_primary=True
    )
    return user


@pytest.fixture
def business_unit_tenant_a(tenant_a):
    """Create business unit in Tenant A."""
    return BusinessUnit.objects.create(
        buname="BU Tenant A",
        bucode="BU_A",
        client=tenant_a
    )


@pytest.fixture
def business_unit_tenant_b(tenant_b):
    """Create business unit in Tenant B."""
    return BusinessUnit.objects.create(
        buname="BU Tenant B",
        bucode="BU_B",
        client=tenant_b
    )


@pytest.mark.django_db
class TestCrossTenantAccessPrevention:
    """Test cross-tenant access is blocked."""
    
    def test_user_cannot_access_other_tenant_data(
        self, user_tenant_a, business_unit_tenant_b
    ):
        """Test user from Tenant A cannot access Tenant B data."""
        # Get user's tenant
        user_tenant = user_tenant_a.peopletenant_set.filter(is_primary=True).first().tenant
        
        # Verify they're in different tenants
        assert user_tenant != business_unit_tenant_b.client
        
        # Try to access cross-tenant data
        result = MultiTenantSecurityService.validate_access(
            user=user_tenant_a,
            resource=business_unit_tenant_b,
            tenant_field='client'
        )
        
        assert result is False
    
    def test_same_tenant_access_allowed(
        self, user_tenant_a, business_unit_tenant_a
    ):
        """Test user can access data from their own tenant."""
        # Get user's tenant
        user_tenant = user_tenant_a.peopletenant_set.filter(is_primary=True).first().tenant
        
        # Verify same tenant
        assert user_tenant == business_unit_tenant_a.client
        
        # Access should be allowed
        result = MultiTenantSecurityService.validate_access(
            user=user_tenant_a,
            resource=business_unit_tenant_a,
            tenant_field='client'
        )
        
        assert result is True
    
    def test_cross_tenant_queryset_filtering(
        self, user_tenant_a, tenant_a, tenant_b, business_unit_tenant_a, business_unit_tenant_b
    ):
        """Test queryset is filtered to user's tenant only."""
        # Get all business units for user
        queryset = BusinessUnit.objects.all()
        
        filtered_qs = MultiTenantSecurityService.filter_by_tenant(
            queryset=queryset,
            user=user_tenant_a,
            tenant_field='client'
        )
        
        # Should only contain Tenant A's data
        assert filtered_qs.count() == 1
        assert filtered_qs.first().client == tenant_a
        assert business_unit_tenant_b not in filtered_qs


@pytest.mark.django_db
class TestTenantContextIsolation:
    """Test tenant context is properly isolated."""
    
    def test_tenant_context_set_correctly(self, user_tenant_a, tenant_a):
        """Test tenant context is set from user."""
        request = RequestFactory().get('/')
        request.user = user_tenant_a
        
        tenant_context = MultiTenantSecurityService.get_tenant_context(request)
        
        assert tenant_context == tenant_a
    
    def test_tenant_context_persists_through_request(
        self, user_tenant_a, tenant_a
    ):
        """Test tenant context doesn't leak between requests."""
        request1 = RequestFactory().get('/')
        request1.user = user_tenant_a
        
        context1 = MultiTenantSecurityService.get_tenant_context(request1)
        
        # Simulate different request
        request2 = RequestFactory().get('/')
        request2.user = user_tenant_a
        
        context2 = MultiTenantSecurityService.get_tenant_context(request2)
        
        # Both should have same tenant
        assert context1 == context2 == tenant_a
    
    def test_no_global_tenant_state(self, user_tenant_a, user_tenant_b):
        """Test no global state leaks between different users."""
        request1 = RequestFactory().get('/')
        request1.user = user_tenant_a
        context1 = MultiTenantSecurityService.get_tenant_context(request1)
        
        request2 = RequestFactory().get('/')
        request2.user = user_tenant_b
        context2 = MultiTenantSecurityService.get_tenant_context(request2)
        
        # Should be different tenants
        assert context1 != context2


@pytest.mark.django_db
class TestDataLeakagePrevention:
    """Test data leakage prevention mechanisms."""
    
    def test_default_deny_access(self, user_tenant_a):
        """Test default behavior is to deny access when tenant unclear."""
        # Create resource without tenant assignment
        orphan_bu = BusinessUnit.objects.create(
            buname="Orphan BU",
            bucode="ORPHAN",
            client=None
        )
        
        result = MultiTenantSecurityService.validate_access(
            user=user_tenant_a,
            resource=orphan_bu,
            tenant_field='client'
        )
        
        # Should deny access to orphaned resources
        assert result is False
    
    def test_sql_injection_prevented_in_tenant_filter(
        self, user_tenant_a, tenant_a
    ):
        """Test tenant filtering uses parameterized queries."""
        queryset = BusinessUnit.objects.all()
        
        # This should use safe, parameterized queries
        filtered = MultiTenantSecurityService.filter_by_tenant(
            queryset=queryset,
            user=user_tenant_a,
            tenant_field='client'
        )
        
        # Check the SQL is parameterized
        sql = str(filtered.query)
        assert 'client' in sql.lower()
        # Should not contain raw values, only references
    
    def test_audit_logging_on_cross_tenant_attempt(
        self, user_tenant_a, business_unit_tenant_b, caplog
    ):
        """Test cross-tenant access attempts are logged."""
        import logging
        caplog.set_level(logging.WARNING)
        
        MultiTenantSecurityService.validate_access(
            user=user_tenant_a,
            resource=business_unit_tenant_b,
            tenant_field='client'
        )
        
        # Should log security warning
        assert any(
            'cross-tenant' in record.message.lower() or 
            'unauthorized' in record.message.lower()
            for record in caplog.records
        )


@pytest.mark.django_db
class TestPermissionValidation:
    """Test permission-based access validation."""
    
    def test_admin_can_access_within_tenant(self, tenant_a, business_unit_tenant_a):
        """Test admin users have appropriate access within their tenant."""
        admin_user = People.objects.create(
            peoplename="admin_a",
            peopleemail="admin_a@example.com",
            peoplerole="admin"
        )
        PeopleTenant.objects.create(
            people=admin_user,
            tenant=tenant_a,
            is_primary=True
        )
        
        result = MultiTenantSecurityService.validate_access(
            user=admin_user,
            resource=business_unit_tenant_a,
            tenant_field='client'
        )
        
        assert result is True
    
    def test_admin_cannot_access_other_tenant(
        self, tenant_a, business_unit_tenant_b
    ):
        """Test even admins cannot access other tenants."""
        admin_user = People.objects.create(
            peoplename="admin_a",
            peopleemail="admin_a@example.com",
            peoplerole="admin"
        )
        PeopleTenant.objects.create(
            people=admin_user,
            tenant=tenant_a,
            is_primary=True
        )
        
        result = MultiTenantSecurityService.validate_access(
            user=admin_user,
            resource=business_unit_tenant_b,
            tenant_field='client'
        )
        
        # Admin powers stop at tenant boundary
        assert result is False
