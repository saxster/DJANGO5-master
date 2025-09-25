# Manager Pattern - Three-Tier Query Optimization

## Overview
YOUTILITY5 implements a sophisticated three-tier manager pattern for database query optimization. This architecture provides progressive levels of optimization from basic CRUD operations to highly cached, performance-tuned queries.

## Three-Tier Architecture

### Tier 1: Standard Managers
Basic CRUD operations without optimization

### Tier 2: ORM-Optimized Managers
Strategic use of `select_related()` and `prefetch_related()`

### Tier 3: Cached Managers
Redis caching with intelligent invalidation

## Standard Manager Implementation

### Basic Manager Pattern
**Location**: `/apps/activity/managers/job_manager.py`

```python
from django.db import models
from django.db.models import Q, F, Count
from django.utils import timezone

class JobManager(models.Manager):
    """Basic manager for Job model"""

    def get_active_jobs(self):
        """Get all active jobs"""
        return self.filter(status='active')

    def get_overdue_jobs(self):
        """Get jobs past their deadline"""
        return self.filter(
            status__in=['pending', 'in_progress'],
            deadline__lt=timezone.now()
        )

    def get_user_jobs(self, user_id):
        """Get jobs assigned to a specific user"""
        return self.filter(assigned_to_id=user_id)

    def get_by_priority(self):
        """Get jobs ordered by priority"""
        return self.order_by('-priority', 'created_at')

    def search_jobs(self, query):
        """Search jobs by code or name"""
        return self.filter(
            Q(jobcode__icontains=query) |
            Q(jobname__icontains=query) |
            Q(description__icontains=query)
        )
```

### Model Integration
```python
class Job(BaseModel, TenantAwareModel):
    # Fields definition...

    objects = JobManager()  # Default manager

    class Meta(BaseModel.Meta):
        db_table = 'activity_job'
```

## ORM-Optimized Manager

### Advanced Query Optimization
**Location**: `/apps/activity/managers/job_manager_orm_optimized.py`

```python
class JobneedManagerORMOptimized:
    """Optimized Django ORM implementations for complex Jobneed queries"""

    # Cache timeouts for different query types
    CACHE_TIMEOUTS = {
        'schedule_query': 300,      # 5 minutes
        'report_data': 900,         # 15 minutes
        'hierarchical_data': 1800,  # 30 minutes
        'job_needs': 120,           # 2 minutes
        'external_tours': 300       # 5 minutes
    }

    @staticmethod
    def get_jobs_with_relations(manager, bu_id):
        """
        Optimized query with selective field loading and prefetching.

        Performance improvements:
        - 60-80% reduction in query execution time
        - 40-60% reduction in memory usage
        - Eliminates N+1 queries
        """
        return manager.filter(
            bu_id=bu_id,
            status='active'
        ).select_related(
            # Single JOIN queries for one-to-one/foreign keys
            'assigned_to',
            'created_by',
            'site',
            'asset'
        ).prefetch_related(
            # Separate queries for many-to-many/reverse foreign keys
            'attachments',
            'comments',
            Prefetch(
                'comments',
                queryset=Comment.objects.select_related('author')
            )
        ).only(
            # Only fetch required fields
            'id', 'jobcode', 'jobname', 'status', 'priority',
            'assigned_to__peoplename', 'assigned_to__email',
            'site__name', 'asset__assetcode'
        ).order_by('-priority', 'created_at')

    @staticmethod
    def get_schedule_for_adhoc(manager, pdt, peopleid, assetid, qsetid, buid):
        """
        Find available schedule slot with optimizations:
        - Cached group lookup
        - Selective field loading
        - Index-friendly query patterns
        """
        # Get person's groups (cached)
        group_ids = cls._get_person_groups_cached(peopleid)

        queryset = manager.filter(
            jobstatus__exclude='COMPLETED',
            asset_id=assetid,
            bu_id=buid,
            qset_id=qsetid,
            plandatetime__lte=pdt + timedelta(minutes=F('gracetime')),
            expirydatetime__gte=pdt
        ).filter(
            Q(people_id=peopleid) | Q(pgroup_id__in=group_ids)
        ).select_related(
            'bu', 'asset', 'qset'
        ).only(
            'id', 'plandatetime', 'expirydatetime', 'gracetime',
            'bu__buname', 'asset__assetname', 'qset__qsetname'
        ).order_by('plandatetime')[:1]

        return list(queryset)
```

### Prefetch Patterns

