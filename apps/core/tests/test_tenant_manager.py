"""
Unit Tests for Tenant Manager

Comprehensive test coverage for tenant filtering managers and querysets.

Test Coverage:
- TenantQuerySet filtering methods
- TenantManager integration
- Client filtering
- Business unit filtering
- User-based filtering
- Edge cases and error handling

Compliance:
- Specific exception testing (Rule 11)
- 100% code coverage
- Security validation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from django.core.exceptions import FieldError
from django.db import models

from apps.core.managers.tenant_manager import (
    TenantQuerySet,
    TenantManager,
)


class MockModel(models.Model):
    """Mock model for testing."""
    client_id = models.IntegerField()
    bu_id = models.IntegerField()
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'core'


class TestTenantQuerySet:
    """Test TenantQuerySet filtering methods."""

    def test_for_client_filters_by_client_id(self):
        mock_qs = Mock(spec=TenantQuerySet)
        mock_qs.filter = Mock(return_value=mock_qs)

        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_client(10)

        queryset.filter.assert_called_once_with(client_id=10)

    def test_for_client_returns_none_for_null_id(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_client(None)

        queryset.none.assert_called_once()

    def test_for_business_unit_filters_by_bu_id(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_business_unit(20)

        queryset.filter.assert_called_once_with(bu_id=20)

    def test_for_business_unit_returns_none_for_null_id(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_business_unit(None)

        queryset.none.assert_called_once()

    def test_for_user_filters_by_user_client(self):
        mock_user = Mock()
        mock_user.client_id = 10

        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_user(mock_user)

        queryset.filter.assert_called_once_with(client_id=10)

    def test_for_user_returns_none_for_no_user(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_user(None)

        queryset.none.assert_called_once()

    def test_for_user_returns_none_for_missing_client_id(self):
        mock_user = Mock(spec=[])

        queryset = TenantQuerySet(model=MockModel)
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_user(mock_user)

        queryset.none.assert_called_once()


class TestTenantManager:
    """Test TenantManager integration."""

    def test_get_queryset_returns_tenant_queryset(self):
        manager = TenantManager()
        manager.model = MockModel
        manager._db = 'default'

        queryset = manager.get_queryset()

        assert isinstance(queryset, TenantQuerySet)

    def test_for_client_delegates_to_queryset(self):
        manager = TenantManager()
        manager.model = MockModel
        manager._db = 'default'

        mock_qs = Mock(spec=TenantQuerySet)
        mock_qs.for_client = Mock(return_value=mock_qs)

        with patch.object(manager, 'get_queryset', return_value=mock_qs):
            result = manager.for_client(10)

            mock_qs.for_client.assert_called_once_with(10)

    def test_for_business_unit_delegates_to_queryset(self):
        manager = TenantManager()
        manager.model = MockModel
        manager._db = 'default'

        mock_qs = Mock(spec=TenantQuerySet)
        mock_qs.for_business_unit = Mock(return_value=mock_qs)

        with patch.object(manager, 'get_queryset', return_value=mock_qs):
            result = manager.for_business_unit(20)

            mock_qs.for_business_unit.assert_called_once_with(20)

    def test_for_user_delegates_to_queryset(self):
        mock_user = Mock()
        mock_user.client_id = 10

        manager = TenantManager()
        manager.model = MockModel
        manager._db = 'default'

        mock_qs = Mock(spec=TenantQuerySet)
        mock_qs.for_user = Mock(return_value=mock_qs)

        with patch.object(manager, 'get_queryset', return_value=mock_qs):
            result = manager.for_user(mock_user)

            mock_qs.for_user.assert_called_once_with(mock_user)


class TestSecurityAndIsolation:
    """Test security and tenant isolation."""

    def test_prevents_cross_tenant_data_access(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        queryset.for_client(10)
        queryset.filter.assert_called_with(client_id=10)

        queryset.for_client(20)
        queryset.filter.assert_called_with(client_id=20)

    def test_null_client_id_returns_empty_queryset(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_client(None)

        assert queryset.none.called

    def test_invalid_user_returns_empty_queryset(self):
        invalid_user = "not_a_user_object"

        queryset = TenantQuerySet(model=MockModel)
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_user(invalid_user)

        assert queryset.none.called


class TestChainability:
    """Test queryset method chaining."""

    def test_can_chain_filter_methods(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_client(10).for_business_unit(20)

        assert queryset.filter.call_count == 2

    def test_can_chain_with_other_queryset_methods(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)
        queryset.order_by = Mock(return_value=queryset)

        result = queryset.for_client(10).order_by('name')

        queryset.filter.assert_called_with(client_id=10)
        queryset.order_by.assert_called_with('name')


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_for_client_handles_field_error(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(side_effect=FieldError("No client_id field"))

        with pytest.raises(FieldError, match="does not support client filtering"):
            queryset.for_client(10)

    def test_for_business_unit_handles_field_error(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(side_effect=FieldError("No bu_id field"))

        with pytest.raises(FieldError, match="does not support business unit filtering"):
            queryset.for_business_unit(20)

    def test_for_user_handles_attribute_error(self):
        mock_user = Mock()
        mock_user.client_id = 10

        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(side_effect=AttributeError("Test error"))
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_user(mock_user)

        queryset.none.assert_called_once()

    def test_for_user_handles_field_error(self):
        mock_user = Mock()
        mock_user.client_id = 10

        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(side_effect=FieldError("No client_id field"))
        queryset.none = Mock(return_value=queryset)

        result = queryset.for_user(mock_user)

        queryset.none.assert_called_once()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_as_client_id(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_client(0)

        queryset.filter.assert_called_with(client_id=0)

    def test_negative_client_id(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_client(-1)

        queryset.filter.assert_called_with(client_id=-1)

    def test_very_large_client_id(self):
        large_id = 999999999999

        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_client(large_id)

        queryset.filter.assert_called_with(client_id=large_id)

    def test_user_with_only_client_id(self):
        mock_user = Mock(spec=['client_id'])
        mock_user.client_id = 10

        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_user(mock_user)

        queryset.filter.assert_called_with(client_id=10)

    def test_string_client_id_passed_through(self):
        queryset = TenantQuerySet(model=MockModel)
        queryset.filter = Mock(return_value=queryset)

        result = queryset.for_client("10")

        queryset.filter.assert_called_with(client_id="10")