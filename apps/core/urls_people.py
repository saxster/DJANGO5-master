"""
Consolidated URL configuration for People domain
Combines: peoples, attendance, and people-related activity functionality
"""
from django.urls import path
from django.views.generic import RedirectView
from apps.peoples import views as people_views
from apps.attendance import views as attendance_views

# Import mobile views if available
try:
    from apps.activity.views.deviceevent_log_views import MobileUserLog, MobileUserDetails
except ImportError:
    # Create placeholder views if not available
    from django.views.generic import TemplateView
    class MobileUserLog(TemplateView):
        template_name = 'core/placeholder.html'
    class MobileUserDetails(TemplateView):
        template_name = 'core/placeholder.html'

# Skip employee_creation views for now to avoid app dependency issues
employee_views = None

app_name = 'people'

urlpatterns = [
    # ========== PEOPLE DIRECTORY ==========
    path('', people_views.PeopleView.as_view(), name='people_list'),
    path('create/', people_views.PeopleView.as_view(), name='people_create'),
    path('<int:pk>/', people_views.PeopleView.as_view(), name='people_detail'),
    path('<int:pk>/edit/', people_views.PeopleView.as_view(), name='people_edit'),
    path('<int:pk>/change-password/', people_views.ChangePeoplePassword.as_view(), name='people_change_password'),
    
    # Unassigned People
    path('unassigned/', people_views.NoSite.as_view(), name='people_unassigned'),
    
    # ========== CAPABILITIES ==========
    path('capabilities/', people_views.Capability.as_view(), name='capabilities_list'),
    path('capabilities/create/', people_views.Capability.as_view(), name='capability_create'),
    path('capabilities/<int:pk>/', people_views.Capability.as_view(), name='capability_detail'),
    
    # ========== GROUPS & TEAMS ==========
    path('groups/', people_views.PeopleGroup.as_view(), name='groups_list'),
    path('groups/create/', people_views.PeopleGroup.as_view(), name='group_create'),
    path('groups/<int:pk>/', people_views.PeopleGroup.as_view(), name='group_detail'),
    
    # Site Groups
    path('site-groups/', people_views.SiteGroup.as_view(), name='site_groups_list'),
    path('site-groups/create/', people_views.SiteGroup.as_view(), name='site_group_create'),
    path('site-groups/<int:pk>/', people_views.SiteGroup.as_view(), name='site_group_detail'),
    
    # ========== ATTENDANCE ==========
    path('attendance/', attendance_views.Attendance.as_view(), name='attendance'),
    path('attendance/', attendance_views.Attendance.as_view(), name='attendance_view'),  # Legacy alias
    
    # ========== TRACKING & LOCATION ==========
    path('tracking/', attendance_views.GeofenceTracking.as_view(), name='tracking'),
    
    # ========== EXPENSES ==========
    path('expenses/conveyance/', attendance_views.Conveyance.as_view(), name='expenses_conveyance'),
    
    # ========== MOBILE TRACKING ==========
    path('mobile/logs/', MobileUserLog.as_view(), name='mobile_logs'),
    path('mobile/details/', MobileUserDetails.as_view(), name='mobile_details'),
    path('mobile/details/<int:user_id>/', MobileUserDetails.as_view(), name='mobile_user_details'),
    
    # ========== EMPLOYEES ==========
    path('employees/', people_views.PeopleView.as_view(), name='employees_list'),
    
    # ========== EMAIL VERIFICATION (redirect to peoples app location) ==========
    path('verify-email/', RedirectView.as_view(url='/peoples/verifyemail', permanent=False, query_string=True), name='verify_email_redirect'),
]