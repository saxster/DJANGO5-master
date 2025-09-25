# URL Migration Mapping - Complete Reference

This document provides a comprehensive mapping of all URLs from the old structure to the new optimized Information Architecture.

## Quick Reference

### New Domain Structure
- `/operations/` - Tasks, tours, work orders, PPM
- `/assets/` - Inventory, maintenance, locations, monitoring  
- `/people/` - Directory, attendance, expenses, tracking
- `/help-desk/` - Tickets, escalations, requests
- `/reports/` - All reporting functionality
- `/admin/` - Business units, configuration, data management

---

## Complete URL Mappings

### 🔧 Operations Domain

| Old URL | New URL | Description |
|---------|---------|-------------|
| `schedhuler/jobneedtasks/` | `operations/tasks/` | Task management |
| `schedhuler/schedhule_task/` | `operations/tasks/schedule/` | Task scheduling |
| `schedhuler/tasklist_jobneed/` | `operations/tasks/list/` | Task listing |
| `schedhuler/jobschdtasks/` | `operations/tasks/scheduled/` | Scheduled tasks |
| `schedhuler/task_jobneed/<pk>/` | `operations/tasks/<pk>/` | Task details |
| `activity/adhoctasks/` | `operations/tasks/adhoc/` | Ad-hoc tasks |
| `schedhuler/jobneedtours/` | `operations/tours/` | Tour management |
| `schedhuler/jobneedexternaltours/` | `operations/tours/external/` | External tours |
| `schedhuler/internal-tours/` | `operations/tours/internal/` | Internal tours |
| `schedhuler/schd_internal_tour/` | `operations/schedules/tours/internal/` | Internal tour scheduling |
| `schedhuler/schd_external_tour/` | `operations/schedules/tours/external/` | External tour scheduling |
| `schedhuler/schedhule_tour/` | `operations/tours/schedule/` | Tour scheduling |
| `schedhuler/external_schedhule_tour/` | `operations/tours/external/schedule/` | External tour scheduling |
| `schedhuler/site_tour_tracking/` | `operations/tours/tracking/` | Tour tracking |
| `activity/adhoctours/` | `operations/tours/adhoc/` | Ad-hoc tours |
| `work_order_management/work_order/` | `operations/work-orders/` | Work orders |
| `work_order_management/workorder/` | `operations/work-orders/` | Work orders (alt) |
| `work_order_management/work_permit/` | `operations/work-permits/` | Work permits |
| `work_order_management/workpermit/` | `operations/work-permits/` | Work permits (alt) |
| `work_order_management/sla/` | `operations/sla/` | Service Level Agreements |
| `work_order_management/vendor/` | `operations/vendors/` | Vendor management |
| `work_order_management/approver/` | `operations/approvers/` | Approver management |
| `activity/ppm/` | `operations/ppm/` | Preventive maintenance |
| `activity/ppm_jobneed/` | `operations/ppm/jobs/` | PPM job needs |

### 🏢 Assets Domain

| Old URL | New URL | Description |
|---------|---------|-------------|
| `activity/asset/` | `assets/` | Asset management |
| `activity/assetmaintainance/` | `assets/maintenance/` | Asset maintenance |
| `activity/assetmaintenance/` | `assets/maintenance/` | Asset maintenance (alt) |
| `activity/comparision/` | `assets/compare/` | Asset comparison |
| `activity/param_comparision/` | `assets/compare/parameters/` | Parameter comparison |
| `activity/assetlog/` | `assets/logs/` | Asset logs |
| `activity/assetlogs/` | `assets/logs/` | Asset logs (alt) |
| `activity/location/` | `assets/locations/` | Location management |
| `activity/checkpoint/` | `assets/checkpoints/` | Checkpoint management |
| `activity/peoplenearassets/` | `assets/people-nearby/` | People near assets |
| `activity/question/` | `assets/checklists/questions/` | Checklist questions |
| `activity/questionset/` | `assets/checklists/` | Checklists |
| `activity/qsetnQsetblng/` | `assets/checklists/relationships/` | Checklist relationships |

### 👥 People Domain

