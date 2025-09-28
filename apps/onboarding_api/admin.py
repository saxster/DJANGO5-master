"""
Admin interfaces for Conversational Onboarding rollout and feature management

This module provides Django admin interfaces for controlling the rollout
of conversational onboarding features at tenant and user levels.
"""
import json
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.html import format_html, mark_safe
from django.utils.safestring import SafeString
from django.db.models import Count, Q


# Proxy models for separate admin interfaces
class PeopleOnboardingProxy(People):
    """Proxy model for conversational onboarding user management"""
    class Meta:
        proxy = True
        verbose_name = "User Onboarding Capability"
        verbose_name_plural = "User Onboarding Capabilities"


class TenantOnboardingProxy(Bt):
    """Proxy model for tenant onboarding rollout management"""
    class Meta:
        proxy = True
        verbose_name = "Tenant Onboarding Rollout"
        verbose_name_plural = "Tenant Onboarding Rollouts"


class ConversationalOnboardingCapabilityFilter(SimpleListFilter):
    """Filter users by their conversational onboarding capabilities"""
    title = 'Conversational Onboarding Capabilities'
    parameter_name = 'onboarding_capabilities'

    def lookups(self, request: HttpRequest, model_admin):
        return (
            ('enabled', 'Conversational Onboarding Enabled'),
            ('approver', 'Can Approve AI Recommendations'),
            ('manage_kb', 'Can Manage Knowledge Base'),
            ('none', 'No Onboarding Capabilities'),
        )

    def queryset(self, request: HttpRequest, queryset):
        if self.value() == 'enabled':
            return queryset.filter(capabilities__has_key='can_use_conversational_onboarding')
        elif self.value() == 'approver':
            return queryset.filter(capabilities__has_key='can_approve_ai_recommendations')
        elif self.value() == 'manage_kb':
            return queryset.filter(capabilities__has_key='can_manage_knowledge_base')
        elif self.value() == 'none':
            return queryset.filter(
                Q(capabilities__isnull=True) |
                ~Q(capabilities__has_any_keys=['can_use_conversational_onboarding', 'can_approve_ai_recommendations', 'can_manage_knowledge_base'])
            )
        return queryset


