"""
Multi-Level Caching Strategy for Performance Optimization

This module implements a comprehensive caching strategy with:
1. Database query result caching
2. Template fragment caching
3. API response caching
4. Static data caching
5. Intelligent cache warming
6. Cache invalidation patterns

Performance targets:
- 90%+ cache hit rate for frequently accessed data
- <10ms cache retrieval time
- Intelligent cache warming during off-peak hours
- Automatic cache invalidation on data changes
"""

import json
import hashlib
import logging
from functools import wraps
from typing import Any, Dict, List, Optional, Union, Callable, Type
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db.models import Model, QuerySet
from django.http import HttpResponse, JsonResponse
from django.template import Context, Template
from django.utils import timezone
from django.conf import settings
from django.dispatch import receiver

logger = logging.getLogger('cache_strategies')


class CacheKeyGenerator:
    """Generates consistent cache keys across the application"""
    
    @staticmethod
    def generate_key(*args, prefix: str = '', version: int = 1, **kwargs) -> str:
        """Generate a consistent cache key from arguments"""
        # Combine all arguments into a string
        key_data = {
            'args': [str(arg) for arg in args],
            'kwargs': {k: str(v) for k, v in sorted(kwargs.items())},
            'version': version
        }
        
        # Create hash for consistent key length
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:12]
        
        # Construct final key
        if prefix:
            return f"{prefix}:{key_hash}"
        else:
            return f"cache:{key_hash}"
    
    @staticmethod
    def generate_model_key(model: Union[Model, Type[Model]], instance_id: Optional[int] = None, 
                          action: str = '', version: int = 1) -> str:
        """Generate cache key for model instances"""
        model_name = model._meta.label_lower if hasattr(model, '_meta') else model.__name__.lower()
        
        if instance_id:
            return CacheKeyGenerator.generate_key(
                model_name, instance_id, action,
                prefix=f"model:{model_name}",
                version=version
            )
        else:
            return CacheKeyGenerator.generate_key(
                model_name, action,
                prefix=f"model:{model_name}",
                version=version
            )
    
    @staticmethod
    def generate_query_key(queryset: QuerySet, filters: Dict = None, version: int = 1) -> str:
        """Generate cache key for querysets"""
        model_name = queryset.model._meta.label_lower
        query_hash = hashlib.md5(str(queryset.query).encode()).hexdigest()[:8]
        
        return CacheKeyGenerator.generate_key(
            model_name, query_hash,
            filters=filters or {},
            prefix=f"query:{model_name}",
            version=version
        )


