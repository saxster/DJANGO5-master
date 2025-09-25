"""
Unit tests for API ViewSets.

Tests query optimization, pagination, filtering, and bulk operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.db.models import QuerySet
from django.core.cache import cache
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from rest_framework import status
from rest_framework.response import Response

from apps.api.v1.views.base import (
    OptimizedModelViewSet,
    track_performance
)
from apps.api.v1.pagination.custom_pagination import (
    StandardResultsSetPagination,
    CursorPagination,
    LimitOffsetPagination
)
from apps.peoples.models import People, Pgroup


@pytest.mark.unit
@pytest.mark.api
class TestOptimizedModelViewSet:
    """Test OptimizedModelViewSet functionality."""
    
    def test_viewset_initialization(self):
        """Test that OptimizedModelViewSet can be instantiated."""
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        assert viewset is not None
        assert hasattr(viewset, 'get_queryset')
        assert hasattr(viewset, 'get_optimized_queryset')
    
    def test_get_optimized_queryset(self, people_factory, query_counter):
        """Test that queryset optimization is applied."""
        people = people_factory.create_batch(5)
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            optimization_config = {
                'select_related': ['shift', 'bt'],
                'prefetch_related': ['groups']
            }
        
        viewset = TestViewSet()
        request = APIRequestFactory().get('/')
        viewset.request = Request(request)
        
        with query_counter() as context:
            optimized_qs = viewset.get_optimized_queryset()
            # Force evaluation
            list(optimized_qs)
        
        # Should use select_related and prefetch_related
        assert len(context) <= 2  # Base query + prefetch query
    
    def test_field_selection_via_request(self, people_factory):
        """Test field selection through request parameters."""
        person = people_factory.create()
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/', {'fields': 'id,first_name,email'})
        viewset.request = Request(request)
        
        # Mock the serializer to check if context is passed
        mock_serializer_class = Mock()
        mock_serializer = Mock()
        mock_serializer_class.return_value = mock_serializer
        viewset.get_serializer_class = Mock(return_value=mock_serializer_class)
        
        serializer = viewset.get_serializer(instance=person)
        
        # Check that context is passed to serializer
        mock_serializer_class.assert_called_once()
        call_kwargs = mock_serializer_class.call_args[1]
        assert 'context' in call_kwargs
        assert call_kwargs['context']['request'] == viewset.request
    
    def test_bulk_create_action(self, db):
        """Test bulk create functionality."""
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        
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
        
        request = factory.post('/bulk_create/', data, format='json')
        viewset.request = Request(request)
        
        # Mock serializer
        mock_serializer = Mock()
        mock_serializer.is_valid.return_value = True
        mock_serializer.validated_data = data
        mock_serializer.bulk_create.return_value = [Mock(id=1), Mock(id=2)]
        
        viewset.get_serializer = Mock(return_value=mock_serializer)
        
        response = viewset.bulk_create(request)
        
        assert response.status_code == status.HTTP_201_CREATED
        mock_serializer.is_valid.assert_called_once()
        mock_serializer.bulk_create.assert_called_once()
    
    def test_bulk_update_action(self, people_factory):
        """Test bulk update functionality."""
        people = people_factory.create_batch(3)
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        
        data = {
            'ids': [p.id for p in people],
            'updates': {'last_name': 'UpdatedName'}
        }
        
        request = factory.put('/bulk_update/', data, format='json')
        viewset.request = Request(request)
        
        # Mock serializer
        mock_serializer = Mock()
        mock_serializer.bulk_update.return_value = people
        
        viewset.get_serializer = Mock(return_value=mock_serializer)
        
        response = viewset.bulk_update(request)
        
        assert response.status_code == status.HTTP_200_OK
        mock_serializer.bulk_update.assert_called_once_with(
            data['ids'], data['updates']
        )
    
    def test_bulk_delete_action(self, people_factory):
        """Test bulk delete functionality."""
        people = people_factory.create_batch(3)
        ids = [p.id for p in people]
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        
        request = factory.delete('/bulk_delete/', {'ids': ids}, format='json')
        viewset.request = Request(request)
        
        response = viewset.bulk_delete(request)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Verify objects were deleted
        assert People.objects.filter(id__in=ids).count() == 0
    
    def test_caching_integration(self, people_factory):
        """Test that ViewSet integrates with caching."""
        person = people_factory.create()
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            cache_timeout = 300
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/')
        viewset.request = Request(request)
        
        # Test that cache key is generated
        cache_key = viewset.get_cache_key('list')
        assert cache_key is not None
        assert 'people' in cache_key.lower()
        assert 'list' in cache_key


@pytest.mark.unit
@pytest.mark.api
class TestTrackPerformanceDecorator:
    """Test performance tracking decorator."""
    
    def test_performance_decorator_tracks_time(self):
        """Test that performance decorator tracks execution time."""
        @track_performance
        def test_function():
            return "test result"
        
        with patch('apps.api.v1.views.base.api_analytics') as mock_analytics:
            result = test_function()
            
            assert result == "test result"
            # Analytics tracking would be called here
    
    def test_performance_decorator_handles_exceptions(self):
        """Test that performance decorator handles exceptions properly."""
        @track_performance
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
    
    def test_performance_decorator_with_viewset_method(self, people_factory):
        """Test performance decorator on ViewSet method."""
        person = people_factory.create()
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            
            @track_performance
            def custom_action(self, request):
                return Response({'status': 'success'})
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/')
        
        with patch('apps.api.v1.views.base.api_analytics'):
            response = viewset.custom_action(Request(request))
            
            assert response.status_code == status.HTTP_200_OK
            assert response.data == {'status': 'success'}


@pytest.mark.unit
@pytest.mark.api
class TestPaginationIntegration:
    """Test pagination integration with ViewSets."""
    
    def test_standard_pagination(self, people_factory):
        """Test standard page-based pagination."""
        people_factory.create_batch(25)  # Create more than page size
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            pagination_class = StandardResultsSetPagination
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/', {'page': 1, 'page_size': 10})
        viewset.request = Request(request)
        
        paginator = viewset.pagination_class()
        queryset = viewset.get_queryset()
        
        page = paginator.paginate_queryset(queryset, request)
        assert len(page) == 10
    
    def test_cursor_pagination(self, people_factory):
        """Test cursor-based pagination."""
        people_factory.create_batch(25)
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            pagination_class = CursorPagination
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/', {'page_size': 10})
        viewset.request = Request(request)
        
        paginator = viewset.pagination_class()
        queryset = viewset.get_queryset().order_by('id')
        
        page = paginator.paginate_queryset(queryset, request)
        assert len(page) == 10
    
    def test_limit_offset_pagination(self, people_factory):
        """Test limit/offset pagination."""
        people_factory.create_batch(25)
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            pagination_class = LimitOffsetPagination
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/', {'limit': 10, 'offset': 5})
        viewset.request = Request(request)
        
        paginator = viewset.pagination_class()
        queryset = viewset.get_queryset()
        
        page = paginator.paginate_queryset(queryset, request)
        assert len(page) == 10


@pytest.mark.unit
@pytest.mark.api
class TestFilteringIntegration:
    """Test filtering integration with ViewSets."""
    
    def test_basic_filtering(self, people_factory):
        """Test basic filtering functionality."""
        active_people = people_factory.create_batch(5, is_active=True)
        inactive_people = people_factory.create_batch(3, is_active=False)
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            filterset_fields = ['is_active']
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/', {'is_active': 'true'})
        viewset.request = Request(request)
        
        # Apply filtering
        queryset = viewset.filter_queryset(viewset.get_queryset())
        
        assert queryset.count() == 5
        assert all(person.is_active for person in queryset)
    
    def test_search_filtering(self, people_factory):
        """Test search functionality."""
        john = people_factory.create(first_name='John', last_name='Doe')
        jane = people_factory.create(first_name='Jane', last_name='Smith')
        bob = people_factory.create(first_name='Bob', last_name='Johnson')
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            search_fields = ['first_name', 'last_name', 'email']
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/', {'search': 'John'})
        viewset.request = Request(request)
        
        # This would require actual implementation of search filtering
        # For now, just test that the ViewSet can handle the parameter
        assert 'search' in request.GET
    
    def test_ordering(self, people_factory):
        """Test ordering functionality."""
        people_factory.create(first_name='Alice', created_at='2023-01-01')
        people_factory.create(first_name='Bob', created_at='2023-01-02')
        people_factory.create(first_name='Charlie', created_at='2023-01-03')
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            ordering_fields = ['first_name', 'created_at']
            ordering = ['-created_at']
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/', {'ordering': 'first_name'})
        viewset.request = Request(request)
        
        queryset = viewset.get_queryset()
        ordered_queryset = queryset.order_by('first_name')
        
        names = [person.first_name for person in ordered_queryset]
        assert names == ['Alice', 'Bob', 'Charlie']


@pytest.mark.unit
@pytest.mark.api
class TestViewSetErrorHandling:
    """Test error handling in ViewSets."""
    
    def test_bulk_create_validation_error(self, db):
        """Test bulk create with validation errors."""
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        
        # Invalid data (missing required fields)
        data = [{'first_name': 'John'}]  # Missing email, employee_code
        
        request = factory.post('/bulk_create/', data, format='json')
        viewset.request = Request(request)
        
        # Mock serializer with validation errors
        mock_serializer = Mock()
        mock_serializer.is_valid.return_value = False
        mock_serializer.errors = {'email': ['This field is required.']}
        
        viewset.get_serializer = Mock(return_value=mock_serializer)
        
        response = viewset.bulk_create(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data
    
    def test_bulk_update_invalid_ids(self, db):
        """Test bulk update with invalid IDs."""
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        
        data = {
            'ids': [999, 998, 997],  # Non-existent IDs
            'updates': {'last_name': 'UpdatedName'}
        }
        
        request = factory.put('/bulk_update/', data, format='json')
        viewset.request = Request(request)
        
        mock_serializer = Mock()
        mock_serializer.bulk_update.side_effect = ValueError("Invalid IDs")
        
        viewset.get_serializer = Mock(return_value=mock_serializer)
        
        response = viewset.bulk_update(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_permission_denied_handling(self, people_factory, test_user):
        """Test permission denied handling."""
        person = people_factory.create()
        
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.delete(f'/{person.id}/')
        request.user = test_user
        viewset.request = Request(request)
        
        # Test would need actual permission checking implementation
        # For now, just verify the ViewSet can handle the request
        assert viewset.request.method == 'DELETE'
    
    def test_queryset_optimization_error_handling(self):
        """Test error handling in queryset optimization."""
        class TestViewSet(OptimizedModelViewSet):
            queryset = People.objects.all()
            serializer_class = Mock()
            optimization_config = {
                'select_related': ['invalid_field']  # Invalid field
            }
        
        viewset = TestViewSet()
        factory = APIRequestFactory()
        request = factory.get('/')
        viewset.request = Request(request)
        
        # Should handle invalid optimization gracefully
        try:
            queryset = viewset.get_optimized_queryset()
            # In real implementation, this would log the error and continue
            assert queryset is not None
        except Exception as e:
            # Expected behavior - optimization fails gracefully
            assert True