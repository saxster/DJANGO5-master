# Code Deduplication - Migration Guide

**Purpose:** Step-by-step guide for migrating existing views and forms to use new mixins
**Target Audience:** Development team
**Last Updated:** 2025-09-27

---

## 🎯 **Migration Strategy**

### Phase Approach
1. **Pilot:** Migrate 1-2 views to validate approach
2. **Iterate:** Refine based on lessons learned
3. **Scale:** Migrate remaining views systematically
4. **Cleanup:** Remove legacy code after validation

### Safety Principles
- ✅ Never modify original files directly
- ✅ Create `*_refactored.py` files alongside originals
- ✅ Run regression tests before/after
- ✅ Keep both versions running during pilot
- ✅ Use feature flags for gradual rollout

---

## 📋 **Step-by-Step Migration**

### Step 1: Analyze Current View

**Checklist:**
- [ ] Identify view type (CRUD, list-only, form-only)
- [ ] Count lines of code (target < 30 per method)
- [ ] List custom actions (beyond standard CRUD)
- [ ] Identify business logic to extract
- [ ] Note exception handling patterns
- [ ] Check if service layer exists

**Example Analysis:**
```python
# Current: AssetView (160 lines)
# - GET method: 60 lines (standard CRUD + 2 custom actions)
# - POST method: 100 lines (validation + 8 exception types + business logic)
# - Custom actions: qrdownload, fetchStatus
# - Business logic: save asset + extras + quality assessment
# - Service needed: AssetManagementService
```

---

### Step 2: Create or Identify Service

**If business logic exists in view:**

```python
# 1. Create service file: apps/{app}/services/{model}_service.py

from apps.core.services.base_service import BaseService
from dataclasses import dataclass

@dataclass
class MyOperationResult:
    success: bool
    instance: Any = None
    error_message: str = None

class MyManagementService(BaseService):
    def get_service_name(self):
        return "MyManagementService"

    @BaseService.monitor_performance("create")
    def create(self, data, user, session):
        try:
            with self.database_transaction():
                # Extract logic from handle_valid_form
                instance = MyModel(**data)
                instance = putils.save_userinfo(instance, user, session, create=True)
                return MyOperationResult(success=True, instance=instance)
        except IntegrityError:
            return MyOperationResult(success=False, error_message="Duplicate")

# 2. Update apps/{app}/services/__init__.py
from .my_service import MyManagementService
__all__ = ['MyManagementService', ...]
```

---

### Step 3: Create Refactored View

**Template:**

```python
"""
{Model} Views - Refactored Version

COMPARISON:
- Original: {X} lines
- Refactored: {Y} lines
- Reduction: {Z}%

Following .claude/rules.md:
- View methods < 30 lines (Rule 8)
- Business logic in service layer (Rule 8)
- Specific exception handling (Rule 11)
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import View
from django.http import JsonResponse

from apps.core.mixins import (
    CRUDActionMixin,
    ExceptionHandlingMixin,
    ValidatedFormProcessingMixin,  # Or StandardFormProcessingMixin
)

class MyViewRefactored(
    CRUDActionMixin,
    ExceptionHandlingMixin,
    ValidatedFormProcessingMixin,
    LoginRequiredMixin,
    View
):
    """Refactored view using mixins."""

    crud_config = {
        "template_list": "app/list.html",
        "template_form": "app/form.html",
        "model": MyModel,
        "form": MyForm,
        "form_name": "myform",
        "related": ["fk1", "fk2"],
        "fields": ["id", "name", "code"],
        "list_method": "get_my_listview",  # If exists
    }

    def __init__(self):
        super().__init__()
        self.service = MyManagementService()

    def handle_custom_action(self, request, action, config):
        """Handle app-specific actions."""
        # Copy custom action handlers from original
        if action == "custom1":
            return self._handle_custom1(request)
        return None

    def post(self, request, *args, **kwargs):
        """Handle POST with exception handling."""
        return self.handle_exceptions(request, self._process_post)

    def _process_post(self, request):
        """Process POST using form mixin."""
        return self.process_form_post(request)

    def process_valid_form(self, form, request, is_create):
        """Delegate to service layer."""
        if is_create:
            result = self.service.create(form.cleaned_data, request.user, request.session)
        else:
            result = self.service.update(form.instance.id, form.cleaned_data, request.user)

        if result.success:
            return {"pk": result.instance.id}
        else:
            return JsonResponse({"error": result.error_message}, status=422)
```

