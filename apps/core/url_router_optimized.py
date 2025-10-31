"""
Optimized URL Router for Information Architecture
Implements domain-driven URL structure with comprehensive legacy support
"""
from typing import List, Dict, Any
from django.views.generic import RedirectView
from django.conf import settings
from django.core.cache import cache
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OptimizedURLRouter:
    """Enhanced URL routing with domain-based organization"""
    
    # Complete mapping of ALL old URLs to new optimized structure
    URL_MAPPINGS = {
        # ========== OPERATIONS DOMAIN ==========
        # Task Management
        'scheduler/jobneedtasks/': 'operations/tasks/',
        'scheduler/schedhule_task/': 'operations/tasks/schedule/',
        'scheduler/tasklist_jobneed/': 'operations/tasks/list/',
        'scheduler/jobschdtasks/': 'operations/tasks/scheduled/',
        'scheduler/task_jobneed/<str:pk>/': 'operations/tasks/<str:pk>/',
        'activity/adhoctasks/': 'operations/tasks/adhoc/',
        
        # Tour Management
        'scheduler/jobneedtours/': 'operations/tours/',
        'scheduler/jobneedexternaltours/': 'operations/tours/external/',
        'scheduler/internal-tours/': 'operations/tours/internal/',
        'scheduler/schd_internal_tour/': 'operations/schedules/tours/internal/',
        'scheduler/schd_external_tour/': 'operations/schedules/tours/external/',
        'scheduler/schedhule_tour/': 'operations/tours/schedule/',
        'scheduler/external_schedhule_tour/': 'operations/tours/external/schedule/',
        'scheduler/site_tour_tracking/': 'operations/tours/tracking/',
        'activity/adhoctours/': 'operations/tours/adhoc/',
        
        # Work Order Management
        'work_order_management/work_order/': 'operations/work-orders/',
        'work_order_management/workorder/': 'operations/work-orders/',
        'work_order_management/work_permit/': 'operations/work-permits/',
        'work_order_management/workpermit/': 'operations/work-permits/',
        'work_order_management/sla/': 'operations/sla/',
        'work_order_management/vendor/': 'operations/vendors/',
        'work_order_management/approver/': 'operations/approvers/',
        
        # PPM Management
        'activity/ppm/': 'operations/ppm/',
        'activity/ppm_jobneed/': 'operations/ppm/jobs/',
        
        # ========== ASSETS DOMAIN ==========
        # Asset Core
        'activity/asset/': 'assets/',
        'activity/assetmaintainance/': 'assets/maintenance/',
        'activity/assetmaintenance/': 'assets/maintenance/',
        
        # Asset Monitoring & Comparison
        'activity/comparision/': 'assets/compare/',
        'activity/param_comparision/': 'assets/compare/parameters/',
        'activity/assetlog/': 'assets/logs/',
        'activity/assetlogs/': 'assets/logs/',
        
        # Locations & Checkpoints
        'activity/location/': 'assets/locations/',
        'activity/checkpoint/': 'assets/checkpoints/',
        'activity/peoplenearassets/': 'assets/people-nearby/',
        
        # Questions & Checklists
        'activity/question/': 'assets/checklists/questions/',
        'activity/questionset/': 'assets/checklists/',
        'activity/qsetnQsetblng/': 'assets/checklists/relationships/',
        
        # ========== PEOPLE DOMAIN ==========
        # Core People Management
        'peoples/people/': 'people/',
        'peoples/peole_form/': 'people/form/',
        'peoples/capability/': 'people/capabilities/',
        'peoples/no-site/': 'people/unassigned/',
        
        # Groups & Teams
        'peoples/peoplegroup/': 'people/groups/',
        'peoples/sitegroup/': 'people/site-groups/',
        
        # Attendance & Tracking
        'attendance/attendance_view/': 'people/attendance/',
        'attendance/geofencetracking/': 'people/tracking/',
        'attendance/sos_list/': 'people/sos/',
        'attendance/site_diversions/': 'people/diversions/',
        'attendance/sitecrisis_list/': 'people/crisis/',
        
        # Expenses
        'attendance/conveyance/': 'people/expenses/conveyance/',
        'attendance/travel_expense/': 'people/expenses/travel/',
        
        # Mobile & Logs
        'activity/mobileuserlogs/': 'people/mobile/logs/',
        'activity/mobileuserdetails/': 'people/mobile/details/',
        
        # Employee Creation
        'employee_creation/employee/': 'people/employees/',
        
        # ========== HELP DESK DOMAIN ==========
        'helpdesk/ticket/': 'help-desk/tickets/',
        'y_helpdesk/ticket/': 'help-desk/tickets/',
        'helpdesk/escalationmatrix/': 'help-desk/escalations/',
        'y_helpdesk/escalation/': 'help-desk/escalations/',
        'helpdesk/postingorder/': 'help-desk/posting-orders/',
        'y_helpdesk/posting_order/': 'help-desk/posting-orders/',
        'helpdesk/uniform/': 'help-desk/uniforms/',
        'y_helpdesk/uniform/': 'help-desk/uniforms/',
        
        # ========== REPORTS DOMAIN ==========
        'reports/get_reports/': 'reports/download/',
        'reports/exportreports/': 'reports/download/',
        'reports/schedule-email-report/': 'reports/schedule/',
        'reports/schedule_email_report/': 'reports/schedule/',
        'reports/sitereport_list/': 'reports/site-reports/',
        'reports/incidentreport_list/': 'reports/incident-reports/',
        'reports/sitereport_template/': 'reports/templates/site/',
        'reports/incidentreport_template/': 'reports/templates/incident/',
        'reports/workpermitreport_template/': 'reports/templates/work-permit/',
        'reports/generatepdf/': 'reports/generate/pdf/',
        'reports/generateletter/': 'reports/generate/letter/',
        'reports/design/': 'reports/designer/',
        
        # ========== ADMIN DOMAIN ==========
        # Business Units & Organization
        'onboarding/bu/': 'admin/business-units/',
        'onboarding/client/': 'admin/clients/',
        'clientbilling/features/': 'admin/clients/features/',
        'onboarding/contract/': 'admin/contracts/',
        
        # Configuration
        'onboarding/typeassist/': 'admin/config/types/',
        'onboarding/shift/': 'admin/config/shifts/',
        'onboarding/geofence/': 'admin/config/geofences/',
        
        # Data Management
        'onboarding/import/': 'admin/data/import/',
        'onboarding/import_update/': 'admin/data/bulk-update/',
        'onboarding/import_image_data/': 'admin/data/import-images/',
        
        # ========== API ENDPOINTS ==========
        'api/': 'api/v1/',
        'service/': 'api/v1/service/',
        
        # ========== MONITORING ==========
        'monitoring/health/': 'monitoring/health/',
        'monitoring/metrics/': 'monitoring/metrics/',
        'monitoring/performance/': 'monitoring/performance/',
        
        # ========== AUTHENTICATION ==========
        'login/': 'auth/login/',
        'logout/': 'auth/logout/',
        # 'peoples/verifyemail/': 'auth/verify-email/',  # Commented out to prevent redirect loop
        'email/': 'auth/email/',
        
        # ========== DEAD/DEPRECATED URLS ==========
        # These redirect to appropriate new locations
        'apps/customers/getting-started.html': 'dashboard/',
        'apps/customers/list.html': 'people/',
        'apps/customers/view.html': 'people/',
        'scheduler/retrieve_tickets/': 'help-desk/tickets/',
        'reminder/': 'dashboard/',  # Reminder app was removed
    }
    
    # Navigation menu structure for new IA
    NAVIGATION_STRUCTURE = {
        'main': [
            {
                'name': 'Dashboard',
                'url': '/dashboard/',
                'icon': 'dashboard',
                'capability': 'view_dashboard'
            },
            {
                'name': 'Operations',
                'url': '/operations/',
                'icon': 'settings',
                'capability': 'view_operations',
                'children': [
                    {'name': 'Tasks', 'url': '/operations/tasks/'},
                    {'name': 'Tours', 'url': '/operations/tours/'},
                    {'name': 'Work Orders', 'url': '/operations/work-orders/'},
                    {'name': 'Schedules', 'url': '/operations/schedules/'},
                    {'name': 'PPM', 'url': '/operations/ppm/'},
                ]
            },
            {
                'name': 'Assets',
                'url': '/assets/',
                'icon': 'business',
                'capability': 'view_assets',
                'children': [
                    {'name': 'Inventory', 'url': '/assets/'},
                    {'name': 'Maintenance', 'url': '/assets/maintenance/'},
                    {'name': 'Locations', 'url': '/assets/locations/'},
                    {'name': 'Monitoring', 'url': '/assets/logs/'},
                    {'name': 'Checklists', 'url': '/assets/checklists/'},
                ]
            },
            {
                'name': 'People',
                'url': '/people/',
                'icon': 'people',
                'capability': 'view_people',
                'children': [
                    {'name': 'Directory', 'url': '/people/'},
                    {'name': 'Attendance', 'url': '/people/attendance/'},
                    {'name': 'Groups', 'url': '/people/groups/'},
                    {'name': 'Expenses', 'url': '/people/expenses/'},
                    {'name': 'Tracking', 'url': '/people/tracking/'},
                ]
            },
            {
                'name': 'Help Desk',
                'url': '/help-desk/',
                'icon': 'help',
                'capability': 'view_helpdesk',
                'children': [
                    {'name': 'Tickets', 'url': '/help-desk/tickets/'},
                    {'name': 'Escalations', 'url': '/help-desk/escalations/'},
                    {'name': 'Requests', 'url': '/help-desk/posting-orders/'},
                ]
            },
            {
                'name': 'Reports',
                'url': '/reports/',
                'icon': 'assessment',
                'capability': 'view_reports',
                'children': [
                    {'name': 'Site Reports', 'url': '/reports/site-reports/'},
                    {'name': 'Incident Reports', 'url': '/reports/incident-reports/'},
                    {'name': 'Download', 'url': '/reports/download/'},
                    {'name': 'Schedule', 'url': '/reports/schedule/'},
                ]
            },
        ],
        'admin': [
            {
                'name': 'Administration',
                'url': '/admin/',
                'icon': 'admin_panel_settings',
                'capability': 'view_admin',
                'children': [
                    {'name': 'Business Units', 'url': '/admin/business-units/'},
                    {'name': 'Clients', 'url': '/admin/clients/'},
                    {'name': 'Configuration', 'url': '/admin/config/'},
                    {'name': 'Data Import', 'url': '/admin/data/'},
                    {'name': 'Monitoring', 'url': '/monitoring/'},
                ]
            }
        ]
    }
    
    # Track URL usage for analytics
    URL_USAGE_ANALYTICS = {}
    
    @classmethod
    def get_optimized_patterns(cls):
        """Generate URL patterns for new optimized structure"""
        patterns = []
        
        # Add redirect patterns for all legacy URLs
        for old_url, new_url in cls.URL_MAPPINGS.items():
            redirect_view = cls._create_smart_redirect(old_url, new_url)
            # Handle dynamic URL parameters
            if '<' in old_url:
                # Extract parameter pattern
                pattern = old_url
            else:
                pattern = old_url
            # Clean the name to remove colons and angle brackets
            clean_name = old_url.replace("/", "_").replace(":", "_").replace("<", "").replace(">", "")
            patterns.append(
                path(pattern, redirect_view, name=f'legacy_{clean_name}')
            )
        
        return patterns
    
    @classmethod
    def _create_smart_redirect(cls, old_url: str, new_url: str):
        """Create an intelligent redirect that tracks usage and handles parameters"""
        
        class SmartRedirectView(RedirectView):
            permanent = True  # Use 301 permanent redirects after migration completion
            
            def get_redirect_url(self, *args, **kwargs):
                # Track usage
                cls._track_url_usage(old_url, new_url, self.request)
                
                # Handle dynamic parameters
                redirect_url = new_url
                for key, value in kwargs.items():
                    placeholder = f'<str:{key}>/'
                    if placeholder in new_url:
                        redirect_url = redirect_url.replace(placeholder, f'{value}/')
                
                # Preserve query parameters
                query_string = self.request.META.get('QUERY_STRING', '')
                if query_string:
                    redirect_url += f'?{query_string}'
                
                # Log redirect in development
                if settings.DEBUG:
                    username = 'anonymous'
                    if self.request.user.is_authenticated:
                        username = getattr(self.request.user, 'loginid', getattr(self.request.user, 'username', str(self.request.user.id)))
                    logger.info(f"URL Redirect: {old_url} -> {redirect_url} (User: {username})")
                
                return '/' + redirect_url
        
        return SmartRedirectView.as_view()
    
    @classmethod
    def _track_url_usage(cls, old_url: str, new_url: str, request):
        """Track URL usage for migration analytics"""
        # Initialize tracking
        if old_url not in cls.URL_USAGE_ANALYTICS:
            cls.URL_USAGE_ANALYTICS[old_url] = {
                'count': 0,
                'users': set(),
                'last_accessed': None,
                'new_url': new_url
            }
        
        # Update analytics
        cls.URL_USAGE_ANALYTICS[old_url]['count'] += 1
        cls.URL_USAGE_ANALYTICS[old_url]['last_accessed'] = datetime.now()
        
        if request.user.is_authenticated:
            # Use the correct username field for the People model
            username = getattr(request.user, 'loginid', getattr(request.user, 'username', str(request.user.id)))
            cls.URL_USAGE_ANALYTICS[old_url]['users'].add(username)
        
        # Cache analytics data
        cache.set('url_usage_analytics', cls.URL_USAGE_ANALYTICS, 3600)
    
    @classmethod
    def get_navigation_menu(cls, user=None, menu_type='main'):
        """Get navigation menu structure based on user permissions"""
        menu = cls.NAVIGATION_STRUCTURE.get(menu_type, [])
        
        if not user:
            return menu
        
        # Filter based on user capabilities
        filtered_menu = []
        for item in menu:
            # Check capability if specified
            if 'capability' in item:
                if not user.has_perm(item['capability']):
                    continue
            
            # Filter children
            if 'children' in item:
                filtered_children = []
                for child in item['children']:
                    if 'capability' in child:
                        if user.has_perm(child['capability']):
                            filtered_children.append(child)
                    else:
                        filtered_children.append(child)
                
                if filtered_children:
                    item = item.copy()
                    item['children'] = filtered_children
                    filtered_menu.append(item)
            else:
                filtered_menu.append(item)
        
        return filtered_menu
    
    @classmethod
    def get_breadcrumbs(cls, current_url: str) -> List[Dict[str, str]]:
        """Generate breadcrumb navigation for current URL"""
        breadcrumbs = [{'name': 'Home', 'url': '/'}]
        
        # Parse URL segments
        segments = current_url.strip('/').split('/')
        current_path = ''
        
        for segment in segments:
            current_path += f'/{segment}'
            
            # Map segment to readable name
            name = segment.replace('-', ' ').title()
            
            # Special mappings
            name_mappings = {
                'Ppm': 'PPM',
                'Sla': 'SLA',
                'Sos': 'SOS',
                'Help Desk': 'Help Desk',
                'Work Orders': 'Work Orders',
            }
            
            name = name_mappings.get(name, name)
            
            breadcrumbs.append({
                'name': name,
                'url': current_path + '/'
            })
        
        return breadcrumbs
    
    @classmethod
    def get_migration_report(cls) -> Dict:
        """Generate comprehensive migration report"""
        analytics = cache.get('url_usage_analytics', cls.URL_USAGE_ANALYTICS)
        
        # Calculate statistics
        total_legacy_urls = len(cls.URL_MAPPINGS)
        used_legacy_urls = len(analytics)
        unused_legacy_urls = total_legacy_urls - used_legacy_urls
        
        # Find most used legacy URLs
        top_legacy_urls = sorted(
            analytics.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:10]
        
        # Calculate adoption rate
        adoption_rate = (unused_legacy_urls / total_legacy_urls * 100) if total_legacy_urls > 0 else 100
        
        return {
            'summary': {
                'total_legacy_urls': total_legacy_urls,
                'used_legacy_urls': used_legacy_urls,
                'unused_legacy_urls': unused_legacy_urls,
                'adoption_rate': round(adoption_rate, 2),
                'total_redirects': sum(data['count'] for data in analytics.values()),
            },
            'top_legacy_urls': [
                {
                    'old_url': url,
                    'new_url': data['new_url'],
                    'usage_count': data['count'],
                    'unique_users': len(data['users']),
                    'last_accessed': data['last_accessed']
                }
                for url, data in top_legacy_urls
            ],
            'recommendations': cls._generate_recommendations(analytics),
            'timestamp': datetime.now()
        }
    
    @classmethod
    def _generate_recommendations(cls, analytics: Dict) -> List[str]:
        """Generate recommendations based on usage analytics"""
        recommendations = []
        
        # Check for high-usage legacy URLs
        high_usage = [url for url, data in analytics.items() if data['count'] > 100]
        if high_usage:
            recommendations.append(
                f"Update templates and bookmarks for {len(high_usage)} frequently accessed legacy URLs"
            )
        
        # Check for recently used legacy URLs
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_urls = [
            url for url, data in analytics.items() 
            if data['last_accessed'] and data['last_accessed'] > recent_cutoff
        ]
        if recent_urls:
            recommendations.append(
                f"Train users on new URLs - {len(recent_urls)} legacy URLs accessed in past week"
            )
        
        # Check adoption rate
        adoption_rate = cls.get_migration_report()['summary']['adoption_rate']
        if adoption_rate < 50:
            recommendations.append(
                "Low adoption rate - consider user training and documentation updates"
            )
        elif adoption_rate > 90:
            recommendations.append(
                "High adoption rate - consider making redirects permanent (301)"
            )
        
        return recommendations
    
    @classmethod
    def validate_url_structure(cls) -> Dict[str, List[str]]:
        """Validate the new URL structure for consistency"""
        issues = {
            'naming_inconsistencies': [],
            'deep_nesting': [],
            'missing_redirects': [],
            'duplicate_targets': {}
        }
        
        # Check for naming consistency
        for old_url, new_url in cls.URL_MAPPINGS.items():
            # Check for consistent hyphenation
            if '_' in new_url:
                issues['naming_inconsistencies'].append(
                    f"{new_url} contains underscores (should use hyphens)"
                )
            
            # Check for deep nesting (more than 3 levels)
            if new_url.count('/') > 3:
                issues['deep_nesting'].append(
                    f"{new_url} is deeply nested ({new_url.count('/')} levels)"
                )
        
        # Check for duplicate redirect targets
        target_counts = {}
        for old_url, new_url in cls.URL_MAPPINGS.items():
            if new_url not in target_counts:
                target_counts[new_url] = []
            target_counts[new_url].append(old_url)
        
        for new_url, old_urls in target_counts.items():
            if len(old_urls) > 1:
                issues['duplicate_targets'][new_url] = old_urls

        return issues


# Backward compatibility alias for legacy imports
URLRouter = OptimizedURLRouter