class MultiLevelCache:
    """Implements multi-level caching strategy"""
    
    # Cache level priorities (higher = more frequently accessed)
    CACHE_LEVELS = {
        'hot': {
            'timeout': 300,     # 5 minutes
            'description': 'Frequently accessed data (user sessions, active jobs)'
        },
        'warm': {
            'timeout': 1800,    # 30 minutes
            'description': 'Moderately accessed data (asset lists, reports)'
        },
        'cold': {
            'timeout': 7200,    # 2 hours
            'description': 'Static/reference data (capabilities, configurations)'
        },
        'frozen': {
            'timeout': 86400,   # 24 hours
            'description': 'Rarely changing data (system settings, constants)'
        }
    }
    
    def __init__(self, level: str = 'warm'):
        self.level = level
        self.timeout = self.CACHE_LEVELS[level]['timeout']
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get from cache with level-specific logic"""
        try:
            value = cache.get(key, default)
            if value is not default:
                # Update access time for hot cache items
                if self.level == 'hot':
                    self._update_access_time(key)
            return value
        except (ConnectionError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set cache with level-specific timeout"""
        try:
            cache_timeout = timeout or self.timeout
            cache.set(key, value, cache_timeout)
            
            # Store metadata for cache warming
            self._store_cache_metadata(key, cache_timeout)
            return True
        except (ConnectionError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete from cache"""
        try:
            cache.delete(key)
            self._remove_cache_metadata(key)
            return True
        except (ConnectionError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    def get_or_set(self, key: str, callable_obj: Callable, timeout: Optional[int] = None) -> Any:
        """Get from cache or set if not exists"""
        value = self.get(key)
        if value is None:
            value = callable_obj()
            self.set(key, value, timeout)
        return value
    
    def _update_access_time(self, key: str):
        """Update access time for hot cache analytics"""
        access_key = f"access:{key}"
        cache.set(access_key, timezone.now().timestamp(), 3600)
    
    def _store_cache_metadata(self, key: str, timeout: int):
        """Store metadata for cache management"""
        metadata = {
            'created_at': timezone.now().timestamp(),
            'expires_at': timezone.now().timestamp() + timeout,
            'level': self.level,
            'timeout': timeout
        }
        meta_key = f"meta:{key}"
        cache.set(meta_key, metadata, timeout + 3600)  # Store metadata longer
    
    def _remove_cache_metadata(self, key: str):
        """Remove cache metadata"""
        meta_key = f"meta:{key}"
        cache.delete(meta_key)


class SmartQueryCache:
    """Intelligent query result caching with automatic invalidation"""
    
    def __init__(self, level: str = 'warm'):
        self.cache_level = MultiLevelCache(level)
        self.dependency_tracker = CacheDependencyTracker()
    
    def cache_queryset(self, timeout: Optional[int] = None, 
                      dependencies: Optional[List[str]] = None,
                      version: int = 1):
        """Decorator for caching queryset results"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = CacheKeyGenerator.generate_key(
                    func.__name__, *args, 
                    prefix='query_result',
                    version=version,
                    **kwargs
                )
                
                # Try cache first
                cached_result = self.cache_level.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute query
                result = func(*args, **kwargs)
                
                # Convert queryset to list for caching
                if isinstance(result, QuerySet):
                    result = list(result)
                
                # Cache result
                self.cache_level.set(cache_key, result, timeout)
                
                # Track dependencies for invalidation
                if dependencies:
                    self.dependency_tracker.add_dependencies(cache_key, dependencies)
                
                return result
            
            wrapper.invalidate_cache = lambda: self._invalidate_function_cache(func.__name__, version)
            return wrapper
        return decorator
    
    def cache_model_method(self, timeout: Optional[int] = None,
                          dependencies: Optional[List[str]] = None):
        """Decorator for caching model methods"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(instance, *args, **kwargs):
                # Generate cache key based on model instance
                cache_key = CacheKeyGenerator.generate_model_key(
                    instance.__class__, instance.pk, func.__name__
                )
                
                # Try cache
                cached_result = self.cache_level.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute method
                result = func(instance, *args, **kwargs)
                
                # Cache result
                self.cache_level.set(cache_key, result, timeout)
                
                # Track dependencies
                if dependencies:
                    self.dependency_tracker.add_dependencies(cache_key, dependencies)
                else:
                    # Auto-track model as dependency
                    model_dep = f"{instance._meta.label_lower}:{instance.pk}"
                    self.dependency_tracker.add_dependencies(cache_key, [model_dep])
                
                return result
            
            return wrapper
        return decorator
    
    def _invalidate_function_cache(self, func_name: str, version: int):
        """Invalidate all cache entries for a function"""
        pattern = f"query_result:{func_name}:*:v{version}"
        self._delete_pattern(pattern)
    
    def _delete_pattern(self, pattern: str):
        """Delete cache keys matching pattern (Redis-specific)"""
        try:
            if hasattr(cache._cache, 'delete_pattern'):
                cache._cache.delete_pattern(pattern)
            else:
                # Fallback for non-Redis backends
                logger.warning(f"Pattern deletion not supported for cache backend")
        except (ConnectionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error deleting cache pattern {pattern}: {e}")


class CacheDependencyTracker:
    """Tracks cache dependencies for intelligent invalidation"""
    
    def __init__(self):
        self.dependency_cache = MultiLevelCache('frozen')
    
    def add_dependencies(self, cache_key: str, dependencies: List[str]):
        """Add dependencies for a cache key"""
        dep_key = f"deps:{cache_key}"
        self.dependency_cache.set(dep_key, dependencies, 86400)  # 24 hours
        
        # Reverse mapping: dependency -> cache keys
        for dep in dependencies:
            reverse_key = f"rev_deps:{dep}"
            existing_keys = self.dependency_cache.get(reverse_key, [])
            if cache_key not in existing_keys:
                existing_keys.append(cache_key)
                self.dependency_cache.set(reverse_key, existing_keys, 86400)
    
    def get_dependent_keys(self, dependency: str) -> List[str]:
        """Get all cache keys dependent on a specific dependency"""
        reverse_key = f"rev_deps:{dependency}"
        return self.dependency_cache.get(reverse_key, [])
    
    def invalidate_dependency(self, dependency: str):
        """Invalidate all caches dependent on a specific dependency"""
        dependent_keys = self.get_dependent_keys(dependency)
        cache_manager = MultiLevelCache()
        
        for key in dependent_keys:
            cache_manager.delete(key)
            logger.info(f"Invalidated cache key {key} due to dependency {dependency}")
        
        # Clean up reverse mapping
        reverse_key = f"rev_deps:{dependency}"
        self.dependency_cache.delete(reverse_key)


class TemplateFragmentCache:
    """Advanced template fragment caching"""
    
    def __init__(self):
        self.cache_level = MultiLevelCache('warm')
    
    def cache_template_fragment(self, fragment_name: str, *vary_on, timeout: int = 1800):
        """Cache template fragments with versioning"""
        def render_fragment(template_string: str, context: Dict) -> str:
            cache_key = make_template_fragment_key(fragment_name, vary_on)
            
            cached_content = self.cache_level.get(cache_key)
            if cached_content is not None:
                return cached_content
            
            # Render template
            template = Template(template_string)
            rendered = template.render(Context(context))
            
            # Cache rendered content
            self.cache_level.set(cache_key, rendered, timeout)
            
            return rendered
        
        return render_fragment
    
    def invalidate_template_fragments(self, fragment_name: str):
        """Invalidate all variations of a template fragment"""
        pattern = f"template.cache.{fragment_name}.*"
        
        try:
            # Try Redis-specific pattern deletion first
            if hasattr(cache._cache, 'delete_pattern'):
                cache._cache.delete_pattern(pattern)
                logger.info(f"Invalidated template fragments matching pattern: {pattern}")
            else:
                # Fallback: track fragment keys manually
                tracking_key = f"fragment_keys:{fragment_name}"
                tracked_keys = cache.get(tracking_key, [])
                
                invalidated_count = 0
                for key in tracked_keys:
                    if cache.delete(key):
                        invalidated_count += 1
                
                # Clear the tracking list
                cache.delete(tracking_key)
                
                if invalidated_count > 0:
                    logger.info(f"Invalidated {invalidated_count} template fragments for {fragment_name}")
                else:
                    logger.warning(f"No template fragments found to invalidate for {fragment_name}")
        except (ConnectionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Could not invalidate template fragments for {fragment_name}: {e}")


class APIResponseCache:
    """Cache API responses with intelligent invalidation"""
    
    def __init__(self):
        self.cache_level = MultiLevelCache('hot')
    
    def cache_api_response(self, timeout: int = 300, 
                          key_func: Optional[Callable] = None,
                          condition: Optional[Callable] = None):
        """Decorator for caching API responses"""
        def decorator(view_func: Callable) -> Callable:
            @wraps(view_func)
            def wrapper(request, *args, **kwargs):
                # Check condition if provided
                if condition and not condition(request, *args, **kwargs):
                    return view_func(request, *args, **kwargs)
                
                # Generate cache key
                if key_func:
                    cache_key = key_func(request, *args, **kwargs)
                else:
                    cache_key = CacheKeyGenerator.generate_key(
                        view_func.__name__, 
                        request.method,
                        request.GET.urlencode(),
                        prefix='api_response',
                        **kwargs
                    )
                
                # Try cache
                cached_response = self.cache_level.get(cache_key)
                if cached_response is not None:
                    return self._deserialize_response(cached_response)
                
                # Execute view
                response = view_func(request, *args, **kwargs)
                
                # Cache successful responses
                if isinstance(response, (HttpResponse, JsonResponse)) and response.status_code == 200:
                    serialized_response = self._serialize_response(response)
                    self.cache_level.set(cache_key, serialized_response, timeout)
                
                return response
            
            return wrapper
        return decorator
    
    def _serialize_response(self, response: HttpResponse) -> Dict:
        """Serialize HTTP response for caching"""
        return {
            'content': response.content.decode('utf-8') if response.content else '',
            'status_code': response.status_code,
            'headers': dict(response.items()),
            'content_type': response.get('Content-Type', 'text/html')
        }
    
    def _deserialize_response(self, cached_data: Dict) -> HttpResponse:
        """Deserialize cached response data"""
        response = HttpResponse(
            content=cached_data['content'],
            status=cached_data['status_code'],
            content_type=cached_data['content_type']
        )
        
        # Restore headers
        for key, value in cached_data.get('headers', {}).items():
            response[key] = value
        
        # Add cache hit indicator
        response['X-Cache-Hit'] = 'true'
        
        return response


class CacheWarmer:
    """Warms critical caches during off-peak hours"""
    
    def __init__(self):
        self.cache_level = MultiLevelCache('warm')
        self.warming_stats = {
            'last_run': None,
            'items_warmed': 0,
            'errors': 0
        }
    
    def warm_critical_caches(self):
        """Warm up critical application caches"""
        logger.info("Starting cache warming process...")
        start_time = timezone.now()
        
        warming_tasks = [
            self._warm_user_permissions,
            self._warm_asset_hierarchies,
            self._warm_capability_trees,
            self._warm_frequent_reports,
            self._warm_static_data
        ]
        
        for task in warming_tasks:
            try:
                items_warmed = task()
                self.warming_stats['items_warmed'] += items_warmed
                logger.info(f"Warmed {items_warmed} items with {task.__name__}")
            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                self.warming_stats['errors'] += 1
                logger.error(f"Error in {task.__name__}: {e}")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        self.warming_stats['last_run'] = end_time
        logger.info(f"Cache warming completed in {duration:.2f}s. "
                   f"Items warmed: {self.warming_stats['items_warmed']}, "
                   f"Errors: {self.warming_stats['errors']}")
    
    def _warm_user_permissions(self) -> int:
        """Warm user permission caches"""
        from apps.peoples.models import People
        
        # Get active users from the last week
        recent_threshold = timezone.now() - timedelta(days=7)
        active_users = People.objects.filter(
            last_login__gte=recent_threshold
        ).values_list('id', flat=True)[:100]  # Limit to prevent overload
        
        warmed = 0
        for user_id in active_users:
            try:
                # Warm permission caches with real user data
                cache_key = f"user_permissions:{user_id}"
                if not self.cache_level.get(cache_key):
                    try:
                        # Load actual user permissions
                        from apps.peoples.models import People
                        user = People.objects.select_related('bu', 'client').filter(id=user_id).first()
                        if user:
                            permissions = {
                                'bu_id': user.bu_id,
                                'client_id': user.client_id if user.client else None,
                                'is_superuser': getattr(user, 'is_superuser', False),
                                'is_staff': getattr(user, 'is_staff', False),
                                'groups': list(user.pgbelonging_set.filter(
                                    pgroup_id__gt=0
                                ).values_list('pgroup_id', flat=True)) if hasattr(user, 'pgbelonging_set') else []
                            }
                            self.cache_level.set(cache_key, permissions, 3600)
                            warmed += 1
                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as perm_error:
                        logger.warning(f"Error loading permissions for user {user_id}: {perm_error}")
            except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
                logger.warning(f"Error warming permissions for user {user_id}: {e}")
        
        return warmed
    
    def _warm_asset_hierarchies(self) -> int:
        """Warm asset hierarchy caches"""
        from apps.client_onboarding.models import Bt
        
        # Get active business units
        active_bus = Bt.objects.filter(
            enable=True,
            identifier__tacode='BUSINESSUNIT'
        ).values_list('id', flat=True)[:20]
        
        warmed = 0
        for bu_id in active_bus:
            try:
                cache_key = f"asset_hierarchy:{bu_id}"
                if not self.cache_level.get(cache_key):
                    # Load actual asset hierarchy
                    try:
                        from apps.activity.models.asset_model import Asset
                        assets = list(
                            Asset.objects.filter(
                                bu_id=bu_id,
                                enable=True
                            ).select_related('parent').only(
                                'id', 'parent_id', 'assetcode', 'assetname', 
                                'iscritical', 'runningstatus'
                            ).values(
                                'id', 'parent_id', 'assetcode', 'assetname', 
                                'iscritical', 'runningstatus'
                            )
                        )
                        
                        # Build simple hierarchy structure
                        hierarchy = self._build_asset_tree(assets)
                        self.cache_level.set(cache_key, hierarchy, 3600)
                        warmed += 1
                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as asset_error:
                        logger.warning(f"Error loading asset hierarchy for BU {bu_id}: {asset_error}")
            except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
                logger.warning(f"Error warming asset hierarchy for BU {bu_id}: {e}")
        
        return warmed
    
    def _warm_capability_trees(self) -> int:
        """Warm capability tree caches"""
        from apps.peoples.models import Capability
        
        try:
            cache_key = "capability_tree:all"
            if not self.cache_level.get(cache_key):
                # Load capability tree
                capabilities = list(Capability.objects.all().values('id', 'capname', 'parent_id'))
                self.cache_level.set(cache_key, capabilities, 7200)
                return len(capabilities)
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Error warming capability tree: {e}")
        
        return 0
    
    def _warm_frequent_reports(self) -> int:
        """Warm frequently accessed report caches"""
        warmed = 0
        
        try:
            # Warm dashboard metrics cache
            cache_key = "dashboard_metrics:all"
            if not self.cache_level.get(cache_key):
                from apps.activity.models.job_model import Jobneed
                from apps.activity.models.asset_model import Asset
                
                metrics = {
                    'total_jobs': Jobneed.objects.filter(enable=True).count(),
                    'completed_jobs': Jobneed.objects.filter(
                        jobstatus='COMPLETED'
                    ).count(),
                    'pending_jobs': Jobneed.objects.filter(
                        jobstatus__in=['PENDING', 'ASSIGNED']
                    ).count(),
                    'active_assets': Asset.objects.filter(enable=True).count(),
                    'critical_assets': Asset.objects.filter(
                        enable=True, iscritical=True
                    ).count()
                }
                self.cache_level.set(cache_key, metrics, 1800)  # 30 minutes
                warmed += 1
                
            # Warm recent activity summary
            cache_key = "recent_activity:summary"
            if not self.cache_level.get(cache_key):
                from django.utils import timezone
                from datetime import timedelta
                
                recent_threshold = timezone.now() - timedelta(hours=24)
                activity = {
                    'recent_jobs': Jobneed.objects.filter(
                        cdtz__gte=recent_threshold
                    ).count(),
                    'completed_today': Jobneed.objects.filter(
                        endtime__gte=recent_threshold,
                        jobstatus='COMPLETED'
                    ).count(),
                    'overdue_jobs': Jobneed.objects.filter(
                        expirydatetime__lt=timezone.now(),
                        jobstatus__in=['PENDING', 'ASSIGNED']
                    ).count()
                }
                self.cache_level.set(cache_key, activity, 900)  # 15 minutes
                warmed += 1
                
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Error warming report caches: {e}")
        
        return warmed
    
    def _warm_static_data(self) -> int:
        """Warm static/reference data caches"""
        warmed = 0
        
        try:
            # Warm type assist lookup caches
            from apps.core_onboarding.models import TypeAssist
            
            important_categories = ['JOBSTATUS', 'PRIORITY', 'ASSET_TYPE', 'FREQUENCY', 'SCANTYPE']
            for category in important_categories:
                cache_key = f"typeassist:{category}"
                if not self.cache_level.get(cache_key):
                    types = list(
                        TypeAssist.objects.filter(
                            tacode=category,
                            enable=True
                        ).values('id', 'taname', 'tacode', 'tadesc')
                    )
                    if types:
                        self.cache_level.set(cache_key, types, 3600)  # 1 hour
                        warmed += 1
            
            # Warm system configuration cache
            cache_key = "system_config:all"
            if not self.cache_level.get(cache_key):
                config = {
                    'default_timezone': 'UTC',
                    'cache_timeout_default': 300,
                    'max_file_upload_size': getattr(settings, 'DATA_UPLOAD_MAX_MEMORY_SIZE', 2621440),
                    'static_url': getattr(settings, 'STATIC_URL', '/static/'),
                    'media_url': getattr(settings, 'MEDIA_URL', '/media/')
                }
                self.cache_level.set(cache_key, config, 86400)  # 24 hours
                warmed += 1
                
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Error warming static data caches: {e}")
        
        return warmed
    
    def _build_asset_tree(self, assets: List[Dict]) -> List[Dict]:
        """Build simple asset tree structure from flat list"""
        if not assets:
            return []
        
        # Create lookup dictionaries
        asset_dict = {asset['id']: asset for asset in assets}
        children_dict = {}
        
        # Group children by parent
        for asset in assets:
            parent_id = asset.get('parent_id')
            if parent_id:
                if parent_id not in children_dict:
                    children_dict[parent_id] = []
                children_dict[parent_id].append(asset)
        
        # Build tree (just return flat structure with parent references)
        # This is a simple implementation - could be enhanced for full tree
        tree = []
        for asset in assets:
            if not asset.get('parent_id'):  # Root assets
                asset_node = asset.copy()
                asset_node['children'] = children_dict.get(asset['id'], [])
                tree.append(asset_node)
        
        return tree


# Signal-based cache invalidation
class CacheInvalidationSignals:
    """Handles automatic cache invalidation based on model signals"""
    
    def __init__(self):
        self.dependency_tracker = CacheDependencyTracker()
    
    def register_model_invalidation(self, model_class: Type[Model], 
                                   dependencies: Optional[List[str]] = None):
        """Register automatic cache invalidation for a model"""
        
        @receiver(post_save, sender=model_class)
        def invalidate_on_save(sender, instance, **kwargs):
            self._invalidate_model_caches(instance, dependencies)
        
        @receiver(post_delete, sender=model_class)
        def invalidate_on_delete(sender, instance, **kwargs):
            self._invalidate_model_caches(instance, dependencies)
    
    def _invalidate_model_caches(self, instance: Model, dependencies: Optional[List[str]]):
        """Invalidate caches for a model instance"""
        # Model-specific invalidation
        model_dep = f"{instance._meta.label_lower}:{instance.pk}"
        self.dependency_tracker.invalidate_dependency(model_dep)
        
        # Custom dependencies
        if dependencies:
            for dep in dependencies:
                self.dependency_tracker.invalidate_dependency(dep)
        
        logger.info(f"Invalidated caches for {instance._meta.label_lower}:{instance.pk}")


# Initialize global cache instances
query_cache = SmartQueryCache()
template_cache = TemplateFragmentCache()
api_cache = APIResponseCache()
cache_warmer = CacheWarmer()
cache_invalidation = CacheInvalidationSignals()

# Export decorators and utilities
cache_queryset = query_cache.cache_queryset
cache_model_method = query_cache.cache_model_method
cache_api_response = api_cache.cache_api_response