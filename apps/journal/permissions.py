"""
Journal & Wellness Permissions System

Integrates with existing IntelliWiz permission system to provide:
- Granular permissions for journal and wellness functionality
- Role-based access control (RBAC) integration
- Privacy-aware permission enforcement
- Multi-tenant permission isolation
- Dynamic permission assignment based on user roles
"""

from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
import logging

from apps.journal.models import JournalEntry, JournalPrivacySettings

User = get_user_model()
logger = logging.getLogger(__name__)


class JournalWellnessPermissions:
    """
    Comprehensive permission system for journal and wellness functionality

    Permission Categories:
    - Journal Entry Permissions (create, read, update, delete, share)
    - Wellness Content Permissions (view, manage, create, approve)
    - Analytics Permissions (view_own, view_team, view_aggregate)
    - Administrative Permissions (manage_privacy, export_data, content_curation)
    """

    # Journal Entry Permissions
    JOURNAL_PERMISSIONS = [
        ('add_journalentry', 'Can create journal entries'),
        ('change_journalentry', 'Can edit own journal entries'),
        ('delete_journalentry', 'Can delete own journal entries'),
        ('view_journalentry', 'Can view own journal entries'),
        ('share_journalentry', 'Can share journal entries with others'),
        ('view_others_journalentry', 'Can view others\' journal entries (manager/admin)'),
        ('export_journalentry', 'Can export journal data'),
    ]

    # Wellness Content Permissions
    WELLNESS_PERMISSIONS = [
        ('view_wellnesscontent', 'Can view wellness education content'),
        ('add_wellnesscontent', 'Can create wellness content'),
        ('change_wellnesscontent', 'Can edit wellness content'),
        ('delete_wellnesscontent', 'Can delete wellness content'),
        ('approve_wellnesscontent', 'Can approve wellness content for publication'),
        ('manage_wellness_categories', 'Can manage wellness content categories'),
        ('view_content_analytics', 'Can view wellness content effectiveness analytics'),
    ]

    # Analytics Permissions
    ANALYTICS_PERMISSIONS = [
        ('view_own_analytics', 'Can view own wellbeing analytics'),
        ('view_team_analytics', 'Can view team wellbeing analytics (aggregated)'),
        ('view_organizational_analytics', 'Can view organizational wellness analytics'),
        ('export_analytics', 'Can export analytics data'),
        ('generate_wellness_reports', 'Can generate wellness reports'),
    ]

    # Privacy & Administrative Permissions
    PRIVACY_PERMISSIONS = [
        ('manage_privacy_settings', 'Can manage privacy settings'),
        ('view_privacy_reports', 'Can view privacy compliance reports'),
        ('handle_consent_requests', 'Can handle user consent requests'),
        ('process_data_requests', 'Can process GDPR data requests'),
        ('manage_data_retention', 'Can manage data retention policies'),
    ]

    # Crisis Intervention Permissions
    CRISIS_PERMISSIONS = [
        ('view_crisis_alerts', 'Can view crisis intervention alerts'),
        ('respond_to_crisis', 'Can respond to crisis situations'),
        ('manage_crisis_protocols', 'Can manage crisis intervention protocols'),
        ('access_crisis_reports', 'Can access crisis intervention reports'),
    ]

    @classmethod
    def create_all_permissions(cls):
        """Create all journal and wellness permissions"""
        logger.info("Creating journal and wellness permissions")

        created_permissions = []

        # Get content types
        journal_ct = ContentType.objects.get_for_model(JournalEntry)
        wellness_ct = ContentType.objects.get_for_model(WellnessContent)

        # Create permissions for each category
        permission_sets = [
            (cls.JOURNAL_PERMISSIONS, journal_ct),
            (cls.WELLNESS_PERMISSIONS, wellness_ct),
            (cls.ANALYTICS_PERMISSIONS, journal_ct),  # Analytics tied to journal entries
            (cls.PRIVACY_PERMISSIONS, journal_ct),
            (cls.CRISIS_PERMISSIONS, journal_ct),
        ]

        for permissions, content_type in permission_sets:
            for codename, name in permissions:
                permission, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )

                if created:
                    created_permissions.append(permission)
                    logger.info(f"Created permission: {codename}")

        return created_permissions

    @classmethod
    def create_permission_groups(cls):
        """Create permission groups for different user roles"""
        logger.info("Creating journal and wellness permission groups")

        groups_config = {
            'Journal Users': {
                'description': 'Standard journal users with basic functionality',
                'permissions': [
                    'add_journalentry', 'change_journalentry', 'delete_journalentry',
                    'view_journalentry', 'view_wellnesscontent', 'view_own_analytics',
                    'manage_privacy_settings'
                ]
            },
            'Wellness Content Viewers': {
                'description': 'Users who can access wellness education content',
                'permissions': [
                    'view_wellnesscontent', 'view_own_analytics'
                ]
            },
            'Team Managers': {
                'description': 'Managers who can view team wellness analytics',
                'permissions': [
                    'view_journalentry', 'view_wellnesscontent', 'view_own_analytics',
                    'view_team_analytics', 'view_others_journalentry',
                    'generate_wellness_reports'
                ]
            },
            'Wellness Content Managers': {
                'description': 'Users who can manage wellness education content',
                'permissions': [
                    'view_wellnesscontent', 'add_wellnesscontent', 'change_wellnesscontent',
                    'approve_wellnesscontent', 'manage_wellness_categories',
                    'view_content_analytics'
                ]
            },
            'HR Wellness Administrators': {
                'description': 'HR personnel with full wellness system access',
                'permissions': [
                    'view_wellnesscontent', 'add_wellnesscontent', 'change_wellnesscontent',
                    'approve_wellnesscontent', 'view_team_analytics',
                    'view_organizational_analytics', 'generate_wellness_reports',
                    'view_privacy_reports', 'handle_consent_requests',
                    'process_data_requests'
                ]
            },
            'Crisis Response Team': {
                'description': 'Personnel authorized for crisis intervention',
                'permissions': [
                    'view_crisis_alerts', 'respond_to_crisis', 'access_crisis_reports',
                    'view_team_analytics'
                ]
            },
            'Privacy Officers': {
                'description': 'Personnel responsible for privacy compliance',
                'permissions': [
                    'view_privacy_reports', 'handle_consent_requests',
                    'process_data_requests', 'manage_data_retention',
                    'view_organizational_analytics'
                ]
            },
            'System Administrators': {
                'description': 'Full system access for technical administration',
                'permissions': [
                    # All permissions
                    'add_journalentry', 'change_journalentry', 'delete_journalentry',
                    'view_journalentry', 'share_journalentry', 'view_others_journalentry',
                    'export_journalentry', 'view_wellnesscontent', 'add_wellnesscontent',
                    'change_wellnesscontent', 'delete_wellnesscontent',
                    'approve_wellnesscontent', 'manage_wellness_categories',
                    'view_content_analytics', 'view_own_analytics', 'view_team_analytics',
                    'view_organizational_analytics', 'export_analytics',
                    'generate_wellness_reports', 'manage_privacy_settings',
                    'view_privacy_reports', 'handle_consent_requests',
                    'process_data_requests', 'manage_data_retention',
                    'view_crisis_alerts', 'respond_to_crisis',
                    'manage_crisis_protocols', 'access_crisis_reports'
                ]
            }
        }

        created_groups = []

        for group_name, config in groups_config.items():
            # Create or get group
            group, created = Group.objects.get_or_create(
                name=group_name,
                defaults={'name': group_name}
            )

            if created:
                created_groups.append(group)
                logger.info(f"Created permission group: {group_name}")

            # Add permissions to group
            permission_codenames = config['permissions']
            permissions = Permission.objects.filter(codename__in=permission_codenames)

            group.permissions.set(permissions)
            logger.info(f"Assigned {permissions.count()} permissions to group {group_name}")

        return created_groups

    @classmethod
    def assign_user_to_groups(cls, user, role_names):
        """Assign user to permission groups based on their roles"""
        try:
            # Remove user from all journal/wellness groups first
            journal_wellness_groups = Group.objects.filter(
                name__in=[
                    'Journal Users', 'Wellness Content Viewers', 'Team Managers',
                    'Wellness Content Managers', 'HR Wellness Administrators',
                    'Crisis Response Team', 'Privacy Officers', 'System Administrators'
                ]
            )

            user.groups.remove(*journal_wellness_groups)

            # Add user to specified groups
            for role_name in role_names:
                try:
                    group = Group.objects.get(name=role_name)
                    user.groups.add(group)
                    logger.info(f"Added user {user.id} to group {role_name}")
                except Group.DoesNotExist:
                    logger.warning(f"Permission group {role_name} not found")

            return True

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to assign user {user.id} to groups {role_names}: {e}")
            return False


