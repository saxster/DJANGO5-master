# Performance Optimization Quick Reference

**Quick lookup guide for performance patterns in the ontology**

---

## 🚀 Quick Queries

```python
from apps.ontology.registry import OntologyRegistry

# Get N+1 problem explanation
n1 = OntologyRegistry.get("concepts.n_plus_one_query_problem")

# Get all performance concepts
perf = OntologyRegistry.get_by_domain("performance.database")

# Find optimization examples
examples = OntologyRegistry.get_by_tag("example")

# Search for specific pattern
results = OntologyRegistry.search("select_related")
```

---

## 📊 Concept Cheat Sheet

| Concept | When to Use | Example |
|---------|-------------|---------|
| `select_related` | ForeignKey, OneToOne (forward) | `People.objects.select_related('profile')` |
| `prefetch_related` | ManyToMany, Reverse FK | `Task.objects.prefetch_related('assigned_people')` |
| `Prefetch` object | Nested optimizations | `Prefetch('alerts', queryset=...optimized...)` |
| `with_full_details()` | Reusable optimization | `People.objects.with_full_details()` |
| `assertNumQueries` | Testing query count | `with self.assertNumQueries(1):` |

---

## 🔍 Decision Tree

```
Need to optimize a query?
│
├─ ForeignKey/OneToOne relationship?
│  └─ Use: select_related('field_name')
│     Ontology: concepts.select_related
│
├─ ManyToMany/Reverse FK?
│  └─ Use: prefetch_related('field_name')
│     Ontology: concepts.prefetch_related
│
├─ Nested relationships?
│  └─ Use: Prefetch object with to_attr
│     Ontology: concepts.prefetch_object
│
├─ Want reusable pattern?
│  └─ Create: custom manager with with_full_details()
│     Ontology: concepts.custom_manager_methods
│
└─ Detect N+1 issues?
   └─ Use: NPlusOneDetector or @detect_n_plus_one
      Ontology: apps.core.utils_new.query_optimizer.NPlusOneDetector
```

---

## 💡 Common Patterns (from Ontology)

### Pattern 1: People with Profile
```python
# Ontology: examples.people_manager_optimization
# Impact: 301 queries → 1 query (99.7% reduction)

users = People.objects.select_related('profile', 'organizational', 'shift')
```

### Pattern 2: NOC Incident with Alerts
```python
# Ontology: examples.noc_incident_optimization
# Impact: 101 queries → 3 queries (97% reduction)

incidents = NOCIncident.objects.select_related(
    'site', 'severity'
).prefetch_related('alerts', 'notifications')
```

### Pattern 3: Nested Prefetch
```python
# Ontology: concepts.prefetch_object

from django.db.models import Prefetch

incidents = NOCIncident.objects.prefetch_related(
    Prefetch(
        'alerts',
        queryset=NOCAlert.objects.select_related('device'),
        to_attr='cached_alerts'
    )
)
```

---

## ⚠️ Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution | Ontology Ref |
|--------------|---------|----------|--------------|
| Over-prefetching | Wastes memory | Use `minimal` profile | `anti_patterns.over_prefetching` |
| Missing to_attr | Re-queries data | Add `to_attr='name'` | `anti_patterns.missing_to_attr` |
| Query in loop | N+1 problem | Use `filter(id__in=ids)` | `anti_patterns.queryset_in_loop` |

---

## 🧪 Testing Patterns

### Basic Query Count Test
```python
# Ontology: concepts.assertNumQueries

def test_optimized_query(self):
    with self.assertNumQueries(1):
        users = list(People.objects.select_related('profile'))
        for user in users:
            _ = user.profile.gender  # No extra query
```

### Complex Optimization Test
```python
# Ontology: concepts.query_count_testing

def test_with_full_details(self):
    '''Verify with_full_details() reduces queries.'''
    with self.assertNumQueries(3):  # 1 main + 2 prefetch
        incident = NOCIncident.objects.with_full_details().first()
        _ = incident.alerts.all()
        _ = incident.site.name
```

---

## 🔧 Implementation Quick Start

### Step 1: Create Optimized Manager
```python
# Ontology: concepts.custom_manager_methods

from apps.core.managers.optimized_managers import OptimizedManager

class MyModelManager(OptimizedManager):
    def with_full_details(self):
        return self.select_related(
            'fk1', 'fk2'
        ).prefetch_related('m2m1', 'm2m2')
```

### Step 2: Add to Model
```python
class MyModel(models.Model):
    # ... fields ...
    
    objects = MyModelManager()
```

### Step 3: Use in Views
```python
# Ontology: apps.core.utils_new.query_optimizer.NPlusOneDetector

from apps.core.utils_new.query_optimizer import detect_n_plus_one

@detect_n_plus_one  # Auto-detect N+1 in development
def my_view(request):
    items = MyModel.objects.with_full_details()
    return render(request, 'template.html', {'items': items})
```

### Step 4: Add Tests
```python
# Ontology: concepts.query_count_testing

def test_my_model_optimization(self):
    with self.assertNumQueries(3):
        items = list(MyModel.objects.with_full_details()[:10])
```

---

## 📚 Learn More

### Ontology Commands
```bash
# Load performance patterns
python manage.py load_performance_ontology --stats

# Extract all ontology
python manage.py extract_ontology

# Search via Claude Code
/ontology performance
```

### Key Documentation
- **Complete Guide**: `docs/ontology/PERFORMANCE_OPTIMIZATION_ONTOLOGY.md`
- **Architecture**: `docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md`
- **Deliverables**: `N1_OPTIMIZATION_PART2_DELIVERABLES.md`

### Real Implementations
- **People**: `apps/peoples/managers.py:82`
- **NOC**: `apps/noc/models/incident.py:21`
- **Activity**: `apps/activity/models/job_model.py`
- **Base**: `apps/core/managers/optimized_managers.py:192`

---

## 🎯 By Use Case

### Optimizing List Views
```python
# Search ontology
examples = OntologyRegistry.search("with_full_details")
# Shows People, NOC, Job examples
```

### Debugging Slow Queries
```python
# Use detector
from apps.core.utils_new.query_optimizer import NPlusOneDetector

with NPlusOneDetector(threshold=5) as detector:
    # Your code
    if detector.has_issues():
        print(detector.get_report())
```

### Writing Tests
```python
# Query ontology for patterns
testing = OntologyRegistry.get_by_domain("performance.testing")
# Shows assertNumQueries, benchmarking, query count patterns
```

---

**💡 Tip**: Use `/ontology performance` in Claude Code to load all patterns!
