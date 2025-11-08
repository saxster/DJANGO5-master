# Django Model Meta Standards - Quick Reference

**Last Updated**: November 6, 2025  
**Applies To**: All Django models in `apps/`

---

## Required Meta Properties

Every Django model MUST have a complete `Meta` class with:

1. ✅ **verbose_name** - Human-readable singular name
2. ✅ **verbose_name_plural** - Grammatically correct plural
3. ✅ **ordering** - Default query ordering
4. ✅ **indexes** - Performance indexes for common queries

---

## Standard Template

```python
from django.db import models
from django.utils.translation import gettext_lazy as _

class YourModel(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Your Model")
        verbose_name_plural = _("Your Models")
        ordering = ['-created_at', 'name']
        db_table = 'your_model'  # Optional: custom table name
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self):
        return self.name
```

---

## Ordering Best Practices

### Chronological Models (Logs, Events, History)
```python
ordering = ['-created_at']  # Newest first
ordering = ['-timestamp', 'id']  # Newest first, ID tiebreaker
```

**Examples**: DeviceEventLog, Attachment, StreamEvent

### Name-Based Models (Master Data)
```python
ordering = ['name']  # Alphabetical
ordering = ['name', 'code']  # Name + code tiebreaker
```

**Examples**: Location, People, Client

### Status-Based Models
```python
ordering = ['status', '-created_at']  # Status first, then chronological
ordering = ['priority', '-created_at']  # Priority, then recent
```

**Examples**: Task, Ticket, WorkOrder

---

## Verbose Name Examples

### Simple Models
```python
verbose_name = "Location"
verbose_name_plural = "Locations"
```

### Compound Names
```python
verbose_name = "Device Event Log"
verbose_name_plural = "Device Event Logs"
```

### Irregular Plurals
```python
verbose_name = "Category"
verbose_name_plural = "Categories"  # NOT "Categorys"

verbose_name = "Person"
verbose_name_plural = "People"  # NOT "Persons"
```

---

## Index Strategy

### Rule 1: Index Ordering Fields
```python
ordering = ['-created_at', 'name']

indexes = [
    models.Index(fields=['created_at']),  # For ordering
    models.Index(fields=['name']),        # For tiebreaker
]
```

### Rule 2: Index Common Filters
```python
# If you filter by status + date often
indexes = [
    models.Index(fields=['status', 'created_at']),
]
```

### Rule 3: Index Foreign Keys
```python
# Django auto-indexes FKs, but compound indexes help
indexes = [
    models.Index(fields=['client', 'bu']),  # Multi-tenant queries
    models.Index(fields=['owner', 'created_at']),  # User history
]
```

---

## Inheritance Patterns

### Inheriting from BaseModel
```python
class Location(BaseModel, TenantAwareModel):
    name = models.CharField(max_length=100)
    
    class Meta(BaseModel.Meta):  # Inherit parent Meta
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ['name']  # Override parent ordering
        db_table = "location"
```

### Multiple Inheritance
```python
class MyModel(BaseModel, TenantAwareModel):
    # ...
    
    class Meta(BaseModel.Meta, TenantAwareModel.Meta):
        verbose_name = "My Model"
        ordering = ['-created_at']
```

---

## Common Mistakes

### ❌ Missing Plural
```python
class Meta:
    verbose_name = "Category"
    # Missing verbose_name_plural - will auto-generate "Categorys"
```

### ✅ Correct
```python
class Meta:
    verbose_name = "Category"
    verbose_name_plural = "Categories"
```

---

### ❌ No Ordering
```python
class Meta:
    verbose_name = "Event"
    # Missing ordering - results in random order
```

### ✅ Correct
```python
class Meta:
    verbose_name = "Event"
    ordering = ['-timestamp']
```

---

### ❌ Ordering Without Index
```python
class Meta:
    ordering = ['-created_at']
    # Missing index - will cause table scans on large tables
```

### ✅ Correct
```python
class Meta:
    ordering = ['-created_at']
    indexes = [
        models.Index(fields=['created_at']),
    ]
```

---

## Validation

### Check Your Models
```bash
# Run the validation script
python scripts/check_model_meta_completeness.py

# Output shows missing properties
Found 5 models with incomplete Meta classes:
  Location: Missing ordering
  Attachment: Missing verbose_name
  ...
```

### Django Check Framework
```bash
# Django's built-in checks
python manage.py check

# Check for index issues
python manage.py makemigrations --dry-run
```

