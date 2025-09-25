# Information Architecture Setup Guide

This guide walks you through setting up the complete Information Architecture optimization for your Django YOUTILITY5 project.

## 🚀 Quick Start

### 1. Enable IA Features

Add to your `settings.py`:

```python
# Import IA settings
from intelliwiz_config.settings_ia import apply_ia_settings, get_development_settings

# Apply IA configuration
apply_ia_settings(locals())

# Environment-specific settings
if DEBUG:
    locals().update(get_development_settings())
```

### 2. Update URL Configuration

Replace your main `urls.py` content with:

```python
# intelliwiz_config/urls.py
from intelliwiz_config.urls_optimized import urlpatterns
```

### 3. Run Initial Setup

```bash
# Run database migrations
python manage.py migrate

# Validate IA setup
python manage.py validate_ia

# Generate redirect rules
python manage.py generate_redirects --format apache --output redirects.conf
```

---

## 📋 Complete Setup Checklist

### Phase 1: Basic Setup ✅

- [ ] **Settings Configuration**
  ```python
  # Add to settings.py
  USE_OPTIMIZED_URLS = True
  ENABLE_LEGACY_URLS = True
  SHOW_DEPRECATION_WARNINGS = True
  ENABLE_NAVIGATION_TRACKING = True
  ```

- [ ] **Middleware Setup**
  ```python
  # Add to MIDDLEWARE
  'apps.core.middleware.navigation_tracking.NavigationTrackingMiddleware',
  ```

- [ ] **Template Tags**
  ```python
  # Add to INSTALLED_APPS
  'apps.core',
  ```

- [ ] **Context Processor**
  ```python
  # Add to TEMPLATES context_processors
  'apps.core.context_processors.ia_context',
  ```

### Phase 2: URL Migration ✅

- [ ] **Switch URL Configuration**
  ```python
  # Replace main urlpatterns
  from intelliwiz_config.urls_optimized import urlpatterns
  ```

- [ ] **Generate Web Server Redirects**
  ```bash
  # For Apache
  python manage.py generate_redirects --format apache --output /etc/apache2/redirects.conf
  
  # For Nginx  
  python manage.py generate_redirects --format nginx --output /etc/nginx/redirects.conf
  ```

- [ ] **Database Migration** (Optional)
  ```bash
  python scripts/migrate_ia_database.py
  ```

### Phase 3: Template Updates ✅

- [ ] **Update Navigation Menus**
  ```django
  {% load ia_tags %}
  {% render_navigation_menu 'main' %}
  ```

- [ ] **Add Breadcrumbs**
  ```django
  {% load ia_tags %}
  {% render_breadcrumbs %}
  ```

- [ ] **Show Deprecation Warnings**
  ```django
  {% load ia_tags %}
  {% show_deprecation_warning %}
  ```

### Phase 4: Monitoring Setup ✅

- [ ] **Access Monitoring Dashboard**
  - URL: `/monitoring/ia-dashboard/`
  - Requires staff privileges

- [ ] **Set Up Analytics**
  ```python
  # Optional: Configure external integrations
  IA_INTEGRATIONS = {
      'google_analytics': {'enabled': True, 'tracking_id': 'GA-XXXXX'},
      'sentry': {'enabled': True, 'track_404_errors': True},
  }
  ```

---

## 🔧 Configuration Options

### Settings Overview

```python
# Core IA settings
USE_OPTIMIZED_URLS = True           # Enable new URL structure
ENABLE_LEGACY_URLS = True           # Keep old URLs during migration
SHOW_DEPRECATION_WARNINGS = True    # Warn users about old URLs
ENABLE_NAVIGATION_TRACKING = True   # Track navigation patterns

# Migration settings
IA_MIGRATION_PHASE = 'active'       # 'planning', 'active', 'complete'
LEGACY_REDIRECT_TYPE = 'temporary'  # 'temporary' or 'permanent'

# Performance thresholds
IA_PERFORMANCE_THRESHOLDS = {
    'slow_page_threshold': 3.0,     # seconds
    'high_bounce_rate': 70.0,       # percentage
    'max_404_errors': 50,           # count
}
```

### Environment-Specific Settings

```python
# Development
if DEBUG:
    locals().update({
        'SHOW_DEPRECATION_WARNINGS': True,
        'IA_LOGGING': {'log_level': 'DEBUG'},
        'IA_MONITORING': {'enable_real_time_updates': True},
    })

# Production  
else:
    locals().update({
        'SHOW_DEPRECATION_WARNINGS': False,
        'LEGACY_REDIRECT_TYPE': 'permanent',
        'IA_LOGGING': {'log_level': 'WARNING'},
    })
```

---

## 🧪 Testing & Validation

### 1. URL Validation

```bash
# Basic validation
python manage.py validate_ia

# Comprehensive validation with HTTP checks
python manage.py validate_ia --full-check

# Generate detailed report
python manage.py validate_ia --generate-report --output-format html
```

### 2. Redirect Testing

```bash
# Test redirects with curl
curl -I http://localhost:8000/schedhuler/jobneedtasks/
# Should return 302 redirect to /operations/tasks/

# Test new URLs
curl -I http://localhost:8000/operations/tasks/
# Should return 200 OK
```

### 3. Navigation Testing

```python
# In Django shell
from apps.core.url_router_optimized import OptimizedURLRouter

# Test navigation menu
menu = OptimizedURLRouter.get_navigation_menu()
print(len(menu))  # Should show menu items

# Test breadcrumbs
breadcrumbs = OptimizedURLRouter.get_breadcrumbs('/operations/tasks/')
print(breadcrumbs)  # Should show breadcrumb path
```

