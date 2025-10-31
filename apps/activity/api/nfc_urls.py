"""
NFC API URL Configuration (Sprint 4.3)

URL patterns for NFC tag management REST API endpoints.

Base URL: /api/v1/assets/nfc/
"""

from django.urls import path
from .nfc_views import (
    NFCTagBindView,
    NFCScanView,
    NFCScanHistoryView,
    NFCTagStatusView
)

app_name = 'nfc_api'

urlpatterns = [
    # Bind tag to asset
    path('bind/', NFCTagBindView.as_view(), name='nfc-bind'),

    # Record NFC scan
    path('scan/', NFCScanView.as_view(), name='nfc-scan'),

    # Get scan history
    path('history/', NFCScanHistoryView.as_view(), name='nfc-history'),

    # Update tag status
    path('status/', NFCTagStatusView.as_view(), name='nfc-status'),
]
