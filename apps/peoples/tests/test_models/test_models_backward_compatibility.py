"""
Test backward compatibility after models refactoring.

This test suite ensures that the refactored models/ directory structure
maintains 100% backward compatibility with code that imported from the
old monolithic models.py file.

Tests verify:
1. All model classes accessible via old import path
2. upload_peopleimg() function still works
3. peoplejson() function still works
4. All model functionality unchanged
5. Deprecation warnings are properly issued
"""

import pytest
import warnings
from django.core.exceptions import ValidationError
from django.utils import timezone


class TestBackwardCompatibleImports:
    """Test that old import paths still work."""

    def test_can_import_models_from_old_path(self):
        """Verify all models can be imported from apps.peoples.models"""
        from apps.peoples.models import (
            BaseModel,
            People,
            PeopleProfile,
            PeopleOrganizational,
            PermissionGroup,
            Pgroup,
            Pgbelonging,
            Capability
        )

        assert BaseModel is not None
        assert People is not None
        assert PeopleProfile is not None
        assert PeopleOrganizational is not None
        assert PermissionGroup is not None
        assert Pgroup is not None
        assert Pgbelonging is not None
        assert Capability is not None

    def test_can_import_utility_functions(self):
        """Verify utility functions still accessible"""
        from apps.peoples.models import (
            peoplejson,
            upload_peopleimg,
            now
        )

        assert callable(peoplejson)
        assert callable(upload_peopleimg)
        assert callable(now)

    def test_wildcard_import_works(self):
        """Verify wildcard import includes all expected exports"""
        import apps.peoples.models as models_module

        # Check __all__ is defined
        assert hasattr(models_module, '__all__')
        assert 'People' in models_module.__all__
        assert 'BaseModel' in models_module.__all__
        assert 'upload_peopleimg' in models_module.__all__

    def test_models_are_same_as_refactored_versions(self):
        """Verify imported models are the same objects as refactored versions"""
        from apps.peoples.models import People as PeopleOld
        from apps.peoples.models.user_model import People as PeopleNew

        # Should be the exact same class object
        assert PeopleOld is PeopleNew


class TestDeprecatedFunctions:
    """Test that deprecated utility functions still work but issue warnings."""

    def test_peoplejson_issues_deprecation_warning(self):
        """peoplejson() should work but issue DeprecationWarning"""
        from apps.peoples.models import peoplejson

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = peoplejson()

            # Should have issued a deprecation warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

        # Should still return correct structure
        assert isinstance(result, dict)
        assert 'mobilecapability' in result
        assert 'webcapability' in result

    def test_now_issues_deprecation_warning(self):
        """now() should work but issue DeprecationWarning"""
        from apps.peoples.models import now

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = now()

            # Should have issued a deprecation warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

        # Should still return correct value
        assert result is not None
        assert result.microsecond == 0  # Microseconds should be stripped

    def test_upload_peopleimg_issues_deprecation_warning(self, mock_people_instance):
        """upload_peopleimg() should work but issue DeprecationWarning"""
        from apps.peoples.models import upload_peopleimg

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = upload_peopleimg(mock_people_instance, "test.jpg")

            # Should have issued a deprecation warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

        # Should still return a valid path
        assert isinstance(result, str)
        assert len(result) > 0


