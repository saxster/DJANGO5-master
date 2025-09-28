"""
AI Testing URL Configuration
Coverage Gap Management and Test Generation Routes
"""

from django.urls import path, include
from . import views

app_name = 'ai_testing'

urlpatterns = [
    # Coverage Gap Management
    path('coverage-gaps/', views.coverage_gaps_list, name='coverage_gaps_list'),
    path('coverage-gaps/<uuid:gap_id>/', views.coverage_gap_detail, name='coverage_gap_detail'),
    path('coverage-gaps/<uuid:gap_id>/update-status/', views.update_gap_status, name='update_gap_status'),
    path('coverage-gaps/<uuid:gap_id>/generate-test/', views.generate_test, name='generate_test'),

    # Test Generation
    path('test-generation/', views.test_generation_dashboard, name='test_generation_dashboard'),
    path('test-generation/preview/', views.preview_generated_test, name='preview_generated_test'),
    path('test-generation/download/', views.download_generated_test, name='download_generated_test'),

    # AI Insights API (for external access)
    path('api/insights/', views.ai_insights_api, name='ai_insights_api'),
    path('api/coverage-gaps/', views.coverage_gaps_api, name='coverage_gaps_api'),

    # HTMX Partials
    path('partials/gap-card/<uuid:gap_id>/', views.gap_card_partial, name='gap_card_partial'),
    path('partials/test-preview/', views.test_preview_partial, name='test_preview_partial'),

    # REST API endpoints
    path('api/', include('apps.ai_testing.api.urls')),
]