---

### Step 4: Migrate Form (if needed)

**Template:**

```python
from apps.core.mixins import TenantAwareFormMixin, TypeAssistFilterMixin
from apps.core.utils_new.form_security import SecureFormMixin

class MyFormRefactored(
    TenantAwareFormMixin,
    TypeAssistFilterMixin,
    SecureFormMixin,
    forms.ModelForm
):
    """Refactored form using mixins."""

    # 1. Define tenant filters (replaces manual filtering)
    tenant_filtered_fields = {
        'asset': {
            'model': Asset,
            'filter_by': 'bu_id',
            'extra_filters': Q(status='active'),
        },
        'location': {
            'model': Location,
            'filter_by': 'bu_id',
        },
    }

    # 2. Define TypeAssist filters (if applicable)
    typeassist_fields = {
        'type': 'MYTYPE',
        'category': 'MYCATEGORY',
    }

    class Meta:
        model = MyModel
        fields = ['field1', 'field2', ...]  # Explicit fields (Rule 13)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

        # 3. Apply filters
        self.apply_tenant_filters()
        self.apply_typeassist_filters(self.typeassist_fields)

        # 4. Keep other initialization logic
        self.fields['field1'].required = False
        initailize_form_fields(self)

    # 5. Keep validation methods unchanged
    def clean_field1(self):
        ...
```

---

### Step 5: Create Tests

**Checklist:**
- [ ] Unit tests for service layer (if created)
- [ ] Integration tests comparing old vs new view
- [ ] Test all custom actions
- [ ] Test exception handling
- [ ] Test tenant isolation (if forms modified)

**Template:**

```python
import pytest
from django.test import TestCase, Client

@pytest.mark.integration
class MyViewRefactoredTestCase(TestCase):
    """Integration tests for refactored view."""

    def setUp(self):
        # Setup test data
        ...

    def test_list_view_identical_to_original(self):
        """Test list view produces same results as original."""
        # Call original view
        response_old = self.client.get('/old/url/?action=list')

        # Call refactored view
        response_new = self.client.get('/new/url/?action=list')

        # Compare responses
        self.assertEqual(response_old.status_code, response_new.status_code)
        self.assertEqual(response_old.json(), response_new.json())

    def test_create_identical_to_original(self):
        """Test create functionality identical."""
        data = {...}

        response_old = self.client.post('/old/url/', data)
        response_new = self.client.post('/new/url/', data)

        self.assertEqual(response_old.status_code, response_new.status_code)

    def test_custom_actions_work(self):
        """Test custom actions still function."""
        ...
```

---

### Step 6: Run Regression Tests

```bash
# Run all tests for the app
python -m pytest apps/myapp/tests/ -v

# Run specific integration tests
python -m pytest apps/myapp/tests/test_my_view_refactored.py -v

# Compare performance
python -m pytest apps/myapp/tests/ --durations=10
```

**Validation Criteria:**
- ✅ All tests pass
- ✅ Response structure identical
- ✅ HTTP status codes identical
- ✅ Data saved correctly
- ✅ Error handling works
- ✅ Custom actions work

---

### Step 7: Deploy with Feature Flag

```python
# settings.py or feature flags
FEATURE_FLAGS = {
    'USE_REFACTORED_ASSET_VIEW': os.getenv('USE_REFACTORED_ASSET_VIEW', 'False').lower() == 'true',
}

# urls.py
from django.conf import settings

if settings.FEATURE_FLAGS.get('USE_REFACTORED_ASSET_VIEW'):
    from apps.activity.views.asset.crud_views_refactored import AssetViewRefactored as AssetView
else:
    from apps.activity.views.asset.crud_views import AssetView

urlpatterns = [
    path('assets/', AssetView.as_view(), name='asset_crud'),
]
```

**Rollout Steps:**
1. Deploy with flag OFF
2. Enable for dev environment
3. Run tests in dev
4. Enable for staging
5. Monitor for 24-48 hours
6. Enable for production
7. Monitor for 1 week
8. Remove flag and delete original

---

### Step 8: Cleanup