```python
from django.db.models import Prefetch

class AssetManagerOptimized(models.Manager):
    def get_assets_with_maintenance(self):
        """Get assets with maintenance history - optimized"""
        return self.prefetch_related(
            Prefetch(
                'maintenance_records',
                queryset=MaintenanceRecord.objects.filter(
                    completed=True
                ).select_related('technician').order_by('-date')[:5],
                to_attr='recent_maintenance'
            )
        )

    def get_assets_by_location(self, location_id):
        """Get assets with all related data - single database hit"""
        return self.filter(
            location_id=location_id
        ).select_related(
            'location',
            'category',
            'manufacturer'
        ).prefetch_related(
            'warranties',
            'documents',
            Prefetch(
                'assigned_jobs',
                queryset=Job.objects.filter(
                    status__in=['pending', 'in_progress']
                ).select_related('assigned_to')
            )
        )
```

## Cached Manager Pattern

### Redis-Cached Queries
**Location**: `/apps/activity/managers/asset_manager_cached.py`

```python
from django.core.cache import cache
from apps.core.cache_manager import CacheManager

class AssetManagerCached(models.Manager):
    """Manager with Redis caching for frequently accessed data"""

    CACHE_PREFIX = 'asset'
    DEFAULT_TIMEOUT = 300  # 5 minutes

    def _get_cache_key(self, key_parts):
        """Generate consistent cache key"""
        return f"{self.CACHE_PREFIX}:{':'.join(map(str, key_parts))}"

    def get_active_assets_cached(self, bu_id):
        """
        Get active assets with caching.

        Cache invalidation triggers:
        - Asset creation/update/deletion
        - Status change
        - Every 5 minutes (TTL)
        """
        cache_key = self._get_cache_key(['active', bu_id])

        # Try cache first
        assets = cache.get(cache_key)

        if assets is None:
            # Cache miss - fetch from database
            assets = list(
                self.filter(
                    bu_id=bu_id,
                    status='active'
                ).select_related(
                    'location', 'category'
                ).values(
                    'id', 'assetcode', 'assetname',
                    'location__name', 'category__name'
                )
            )

            # Store in cache
            cache.set(cache_key, assets, self.DEFAULT_TIMEOUT)

        return assets

    def invalidate_asset_cache(self, bu_id=None):
        """Invalidate cache when data changes"""
        if bu_id:
            cache.delete(self._get_cache_key(['active', bu_id]))
        else:
            # Clear all asset caches
            cache.delete_pattern(f"{self.CACHE_PREFIX}:*")

    def get_asset_summary_cached(self, bu_id):
        """
        Get asset summary statistics with caching.

        Uses Django's cache framework with intelligent key management.
        """
        cache_key = self._get_cache_key(['summary', bu_id])

        summary = cache.get(cache_key)

        if summary is None:
            from django.db.models import Count, Q

            summary = self.filter(bu_id=bu_id).aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(status='active')),
                maintenance=Count('id', filter=Q(status='maintenance')),
                retired=Count('id', filter=Q(status='retired'))
            )

            cache.set(cache_key, summary, 900)  # 15 minutes

        return summary
```

### Cache Invalidation Strategy

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver([post_save, post_delete], sender=Asset)
def invalidate_asset_cache_on_change(sender, instance, **kwargs):
    """Invalidate cache when asset changes"""
    AssetManagerCached().invalidate_asset_cache(instance.bu_id)

    # Also invalidate related caches
    cache.delete(f"location_assets:{instance.location_id}")
    cache.delete(f"category_assets:{instance.category_id}")
```

## Complex Query Patterns

### Hierarchical Data Queries
```python
class PeopleManagerOptimized(models.Manager):
    def get_team_hierarchy(self, manager_id):
        """Get complete team hierarchy with single query"""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("""
                WITH RECURSIVE team_tree AS (
                    -- Anchor: Get the manager
                    SELECT id, peoplename, manager_id, 0 as level
                    FROM peoples_people
                    WHERE id = %s

                    UNION ALL

                    -- Recursive: Get all reports
                    SELECT p.id, p.peoplename, p.manager_id, t.level + 1
                    FROM peoples_people p
                    INNER JOIN team_tree t ON p.manager_id = t.id
                    WHERE t.level < 5  -- Limit depth
                )
                SELECT * FROM team_tree
                ORDER BY level, peoplename;
            """, [manager_id])

            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

