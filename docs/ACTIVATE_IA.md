# 🚀 Information Architecture Activation Guide

Follow these steps to activate the optimized Information Architecture in your Django project.

## Step 1: Enable the System

### 1.1 Update your main settings.py

```python
# intelliwiz_config/settings.py

# Import IA settings
from intelliwiz_config.settings_ia import apply_ia_settings, get_development_settings

# Apply IA configuration (add this near the end of settings.py)
apply_ia_settings(locals())

# Environment-specific settings
if DEBUG:
    # Development environment
    locals().update(get_development_settings())
    print("🔧 IA System: Development mode enabled")
else:
    # Production environment - more conservative settings
    locals().update({
        'SHOW_DEPRECATION_WARNINGS': False,
        'IA_LOGGING': {'log_level': 'WARNING'},
    })
    print("🚀 IA System: Production mode enabled")

# Validate IA settings
from intelliwiz_config.settings_ia import validate_ia_settings
validation = validate_ia_settings()
if validation['errors']:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(f"IA Settings errors: {validation['errors']}")
if validation['warnings']:
    import warnings
    for warning in validation['warnings']:
        warnings.warn(f"IA Settings: {warning}")
```

### 1.2 Verify Settings Applied

Run this check:

```bash
python manage.py shell -c "
from django.conf import settings
print('✅ USE_OPTIMIZED_URLS:', getattr(settings, 'USE_OPTIMIZED_URLS', False))
print('✅ ENABLE_LEGACY_URLS:', getattr(settings, 'ENABLE_LEGACY_URLS', False))
print('✅ Navigation tracking:', 'navigation_tracking' in str(getattr(settings, 'MIDDLEWARE', [])))
print('✅ IA apps installed:', 'apps.core' in getattr(settings, 'INSTALLED_APPS', []))
"
```

## Step 2: Switch URL Configuration

### 2.1 Backup Current URLs

```bash
# Create backup
cp intelliwiz_config/urls.py intelliwiz_config/urls_backup.py
echo "✅ Original URLs backed up"
```

### 2.2 Switch to Optimized URLs

Replace the content of `intelliwiz_config/urls.py`:

```python
# intelliwiz_config/urls.py
"""
URL configuration with optimized Information Architecture
"""
from django.conf import settings

# Import optimized URL patterns
from intelliwiz_config.urls_optimized import urlpatterns

# Optional: Add development-only URLs
if settings.DEBUG:
    import debug_toolbar
    from django.urls import include, path
    
    # Add debug toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# Log URL configuration switch
import logging
logger = logging.getLogger(__name__)
logger.info(f"🔄 Using optimized URLs: {settings.USE_OPTIMIZED_URLS}")
logger.info(f"📊 Total URL patterns loaded: {len(urlpatterns)}")
```

### 2.3 Quick URL Test

```bash
# Test that URLs are loading
python manage.py shell -c "
from django.urls import reverse
from django.test import Client

client = Client()
print('Testing key URLs...')

# Test dashboard
try:
    response = client.get('/dashboard/')
    print(f'✅ Dashboard: {response.status_code}')
except Exception as e:
    print(f'❌ Dashboard error: {e}')

# Test operations
try:
    response = client.get('/operations/')
    print(f'✅ Operations: {response.status_code}')
except Exception as e:
    print(f'❌ Operations error: {e}')

print('✅ Basic URL test complete')
"
```

## Step 3: Validate Setup

### 3.1 Run Comprehensive Validation

```bash
echo "🔍 Running comprehensive IA validation..."

# Basic validation
python manage.py validate_ia

echo ""
echo "🔬 Running full validation with HTTP checks..."

# Full validation with HTTP checks
python manage.py validate_ia --full-check

echo ""
echo "📊 Generating detailed report..."

# Generate HTML report
python manage.py validate_ia --generate-report --output-format html
```

### 3.2 Check for Common Issues

```bash
# Check middleware order
python manage.py shell -c "
from django.conf import settings
middleware = settings.MIDDLEWARE
nav_middleware = 'apps.core.middleware.navigation_tracking.NavigationTrackingMiddleware'

if nav_middleware in middleware:
    index = middleware.index(nav_middleware)
    print(f'✅ Navigation middleware at position {index}')
    if index < 3:
        print('⚠️  Consider moving middleware after CommonMiddleware')
else:
    print('❌ Navigation middleware not found')
"

# Check cache configuration
python manage.py shell -c "
from django.core.cache import cache
try:
    cache.set('ia_test', 'working', 30)
    result = cache.get('ia_test')
    if result == 'working':
        print('✅ Cache working correctly')
    else:
        print('❌ Cache not working')
except Exception as e:
    print(f'❌ Cache error: {e}')
"
```

