# DateTimeField Standardization Guide

This guide establishes standardized patterns for DateTimeField usage across the Django application.

## ✅ **Recommended Patterns**

### 1. **Creation Timestamps (Non-editable)**
```python
created_at = models.DateTimeField(auto_now_add=True)
```
- **Use for**: Record creation time that never changes
- **Benefits**: Automatically set on record creation, non-editable
- **Examples**: User registration time, model instance creation

### 2. **Last Modified Timestamps (Non-editable)**
```python
updated_at = models.DateTimeField(auto_now=True)
```
- **Use for**: Last modification time that updates automatically
- **Benefits**: Automatically updated on every save
- **Examples**: Profile updates, record modifications

### 3. **Event/User-defined Timestamps (Editable)**
```python
event_datetime = models.DateTimeField(default=timezone.now)
```
- **Use for**: User-defined or event-specific times
- **Benefits**: Editable with sensible default
- **Examples**: Meeting times, upload timestamps, event scheduling

### 4. **Optional Timestamps**
```python
completed_at = models.DateTimeField(null=True, blank=True)
```
- **Use for**: Optional completion/status times
- **Benefits**: Can remain empty until set
- **Examples**: Task completion, workflow milestones

## 🔧 **Implementation Examples**

### Standard Model Pattern
```python
from django.db import models
from django.utils import timezone

class StandardModel(models.Model):
    # Creation timestamp (auto-set, non-editable)
    created_at = models.DateTimeField(auto_now_add=True)

    # Last modified timestamp (auto-update, non-editable)
    updated_at = models.DateTimeField(auto_now=True)

    # Event timestamp (editable with default)
    event_time = models.DateTimeField(default=timezone.now)

    # Optional completion timestamp
    completed_at = models.DateTimeField(null=True, blank=True)
```

### Workflow/Process Model Pattern
```python
class WorkflowModel(models.Model):
    # Process started (creation time)
    started_at = models.DateTimeField(auto_now_add=True)

    # Last activity (auto-update on save)
    last_activity_at = models.DateTimeField(auto_now=True)

    # Optional completion time
    completed_at = models.DateTimeField(null=True, blank=True)

    # Optional milestone times
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
```

## ❌ **Anti-patterns to Avoid**

### 1. **Manual defaults for creation timestamps**
```python
# ❌ AVOID
created_at = models.DateTimeField(default=timezone.now)

# ✅ USE INSTEAD
created_at = models.DateTimeField(auto_now_add=True)
```

### 2. **Manual defaults for last-modified timestamps**
```python
# ❌ AVOID
updated_at = models.DateTimeField(default=timezone.now)

# ✅ USE INSTEAD
updated_at = models.DateTimeField(auto_now=True)
```

### 3. **Legacy naming patterns**
```python
# ❌ AVOID
cdtz = models.DateTimeField(...)  # Unclear abbreviation
mdtz = models.DateTimeField(...)  # Unclear abbreviation

# ✅ USE INSTEAD
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

### 4. **Non-timezone-aware defaults**
```python
# ❌ AVOID
from datetime import datetime
timestamp = models.DateTimeField(default=datetime.now)  # Not timezone-aware

# ✅ USE INSTEAD
from django.utils import timezone
timestamp = models.DateTimeField(default=timezone.now)  # Timezone-aware
```

## 🎯 **Field Naming Conventions**

### Standard Names
- `created_at` - Record creation time
- `updated_at` - Last modification time
- `started_at` - Process/workflow start time
- `completed_at` - Process/workflow completion time
- `expires_at` - Expiration time
- `scheduled_at` - Scheduled execution time
- `last_activity_at` - Last activity/interaction time

### Domain-specific Names
- `workflow_started_at` - Workflow initiation
- `last_escalated_at` - Last escalation time
- `reported_at` - Issue/violation reporting time
- `detected_at` - Detection/discovery time
- `checked_at` - Health check/monitoring time

## 📊 **Migration Considerations**

When updating existing DateTimeField configurations:

1. **Ensure data preservation**:
   ```python
   # In migration files, preserve existing data
   operations = [
       migrations.AlterField(
           model_name='mymodel',
           name='created_at',
           field=models.DateTimeField(auto_now_add=True),
           preserve_default=False,
       ),
   ]
   ```

2. **Handle timezone awareness**:
   - Ensure all existing datetime data is timezone-aware
   - Use Django's timezone utilities for migrations

3. **Test thoroughly**:
   - Verify timestamp behavior in tests
   - Check serialization/deserialization
   - Validate API responses

## 🔍 **Code Review Checklist**

- [ ] Creation timestamps use `auto_now_add=True`
- [ ] Last-modified timestamps use `auto_now=True`
- [ ] User/event timestamps use `default=timezone.now`
- [ ] Optional timestamps use `null=True, blank=True`
- [ ] Field names follow conventions (`created_at`, `updated_at`)
- [ ] All defaults use timezone-aware functions
- [ ] Help text describes field purpose
- [ ] Database indexes added where needed

## 🎯 **Benefits of Standardization**

1. **Consistency**: Uniform patterns across all models
2. **Maintainability**: Clear field purposes and behaviors
3. **Performance**: Proper indexing and query optimization
4. **Reliability**: Timezone-aware, automatic timestamp management
5. **Developer Experience**: Predictable field behavior

---

*Last Updated: 2025-01-15*
*Standards Version: 1.0*