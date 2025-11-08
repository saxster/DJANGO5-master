# Performance Optimization Ontology

**Created**: November 6, 2025  
**Status**: Complete  
**Components**: 25+ patterns, concepts, and examples  
**Domain**: Performance Optimization

---

## Overview

The Performance Optimization Ontology captures all N+1 query optimization knowledge, patterns, testing utilities, and best practices developed during the November 2025 performance enhancement work. This ontology enables LLM-assisted development by making performance knowledge searchable and discoverable.

---

## Quick Start

### Load Performance Patterns

```bash
# Load all performance optimization patterns
python manage.py load_performance_ontology

# Load with statistics
python manage.py load_performance_ontology --stats

# Clear and reload
python manage.py load_performance_ontology --clear --stats
```

### Query Performance Knowledge

```python
from apps.ontology.registry import OntologyRegistry

# Get N+1 query problem explanation
n1_concept = OntologyRegistry.get("concepts.n_plus_one_query_problem")
print(n1_concept['purpose'])
print(n1_concept['examples'][0]['code'])

# Find all performance testing concepts
testing_concepts = OntologyRegistry.get_by_domain("performance.testing")

# Search for optimization patterns
results = OntologyRegistry.search("select_related")

# Get all implementation examples
examples = OntologyRegistry.get_by_tag("example")
```

---

## Registered Components

### 1. Core Concepts (4 components)

#### N+1 Query Problem
- **qualified_name**: `concepts.n_plus_one_query_problem`
- **Purpose**: Understanding the classic N+1 performance anti-pattern
- **Criticality**: High
- **Examples**: Before/after code showing 101 queries → 1 query
- **Related**: NPlusOneDetector, select_related, prefetch_related

#### select_related()
- **qualified_name**: `concepts.select_related`
- **Purpose**: SQL JOIN optimization for ForeignKey and OneToOne
- **When to Use**: Forward ForeignKey, OneToOneField relationships
- **Examples**: Single, multiple, and nested select_related patterns
- **Documentation**: Django docs, QUERY_OPTIMIZATION_ARCHITECTURE.md

#### prefetch_related()
- **qualified_name**: `concepts.prefetch_related`
- **Purpose**: Separate query optimization for ManyToMany and reverse FK
- **When to Use**: ManyToMany, reverse ForeignKey relationships
- **Examples**: Basic and advanced with Prefetch objects
- **Documentation**: Django docs, optimization architecture

#### Prefetch Object
- **qualified_name**: `concepts.prefetch_object`
- **Purpose**: Advanced prefetch with custom querysets and filtering
- **Criticality**: Medium
- **Examples**: Nested optimizations, filtered prefetch
- **Advanced Pattern**: Using to_attr for caching

### 2. Optimization Techniques (2 components)

#### Custom Manager Methods
- **qualified_name**: `concepts.custom_manager_methods`
- **Purpose**: Reusable optimization patterns via custom managers
- **Pattern**: `with_full_details()` convention
- **Implementations**:
  - `apps/peoples/managers.py:82` - PeopleManager
  - `apps/noc/models/incident.py:21` - NOCIncidentManager
  - `apps/activity/models/job_model.py` - JobManager
  - `apps/core/managers/optimized_managers.py:192` - Base class

#### Query Result Caching
- **qualified_name**: `concepts.query_result_caching`
- **Purpose**: Redis caching complementing query optimization
- **Criticality**: Medium
- **Integration**: Combine with optimized queries for maximum performance

### 3. Detection & Monitoring (2 tools)

#### NPlusOneDetector
- **qualified_name**: `apps.core.utils_new.query_optimizer.NPlusOneDetector`
- **Type**: Runtime monitoring class
- **Purpose**: Real-time N+1 detection during execution
- **Usage**:
  - Context manager: `with NPlusOneDetector(threshold=5)`
  - Decorator: `@detect_n_plus_one`
- **Features**:
  - Query signature normalization
  - Stack trace capture
  - Threshold-based alerting
- **Implementation**: `apps/core/utils_new/query_optimizer.py:33-150`

#### QueryOptimizer Service
- **qualified_name**: `apps.core.services.query_optimization_service.QueryOptimizer`
- **Type**: Service-layer automation
- **Purpose**: Automatic queryset optimization
- **Profiles**:
  - **minimal**: Critical non-nullable FKs only
  - **default**: High-impact relationships (recommended)
  - **aggressive**: All relationships
