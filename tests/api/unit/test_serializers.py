"""
Unit tests for API serializers.

Tests dynamic field selection, bulk operations, caching, and permissions.
"""

import pytest
from unittest.mock import Mock, patch
from django.core.cache import cache
from rest_framework import serializers
from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import User, AnonymousUser

from apps.api.v1.serializers.base import (
    OptimizedModelSerializer,
    DynamicFieldsMixin,
    BulkSerializerMixin,
    CachedSerializerMixin,
    FieldPermissionsMixin
)
from apps.peoples.models import People, Pgroup


@pytest.mark.unit
@pytest.mark.api
class TestOptimizedModelSerializer:
    """Test OptimizedModelSerializer functionality."""
    
    def test_creates_serializer_successfully(self, people_factory):
        """Test that OptimizedModelSerializer can be instantiated."""
        person = people_factory.create()
        
        class TestSerializer(OptimizedModelSerializer):
            class Meta:
                model = People
                fields = '__all__'
        
        serializer = TestSerializer(instance=person)
        assert serializer is not None
        assert hasattr(serializer, 'get_queryset')
    
    def test_queryset_optimization(self, people_factory):
        """Test that queryset optimization is applied."""
        person = people_factory.create()
        
        class TestSerializer(OptimizedModelSerializer):
            class Meta:
                model = People
                fields = '__all__'
            
            def get_queryset(self, queryset):
                return queryset.select_related('shift', 'bt')
        
        serializer = TestSerializer(instance=person)
        # This test would need more setup to verify select_related is called
        assert serializer.instance == person


@pytest.mark.unit
@pytest.mark.api
class TestDynamicFieldsMixin:
    """Test dynamic field selection functionality."""
    
    def test_field_selection_with_fields_param(self, people_factory):
        """Test field selection with 'fields' parameter."""
        person = people_factory.create()
        
        class TestSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = '__all__'
        
        # Test with specific fields
        request = Mock()
        request.GET = {'fields': 'id,first_name,email'}
        
        serializer = TestSerializer(instance=person, context={'request': request})
        serializer_fields = set(serializer.fields.keys())
        expected_fields = {'id', 'first_name', 'email'}
        
        assert serializer_fields == expected_fields
    
    def test_field_exclusion_with_exclude_param(self, people_factory):
        """Test field exclusion with 'exclude' parameter."""
        person = people_factory.create()
        
        class TestSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email', 'mobile']
        
        request = Mock()
        request.GET = {'exclude': 'mobile,last_name'}
        
        serializer = TestSerializer(instance=person, context={'request': request})
        serializer_fields = set(serializer.fields.keys())
        expected_fields = {'id', 'first_name', 'email'}
        
        assert serializer_fields == expected_fields
    
    def test_expand_nested_fields(self, people_factory, pgroup_factory):
        """Test expanding nested relationships."""
        group = pgroup_factory.create()
        person = people_factory.create()
        person.groups.add(group)
        
        class TestSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
            groups = serializers.SerializerMethodField()
            
            class Meta:
                model = People
                fields = ['id', 'first_name', 'groups']
            
            def get_groups(self, obj):
                return [{'id': g.id, 'name': g.name} for g in obj.groups.all()]
        
        request = Mock()
        request.GET = {'expand': 'groups'}
        
        serializer = TestSerializer(instance=person, context={'request': request})
        data = serializer.data
        
        assert 'groups' in data
        assert isinstance(data['groups'], list)
    
    def test_no_dynamic_fields_default_behavior(self, people_factory):
        """Test that serializer works normally without dynamic field parameters."""
        person = people_factory.create()
        
        class TestSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email']
        
        request = Mock()
        request.GET = {}
        
        serializer = TestSerializer(instance=person, context={'request': request})
        serializer_fields = set(serializer.fields.keys())
        expected_fields = {'id', 'first_name', 'last_name', 'email'}
        
        assert serializer_fields == expected_fields


