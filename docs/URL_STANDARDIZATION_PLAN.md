# URL Standardization Plan

## Current URL Analysis

### Naming Convention Issues

The current codebase uses inconsistent URL naming:
- **Snake case**: `attendance_view`, `sitereport_list`
- **Camelcase**: `typeassist`, `peoplegroup` 
- **No separators**: `assetmaintainance`, `mobileuserlog`
- **Inconsistent plurals**: `people` vs `peoples`

### Proposed URL Standards

All URLs should follow these conventions:
1. **Use hyphens** for word separation (not underscores)
2. **Use plural** for resource collections
3. **Use lowercase** only
4. **Follow RESTful patterns** where applicable

## URL Mapping Table

### Core Routes

| Current URL | Proposed URL | Notes |
|------------|--------------|-------|
| `/` | `/` | Keep as is |
| `/dashboard/` | `/dashboard/` | Keep as is |
| `/admin/` | `/admin/` | Django admin - keep as is |

### Operations Module

| Current URL | Proposed URL | Notes |
|------------|--------------|-------|
| `/schedhuler/jobneedtasks/` | `/operations/tasks/` | Fix typo, simplify |
| `/schedhuler/jobneedtours/` | `/operations/tours/` | Simplify path |
| `/schedhuler/schd_internal_tour/` | `/operations/schedules/tours/` | Clear hierarchy |
| `/schedhuler/schedhule_task/` | `/operations/schedules/tasks/` | Fix typo |
| `/work_order_management/work_order/` | `/operations/work-orders/` | Simplify |

### Assets Module  

| Current URL | Proposed URL | Notes |
|------------|--------------|-------|
| `/activity/asset/` | `/assets/` | Top-level resource |
| `/activity/assetmaintainance/` | `/assets/maintenance/` | Fix spelling |
| `/activity/comparision/` | `/assets/compare/` | Fix spelling |
| `/activity/param_comparision/` | `/assets/compare/parameters/` | Nested comparison |
| `/activity/location/` | `/assets/locations/` | Group with assets |
| `/activity/assetlog/` | `/assets/logs/` | Clearer naming |

### People Module

| Current URL | Proposed URL | Notes |
|------------|--------------|-------|
| `/peoples/people/` | `/people/` | Remove redundancy |
| `/peoples/peoplegroup/` | `/people/groups/` | Clear hierarchy |
| `/peoples/sitegroup/` | `/people/site-groups/` | Hyphenate |
| `/attendance/attendance_view/` | `/people/attendance/` | Group with people |
| `/attendance/geofencetracking/` | `/people/tracking/` | Simplify |
| `/attendance/travel_expense/` | `/people/expenses/` | Clearer naming |

### Help Desk Module

| Current URL | Proposed URL | Notes |
|------------|--------------|-------|
| `/helpdesk/ticket/` | `/help-desk/tickets/` | Pluralize, hyphenate |
| `/helpdesk/escalationmatrix/` | `/help-desk/escalations/` | Simplify |
| `/helpdesk/postingorder/` | `/help-desk/posting-orders/` | Hyphenate |
| `/helpdesk/uniform/` | `/help-desk/uniforms/` | Pluralize |

### Reports Module

| Current URL | Proposed URL | Notes |
|------------|--------------|-------|
| `/reports/get_reports/` | `/reports/download/` | RESTful naming |
| `/reports/schedule-email-report/` | `/reports/schedule/` | Simplify |
| `/reports/sitereport_list/` | `/reports/site-reports/` | Consistent hyphenation |
| `/reports/incidentreport_list/` | `/reports/incident-reports/` | Consistent hyphenation |

### Admin Module

| Current URL | Proposed URL | Notes |
|------------|--------------|-------|
| `/onboarding/bu/` | `/admin/business-units/` | Full name, clear purpose |
| `/onboarding/typeassist/` | `/admin/type-definitions/` | Clearer naming |
| `/onboarding/import/` | `/admin/data/import/` | Clear hierarchy |
| `/onboarding/import_update/` | `/admin/data/bulk-update/` | Better naming |

## Implementation Strategy

### Step 1: Create URL Router (Week 2, Day 1-2)

```python
# apps/core/urls_router.py
from django.urls import path, include
from django.views.generic import RedirectView

class URLRouter:
    """Centralized URL routing with legacy support"""
    
    # Mapping of old URLs to new URLs
    URL_MAPPINGS = {
        'schedhuler/jobneedtasks/': 'operations/tasks/',
        'schedhuler/jobneedtours/': 'operations/tours/',
        'peoples/people/': 'people/',
        'peoples/peoplegroup/': 'people/groups/',
        'activity/asset/': 'assets/',
        'activity/assetmaintainance/': 'assets/maintenance/',
        # ... complete mapping
    }
    
    @classmethod
    def get_redirects(cls):
        """Generate redirect patterns for legacy URLs"""
        redirects = []
        for old_url, new_url in cls.URL_MAPPINGS.items():
            redirects.append(
                path(old_url, RedirectView.as_view(
                    url=f'/{new_url}', 
                    permanent=True
                ))
            )
        return redirects
```

### Step 2: Update URL Configurations (Week 2, Day 3-4)

Create new URL configuration files with standardized patterns:

```python
# apps/operations/urls.py
from django.urls import path, include

app_name = 'operations'
urlpatterns = [
    path('tasks/', include('apps.operations.tasks_urls')),
    path('tours/', include('apps.operations.tours_urls')),
    path('schedules/', include('apps.operations.schedules_urls')),
    path('work-orders/', include('apps.operations.work_orders_urls')),
]
```

### Step 3: Update Templates (Week 2, Day 5)

Create a template tag for URL migration:

```python
# apps/core/templatetags/url_helpers.py
from django import template
from apps.core.urls_router import URLRouter

register = template.Library()

@register.simple_tag
def standard_url(url_name, *args, **kwargs):
    """Generate standardized URLs with fallback to legacy"""
    try:
        # Try new URL first
        return reverse(url_name, args=args, kwargs=kwargs)
    except:
        # Fallback to legacy URL
        legacy_name = URLRouter.get_legacy_name(url_name)
        return reverse(legacy_name, args=args, kwargs=kwargs)
```

## Testing Plan

### Automated Tests
```python
# tests/test_url_migration.py
class URLMigrationTest(TestCase):
    def test_legacy_urls_redirect(self):
        """Ensure all legacy URLs redirect to new URLs"""
        for old_url, new_url in URLRouter.URL_MAPPINGS.items():
            response = self.client.get(f'/{old_url}')
            self.assertRedirects(
                response, 
                f'/{new_url}', 
                status_code=301
            )
    
    def test_new_urls_accessible(self):
        """Ensure all new URLs are accessible"""
        for new_url in URLRouter.URL_MAPPINGS.values():
            response = self.client.get(f'/{new_url}')
            self.assertIn(
                response.status_code, 
                [200, 302]  # OK or redirect to login
            )
```

### Manual Testing Checklist
- [ ] All menu links work correctly
- [ ] Bookmarked URLs redirect properly
- [ ] API endpoints maintain compatibility
- [ ] No broken links in emails
- [ ] Search engines notified of changes

## Rollback Plan

1. Keep old URL patterns active with deprecation warnings
2. Log usage of legacy URLs for 30 days
3. Remove legacy URLs only after confirming zero usage
4. Maintain redirect mappings indefinitely for SEO

## Success Metrics

- Zero 404 errors from URL changes
- < 5% of traffic using legacy URLs after 30 days
- No increase in support tickets
- Improved developer onboarding time