**After validation:**
- [ ] Remove feature flag
- [ ] Delete or archive original file
- [ ] Update imports across codebase
- [ ] Update documentation
- [ ] Update URL routing
- [ ] Remove old tests (if duplicated)

---

## 🔄 **Example Migrations**

### Example 1: AssetView Migration

**Step-by-Step:**

```bash
# 1. Analyze
wc -l apps/activity/views/asset/crud_views.py
# Output: 235 lines

# 2. Create service (already exists)
# apps/activity/services/asset_service.py ✓

# 3. Create refactored view
# apps/activity/views/asset/crud_views_refactored.py ✓

# 4. Create tests
# apps/activity/tests/test_services/test_asset_service.py ✓

# 5. Run tests
python -m pytest apps/activity/tests/test_services/test_asset_service.py -v

# 6. Compare line counts
wc -l apps/activity/views/asset/crud_views_refactored.py
# Output: 80 lines (66% reduction!)

# 7. Deploy with feature flag
# Update urls.py with conditional import

# 8. Monitor and cleanup after validation
```

**Result:** 235 lines → 80 lines (155 lines eliminated)

---

### Example 2: Ticket View Migration

**Before (y_helpdesk/views.py lines 83-179):**
```python
class TicketView(LoginRequiredMixin, View):
    params = {...}  # 10 lines

    def get(self, request):
        # 50 lines of if/elif routing
        ...

    def post(self, request):
        # 40 lines of try/except
        ...

    def handle_valid_form(self, form, request):
        # 30 lines of business logic
        ...
```

**After (y_helpdesk/views_refactored.py):**
```python
class TicketViewRefactored(
    CRUDActionMixin,
    ExceptionHandlingMixin,
    ValidatedFormProcessingMixin,
    LoginRequiredMixin,
    View
):
    crud_config = {...}  # 10 lines

    def __init__(self):
        super().__init__()
        self.service = TicketWorkflowService()  # Already exists!

    def post(self, request):
        return self.handle_exceptions(request, self._process_post)

    def _process_post(self, request):
        return self.process_form_post(request)

    def process_valid_form(self, form, request, is_create):
        result = self.service.create_or_update_ticket(...)
        return {"pk": result.ticket.id}
```

**Result:** 130 lines → 30 lines (77% reduction)

---

## 🎓 **Common Migration Scenarios**

### Scenario 1: View with No Custom Logic

**Use:** StandardFormProcessingMixin
**Effort:** 15 minutes
**Code Reduction:** 80-90%

```python
class SimpleView(CRUDActionMixin, ExceptionHandlingMixin, StandardFormProcessingMixin, LoginRequiredMixin, View):
    crud_config = {...}

    def post(self, request):
        return self.handle_exceptions(request, lambda r: self.process_form_post(r))
```

---

### Scenario 2: View with Simple Business Logic

**Use:** ValidatedFormProcessingMixin + inline logic
**Effort:** 30 minutes
**Code Reduction:** 70-80%

```python
class ModerateView(CRUDActionMixin, ExceptionHandlingMixin, ValidatedFormProcessingMixin, LoginRequiredMixin, View):
    def process_valid_form(self, form, request, is_create):
        instance = form.save(commit=False)
        instance.custom_field = self.calculate_custom_value(request)
        instance.save()
        putils.save_userinfo(instance, request.user, request.session, is_create)
        return {"pk": instance.id}
```

---

### Scenario 3: View with Complex Business Logic

**Use:** Full service layer
**Effort:** 1-2 hours
**Code Reduction:** 60-75%

```python
# 1. Create service
class MyService(BaseService):
    @BaseService.monitor_performance("complex_operation")
    def complex_operation(self, data, user, session):
        with self.database_transaction():
            # Business logic from handle_valid_form
            ...
            return OperationResult(success=True, ...)

# 2. Use in view
class ComplexView(...):
    def __init__(self):
        super().__init__()
        self.service = MyService()

    def process_valid_form(self, form, request, is_create):
        result = self.service.complex_operation(...)
        return {"pk": result.instance.id} if result.success else ...
```

---

### Scenario 4: View with Many Custom Actions

**Use:** CRUDActionMixin with extended handle_custom_action
**Effort:** 45 minutes
**Code Reduction:** 50-60%

