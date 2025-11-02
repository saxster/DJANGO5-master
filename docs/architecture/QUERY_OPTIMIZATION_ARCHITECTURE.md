# Query Optimization Architecture

**Last Updated**: 2025-10-31
**Status**: Active
**Maintainer**: Development Team

---

## Overview

This document explains the query optimization architecture in the codebase, clarifying the roles of different modules and when to use each one.

## Executive Summary

The query optimization system is divided into **TWO complementary modules**:

1. **Runtime Detection** (`query_optimizer.py`) - Monitors queries during execution
2. **Service-Layer Optimization** (`query_optimization_service.py`) - Automatically optimizes querysets

**These are NOT duplicates** - they serve different architectural concerns and work together.

---

## Module Breakdown

### 1. Runtime Detection & Monitoring

**File**: `apps/core/utils_new/query_optimizer.py` (424 lines)

**Purpose**: Real-time N+1 query detection and performance monitoring

**Core Components**:
- `NPlusOneDetector` - Runtime N+1 detection with threshold-based alerting
- `QueryOptimizer` - Analyzes querysets and suggests optimizations
- `@detect_n_plus_one` - Decorator for automatic N+1 detection in views
- `QueryAnalyzer` - Context manager for query analysis

**When to Use**:
- Development/debugging to identify N+1 issues
- Production monitoring via middleware
- Testing query optimization effectiveness
- Performance profiling

**Example Usage**:
```python
from apps.core.utils_new.query_optimizer import NPlusOneDetector, detect_n_plus_one

# As a decorator
@detect_n_plus_one
def my_view(request):
    users = People.objects.all()
    for user in users:
        print(user.profile.gender)  # Would trigger N+1 warning

# As a context manager
with NPlusOneDetector(threshold=5) as detector:
    # Your code here
    detector.stop_monitoring()
    print(detector.get_report())
```

**Key Features**:
- Query signature normalization
- Stack trace capture
- Threshold-based alerting
- Integration with Django Debug mode

**Consumers**:
- `monitoring/performance_monitor_enhanced.py` - Production monitoring
- `scripts/test_performance_optimizations.py` - Test infrastructure
- Various middleware for real-time detection

---

### 2. Service-Layer Optimization

**File**: `apps/core/services/query_optimization_service.py` (469 lines)

**Purpose**: Automated queryset optimization with intelligent relationship analysis

**Core Components**:
- `QueryOptimizer` - Service class with automated analysis
- Three optimization profiles: `minimal`, `default`, `aggressive`
- Domain-specific methods: `optimize_people_queries()`, `optimize_activity_queries()`
- `create_optimized_prefetch()` - Factory for complex Prefetch objects
- `analyze_query_performance()` - Diagnostic tool

**When to Use**:
- Model managers (via `OptimizedManager`)
- Service layer query building
- API endpoints requiring optimized querysets
- Automated optimization without manual select_related/prefetch_related

**Example Usage**:
```python
from apps.core.services.query_optimization_service import QueryOptimizer

# Automatic optimization with profiles
queryset = Job.objects.all()
optimized = QueryOptimizer.optimize_queryset(queryset, profile='default')

# Domain-specific optimization
people_qs = QueryOptimizer.optimize_people_queries()

# Complex prefetch patterns
prefetch = QueryOptimizer.create_optimized_prefetch(
    'assigned_people',
    queryset=People.objects.select_related('shift'),
    to_attr='optimized_people'
)
```

**Optimization Profiles**:

| Profile | Strategy | Use Case |
|---------|----------|----------|
| `minimal` | Only critical non-nullable FKs | Memory-constrained, read-heavy loads |
| `default` | High-impact relationships | General production use (RECOMMENDED) |
| `aggressive` | All relationships | Admin interfaces, reporting |

**Key Features**:
- Automatic relationship discovery via Django meta API
- Performance impact assessment (high/medium/low)
- Relationship caching for repeated queries
- ErrorHandler integration
- Sanitized logging

**Consumers**:
- `apps/core/managers/optimized_managers.py` - Base class for all optimized managers
- `apps/core/management/commands/audit_query_optimization.py` - Auditing tool
- Various service classes for domain logic

