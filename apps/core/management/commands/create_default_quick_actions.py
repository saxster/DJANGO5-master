"""
Management Command: Create Default Quick Actions

Seeds the database with common pre-built quick actions.

Author: Claude Code
Date: 2025-11-07
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models.quick_action import QuickAction


class Command(BaseCommand):
    help = 'Create default Quick Actions for common scenarios'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Delete existing actions and create fresh ones'
        )
    
    def handle(self, *args, **options):
        if options['overwrite']:
            count = QuickAction.objects.all().delete()[0]
            self.stdout.write(
                self.style.WARNING(f'Deleted {count} existing Quick Actions')
            )
        
        actions = self.get_default_actions()
        
        created_count = 0
        with transaction.atomic():
            for action_data in actions:
                action, created = QuickAction.objects.get_or_create(
                    name=action_data['name'],
                    defaults=action_data
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Created: {action.name}")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Already exists: {action.name}")
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Done! Created {created_count} new Quick Action(s)'
            )
        )
    
    def get_default_actions(self):
        """Return list of default quick actions."""
        return [
            {
                'name': 'Camera Offline - Quick Fix',
                'description': 'First response when a camera stops working',
                'when_to_use': 'Use this when you get a camera offline alert',
                'automated_steps': [
                    {
                        'action_label': 'Ping camera to check connection',
                        'action_type': 'ping_device',
                        'params': {}
                    },
                    {
                        'action_label': 'Update ticket status to "In Progress"',
                        'action_type': 'update_status',
                        'params': {'status': 'in_progress'}
                    },
                    {
                        'action_label': 'Assign to Tech Team',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Tech Team'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Check if camera has power (look for LED light)',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Check network cable connection',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Note camera model and location',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'High Priority Ticket Response',
                'description': 'Standard response for urgent customer issues',
                'when_to_use': 'Use this for any high-priority or urgent ticket',
                'automated_steps': [
                    {
                        'action_label': 'Acknowledge ticket immediately',
                        'action_type': 'update_status',
                        'params': {'status': 'acknowledged'}
                    },
                    {
                        'action_label': 'Set priority to High',
                        'action_type': 'set_priority',
                        'params': {'priority': 'high'}
                    },
                    {
                        'action_label': 'Notify customer we received it',
                        'action_type': 'send_notification',
                        'params': {
                            'recipient': 'customer',
                            'message': 'We received your urgent request and are working on it'
                        }
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Call customer to confirm issue',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Get more details about the problem',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Access Control Issue',
                'description': 'Handle door/gate access problems',
                'when_to_use': 'Use when someone reports access control not working',
                'automated_steps': [
                    {
                        'action_label': 'Check device status',
                        'action_type': 'ping_device',
                        'params': {}
                    },
                    {
                        'action_label': 'Assign to Security Team',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Security Team'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Verify which door/gate is affected',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Test access card on reader',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Check for error messages on reader display',
                        'needs_photo': True,
                        'needs_note': False
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Fire Alarm Test',
                'description': 'Standard procedure for scheduled fire alarm testing',
                'when_to_use': 'Use for monthly fire alarm system tests',
                'automated_steps': [
                    {
                        'action_label': 'Notify all occupants of test',
                        'action_type': 'send_notification',
                        'params': {
                            'recipient': 'all_users',
                            'message': 'Fire alarm test in progress - DO NOT EVACUATE'
                        }
                    },
                    {
                        'action_label': 'Create test record',
                        'action_type': 'add_comment',
                        'params': {'comment': 'Fire alarm test initiated'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Test each fire alarm pull station',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Verify alarm sounds at all locations',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Reset alarm panel',
                        'needs_photo': True,
                        'needs_note': False
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Equipment Maintenance Check',
                'description': 'Standard preventive maintenance procedure',
                'when_to_use': 'Use for scheduled equipment maintenance',
                'automated_steps': [
                    {
                        'action_label': 'Update status to "Under Maintenance"',
                        'action_type': 'update_status',
                        'params': {'status': 'maintenance'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Visual inspection for damage or wear',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Clean equipment exterior',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Test all functions',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Record meter readings',
                        'needs_photo': True,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'New Employee Onboarding',
                'description': 'Standard steps for new employee setup',
                'when_to_use': 'Use when a new employee starts',
                'automated_steps': [
                    {
                        'action_label': 'Create user account',
                        'action_type': 'add_comment',
                        'params': {'comment': 'User account created'}
                    },
                    {
                        'action_label': 'Send welcome email',
                        'action_type': 'send_notification',
                        'params': {
                            'recipient': 'new_employee',
                            'message': 'Welcome to the team!'
                        }
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Issue access card',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Give facility tour',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Explain emergency procedures',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Power Outage Response',
                'description': 'Standard procedure for power outage',
                'when_to_use': 'Use when facility loses power',
                'automated_steps': [
                    {
                        'action_label': 'Notify facilities team',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Facilities Team'}
                    },
                    {
                        'action_label': 'Alert occupants',
                        'action_type': 'send_notification',
                        'params': {
                            'recipient': 'all_users',
                            'message': 'Power outage detected - backup systems active'
                        }
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Check backup generator status',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Verify critical systems are running',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Contact utility company',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Water Leak Emergency',
                'description': 'Immediate response to water leaks',
                'when_to_use': 'Use immediately when water leak is reported',
                'automated_steps': [
                    {
                        'action_label': 'Set priority to URGENT',
                        'action_type': 'set_priority',
                        'params': {'priority': 'urgent'}
                    },
                    {
                        'action_label': 'Notify maintenance team',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Maintenance Team'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Locate source of leak',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Shut off water supply if possible',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Place warning signs',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Document damage',
                        'needs_photo': True,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'HVAC Not Working',
                'description': 'Standard response for heating/cooling issues',
                'when_to_use': 'Use when HVAC system is not maintaining temperature',
                'automated_steps': [
                    {
                        'action_label': 'Assign to HVAC technician',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'HVAC Team'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Check thermostat settings',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Check air filter condition',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Listen for unusual noises',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Suspicious Activity Report',
                'description': 'Standard procedure for security concerns',
                'when_to_use': 'Use when suspicious activity is reported',
                'automated_steps': [
                    {
                        'action_label': 'Alert security team immediately',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Security Team'}
                    },
                    {
                        'action_label': 'Set to HIGH priority',
                        'action_type': 'set_priority',
                        'params': {'priority': 'high'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Document exact location and time',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Review camera footage',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Interview witnesses if available',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Lighting Failure',
                'description': 'Standard response for lighting problems',
                'when_to_use': 'Use when lights are not working in an area',
                'automated_steps': [
                    {
                        'action_label': 'Assign to electrical team',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Electrical Team'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Identify affected area',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Check circuit breaker',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Test light switches',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Elevator Out of Service',
                'description': 'Standard procedure for elevator problems',
                'when_to_use': 'Use when elevator is not working',
                'automated_steps': [
                    {
                        'action_label': 'Set to URGENT priority',
                        'action_type': 'set_priority',
                        'params': {'priority': 'urgent'}
                    },
                    {
                        'action_label': 'Notify elevator service company',
                        'action_type': 'send_notification',
                        'params': {
                            'recipient': 'elevator_service',
                            'message': 'Elevator service required'
                        }
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Post "Out of Service" signs',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Check if anyone is trapped',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Note error codes on display',
                        'needs_photo': True,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Parking Access Issue',
                'description': 'Handle parking gate/barrier problems',
                'when_to_use': 'Use when parking access system is not working',
                'automated_steps': [
                    {
                        'action_label': 'Assign to parking management',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Parking Team'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Test parking pass reader',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Check gate/barrier mechanism',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Verify no obstructions',
                        'needs_photo': True,
                        'needs_note': False
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Workstation Setup',
                'description': 'Set up new workstation for employee',
                'when_to_use': 'Use when setting up a new desk/workstation',
                'automated_steps': [
                    {
                        'action_label': 'Create setup task',
                        'action_type': 'add_comment',
                        'params': {'comment': 'Workstation setup initiated'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Set up computer and peripherals',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Test network connection',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Arrange furniture ergonomically',
                        'needs_photo': True,
                        'needs_note': False
                    },
                    {
                        'instruction': 'Stock supplies',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Meeting Room Booking Issue',
                'description': 'Resolve meeting room reservation problems',
                'when_to_use': 'Use when there is a meeting room booking conflict',
                'automated_steps': [
                    {
                        'action_label': 'Notify admin team',
                        'action_type': 'assign_to_group',
                        'params': {'group_name': 'Admin Team'}
                    }
                ],
                'manual_steps': [
                    {
                        'instruction': 'Verify booking details in system',
                        'needs_photo': True,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Contact affected parties',
                        'needs_photo': False,
                        'needs_note': True
                    },
                    {
                        'instruction': 'Offer alternative room if available',
                        'needs_photo': False,
                        'needs_note': True
                    }
                ],
                'is_active': True
            }
        ]