### 4. Performance Testing

```bash
# Check migration report
python manage.py shell -c "
from apps.core.url_router_optimized import OptimizedURLRouter
report = OptimizedURLRouter.get_migration_report()
print(f'Adoption Rate: {report[\"summary\"][\"adoption_rate\"]}%')
"
```

---

## 🎯 Template Integration

### Update Base Template

```django
<!-- base.html -->
{% load ia_tags %}
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}YOUTILITY{% endblock %}</title>
    {% get_ia_settings as ia_settings %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        {% render_navigation_menu 'main' 'navbar-nav' %}
        {% if user.is_staff %}
            {% render_navigation_menu 'admin' 'admin-nav' %}
        {% endif %}
    </nav>
    
    <!-- Breadcrumbs -->
    {% render_breadcrumbs 'breadcrumb' %}
    
    <!-- Deprecation Warning -->
    {% show_deprecation_warning %}
    
    <!-- Main Content -->
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <!-- IA Analytics -->
    <script>
        // Track navigation clicks
        document.addEventListener('click', function(e) {
            if (e.target.matches('.nav-link')) {
                // Custom analytics tracking
                console.log('Navigation:', e.target.href);
            }
        });
    </script>
</body>
</html>
```

### Update Individual Templates

```django
<!-- operations/tasks/list.html -->
{% extends "base.html" %}
{% load ia_tags %}

{% block title %}Tasks - Operations{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Task Management</h1>
    {% get_breadcrumbs as breadcrumbs %}
    <!-- Breadcrumbs automatically displayed in base template -->
</div>

<div class="task-list">
    <!-- Your existing task list content -->
</div>
{% endblock %}
```

---

## 📊 Monitoring & Analytics

### Access Monitoring Dashboard

1. **Login as staff user**
2. **Navigate to**: `/monitoring/ia-dashboard/`
3. **Review metrics**:
   - Migration progress
   - URL usage patterns  
   - Performance metrics
   - Dead link detection

### Key Metrics to Monitor

- **Adoption Rate**: >90% target
- **404 Errors**: <10 target
- **Legacy URL Usage**: Decreasing trend
- **Page Response Times**: <2s target

### API Endpoints

```python
# Get migration status
GET /monitoring/api/ia/?action=migration_report

# Get navigation analytics  
GET /monitoring/api/ia/?action=navigation_analytics

# Get live stats
GET /monitoring/api/ia/?action=live_stats
```

---

## 🚨 Troubleshooting

### Common Issues

1. **404 Errors on New URLs**
   ```bash
   # Check URL configuration
   python manage.py show_urls | grep operations
   
   # Validate IA setup
   python manage.py validate_ia
   ```

2. **Redirects Not Working**
   ```bash
   # Check middleware is installed
   python manage.py shell -c "
   from django.conf import settings
   print('navigation_tracking' in str(settings.MIDDLEWARE))
   "
   ```

3. **Template Errors**
   ```bash
   # Check template tags are loaded
   python manage.py shell -c "
   from apps.core.templatetags import ia_tags
   print('Template tags loaded successfully')
   "
   ```

4. **Performance Issues**
   ```bash
   # Check cache configuration
   python manage.py shell -c "
   from django.core.cache import cache
   cache.set('test', 'works', 1)
   print(cache.get('test'))
   "
   ```

### Debug Mode

Enable detailed logging:

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'apps.core.ia': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

---

## 🎉 Go-Live Checklist

### Pre-Deployment

- [ ] All validation tests pass
- [ ] Templates updated with new navigation
- [ ] Web server redirects configured
- [ ] Monitoring dashboard accessible
- [ ] Performance benchmarks recorded
- [ ] Team training completed

### Deployment

- [ ] Deploy IA-enabled code
- [ ] Apply web server redirect rules
- [ ] Monitor error logs
- [ ] Check key user flows
- [ ] Verify analytics tracking

### Post-Deployment  

- [ ] Monitor adoption metrics
- [ ] Review 404 error reports
- [ ] Collect user feedback
- [ ] Plan phase 2 improvements
- [ ] Schedule redirect cleanup

---

## 📈 Migration Timeline

### Week 1-2: Implementation
- Deploy IA code with redirects
- Enable monitoring
- Update critical templates

### Week 3-4: Validation  
- Run comprehensive validation
- Fix identified issues
- Update documentation

### Month 2: Optimization
- Analyze usage patterns
- Optimize based on data
- Train users

### Month 3+: Completion
- Make redirects permanent (301)
- Remove legacy URL support
- Clean up old references

---

## 🆘 Support

### Documentation
- **Setup Guide**: This document
- **URL Mappings**: `documentation/URL_MIGRATION_MAPPING.md`
- **Implementation Details**: `documentation/IA_OPTIMIZATION_IMPLEMENTATION.md`

### Commands
- **Validation**: `python manage.py validate_ia`
- **Redirects**: `python manage.py generate_redirects`
- **Monitoring**: Visit `/monitoring/ia-dashboard/`

### Contact
- **Issues**: Create ticket with monitoring dashboard screenshots
- **Questions**: Include validation command output
- **Emergencies**: Use rollback procedures in documentation

---

*Setup complete! Your Django project now has an optimized Information Architecture with comprehensive monitoring and migration tools.* 🎊