| Old URL | New URL | Description |
|---------|---------|-------------|
| `peoples/people/` | `people/` | People directory |
| `peoples/peole_form/` | `people/form/` | People form (typo in original) |
| `peoples/capability/` | `people/capabilities/` | Capabilities management |
| `peoples/no-site/` | `people/unassigned/` | Unassigned people |
| `peoples/peoplegroup/` | `people/groups/` | People groups |
| `peoples/sitegroup/` | `people/site-groups/` | Site groups |
| `attendance/attendance_view/` | `people/attendance/` | Attendance tracking |
| `attendance/geofencetracking/` | `people/tracking/` | Geofence tracking |
| `attendance/sos_list/` | `people/sos/` | SOS alerts |
| `attendance/site_diversions/` | `people/diversions/` | Site diversions |
| `attendance/sitecrisis_list/` | `people/crisis/` | Site crisis management |
| `attendance/conveyance/` | `people/expenses/conveyance/` | Conveyance expenses |
| `attendance/travel_expense/` | `people/expenses/travel/` | Travel expenses |
| `activity/mobileuserlogs/` | `people/mobile/logs/` | Mobile user logs |
| `activity/mobileuserdetails/` | `people/mobile/details/` | Mobile user details |
| `employee_creation/employee/` | `people/employees/` | Employee management |

### 🎫 Help Desk Domain

| Old URL | New URL | Description |
|---------|---------|-------------|
| `helpdesk/ticket/` | `help-desk/tickets/` | Ticket management |
| `y_helpdesk/ticket/` | `help-desk/tickets/` | Ticket management (alt) |
| `helpdesk/escalationmatrix/` | `help-desk/escalations/` | Escalation matrix |
| `y_helpdesk/escalation/` | `help-desk/escalations/` | Escalations |
| `helpdesk/postingorder/` | `help-desk/posting-orders/` | Posting orders |
| `y_helpdesk/posting_order/` | `help-desk/posting-orders/` | Posting orders (alt) |
| `helpdesk/uniform/` | `help-desk/uniforms/` | Uniform management |
| `y_helpdesk/uniform/` | `help-desk/uniforms/` | Uniform management (alt) |

### 📊 Reports Domain

| Old URL | New URL | Description |
|---------|---------|-------------|
| `reports/get_reports/` | `reports/download/` | Report downloads |
| `reports/exportreports/` | `reports/download/` | Report exports |
| `reports/schedule-email-report/` | `reports/schedule/` | Report scheduling |
| `reports/schedule_email_report/` | `reports/schedule/` | Report scheduling (alt) |
| `reports/sitereport_list/` | `reports/site-reports/` | Site reports |
| `reports/incidentreport_list/` | `reports/incident-reports/` | Incident reports |
| `reports/sitereport_template/` | `reports/templates/site/` | Site report templates |
| `reports/incidentreport_template/` | `reports/templates/incident/` | Incident report templates |
| `reports/workpermitreport_template/` | `reports/templates/work-permit/` | Work permit templates |
| `reports/generatepdf/` | `reports/generate/pdf/` | PDF generation |
| `reports/generateletter/` | `reports/generate/letter/` | Letter generation |
| `reports/design/` | `reports/designer/` | Report designer |

### ⚙️ Admin Domain

| Old URL | New URL | Description |
|---------|---------|-------------|
| `onboarding/bu/` | `admin/business-units/` | Business units |
| `onboarding/client/` | `admin/clients/` | Client management |
| `clientbilling/features/` | `admin/clients/features/` | Client features |
| `onboarding/contract/` | `admin/contracts/` | Contract management |
| `onboarding/typeassist/` | `admin/config/types/` | Type definitions |
| `onboarding/shift/` | `admin/config/shifts/` | Shift management |
| `onboarding/geofence/` | `admin/config/geofences/` | Geofence configuration |
| `onboarding/import/` | `admin/data/import/` | Data import |
| `onboarding/import_update/` | `admin/data/bulk-update/` | Bulk data updates |
| `onboarding/import_image_data/` | `admin/data/import-images/` | Image data import |

### 🔌 API & Technical

| Old URL | New URL | Description |
|---------|---------|-------------|
| `api/` | `api/v1/` | API endpoints (versioned) |
| `service/` | `api/v1/service/` | Service endpoints |
| `graphql/` | `api/graphql/` | GraphQL endpoint |
| `monitoring/health/` | `monitoring/health/` | Health checks |
| `monitoring/metrics/` | `monitoring/metrics/` | System metrics |

### 🔐 Authentication

| Old URL | New URL | Description |
|---------|---------|-------------|
| `login/` | `auth/login/` | User login |
| `logout/` | `auth/logout/` | User logout |
| `peoples/verifyemail/` | `auth/verify-email/` | Email verification |
| `email/` | `auth/email/` | Email management |

---

## Migration Strategies

### 1. Template Updates

Update your templates to use the new URLs:

