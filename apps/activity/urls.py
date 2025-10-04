from django.urls import path
from apps.activity.views.question_views import (
    Question,
    QuestionSet,
    QsetNQsetBelonging,
    Checkpoint,
    deleteQSB,
)
from apps.activity.views.asset_views import (
    AssetView,
    AssetMaintainceList,
    AssetComparisionView,
    ParameterComparisionView,
    PeopleNearAsset,
    AssetLogView,
)
from apps.activity.views.location_views import LocationView
from apps.activity.views.job_views import (
    PPMView,
    PPMJobneedView,
    AdhocTasks,
    AdhocTours,
    CalendarView,
)
from apps.activity.views.attachment_views import Attachments, PreviewImage
from apps.activity.views.deviceevent_log_views import MobileUserLog, MobileUserDetails
from apps.activity.views.site_survey_views import SiteSurveyListView, SiteSurveyDetailView
from apps.activity.views.transcript_views import (
    TranscriptStatusView,
    TranscriptManagementView,
    SpeechServiceStatusView,
)
from apps.activity.views.meter_reading_views import (
    MeterReadingUploadAPIView,
    MeterReadingValidateAPIView,
    MeterReadingListAPIView,
    MeterReadingAnalyticsAPIView,
    MeterReadingDashboard,
    MeterReadingCapture,
    MeterReadingValidation,
    MeterReadingAssetView,
)
from apps.activity.views.vehicle_entry_views import (
    VehicleEntryUploadAPIView,
    VehicleExitAPIView,
    VehicleHistoryAPIView,
    ActiveVehiclesAPIView,
    VehicleEntryDashboard,
    VehicleEntryCapture,
    VehicleEntryApproval,
    VehicleSecurityAlerts,
)

app_name = "activity"
urlpatterns = [
    path("question/", Question.as_view(), name="question"),
    path("questionset/", QuestionSet.as_view(), name="checklist"),
    # path('questionset/', views.QuestionSet.as_view(), name='questionset'),
    path("checkpoint/", Checkpoint.as_view(), name="checkpoint"),
    # path('smartplace/', views.Smartplace.as_view(), name='smartplace'),
    path("ppm/", PPMView.as_view(), name="ppm"),
    path("ppm_jobneed/", PPMJobneedView.as_view(), name="ppmjobneed"),
    path("asset/", AssetView.as_view(), name="asset"),
    path("location/", LocationView.as_view(), name="location"),
    path("delete_qsb/", deleteQSB, name="delete_qsb"),
    # path('esclist/', views.RetriveEscList.as_view(), name='esc_list'),
    path("adhoctasks/", AdhocTasks.as_view(), name="adhoctasks"),
    path("adhoctours/", AdhocTours.as_view(), name="adhoctours"),
    path("assetmaintainance/", AssetMaintainceList.as_view(), name="assetmaintainance"),
    path("qsetnQsetblng/", QsetNQsetBelonging.as_view(), name="qset_qsetblng"),
    path("mobileuserlogs/", MobileUserLog.as_view(), name="mobileuserlogs"),
    path("mobileuserdetails/", MobileUserDetails.as_view(), name="mobileuserdetails"),
    path("peoplenearassets/", PeopleNearAsset.as_view(), name="peoplenearasset"),
    path("attachments/", Attachments.as_view(), name="attachments"),
    path("previewImage/", PreviewImage.as_view(), name="previewImage"),
    path("calendar/", CalendarView.as_view(), name="calendar"),
    path("assetlog/", AssetLogView.as_view(), name="assetlogs"),
    path("comparision/", AssetComparisionView.as_view(), name="comparision"),
    path(
        "param_comparision/",
        ParameterComparisionView.as_view(),
        name="param_comparision",
    ),
    path("site_survey/", SiteSurveyListView.as_view(), name="site_survey_list"),
    path("site_survey_detail/", SiteSurveyDetailView.as_view(), name="site_survey_detail"),
    # Speech-to-Text API endpoints
    path("transcript_status/", TranscriptStatusView.as_view(), name="transcript_status"),
    path("transcript_management/", TranscriptManagementView.as_view(), name="transcript_management"),
    path("speech_service_status/", SpeechServiceStatusView.as_view(), name="speech_service_status"),

    # Meter Reading endpoints
    path("meter_readings/", MeterReadingDashboard.as_view(), name="meter_reading_dashboard"),
    path("meter_readings/capture/", MeterReadingCapture.as_view(), name="meter_reading_capture"),
    path("meter_readings/validation/", MeterReadingValidation.as_view(), name="meter_reading_validation"),
    path("meter_readings/asset/<int:asset_id>/", MeterReadingAssetView.as_view(), name="meter_reading_asset"),

    # Meter Reading API endpoints (for mobile/external access)
    path("api/meter_readings/upload/", MeterReadingUploadAPIView.as_view(), name="api_meter_reading_upload"),
    path("api/meter_readings/<int:reading_id>/validate/", MeterReadingValidateAPIView.as_view(), name="api_meter_reading_validate"),
    path("api/meter_readings/asset/<int:asset_id>/", MeterReadingListAPIView.as_view(), name="api_meter_reading_list"),
    path("api/meter_readings/asset/<int:asset_id>/analytics/", MeterReadingAnalyticsAPIView.as_view(), name="api_meter_reading_analytics"),

    # Vehicle Entry endpoints
    path("vehicle_entries/", VehicleEntryDashboard.as_view(), name="vehicle_entry_dashboard"),
    path("vehicle_entries/capture/", VehicleEntryCapture.as_view(), name="vehicle_entry_capture"),
    path("vehicle_entries/approval/", VehicleEntryApproval.as_view(), name="vehicle_entry_approval"),
    path("vehicle_entries/alerts/", VehicleSecurityAlerts.as_view(), name="vehicle_security_alerts"),

    # Vehicle Entry API endpoints (for gate systems/mobile access)
    path("api/vehicle_entries/upload/", VehicleEntryUploadAPIView.as_view(), name="api_vehicle_entry_upload"),
    path("api/vehicle_entries/exit/", VehicleExitAPIView.as_view(), name="api_vehicle_exit"),
    path("api/vehicle_entries/history/<str:license_plate>/", VehicleHistoryAPIView.as_view(), name="api_vehicle_history"),
    path("api/vehicle_entries/active/", ActiveVehiclesAPIView.as_view(), name="api_active_vehicles"),
]
