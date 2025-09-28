# Code Deduplication - Developer Quick Reference

**Purpose:** Quick guide for using new mixins and services to eliminate code duplication

**Last Updated:** 2025-09-27

---

## 🚀 **Quick Start: Creating a New CRUD View**

### Minimal CRUD View (15 lines)

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import View
from apps.core.mixins import (
    CRUDActionMixin,
    ExceptionHandlingMixin,
    StandardFormProcessingMixin,
)

class MyView(
    CRUDActionMixin,
    ExceptionHandlingMixin,
    StandardFormProcessingMixin,
    LoginRequiredMixin,
    View
):
    crud_config = {
        "template_list": "myapp/list.html",
        "template_form": "myapp/form.html",
        "model": MyModel,
        "form": MyForm,
        "related": ["field1", "field2"],
        "fields": ["id", "name", "code"],
    }

    def post(self, request):
        return self.handle_exceptions(request, self._process_post)

    def _process_post(self, request):
        return self.process_form_post(request)
```

**That's it!** This gives you:
- ✅ List view with JSON API
- ✅ Create form
- ✅ Update form
- ✅ Delete confirmation
- ✅ Automatic exception handling
- ✅ Correlation ID tracking
- ✅ Automatic userinfo tracking

---

## 📋 **Mixin Reference**

### CRUDActionMixin

**When to use:** Every view with standard CRUD operations

**Configuration:**
```python
crud_config = {
    "template_list": "path/to/list.html",       # Required
    "template_form": "path/to/form.html",       # Required
    "model": MyModel,                           # Required
    "form": MyForm,                             # Required
    "form_name": "myform",                      # Optional (default: "form")
    "related": ["fk1", "fk2"],                  # Optional
    "fields": ["field1", "field2"],             # Optional
    "list_method": "get_custom_listview",       # Optional (default: generic)
}
```

**Custom Actions:**
```python
def handle_custom_action(self, request, action, config):
    if action == "export":
        return self.export_data(request)
    if action == "custom":
        return self.custom_logic(request)
    return None  # Let mixin handle standard actions
```

**Custom Context:**
```python
def get_template_context(self, request):
    return {"extra": "data"}

def get_form_context(self, request, form, is_update, instance=None):
    return {"myform": form, "msg": "Custom message"}
```

---

### ExceptionHandlingMixin

**When to use:** Every view that needs consistent error handling

**Usage:**
```python
def post(self, request):
    return self.handle_exceptions(request, self._process_post)

def _process_post(self, request):
    # Your logic here - exceptions automatically caught
    if something_wrong:
        raise ValidationError("Descriptive error message")
    return JsonResponse({"success": True})
```

**Decorator Style:**
```python
from apps.core.mixins import with_exception_handling

class MyView(ExceptionHandlingMixin, View):
    @with_exception_handling
    def post(self, request):
        # Exceptions automatically handled
        ...
```

**Exception to Status Code Mapping:**
- `ValidationError` → 400
- `ActivityManagementException` → 422
- `BusinessLogicException` → 422
- `PermissionDenied` → 403
- `ObjectDoesNotExist` → 404
- `ValueError`, `TypeError` → 400
- `IntegrityError`, `DatabaseError` → 422
- `SystemException` → 500

---

### TenantAwareFormMixin

**When to use:** Forms with ForeignKey/ManyToMany fields that need tenant filtering

**Usage:**
```python
from apps.core.mixins import TenantAwareFormMixin

class MyForm(TenantAwareFormMixin, forms.ModelForm):
    tenant_filtered_fields = {
        'asset': {
            'model': Asset,
            'filter_by': 'bu_id',                          # bu_id from session
            'extra_filters': Q(status='active'),           # Additional filters
            'select_related': ['parent', 'location'],      # Optimization
        },
        'location': {
            'model': Location,
            'filter_by': 'client_id',                      # client_id from session
        },
    }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)
        self.apply_tenant_filters()  # Apply automatic filtering
