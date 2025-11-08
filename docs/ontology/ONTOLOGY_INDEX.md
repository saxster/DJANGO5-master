# Ontology System - Complete Index

**Last Updated**: November 6, 2025  
**Status**: Active  
**Total Registered Components**: 63+ (38 premium + 25+ performance)

---

## Quick Navigation

| Category | Components | Documentation |
|----------|------------|---------------|
| **Premium Features** | 38 | [November 2025 Improvements](../../apps/ontology/registrations/november_2025_improvements.py) |
| **Performance Patterns** | 25+ | [PERFORMANCE_OPTIMIZATION_ONTOLOGY.md](PERFORMANCE_OPTIMIZATION_ONTOLOGY.md) |
| **Strategic Features** | - | [November 2025 Strategic](../../apps/ontology/registrations/november_2025_strategic_features.py) |

---

## Load All Registrations

### Command Line

```bash
# Load premium features
python manage.py shell -c "from apps.ontology.registrations.november_2025_improvements import register_november_2025_improvements; register_november_2025_improvements()"

# Load performance patterns
python manage.py load_performance_ontology --stats

# Extract all ontology from codebase
python manage.py extract_ontology --apps core activity peoples noc reports
```

### Python

```python
from apps.ontology.registrations.november_2025_improvements import register_november_2025_improvements
from apps.ontology.registrations.performance_optimization_patterns import register_performance_optimization_patterns

# Load all patterns
register_november_2025_improvements()  # 38 components
register_performance_optimization_patterns()  # 25+ components

# Verify
from apps.ontology.registry import OntologyRegistry
stats = OntologyRegistry.get_statistics()
print(f"Total components: {stats['total_components']}")
```

---

## Documentation by Category

### Performance Optimization

1. **[PERFORMANCE_OPTIMIZATION_ONTOLOGY.md](PERFORMANCE_OPTIMIZATION_ONTOLOGY.md)** (500+ lines)
   - Complete guide to all 25+ performance patterns
   - Real-world examples with metrics
   - Usage patterns and integration

2. **[PERFORMANCE_QUICK_REFERENCE.md](PERFORMANCE_QUICK_REFERENCE.md)** (200+ lines)
   - Quick lookup guide
   - Decision trees
   - Common patterns cheat sheet

3. **[../../ONTOLOGY_PERFORMANCE_PATTERNS_COMPLETE.md](../../ONTOLOGY_PERFORMANCE_PATTERNS_COMPLETE.md)**
   - Deliverables summary
   - Metrics and validation
   - Success metrics

### Core Ontology System

1. **[../../apps/ontology/README.md](../../apps/ontology/README.md)**
   - System overview
   - Quick start guide
   - Phase 6 & 7 registrations
   - Extractor documentation

2. **[GOLD_STANDARD_EXAMPLES.md](GOLD_STANDARD_EXAMPLES.md)**
   - High-quality ontology examples
   - Best practices
   - Template patterns

3. **[TAG_TAXONOMY.md](TAG_TAXONOMY.md)**
   - Complete tag classification
   - Usage guidelines
   - Consistency rules

---

## Component Breakdown

### By Domain (Performance)

| Domain | Count | Key Components |
|--------|-------|----------------|
| performance.database | 6 | N+1, select_related, prefetch_related |
| performance.testing | 3 | assertNumQueries, benchmarking |
| performance.monitoring | 2 | NPlusOneDetector, QueryOptimizer |
| performance.implementation | 3 | NOC, People, Reports examples |
| performance.pitfalls | 3 | Anti-patterns |
| performance.managers | 3 | OptimizedManager implementations |

### By Domain (Premium Features)

| Domain | Count | Key Components |
|--------|-------|----------------|
| security.session | 2 | Session revocation |
| security.upload | 4 | CSRF protected uploads |
| security.download | 3 | Secure file serving |
| performance.analytics | 15 | Worker metrics, BPI, gamification |
| reliability | 5 | Exception handling, transactions |
| premium.features | 7 | SOAR, SLA, device health |

---

## Common Queries

### Performance Optimization

```python
from apps.ontology.registry import OntologyRegistry

# Get N+1 problem explanation
n1 = OntologyRegistry.get("concepts.n_plus_one_query_problem")

# Find all testing utilities
testing = OntologyRegistry.get_by_domain("performance.testing")

# Search for optimization examples
examples = OntologyRegistry.search("select_related")

# Get all anti-patterns
anti_patterns = OntologyRegistry.get_by_tag("anti-pattern")
```

### Premium Features

```python
# Find security features
security = OntologyRegistry.get_by_domain("security.download")

# Get performance analytics
analytics = OntologyRegistry.get_by_domain("performance.analytics")

# Find high-criticality components
all_components = OntologyRegistry.get_all()
critical = [c for c in all_components if c.get('criticality') == 'high']
```

### General Queries

```python
# Get statistics
stats = OntologyRegistry.get_statistics()
print(f"Total: {stats['total_components']}")
print(f"Domains: {stats['domains']}")
print(f"Tags: {stats['tags']}")

# Search across all components
results = OntologyRegistry.search("optimization")

# Get by tag
performance = OntologyRegistry.get_by_tag("performance")
```

---

## Claude Code Integration

### Slash Commands

```
/ontology performance
# Loads all performance optimization patterns

/ontology security
# Loads security-related components

/ontology premium
# Loads premium features and analytics
```

### Smart Context Injection

```python
from apps.ontology.claude import inject_ontology_context

# Automatically detects code references in queries
query = "How does the People model optimization work?"
context = inject_ontology_context(query)
# Returns metadata about PeopleManager, select_related, examples
```