```python
class ManyActionsView(CRUDActionMixin, ...):
    def handle_custom_action(self, request, action, config):
        """Route custom actions."""
        action_map = {
            'export': self.handle_export,
            'import': self.handle_import,
            'stats': self.handle_stats,
            'custom': self.handle_custom,
        }

        handler = action_map.get(action)
        if handler:
            return handler(request, config)

        return None  # Standard CRUD action

    def handle_export(self, request, config):
        # Export logic (< 30 lines)
        ...
```

---

## ⚠️ **Common Pitfalls & Solutions**

### Pitfall 1: Forgetting to Pop Request in Form

**Problem:**
```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)  # ERROR: request still in kwargs
    self.request = kwargs.get('request')
```

**Solution:**
```python
def __init__(self, *args, **kwargs):
    self.request = kwargs.pop('request')  # Pop BEFORE super()
    super().__init__(*args, **kwargs)
```

---

### Pitfall 2: Incorrect Mixin Order

**Problem:**
```python
class MyView(View, CRUDActionMixin):  # View first - methods won't be overridden
    pass
```

**Solution:**
```python
class MyView(CRUDActionMixin, View):  # Mixins first
    pass
```

**Rule:** Mixins → Auth → View (left to right, most specific to least specific)

---

### Pitfall 3: Missing crud_config

**Problem:**
```python
class MyView(CRUDActionMixin, View):
    pass  # No config!
```

**Solution:**
```python
class MyView(CRUDActionMixin, View):
    crud_config = {"model": MyModel, "form": MyForm, ...}
    # OR use P or params (legacy)
```

---

### Pitfall 4: Not Using Transactions in Service

**Problem:**
```python
class MyService(BaseService):
    def create(self, data):
        obj = MyModel.objects.create(**data)  # No transaction!
        obj.add_history()  # Could fail leaving inconsistent state
        return obj
```

**Solution:**
```python
class MyService(BaseService):
    def create(self, data):
        with self.database_transaction():  # Atomic
            obj = MyModel.objects.create(**data)
            obj.add_history()
            return obj
```

---

### Pitfall 5: Exposing Debug Info in Errors

**Problem:**
```python
except Exception as e:
    return JsonResponse({"error": str(e), "traceback": ...})  # Rule 5 violation!
```

**Solution:**
```python
# Use ExceptionHandlingMixin - it handles this automatically
return self.handle_exceptions(request, handler)
# Returns sanitized error with correlation ID only
```

---

## 📊 **Migration Tracking**

### Views Migrated

| App | View | Original Lines | New Lines | Status |
|---|---|---|---|---|
| activity | AssetView | 235 | 80 | ✅ Complete |
| activity | PPMView | 156 | 35 | ✅ Complete |
| activity | PPMJobneedView | 118 | 30 | ✅ Complete |
| activity | QuestionView | TBD | TBD | 🔄 Pending |
| y_helpdesk | TicketView | TBD | TBD | 🔄 Pending |
| onboarding | TypeAssistView | TBD | TBD | 🔄 Pending |
| ... | ... | ... | ... | ... |

**Total Progress:** 3/15 views (20%)
**Total Lines Eliminated:** 399 lines
**Average Reduction:** 69%

---

## 🎯 **Next Steps for Team**

### This Week
1. Review refactored examples
2. Attempt migration of 1 simple view
3. Report issues or questions
4. Provide feedback on patterns

### Next Week
1. Migrate 2-3 views per developer
2. Share learnings in team meeting
3. Refine mixins based on feedback
4. Update this guide with lessons learned

### Ongoing
1. Use mixins for all new views
2. Refactor legacy views opportunistically
3. Monitor metrics and error rates
4. Celebrate improved code quality!

---

## 📚 **Additional Resources**

- **Quick Reference:** `docs/CODE_DEDUPLICATION_QUICK_REFERENCE.md`
- **Implementation Summary:** `CODE_DEDUPLICATION_PHASE2_COMPLETE.md`
- **Examples:** `apps/activity/views/asset/crud_views_refactored.py`
- **Tests:** `apps/core/tests/test_*_mixin.py`
- **Mixins:** `apps/core/mixins/`
- **Services:** `apps/*/services/`

---

**Questions?** Ask in #code-quality Slack channel or review team lead