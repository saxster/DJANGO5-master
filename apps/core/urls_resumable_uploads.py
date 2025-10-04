"""
URL routing for resumable upload endpoints.

Sprint 3: API endpoints for chunked file uploads.
"""

from django.urls import path
from apps.core.views.resumable_upload_views import (
    InitUploadView,
    UploadChunkView,
    CompleteUploadView,
    CancelUploadView,
    UploadStatusView,
)

app_name = 'resumable_uploads'

urlpatterns = [
    path('init', InitUploadView.as_view(), name='init'),
    path('chunk', UploadChunkView.as_view(), name='chunk'),
    path('complete', CompleteUploadView.as_view(), name='complete'),
    path('cancel', CancelUploadView.as_view(), name='cancel'),
    path('status/<uuid:upload_id>', UploadStatusView.as_view(), name='status'),
]