class JournalPermissionChecker:
    """
    Runtime permission checker for journal and wellness operations

    Features:
    - Dynamic permission checking with context awareness
    - Privacy scope integration
    - Multi-tenant permission isolation
    - Operation-specific permission validation
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def check_journal_entry_permission(self, user, journal_entry, operation):
        """
        Check permission for journal entry operations

        Args:
            user: User requesting access
            journal_entry: JournalEntry object
            operation: Operation type ('create', 'read', 'update', 'delete', 'share')

        Returns:
            dict: Permission check result
        """

        self.logger.debug(f"Checking {operation} permission for user {user.id} on entry {journal_entry.id}")

        try:
            # Owner always has full permissions to their own entries
            if journal_entry.user == user:
                return {
                    'allowed': True,
                    'reason': 'owner_access',
                    'permission_source': 'ownership'
                }

            # Check Django permissions
            permission_map = {
                'create': 'journal.add_journalentry',
                'read': 'journal.view_journalentry',
                'update': 'journal.change_journalentry',
                'delete': 'journal.delete_journalentry',
                'share': 'journal.share_journalentry'
            }

            required_permission = permission_map.get(operation)
            if required_permission and not user.has_perm(required_permission):
                return {
                    'allowed': False,
                    'reason': f'missing_permission_{required_permission}',
                    'required_permission': required_permission
                }

            # Check privacy scope permissions
            privacy_result = self._check_privacy_scope_permission(user, journal_entry, operation)
            if not privacy_result['allowed']:
                return privacy_result

            # Check tenant isolation
            if journal_entry.tenant != user.tenant:
                return {
                    'allowed': False,
                    'reason': 'cross_tenant_access_denied',
                    'user_tenant': user.tenant.tenantname if user.tenant else None,
                    'entry_tenant': journal_entry.tenant.tenantname if journal_entry.tenant else None
                }

            # All checks passed
            return {
                'allowed': True,
                'reason': 'permission_granted',
                'permission_source': 'role_based',
                'privacy_scope': journal_entry.privacy_scope
            }

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Permission check failed for user {user.id}: {e}")
            return {
                'allowed': False,
                'reason': 'permission_check_error',
                'error': str(e)
            }

    def check_wellness_content_permission(self, user, wellness_content, operation):
        """Check permission for wellness content operations"""

        permission_map = {
            'view': 'wellness.view_wellnesscontent',
            'create': 'wellness.add_wellnesscontent',
            'update': 'wellness.change_wellnesscontent',
            'delete': 'wellness.delete_wellnesscontent',
            'approve': 'wellness.approve_wellnesscontent'
        }

        required_permission = permission_map.get(operation)

        if required_permission and not user.has_perm(required_permission):
            return {
                'allowed': False,
                'reason': f'missing_permission_{required_permission}',
                'required_permission': required_permission
            }

        # Check tenant isolation for content management
        if operation in ['create', 'update', 'delete'] and wellness_content.tenant != user.tenant:
            return {
                'allowed': False,
                'reason': 'cross_tenant_content_access_denied'
            }

        return {
            'allowed': True,
            'reason': 'permission_granted'
        }

    def check_analytics_permission(self, user, target_user=None, analytics_type='own'):
        """Check permission for analytics operations"""

        permission_map = {
            'own': 'journal.view_own_analytics',
            'team': 'journal.view_team_analytics',
            'organizational': 'journal.view_organizational_analytics'
        }

        required_permission = permission_map.get(analytics_type)

        if required_permission and not user.has_perm(required_permission):
            return {
                'allowed': False,
                'reason': f'missing_permission_{required_permission}',
                'required_permission': required_permission
            }

        # For own analytics, user must be viewing their own data
        if analytics_type == 'own' and target_user and target_user != user:
            return {
                'allowed': False,
                'reason': 'cannot_view_others_personal_analytics'
            }

        # For team analytics, check if user can view target user's data
        if analytics_type == 'team' and target_user:
            team_access_result = self._check_team_analytics_access(user, target_user)
            if not team_access_result['allowed']:
                return team_access_result

        return {
            'allowed': True,
            'reason': 'analytics_permission_granted',
            'analytics_type': analytics_type
        }

    def check_crisis_intervention_permission(self, user, target_user=None):
        """Check permission for crisis intervention operations"""

        if not user.has_perm('journal.view_crisis_alerts'):
            return {
                'allowed': False,
                'reason': 'missing_crisis_intervention_permission',
                'required_permission': 'journal.view_crisis_alerts'
            }

        # Check if target user has given crisis intervention consent
        if target_user:
            try:
                privacy_settings = target_user.journal_privacy_settings
                if not privacy_settings.crisis_intervention_consent:
                    return {
                        'allowed': False,
                        'reason': 'target_user_no_crisis_consent',
                        'target_user': target_user.id
                    }
            except JournalPrivacySettings.DoesNotExist:
                return {
                    'allowed': False,
                    'reason': 'target_user_no_privacy_settings'
                }

        return {
            'allowed': True,
            'reason': 'crisis_intervention_authorized'
        }

    def _check_privacy_scope_permission(self, user, journal_entry, operation):
        """Check permission based on entry's privacy scope"""

        privacy_scope = journal_entry.privacy_scope

        # Private entries - only owner or specific shared users
        if privacy_scope == 'private':
            if user != journal_entry.user:
                return {
                    'allowed': False,
                    'reason': 'private_entry_access_denied',
                    'privacy_scope': 'private'
                }

        # Shared entries - check sharing permissions
        elif privacy_scope == 'shared':
            if user != journal_entry.user and str(user.id) not in journal_entry.sharing_permissions:
                return {
                    'allowed': False,
                    'reason': 'not_in_sharing_permissions',
                    'privacy_scope': 'shared'
                }

        # Manager entries - check manager relationship
        elif privacy_scope == 'manager':
            if user != journal_entry.user and not self._is_manager_of(user, journal_entry.user):
                return {
                    'allowed': False,
                    'reason': 'not_manager_of_user',
                    'privacy_scope': 'manager'
                }

        # Team entries - check team membership
        elif privacy_scope == 'team':
            if user != journal_entry.user and not self._is_team_member_of(user, journal_entry.user):
                return {
                    'allowed': False,
                    'reason': 'not_team_member',
                    'privacy_scope': 'team'
                }

        # Aggregate only - only for analytics operations
        elif privacy_scope == 'aggregate_only':
            if operation not in ['aggregate', 'analytics']:
                return {
                    'allowed': False,
                    'reason': 'aggregate_only_entry',
                    'privacy_scope': 'aggregate_only'
                }

        return {
            'allowed': True,
            'privacy_scope': privacy_scope
        }

    def _check_team_analytics_access(self, user, target_user):
        """Check if user can access team analytics for target user"""
        # Manager can view their team's analytics
        if self._is_manager_of(user, target_user):
            return {
                'allowed': True,
                'reason': 'manager_team_access'
            }

        # Team lead can view team analytics
        if self._is_team_lead_of(user, target_user):
            return {
                'allowed': True,
                'reason': 'team_lead_access'
            }

        # HR can view organizational analytics
        if user.has_perm('journal.view_organizational_analytics'):
            return {
                'allowed': True,
                'reason': 'hr_organizational_access'
            }

        return {
            'allowed': False,
            'reason': 'no_team_analytics_relationship'
        }

    def _is_manager_of(self, manager, employee):
        """Check if user is manager of another user"""
        # TODO: Integrate with existing IntelliWiz organizational structure
        # This would check against your existing People/Department relationships

        # Placeholder implementation
        try:
            # Example: Check if manager's department matches employee's department
            # and manager has appropriate role

            if (hasattr(manager, 'department') and hasattr(employee, 'department') and
                manager.department == employee.department and
                getattr(manager, 'isadmin', False)):
                return True

            # Check explicit manager relationships if you have them
            # if hasattr(employee, 'manager') and employee.manager == manager:
            #     return True

            return False

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Error checking manager relationship: {e}")
            return False

    def _is_team_member_of(self, user1, user2):
        """Check if users are on the same team"""
        # TODO: Integrate with existing team structure
        try:
            # Example: Check if users are in same department/team
            if (hasattr(user1, 'department') and hasattr(user2, 'department') and
                user1.department == user2.department):
                return True

            return False

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Error checking team membership: {e}")
            return False

    def _is_team_lead_of(self, lead, member):
        """Check if user is team lead of another user"""
        # TODO: Implement based on your team lead structure
        return False  # Placeholder


