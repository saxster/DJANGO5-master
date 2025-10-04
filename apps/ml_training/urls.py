"""
URL configuration for ML Training Data Platform.
"""

from django.urls import path
from . import views

app_name = "ml_training"

urlpatterns = [
    # Dataset management
    path("", views.DatasetListView.as_view(), name="dataset_list"),
    path("datasets/create/", views.DatasetCreateView.as_view(), name="dataset_create"),
    path("datasets/<int:dataset_id>/", views.DatasetDetailView.as_view(), name="dataset_detail"),
    path("datasets/<int:dataset_id>/upload/", views.DatasetUploadView.as_view(), name="dataset_upload"),

    # Labeling interface
    path("labeling/", views.LabelingDashboard.as_view(), name="labeling_dashboard"),
    path("labeling/task/<int:task_id>/", views.LabelingInterface.as_view(), name="labeling_interface"),

    # Active learning
    path("active-learning/", views.ActiveLearningDashboard.as_view(), name="active_learning_dashboard"),
    path("active-learning/select-batch/", views.SelectLabelingBatch.as_view(), name="select_labeling_batch"),

    # Feedback integration
    path("feedback/", views.FeedbackDashboard.as_view(), name="feedback_dashboard"),
    path("feedback/import/", views.ImportFeedbackView.as_view(), name="import_feedback"),

    # API endpoints
    path("api/datasets/", views.DatasetAPIView.as_view(), name="api_datasets"),
    path("api/datasets/<int:dataset_id>/upload/", views.BulkUploadAPIView.as_view(), name="api_bulk_upload"),
    path("api/examples/<uuid:example_uuid>/label/", views.LabelExampleAPIView.as_view(), name="api_label_example"),
    path("api/feedback/capture/", views.CaptureFeedbackAPIView.as_view(), name="api_capture_feedback"),
]