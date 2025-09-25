"""
Optimized URL Configuration for YOUTILITY5
Implements clean, domain-driven information architecture
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from django.views.generic import TemplateView, RedirectView
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django_email_verification import urls as email_urls
from apps.peoples.views import SignIn, SignOut
from graphene_file_upload.django import FileUploadGraphQLView
import debug_toolbar
from apps.service.mutations import UploadFile
from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.views.dashboard_views import ModernDashboardView
from apps.core.health_checks import (
    health_check,
    readiness_check,
    liveness_check,
    detailed_health_check,
)

# Main URL patterns with optimized structure
urlpatterns = [
    # ========== AUTHENTICATION ==========
    path('', SignIn.as_view(), name='login'),  # Root redirects to login
    path('logout/', SignOut.as_view(), name='logout'),  # Legacy logout URL
    path('auth/login/', SignIn.as_view(), name='auth_login'),
    path('auth/logout/', SignOut.as_view(), name='auth_logout'),
    path('auth/verify/', include(email_urls)),  # This handles /auth/verify/email/<token>
    path('auth/verify-email/', RedirectView.as_view(url='/peoples/verifyemail', query_string=True), name='auth_verify_email'),
    
    # ========== DASHBOARD ==========
    path('dashboard/', login_required(ModernDashboardView.as_view()), name='dashboard'),
    path('home/', login_required(ModernDashboardView.as_view()), name='home'),  # Legacy home URL
    path('dashboard/', include('apps.core.urls_dashboard')),
    
    # ========== CORE BUSINESS DOMAINS ==========
    # Operations (Tasks, Tours, Work Orders, PPM)
    path('operations/', include('apps.core.urls_operations')),
    
    # Assets (Inventory, Maintenance, Locations, Monitoring)
    path('assets/', include('apps.core.urls_assets')),
    
    # People (Directory, Attendance, Groups, Expenses)
    path('people/', include('apps.core.urls_people')),
    
    # Help Desk (Tickets, Escalations, Requests)
    path('help-desk/', include('apps.core.urls_helpdesk')),
    
    # Reports (All reporting functionality)
    path('reports/', include('apps.reports.urls')),
    
    # ========== ADMINISTRATION ==========
    path('admin/', include('apps.core.urls_admin')),
    
    # ========== API ENDPOINTS ==========
    path('api/v1/', include('apps.service.rest_service.urls')),
    path('api/graphql/', csrf_exempt(FileUploadGraphQLView.as_view(graphiql=True))),
    path('graphql/', csrf_exempt(FileUploadGraphQLView.as_view(graphiql=True))),  # With trailing slash
    path('graphql', csrf_exempt(FileUploadGraphQLView.as_view(graphiql=True))),   # Without trailing slash
    path('api/upload/att_file/', UploadFile.as_view()),
    
    # ========== MONITORING & HEALTH ==========
    path('monitoring/', include('monitoring.urls')),

    # Root-level health endpoints for testing and monitoring
    path('health/', health_check, name='root_health_check'),
    path('ready/', readiness_check, name='root_readiness_check'),
    path('alive/', liveness_check, name='root_liveness_check'),
    path('health/detailed/', detailed_health_check, name='root_detailed_health_check'),
    
    # ========== AI & INTELLIGENCE ==========
    # All AI apps have been removed to reduce complexity
    
    # ========== UTILITIES ==========
    path('select2/', include('django_select2.urls')),
    
    # ========== COMMON WEB REQUESTS ==========
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('sitemap.xml', RedirectView.as_view(url='/static/sitemap.xml', permanent=True)),
    
    # ========== DEBUG (Development Only) ==========
]

# Add debug toolbar in development
if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
    # Static files serving in development
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ========== LEGACY URL REDIRECTS ==========
# Add all legacy URL redirects to maintain backward compatibility
# These will automatically track usage and redirect to new URLs
# DISABLED: OptimizedURLRouter causing issues with scheduler and other apps
# urlpatterns += OptimizedURLRouter.get_optimized_patterns()

# ========== FALLBACK PATTERNS ==========
# Keep original app URLs as fallback during transition
# These can be removed once migration is complete
LEGACY_PATTERNS = [
    # These are included but will trigger redirects from OptimizedURLRouter
    path('onboarding/', include('apps.onboarding.urls')),
    path('work_order_management/', include('apps.work_order_management.urls')),
    path('peoples/', include('apps.peoples.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('activity/', include('apps.activity.urls')),
    path('schedhuler/', include('apps.schedhuler.urls')),
    path('schedhule/', include(('apps.schedhuler.urls', 'schedhuler'), namespace='schedhuler_typo')),  # Common typo with different namespace
    path('helpdesk/', include('apps.y_helpdesk.urls')),
    path('y_helpdesk/', include(('apps.y_helpdesk.urls', 'helpdesk'), namespace='y_helpdesk')),
    path('clientbilling/', include('apps.clientbilling.urls')),
    # reminder app removed
]

# Add legacy patterns only if feature flag is enabled
if getattr(settings, 'ENABLE_LEGACY_URLS', True):
    urlpatterns += LEGACY_PATTERNS

# ========== CUSTOM 404 HANDLER ==========
# Track 404s for dead URL detection
handler404 = 'apps.core.views.base_views.custom_404_view'
handler500 = 'apps.core.views.base_views.custom_500_view'