class PermissionDecorator:
    """Decorator class for permission-protected views"""

    @staticmethod
    def require_journal_permission(permission_type):
        """Decorator to require specific journal permission"""
        def decorator(view_func):
            def wrapper(request, *args, **kwargs):
                if not request.user.is_authenticated:
                    raise PermissionDenied("Authentication required")

                # Check specific permission
                checker = JournalPermissionChecker()

                if permission_type == 'view_analytics':
                    result = checker.check_analytics_permission(request.user)
                elif permission_type == 'crisis_intervention':
                    result = checker.check_crisis_intervention_permission(request.user)
                else:
                    # General permission check
                    if not request.user.has_perm(f'journal.{permission_type}'):
                        raise PermissionDenied(f"Missing required permission: {permission_type}")
                    result = {'allowed': True}

                if not result['allowed']:
                    raise PermissionDenied(result.get('reason', 'Permission denied'))

                return view_func(request, *args, **kwargs)

            return wrapper
        return decorator

    @staticmethod
    def require_wellness_permission(permission_type):
        """Decorator to require specific wellness permission"""
        def decorator(view_func):
            def wrapper(request, *args, **kwargs):
                if not request.user.is_authenticated:
                    raise PermissionDenied("Authentication required")

                if not request.user.has_perm(f'wellness.{permission_type}'):
                    raise PermissionDenied(f"Missing required permission: {permission_type}")

                return view_func(request, *args, **kwargs)

            return wrapper
        return decorator