---

## Migration Impact

### Meta Changes That Require Migrations

**YES - Creates Migration**:
- Adding `db_table`
- Adding `indexes`
- Adding `constraints`
- Changing `unique_together`

**NO - Python Only**:
- Adding `verbose_name`
- Adding `verbose_name_plural`
- Adding `ordering`
- Changing `get_latest_by`

### Example Migration
```bash
# Generate migrations for new indexes
python manage.py makemigrations activity

# Review the migration
cat apps/activity/migrations/0042_auto_20251106_1234.py

# Apply migration
python manage.py migrate activity
```

---

## Admin Interface Impact

### Before Meta Improvements
```
Select deviceeventlog to change
Add deviceeventlog
3 deviceeventlogs
```

### After Meta Improvements
```
Select Device Event Log to change
Add Device Event Log
3 Device Event Logs
```

**Result**: Professional, readable admin interface

---

## Performance Testing

### Check Query Performance
```python
# In Django shell
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as queries:
    list(Location.objects.all()[:100])
    
for query in queries:
    print(query['sql'])
    print(f"Time: {query['time']}")
```

### Expected Results
- Queries should use indexes (check EXPLAIN)
- Order by should not cause filesort on large tables
- Response time < 100ms for typical queries

---

## Code Review Checklist

When reviewing model changes, verify:

- [ ] `verbose_name` present and human-readable
- [ ] `verbose_name_plural` present and grammatically correct
- [ ] `ordering` defined and appropriate for model type
- [ ] Indexes added for ordering fields
- [ ] Indexes added for common query patterns
- [ ] `__str__` method returns meaningful representation
- [ ] Migration generated if indexes added
- [ ] Tests updated if ordering affects assertions

---

## Examples by Model Type

### Event/Log Models
```python
class DeviceEventLog(BaseModel):
    device_id = models.CharField(max_length=55)
    received_on = models.DateTimeField(auto_now_add=True)
    
    class Meta(BaseModel.Meta):
        verbose_name = "Device Event Log"
        verbose_name_plural = "Device Event Logs"
        ordering = ['-received_on', 'device_id']
        db_table = "deviceeventlog"
        indexes = [
            models.Index(fields=['device_id', 'received_on']),
            models.Index(fields=['received_on']),
        ]
```

### Master Data Models
```python
class Location(BaseModel):
    name = models.CharField(max_length=250)
    code = models.CharField(max_length=50)
    
    class Meta(BaseModel.Meta):
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ['name', 'code']
        db_table = "location"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['code']),
        ]
```

### Transaction Models
```python
class Attachment(BaseModel):
    filename = models.ImageField()
    datetime = models.DateTimeField()
    
    class Meta(BaseModel.Meta):
        verbose_name = "Attachment"
        verbose_name_plural = "Attachments"
        ordering = ['-datetime', 'filename']
        db_table = "attachment"
        indexes = [
            models.Index(fields=['datetime']),
            models.Index(fields=['owner', 'datetime']),
        ]
```

---

## Tools & Resources

### Validation Tools
- `scripts/check_model_meta_completeness.py` - Audit all models
- `python manage.py check` - Django system checks
- Pre-commit hooks (planned)

### Documentation
- Django Meta Options: https://docs.djangoproject.com/en/5.2/ref/models/options/
- Database Indexes: https://docs.djangoproject.com/en/5.2/ref/models/indexes/
- CLAUDE.md: Architecture standards

### Related Standards
- File size limits: Models < 150 lines
- Method limits: Methods < 30 lines
- Single responsibility principle

---

## FAQ

**Q: Do I need verbose_name if using gettext_lazy on fields?**  
A: Yes, Meta verbose_name is for the model itself, field verbose_name is for individual fields.

**Q: Can I skip ordering on abstract models?**  
A: Yes, abstract models don't need ordering. Concrete models inheriting from them should add it.

**Q: Should proxy models have their own Meta?**  
A: Yes, proxy models should override verbose_name but can reuse parent's ordering.

**Q: How many indexes is too many?**  
A: Generally 3-5 indexes per model. More indexes = slower writes. Measure with real queries.

**Q: Do I need to update tests when changing ordering?**  
A: Yes, if tests assert on list order or use `.first()` / `.last()`, update assertions.

---

**Maintained By**: Development Team  
**Review Cycle**: Quarterly or when adding new models  
**Last Audit**: November 6, 2025 (23 models identified for updates)