- **Methods**:
  - `optimize_queryset(queryset, profile='default')`
  - `optimize_people_queries()`
  - `optimize_activity_queries()`
  - `create_optimized_prefetch()`
- **Implementation**: `apps/core/services/query_optimization_service.py`

### 4. Testing Utilities (3 concepts)

#### assertNumQueries
- **qualified_name**: `concepts.assertNumQueries`
- **Purpose**: Assert specific query count to prevent regressions
- **Criticality**: High
- **Examples**:
  - Basic: `with self.assertNumQueries(1):`
  - Complex: Multi-prefetch verification
- **Implementations**:
  - `apps/noc/tests/test_performance/test_n1_optimizations.py`
  - `apps/peoples/tests/test_user_model.py:213`

#### Performance Benchmarking
- **qualified_name**: `concepts.performance_benchmarking`
- **Purpose**: Measure before/after optimization performance
- **Criticality**: Medium
- **Pattern**: Time comparison with improvement percentage

#### Query Count Testing
- **qualified_name**: `concepts.query_count_testing`
- **Purpose**: Regression prevention via query thresholds
- **Criticality**: High
- **Best Practice**: Test suite with assertNumQueries for all optimized views
- **CI/CD Integration**: Run in automated testing

### 5. Real-World Examples (3 case studies)

#### NOC Incident Optimization
- **qualified_name**: `examples.noc_incident_optimization`
- **Impact**: 101 queries → 3 queries (97% reduction)
- **Pattern**: Custom manager with select_related + Prefetch
- **Implementation**: `apps/noc/models/incident.py:21`
- **Tests**: `apps/noc/tests/test_performance/test_n1_optimizations.py:277`

#### People Manager Optimization
- **qualified_name**: `examples.people_manager_optimization`
- **Impact**: 301 queries → 1 query (99.7% reduction)
- **Pattern**: select_related for profile, organizational, shift
- **Implementation**: `apps/peoples/managers.py:82`
- **Tests**: `apps/peoples/tests/test_user_model.py:213`
- **Documentation**: `apps/peoples/models/user_model.py:88`

#### Reports Service Optimization
- **qualified_name**: `examples.reports_service_optimization`
- **Impact**: 102 queries → 4 queries (96% reduction)
- **Pattern**: Nested Prefetch with filtered querysets
- **Implementation**: `apps/reports/services/`

### 6. Anti-Patterns (3 pitfalls)

#### Over-Prefetching
- **qualified_name**: `anti_patterns.over_prefetching`
- **Problem**: Fetching too much data wastes memory
- **Solution**: Use `minimal` profile or `only()` for limited fields

#### Missing to_attr
- **qualified_name**: `anti_patterns.missing_to_attr`
- **Problem**: Nested prefetch without to_attr causes re-queries
- **Solution**: Always use `to_attr='cached_name'` in nested Prefetch

#### Queryset in Loop
- **qualified_name**: `anti_patterns.queryset_in_loop`
- **Problem**: Classic N+1 pattern
- **Solution**: Batch queries with `filter(id__in=ids)`

### 7. Manager Implementations (3 components)

#### OptimizedManager (Base Class)
- **qualified_name**: `apps.core.managers.optimized_managers.OptimizedManager`
- **Purpose**: Base class for all optimized managers
- **Methods**:
  - `with_optimizations()` - Default optimizations
  - `with_full_details()` - Full relationship prefetch
- **Usage**: Extend in custom managers
- **Implementation**: `apps/core/managers/optimized_managers.py`

#### PeopleManager.with_full_details
- **qualified_name**: `apps.peoples.managers.PeopleManager.with_full_details`
- **Optimizations**:
  - select_related('profile')
  - select_related('organizational')
  - select_related('shift')
- **Tests**: Complete coverage with assertNumQueries

#### NOCIncidentManager.with_full_details
- **qualified_name**: `apps.noc.models.incident.NOCIncidentManager.with_full_details`
- **Optimizations**:
  - select_related('site', 'severity', 'assigned_to')
  - prefetch_related('alerts', 'notifications')
- **Tests**: Verified <= 4 queries

### 8. Documentation (2 references)

#### Query Optimization Architecture
- **qualified_name**: `documentation.query_optimization_architecture`
- **Path**: `docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md`
- **Sections**:
  - Module Breakdown
  - Decision Tree
  - Common Patterns
  - Performance Guidelines
  - Testing Strategy