# Permission checking middleware
class JournalPrivacyPermissionMiddleware:
    """Middleware to enforce journal privacy permissions on all requests"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def __call__(self, request):
        """Process request with permission checking"""
        # Only apply to journal/wellness API endpoints
        if request.path.startswith('/api/v1/journal/') or request.path.startswith('/api/v1/wellness/'):
            self._check_api_permissions(request)

        response = self.get_response(request)
        return response

    def _check_api_permissions(self, request):
        """Check API permissions for journal/wellness endpoints"""
        try:
            if not request.user.is_authenticated:
                return  # Authentication middleware will handle this

            # Log API access for audit trail
            self.logger.debug(f"Journal/Wellness API access: {request.user.id} -> {request.path}")

            # Check rate limiting for sensitive operations
            if self._is_sensitive_operation(request):
                self._check_rate_limits(request)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Permission middleware error: {e}")

    def _is_sensitive_operation(self, request):
        """Check if operation is sensitive and requires rate limiting"""
        sensitive_paths = [
            '/api/v1/journal/analytics/',
            '/api/v1/journal/search/',
            '/api/v1/wellness/personalized/',
            '/api/v1/journal/sync/'
        ]

        return any(request.path.startswith(path) for path in sensitive_paths)

    def _check_rate_limits(self, request):
        """Check rate limits for sensitive operations"""
        # TODO: Implement rate limiting logic
        # This could integrate with existing rate limiting infrastructure
        pass


# Convenience functions for permission checking

def check_journal_permission(user, journal_entry, operation):
    """Convenience function to check journal permissions"""
    checker = JournalPermissionChecker()
    return checker.check_journal_entry_permission(user, journal_entry, operation)


def check_wellness_permission(user, wellness_content, operation):
    """Convenience function to check wellness permissions"""
    checker = JournalPermissionChecker()
    return checker.check_wellness_content_permission(user, wellness_content, operation)


def check_analytics_permission(user, analytics_type='own', target_user=None):
    """Convenience function to check analytics permissions"""
    checker = JournalPermissionChecker()
    return checker.check_analytics_permission(user, target_user, analytics_type)


def setup_permissions_for_tenant(tenant):
    """Setup default permissions for a new tenant"""
    try:
        # Create all permissions
        JournalWellnessPermissions.create_all_permissions()

        # Create permission groups
        JournalWellnessPermissions.create_permission_groups()

        # Assign default permissions to existing users in tenant
        tenant_users = User.objects.filter(tenant=tenant)

        for user in tenant_users:
            # Default role assignment based on user properties
            default_roles = ['Journal Users', 'Wellness Content Viewers']

            if getattr(user, 'isadmin', False):
                default_roles.append('System Administrators')
            elif getattr(user, 'is_staff', False):
                default_roles.append('Team Managers')

            JournalWellnessPermissions.assign_user_to_groups(user, default_roles)

        logger.info(f"Setup permissions for tenant {tenant.tenantname}: {tenant_users.count()} users configured")

        return True

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to setup permissions for tenant {tenant.id}: {e}")
        return False


def assign_user_journal_permissions(user, roles):
    """Assign journal and wellness permissions to user based on roles"""
    return JournalWellnessPermissions.assign_user_to_groups(user, roles)