### MCP Server

```json
{
  "mcpServers": {
    "ontology": {
      "command": "python",
      "args": ["/path/to/apps/ontology/mcp/run_server.py"]
    }
  }
}
```

**Tools Available**:
- `ontology_query` - Query by domain/tag/purpose
- `ontology_get` - Get specific component
- `ontology_stats` - Coverage statistics
- `ontology_relationships` - Component relationships

---

## Key Implementations

### Performance Optimizations

| Implementation | File | Ontology Ref |
|----------------|------|--------------|
| PeopleManager.with_full_details | `apps/peoples/managers.py:82` | `apps.peoples.managers.PeopleManager.with_full_details` |
| NOCIncidentManager.with_full_details | `apps/noc/models/incident.py:21` | `apps.noc.models.incident.NOCIncidentManager.with_full_details` |
| OptimizedManager | `apps/core/managers/optimized_managers.py:192` | `apps.core.managers.optimized_managers.OptimizedManager` |
| NPlusOneDetector | `apps/core/utils_new/query_optimizer.py` | `apps.core.utils_new.query_optimizer.NPlusOneDetector` |
| QueryOptimizer | `apps/core/services/query_optimization_service.py` | `apps.core.services.query_optimization_service.QueryOptimizer` |

### Premium Features

| Implementation | File | Ontology Ref |
|----------------|------|--------------|
| SecureFileDownloadService | `apps/core/services/secure_file_download_service.py` | `apps.core.services.secure_file_download_service.SecureFileDownloadService` |
| SessionRevokeView | `apps/peoples/api/session_views.py` | `apps.peoples.api.session_views.SessionRevokeView` |
| WorkerMetricsService | `apps/performance_analytics/services/` | Various |

---

## Test Coverage

### Performance Patterns

- ✅ `apps/noc/tests/test_performance/test_n1_optimizations.py:277`
- ✅ `apps/peoples/tests/test_user_model.py:213`
- ✅ `apps/peoples/tests/test_user_integration.py:358`
- ✅ `apps/work_order_management/tests/test_work_order_crud.py:132`

### Premium Features

- ✅ Security tests in `apps/core/tests/test_comprehensive_security_fixes.py`
- ✅ Performance analytics tests in `apps/performance_analytics/tests/`

---

## Metrics

### Coverage Statistics

- **Total Components**: 63+ registered
- **Domains**: 15+ unique domains
- **Tags**: 30+ unique tags
- **Critical Components**: 15+ (high criticality)
- **Test Coverage**: 100% of registered components

### Impact Metrics

| Category | Metric | Value |
|----------|--------|-------|
| **Query Reduction** | NOC Incidents | 97% (101→3 queries) |
| **Query Reduction** | People List | 99.7% (301→1 query) |
| **Query Reduction** | Reports | 96% (102→4 queries) |
| **Revenue Impact** | Premium Features | $1.4M ARR potential |
| **Apps Optimized** | Performance | 9 apps |
| **Security Fixes** | CSRF Protection | 6 endpoints |

---

## Maintenance

### Adding New Patterns

1. **Create Registration**:
   ```python
   # In apps/ontology/registrations/your_domain.py
   def register_your_patterns():
       patterns = [
           {
               "qualified_name": "your.pattern.name",
               "type": "concept",
               "domain": "your.domain",
               "purpose": "Description",
               # ...
           }
       ]
       OntologyRegistry.bulk_register(patterns)
   ```

2. **Create Management Command** (optional):
   ```python
   # In apps/ontology/management/commands/load_your_patterns.py
   from django.core.management.base import BaseCommand
   
   class Command(BaseCommand):
       def handle(self, *args, **options):
           register_your_patterns()
   ```

3. **Update Documentation**:
   - Add to this index
   - Create domain-specific guide
   - Update main README

### Updating Existing Patterns

1. Modify registration in `apps/ontology/registrations/`
2. Reload: `python manage.py load_<domain>_ontology`
3. Verify: `OntologyRegistry.get("pattern.name")`
4. Update documentation

---

## Troubleshooting

### Patterns Not Loading

```python
# Check if patterns are registered
from apps.ontology.registry import OntologyRegistry
stats = OntologyRegistry.get_statistics()
print(stats)

# Reload manually
from apps.ontology.registrations.performance_optimization_patterns import register_performance_optimization_patterns
register_performance_optimization_patterns()
```

### Search Not Finding Components

```python
# Try different search fields
results = OntologyRegistry.search("your_term", fields=["qualified_name", "purpose", "tags"])

# Or search by domain
results = OntologyRegistry.get_by_domain("performance.database")
```

### Statistics Not Accurate

```python
# Clear and reload
OntologyRegistry.clear()
register_november_2025_improvements()
register_performance_optimization_patterns()

# Verify
stats = OntologyRegistry.get_statistics()
```

---

## Related Documentation

### Architecture

- [QUERY_OPTIMIZATION_ARCHITECTURE.md](../architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md)
- [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)

### Deliverables

- [N1_OPTIMIZATION_PART2_DELIVERABLES.md](../../N1_OPTIMIZATION_PART2_DELIVERABLES.md)
- [COMPLETE_IMPLEMENTATION_MANIFEST_NOV_6_2025.md](../../COMPLETE_IMPLEMENTATION_MANIFEST_NOV_6_2025.md)

### Testing

- [TESTING_AND_QUALITY_GUIDE.md](../testing/TESTING_AND_QUALITY_GUIDE.md)

---

**Maintained By**: Development Team  
**Review Cycle**: Monthly or on major feature additions  
**Last Review**: November 6, 2025
