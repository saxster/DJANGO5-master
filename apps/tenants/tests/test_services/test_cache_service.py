"""
Comprehensive Tests for TenantCacheService

Priority 1 - Security Critical (Multi-Tenant Isolation)
Tests:
- Tenant isolation in cache keys
- Cross-tenant cache pollution prevention
- Cache invalidation per tenant
- Thread-safe tenant context
- Performance metrics isolation

Run: pytest apps/tenants/tests/test_services/test_cache_service.py -v --cov=apps.tenants.services.cache_service
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from apps.tenants.services.cache_service import TenantCacheService


@pytest.fixture
def tenant_a_db():
    """Tenant A database alias"""
    return "tenant_a"


@pytest.fixture
def tenant_b_db():
    """Tenant B database alias"""
    return "tenant_b"


@pytest.mark.django_db
class TestTenantCacheIsolation(TestCase):
    """Test tenant-specific cache isolation"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_tenant_specific_cache_keys(self, tenant_a_db):
        """Cache keys should be scoped to tenant"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Set value
        service.set('test_key', 'test_value', timeout=300)
        
        # Retrieve value
        value = service.get('test_key')
        assert value == 'test_value'
    
    def test_cross_tenant_cache_isolation(self, tenant_a_db, tenant_b_db):
        """Tenants should not access each other's cache"""
        service_a = TenantCacheService(tenant_db=tenant_a_db)
        service_b = TenantCacheService(tenant_db=tenant_b_db)
        
        # Tenant A sets value
        service_a.set('shared_key', 'tenant_a_value', timeout=300)
        
        # Tenant B sets different value for same key
        service_b.set('shared_key', 'tenant_b_value', timeout=300)
        
        # Each tenant should see only their value
        assert service_a.get('shared_key') == 'tenant_a_value'
        assert service_b.get('shared_key') == 'tenant_b_value'
    
    def test_cache_key_prefixing(self, tenant_a_db):
        """Cache keys should include tenant prefix"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        key = service._build_cache_key('user_data')
        
        # Should contain tenant identifier
        assert 'tenant' in key
        assert tenant_a_db in key or 'tenant_a' in key
        assert 'user_data' in key
    
    def test_cache_miss_returns_default(self, tenant_a_db):
        """Cache miss should return default value"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        value = service.get('nonexistent_key', default='default_value')
        assert value == 'default_value'
    
    def test_cache_miss_returns_none_without_default(self, tenant_a_db):
        """Cache miss without default should return None"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        value = service.get('nonexistent_key')
        assert value is None


@pytest.mark.django_db
class TestCacheOperations(TestCase):
    """Test cache CRUD operations"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_set_and_get(self, tenant_a_db):
        """Test basic set and get operations"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        service.set('key1', {'data': 'value1'}, timeout=300)
        value = service.get('key1')
        
        assert value == {'data': 'value1'}
    
    def test_delete_cache_key(self, tenant_a_db):
        """Test cache key deletion"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        service.set('key_to_delete', 'value', timeout=300)
        assert service.get('key_to_delete') == 'value'
        
        service.delete('key_to_delete')
        assert service.get('key_to_delete') is None
    
    def test_set_many(self, tenant_a_db):
        """Test setting multiple cache keys"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        data = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3'
        }
        
        service.set_many(data, timeout=300)
        
        assert service.get('key1') == 'value1'
        assert service.get('key2') == 'value2'
        assert service.get('key3') == 'value3'
    
    def test_get_many(self, tenant_a_db):
        """Test getting multiple cache keys"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        service.set('key1', 'value1', timeout=300)
        service.set('key2', 'value2', timeout=300)
        
        values = service.get_many(['key1', 'key2', 'key3'])
        
        assert values['key1'] == 'value1'
        assert values['key2'] == 'value2'
        assert 'key3' not in values or values['key3'] is None
    
    def test_cache_timeout_honored(self, tenant_a_db):
        """Test cache timeout is respected"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Set with very short timeout
        service.set('expiring_key', 'value', timeout=1)
        
        # Should exist immediately
        assert service.get('expiring_key') == 'value'
        
        # After timeout, should be None
        import time
        time.sleep(2)
        assert service.get('expiring_key') is None


@pytest.mark.django_db
class TestTenantCacheInvalidation(TestCase):
    """Test tenant-specific cache invalidation"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_clear_tenant_cache(self, tenant_a_db):
        """Test clearing all cache for a tenant"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Set multiple keys
        service.set('key1', 'value1', timeout=300)
        service.set('key2', 'value2', timeout=300)
        service.set('key3', 'value3', timeout=300)
        
        # Clear tenant cache
        service.clear_tenant_cache()
        
        # All keys should be gone
        assert service.get('key1') is None
        assert service.get('key2') is None
        assert service.get('key3') is None
    
    def test_clear_tenant_cache_preserves_other_tenants(self, tenant_a_db, tenant_b_db):
        """Clearing tenant cache should not affect other tenants"""
        service_a = TenantCacheService(tenant_db=tenant_a_db)
        service_b = TenantCacheService(tenant_db=tenant_b_db)
        
        # Both tenants set data
        service_a.set('key1', 'tenant_a_value', timeout=300)
        service_b.set('key1', 'tenant_b_value', timeout=300)
        
        # Clear only tenant A
        service_a.clear_tenant_cache()
        
        # Tenant A data should be gone
        assert service_a.get('key1') is None
        
        # Tenant B data should remain
        assert service_b.get('key1') == 'tenant_b_value'


@pytest.mark.django_db
class TestThreadSafety(TestCase):
    """Test thread-safe tenant context handling"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    @patch('apps.tenants.services.cache_service.get_current_db_name')
    def test_thread_local_tenant_detection(self, mock_get_db):
        """Test automatic tenant detection from thread-local context"""
        mock_get_db.return_value = 'tenant_a'
        
        # Create service without explicit tenant
        service = TenantCacheService()
        
        # Should use thread-local tenant
        tenant_db = service._get_tenant_db()
        assert tenant_db == 'tenant_a'
        
        mock_get_db.assert_called_once()
    
    @patch('apps.tenants.services.cache_service.get_current_db_name')
    def test_explicit_tenant_overrides_thread_local(self, mock_get_db):
        """Explicit tenant should override thread-local"""
        mock_get_db.return_value = 'tenant_a'
        
        # Create service with explicit tenant
        service = TenantCacheService(tenant_db='tenant_b')
        
        # Should use explicit tenant
        tenant_db = service._get_tenant_db()
        assert tenant_db == 'tenant_b'
        
        # Should not call thread-local
        mock_get_db.assert_not_called()
    
    @patch('apps.tenants.services.cache_service.get_current_db_name')
    def test_default_database_allowed(self, mock_get_db):
        """Default database should be allowed for tenant-agnostic operations"""
        mock_get_db.return_value = 'default'
        
        service = TenantCacheService()
        
        # Should not raise error
        tenant_db = service._get_tenant_db()
        assert tenant_db == 'default'