class TestUploadPeopleimgDelegation:
    """Test that upload_peopleimg delegates to SecureFileUploadService."""

    def test_upload_peopleimg_delegates_to_service(self, mock_people_instance, monkeypatch):
        """Verify upload_peopleimg calls SecureFileUploadService"""
        from apps.peoples.models import upload_peopleimg

        # Track if service was called
        service_called = False
        original_path = "master/test_client/people/secure_file.jpg"

        def mock_generate_secure_upload_path(instance, filename):
            nonlocal service_called
            service_called = True
            return original_path

        # Monkeypatch the service
        from apps.peoples.services import file_upload_service
        monkeypatch.setattr(
            file_upload_service.SecureFileUploadService,
            'generate_secure_upload_path',
            mock_generate_secure_upload_path
        )

        # Call the deprecated function
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignore deprecation warning for this test
            result = upload_peopleimg(mock_people_instance, "test.jpg")

        # Verify service was called
        assert service_called
        assert result == original_path

    def test_upload_peopleimg_handles_service_failure(self, mock_people_instance, monkeypatch):
        """Verify upload_peopleimg returns fallback on service failure"""
        from apps.peoples.models import upload_peopleimg

        def mock_generate_secure_upload_path_fails(instance, filename):
            raise ValueError("Service failed")

        # Monkeypatch the service to fail
        from apps.peoples.services import file_upload_service
        monkeypatch.setattr(
            file_upload_service.SecureFileUploadService,
            'generate_secure_upload_path',
            mock_generate_secure_upload_path_fails
        )

        # Should return fallback path
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = upload_peopleimg(mock_people_instance, "test.jpg")

        assert result == "master/people/blank.png"  # Fallback path


class TestModelFunctionality:
    """Test that core model functionality remains unchanged."""

    def test_people_model_has_all_expected_fields(self):
        """Verify People model has all expected fields"""
        from apps.peoples.models import People

        # Core authentication fields
        assert hasattr(People, 'loginid')
        assert hasattr(People, 'peoplecode')
        assert hasattr(People, 'peoplename')
        assert hasattr(People, 'email')
        assert hasattr(People, 'mobno')
        assert hasattr(People, 'isadmin')
        assert hasattr(People, 'is_staff')
        assert hasattr(People, 'isverified')
        assert hasattr(People, 'enable')
        assert hasattr(People, 'capabilities')

    def test_people_model_has_capability_methods(self):
        """Verify capability management methods still available"""
        from apps.peoples.models import People

        # Methods should be available via mixin
        assert hasattr(People, 'has_capability')
        assert hasattr(People, 'add_capability')
        assert hasattr(People, 'remove_capability')
        assert hasattr(People, 'get_all_capabilities')
        assert hasattr(People, 'set_ai_capabilities')
        assert hasattr(People, 'get_effective_permissions')

    def test_organizational_model_has_query_helpers(self):
        """Verify OrganizationalQueryMixin methods available"""
        from apps.peoples.models import PeopleOrganizational

        # Methods should be available via mixin
        assert hasattr(PeopleOrganizational, 'get_team_members')
        assert hasattr(PeopleOrganizational, 'get_department_colleagues')
        assert hasattr(PeopleOrganizational, 'get_location_colleagues')
        assert hasattr(PeopleOrganizational, 'is_in_same_business_unit')
        assert hasattr(PeopleOrganizational, 'get_reporting_chain')


# Pytest fixtures

@pytest.fixture
def mock_people_instance():
    """Create a mock People instance for testing."""
    from unittest.mock import Mock

    mock_instance = Mock()
    mock_instance.id = 1
    mock_instance.peoplecode = "TEST001"
    mock_instance.peoplename = "Test User"
    mock_instance.client_id = 1

    # Mock client with bucode
    mock_client = Mock()
    mock_client.bucode = "TESTCLIENT"
    mock_client.id = 1
    mock_instance.client = mock_client

    return mock_instance


@pytest.mark.django_db
class TestDatabaseBackwardCompatibility:
    """Test that database operations work correctly with refactored models."""

    def test_can_query_people_via_old_import(self, create_test_user):
        """Verify querying People model works via old import path"""
        from apps.peoples.models import People

        # Should be able to query normally
        users = People.objects.all()
        assert users.count() >= 1

    def test_model_meta_unchanged(self):
        """Verify model Meta settings remain consistent"""
        from apps.peoples.models import People

        assert People._meta.db_table == "people"
        assert People._meta.verbose_name == "Person"


@pytest.fixture
def create_test_user(db):
    """Create a test user for database tests."""
    from apps.peoples.models import People
    from django.contrib.auth.hashers import make_password
    import datetime

    user = People.objects.create(
        loginid="testuser",
        peoplecode="TEST001",
        peoplename="Test User",
        email="test@example.com",
        password=make_password("testpass123"),
        dateofbirth=datetime.date(1990, 1, 1),
        isverified=True,
        enable=True
    )
    return user