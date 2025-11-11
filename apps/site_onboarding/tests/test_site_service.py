import pytest
from django.db import IntegrityError
from apps.site_onboarding.services import SiteService
from apps.core_onboarding.models import ConversationSession


@pytest.mark.django_db
class TestSiteService:

    def test_create_site_returns_uuid(self):
        """Test creating site returns UUID string with required conversation_session"""
        from apps.client_onboarding.services import ClientService
        from apps.peoples.models import People

        # Create user for conversation session
        user = People.objects.create(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

        # Create client first
        client_service = ClientService()
        client_id = client_service.create_client(
            name='Test Client',
            client_type='CORPORATE',
            preferences={}
        )

        # Create conversation session
        conversation = ConversationSession.objects.create(
            user=user,
            context_type='SITE',
            language='en'
        )

        # Create site with required conversation_session_id
        site_service = SiteService()
        site_id = site_service.create_site(
            client_id=client_id,
            site_type='OFFICE',
            conversation_session_id=str(conversation.session_id)
        )

        assert isinstance(site_id, str)
        assert len(site_id) == 36

        # Verify FK relationship is established
        conversation.refresh_from_db()
        assert conversation.context_object_id == site_id

    def test_create_site_requires_conversation_session(self):
        """Test that missing conversation_session_id raises DoesNotExist"""
        from apps.client_onboarding.services import ClientService

        # Create client first
        client_service = ClientService()
        client_id = client_service.create_client(
            name='Test Client',
            client_type='CORPORATE',
            preferences={}
        )

        # Try to create site with invalid conversation_session_id
        site_service = SiteService()
        with pytest.raises(ConversationSession.DoesNotExist):
            site_service.create_site(
                client_id=client_id,
                site_type='OFFICE',
                conversation_session_id='00000000-0000-0000-0000-000000000000'
            )

    def test_add_observation_with_zero_media(self):
        """Test adding text-only observation (0 media)"""
        site_service = SiteService()
        # ... test 0 media scenario

    def test_add_observation_with_multiple_media(self):
        """Test adding observation with N photos"""
        site_service = SiteService()
        # ... test N media scenario
