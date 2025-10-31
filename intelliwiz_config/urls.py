"""intelliwiz_config URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
import debug_toolbar


# urlpatterns = [
#     # Health check endpoints (no authentication required)
#     path('', include('apps.core.urls_health')),
    
#     path('', SignIn.as_view(), name='login'),
#     path('logout/', SignOut.as_view(), name='logout'),
#     path('dashboard/', login_required(TemplateView.as_view(template_name='layout.html')), name='home'),
#     path('admin/', admin.site.urls),
#     path('onboarding/', include('apps.onboarding.urls')),
#     path('work_order_management/', include('apps.work_order_management.urls')),
#     path('peoples/', include('apps.peoples.urls')),
#     path('', include('apps.attendance.urls')),
#     path('activity/', include('apps.activity.urls')),
#     path('schedhule/', include('apps.scheduler.urls')),
#     path('reports/', include('apps.reports.urls')),
#     path('helpdesk/', include('apps.y_helpdesk.urls')),
#     path('clientbilling/', include('apps.clientbilling.urls')),
#     #path('reminder/', include('apps.reminder.urls')),
#     path('email/', include(email_urls)), 
#     path('__debug__/', include(debug_toolbar.urls)), # shoul use when debug = True
#     path('select2/', include('django_select2.urls')),
#     path("legacy-endpoint", FileUploadLegacyView.as_view()),
#     path("upload/att_file", UploadFile.as_view()),
#     path("api/", include('apps.service.rest_service.urls'), name='api'),
# ]
from intelliwiz_config.urls_optimized import urlpatterns

# Debug toolbar is already included in urls_optimized.py
# Static files are already handled in urls_optimized.py