```

**Session Keys:**
- `bu_id` - Business unit ID
- `client_id` - Client ID
- `sites` → `assignedsites` - Multiple site IDs

---

### TypeAssistFilterMixin

**When to use:** Forms with TypeAssist dropdown fields

**Usage:**
```python
from apps.core.mixins import TypeAssistFilterMixin

class MyForm(TypeAssistFilterMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        self.apply_typeassist_filters({
            'type': 'ASSETTYPE',
            'category': 'ASSETCATEGORY',
            'subcategory': 'ASSETSUBCATEGORY',
        })
```

---

### ValidatedFormProcessingMixin

**When to use:** Views that process form POST requests

**Simple Usage (StandardFormProcessingMixin):**
```python
from apps.core.mixins import StandardFormProcessingMixin

class MyView(StandardFormProcessingMixin, View):
    crud_config = {"form": MyForm, "model": MyModel}

    def post(self, request):
        return self.handle_exceptions(request, self._process_post)

    def _process_post(self, request):
        return self.process_form_post(request)

    # Optional: Override to customize save
    def save_model(self, form, request, is_create):
        instance = form.save(commit=False)
        instance.custom_field = "value"
        instance.save()
        return instance
```

**Advanced Usage (with Service Layer):**
```python
from apps.core.mixins import ValidatedFormProcessingMixin

class MyView(ValidatedFormProcessingMixin, View):
    def __init__(self):
        super().__init__()
        self.service = MyService()

    def process_valid_form(self, form, request, is_create):
        if is_create:
            result = self.service.create(form.cleaned_data, request.user)
        else:
            result = self.service.update(form.instance.id, form.cleaned_data)

        if result.success:
            return {"pk": result.id}
        else:
            return JsonResponse({"error": result.error}, status=422)
```

---

## 🏢 **Service Layer Reference**

### Creating a Service

```python
from apps.core.services.base_service import BaseService
from dataclasses import dataclass

@dataclass
class MyOperationResult:
    success: bool
    data: Any = None
    error_message: str = None

class MyService(BaseService):
    def get_service_name(self):
        return "MyService"

    @BaseService.monitor_performance("my_operation")
    def my_operation(self, data, user):
        try:
            with self.database_transaction():
                # Business logic here
                obj = MyModel.objects.create(**data)
                return MyOperationResult(success=True, data=obj)

        except IntegrityError as e:
            return MyOperationResult(
                success=False,
                error_message="Duplicate entry"
            )
```

### Using Service Metrics

```python
service = MyService()
service.my_operation(data, user)

metrics = service.get_service_metrics()
print(f"Calls: {metrics['call_count']}")
print(f"Avg Duration: {metrics['average_duration']}s")
print(f"Error Rate: {metrics['error_rate']}%")
print(f"Cache Hit Rate: {metrics['cache_hit_rate']}%")
```

### Service Transaction Management

```python
with self.database_transaction():
    # All operations in single transaction
    obj1 = Model1.objects.create(...)
    obj2 = Model2.objects.create(...)
    # Auto-commits or auto-rollbacks
```

### Service Caching

```python
def get_expensive_data(self, key):
    cached = self.get_cached_data(f"myservice:{key}", ttl=600)
    if cached:
        return cached

    data = self._compute_expensive_data(key)
    self.set_cached_data(f"myservice:{key}", data, ttl=600)
    return data
```

---

## 🎯 **Common Patterns**

### Pattern 1: Simple List + Form View

```python
class MyView(CRUDActionMixin, ExceptionHandlingMixin, StandardFormProcessingMixin, LoginRequiredMixin, View):
    crud_config = {
        "template_list": "app/list.html",
        "template_form": "app/form.html",
        "model": MyModel,
        "form": MyForm,
    }

    def post(self, request):
        return self.handle_exceptions(request, lambda r: self.process_form_post(r))
```

### Pattern 2: View with Custom Business Logic

```python
class MyView(CRUDActionMixin, ExceptionHandlingMixin, ValidatedFormProcessingMixin, LoginRequiredMixin, View):
    def __init__(self):
        super().__init__()
        self.service = MyService()

    def process_valid_form(self, form, request, is_create):
        result = self.service.create_or_update(
            form.cleaned_data,
            request.user,
            is_create
        )
        return {"pk": result.id} if result.success else JsonResponse(
            {"error": result.error}, status=422
        )
```

### Pattern 3: View with Custom GET Actions

```python
class MyView(CRUDActionMixin, LoginRequiredMixin, View):
    crud_config = {...}

    def handle_custom_action(self, request, action, config):
        if action == "export":
            return self.export_to_csv(request)
        if action == "stats":
            return JsonResponse({"stats": self.get_stats()})
        return None  # Standard actions handled by mixin
```

---

## 🔧 **Troubleshooting**

### Issue: Mixin methods not being called

**Problem:** Method resolution order (MRO) is incorrect

**Solution:** Ensure mixins come BEFORE view base classes
```python
# WRONG: View comes first
class MyView(View, CRUDActionMixin):
    pass

# CORRECT: Mixins come first
class MyView(CRUDActionMixin, View):
    pass
```

### Issue: Config not found

**Problem:** View has neither P, params, nor crud_config

**Solution:** Define one of these attributes
```python
class MyView(CRUDActionMixin, View):
    crud_config = {"model": MyModel, ...}  # Option 1
    # OR
    P = {"model": MyModel, ...}            # Option 2 (legacy)
    # OR
    params = {"model": MyModel, ...}       # Option 3 (legacy)
```

### Issue: Form not getting request

**Problem:** Form __init__ expects request parameter

**Solution:** Always pop request in form __init__
```python
def __init__(self, *args, **kwargs):
    self.request = kwargs.pop('request')  # MUST pop before super()
    super().__init__(*args, **kwargs)
```

### Issue: Transaction not working

**Problem:** Nested transactions causing issues

**Solution:** Use service layer for transaction management
```python
# AVOID: Nested transactions
with transaction.atomic():
    with transaction.atomic():  # Problematic
        ...

# PREFER: Service layer handles transactions
service.my_operation(...)  # Transaction inside service
```

---

## 📊 **Migration Checklist**

When refactoring an existing view:

- [ ] Create/identify domain service if needed
- [ ] Create `{view_name}_refactored.py` file
- [ ] Inherit from appropriate mixins
- [ ] Define `crud_config` dictionary
- [ ] Implement `post()` with exception handling
- [ ] Implement `process_valid_form()` or use StandardFormProcessingMixin
- [ ] Override `handle_custom_action()` for custom actions
- [ ] Create unit tests for custom logic
- [ ] Run regression tests comparing old vs new
- [ ] Update URL routing to use refactored view
- [ ] Delete or archive original file

---

## 🎓 **Best Practices**

### DO ✅
- Inherit mixins in order: CRUD, Exception, Form, Auth, View
- Use service layer for business logic
- Use StandardFormProcessingMixin for simple saves
- Override hooks for customization (handle_custom_action, get_form_context)
- Write tests for custom logic
- Use correlation IDs for debugging

### DON'T ❌
- Don't put business logic in views
- Don't use generic `except Exception`
- Don't skip transaction.atomic for multi-step operations
- Don't expose debug info in errors
- Don't nest transactions unnecessarily

---

## 📚 **Additional Resources**

- **Mixins Package:** `apps/core/mixins/`
- **Services Package:** `apps/core/services/`, `apps/*/services/`
- **Examples:**
  - `apps/activity/views/asset/crud_views_refactored.py`
  - `apps/activity/views/job_views_refactored.py`
  - `apps/activity/forms/asset_form_refactored.py`
- **Tests:** `apps/core/tests/test_*_mixin.py`
- **Summary:** `CODE_DEDUPLICATION_PHASE2_COMPLETE.md`

---

## 🆘 **Getting Help**

1. Check usage examples in this guide
2. Review existing refactored views
3. Read mixin docstrings (comprehensive)
4. Check test files for usage patterns
5. Ask team lead for code review

---

**Remember:** The goal is to eliminate duplication while maintaining functionality. When in doubt, create a refactored version alongside the original, test thoroughly, then swap.