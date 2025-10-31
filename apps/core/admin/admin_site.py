"""
IntelliWiz Custom Admin Site with Unfold Theme

Provides organized model grouping and modern UI for Django admin.

Features:
- Modern UI with Unfold theme
- Logical model organization by business domain
- Custom dashboard with metrics
- Enhanced search and filtering

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: Modular structure (<200 lines)
"""
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _


class IntelliWizAdminSite(AdminSite):
    """
    Custom admin site with Unfold theme and logical model grouping.

    Organizes models by business domain instead of technical app structure,
    making it easier for operations teams to find and manage data.
    """

    site_header = _('IntelliWiz Operations Center')
    site_title = _('IntelliWiz Admin')
    index_title = _('System Management Dashboard')
    enable_nav_sidebar = True

    def get_app_list(self, request, app_label=None):
        """
        Custom app list with logical business domain grouping.

        Instead of showing models grouped by Django app (technical structure),
        this groups them by business domain (functional structure).

        Example:
            Technical: activity.Job, activity.Asset (confusing)
            Business: Operations > Tasks & Tours, Operations > Assets (clear)
        """
        app_list = super().get_app_list(request, app_label)

        # Get logical groupings
        grouped_models = self._get_grouped_models()

        # Build new app list
        new_app_list = []
        for group_name, group_config in grouped_models.items():
            group_dict = {
                'name': group_name,
                'app_label': group_config['app_label'],
                'app_url': group_config.get('app_url', '#'),
                'models': self._extract_models_for_group(
                    app_list, group_config['models']
                ),
            }
            if group_dict['models']:
                new_app_list.append(group_dict)

        return new_app_list

    def _get_grouped_models(self):
        """
        Define logical model groups for admin dashboard.

        Returns:
            Dict mapping group names to their configuration including
            models list and app_label for URL routing.
        """
        return {
            'Operations': {
                'app_label': 'operations',
                'models': [
                    'activity.Job',
                    'activity.Asset',
                    'activity.MeterReading',
                    'activity.MeterReadingAlert',
                    'activity.VehicleEntry',
                    'activity.VehicleSecurityAlert',
                    'attendance.Attendance',
                ],
            },
            'People & Access': {
                'app_label': 'people',
                'models': [
                    'peoples.People',
                    'peoples.Pgroup',
                    'peoples.Pgbelonging',
                    'peoples.Capability',
                    'peoples.DeviceRegistration',
                    'peoples.DeviceRiskEvent',
                ],
            },
            'Help Desk & Tickets': {
                'app_label': 'helpdesk',
                'models': [
                    'y_helpdesk.Ticket',
                    'work_order_management.WorkOrder',
                ],
            },
            'Security & AI': {
                'app_label': 'security',
                'models': [
                    'helpbot.HelpBotSession',
                    'helpbot.HelpBotMessage',
                    'helpbot.HelpBotKnowledge',
                    'helpbot.HelpBotFeedback',
                    'helpbot.HelpBotContext',
                    'helpbot.HelpBotAnalytics',
                    'noc.Incident',
                    'face_recognition.FaceProfile',
                    'voice_recognition.VoiceProfile',
                ],
            },
            'Configuration': {
                'app_label': 'configuration',
                'models': [
                    'onboarding.TypeAssist',
                    'onboarding.Bt',
                    'onboarding.Shift',
                ],
            },
            'Wellness & Journal': {
                'app_label': 'wellness',
                'models': [
                    'journal.JournalEntry',
                    'journal.JournalMediaAttachment',
                    'journal.JournalPrivacySettings',
                    'wellness.WellnessProgram',
                ],
            },
            'Reports & Analytics': {
                'app_label': 'reports',
                'models': [
                    'reports.ReportTemplate',
                ],
            },
            'System Management': {
                'app_label': 'system',
                'models': [
                    'core.TaskFailureRecord',
                    'tenants.Tenant',
                ],
            },
        }

    def _extract_models_for_group(self, app_list, model_identifiers):
        """
        Extract model entries from app_list based on identifiers.

        Args:
            app_list: List of app dicts from Django admin
            model_identifiers: List of 'app_label.ModelName' strings

        Returns:
            List of model dicts matching the identifiers
        """
        models = []
        for model_id in model_identifiers:
            try:
                app_label, model_name = model_id.split('.')
            except ValueError:
                continue  # Skip invalid identifiers

            # Find model in app_list
            for app in app_list:
                if app['app_label'] != app_label:
                    continue

                for model in app['models']:
                    if model['object_name'] == model_name:
                        models.append(model)
                        break

        return models


# Note:
# The site is activated via apps.core.admin.apps.IntelliWizAdminConfig,
# which sets ``default_site`` to this class. Use ``django.contrib.admin.site``
# at runtime to access the configured IntelliWiz admin instance.
