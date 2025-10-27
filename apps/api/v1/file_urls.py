"""
File Upload API URLs (v1)

Domain: /api/v1/files/

Handles secure file uploads with validation and metadata tracking.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path
from apps.api.v1.file_views import FileUploadView, FileDownloadView, FileMetadataView

app_name = 'files'

urlpatterns = [
    # File operations
    path('upload/', FileUploadView.as_view(), name='upload'),
    path('<str:file_id>/download/', FileDownloadView.as_view(), name='download'),
    path('<str:file_id>/metadata/', FileMetadataView.as_view(), name='metadata'),
]
