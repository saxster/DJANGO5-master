"""
Cache management for Django ORM queries.
Implements intelligent caching for hierarchical data and frequently accessed queries.
"""

import json
import hashlib
from functools import wraps

from django.core.cache import cache


class CacheManager:
    """Manages caching for ORM queries with intelligent invalidation"""
    
    # Cache timeout configurations (in seconds)
    CACHE_TIMEOUTS = {
        'capability_tree': 3600,        # 1 hour - rarely changes
        'bt_hierarchy': 1800,           # 30 minutes - changes occasionally
        'ticket_escalation': 300,       # 5 minutes - changes frequently
        'report_data': 900,             # 15 minutes - computed data
        'user_permissions': 600,        # 10 minutes - security sensitive
        'asset_status': 600,            # 10 minutes - status updates
        'default': 300                  # 5 minutes default
    }
    
    # Cache key prefixes
    CACHE_PREFIXES = {
        'capability': 'cap',
        'bt': 'bt',
        'ticket': 'tkt',
        'report': 'rpt',
        'user': 'usr',
        'asset': 'ast'
    }
    
    @classmethod
    def get_cache_key(cls, prefix: str, *args, **kwargs) -> str:
        """Generate a unique cache key based on function arguments"""
        # Create a unique identifier from args and kwargs
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:8]
        
        return f"{prefix}:{key_hash}"
    
    @classmethod
    def get_timeout(cls, cache_type: str) -> int:
        """Get cache timeout for a specific cache type"""
        return cls.CACHE_TIMEOUTS.get(cache_type, cls.CACHE_TIMEOUTS['default'])
    
    @classmethod
    def invalidate_pattern(cls, pattern: str):
        """Invalidate all cache keys matching a pattern"""
        # Note: This requires cache backend that supports key pattern deletion
        # For Redis: cache._cache.delete_pattern(f"{pattern}*")
        # For other backends, you might need to track keys separately
        if hasattr(cache, '_cache') and hasattr(cache._cache, 'delete_pattern'):
            cache._cache.delete_pattern(f"{pattern}*")
    
    @classmethod
    def cache_query(cls, cache_type: str, prefix: Optional[str] = None):
        """Decorator for caching query results"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Determine cache prefix
                cache_prefix = prefix or cls.CACHE_PREFIXES.get(
                    cache_type.split('_')[0], 
                    'query'
                )
                
                # Generate cache key
                cache_key = cls.get_cache_key(cache_prefix, *args, **kwargs)
                
                # Try to get from cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute query
                result = func(*args, **kwargs)
                
                # Cache the result
                timeout = cls.get_timeout(cache_type)
                cache.set(cache_key, result, timeout)
                
                return result
            
            # Add cache invalidation method
            wrapper.invalidate_cache = lambda: cls.invalidate_pattern(
                prefix or cls.CACHE_PREFIXES.get(cache_type.split('_')[0], 'query')
            )
            
            return wrapper
        return decorator


class TreeCache:
    """Specialized cache for hierarchical tree structures"""
    
    def __init__(self, model: Model, parent_field: str = 'parent_id'):
        self.model = model
        self.parent_field = parent_field
        self.cache_prefix = f"tree:{model._meta.label_lower}"
    
    def get_or_build_tree(self, root_id: Optional[int] = None, 
                          filter_kwargs: Optional[Dict] = None) -> List[Dict]:
        """Get tree from cache or build it"""
        # Generate cache key
        cache_key = f"{self.cache_prefix}:{root_id}:{hash(str(filter_kwargs))}"
        
        # Try cache first
        cached_tree = cache.get(cache_key)
        if cached_tree is not None:
            return cached_tree
        
        # Build tree
        tree = self._build_tree(root_id, filter_kwargs)
        
        # Cache it
        cache.set(cache_key, tree, CacheManager.get_timeout('capability_tree'))
        
        return tree
    
    def _build_tree(self, root_id: Optional[int] = None, 
                    filter_kwargs: Optional[Dict] = None) -> List[Dict]:
        """Build tree structure from database"""
        # Get all nodes
        queryset = self.model.objects.all()
        if filter_kwargs:
            queryset = queryset.filter(**filter_kwargs)
        
        nodes = list(queryset)
        
        # Build lookup structures
        node_dict = {node.id: node for node in nodes}
        children_dict = {}
        
        for node in nodes:
            parent_id = getattr(node, self.parent_field)
            if parent_id:
                children_dict.setdefault(parent_id, []).append(node)
        
        # Build tree recursively
        def build_subtree(node_id: int, depth: int = 1) -> List[Dict]:
            results = []
            node = node_dict.get(node_id)
            if not node:
                return results
            
            # Add current node
            node_data = {
                'id': node.id,
                'depth': depth,
                'node': node,
                'children': []
            }
            
            # Add children
            for child in children_dict.get(node_id, []):
                node_data['children'].extend(
                    build_subtree(child.id, depth + 1)
                )
            
            results.append(node_data)
            return results
        
        # Build from root
        if root_id:
            return build_subtree(root_id)
        else:
            # Find all root nodes
            root_nodes = [n for n in nodes if not getattr(n, self.parent_field)]
            results = []
            for root in root_nodes:
                results.extend(build_subtree(root.id))
            return results
    
    def invalidate(self):
        """Invalidate all tree caches for this model"""
        CacheManager.invalidate_pattern(self.cache_prefix)


class QueryCache:
    """Advanced query caching with automatic invalidation"""
    
    def __init__(self):
        self.cache_dependencies = {}
    
    def cache_with_tags(self, tags: List[str], timeout: Optional[int] = None):
        """Cache with tags for grouped invalidation"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = CacheManager.get_cache_key('tagged', func.__name__, *args, **kwargs)
                
                # Try cache
                result = cache.get(cache_key)
                if result is not None:
                    return result
                
                # Execute query
                result = func(*args, **kwargs)
                
                # Cache with tags
                cache_timeout = timeout or CacheManager.get_timeout('default')
                cache.set(cache_key, result, cache_timeout)
                
                # Store tags for invalidation
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    tagged_keys = cache.get(tag_key, [])
                    tagged_keys.append(cache_key)
                    cache.set(tag_key, tagged_keys, 86400)  # 24 hours
                
                return result
            
            wrapper.invalidate_by_tags = lambda tags: self._invalidate_by_tags(tags)
            return wrapper
        return decorator
    
    def _invalidate_by_tags(self, tags: List[str]):
        """Invalidate all cached queries with specific tags"""
        for tag in tags:
            tag_key = f"tag:{tag}"
            tagged_keys = cache.get(tag_key, [])
            
            # Delete all tagged cache entries
            for key in tagged_keys:
                cache.delete(key)
            
            # Clear the tag list
            cache.delete(tag_key)


