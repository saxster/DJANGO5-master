"""
Tests for UserCapabilityService - user capability and permission management.

Tests cover:
- Capability CRUD operations
- AI capability management
- Permission validation
- Bulk capability updates
- Effective permissions calculation
- Security boundaries
- Error handling

Security: Ensures capability changes are validated and logged
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError

from apps.peoples.services.user_capability_service import UserCapabilityService
from apps.peoples.models import People


@pytest.fixture
def user(db):
    """Test user fixture."""
    user = People.objects.create(
        username="test_user",
        email="test@example.com",
        first_name="Test",
        last_name="User",
        capabilities={}
    )
    return user


@pytest.fixture
def admin_user(db):
    """Admin user fixture."""
    user = People.objects.create(
        username="admin_user",
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        is_staff=True,
        is_superuser=True,
        isadmin=True,
        capabilities={}
    )
    return user


@pytest.mark.django_db
class TestUserCapabilityService:
    """Test suite for UserCapabilityService."""

    def test_has_capability_true(self, user):
        """Test checking capability that exists."""
        user.capabilities = {'can_approve_ai_recommendations': True}

        assert UserCapabilityService.has_capability(
            user, 'can_approve_ai_recommendations'
        ) is True

    def test_has_capability_false(self, user):
        """Test checking capability that doesn't exist."""
        user.capabilities = {}

        assert UserCapabilityService.has_capability(
            user, 'non_existent_capability'
        ) is False

    def test_has_capability_null_capabilities(self, user):
        """Test checking capability when capabilities is None."""
        user.capabilities = None

        assert UserCapabilityService.has_capability(
            user, 'any_capability'
        ) is False

    def test_add_capability_new(self, user):
        """Test adding new capability."""
        result = UserCapabilityService.add_capability(
            user, 'new_capability', True
        )

        assert result is True
        assert user.capabilities['new_capability'] is True

    def test_add_capability_update_existing(self, user):
        """Test updating existing capability."""
        user.capabilities = {'existing_capability': False}

        result = UserCapabilityService.add_capability(
            user, 'existing_capability', True
        )

        assert result is True
        assert user.capabilities['existing_capability'] is True

    def test_add_capability_custom_value(self, user):
        """Test adding capability with custom value."""
        result = UserCapabilityService.add_capability(
            user, 'custom_capability', {'level': 'advanced'}
        )

        assert result is True
        assert user.capabilities['custom_capability'] == {'level': 'advanced'}

    def test_add_capability_null_capabilities(self, user):
        """Test adding capability when capabilities is None."""
        user.capabilities = None

        result = UserCapabilityService.add_capability(
            user, 'first_capability', True
        )

        assert result is True
        assert user.capabilities is not None
        assert user.capabilities['first_capability'] is True

    def test_remove_capability_existing(self, user):
        """Test removing existing capability."""
        user.capabilities = {'to_remove': True, 'to_keep': True}

        result = UserCapabilityService.remove_capability(user, 'to_remove')

        assert result is True
        assert 'to_remove' not in user.capabilities
        assert 'to_keep' in user.capabilities

    def test_remove_capability_non_existent(self, user):
        """Test removing non-existent capability."""
        user.capabilities = {'existing': True}

        result = UserCapabilityService.remove_capability(user, 'non_existent')

        assert result is True  # Still returns True

    def test_remove_capability_null_capabilities(self, user):
        """Test removing capability when capabilities is None."""
        user.capabilities = None

        result = UserCapabilityService.remove_capability(user, 'any_capability')

        assert result is True

    def test_get_all_capabilities_with_data(self, user):
        """Test getting all capabilities."""
        user.capabilities = {
            'cap1': True,
            'cap2': False,
            'cap3': {'nested': 'value'}
        }

        all_caps = UserCapabilityService.get_all_capabilities(user)

        assert len(all_caps) == 3
        assert all_caps['cap1'] is True
        assert all_caps['cap2'] is False
        assert all_caps['cap3'] == {'nested': 'value'}

    def test_get_all_capabilities_empty(self, user):
        """Test getting capabilities when empty."""
        user.capabilities = {}

        all_caps = UserCapabilityService.get_all_capabilities(user)

        assert all_caps == {}

    def test_get_all_capabilities_null(self, user):
        """Test getting capabilities when None."""
        user.capabilities = None

        all_caps = UserCapabilityService.get_all_capabilities(user)

        assert all_caps == {}

    def test_get_all_capabilities_returns_copy(self, user):
        """Test that get_all_capabilities returns a copy, not reference."""
        user.capabilities = {'original': True}

        all_caps = UserCapabilityService.get_all_capabilities(user)
        all_caps['modified'] = True

        # Original should be unchanged
        assert 'modified' not in user.capabilities

    def test_set_ai_capabilities_all_enabled(self, user):
        """Test setting all AI capabilities to True."""
        result = UserCapabilityService.set_ai_capabilities(
            user,
            can_approve=True,
            can_manage_kb=True,
            is_approver=True
        )

        assert result is True
        assert user.capabilities['can_approve_ai_recommendations'] is True
        assert user.capabilities['can_manage_knowledge_base'] is True
        assert user.capabilities['ai_recommendation_approver'] is True

    def test_set_ai_capabilities_mixed(self, user):
        """Test setting AI capabilities with mixed values."""
        result = UserCapabilityService.set_ai_capabilities(
            user,
            can_approve=True,
            can_manage_kb=False,
            is_approver=False
        )

        assert result is True
        assert user.capabilities['can_approve_ai_recommendations'] is True
        assert user.capabilities['can_manage_knowledge_base'] is False
        assert user.capabilities['ai_recommendation_approver'] is False

    def test_set_ai_capabilities_preserves_other(self, user):
        """Test AI capability setting preserves other capabilities."""
        user.capabilities = {'other_capability': 'preserved'}

        UserCapabilityService.set_ai_capabilities(
            user, can_approve=True
        )

        assert user.capabilities['other_capability'] == 'preserved'
        assert user.capabilities['can_approve_ai_recommendations'] is True

    def test_set_ai_capabilities_null_capabilities(self, user):
        """Test setting AI capabilities when capabilities is None."""
        user.capabilities = None

        result = UserCapabilityService.set_ai_capabilities(
            user, can_approve=True
        )

        assert result is True
        assert user.capabilities is not None

    def test_get_effective_permissions_regular_user(self, user):
        """Test effective permissions for regular user."""
        user.capabilities = {'custom_capability': True}
        user.is_staff = False
        user.is_superuser = False
        user.isadmin = False

        perms = UserCapabilityService.get_effective_permissions(user)

        assert perms['custom_capability'] is True
        assert 'system_administrator' not in perms or perms['system_administrator'] is False
        assert 'staff_access' not in perms or perms['staff_access'] is False

    def test_get_effective_permissions_superuser(self, admin_user):
        """Test effective permissions for superuser."""
        admin_user.capabilities = {}

        perms = UserCapabilityService.get_effective_permissions(admin_user)

        assert perms['system_administrator'] is True
        assert perms['staff_access'] is True
        assert perms['tenant_administrator'] is True

    def test_get_effective_permissions_staff(self, user):
        """Test effective permissions for staff user."""
        user.is_staff = True
        user.capabilities = {}

        perms = UserCapabilityService.get_effective_permissions(user)

        assert perms['staff_access'] is True

    def test_get_effective_permissions_admin(self, user):
        """Test effective permissions for admin user."""
        user.isadmin = True
        user.capabilities = {}

        perms = UserCapabilityService.get_effective_permissions(user)

        assert perms['tenant_administrator'] is True

    def test_validate_capability_update_valid_name(self):
        """Test validation accepts valid capability names."""
        assert UserCapabilityService.validate_capability_update(
            'custom_capability', True
        ) is True

    def test_validate_capability_update_empty_name(self):
        """Test validation rejects empty capability name."""
        with pytest.raises(ValidationError, match="non-empty string"):
            UserCapabilityService.validate_capability_update('', True)

    def test_validate_capability_update_non_string_name(self):
        """Test validation rejects non-string capability name."""
        with pytest.raises(ValidationError, match="non-empty string"):
            UserCapabilityService.validate_capability_update(123, True)

    def test_validate_capability_update_ai_capability_boolean(self):
        """Test AI capabilities must be boolean."""
        # Valid boolean
        assert UserCapabilityService.validate_capability_update(
            'can_approve_ai_recommendations', True
        ) is True

        # Invalid non-boolean
        with pytest.raises(ValidationError, match="must be a boolean"):
            UserCapabilityService.validate_capability_update(
                'can_approve_ai_recommendations', "yes"
            )

    def test_validate_capability_update_system_capability_protected(self):
        """Test system capabilities cannot be modified directly."""
        with pytest.raises(ValidationError, match="cannot be modified directly"):
            UserCapabilityService.validate_capability_update(
                'system_administrator', True
            )

    def test_bulk_update_capabilities_success(self, user):
        """Test bulk updating multiple capabilities."""
        capabilities = {
            'cap1': True,
            'cap2': False,
            'cap3': {'nested': 'data'}
        }

        success, errors = UserCapabilityService.bulk_update_capabilities(
            user, capabilities
        )

        assert success is True
        assert errors == []
        assert user.capabilities['cap1'] is True
        assert user.capabilities['cap2'] is False
        assert user.capabilities['cap3'] == {'nested': 'data'}

    def test_bulk_update_capabilities_validation_error(self, user):
        """Test bulk update with validation error."""
        capabilities = {
            'valid_cap': True,
            'system_administrator': True,  # Protected
        }

        success, errors = UserCapabilityService.bulk_update_capabilities(
            user, capabilities
        )

        assert success is False
        assert len(errors) > 0
        assert any('system_administrator' in err for err in errors)
        # Valid capabilities should not be applied if any validation fails
        assert 'valid_cap' not in user.capabilities

    def test_bulk_update_capabilities_mixed_validation(self, user):
        """Test bulk update with multiple validation errors."""
        capabilities = {
            '': True,  # Invalid name
            'can_approve_ai_recommendations': 'not_boolean',  # Invalid value
        }

        success, errors = UserCapabilityService.bulk_update_capabilities(
            user, capabilities
        )

        assert success is False
        assert len(errors) == 2

    def test_bulk_update_capabilities_null_capabilities(self, user):
        """Test bulk update when capabilities is None."""
        user.capabilities = None

        capabilities = {'new_cap': True}

        success, errors = UserCapabilityService.bulk_update_capabilities(
            user, capabilities
        )

        assert success is True
        assert user.capabilities is not None
        assert user.capabilities['new_cap'] is True

    def test_bulk_update_capabilities_preserves_existing(self, user):
        """Test bulk update preserves non-updated capabilities."""
        user.capabilities = {'preserve_this': 'original'}

        capabilities = {'new_cap': True}

        UserCapabilityService.bulk_update_capabilities(user, capabilities)

        assert user.capabilities['preserve_this'] == 'original'
        assert user.capabilities['new_cap'] is True

    @patch('apps.peoples.services.user_capability_service.ErrorHandler.handle_exception')
    def test_add_capability_error_handling(self, mock_error_handler, user):
        """Test error handling in add_capability."""
        # Simulate error by making capabilities.get() fail
        user.capabilities = Mock()
        user.capabilities.get.side_effect = TypeError("Mock error")

        mock_error_handler.return_value = "correlation_id_123"

        result = UserCapabilityService.add_capability(user, 'test_cap', True)

        assert result is False
        assert mock_error_handler.called

    @patch('apps.peoples.services.user_capability_service.ErrorHandler.handle_exception')
    def test_remove_capability_error_handling(self, mock_error_handler, user):
        """Test error handling in remove_capability."""
        user.capabilities = Mock()
        user.capabilities.pop.side_effect = TypeError("Mock error")

        mock_error_handler.return_value = "correlation_id_456"

        result = UserCapabilityService.remove_capability(user, 'test_cap')

        assert result is False
        assert mock_error_handler.called

    @patch('apps.peoples.services.user_capability_service.ErrorHandler.handle_exception')
    def test_set_ai_capabilities_error_handling(self, mock_error_handler, user):
        """Test error handling in set_ai_capabilities."""
        user.capabilities = Mock()
        user.capabilities.update.side_effect = DatabaseError("DB error")

        mock_error_handler.return_value = "correlation_id_789"

        result = UserCapabilityService.set_ai_capabilities(user, can_approve=True)

        assert result is False
        assert mock_error_handler.called

    @patch('apps.peoples.services.user_capability_service.ErrorHandler.handle_exception')
    def test_bulk_update_capabilities_error_handling(self, mock_error_handler, user):
        """Test error handling in bulk_update_capabilities."""
        user.capabilities = Mock()
        user.capabilities.update.side_effect = DatabaseError("DB error")

        mock_error_handler.return_value = "correlation_id_101"

        capabilities = {'test_cap': True}
        success, errors = UserCapabilityService.bulk_update_capabilities(
            user, capabilities
        )

        assert success is False
        assert len(errors) > 0
        assert mock_error_handler.called

    def test_ai_capabilities_constant(self):
        """Test AI_CAPABILITIES constant contains expected values."""
        ai_caps = UserCapabilityService.AI_CAPABILITIES

        assert 'can_approve_ai_recommendations' in ai_caps
        assert 'can_manage_knowledge_base' in ai_caps
        assert 'ai_recommendation_approver' in ai_caps

    def test_system_capabilities_constant(self):
        """Test SYSTEM_CAPABILITIES constant contains expected values."""
        sys_caps = UserCapabilityService.SYSTEM_CAPABILITIES

        assert 'system_administrator' in sys_caps
        assert 'staff_access' in sys_caps
        assert 'tenant_administrator' in sys_caps


