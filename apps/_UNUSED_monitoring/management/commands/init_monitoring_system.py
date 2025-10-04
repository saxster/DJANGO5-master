"""
Initialize Monitoring System Command

Sets up default alert rules, ticket categories, and monitoring configuration.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.monitoring.models import (
    AlertRule, TicketCategory, AutomatedAction
)

class Command(BaseCommand):
    help = 'Initialize monitoring system with default configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing configuration (WARNING: destructive)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 INITIALIZING MONITORING SYSTEM')
        )

        try:
            with transaction.atomic():
                if options.get('reset', False):
                    self._reset_configuration()

                self._create_default_alert_rules()
                self._create_default_ticket_categories()
                self._create_automated_actions()

                self.stdout.write(
                    self.style.SUCCESS('✅ Monitoring system initialized successfully')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error initializing monitoring system: {str(e)}')
            )

    def _reset_configuration(self):
        """Reset existing monitoring configuration"""
        self.stdout.write('⚠️  Resetting existing configuration...')

        AlertRule.objects.all().delete()
        TicketCategory.objects.all().delete()
        AutomatedAction.objects.all().delete()

        self.stdout.write('   - Cleared existing configuration')

    def _create_default_alert_rules(self):
        """Create default alert rules"""
        self.stdout.write('📋 Creating default alert rules...')

        default_rules = [
            {
                'name': 'Critical Battery Level',
                'alert_type': 'BATTERY_CRITICAL',
                'severity': 'CRITICAL',
                'conditions': {
                    'battery_level_threshold': 10,
                    'time_window_minutes': 5
                },
                'cooldown_minutes': 5,
                'auto_resolve_minutes': 60,
                'notification_channels': ['dashboard', 'email', 'sms']
            },
            {
                'name': 'Low Battery Warning',
                'alert_type': 'BATTERY_LOW',
                'severity': 'WARNING',
                'conditions': {
                    'battery_level_threshold': 20,
                    'consider_shift_time': True
                },
                'cooldown_minutes': 15,
                'notification_channels': ['dashboard', 'email']
            },
            {
                'name': 'No Movement Detection',
                'alert_type': 'NO_MOVEMENT',
                'severity': 'HIGH',
                'conditions': {
                    'stationary_minutes_threshold': 30,
                    'exclude_break_times': True,
                    'work_hours_only': True
                },
                'cooldown_minutes': 10,
                'notification_channels': ['dashboard', 'sms', 'webhook']
            },
            {
                'name': 'Location Violation',
                'alert_type': 'LOCATION_VIOLATION',
                'severity': 'HIGH',
                'conditions': {
                    'geofence_buffer_meters': 100,
                    'min_accuracy_meters': 50
                },
                'cooldown_minutes': 5,
                'notification_channels': ['dashboard', 'email', 'sms']
            },
            {
                'name': 'Network Connectivity Lost',
                'alert_type': 'NETWORK_DOWN',
                'severity': 'HIGH',
                'conditions': {
                    'offline_minutes_threshold': 10
                },
                'cooldown_minutes': 10,
                'notification_channels': ['dashboard', 'email']
            },
            {
                'name': 'Poor Signal Strength',
                'alert_type': 'SIGNAL_POOR',
                'severity': 'WARNING',
                'conditions': {
                    'signal_threshold_dbm': -100,
                    'duration_minutes': 15
                },
                'cooldown_minutes': 20,
                'notification_channels': ['dashboard']
            },
            {
                'name': 'Biometric Authentication Failure',
                'alert_type': 'BIOMETRIC_FAILURE',
                'severity': 'HIGH',
                'conditions': {
                    'max_failed_attempts': 3,
                    'time_window_minutes': 10
                },
                'cooldown_minutes': 15,
                'notification_channels': ['dashboard', 'email', 'sms']
            },
            {
                'name': 'Concurrent Device Usage',
                'alert_type': 'CONCURRENT_USAGE',
                'severity': 'CRITICAL',
                'conditions': {
                    'detection_window_minutes': 5
                },
                'cooldown_minutes': 5,
                'notification_channels': ['dashboard', 'email', 'sms', 'webhook']
            },
            {
                'name': 'Device Overheating',
                'alert_type': 'DEVICE_OVERHEATING',
                'severity': 'CRITICAL',
                'conditions': {
                    'thermal_state': ['serious', 'critical']
                },
                'cooldown_minutes': 5,
                'auto_resolve_minutes': 30,
                'notification_channels': ['dashboard', 'sms', 'webhook']
            },
            {
                'name': 'High Memory Usage',
                'alert_type': 'MEMORY_HIGH',
                'severity': 'WARNING',
                'conditions': {
                    'memory_usage_threshold': 80,
                    'duration_minutes': 10
                },
                'cooldown_minutes': 30,
                'notification_channels': ['dashboard']
            }
        ]

        created_count = 0
        for rule_data in default_rules:
            rule, created = AlertRule.objects.get_or_create(
                name=rule_data['name'],
                alert_type=rule_data['alert_type'],
                defaults=rule_data
            )

            if created:
                created_count += 1
                self.stdout.write(f"   ✅ Created: {rule.name}")
            else:
                self.stdout.write(f"   ➡️  Exists: {rule.name}")

        self.stdout.write(f"📋 Created {created_count} new alert rules")

    def _create_default_ticket_categories(self):
        """Create default ticket categories"""
        self.stdout.write('🎫 Creating default ticket categories...')

        default_categories = [
            {
                'name': 'Battery Issues',
                'description': 'Tickets for battery-related problems',
                'default_priority': 'HIGH',
                'default_assignee_role': 'field_technician',
                'response_time_minutes': 30,
                'resolution_time_hours': 4,
                'title_template': 'Battery Issue: {user_name} - {device_id}',
                'description_template': 'Battery alert: {alert_description}',
                'auto_assign': True,
                'auto_escalate': True,
                'notification_channels': ['email', 'dashboard']
            },
            {
                'name': 'Security Incidents',
                'description': 'Security-related incidents and violations',
                'default_priority': 'CRITICAL',
                'default_assignee_role': 'security_team',
                'response_time_minutes': 15,
                'resolution_time_hours': 2,
                'title_template': 'Security Incident: {alert_type} - {user_name}',
                'description_template': 'Security alert: {alert_description}',
                'auto_assign': True,
                'auto_escalate': True,
                'notification_channels': ['email', 'sms', 'dashboard', 'webhook']
            },
            {
                'name': 'Device Performance',
                'description': 'Device performance and technical issues',
                'default_priority': 'MEDIUM',
                'default_assignee_role': 'it_support',
                'response_time_minutes': 60,
                'resolution_time_hours': 8,
                'title_template': 'Device Issue: {device_id} - {user_name}',
                'description_template': 'Performance alert: {alert_description}',
                'auto_assign': True,
                'auto_escalate': True,
                'notification_channels': ['email', 'dashboard']
            },
            {
                'name': 'Network Connectivity',
                'description': 'Network and connectivity issues',
                'default_priority': 'HIGH',
                'default_assignee_role': 'network_admin',
                'response_time_minutes': 45,
                'resolution_time_hours': 6,
                'title_template': 'Network Issue: {user_name} - {site_name}',
                'description_template': 'Network alert: {alert_description}',
                'auto_assign': True,
                'auto_escalate': True,
                'notification_channels': ['email', 'dashboard']
            },
            {
                'name': 'Emergency Response',
                'description': 'Emergency situations requiring immediate response',
                'default_priority': 'EMERGENCY',
                'default_assignee_role': 'emergency_response',
                'response_time_minutes': 5,
                'resolution_time_hours': 1,
                'title_template': 'EMERGENCY: {alert_type} - {user_name}',
                'description_template': 'Emergency alert: {alert_description}',
                'auto_assign': True,
                'auto_escalate': True,
                'notification_channels': ['sms', 'webhook', 'dashboard', 'email']
            }
        ]

        created_count = 0
        for category_data in default_categories:
            category, created = TicketCategory.objects.get_or_create(
                name=category_data['name'],
                defaults=category_data
            )

            if created:
                created_count += 1
                self.stdout.write(f"   ✅ Created: {category.name}")
            else:
                self.stdout.write(f"   ➡️  Exists: {category.name}")

        self.stdout.write(f"🎫 Created {created_count} new ticket categories")

    def _create_automated_actions(self):
        """Create automated actions"""
        self.stdout.write('🤖 Creating automated actions...')

        default_actions = [
            {
                'name': 'Emergency Call on No Movement',
                'description': 'Automatically call user when no movement detected',
                'action_type': 'NOTIFICATION',
                'trigger_condition': 'ALERT_CREATED',
                'trigger_criteria': {
                    'alert_types': ['NO_MOVEMENT'],
                    'severity_levels': ['HIGH', 'CRITICAL']
                },
                'action_config': {
                    'type': 'emergency_call',
                    'recipients': 'user_and_supervisor',
                    'max_attempts': 3
                },
                'cooldown_minutes': 10,
                'max_executions_per_hour': 6
            },
            {
                'name': 'Send Replacement Device',
                'description': 'Automatically request device replacement for critical battery',
                'action_type': 'RESOURCE_ALLOCATION',
                'trigger_condition': 'ALERT_CREATED',
                'trigger_criteria': {
                    'alert_types': ['BATTERY_CRITICAL'],
                    'severity_levels': ['CRITICAL']
                },
                'action_config': {
                    'resource_type': 'replacement_device',
                    'delivery_method': 'field_technician',
                    'priority': 'urgent'
                },
                'cooldown_minutes': 60,
                'max_executions_per_hour': 2
            },
            {
                'name': 'Security Investigation',
                'description': 'Automatically create security investigation for fraud alerts',
                'action_type': 'TICKET_CREATE',
                'trigger_condition': 'ALERT_CREATED',
                'trigger_criteria': {
                    'alert_types': ['FRAUD_RISK', 'CONCURRENT_USAGE'],
                    'severity_levels': ['CRITICAL', 'HIGH']
                },
                'action_config': {
                    'ticket_category': 'security_investigation',
                    'assign_to_role': 'security_investigator',
                    'priority': 'urgent'
                },
                'cooldown_minutes': 30,
                'max_executions_per_hour': 4
            },
            {
                'name': 'Device Restart Command',
                'description': 'Send restart command for performance issues',
                'action_type': 'DEVICE_COMMAND',
                'trigger_condition': 'ALERT_CREATED',
                'trigger_criteria': {
                    'alert_types': ['MEMORY_HIGH', 'PERFORMANCE_DEGRADED'],
                    'severity_levels': ['HIGH', 'CRITICAL']
                },
                'action_config': {
                    'command': 'restart_app',
                    'confirmation_required': False,
                    'timeout_seconds': 30
                },
                'cooldown_minutes': 120,
                'max_executions_per_hour': 1
            }
        ]

        created_count = 0
        for action_data in default_actions:
            action, created = AutomatedAction.objects.get_or_create(
                name=action_data['name'],
                defaults=action_data
            )

            if created:
                created_count += 1
                self.stdout.write(f"   ✅ Created: {action.name}")
            else:
                self.stdout.write(f"   ➡️  Exists: {action.name}")

        self.stdout.write(f"🤖 Created {created_count} new automated actions")