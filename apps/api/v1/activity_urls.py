"""
Activity API v1 URLs

Consolidated API endpoints for activity app moved to centralized /api/v1/ namespace.

Previously scattered across:
- /activity/api/meter_readings/
- /activity/api/vehicle_entries/

Now centralized under:
- /api/v1/meter-readings/
- /api/v1/vehicle-entries/

Follows RESTful conventions and URL_STANDARDS.md
"""

from django.urls import path
from apps.activity.views.meter_reading_views import (
    MeterReadingUploadAPIView,
    MeterReadingValidateAPIView,
    MeterReadingListAPIView,
    MeterReadingAnalyticsAPIView,
)
from apps.activity.views.vehicle_entry_views import (
    VehicleEntryUploadAPIView,
    VehicleExitAPIView,
    VehicleHistoryAPIView,
    ActiveVehiclesAPIView,
)

app_name = 'api_v1_activity'

urlpatterns = [
    # ========== METER READINGS API ==========
    # RESTful resource: /api/v1/meter-readings/

    # Upload meter reading (mobile/IoT devices)
    path('meter-readings/upload/', MeterReadingUploadAPIView.as_view(), name='meter-reading-upload'),

    # Validate meter reading
    path('meter-readings/<int:reading_id>/validate/', MeterReadingValidateAPIView.as_view(), name='meter-reading-validate'),

    # List meter readings for an asset
    path('meter-readings/asset/<int:asset_id>/', MeterReadingListAPIView.as_view(), name='meter-reading-list'),

    # Get analytics for asset meter readings
    path('meter-readings/asset/<int:asset_id>/analytics/', MeterReadingAnalyticsAPIView.as_view(), name='meter-reading-analytics'),

    # Alternative: Get all readings for an asset (alias)
    path('assets/<int:asset_id>/meter-readings/', MeterReadingListAPIView.as_view(), name='asset-meter-readings'),
    path('assets/<int:asset_id>/meter-readings/analytics/', MeterReadingAnalyticsAPIView.as_view(), name='asset-meter-readings-analytics'),

    # ========== VEHICLE ENTRIES API ==========
    # RESTful resource: /api/v1/vehicle-entries/

    # Upload vehicle entry (gate systems)
    path('vehicle-entries/upload/', VehicleEntryUploadAPIView.as_view(), name='vehicle-entry-upload'),

    # Record vehicle exit
    path('vehicle-entries/exit/', VehicleExitAPIView.as_view(), name='vehicle-exit'),

    # Get vehicle history by license plate
    path('vehicle-entries/history/<str:license_plate>/', VehicleHistoryAPIView.as_view(), name='vehicle-history'),

    # List active vehicles currently on premises
    path('vehicle-entries/active/', ActiveVehiclesAPIView.as_view(), name='active-vehicles'),

    # ========== LEGACY COMPATIBILITY ==========
    # Redirects from old /activity/api/* patterns
    # These are kept for 6 months, then deprecated

    # Legacy meter reading patterns
    path('activity/meter-readings/upload/', MeterReadingUploadAPIView.as_view(), name='meter-reading-upload-legacy'),
    path('activity/meter-readings/<int:reading_id>/validate/', MeterReadingValidateAPIView.as_view(), name='meter-reading-validate-legacy'),
    path('activity/meter-readings/asset/<int:asset_id>/', MeterReadingListAPIView.as_view(), name='meter-reading-list-legacy'),
    path('activity/meter-readings/asset/<int:asset_id>/analytics/', MeterReadingAnalyticsAPIView.as_view(), name='meter-reading-analytics-legacy'),

    # Legacy vehicle entry patterns
    path('activity/vehicle-entries/upload/', VehicleEntryUploadAPIView.as_view(), name='vehicle-entry-upload-legacy'),
    path('activity/vehicle-entries/exit/', VehicleExitAPIView.as_view(), name='vehicle-exit-legacy'),
    path('activity/vehicle-entries/history/<str:license_plate>/', VehicleHistoryAPIView.as_view(), name='vehicle-history-legacy'),
    path('activity/vehicle-entries/active/', ActiveVehiclesAPIView.as_view(), name='active-vehicles-legacy'),
]

# ========== API DOCUMENTATION NOTES ==========
"""
OpenAPI Schema Generation:

These endpoints are automatically included in the OpenAPI schema at:
    /api/schema/swagger.json
    /api/schema/redoc/

Example Request (Meter Reading Upload):
    POST /api/v1/meter-readings/upload/
    Content-Type: application/json
    Authorization: Bearer <token>

    {
        "asset_id": 123,
        "reading_value": 1234.56,
        "reading_unit": "kWh",
        "reading_date": "2025-10-11T14:30:00Z",
        "photo": "<base64_encoded_image>"
    }

Example Response:
    HTTP 201 Created
    {
        "id": 456,
        "asset_id": 123,
        "reading_value": 1234.56,
        "status": "pending_validation",
        "created_at": "2025-10-11T14:30:15Z",
        "_links": {
            "self": "/api/v1/meter-readings/456/",
            "validate": "/api/v1/meter-readings/456/validate/",
            "asset": "/api/v1/assets/123/"
        }
    }

Rate Limiting:
    - Authenticated users: 1000 requests/hour
    - Anonymous users: 100 requests/hour
    - Upload endpoints: 100 requests/hour (even for authenticated)

Authentication:
    - Token-based (Authorization: Bearer <token>)
    - Session-based (Django session cookie)
    - API Key (X-API-Key: <key>)

Error Responses:
    - 400 Bad Request: Invalid input
    - 401 Unauthorized: Missing/invalid authentication
    - 403 Forbidden: Insufficient permissions
    - 404 Not Found: Resource doesn't exist
    - 429 Too Many Requests: Rate limit exceeded
    - 500 Internal Server Error: Server error

For mobile client SDK generation:
    npx @openapitools/openapi-generator-cli generate \
        -i http://localhost:8000/api/schema/swagger.json \
        -g kotlin \
        -o mobile/kotlin-client/

For questions:
    - API Documentation: /api/schema/redoc/
    - API Standards: URL_STANDARDS.md
    - Migration Guide: URL_MIGRATION_GUIDE.md
    - Support: #api-help on Slack
"""
