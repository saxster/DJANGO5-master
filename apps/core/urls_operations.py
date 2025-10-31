"""
Consolidated URL configuration for Operations domain
Combines: scheduler, work_order_management, and parts of activity apps
"""
from django.urls import path, include

# Import actual views that exist
from apps.scheduler import views as scheduler_views
from apps.work_order_management import views as wom_views
# Import activity views for PPM functionality
from apps.activity.views.job_views import PPMView, PPMJobneedView
# Adhoc functionality from scheduler
AdhocTasks = scheduler_views.JobneedTasks
AdhocTours = scheduler_views.JobneedTours

app_name = 'operations'

urlpatterns = [
    # ========== TASKS ==========
    path('tasks/', scheduler_views.JobneedTasks.as_view(), name='tasks_list'),
    path('tasks/adhoc/', AdhocTasks.as_view(), name='tasks_adhoc'),
    path('tasks/schedule/', scheduler_views.SchdTaskFormJob.as_view(), name='tasks_schedule'),
    path('tasks/scheduled/', scheduler_views.RetriveSchdTasksJob.as_view(), name='tasks_scheduled'),  # Fixed: was SchdTasks
    path('tasks/<str:pk>/', scheduler_views.GetTaskFormJobneed.as_view(), name='task_detail'),
    path('tasks/<str:pk>/update/', scheduler_views.UpdateSchdTaskJob.as_view(), name='task_update'),
    
    # ========== TOURS ==========
    path('tours/', scheduler_views.JobneedTours.as_view(), name='tours_list'),
    path('tours/', scheduler_views.JobneedTours.as_view(), name='jobneedtours'),  # Legacy alias
    path('tours/internal/', scheduler_views.Retrive_I_ToursJobneed.as_view(), name='tours_internal'),
    path('tours/external/', scheduler_views.JobneedExternalTours.as_view(), name='tours_external'),
    path('tours/external/', scheduler_views.JobneedExternalTours.as_view(), name='jobneedexternaltours'),  # Legacy alias
    path('tours/adhoc/', AdhocTours.as_view(), name='tours_adhoc'),
    path('tours/tracking/', scheduler_views.ExternalTourTracking.as_view(), name='tours_tracking'),
    path('tours/<str:pk>/', scheduler_views.Get_I_TourJobneed.as_view(), name='tour_detail'),
    path('tours/<str:pk>/update/', scheduler_views.Update_I_TourFormJob.as_view(), name='tour_update'),
    
    # Tour Scheduling
    path('tours/schedule/', scheduler_views.Schd_I_TourFormJob.as_view(), name='tours_schedule'),
    path('tours/external/schedule/', scheduler_views.Schd_E_TourFormJob.as_view(), name='tours_external_schedule'),
    
    # ========== SCHEDULES ==========
    path('schedules/', scheduler_views.CalendarView.as_view() if hasattr(scheduler_views, 'CalendarView') else scheduler_views.JobneedTours.as_view(), name='schedules_calendar'),
    path('schedules/tours/internal/', scheduler_views.Schd_I_TourFormJob.as_view(), name='schedules_tours_internal'),
    path('schedules/tours/external/', scheduler_views.Schd_E_TourFormJob.as_view(), name='schedules_tours_external'),
    path('schedules/tasks/', scheduler_views.RetriveSchdTasksJob.as_view(), name='schedules_tasks'),
    
    # ========== WORK ORDERS ==========
    path('work-orders/', wom_views.WorkOrderView.as_view(), name='work_orders_list'),
    path('work-orders/', wom_views.WorkOrderView.as_view(), name='workorder'),  # Legacy alias
    path('work-orders/reply/', wom_views.ReplyWorkOrder.as_view(), name='work_order_reply'),
    
    # ========== WORK PERMITS ==========
    path('work-permits/', wom_views.WorkPermit.as_view(), name='work_permits_list'),
    path('work-permits/', wom_views.WorkPermit.as_view(), name='work_permit'),  # Legacy alias
    path('work-permits/reply/', wom_views.ReplyWorkPermit.as_view(), name='work_permit_reply'),
    path('work-permits/verifier-reply/', wom_views.VerifierReplyWorkPermit.as_view(), name='work_permit_verifier_reply'),
    
    # ========== SLA MANAGEMENT ==========
    path('sla/', wom_views.SLA_View.as_view(), name='sla_list'),
    path('sla/reply/', wom_views.ReplySla.as_view(), name='sla_reply'),
    
    # ========== VENDORS & APPROVERS ==========
    path('vendors/', wom_views.VendorView.as_view(), name='vendors_list'),
    path('approvers/', wom_views.ApproverView.as_view(), name='approvers_list'),
    
    # ========== PPM (Planned Preventive Maintenance) ==========
    path('ppm/', PPMView.as_view(), name='ppm_list'),
    path('ppm/jobs/', PPMJobneedView.as_view(), name='ppm_jobs'),
    path('ppm/jobs/', PPMJobneedView.as_view(), name='ppmjobneed'),  # Legacy alias for activity:ppmjobneed
    path('ppm/create/', PPMView.as_view(), name='ppm_create'),
    path('ppm/<int:pk>/', PPMView.as_view(), name='ppm_detail'),
]