#### N+1 Optimization Deliverables
- **qualified_name**: `documentation.n1_optimization_deliverables`
- **Files**:
  - `N1_OPTIMIZATION_PART2_DELIVERABLES.md`
  - `N1_OPTIMIZATION_QUICK_REFERENCE.md`
  - `N_PLUS_ONE_FIXES_PART1_COMPLETE.md`
- **Apps Optimized**: 9 apps (noc, reports, activity, peoples, etc.)

---

## Usage Patterns

### Pattern 1: Find Optimization for Specific Model

```python
from apps.ontology.registry import OntologyRegistry

# Search for People model optimization
results = OntologyRegistry.search("PeopleManager")
for result in results:
    if 'implementation' in result:
        print(f"File: {result['implementation']}")
        print(f"Purpose: {result['purpose']}")
```

### Pattern 2: Get All Testing Utilities

```python
# Get all performance testing concepts
testing = OntologyRegistry.get_by_domain("performance.testing")

for concept in testing:
    print(f"{concept['qualified_name']}:")
    print(f"  {concept['purpose']}")
    if 'examples' in concept:
        print(f"  Examples: {len(concept['examples'])}")
```

### Pattern 3: Claude Code Integration

Use in Claude Code slash command:

```
/ontology performance

# Loads all performance optimization concepts
# Shows N+1 patterns, select_related examples, testing utilities
```

### Pattern 4: Find Anti-Patterns

```python
# Get all anti-patterns
anti_patterns = OntologyRegistry.get_by_tag("anti-pattern")

for pattern in anti_patterns:
    print(f"⚠️  {pattern['qualified_name']}")
    print(f"   Problem: {pattern['description']}")
    print(f"   Solution: {pattern['solution']}")
```

---

## Metrics & Coverage

### Components by Domain

| Domain | Count | Description |
|--------|-------|-------------|
| performance.database | 6 | Core concepts (N+1, select_related, prefetch_related) |
| performance.optimization | 1 | QueryOptimizer service |
| performance.monitoring | 1 | NPlusOneDetector |
| performance.testing | 3 | assertNumQueries, benchmarking, query count testing |
| performance.implementation | 3 | Real-world case studies |
| performance.pitfalls | 3 | Anti-patterns to avoid |
| performance.managers | 3 | Optimized manager implementations |
| performance.caching | 1 | Query result caching |
| performance.reference | 2 | Documentation references |

**Total Components**: 25

### Tags Distribution

- `performance`: 22 components
- `database`: 8 components
- `optimization`: 10 components
- `testing`: 5 components
- `example`: 3 components
- `anti-pattern`: 3 components
- `monitoring`: 2 components
- `n+1`: 4 components

### Criticality Breakdown

- **High**: 11 components (44%)
- **Medium**: 4 components (16%)
- **Not specified**: 10 components (40%)

---

## Before/After Impact Summary

### Real-World Results from Ontology Examples

| Example | Before | After | Reduction | Impact |
|---------|--------|-------|-----------|--------|
| NOC Incidents | 101 queries | 3 queries | 97% | High |
| People List | 301 queries | 1 query | 99.7% | High |
| Reports | 102 queries | 4 queries | 96% | High |

### Apps Optimized (from documentation references)

1. **noc** - Incident and alert queries
2. **reports** - Report generation services
3. **activity** - Job and asset queries
4. **peoples** - User profile and organizational data
5. **work_order_management** - Work order relationships
6. **attendance** - Attendance records with user data
7. **journal** - Journal entries with people
8. **wellness** - Wellness content delivery
9. **y_helpdesk** - Ticket queries with relationships

---

## Integration with Development Workflow

### 1. When Implementing New Features

```python
# Step 1: Check ontology for patterns
from apps.ontology.registry import OntologyRegistry

patterns = OntologyRegistry.search("custom manager")
# Review existing patterns before implementing

# Step 2: Use OptimizedManager base class
from apps.core.managers.optimized_managers import OptimizedManager

class MyModelManager(OptimizedManager):
    def with_full_details(self):
        return self.select_related('fk1', 'fk2').prefetch_related('m2m')

# Step 3: Add tests with assertNumQueries
def test_my_model_optimization(self):
    with self.assertNumQueries(3):
        items = list(MyModel.objects.with_full_details()[:10])
```

### 2. When Debugging Performance Issues