# Singleton instances
query_cache = QueryCache()


# Utility functions for common caching patterns
def cache_capability_tree():
    """Decorator specifically for capability tree queries"""
    return CacheManager.cache_query('capability_tree', 'cap')


def cache_bt_hierarchy():
    """Decorator specifically for BT hierarchy queries"""
    return CacheManager.cache_query('bt_hierarchy', 'bt')


def cache_report_data(timeout: int = 900):
    """Decorator for report data with custom timeout"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = CacheManager.get_cache_key('rpt', func.__name__, *args, **kwargs)
            
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        
        return wrapper
    return decorator


def invalidate_user_cache(user_id: int):
    """Invalidate all caches related to a specific user"""
    patterns = [
        f"usr:*{user_id}*",
        f"cap:*{user_id}*",
        f"rpt:*{user_id}*"
    ]
    
    for pattern in patterns:
        CacheManager.invalidate_pattern(pattern)


def invalidate_site_cache(site_id: int):
    """Invalidate all caches related to a specific site"""
    patterns = [
        f"bt:*{site_id}*",
        f"tkt:*{site_id}*",
        f"rpt:*{site_id}*",
        f"ast:*{site_id}*"
    ]
    
    for pattern in patterns:
        CacheManager.invalidate_pattern(pattern)


# Cache warming utilities
def warm_critical_caches():
    """Pre-populate critical caches during off-peak hours"""
    from apps.core.queries import QueryRepository
    
    # Warm capability trees
    QueryRepository.get_web_caps_for_client()
    QueryRepository.get_mob_caps_for_client()
    
    # Warm BT hierarchies for active clients
    from apps.onboarding.models import Bt
    active_clients = Bt.objects.filter(
        identifier__tacode='CLIENT',
        enable=True
    ).values_list('id', flat=True)[:10]  # Top 10 clients
    
    for client_id in active_clients:
        QueryRepository.get_childrens_of_bt(client_id)


# Cache statistics and monitoring
class CacheStats:
    """Monitor cache performance"""
    
    @staticmethod
    def get_hit_rate(cache_prefix: str) -> Dict[str, Any]:
        """Calculate cache hit rate for a prefix"""
        # This would need to be implemented based on your cache backend
        # Example for Redis:
        stats = {
            'hits': 0,
            'misses': 0,
            'hit_rate': 0.0,
            'avg_get_time': 0.0
        }
        
        # Implementation would depend on cache backend
        return stats
    
    @staticmethod
    def get_cache_size(cache_prefix: str) -> int:
        """Get total size of cached data for a prefix"""
        # Implementation depends on cache backend
        return 0
    
    @staticmethod
    def get_expired_keys(since: datetime) -> List[str]:
        """Get list of keys that expired since given time"""
        # Implementation depends on cache backend
        return []