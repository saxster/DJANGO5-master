"""
URL Configuration for People Onboarding Module

Complete routing for both UI views and API endpoints.
"""
from django.urls import path, include
from . import views, api_views

app_name = 'people_onboarding'

urlpatterns = [
    # ========== UI/Template Views ==========

    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('requests/', views.request_list, name='request_list'),
    path('requests/<uuid:uuid>/', views.request_detail, name='request_detail'),

    # Create/Submit Workflow
    path('start/', views.start_onboarding, name='start_onboarding'),
    path('wizard/<uuid:uuid>/', views.onboarding_wizard, name='onboarding_wizard'),

    # Approval Workflow
    path('approvals/', views.approval_list, name='approval_list'),
    path('approvals/<uuid:uuid>/decide/', views.approval_decision, name='approval_decide'),

    # Documents
    path('requests/<uuid:uuid>/documents/', views.document_upload, name='document_upload'),

    # Tasks
    path('requests/<uuid:uuid>/tasks/', views.task_list, name='task_list'),

    # ========== REST API Endpoints ==========

    # Onboarding Requests API
    path('api/requests/', api_views.request_list_api, name='api_request_list'),
    path('api/requests/<uuid:uuid>/', api_views.request_detail_api, name='api_request_detail'),

    # Document Management API
    path('api/documents/upload/', api_views.document_upload_api, name='api_document_upload'),
    path('api/documents/<uuid:uuid>/', api_views.document_delete_api, name='api_document_delete'),

    # Approval API
    path('api/approvals/<uuid:uuid>/decision/', api_views.approval_decision_api, name='api_approval_decision'),

    # Task Management API
    path('api/tasks/<uuid:uuid>/start/', api_views.task_start_api, name='api_task_start'),
    path('api/tasks/<uuid:uuid>/complete/', api_views.task_complete_api, name='api_task_complete'),

    # Analytics/Dashboard API
    path('api/dashboard/analytics/', api_views.dashboard_analytics_api, name='api_dashboard_analytics'),
]