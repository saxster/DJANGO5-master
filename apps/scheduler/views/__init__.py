"""
Scheduler Views

Modular view structure following SRP and Rule 8 compliance.

Import all views for backward compatibility with existing URLs.

Directory Structure:
- internal_tour_views.py: Internal tour scheduling
- external_tour_views.py: External tour scheduling
- task_views.py: Task scheduling
- jobneed_views.py: Jobneed management
"""

from apps.schedhuler.views.internal_tour_views import (
    Schd_I_TourFormJob,
    Update_I_TourFormJob,
    Retrive_I_ToursJob,
    Retrive_I_ToursJobneed,
    Get_I_TourJobneed,
    add_cp_internal_tour,
    delete_checkpoint as deleteChekpointFromTour,
)

from apps.schedhuler.views.external_tour_views import (
    Schd_E_TourFormJob,
    Update_E_TourFormJob,
    Retrive_E_ToursJob,
    ExternalTourTracking,
    save_assigned_sites_for_externaltour,
)

from apps.schedhuler.views.task_views import (
    SchdTaskFormJob,
    UpdateSchdTaskJob,
    RetriveSchdTasksJob,
    RetrieveTasksJobneed,
    GetTaskFormJobneed,
)

from apps.schedhuler.views.jobneed_views import (
    JobneedTours,
    JobneedExternalTours,
    JobneedTasks,
    JobneednJNDEditor,
)

from apps.schedhuler.views_optimized import (
    get_cron_datetime_optimized as get_cron_datetime,
)

__all__ = [
    'Schd_I_TourFormJob',
    'Update_I_TourFormJob',
    'Retrive_I_ToursJob',
    'Retrive_I_ToursJobneed',
    'Get_I_TourJobneed',
    'add_cp_internal_tour',
    'deleteChekpointFromTour',
    'Schd_E_TourFormJob',
    'Update_E_TourFormJob',
    'Retrive_E_ToursJob',
    'ExternalTourTracking',
    'save_assigned_sites_for_externaltour',
    'SchdTaskFormJob',
    'UpdateSchdTaskJob',
    'RetriveSchdTasksJob',
    'RetrieveTasksJobneed',
    'GetTaskFormJobneed',
    'JobneedTours',
    'JobneedExternalTours',
    'JobneedTasks',
    'JobneednJNDEditor',
    'get_cron_datetime',
]