```python
# Step 1: Enable N+1 detection
from apps.core.utils_new.query_optimizer import detect_n_plus_one

@detect_n_plus_one
def my_slow_view(request):
    # Will automatically report N+1 issues
    pass

# Step 2: Apply optimization from ontology
# Search for similar patterns:
similar = OntologyRegistry.search("prefetch_related")
# Apply learned patterns
```

### 3. When Writing Documentation

Reference ontology concepts:

```markdown
This view uses the N+1 optimization pattern documented in the ontology
(`concepts.select_related`). See `apps/peoples/managers.py:82` for
implementation example.
```

---

## Future Enhancements

### Planned Additions

1. **Query Plan Analysis Integration**
   - Link to `apps/core/services/query_plan_analyzer.py`
   - Automatic EXPLAIN output for slow queries

2. **ML-Based Profile Recommendation**
   - Analyze query patterns
   - Suggest optimal profile (minimal/default/aggressive)

3. **Visual Performance Dashboard**
   - Real-time N+1 visualization
   - Query count trends
   - Optimization suggestions

4. **Automated Migration Assistant**
   - Detect manual select_related patterns
   - Suggest OptimizedManager migration

### Under Consideration

- Query result caching at optimizer level
- Lazy prefetch (fetch on access)
- Query rewriting for complex patterns
- Integration with Django Debug Toolbar

---

## Contributing New Patterns

When you discover a new optimization pattern:

1. **Document in Code**:
   ```python
   @ontology(
       domain="performance.database",
       purpose="Your optimization pattern",
       examples=[...],
       tags=["performance", "optimization"]
   )
   ```

2. **Add to Registration**:
   - Update `apps/ontology/registrations/performance_optimization_patterns.py`
   - Add to appropriate section (concepts/tools/examples/anti-patterns)

3. **Include Tests**:
   - Add test coverage with `assertNumQueries`
   - Link test file in `test_coverage` field

4. **Update Documentation**:
   - Add to implementation examples
   - Document impact (query reduction %)

---

## FAQ

### Q: How do I find the right optimization for my model?

**A**: 
```python
# Search for similar models
results = OntologyRegistry.search("your_model_name")

# Or browse by domain
db_concepts = OntologyRegistry.get_by_domain("performance.database")
```

### Q: What's the difference between NPlusOneDetector and QueryOptimizer?

**A**: 
- **NPlusOneDetector**: Monitors/detects issues (diagnostic)
- **QueryOptimizer**: Fixes/optimizes queries (prescriptive)
- See: `documentation.query_optimization_architecture`

### Q: When should I use select_related vs prefetch_related?

**A**: Query the ontology:
```python
select_related = OntologyRegistry.get("concepts.select_related")
print(select_related['examples'][1]['description'])
# "✅ Use for: ForeignKey, OneToOneField (forward)"

prefetch_related = OntologyRegistry.get("concepts.prefetch_related")  
print(prefetch_related['examples'][0]['title'])
# Shows when to use each
```

### Q: How do I prevent N+1 regressions?

**A**: Use `concepts.query_count_testing` pattern:
```python
concept = OntologyRegistry.get("concepts.query_count_testing")
# Shows test patterns with assertNumQueries
```

---

## References

### Implementation Files

- **Registry**: `apps/ontology/registrations/performance_optimization_patterns.py`
- **Management Command**: `apps/ontology/management/commands/load_performance_ontology.py`
- **Base Manager**: `apps/core/managers/optimized_managers.py`
- **Detector**: `apps/core/utils_new/query_optimizer.py`
- **Service**: `apps/core/services/query_optimization_service.py`

### Documentation

- **Architecture**: `docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md`
- **Deliverables**: `N1_OPTIMIZATION_PART2_DELIVERABLES.md`
- **Quick Reference**: `N1_OPTIMIZATION_QUICK_REFERENCE.md`
- **Testing Guide**: `docs/testing/TESTING_AND_QUALITY_GUIDE.md`

### Related Systems

- **Caching**: `docs/features/DOMAIN_SPECIFIC_SYSTEMS.md#Caching-Strategy`
- **Monitoring**: `monitoring/performance_monitor_enhanced.py`
- **Query Analysis**: `apps/core/services/query_plan_analyzer.py`

---

**Last Updated**: November 6, 2025  
**Maintainer**: Development Team  
**Next Review**: December 2025 or on major optimization work
