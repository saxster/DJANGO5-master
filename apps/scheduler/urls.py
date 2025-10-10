from django.urls import path
from apps.schedhuler.views import (
    Schd_I_TourFormJob,
    Update_I_TourFormJob,
    Retrive_I_ToursJob,
    Retrive_I_ToursJobneed,
    Get_I_TourJobneed,
    Schd_E_TourFormJob,
    Update_E_TourFormJob,
    Retrive_E_ToursJob,
    SchdTaskFormJob,
    UpdateSchdTaskJob,
    RetriveSchdTasksJob,
    RetrieveTasksJobneed,
    GetTaskFormJobneed,
    JobneedTours,
    JobneedExternalTours,
    JobneedTasks,
    JobneednJNDEditor,
    ExternalTourTracking,
    add_cp_internal_tour,
    deleteChekpointFromTour,
    save_assigned_sites_for_externaltour,
    get_cron_datetime,
)

app_name = "schedhuler"
urlpatterns = [
    path(
        "schedhule_tour/", Schd_I_TourFormJob.as_view(), name="create_tour"
    ),  # job
    path("schedhule_task/", SchdTaskFormJob.as_view(), name="create_task"),  # job
    path(
        "external_schedhule_tour/",
        Schd_E_TourFormJob.as_view(),
        name="create_externaltour",
    ),  # job
    path(
        "external_schedhule_tour/saveSites/",
        save_assigned_sites_for_externaltour,
        name="save_assigned_sites",
    ),  # job
    path(
        "schedhule_tour/<str:pk>/",
        Update_I_TourFormJob.as_view(),
        name="update_tour",
    ),  # job
    path(
        "external_schedhule_tour/<str:pk>/",
        Update_E_TourFormJob.as_view(),
        name="update_externaltour",
    ),  # job
    path(
        "schedhule_task/<str:pk>/",
        UpdateSchdTaskJob.as_view(),
        name="update_task",
    ),  # job
    path(
        "schedhule_tours/", Retrive_I_ToursJob.as_view(), name="retrieve_tours"
    ),  # job
    path(
        "schedhule_tasks/", RetriveSchdTasksJob.as_view(), name="retrieve_tasks"
    ),  # job
    path(
        "schedhule_externaltours/",
        Retrive_E_ToursJob.as_view(),
        name="retrieve_externaltours",
    ),  # job
    path(
        "delete-checkpoint/",
        deleteChekpointFromTour,
        name="delete_checkpointTour",
    ),  # job
    path(
        "internal-tours/",
        Retrive_I_ToursJobneed.as_view(),
        name="retrieve_internaltours",
    ),  # jobneed
    path(
        "tasklist_jobneed/",
        RetrieveTasksJobneed.as_view(),
        name="retrieve_tasks_jobneed",
    ),  # jobneed
    path(
        "internal-tour/<str:pk>/",
        Get_I_TourJobneed.as_view(),
        name="internaltour",
    ),  # jobneed
    path(
        "task_jobneed/<str:pk>/",
        GetTaskFormJobneed.as_view(),
        name="update_task_jobneed",
    ),  # jobneed
    path(
        "internal-tour/add/", add_cp_internal_tour, name="add_checkpoint"
    ),  # jobneed
    path("getCronDateTime/", get_cron_datetime, name="getCronDateTime"),
    # SINGLE VIEW CRUD
    path("jobneedtours/", JobneedTours.as_view(), name="jobneedtours"),
    path(
        "jobneedexternaltours/",
        JobneedExternalTours.as_view(),
        name="jobneedexternaltours",
    ),
    path("jnd/editor/", JobneednJNDEditor.as_view(), name="jn_jnd_editor"),
    path("jobneedtasks/", JobneedTasks.as_view(), name="jobneedtasks"),
    path(
        "site_tour_tracking/",
        ExternalTourTracking.as_view(),
        name="site_tour_tracking",
    ),
]

# NOTE: Legacy views for SchdTasks, InternalTourScheduling, ExternalTourScheduling
# and run_internal_tour_scheduler have been moved to views_legacy.py
# These views require significant refactoring and are not yet migrated
