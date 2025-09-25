# Information Architecture Migration Guide

## Overview
This guide documents the migration from the legacy navigation structure to the new clean, organized information architecture.

## Phase 1: Navigation Cleanup (Completed)

### Changes Made

#### 1. Created Clean Sidebar (`sidebar_clean.html`)
- **Removed all hardcoded `display:none` styles** - Menus now visible by default
- **Fixed duplicate IDs** - Each menu item has unique ID with `menu-` prefix
- **Removed dead links** - No more references to non-existent `apps/customers/*.html`
- **Simplified nesting** - Maximum 2 levels instead of 3+
- **Better grouping** - Related features now under same parent menu

#### 2. Menu Structure Changes

**Old Structure Problems:**
- Assets scattered in 3+ locations
- Duplicate "admin" IDs
- Hidden menus requiring JavaScript
- Dead links to customer pages
- Over-nested configuration menus

**New Structure Benefits:**
- Clear top-level categories: Operations, Assets, People, Help Desk, Reports, Admin
- Consistent naming conventions
- Role-based visibility for admin sections
- All related features grouped together
- Better icons for visual recognition

### Migration Steps

#### Step 1: Update Template Reference
In `frontend/templates/globals/layout.html` or base template:

```django
{# Old #}
{% include 'globals/sidebar_menus.html' %}
{# or #}
{% include 'globals/updated_sidebarmenus.html' %}

{# New #}
{% include 'globals/sidebar_clean.html' %}
```

#### Step 2: Update JavaScript Menu Initialization
The new menu doesn't use `display:none`, so update any JavaScript that shows/hides menus:

```javascript
// Old approach - showing hidden menus
document.getElementById('DASHBOARD').style.display = 'block';

// New approach - menus visible by default, use classes
document.getElementById('menu-dashboard').classList.add('active');
```

#### Step 3: Update Permission Checks
Update any JavaScript or backend code checking menu IDs:

```python
# Old IDs
OLD_TO_NEW_MAPPING = {
    'DASHBOARD': 'menu-dashboard',
    'TRACKING': 'menu-operations',  # Tracking merged into Operations
    'COMPARISIONS': 'menu-assets',  # Comparisons moved to Assets
    'ONBOARDING': 'menu-admin',     # Onboarding moved to Admin
    'ADMIN': 'menu-admin',           # Fixed duplicate ID
    'superadmin': 'menu-superadmin', # Consistent naming
}
```

### URL Redirect Mapping

Create redirects for removed/consolidated pages:

```python
# In urls.py
from django.views.generic import RedirectView

legacy_redirects = [
    # Redirect old customer pages to appropriate new locations
    path('apps/customers/getting-started.html', 
         RedirectView.as_view(url='/dashboard/', permanent=True)),
    path('apps/customers/list.html', 
         RedirectView.as_view(url='/people/', permanent=True)),
    path('apps/customers/view.html', 
         RedirectView.as_view(url='/people/', permanent=True)),
    
    # Redirect old schedhuler URLs to new operations URLs
    path('schedhuler/retrieve_tickets/', 
         RedirectView.as_view(url='/helpdesk/tickets/', permanent=True)),
]
```

### Testing Checklist

- [ ] All menu items are visible (no display:none)
- [ ] No duplicate IDs in HTML
- [ ] All links point to valid Django URLs
- [ ] Role-based menus show/hide correctly
- [ ] Mobile responsive menu works
- [ ] No JavaScript errors in console
- [ ] Old URLs redirect to new locations

## Phase 2: URL Standardization (Next Steps)

### Planned URL Changes

1. **Standardize naming conventions:**
   - Change `peoplegroup` → `people-groups`
   - Change `sitegroup` → `site-groups`
   - Change `escalationmatrix` → `escalation-matrix`

2. **Create consistent REST patterns:**
   ```
   /assets/                    # List
   /assets/create/            # Create
   /assets/<id>/              # Detail
   /assets/<id>/edit/         # Edit
   /assets/<id>/delete/       # Delete
   ```

3. **Consolidate scattered features:**
   - Move all asset-related URLs under `/assets/`
   - Move all people-related URLs under `/people/`
   - Move all report URLs under `/reports/`

### Implementation Timeline

- **Week 1**: Navigation cleanup ✅ COMPLETED
- **Week 2**: URL standardization
- **Week 3-4**: View consolidation
- **Week 5**: Template optimization

## Rollback Plan

If issues arise, revert to old sidebar:
1. Change template include back to `sidebar_menus.html`
2. Re-enable JavaScript menu initialization
3. Remove URL redirects

## Monitoring

Track these metrics after deployment:
- 404 error rates
- Page load times
- User navigation patterns
- Support tickets related to "can't find X feature"

## Next Actions

1. Deploy `sidebar_clean.html` to staging
2. Update JavaScript menu initialization
3. Add URL redirects for dead links
4. Monitor for issues
5. Proceed to Phase 2 after validation