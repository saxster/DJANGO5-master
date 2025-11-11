"""
Test suite for site switching security (Sprint 1, Task 1: IDOR vulnerability fix).

Tests verify that SwitchSite view properly validates tenant ownership and user
assignments before allowing site switching, preventing horizontal privilege
escalation attacks.
"""

import pytest
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from apps.client_onboarding.views.site_views import SwitchSite
from apps.client_onboarding.models import Bt, TypeAssist
from apps.peoples.models import People, Pgroup, Pgbelonging


@pytest.fixture
def setup_multi_tenant_scenario(db):
    """
    Create a multi-tenant test scenario:
    - Two different clients (tenants)
    - Each client has a site
    - Each client has a user assigned to their site
    - Tests cross-tenant access prevention
    """
    # Create TypeAssist for site groups
    site_group_type = TypeAssist.objects.create(
        tacode="SITEGROUP",
        taname="Site Group",
        enable=True
    )

    # Client A setup
    client_a = Bt.objects.create(
        bucode="CLIENT_A",
        buname="Client A Organization",
        enable=True
    )
    site_a = Bt.objects.create(
        bucode="SITE_A",
        buname="Site A",
        parent=client_a,
        enable=True
    )
    user_a = People.objects.create(
        peoplecode="USER_A",
        peoplename="User A",
        loginid="usera",
        email="usera@example.com",
        client=client_a,
        bu=site_a,
        isverified=True,
        enable=True
    )

    # Create site group and assign site_a to user_a
    site_group_a = Pgroup.objects.create(
        groupname="Site Group A",
        identifier=site_group_type,
        client=client_a,
        bu=site_a,
        enable=True
    )
    Pgbelonging.objects.create(
        pgroup=site_group_a,
        people=user_a,
        assignsites=site_a,
        client=client_a,
        bu=site_a
    )

    # Client B setup (different tenant)
    client_b = Bt.objects.create(
        bucode="CLIENT_B",
        buname="Client B Organization",
        enable=True
    )
    site_b = Bt.objects.create(
        bucode="SITE_B",
        buname="Site B",
        parent=client_b,
        enable=True
    )
    user_b = People.objects.create(
        peoplecode="USER_B",
        peoplename="User B",
        loginid="userb",
        email="userb@example.com",
        client=client_b,
        bu=site_b,
        isverified=True,
        enable=True
    )

    # Create site group and assign site_b to user_b
    site_group_b = Pgroup.objects.create(
        groupname="Site Group B",
        identifier=site_group_type,
        client=client_b,
        bu=site_b,
        enable=True
    )
    Pgbelonging.objects.create(
        pgroup=site_group_b,
        people=user_b,
        assignsites=site_b,
        client=client_b,
        bu=site_b
    )

    return {
        'client_a': client_a,
        'site_a': site_a,
        'user_a': user_a,
        'client_b': client_b,
        'site_b': site_b,
        'user_b': user_b
    }


@pytest.fixture
def authenticated_request_factory():
    """Factory for creating authenticated requests with session data."""
    def _create_request(user, current_site):
        factory = RequestFactory()
        request = factory.post('/', data={'buid': ''})  # Empty data, will be updated

        # Add session middleware
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        # Set session data
        request.session["client_id"] = user.client.id
        request.session["bu_id"] = current_site.id
        request.session["sitecode"] = current_site.bucode
        request.session["sitename"] = current_site.buname
        request.session["user_id"] = user.id

        # Set user
        request.user = user

        return request

    return _create_request