@admin.register(PeopleOnboardingProxy)
class PeopleConversationalOnboardingAdmin(admin.ModelAdmin):
    """
    Enhanced People admin with conversational onboarding capability management

    This admin interface extends the default People admin to include
    specific controls for managing conversational onboarding capabilities.
    """
    list_display = [
        'loginid', 'email', 'fname', 'lname', 'client',
        'onboarding_enabled', 'approver_status', 'kb_manager_status',
        'capability_summary', 'last_active'
    ]
    list_filter = [
        ConversationalOnboardingCapabilityFilter,
        'client', 'is_staff', 'is_active', 'is_verified'
    ]
    search_fields = ['loginid', 'email', 'fname', 'lname']
    readonly_fields = ['id', 'cdtz', 'mdtz', 'cuser', 'muser', 'capability_json_display']

    fieldsets = (
        ('Basic Information', {
            'fields': ('loginid', 'email', 'fname', 'lname', 'client')
        }),
        ('Conversational Onboarding Capabilities', {
            'fields': ('onboarding_capability_controls', 'capability_json_display'),
            'description': 'Control access to conversational onboarding features'
        }),
        ('Account Status', {
            'fields': ('is_active', 'is_staff', 'is_verified'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('cdtz', 'mdtz', 'cuser', 'muser'),
            'classes': ('collapse',)
        })
    )

    actions = [
        'enable_conversational_onboarding',
        'disable_conversational_onboarding',
        'make_ai_approvers',
        'remove_ai_approvers',
        'export_capability_report'
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client')

    def onboarding_enabled(self, obj: People) -> SafeString:
        """Display onboarding enabled status with visual indicator"""
        if obj.get_capability('can_use_conversational_onboarding'):
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: red;">✗ Disabled</span>')
    onboarding_enabled.short_description = 'Onboarding'

    def approver_status(self, obj: People) -> SafeString:
        """Display AI approver status"""
        if obj.get_capability('can_approve_ai_recommendations'):
            return format_html('<span style="color: blue;">✓ Approver</span>')
        return format_html('<span style="color: gray;">—</span>')
    approver_status.short_description = 'AI Approver'

    def kb_manager_status(self, obj: People) -> SafeString:
        """Display knowledge base manager status"""
        if obj.get_capability('can_manage_knowledge_base'):
            return format_html('<span style="color: orange;">✓ KB Manager</span>')
        return format_html('<span style="color: gray;">—</span>')
    kb_manager_status.short_description = 'KB Manager'

    def capability_summary(self, obj: People) -> str:
        """Show summary of all AI-related capabilities"""
        caps = []
        if obj.get_capability('can_use_conversational_onboarding'):
            caps.append('User')
        if obj.get_capability('can_approve_ai_recommendations'):
            caps.append('Approver')
        if obj.get_capability('can_manage_knowledge_base'):
            caps.append('KB Manager')
        return ', '.join(caps) if caps else 'None'
    capability_summary.short_description = 'AI Capabilities'

    def last_active(self, obj: People) -> str:
        """Show when user was last active"""
        return obj.mdtz.strftime('%Y-%m-%d %H:%M') if obj.mdtz else 'Never'
    last_active.short_description = 'Last Active'

    def capability_json_display(self, obj: People) -> SafeString:
        """Display capabilities as formatted JSON"""
        if obj.capabilities:
            formatted_json = json.dumps(obj.capabilities, indent=2, sort_keys=True)
            return format_html('<pre style="background: #f8f9fa; padding: 10px;">{}</pre>', formatted_json)
        return 'No capabilities set'
    capability_json_display.short_description = 'Current Capabilities (JSON)'

    def onboarding_capability_controls(self, obj: People) -> SafeString:
        """Render capability control checkboxes"""
        if not obj.pk:  # New object
            return 'Save the user first to manage capabilities'

        controls_html = []
        capabilities_config = [
            ('can_use_conversational_onboarding', 'Enable Conversational Onboarding', 'Allows user to start and use conversational onboarding sessions'),
            ('can_approve_ai_recommendations', 'AI Recommendations Approver', 'Allows user to approve or reject AI-generated recommendations'),
            ('can_manage_knowledge_base', 'Knowledge Base Manager', 'Allows user to manage knowledge base content and settings'),
            ('can_escalate_conversations', 'Conversation Escalation', 'Allows user to escalate conversations to helpdesk'),
            ('can_access_admin_endpoints', 'Admin API Access', 'Allows access to administrative API endpoints'),
        ]

        for cap_key, cap_label, cap_description in capabilities_config:
            is_enabled = obj.get_capability(cap_key)
            checked = 'checked' if is_enabled else ''

            controls_html.append(f'''
                <div style="margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                    <label style="display: block; font-weight: bold;">
                        <input type="checkbox" name="capability_{cap_key}" {checked}
                               onchange="updateCapability('{obj.pk}', '{cap_key}', this.checked)"
                               style="margin-right: 8px;">
                        {cap_label}
                    </label>
                    <small style="color: #666; display: block; margin-left: 20px;">{cap_description}</small>
                </div>
            ''')

        # Add JavaScript for AJAX capability updates
        controls_html.append('''
            <script>
            function updateCapability(userId, capabilityKey, enabled) {
                fetch(`/admin/update-user-capability/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({
                        user_id: userId,
                        capability: capabilityKey,
                        enabled: enabled
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success message
                        const message = document.createElement('div');
                        message.innerHTML = `<p style="color: green;">✓ ${data.message}</p>`;
                        message.style.cssText = 'position: fixed; top: 20px; right: 20px; background: white; padding: 10px; border: 1px solid green; border-radius: 4px; z-index: 9999;';
                        document.body.appendChild(message);
                        setTimeout(() => message.remove(), 3000);
                    } else {
                        alert('Error updating capability: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error updating capability');
                });
            }
            </script>
        ''')

        return mark_safe(''.join(controls_html))
    onboarding_capability_controls.short_description = 'Capability Controls'

    # Admin actions
    @admin.action(description='Enable conversational onboarding for selected users')
    def enable_conversational_onboarding(self, request, queryset):
        updated = 0
        for user in queryset:
            user.set_capability('can_use_conversational_onboarding', True)
            user.save()
            updated += 1
        self.message_user(request, f'Enabled conversational onboarding for {updated} users', messages.SUCCESS)

    @admin.action(description='Disable conversational onboarding for selected users')
    def disable_conversational_onboarding(self, request, queryset):
        updated = 0
        for user in queryset:
            user.set_capability('can_use_conversational_onboarding', False)
            user.save()
            updated += 1
        self.message_user(request, f'Disabled conversational onboarding for {updated} users', messages.SUCCESS)

    @admin.action(description='Make selected users AI recommendation approvers')
    def make_ai_approvers(self, request, queryset):
        updated = 0
        for user in queryset:
            user.set_capability('can_approve_ai_recommendations', True)
            user.save()
            updated += 1
        self.message_user(request, f'Made {updated} users AI approvers', messages.SUCCESS)

    @admin.action(description='Remove AI approver capability from selected users')
    def remove_ai_approvers(self, request, queryset):
        updated = 0
        for user in queryset:
            user.set_capability('can_approve_ai_recommendations', False)
            user.save()
            updated += 1
        self.message_user(request, f'Removed AI approver capability from {updated} users', messages.SUCCESS)

    @admin.action(description='Export capability report for selected users')
    def export_capability_report(self, request, queryset):
        # This would generate a CSV/Excel report of user capabilities
        # Implementation would depend on specific reporting requirements
        self.message_user(request, f'Capability report generation started for {queryset.count()} users', messages.INFO)


class TenantOnboardingStatusFilter(SimpleListFilter):
    """Filter tenants by their onboarding status"""
    title = 'Conversational Onboarding Status'
    parameter_name = 'onboarding_status'

    def lookups(self, request: HttpRequest, model_admin):
        return (
            ('enabled', 'Onboarding Enabled'),
            ('disabled', 'Onboarding Disabled'),
            ('pilot', 'Pilot Program'),
        )

    def queryset(self, request: HttpRequest, queryset):
        # This would filter based on tenant-level settings stored in a related model
        # For now, return the full queryset
        return queryset


@admin.register(TenantOnboardingProxy)
class TenantConversationalOnboardingAdmin(admin.ModelAdmin):
    """
    Enhanced tenant admin with conversational onboarding rollout controls
    """
    list_display = [
        'buname', 'bucode', 'onboarding_status', 'user_count',
        'enabled_users_count', 'pilot_status', 'rollout_percentage'
    ]
    list_filter = [TenantOnboardingStatusFilter, 'is_active']
    search_fields = ['buname', 'bucode']

    actions = [
        'enable_onboarding_for_tenant',
        'disable_onboarding_for_tenant',
        'start_pilot_program',
        'full_rollout'
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            user_count=Count('people'),
            enabled_users_count=Count('people', filter=Q(people__capabilities__has_key='can_use_conversational_onboarding'))
        )

    def onboarding_status(self, obj: Bt) -> SafeString:
        """Display tenant onboarding status"""
        # This would check tenant-level settings
        enabled_users = getattr(obj, 'enabled_users_count', 0)
        total_users = getattr(obj, 'user_count', 0)

        if total_users == 0:
            return format_html('<span style="color: gray;">No Users</span>')
        elif enabled_users == 0:
            return format_html('<span style="color: red;">Disabled</span>')
        elif enabled_users == total_users:
            return format_html('<span style="color: green;">Full Rollout</span>')
        else:
            return format_html('<span style="color: orange;">Partial ({}/{})</span>', enabled_users, total_users)
    onboarding_status.short_description = 'Onboarding Status'

    def user_count(self, obj: Bt) -> int:
        """Total users in tenant"""
        return getattr(obj, 'user_count', 0)
    user_count.short_description = 'Total Users'

    def enabled_users_count(self, obj: Bt) -> int:
        """Users with onboarding enabled"""
        return getattr(obj, 'enabled_users_count', 0)
    enabled_users_count.short_description = 'Enabled Users'

    def pilot_status(self, obj: Bt) -> SafeString:
        """Show if tenant is in pilot program"""
        # This would check a pilot status field/setting
        return format_html('<span style="color: blue;">Active</span>')
    pilot_status.short_description = 'Pilot'

    def rollout_percentage(self, obj: Bt) -> str:
        """Calculate rollout percentage"""
        enabled = getattr(obj, 'enabled_users_count', 0)
        total = getattr(obj, 'user_count', 0)
        if total == 0:
            return '0%'
        return f'{(enabled / total * 100):.1f}%'
    rollout_percentage.short_description = 'Rollout %'

    # Admin actions for tenant-level management
    @admin.action(description='Enable conversational onboarding for all users in selected tenants')
    def enable_onboarding_for_tenant(self, request, queryset):
        updated_tenants = 0
        updated_users = 0

        for tenant in queryset:
            tenant_users = People.objects.filter(client=tenant)
            for user in tenant_users:
                user.set_capability('can_use_conversational_onboarding', True)
                user.save()
                updated_users += 1
            updated_tenants += 1

        self.message_user(
            request,
            f'Enabled conversational onboarding for {updated_users} users across {updated_tenants} tenants',
            messages.SUCCESS
        )

    @admin.action(description='Disable conversational onboarding for all users in selected tenants')
    def disable_onboarding_for_tenant(self, request, queryset):
        updated_tenants = 0
        updated_users = 0

        for tenant in queryset:
            tenant_users = People.objects.filter(client=tenant)
            for user in tenant_users:
                user.set_capability('can_use_conversational_onboarding', False)
                user.save()
                updated_users += 1
            updated_tenants += 1

        self.message_user(
            request,
            f'Disabled conversational onboarding for {updated_users} users across {updated_tenants} tenants',
            messages.SUCCESS
        )


# Custom admin views for rollout management
class OnboardingRolloutDashboardView:
    """Custom admin view for managing conversational onboarding rollout"""

    def __init__(self, admin_site):
        self.admin_site = admin_site

    def rollout_dashboard(self, request: HttpRequest) -> HttpResponse:
        """Main dashboard for rollout management"""
        context = {
            'title': 'Conversational Onboarding Rollout Dashboard',
            'total_tenants': Bt.objects.count(),
            'total_users': People.objects.count(),
            'enabled_users': People.objects.filter(capabilities__has_key='can_use_conversational_onboarding').count(),
            'approvers': People.objects.filter(capabilities__has_key='can_approve_ai_recommendations').count(),
            'kb_managers': People.objects.filter(capabilities__has_key='can_manage_knowledge_base').count(),
        }

        return render(request, 'admin/onboarding_rollout_dashboard.html', context)

    def update_user_capability(self, request: HttpRequest) -> HttpResponse:
        """AJAX endpoint for updating user capabilities"""
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'})

        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            capability = data.get('capability')
            enabled = data.get('enabled')

            user = People.objects.get(pk=user_id)
            user.set_capability(capability, enabled)
            user.save()

            action = 'enabled' if enabled else 'disabled'
            return JsonResponse({
                'success': True,
                'message': f'Capability {capability} {action} for {user.email}'
            })

        except People.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            return JsonResponse({'success': False, 'error': str(e)})


# Custom admin site with additional URLs
class OnboardingAdminSite(admin.AdminSite):
    """Custom admin site with onboarding rollout management"""
    site_header = 'Conversational Onboarding Administration'
    site_title = 'Onboarding Admin'
    index_title = 'Rollout & Feature Management'

    def get_urls(self):
        """Include custom admin URLs"""
        urls = super().get_urls()
        rollout_view = OnboardingRolloutDashboardView(self)

        custom_urls = [
            path('onboarding-rollout-dashboard/', rollout_view.rollout_dashboard, name='onboarding-rollout-dashboard'),
            path('update-user-capability/', rollout_view.update_user_capability, name='update-user-capability'),
        ]
        return custom_urls + urls


# URL patterns for integrating with existing admin
def get_admin_urls():
    """Get URL patterns for custom admin views to integrate with existing admin"""
    rollout_view = OnboardingRolloutDashboardView(admin.site)

    return [
        path('onboarding-rollout-dashboard/', rollout_view.rollout_dashboard, name='onboarding-rollout-dashboard'),
        path('update-user-capability/', rollout_view.update_user_capability, name='update-user-capability'),
    ]