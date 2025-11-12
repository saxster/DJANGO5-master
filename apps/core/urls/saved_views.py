"""
Saved Views URLs
================
URL patterns for saved view management and export functionality.
"""

from django.urls import path

from apps.core.views.saved_view_manager import (
    SavedViewManagerView,
    SaveViewAPIView,
    LoadViewAPIView,
    ExportViewAPIView,
    DeleteViewAPIView,
)

app_name = 'saved_views'

urlpatterns = [
    # View management pages
    path(
        'my-saved-views/',
        SavedViewManagerView.as_view(),
        name='my_saved_views'
    ),
    
    # API endpoints
    path(
        'api/save-view/',
        SaveViewAPIView.as_view(),
        name='api_save_view'
    ),
    path(
        'api/load-view/<int:view_id>/',
        LoadViewAPIView.as_view(),
        name='api_load_view'
    ),
    path(
        'api/export-view/<int:view_id>/',
        ExportViewAPIView.as_view(),
        name='api_export_view'
    ),
    path(
        'api/delete-view/<int:view_id>/',
        DeleteViewAPIView.as_view(),
        name='api_delete_view'
    ),
]