---

## Architectural Decision: Why Two Modules?

### Separation of Concerns

```
┌─────────────────────────────────────────────┐
│  MONITORING LAYER                           │
│  (query_optimizer.py)                       │
│  "What queries ARE running?"                │
│  - Runtime detection                        │
│  - Performance profiling                    │
│  - N+1 alerts                               │
└─────────────────────────────────────────────┘
                    ↕
              Feedback Loop
                    ↕
┌─────────────────────────────────────────────┐
│  OPTIMIZATION LAYER                         │
│  (query_optimization_service.py)            │
│  "How queries SHOULD run"                   │
│  - Automatic optimization                   │
│  - Relationship analysis                    │
│  - Profile-based strategies                 │
└─────────────────────────────────────────────┘
```

### Analogy

Think of it like a car:
- **query_optimizer.py** = Dashboard/sensors (tells you what's happening)
- **query_optimization_service.py** = Engine/transmission (makes things run efficiently)

You wouldn't merge your dashboard into your engine - they're complementary systems.

---

## Decision Tree: Which Module Should I Use?

```
Are you trying to...

┌─ Detect N+1 issues? ────────────────► query_optimizer.py
│                                        └─ Use NPlusOneDetector or @detect_n_plus_one
│
├─ Monitor production performance? ───► query_optimizer.py
│                                        └─ Use in middleware/monitoring
│
├─ Optimize a queryset? ─────────────► query_optimization_service.py
│                                        └─ Use QueryOptimizer.optimize_queryset()
│
├─ Build an optimized manager? ───────► query_optimization_service.py
│                                        └─ Extend OptimizedManager
│
└─ Test query performance? ───────────► Both!
                                         └─ Service for optimization
                                         └─ Optimizer for verification
```

---

## Common Patterns

### Pattern 1: Manager with Optimization

```python
from apps.core.managers.optimized_managers import OptimizedManager
from apps.core.services.query_optimization_service import QueryOptimizer

class MyModel(models.Model):
    # ... fields ...

    objects = OptimizedManager()  # Uses QueryOptimizer internally
```

### Pattern 2: View with N+1 Detection

```python
from apps.core.utils_new.query_optimizer import detect_n_plus_one

@detect_n_plus_one
def my_view(request):
    items = MyModel.objects.with_optimizations()
    # Automatic N+1 detection during development
    return render(request, 'template.html', {'items': items})
```

### Pattern 3: Service Method with Custom Optimization

```python
from apps.core.services.query_optimization_service import QueryOptimizer

def get_dashboard_data():
    # Use aggressive profile for admin dashboard
    tickets = Ticket.objects.filter(status='open')
    optimized = QueryOptimizer.optimize_queryset(tickets, profile='aggressive')
    return optimized
```

### Pattern 4: Testing Query Optimization

```python
from apps.core.utils_new.query_optimizer import QueryAnalyzer
from apps.core.services.query_optimization_service import QueryOptimizer

def test_query_efficiency():
    # Optimize first
    queryset = QueryOptimizer.optimize_queryset(MyModel.objects.all())

    # Then verify
    with QueryAnalyzer() as analyzer:
        list(queryset)  # Force evaluation

    report = analyzer.get_report()
    assert report['query_count'] < 5, "Too many queries"
```

---

## Historical Context

### Deprecated Module: query_optimization.py

**Status**: Deprecated 2025-10-31, moved to `.deprecated/`

**Why Deprecated**:
- Zero production imports (never adopted)
- Mixin-based approach didn't fit architecture
- Service-layer approach proved superior

**What It Had**:
- `QueryOptimizationMixin` - Declarative model mixin
- `OptimizedQueryset` - Custom queryset class
- `CommonOptimizations` - Static helper methods

**Lessons Learned**:
1. Declarative mixin pattern sounded good but wasn't adopted
2. Service-layer with automated analysis proved more maintainable
3. Zero usage = immediate candidate for removal

---

## Performance Guidelines

### When to Optimize

**Always Optimize**:
- List views (tables, cards)
- API endpoints
- Reports and analytics
- Admin interfaces

**Consider Not Optimizing**:
- Single-object detail views
- Queries that only access local fields
- Write-heavy operations (saves, updates)

### Optimization Best Practices

1. **Use `default` profile by default** - Good balance of performance vs memory
2. **Monitor with query_optimizer.py** - Find issues before production
3. **Benchmark before/after** - Verify optimizations actually help
4. **Avoid over-optimization** - Fetching unused data wastes memory

### Common Pitfalls

| Pitfall | Consequence | Solution |
|---------|-------------|----------|
| Over-prefetching | Memory bloat | Use `minimal` profile |
| No optimization | N+1 queries | Use `default` profile |
| Nested prefetch without to_attr | Duplicate queries | Use `create_optimized_prefetch()` |
| Manual select_related everywhere | Maintenance burden | Use OptimizedManager |

---

## Metrics & Monitoring

### Key Metrics

Track these in production:
- **Query count per request** - Should be < 50 for most views
- **N+1 incidents** - Captured by NPlusOneDetector
- **Query execution time** - Should be < 100ms total per request

### Monitoring Setup

```python
# In middleware
from apps.core.utils_new.query_optimizer import NPlusOneDetector

class QueryMonitoringMiddleware:
    def __call__(self, request):
        with NPlusOneDetector(threshold=10) as detector:
            response = self.get_response(request)

            if detector.has_issues():
                logger.warning(
                    "N+1 detected",
                    extra={'path': request.path, 'report': detector.get_report()}
                )
        return response
```

---

## Testing Strategy

### Unit Tests

- Test `QueryOptimizer` with mock models
- Test `NPlusOneDetector` with known N+1 patterns
- Test optimization profiles with various models

### Integration Tests

- Test optimized managers with real queries
- Test N+1 detection in actual views
- Benchmark query counts before/after optimization

### Performance Tests

- Load testing with optimized vs unoptimized queries
- Memory profiling with different profiles
- Query count assertions in critical paths

---

## Future Enhancements

### Planned

1. **Query Plan Analysis** - Integrate with `apps/core/services/query_plan_analyzer.py`
2. **Automatic Profile Selection** - ML-based profile recommendation
3. **Cache Integration** - Coordinate with Redis caching strategy
4. **Dashboard** - Real-time N+1 visualization

### Under Consideration

1. Query result caching at optimizer level
2. Lazy prefetch (fetch on access)
3. Query rewriting for complex patterns

---

## FAQ

### Q: Why not consolidate everything into one module?

**A**: Monitoring (detection) and optimization (fixing) are orthogonal concerns. Mixing them creates god classes that are hard to maintain.

### Q: Can I use both modules together?

**A**: Yes! In fact, that's the recommended approach:
1. Use service for optimization
2. Use optimizer for monitoring/verification

### Q: Which module is "official"?

**A**: Both are official and actively maintained:
- `query_optimizer.py` for detection
- `query_optimization_service.py` for optimization

### Q: What happened to QueryOptimizationMixin?

**A**: It was deprecated (2025-10-31) due to zero adoption. The service-layer approach proved more practical.

### Q: How do I migrate from manual select_related?

**A**: Replace with OptimizedManager:
```python
# Before
class MyModel(models.Model):
    # ...

# In view
queryset = MyModel.objects.select_related('foo', 'bar').prefetch_related('baz')

# After
class MyModel(models.Model):
    objects = OptimizedManager()

# In view
queryset = MyModel.objects.with_optimizations()  # Automatic!
```

### Q: How do I report N+1 issues?

**A**: Use the NPlusOneDetector in development, then file an issue with the query pattern.

---

## References

- **Implementation**: `apps/core/utils_new/query_optimizer.py`
- **Implementation**: `apps/core/services/query_optimization_service.py`
- **Managers**: `apps/core/managers/optimized_managers.py`
- **Tests**: `apps/core/tests/test_comprehensive_security_fixes.py`
- **Monitoring**: `monitoring/performance_monitor_enhanced.py`

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-10-31 | Initial architecture documentation | Claude Code |
| 2025-10-31 | Deprecated query_optimization.py | Claude Code |

---

**Questions?** Contact the development team or file an issue.
