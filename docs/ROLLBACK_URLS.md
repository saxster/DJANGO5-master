# 🔄 Quick Rollback Guide

If you need to quickly revert to the original URL structure:

## Instant Rollback (Safe)

**Option 1: Comment out the new URLs**

In `intelliwiz_config/urls.py`, change:

```python
# Comment out this line:
# from intelliwiz_config.urls_optimized import urlpatterns

# Uncomment the original urlpatterns:
urlpatterns = [
    # Health check endpoints (no authentication required)
    path('', include('apps.core.urls_health')),
    
    path('', SignIn.as_view(), name='login'),
    path('logout/', SignOut.as_view(), name='logout'),
    path('dashboard/', login_required(TemplateView.as_view(template_name='layout.html')), name='home'),
    path('admin/', admin.site.urls),
    path('onboarding/', include('apps.onboarding.urls')),
    path('work_order_management/', include('apps.work_order_management.urls')),
    path('peoples/', include('apps.peoples.urls')),
    path('', include('apps.attendance.urls')),
    path('activity/', include('apps.activity.urls')),
    path('schedhule/', include('apps.schedhuler.urls')),
    path('reports/', include('apps.reports.urls')),
    path('helpdesk/', include('apps.y_helpdesk.urls')),
    path('clientbilling/', include('apps.clientbilling.urls')),
    #path('reminder/', include('apps.reminder.urls')),
    path('email/', include(email_urls)), 
    path('__debug__/', include(debug_toolbar.urls)), # should use when debug = True
    path('select2/', include('django_select2.urls')),
    path("graphql", csrf_exempt(FileUploadGraphQLView.as_view(graphiql = True))),
    path("upload/att_file", UploadFile.as_view()),
    path("api/", include('apps.service.rest_service.urls'), name='api'),
]
```

**Option 2: Use your backup file**

```bash
# Restore from backup
cp intelliwiz_config/urls_backup.py intelliwiz_config/urls.py
```

## Gradual Rollback

**Option 3: Feature flag approach**

Add this to your settings.py:

```python
USE_OPTIMIZED_URLS = False  # Set to False to disable
```

Then modify `intelliwiz_config/urls.py`:

```python
from django.conf import settings

if getattr(settings, 'USE_OPTIMIZED_URLS', False):
    # Use new optimized URLs
    from intelliwiz_config.urls_optimized import urlpatterns
else:
    # Use original URL structure
    urlpatterns = [
        # Your original patterns here
    ]
```

## After Rollback

1. **Restart Django server**:
   ```bash
   python manage.py runserver
   ```

2. **Test original URLs work**:
   - `/schedhuler/jobneedtasks/`
   - `/activity/asset/`
   - `/peoples/people/`

3. **Check logs** for any remaining issues

## Troubleshooting Rollback

If rollback doesn't work:

1. **Check imports**: Make sure you have the required imports:
   ```python
   from django_email_verification import urls as email_urls
   from apps.peoples.views import SignIn, SignOut
   from graphene_file_upload.django import FileUploadGraphQLView
   from apps.service.mutations import UploadFile
   ```

2. **Check apps in INSTALLED_APPS**: Make sure all referenced apps are installed

3. **Clear cache**: 
   ```bash
   python manage.py collectstatic --clear
   ```

## Re-enable Later

When ready to try again:

1. Fix the specific import issues
2. Set `USE_OPTIMIZED_URLS = True`
3. Test step by step

---

**Note**: Rollback is completely safe - it just restores your original working URL structure.