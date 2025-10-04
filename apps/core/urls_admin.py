"""
Consolidated URL configuration for Admin domain
Combines onboarding, clientbilling, and administrative functionality
"""
from django.urls import path, include
from django.contrib import admin
from apps.onboarding import views as onboarding_views
from apps.core.views import ia_dashboard_views

# Import clientbilling views if available
try:
except ImportError:
    billing_views = None

app_name = 'admin_panel'

urlpatterns = [
    # Django Admin
    path('django/', admin.site.urls),
    
    # ========== BUSINESS UNITS ==========
    path('business-units/', onboarding_views.BtView.as_view(), name='bu_list'),
    
    # ========== CLIENTS ==========
    path('clients/', onboarding_views.Client.as_view(), name='clients_list'),
    
    # ========== CONTRACTS ==========
    path('contracts/', onboarding_views.ContractView.as_view(), name='contracts_list'),
    
    # ========== CONFIGURATION ==========
    # Type Definitions
    path('config/types/', onboarding_views.TypeAssistView.as_view(), name='config_types'),
    path('config/types/super/', onboarding_views.SuperTypeAssist.as_view(), name='config_super_types'),

    # Shifts
    path('config/shifts/', onboarding_views.ShiftView.as_view(), name='config_shifts'),

    # Geofences
    path('config/geofences/', onboarding_views.GeoFence.as_view(), name='config_geofences'),

    # ========== SYSTEM MANAGEMENT ==========
    # Cron Job Management
    path('cron/', include('apps.core.urls.cron_management_ui')),

    # Database Performance Monitoring
    path('database/', include('apps.core.urls.database_performance')),

    # Redis Performance Monitoring
    path('redis/', include('apps.core.urls.redis_monitoring_urls')),

    # Task Monitoring Dashboard
    path('tasks/', include('apps.core.urls_task_monitoring')),

    # State Transition Monitoring
    path('state-transitions/', include('apps.core.urls_state_transitions')),

    # Security Dashboards (CSRF, GraphQL audit)
    path('security/', include('apps.core.urls_security_dashboards')),

    # ========== DATA MANAGEMENT ==========
    path('data/import/', onboarding_views.BulkImportData.as_view(), name='data_import'),
    path('data/bulk-update/', onboarding_views.BulkImportUpdate.as_view(), name='data_bulk_update'),

    # ========== INFORMATION ARCHITECTURE ==========
    path('ia-dashboard/', ia_dashboard_views.IADashboardView.as_view(), name='ia_dashboard'),
    path('ia-analytics/', ia_dashboard_views.IAAnalyticsAPIView.as_view(), name='ia_analytics'),
]