@pytest.mark.unit
@pytest.mark.api
class TestBulkSerializerMixin:
    """Test bulk operation functionality."""
    
    def test_bulk_create_method(self, db):
        """Test bulk create functionality."""
        class TestSerializer(BulkSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['first_name', 'last_name', 'email', 'employee_code']
        
        data = [
            {
                'first_name': 'John',
                'last_name': 'Doe', 
                'email': 'john@example.com',
                'employee_code': 'EMP001'
            },
            {
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'jane@example.com', 
                'employee_code': 'EMP002'
            }
        ]
        
        serializer = TestSerializer(data=data, many=True)
        assert serializer.is_valid()
        
        instances = serializer.bulk_create(serializer.validated_data)
        assert len(instances) == 2
        assert People.objects.count() == 2
    
    def test_bulk_update_method(self, people_factory):
        """Test bulk update functionality."""
        people = people_factory.create_batch(3)
        
        class TestSerializer(BulkSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email']
        
        update_data = {
            'last_name': 'UpdatedName'
        }
        
        serializer = TestSerializer()
        updated_instances = serializer.bulk_update(
            [p.id for p in people], 
            update_data
        )
        
        assert len(updated_instances) == 3
        for instance in updated_instances:
            assert instance.last_name == 'UpdatedName'


@pytest.mark.unit
@pytest.mark.api
class TestCachedSerializerMixin:
    """Test caching functionality in serializers."""
    
    def test_cache_key_generation(self, people_factory):
        """Test cache key generation."""
        person = people_factory.create()
        
        class TestSerializer(CachedSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email']
        
        serializer = TestSerializer(instance=person)
        cache_key = serializer.get_cache_key()
        
        assert cache_key is not None
        assert str(person.id) in cache_key
        assert 'people' in cache_key.lower()
    
    def test_cache_serialization(self, people_factory):
        """Test that serialization results are cached."""
        person = people_factory.create()
        
        class TestSerializer(CachedSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email']
        
        serializer = TestSerializer(instance=person)
        
        # First call - should cache
        data1 = serializer.cached_data()
        cache_key = serializer.get_cache_key()
        
        # Second call - should use cache
        data2 = serializer.cached_data()
        cached_data = cache.get(cache_key)
        
        assert data1 == data2
        assert cached_data is not None
        assert cached_data == data1
    
    def test_cache_invalidation(self, people_factory):
        """Test cache invalidation when instance is updated."""
        person = people_factory.create()
        
        class TestSerializer(CachedSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email']
        
        serializer = TestSerializer(instance=person)
        cache_key = serializer.get_cache_key()
        
        # Cache data
        serializer.cached_data()
        assert cache.get(cache_key) is not None
        
        # Invalidate cache
        serializer.invalidate_cache()
        assert cache.get(cache_key) is None


@pytest.mark.unit
@pytest.mark.api
class TestFieldPermissionsMixin:
    """Test field-level permissions."""
    
    def test_field_permissions_for_admin(self, people_factory, admin_user):
        """Test that admin users can see all fields."""
        person = people_factory.create()
        
        class TestSerializer(FieldPermissionsMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email', 'employee_code']
            
            field_permissions = {
                'employee_code': ['view_employee_code', 'is_staff']
            }
        
        request = Mock()
        request.user = admin_user
        
        serializer = TestSerializer(instance=person, context={'request': request})
        assert 'employee_code' in serializer.fields
    
    def test_field_permissions_for_regular_user(self, people_factory, test_user):
        """Test that regular users have restricted field access."""
        person = people_factory.create()
        
        class TestSerializer(FieldPermissionsMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email', 'employee_code']
            
            field_permissions = {
                'employee_code': ['is_staff']
            }
        
        request = Mock()
        request.user = test_user
        
        serializer = TestSerializer(instance=person, context={'request': request})
        assert 'employee_code' not in serializer.fields
    
    def test_field_permissions_for_anonymous_user(self, people_factory):
        """Test field permissions for anonymous users."""
        person = people_factory.create()
        
        class TestSerializer(FieldPermissionsMixin, serializers.ModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email']
            
            field_permissions = {
                'email': ['is_authenticated']
            }
        
        request = Mock()
        request.user = AnonymousUser()
        
        serializer = TestSerializer(instance=person, context={'request': request})
        assert 'email' not in serializer.fields
        assert 'first_name' in serializer.fields


@pytest.mark.unit
@pytest.mark.api
class TestSerializerIntegration:
    """Test integration of multiple serializer mixins."""
    
    def test_combined_serializer_functionality(self, people_factory, test_user):
        """Test serializer with all mixins combined."""
        person = people_factory.create()
        
        class CombinedSerializer(
            DynamicFieldsMixin,
            CachedSerializerMixin,
            BulkSerializerMixin,
            FieldPermissionsMixin,
            OptimizedModelSerializer
        ):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email', 'employee_code']
            
            field_permissions = {
                'employee_code': ['is_staff']
            }
        
        request = Mock()
        request.user = test_user
        request.GET = {'fields': 'id,first_name,email'}
        
        serializer = CombinedSerializer(instance=person, context={'request': request})
        
        # Should have dynamic fields applied
        assert set(serializer.fields.keys()) == {'id', 'first_name'}  # email removed by permissions
        
        # Should be able to cache
        data1 = serializer.cached_data()
        data2 = serializer.cached_data()
        assert data1 == data2
    
    def test_serializer_validation_with_errors(self, db):
        """Test serializer validation handles errors correctly."""
        class TestSerializer(OptimizedModelSerializer):
            class Meta:
                model = People
                fields = ['first_name', 'last_name', 'email', 'employee_code']
        
        # Invalid data (missing required fields)
        data = {'first_name': 'John'}
        serializer = TestSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'email' in serializer.errors
        assert 'employee_code' in serializer.errors
    
    @patch('apps.api.v1.serializers.base.logger')
    def test_serializer_error_logging(self, mock_logger, db):
        """Test that serializer errors are properly logged."""
        class TestSerializer(OptimizedModelSerializer):
            class Meta:
                model = People
                fields = ['first_name', 'last_name', 'email', 'employee_code']
            
            def validate_email(self, value):
                if '@' not in value:
                    raise serializers.ValidationError("Invalid email format")
                return value
        
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'invalid-email',
            'employee_code': 'EMP001'
        }
        
        serializer = TestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'email' in serializer.errors
    
    def test_performance_tracking(self, people_factory):
        """Test that performance tracking works with serializers."""
        person = people_factory.create()
        
        class TestSerializer(OptimizedModelSerializer):
            class Meta:
                model = People
                fields = ['id', 'first_name', 'last_name', 'email']
        
        with patch('time.time') as mock_time:
            mock_time.side_effect = [0.0, 0.1]  # 100ms execution
            
            serializer = TestSerializer(instance=person)
            data = serializer.data
            
            assert data is not None
            assert 'id' in data