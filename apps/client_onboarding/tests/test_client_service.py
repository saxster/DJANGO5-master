import pytest
from apps.client_onboarding.services import ClientService


@pytest.mark.django_db
class TestClientService:

    def test_create_client_returns_uuid(self):
        """Test creating client returns UUID string, not model instance"""
        service = ClientService()

        client_id = service.create_client(
            name='Test Corp',
            client_type='CORPORATE',
            preferences={'industry': 'tech'}
        )

        # Should return UUID string
        assert isinstance(client_id, str)
        assert len(client_id) == 36

    def test_get_client_details_returns_dto(self):
        """Test get_client_details returns dict (DTO), not model"""
        service = ClientService()

        client_id = service.create_client(
            name='Test Corp',
            client_type='CORPORATE',
            preferences={'industry': 'tech'}
        )

        details = service.get_client_details(client_id)

        # Should return dict (DTO)
        assert isinstance(details, dict)
        assert details['id'] == client_id
        assert details['name'] == 'Test Corp'
        assert 'preferences' in details