### 3.3 Test Redirects

```bash
# Test legacy URL redirects
echo "🔄 Testing legacy URL redirects..."

python manage.py shell -c "
from django.test import Client
from apps.core.url_router_optimized import OptimizedURLRouter

client = Client()

# Test sample legacy URLs
test_urls = [
    'schedhuler/jobneedtasks/',
    'activity/asset/', 
    'peoples/people/',
]

for old_url in test_urls:
    try:
        response = client.get(f'/{old_url}')
        if response.status_code in [301, 302]:
            new_url = response.url if hasattr(response, 'url') else 'Unknown'
            print(f'✅ {old_url} → {new_url} ({response.status_code})')
        else:
            print(f'❌ {old_url} → {response.status_code}')
    except Exception as e:
        print(f'❌ {old_url} → Error: {e}')
"
```

## Step 4: Monitor Progress

### 4.1 Access Monitoring Dashboard

```bash
# Start development server if not running
python manage.py runserver 0.0.0.0:8000 &

echo "🖥️  Access monitoring dashboard at:"
echo "   http://localhost:8000/monitoring/ia-dashboard/"
echo ""
echo "📊 Key metrics to monitor:"
echo "   - Adoption Rate (target: >90%)"
echo "   - Dead URLs (target: <10)"
echo "   - Legacy URL Usage (should decrease)"
echo "   - Page Response Times (target: <2s)"
```

### 4.2 Set Up Monitoring Alerts

Create a monitoring script:

```bash
cat > monitor_ia.py << 'EOF'
#!/usr/bin/env python
"""
IA Monitoring Script - Run periodically to check system health
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware

def check_ia_health():
    print("🔍 IA Health Check")
    print("=" * 40)
    
    # Check adoption rate
    try:
        report = OptimizedURLRouter.get_migration_report()
        adoption_rate = report['summary']['adoption_rate']
        
        if adoption_rate >= 90:
            print(f"✅ Adoption Rate: {adoption_rate}% (Excellent)")
        elif adoption_rate >= 70:
            print(f"⚠️  Adoption Rate: {adoption_rate}% (Good)")
        else:
            print(f"❌ Adoption Rate: {adoption_rate}% (Needs Attention)")
    except Exception as e:
        print(f"❌ Could not check adoption rate: {e}")
    
    # Check for dead URLs
    try:
        analytics = NavigationTrackingMiddleware.get_navigation_analytics()
        dead_count = analytics.get('dead_urls', {}).get('total_dead_urls', 0)
        
        if dead_count == 0:
            print("✅ No dead URLs detected")
        elif dead_count <= 10:
            print(f"⚠️  {dead_count} dead URLs found")
        else:
            print(f"❌ {dead_count} dead URLs - immediate attention needed")
    except Exception as e:
        print(f"❌ Could not check dead URLs: {e}")
    
    print("\n📊 Full dashboard: /monitoring/ia-dashboard/")

if __name__ == "__main__":
    check_ia_health()
EOF

chmod +x monitor_ia.py
python monitor_ia.py
```

### 4.3 Create Automated Checks

Add to your deployment/monitoring system:

```bash
# Add to crontab for hourly checks
echo "0 * * * * cd /path/to/project && python monitor_ia.py" | crontab -

# Or create a systemd timer
cat > /etc/systemd/system/ia-monitor.service << EOF
[Unit]
Description=IA Monitoring Check

[Service]
Type=oneshot
ExecStart=/path/to/project/monitor_ia.py
WorkingDirectory=/path/to/project
EOF

cat > /etc/systemd/system/ia-monitor.timer << EOF
[Unit]
Description=Run IA monitoring every hour

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable timer
systemctl enable ia-monitor.timer
systemctl start ia-monitor.timer
```

## Step 5: Update Templates (Gradual)

### 5.1 Update Base Template

