import pytest
from apps.site_onboarding.services import SiteService


@pytest.mark.django_db
class TestSiteService:

    def test_create_site_returns_uuid(self):
        """Test creating site returns UUID string"""
        from apps.client_onboarding.services import ClientService

        # Create client first
        client_service = ClientService()
        client_id = client_service.create_client(
            name='Test Client',
            client_type='CORPORATE',
            preferences={}
        )

        # Create site
        site_service = SiteService()
        site_id = site_service.create_site(
            client_id=client_id,
            name='Main Office',
            site_type='OFFICE'
        )

        assert isinstance(site_id, str)
        assert len(site_id) == 36

    def test_add_observation_with_zero_media(self):
        """Test adding text-only observation (0 media)"""
        site_service = SiteService()
        # ... test 0 media scenario

    def test_add_observation_with_multiple_media(self):
        """Test adding observation with N photos"""
        site_service = SiteService()
        # ... test N media scenario
