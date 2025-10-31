"""
RESTful URL Configuration for Scheduler App

Implements clean REST conventions:
- Plural nouns for collections
- HTTP methods for actions (not URL verbs)
- Consistent naming with hyphens
- Maximum 3 levels of nesting
- Follows URL_STANDARDS.md

Migration from legacy scheduler/urls.py (Phase 2 - October 2025)
"""

from django.urls import path
from apps.scheduler.views import (
    # Internal Tour Views
    Schd_I_TourFormJob,
    Update_I_TourFormJob,
    Retrive_I_ToursJob,
    Retrive_I_ToursJobneed,
    Get_I_TourJobneed,

    # External Tour Views
    Schd_E_TourFormJob,
    Update_E_TourFormJob,
    Retrive_E_ToursJob,

    # Task Views
    SchdTaskFormJob,
    UpdateSchdTaskJob,
    RetriveSchdTasksJob,
    RetrieveTasksJobneed,
    GetTaskFormJobneed,

    # Job/JobNeed Views
    JobneedTours,
    JobneedExternalTours,
    JobneedTasks,
    JobneednJNDEditor,
    ExternalTourTracking,

    # Utility Functions
    add_cp_internal_tour,
    deleteChekpointFromTour,
    save_assigned_sites_for_externaltour,
    get_cron_datetime,
)

app_name = "scheduler"

# ========== TOURS (INTERNAL) ==========
# RESTful resource: /tours/internal/

internal_tour_patterns = [
    # List internal tours
    path('', Retrive_I_ToursJobneed.as_view(), name='internal-tour-list'),

    # Create internal tour (POST to list endpoint in REST)
    # GET for form, POST for creation
    path('create/', Schd_I_TourFormJob.as_view(), name='internal-tour-create'),

    # Detail, Update, Delete for specific tour
    path('<str:tour_id>/', Get_I_TourJobneed.as_view(), name='internal-tour-detail'),
    path('<str:tour_id>/edit/', Update_I_TourFormJob.as_view(), name='internal-tour-edit'),

    # Sub-resources: Checkpoints
    path('<str:tour_id>/checkpoints/add/', add_cp_internal_tour, name='internal-tour-checkpoint-add'),
    path('<str:tour_id>/checkpoints/<int:checkpoint_id>/delete/', deleteChekpointFromTour, name='internal-tour-checkpoint-delete'),
]

# ========== TOURS (EXTERNAL) ==========
# RESTful resource: /tours/external/

external_tour_patterns = [
    # List external tours
    path('', JobneedExternalTours.as_view(), name='external-tour-list'),

    # Create external tour
    path('create/', Schd_E_TourFormJob.as_view(), name='external-tour-create'),

    # Detail and Edit
    path('<str:tour_id>/', Get_I_TourJobneed.as_view(), name='external-tour-detail'),
    path('<str:tour_id>/edit/', Update_E_TourFormJob.as_view(), name='external-tour-edit'),

    # Assign sites to external tour
    path('<str:tour_id>/sites/assign/', save_assigned_sites_for_externaltour, name='external-tour-sites-assign'),

    # Tracking
    path('tracking/', ExternalTourTracking.as_view(), name='external-tour-tracking'),
]

# ========== TASKS ==========
# RESTful resource: /tasks/

task_patterns = [
    # List tasks
    path('', RetrieveTasksJobneed.as_view(), name='task-list'),

    # Create task
    path('create/', SchdTaskFormJob.as_view(), name='task-create'),

    # Detail and Edit
    path('<str:task_id>/', GetTaskFormJobneed.as_view(), name='task-detail'),
    path('<str:task_id>/edit/', UpdateSchdTaskJob.as_view(), name='task-edit'),
]

# ========== JOB-BASED VIEWS (Scheduled Jobs) ==========
# These are for the Job entity (scheduled instances)

job_tour_patterns = [
    path('', Retrive_I_ToursJob.as_view(), name='job-tour-list'),
    path('create/', Schd_I_TourFormJob.as_view(), name='job-tour-create'),
    path('<str:job_id>/edit/', Update_I_TourFormJob.as_view(), name='job-tour-edit'),
]

job_external_tour_patterns = [
    path('', Retrive_E_ToursJob.as_view(), name='job-external-tour-list'),
    path('create/', Schd_E_TourFormJob.as_view(), name='job-external-tour-create'),
    path('<str:job_id>/edit/', Update_E_TourFormJob.as_view(), name='job-external-tour-edit'),
]

job_task_patterns = [
    path('', RetriveSchdTasksJob.as_view(), name='job-task-list'),
    path('create/', SchdTaskFormJob.as_view(), name='job-task-create'),
    path('<str:job_id>/edit/', UpdateSchdTaskJob.as_view(), name='job-task-edit'),
]

# ========== UTILITIES ==========

utility_patterns = [
    # Get cron datetime calculator
    path('cron/calculate/', get_cron_datetime, name='cron-calculate'),

    # JobNeed/JND Editor
    path('jobneed/editor/', JobneednJNDEditor.as_view(), name='jobneed-editor'),
]

# ========== MAIN URL PATTERNS ==========

urlpatterns = [
    # ========== TOURS ==========
    path('tours/internal/', include(internal_tour_patterns)),
    path('tours/external/', include(external_tour_patterns)),

    # Unified tour views (legacy compatibility)
    path('tours/', JobneedTours.as_view(), name='tour-list-unified'),

    # ========== TASKS ==========
    path('tasks/', include(task_patterns)),

    # ========== SCHEDULED JOBS ==========
    # These are for scheduled instances (Job entity, not JobNeed template)
    path('jobs/tours/internal/', include(job_tour_patterns)),
    path('jobs/tours/external/', include(job_external_tour_patterns)),
    path('jobs/tasks/', include(job_task_patterns)),

    # ========== UTILITIES ==========
    path('utils/', include(utility_patterns)),

    # ========== LEGACY COMPATIBILITY ==========
    # Keep select old URL patterns for backward compatibility
    # These will be deprecated in Q2 2026

    # Legacy "internal-" patterns
    path('internal-tours/', Retrive_I_ToursJobneed.as_view(), name='retrieve_internaltours_legacy'),
    path('internal-tour/<str:pk>/', Get_I_TourJobneed.as_view(), name='internaltour_legacy'),
    path('internal-tour/add/', add_cp_internal_tour, name='add_checkpoint_legacy'),

    # Legacy task patterns
    path('tasklist_jobneed/', RetrieveTasksJobneed.as_view(), name='retrieve_tasks_jobneed_legacy'),
    path('task_jobneed/<str:pk>/', GetTaskFormJobneed.as_view(), name='update_task_jobneed_legacy'),

    # Legacy utility patterns
    path('delete-checkpoint/', deleteChekpointFromTour, name='delete_checkpointTour_legacy'),
    path('getCronDateTime/', get_cron_datetime, name='getCronDateTime_legacy'),

    # Legacy unified views
    path('jobneedtours/', JobneedTours.as_view(), name='jobneedtours_legacy'),
    path('jobneedexternaltours/', JobneedExternalTours.as_view(), name='jobneedexternaltours_legacy'),
    path('jobneedtasks/', JobneedTasks.as_view(), name='jobneedtasks_legacy'),
    path('jnd/editor/', JobneednJNDEditor.as_view(), name='jn_jnd_editor_legacy'),
    path('site_tour_tracking/', ExternalTourTracking.as_view(), name='site_tour_tracking_legacy'),
]

# ========== NOTES FOR DEVELOPERS ==========
"""
URL Migration Guide (Legacy → RESTful):

Refer to URL_STANDARDS.md for current conventions and deprecation timelines.
"""