```django
<!-- templates/base.html -->
{% load ia_tags %}
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}YOUTILITY{% endblock %}</title>
    {% get_ia_settings as ia_settings %}
    
    {% if ia_settings.use_optimized_urls %}
    <!-- IA optimizations enabled -->
    <meta name="ia-version" content="1.0">
    {% endif %}
</head>
<body>
    <!-- Show migration status to staff -->
    {% if user.is_staff %}
        {% migration_progress as progress %}
        {% if progress < 90 %}
        <div class="alert alert-info">
            IA Migration Progress: {{ progress }}%
        </div>
        {% endif %}
    {% endif %}
    
    <!-- Deprecation warnings -->
    {% show_deprecation_warning %}
    
    <!-- Navigation with new structure -->
    <nav class="main-nav">
        {% render_navigation_menu 'main' %}
    </nav>
    
    <!-- Breadcrumbs -->
    {% render_breadcrumbs %}
    
    <!-- Content -->
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

### 5.2 Update Navigation Templates

```bash
# Find templates with old navigation
find frontend/templates -name "*.html" -exec grep -l "schedhuler\|activity/asset\|peoples/people" {} \;

# Create update script
cat > update_templates.py << 'EOF'
import os
import re

# URL mappings for template updates
url_replacements = {
    '/schedhuler/jobneedtasks/': '/operations/tasks/',
    '/activity/asset/': '/assets/',
    '/peoples/people/': '/people/',
    '/helpdesk/ticket/': '/help-desk/tickets/',
    '/reports/get_reports/': '/reports/download/',
}

def update_template_urls(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    for old_url, new_url in url_replacements.items():
        content = content.replace(old_url, new_url)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✅ Updated: {file_path}")

# Update templates
for root, dirs, files in os.walk('frontend/templates'):
    for file in files:
        if file.endswith('.html'):
            file_path = os.path.join(root, file)
            update_template_urls(file_path)

print("✅ Template update complete")
EOF

python update_templates.py
```

## Step 6: Production Deployment

### 6.1 Pre-Deployment Checklist

```bash
echo "🚀 Pre-deployment checklist:"
echo "- [ ] All validation tests pass"
echo "- [ ] Web server redirects configured"  
echo "- [ ] Monitoring dashboard accessible"
echo "- [ ] Team training completed"
echo "- [ ] Rollback plan documented"

# Run final validation
python manage.py validate_ia --full-check
```

### 6.2 Generate Web Server Redirects

```bash
# For Apache
python manage.py generate_redirects --format apache --output apache_redirects.conf
echo "✅ Apache redirects: apache_redirects.conf"

# For Nginx  
python manage.py generate_redirects --format nginx --output nginx_redirects.conf
echo "✅ Nginx redirects: nginx_redirects.conf"

# For .htaccess
python manage.py generate_redirects --format htaccess --output .htaccess_redirects
echo "✅ .htaccess redirects: .htaccess_redirects"
```

### 6.3 Deploy with Monitoring

```bash
# Deploy code
git add .
git commit -m "Enable Information Architecture optimization"
git push origin main

# Monitor deployment
echo "🔍 Post-deployment monitoring:"
echo "1. Check error logs for 404s"
echo "2. Monitor /monitoring/ia-dashboard/"
echo "3. Verify key user flows"
echo "4. Check analytics data"

# Set up alerts
python manage.py shell -c "
print('🚨 Set up alerts for:')
print('  - 404 error spikes')
print('  - Slow page loads')
print('  - High legacy URL usage')
print('  - Navigation anomalies')
"
```

## 🎯 Success Criteria

After activation, you should see:

✅ **Adoption Rate**: >90% within 2 weeks  
✅ **404 Errors**: <10 total  
✅ **Page Load Times**: <2 seconds average  
✅ **User Satisfaction**: Improved navigation feedback  
✅ **SEO Impact**: Better search rankings  

## 🆘 Troubleshooting

If you encounter issues:

1. **Check logs**: `tail -f logs/django.log | grep IA`
2. **Validate setup**: `python manage.py validate_ia`
3. **Monitor dashboard**: `/monitoring/ia-dashboard/`
4. **Rollback if needed**: Restore `urls_backup.py`

## 📞 Support

- **Dashboard**: `/monitoring/ia-dashboard/`
- **Validation**: `python manage.py validate_ia --help`
- **Documentation**: `documentation/` folder
- **Emergency rollback**: Set `USE_OPTIMIZED_URLS = False`

---

**Your Information Architecture optimization is now active! 🎉**

Monitor the dashboard and watch your adoption rate climb to 100%!