# Information Architecture Deployment Checklist

## Pre-Deployment Checklist

### 🔍 Code Review
- [ ] Review `sidebar_clean.html` for any missing menu items
- [ ] Verify all menu links use Django URL tags (not hardcoded)
- [ ] Check role-based menu visibility logic
- [ ] Ensure no duplicate IDs in HTML
- [ ] Validate all JavaScript changes

### 🧪 Testing
- [ ] Run automated test suite: `python manage.py test tests.test_information_architecture`
- [ ] Manual testing of all menu links
- [ ] Test on mobile devices
- [ ] Test with different user roles (regular, staff, superuser)
- [ ] Verify all redirects work correctly
- [ ] Check page load performance

### 📦 Staging Deployment
- [ ] Deploy to staging environment
- [ ] Run smoke tests on staging
- [ ] Get stakeholder approval
- [ ] Document any issues found

## Production Deployment Steps

### Step 1: Backup Current State
```bash
# Backup database
python manage.py dbbackup

# Backup current templates
cp -r frontend/templates frontend/templates.backup.$(date +%Y%m%d)

# Create git tag for rollback
git tag pre-ia-migration
git push origin pre-ia-migration
```

### Step 2: Deploy New Files
```bash
# Copy new files
cp frontend/templates/globals/sidebar_clean.html frontend/templates/globals/
cp frontend/static/assets/js/menu-handler-clean.js frontend/static/assets/js/
cp apps/core/url_router.py apps/core/
cp apps/core/views/base_views.py apps/core/views/

# Copy base templates
cp -r frontend/templates/base frontend/templates/

# Collect static files
python manage.py collectstatic --noinput
```

### Step 3: Update Configuration
```python
# In settings.py, add to INSTALLED_APPS if not present
INSTALLED_APPS = [
    # ...
    'apps.core',
    # ...
]

# Add middleware for legacy URL tracking (optional)
MIDDLEWARE = [
    # ...
    'apps.core.middleware.LegacyURLMiddleware',
    # ...
]
```

### Step 4: Update Main URL Configuration
```python
# In intelliwiz_config/urls.py

# Option 1: Gradual migration (recommended)
from apps.core.url_router import URLRouter

# Add at the end of urlpatterns
urlpatterns += URLRouter.get_redirect_patterns()

# Option 2: Full migration
# Replace entire urls.py with urls_clean.py content
```

### Step 5: Update Base Template
```django
{# In frontend/templates/globals/layout.html or base template #}

{# Replace old sidebar include #}
{% comment %}
{% include 'globals/sidebar_menus.html' %}
{% endcomment %}

{# Use new clean sidebar #}
{% include 'globals/sidebar_clean.html' %}
```

### Step 6: Update JavaScript
```html
<!-- In base template before closing </body> -->
<script src="{{ static('assets/js/menu-handler-clean.js') }}"></script>
```

### Step 7: Clear Caches
```bash
# Clear Django cache
python manage.py clear_cache

# Clear browser caches (notify users)
# Clear CDN cache if applicable
```

### Step 8: Run Migrations (if any)
```bash
python manage.py migrate
```

## Post-Deployment Verification

### Immediate Checks (First 30 minutes)
- [ ] Home page loads correctly
- [ ] Navigation menu appears and functions
- [ ] All main sections accessible
- [ ] No 500 errors in logs
- [ ] No JavaScript errors in console

### First Hour Monitoring
- [ ] Monitor error logs: `tail -f logs/django.log`
- [ ] Check 404 rates in analytics
- [ ] Monitor server resources (CPU, memory)
- [ ] Review user feedback channels
- [ ] Check legacy URL redirect logs

### First Day Monitoring
- [ ] Review legacy URL usage report
- [ ] Check user navigation patterns
- [ ] Monitor support tickets
- [ ] Verify all scheduled tasks still work
- [ ] Check integration points

## Rollback Plan

If critical issues arise:

### Quick Rollback (< 5 minutes)
```bash
# Revert template change
cp frontend/templates.backup.$(date +%Y%m%d)/globals/sidebar_menus.html frontend/templates/globals/sidebar_menus.html

# Update base template to use old sidebar
# Edit: frontend/templates/globals/layout.html
# Change: {% include 'globals/sidebar_clean.html' %} 
# To: {% include 'globals/sidebar_menus.html' %}

# Clear cache
python manage.py clear_cache
```

### Full Rollback (if needed)
```bash
# Revert to git tag
git checkout pre-ia-migration

# Restore database if data changes were made
python manage.py dbrestore

# Redeploy
./deploy.sh
```

## Success Criteria

### Day 1
- ✅ No increase in error rates
- ✅ No critical user complaints
- ✅ Core functionality working

### Week 1
- ✅ 404 errors reduced by 90%
- ✅ Positive user feedback
- ✅ No major issues reported

### Month 1
- ✅ Legacy URL usage < 5%
- ✅ Improved navigation metrics
- ✅ Reduced support tickets about "finding features"

## Communication Plan

### Pre-Deployment (1 week before)
- Email to all users about upcoming changes
- Training video/documentation for new navigation
- FAQ document addressing common concerns

### Deployment Day
- Banner notification about updates
- Quick reference guide available
- Support team briefed and ready

### Post-Deployment
- Follow-up email with tips
- Survey after 1 week
- Success metrics report after 1 month

## Support Resources

### Documentation
- User Guide: `/documentation/IA_USER_GUIDE.md`
- Admin Guide: `/documentation/IA_ADMIN_GUIDE.md`
- Developer Guide: `/documentation/IA_DEVELOPER_GUIDE.md`

### Monitoring Dashboards
- Error Tracking: [Your Error Tracking URL]
- Analytics: [Your Analytics URL]
- Legacy URL Report: `/admin/_legacy-urls-report/`

### Contact Points
- Technical Lead: [Contact Info]
- Support Team: [Contact Info]
- Emergency Escalation: [Contact Info]

## Sign-offs

- [ ] Development Team Lead
- [ ] QA Team Lead
- [ ] Product Owner
- [ ] Operations Team
- [ ] Security Team (if applicable)

---

**Deployment Date**: _______________
**Deployed By**: _______________
**Version**: _______________