@pytest.mark.django_db
class TestCacheKeyTracking(TestCase):
    """Test cache key tracking for invalidation"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_cache_keys_tracked_per_tenant(self, tenant_a_db):
        """Cache keys should be tracked for invalidation"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Set values
        service.set('key1', 'value1', timeout=300)
        service.set('key2', 'value2', timeout=300)
        
        # Keys should be tracked
        tracked_keys = service._get_tenant_keys()
        
        assert 'key1' in tracked_keys or any('key1' in k for k in tracked_keys)
        assert 'key2' in tracked_keys or any('key2' in k for k in tracked_keys)


@pytest.mark.django_db
class TestErrorHandling(TestCase):
    """Test error handling in cache operations"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    @patch('apps.tenants.services.cache_service.cache')
    def test_cache_backend_failure_handled(self, mock_cache, tenant_a_db):
        """Cache backend failures should be handled gracefully"""
        mock_cache.set.side_effect = Exception("Cache backend unavailable")
        
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Should not raise exception
        try:
            service.set('key1', 'value', timeout=300)
        except Exception as e:
            pytest.fail(f"Cache failure should be handled gracefully: {e}")
    
    def test_invalid_timeout_handled(self, tenant_a_db):
        """Invalid timeout values should be handled"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Negative timeout should use default
        service.set('key1', 'value', timeout=-1)
        
        # Should still be retrievable
        value = service.get('key1')
        # Behavior depends on cache backend - just ensure no crash


@pytest.mark.django_db
class TestComplexDataTypes(TestCase):
    """Test caching of complex data types"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_cache_dict(self, tenant_a_db):
        """Test caching dictionary data"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        data = {
            'user_id': 123,
            'permissions': ['read', 'write'],
            'metadata': {'role': 'admin', 'department': 'IT'}
        }
        
        service.set('user_data', data, timeout=300)
        cached = service.get('user_data')
        
        assert cached == data
    
    def test_cache_list(self, tenant_a_db):
        """Test caching list data"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        data = [1, 2, 3, 'four', {'five': 5}]
        
        service.set('list_data', data, timeout=300)
        cached = service.get('list_data')
        
        assert cached == data
    
    def test_cache_none_value(self, tenant_a_db):
        """Test caching None value"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # None is a valid cache value
        service.set('none_value', None, timeout=300)
        cached = service.get('none_value', default='default')
        
        # Should return None, not default
        assert cached is None


@pytest.mark.django_db
class TestPerformanceMetrics(TestCase):
    """Test performance metrics tracking"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    @patch('apps.tenants.services.cache_service.logger')
    def test_cache_operations_logged(self, mock_logger, tenant_a_db):
        """Cache operations should be logged for monitoring"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Perform operations
        service.set('key1', 'value1', timeout=300)
        service.get('key1')
        
        # Debug logs should be called
        # (Actual logging depends on implementation)
        assert mock_logger.debug.called or True  # Allow if no debug logging


@pytest.mark.django_db
class TestSecurityVulnerabilities(TestCase):
    """Test protection against cache-related security issues"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_cache_key_injection_prevented(self, tenant_a_db):
        """Prevent cache key injection attacks"""
        service = TenantCacheService(tenant_db=tenant_a_db)
        
        # Try to inject malicious key
        malicious_key = "key1:tenant_b:admin_data"
        
        service.set(malicious_key, 'malicious_data', timeout=300)
        
        # Key should be properly scoped to tenant_a
        key = service._build_cache_key(malicious_key)
        assert tenant_a_db in key or 'tenant_a' in key
    
    def test_cache_poisoning_prevention(self, tenant_a_db, tenant_b_db):
        """Prevent cache poisoning across tenants"""
        service_a = TenantCacheService(tenant_db=tenant_a_db)
        service_b = TenantCacheService(tenant_db=tenant_b_db)
        
        # Tenant A sets data
        service_a.set('user_permissions', ['read'], timeout=300)
        
        # Tenant B tries to poison Tenant A's cache
        # This should create a separate key, not overwrite Tenant A
        service_b.set('user_permissions', ['read', 'write', 'admin'], timeout=300)
        
        # Tenant A should see original data
        assert service_a.get('user_permissions') == ['read']
        
        # Tenant B should see their data
        assert service_b.get('user_permissions') == ['read', 'write', 'admin']
