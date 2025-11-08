"""
Optimized URL Configuration for YOUTILITY5
Implements clean, domain-driven information architecture
"""
from django.contrib import admin
from django.conf import settings

# Set admin site branding (centralized to prevent conflicts)
admin.site.site_header = 'IntelliWiz Administration'
admin.site.site_title = 'IntelliWiz Admin'
admin.site.index_title = 'System Administration Dashboard'
from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import JavaScriptCatalog
from django.views.generic import TemplateView, RedirectView
# from django.views.decorators.csrf import csrf_exempt  # Removed: CSRF protection now handled by middleware
from django.contrib.auth.decorators import login_required
from django_email_verification import urls as email_urls
from apps.peoples.views import SignIn, SignOut
# Legacy schema imports removed - October 2025 (REST API migration complete)
import debug_toolbar
from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.views.dashboard_views import ModernDashboardView

# Import health check views
from apps.core.health_check_views import (
    health_check,
    readiness_check,
    liveness_check,
    detailed_health_check
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
    path('dashboards/', include('apps.core.urls_dashboard_hub')),  # Dashboard Hub Infrastructure

    # ========== CORE BUSINESS DOMAINS ==========
    # Operations (Tasks, Tours, Work Orders, PPM)
    path('operations/', include('apps.core.urls_operations')),

    # Assets (Inventory, Maintenance, Locations, Monitoring)
    path('assets/', include('apps.core.urls_assets')),

    # People (Directory, Attendance, Groups, Expenses)
    path('people/', include('apps.core.urls_people')),

    # People Onboarding (Employee/Contractor onboarding workflow)
    path('people-onboarding/', include('apps.people_onboarding.urls')),

    # NOC (Network Operations Center)
    path('noc/', include('apps.noc.urls')),

    # Journal & Wellness (Personal journaling with privacy controls and evidence-based wellness education)
    path('journal/', include('apps.journal.urls')),
    path('wellness/', include('apps.wellness.urls')),

    # Help Desk (Tickets, Escalations, Requests)
    path('help-desk/', include('apps.core.urls_helpdesk')),
    
    # Reports (All reporting functionality)
    path('reports/', include('apps.reports.urls')),
    
    # Intelligent Report Generation (AI-powered report creation with self-improvement)
    path('', include('apps.report_generation.urls')),

    # Stream Testbench (Stream testing and anomaly detection)
    path('streamlab/', include('apps.streamlab.urls')),
    path('streamlab/ai/', include('apps.ai_testing.urls')),

    # ========== ADMINISTRATION ==========
    path('admin/', include('apps.core.urls_admin')),
    path('admin/secrets/', include('apps.core.urls_secrets')),  # Encrypted Secrets Management
    path('admin/', include('apps.core.urls.saved_views')),  # Saved Views & Exports
    
    # ========== API ENDPOINTS ==========
    # REST API v2 (Primary API - Type-safe endpoints with Pydantic validation)
    # V1 API DELETED - November 7, 2025 - All clients migrated to V2
    path('api/v2/', include('apps.api.v2.urls')),  # Core V2 API (Auth, People, HelpDesk, Reports, Wellness, Command Center, HelpBot, Telemetry)
    path('api/v2/noc/', include(('apps.noc.api.v2.urls', 'noc_api_v2'), namespace='noc_telemetry_api')),  # NOC Telemetry API
    path('api/v2/operations/', include('apps.api.v2.operations_urls')),  # Operations domain (Jobs, Tasks, Tours, PPM)
    path('api/v2/attendance/', include('apps.api.v2.attendance_urls')),  # Attendance domain (Check-in/out, Conveyance)

    # Legacy endpoints (non-versioned, will remain)
    path('api/v1/biometrics/', include('apps.api.biometrics_urls')),  # Biometric Authentication API (Sprint 2)
    path('api/v1/assets/nfc/', include('apps.activity.api.nfc_urls')),  # NFC Asset Tracking API (Sprint 4)
    path('api/v1/journal/', include(('apps.journal.urls', 'journal'), namespace='journal_api')),  # Journal & Wellness API endpoints (legacy routing)
    path('api/v1/wellness/', include(('apps.wellness.urls', 'wellness'), namespace='wellness_api')),  # Wellness education API endpoints (legacy routing)
    path('api/v1/search/', include(('apps.search.urls', 'search'))),  # Global Cross-Domain Search API
    path('api/v1/helpbot/', include('apps.helpbot.urls')),  # AI HelpBot API endpoints (legacy routing)
    path('api/dashboard/', include('apps.core.urls_agent_api')),  # Dashboard Agent Intelligence API
    path('api/performance/', include(('apps.performance_analytics.urls', 'performance_analytics'), namespace='performance_api')),  # Performance Analytics API
    path('', include('apps.core.urls.cron_management')),  # Unified Cron Management API
    path('api/noc/', include(('apps.noc.urls', 'noc'), namespace='noc_api')),  # NOC API endpoints

    # Bounded Context APIs (Multimodal Onboarding)
    path('api/v2/client-onboarding/', include('apps.client_onboarding.urls')),  # Client onboarding context
    path('api/v2/site-onboarding/', include('apps.site_onboarding.urls')),  # Site survey context
    path('api/v2/worker-onboarding/', include('apps.people_onboarding.urls')),  # Worker intake context
    path('api/v2/conversation/', include('apps.core_onboarding.urls')),  # Conversation session management

    # ========== Legacy Schema Removed - October 2025 ==========
    # Single API surface operates at /api/v1/
    # See migration notes for rollout details

    # ========== API DOCUMENTATION (OpenAPI/Swagger) ==========
    # Consolidated OpenAPI schema for v1 + v2 REST endpoints
    # Enables Kotlin/Swift codegen for mobile clients
    # Generated from: drf-spectacular (intelliwiz_config/settings/rest_api.py:138)
    path('api/schema/', include('apps.api.docs.urls')),

    # ========== MONITORING & HEALTH ==========
    path('monitoring/', include('monitoring.urls')),
    path('admin/monitoring/', include('apps.core.urls_performance_monitoring')),  # Performance dashboards (Celery/Cache/DB)
    path('security/', include('apps.core.urls_security')),  # Security monitoring dashboard (CVSS 8.1 fix)
    path('api/spatial-performance/', include('apps.core.urls.spatial_performance_urls')),  # GPS/Geolocation performance monitoring

    # API lifecycle management (Admin-only)
    path('', include('apps.core.urls_api_lifecycle')),  # API deprecation and versioning dashboards

    # Cache monitoring and management (Admin-only)
    path('', include('apps.core.urls_cache')),  # Includes /admin/cache/ and /cache/health/ endpoints

    # Root-level health endpoints for testing and monitoring
    path('health/', health_check, name='root_health_check'),
    path('ready/', readiness_check, name='root_readiness_check'),
    path('alive/', liveness_check, name='root_liveness_check'),
    path('health/detailed/', detailed_health_check, name='root_detailed_health_check'),
    
    # ========== AI & INTELLIGENCE ==========
    # ML Training Data Platform
    path('ml-training/', include('apps.ml_training.urls')),

    # Help Center - Knowledge base and AI assistant
    path('', include('apps.help_center.urls')),

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
    path('work_order_management/', include('apps.work_order_management.urls')),
    path('peoples/', include(('apps.peoples.urls', 'people'), namespace='peoples_legacy')),  # Legacy redirect for peoples → people
    path('attendance/', include('apps.attendance.urls')),
    path('activity/', include('apps.activity.urls')),
    path('scheduler/', include('apps.scheduler.urls')),
    path('helpdesk/', include('apps.y_helpdesk.urls')),
    path('y_helpdesk/', include(('apps.y_helpdesk.urls', 'helpdesk'), namespace='y_helpdesk')),
    path('clientbilling/', include('apps.clientbilling.urls')),
    # reminder app removed

    # ========== INTERNATIONALIZATION ==========
    path('i18n/', include('django.conf.urls.i18n')),  # Language switching URLs
    path('jsi18n/', JavaScriptCatalog.as_view(packages=['apps.core', 'apps.peoples', 'apps.scheduler']), name='javascript-catalog'),
]

# Add legacy patterns only if feature flag is enabled
if getattr(settings, 'ENABLE_LEGACY_URLS', True):
    urlpatterns += LEGACY_PATTERNS

# ========== CUSTOM ERROR HANDLERS ==========
# Custom error views for user-friendly error pages
# Defined in: apps/core/middleware/user_friendly_error_middleware.py
handler404 = 'apps.core.middleware.user_friendly_error_middleware.custom_404_view'
handler500 = 'apps.core.middleware.user_friendly_error_middleware.custom_500_view'