@pytest.mark.django_db
class TestUserCapabilityServiceIntegration:
    """Integration tests for UserCapabilityService."""

    def test_complete_capability_lifecycle(self, user):
        """Test complete lifecycle of adding, updating, and removing capability."""
        # Add capability
        assert UserCapabilityService.add_capability(user, 'test_feature', True) is True
        assert UserCapabilityService.has_capability(user, 'test_feature') is True

        # Update capability
        assert UserCapabilityService.add_capability(user, 'test_feature', False) is True
        assert UserCapabilityService.has_capability(user, 'test_feature') is False

        # Remove capability
        assert UserCapabilityService.remove_capability(user, 'test_feature') is True
        assert UserCapabilityService.has_capability(user, 'test_feature') is False

    def test_ai_enrollment_workflow(self, user):
        """Test AI enrollment capability workflow."""
        # User starts without AI capabilities
        assert UserCapabilityService.has_capability(
            user, 'can_approve_ai_recommendations'
        ) is False

        # Grant AI capabilities
        assert UserCapabilityService.set_ai_capabilities(
            user, can_approve=True, can_manage_kb=True
        ) is True

        # Verify capabilities granted
        assert UserCapabilityService.has_capability(
            user, 'can_approve_ai_recommendations'
        ) is True
        assert UserCapabilityService.has_capability(
            user, 'can_manage_knowledge_base'
        ) is True

        # Check effective permissions
        perms = UserCapabilityService.get_effective_permissions(user)
        assert perms['can_approve_ai_recommendations'] is True

    def test_permission_escalation_prevention(self, user):
        """Test that users cannot escalate to system capabilities."""
        # Attempt to add system capability
        with pytest.raises(ValidationError):
            UserCapabilityService.validate_capability_update(
                'system_administrator', True
            )

        # Bulk update should also fail
        capabilities = {'system_administrator': True}
        success, errors = UserCapabilityService.bulk_update_capabilities(
            user, capabilities
        )

        assert success is False
        assert 'system_administrator' not in user.capabilities

    def test_multi_user_capability_isolation(self, db):
        """Test that capability changes don't affect other users."""
        user1 = People.objects.create(username="user1", email="user1@test.com", capabilities={})
        user2 = People.objects.create(username="user2", email="user2@test.com", capabilities={})

        # Add capability to user1
        UserCapabilityService.add_capability(user1, 'feature_x', True)

        # Verify user2 unaffected
        assert UserCapabilityService.has_capability(user1, 'feature_x') is True
        assert UserCapabilityService.has_capability(user2, 'feature_x') is False

    def test_capability_persistence_after_save(self, user):
        """Test capabilities persist after database save."""
        # Add capability
        UserCapabilityService.add_capability(user, 'persistent_cap', True)
        user.save()

        # Reload from database
        user.refresh_from_db()

        # Verify capability persisted
        assert UserCapabilityService.has_capability(user, 'persistent_cap') is True