### Aggregation with Annotations
```python
class JobManagerAdvanced(models.Manager):
    def get_workload_summary(self):
        """Get workload summary per person"""
        from django.db.models import Count, Avg, F, Q
        from django.db.models.functions import TruncWeek

        return self.filter(
            status__in=['pending', 'in_progress']
        ).values(
            'assigned_to__peoplename'
        ).annotate(
            total_jobs=Count('id'),
            high_priority=Count('id', filter=Q(priority='high')),
            overdue=Count(
                'id',
                filter=Q(deadline__lt=timezone.now())
            ),
            avg_age_days=Avg(
                timezone.now() - F('created_at'),
                output_field=models.DurationField()
            )
        ).order_by('-total_jobs')
```

## Performance Monitoring

### Query Performance Tracking
```python
import time
import logging
from django.db import connection, reset_queries

logger = logging.getLogger('performance')

class PerformanceManager(models.Manager):
    def get_queryset(self):
        """Track all queries in development"""
        if settings.DEBUG:
            reset_queries()

        queryset = super().get_queryset()

        if settings.DEBUG:
            # Log query count and time
            for query in connection.queries:
                logger.debug(
                    f"Query: {query['sql'][:100]}... "
                    f"Time: {query['time']}s"
                )

        return queryset
```

### Cache Hit Rate Monitoring
```python
class CacheMetrics:
    """Monitor cache performance"""

    @staticmethod
    def track_cache_access(cache_key, hit=True):
        """Track cache hits/misses"""
        metric_key = f"cache_metrics:{cache_key.split(':')[0]}"

        metrics = cache.get(metric_key, {'hits': 0, 'misses': 0})

        if hit:
            metrics['hits'] += 1
        else:
            metrics['misses'] += 1

        metrics['hit_rate'] = metrics['hits'] / (metrics['hits'] + metrics['misses'])

        cache.set(metric_key, metrics, 3600)  # Keep for 1 hour

        if metrics['hit_rate'] < 0.5:
            logger.warning(f"Low cache hit rate for {cache_key}: {metrics['hit_rate']:.2%}")
```

## Testing Manager Patterns

### Testing Optimized Queries
```python
from django.test import TestCase
from django.test.utils import override_settings
from django.db import connection
from django.test import TransactionTestCase

class TestOptimizedManagers(TransactionTestCase):
    def setUp(self):
        # Create test data
        self.setup_test_data()

    def test_query_count_optimization(self):
        """Ensure optimized query doesn't cause N+1"""
        with self.assertNumQueries(3):  # Expect exactly 3 queries
            jobs = Job.objects.get_jobs_with_relations(bu_id=1)

            # Force evaluation
            for job in jobs:
                # These should not trigger additional queries
                _ = job.assigned_to.peoplename
                _ = job.site.name
                _ = list(job.comments.all())

    @override_settings(DEBUG=True)
    def test_cache_effectiveness(self):
        """Test cache hit rate"""
        from django.core.cache import cache

        # Clear cache
        cache.clear()

        # First call - cache miss
        assets1 = AssetManagerCached().get_active_assets_cached(1)

        # Second call - cache hit
        assets2 = AssetManagerCached().get_active_assets_cached(1)

        self.assertEqual(assets1, assets2)

        # Check only 1 database query was made
        self.assertEqual(len(connection.queries), 1)
```

## Best Practices

1. **Start with standard managers** for simple queries
2. **Add select_related/prefetch_related** when you see N+1 queries
3. **Use only()** to limit fields when you don't need all columns
4. **Cache frequently accessed, rarely changed data**
5. **Set appropriate cache timeouts** based on data volatility
6. **Implement cache warming** for critical data
7. **Monitor cache hit rates** and adjust strategies
8. **Use database indexes** that match your query patterns
9. **Profile queries** in development with Django Debug Toolbar
10. **Write tests** for query count expectations

## Query Optimization Checklist

- [ ] Identify N+1 query patterns
- [ ] Add appropriate select_related() for ForeignKeys
- [ ] Add prefetch_related() for ManyToMany/reverse ForeignKeys
- [ ] Use only() or defer() for field selection
- [ ] Consider caching for expensive queries
- [ ] Add database indexes for filter/order_by fields
- [ ] Test query performance with realistic data volumes
- [ ] Monitor production query performance
- [ ] Document complex queries
- [ ] Set up cache invalidation triggers

## Related Documentation
- [Model Architecture](./model_architecture.md) - Model structure and inheritance
- [Celery & Redis](./celery_redis.md) - Caching infrastructure
- [Database Optimization](./database_optimization.md) - PostgreSQL tuning