@pytest.mark.django_db
class TestSwitchSiteIDORVulnerability:
    """
    Test suite for IDOR vulnerability in SwitchSite view.

    This test class verifies that the SwitchSite view properly validates
    tenant ownership and user assignments before allowing site switching.
    """

    def test_switch_site_unauthorized_cross_tenant_access(
        self, setup_multi_tenant_scenario, authenticated_request_factory
    ):
        """
        Test that users CANNOT switch to sites they are not assigned to.

        Security Test: Prevents horizontal privilege escalation via IDOR.

        Scenario:
        1. User A is assigned to Site A
        2. User B is assigned to Site B (different tenant)
        3. User A attempts to switch to Site B by posting buid
        4. Expected: 403 Forbidden response
        5. Expected: Session is NOT updated with Site B data

        This test currently FAILS because SwitchSite doesn't validate ownership.
        """
        scenario = setup_multi_tenant_scenario

        # User A attempts to switch to User B's site
        request = authenticated_request_factory(scenario['user_a'], scenario['site_a'])
        request.POST = {'buid': str(scenario['site_b'].id)}

        # Execute the view
        view = SwitchSite.as_view()
        response = view(request)

        # SECURITY ASSERTION: Should return 403 Forbidden
        assert response.status_code == 403, (
            f"Expected 403 Forbidden for unauthorized site access, got {response.status_code}"
        )

        # Verify response contains error message
        response_data = response.json()
        assert response_data.get('rc') == 1, "Response should indicate error"
        assert 'Unauthorized' in response_data.get('errMsg', ''), (
            "Error message should mention unauthorized access"
        )

        # SECURITY ASSERTION: Session should NOT be updated with Site B
        assert request.session.get('bu_id') == scenario['site_a'].id, (
            "Session bu_id should remain Site A (not switched to Site B)"
        )
        assert request.session.get('sitecode') == scenario['site_a'].bucode, (
            "Session sitecode should remain Site A's code"
        )
        assert request.session.get('sitename') == scenario['site_a'].buname, (
            "Session sitename should remain Site A's name"
        )

    def test_switch_site_legitimate_user_can_switch(
        self, setup_multi_tenant_scenario, authenticated_request_factory
    ):
        """
        Test that users CAN switch to sites they ARE assigned to.

        Positive Test: Legitimate site switching should work.

        Scenario:
        1. User A is assigned to Site A
        2. User A attempts to switch to Site A (their own site)
        3. Expected: 200 OK response
        4. Expected: Session is updated with Site A data
        """
        scenario = setup_multi_tenant_scenario

        # User A switches to their own site (legitimate)
        request = authenticated_request_factory(scenario['user_a'], scenario['site_a'])
        request.POST = {'buid': str(scenario['site_a'].id)}

        # Execute the view
        view = SwitchSite.as_view()
        response = view(request)

        # Should succeed
        assert response.status_code == 200, (
            f"Expected 200 OK for legitimate site switch, got {response.status_code}"
        )

        # Verify response indicates success
        response_data = response.json()
        assert response_data.get('rc') == 0, "Response should indicate success"

        # Session should be updated correctly
        assert request.session.get('bu_id') == scenario['site_a'].id
        assert request.session.get('sitecode') == scenario['site_a'].bucode
        assert request.session.get('sitename') == scenario['site_a'].buname

    def test_switch_site_invalid_buid_returns_error(
        self, setup_multi_tenant_scenario, authenticated_request_factory
    ):
        """
        Test that invalid site IDs are rejected gracefully.

        Edge Case: Non-existent site IDs should not cause crashes.
        """
        scenario = setup_multi_tenant_scenario

        # User A attempts to switch to non-existent site
        request = authenticated_request_factory(scenario['user_a'], scenario['site_a'])
        request.POST = {'buid': '99999'}  # Non-existent site

        # Execute the view
        view = SwitchSite.as_view()
        response = view(request)

        # Should return error (not crash)
        response_data = response.json()
        assert response_data.get('rc') == 1, "Response should indicate error"
        assert 'unable to find site' in response_data.get('errMsg', '').lower(), (
            "Error message should mention site not found"
        )

    def test_switch_site_disabled_site_rejected(
        self, setup_multi_tenant_scenario, authenticated_request_factory
    ):
        """
        Test that disabled sites cannot be switched to.

        Edge Case: Disabled sites should be rejected even if user is assigned.
        """
        scenario = setup_multi_tenant_scenario

        # Disable Site A
        scenario['site_a'].enable = False
        scenario['site_a'].save()

        # User A attempts to switch to their own disabled site
        request = authenticated_request_factory(scenario['user_a'], scenario['site_a'])
        request.POST = {'buid': str(scenario['site_a'].id)}

        # Execute the view
        view = SwitchSite.as_view()
        response = view(request)

        # Should return error
        response_data = response.json()
        assert response_data.get('rc') == 1, "Response should indicate error"
        assert 'Inactive Site' in response_data.get('errMsg', ''), (
            "Error message should mention inactive site"
        )


@pytest.mark.django_db
class TestSwitchSiteWithAdminUser:
    """
    Test suite for admin users switching sites.

    Admin users should be able to switch to any site within their client.
    """

    def test_admin_can_switch_to_any_client_site(
        self, setup_multi_tenant_scenario, authenticated_request_factory
    ):
        """
        Test that admin users can switch to any site within their client.

        Admin Privilege: Admins have access to all sites in their client.
        """
        scenario = setup_multi_tenant_scenario

        # Make User A an admin
        scenario['user_a'].isadmin = True
        scenario['user_a'].save()

        # Create another site in Client A
        site_a2 = Bt.objects.create(
            bucode="SITE_A2",
            buname="Site A2",
            parent=scenario['client_a'],
            enable=True
        )

        # Admin User A switches to Site A2 (not explicitly assigned, but same client)
        request = authenticated_request_factory(scenario['user_a'], scenario['site_a'])
        request.POST = {'buid': str(site_a2.id)}

        # Execute the view
        view = SwitchSite.as_view()
        response = view(request)

        # Should succeed (admin has access to all client sites)
        assert response.status_code == 200, (
            f"Expected 200 OK for admin site switch, got {response.status_code}"
        )
        response_data = response.json()
        assert response_data.get('rc') == 0

        # Session should be updated
        assert request.session.get('bu_id') == site_a2.id

    def test_admin_cannot_switch_to_different_client_site(
        self, setup_multi_tenant_scenario, authenticated_request_factory
    ):
        """
        Test that admin users CANNOT switch to sites in different clients.

        Security Test: Admin privileges are scoped to their client (tenant isolation).
        """
        scenario = setup_multi_tenant_scenario

        # Make User A an admin (in Client A)
        scenario['user_a'].isadmin = True
        scenario['user_a'].save()

        # Admin User A attempts to switch to Client B's site
        request = authenticated_request_factory(scenario['user_a'], scenario['site_a'])
        request.POST = {'buid': str(scenario['site_b'].id)}

        # Execute the view
        view = SwitchSite.as_view()
        response = view(request)

        # Should be rejected (different client)
        assert response.status_code == 403, (
            f"Expected 403 Forbidden for cross-client access, got {response.status_code}"
        )
        response_data = response.json()
        assert response_data.get('rc') == 1