```html
<!-- OLD -->
<a href="/schedhuler/jobneedtasks/">Tasks</a>
<a href="/activity/asset/">Assets</a>
<a href="/peoples/people/">People</a>

<!-- NEW -->
<a href="/operations/tasks/">Tasks</a>
<a href="/assets/">Assets</a>
<a href="/people/">People</a>
```

### 2. View Updates

Update reverse() calls in views:

```python
# OLD
from django.urls import reverse
redirect_url = reverse('schedhuler:jobneedtasks')

# NEW  
redirect_url = reverse('operations:tasks_list')
```

### 3. Form Actions

Update form action URLs:

```html
<!-- OLD -->
<form action="/schedhuler/schedhule_task/" method="post">

<!-- NEW -->
<form action="/operations/tasks/schedule/" method="post">
```

### 4. JavaScript/AJAX

Update JavaScript URLs:

```javascript
// OLD
fetch('/activity/asset/')

// NEW
fetch('/assets/')
```

### 5. Documentation Updates

Update all documentation, README files, and API docs:

```markdown
# OLD
- Task management: `/schedhuler/jobneedtasks/`
- Asset management: `/activity/asset/`

# NEW
- Task management: `/operations/tasks/`
- Asset management: `/assets/`
```

---

## Automated Migration Tools

### 1. URL Validation Command

```bash
# Validate all URL mappings
python manage.py validate_ia

# Full validation with HTTP checks
python manage.py validate_ia --full-check

# Generate detailed report
python manage.py validate_ia --generate-report
```

### 2. Template Scanner

```bash
# Scan templates for old URLs (custom script)
python manage.py scan_templates --fix-urls
```

### 3. Redirect Generation

```bash
# Generate Apache redirects
python manage.py generate_redirects --format apache

# Generate Nginx redirects
python manage.py generate_redirects --format nginx
```

---

## Rollback Plan

If issues arise during migration:

### 1. Immediate Rollback

```python
# In settings.py
USE_OPTIMIZED_URLS = False
ENABLE_LEGACY_URLS = True
```

### 2. Gradual Rollback

Disable specific URL mappings:

```python
# Remove problematic mappings from URL_MAPPINGS
del OptimizedURLRouter.URL_MAPPINGS['problematic/url/']
```

### 3. Emergency Rollback

Revert to original URL configuration:

```python
# Use original urls.py
urlpatterns = original_patterns
```

---

## Testing Checklist

### Before Deployment

- [ ] All critical URLs have mappings
- [ ] Redirects work correctly (302 status)
- [ ] Navigation menus updated
- [ ] Forms submit to correct URLs
- [ ] AJAX calls use new URLs
- [ ] Documentation updated
- [ ] External integrations notified

### After Deployment

- [ ] Monitor redirect usage
- [ ] Check for 404 errors
- [ ] Validate performance metrics
- [ ] User feedback collection
- [ ] Analytics data review

### Migration Complete

- [ ] Change redirects to 301 (permanent)
- [ ] Remove legacy URL patterns
- [ ] Clean up old template references
- [ ] Archive old documentation

---

## Support & Troubleshooting

### Common Issues

1. **404 Errors**: Check URL mapping exists and is correct
2. **Redirect Loops**: Ensure new URL doesn't redirect to old URL
3. **Performance Issues**: Monitor redirect overhead
4. **User Confusion**: Show deprecation warnings

### Debugging Tools

1. **Management Command**: `python manage.py validate_ia --full-check`
2. **Monitoring Dashboard**: `/monitoring/ia-dashboard/`
3. **Django Debug Toolbar**: Shows redirect chains
4. **Browser Network Tab**: Inspect redirect responses

### Getting Help

1. Check monitoring dashboard for insights
2. Review validation command output
3. Examine server logs for redirect patterns
4. Contact development team with specific URLs

---

## Migration Timeline

### Phase 1: Implementation (Week 1-2)
- Deploy new URL structure with redirects
- Enable monitoring and tracking
- Update critical templates

### Phase 2: Validation (Week 3-4)
- Run comprehensive validation
- Fix identified issues
- Update remaining templates and docs

### Phase 3: Optimization (Month 2)
- Analyze usage patterns
- Optimize based on data
- Train users on new structure

### Phase 4: Completion (Month 3-6)
- Make redirects permanent (301)
- Remove legacy URL support
- Archive old documentation

---

*This document is automatically generated from the URL mappings in `OptimizedURLRouter.URL_MAPPINGS`. Last updated: Current timestamp*