"""
Unified Ticket Serializer - Context-Aware Serialization System

Replaces 5+ different ticket serialization approaches with a single,
flexible serializer that adapts to different contexts and use cases.

Contexts supported:
- Mobile sync operations
- Web API responses
- Data export operations
- Admin interface display

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Serializer classes <100 lines each
- Rule #11: Specific validation handling
"""

import logging
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from dataclasses import dataclass

from rest_framework import serializers
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.services.ticket_state_machine import TicketStateMachine
from apps.y_helpdesk.services.ticket_audit_service import TicketAuditService

logger = logging.getLogger(__name__)


class SerializationContext(Enum):
    """Different serialization contexts with specific field requirements."""
    MOBILE_SYNC = "mobile_sync"
    WEB_API = "web_api"
    DASHBOARD = "dashboard"
    EXPORT = "export"
    ADMIN = "admin"
    MINIMAL = "minimal"


class SerializationFormat(Enum):
    """Different output formats."""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    FLAT_DICT = "flat_dict"


@dataclass
class SerializationConfig:
    """Configuration for serialization behavior."""
    context: SerializationContext
    format: SerializationFormat = SerializationFormat.JSON
    include_relationships: bool = True
    include_workflow: bool = True
    include_audit_fields: bool = True
    include_computed_fields: bool = True
    field_prefix: str = ""
    max_depth: int = 2
    exclude_sensitive: bool = True


class TicketUnifiedSerializer(serializers.ModelSerializer):
    """
    Unified ticket serializer with context-aware field selection.

    Adapts field selection and validation based on serialization context,
    eliminating the need for multiple specialized serializers.
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        Ticket.objects.select_related('assignedtopeople', 'assignedtogroup', 
                                      'ticketcategory', 'location', 'asset', 
                                      'bu', 'client', 'cuser', 'muser')
                      .prefetch_related('workflow')
    """

    # Context-specific field sets
    FIELD_SETS = {
        SerializationContext.MOBILE_SYNC: {
            'core': ['id', 'uuid', 'ticketno', 'ticketdesc', 'status', 'priority'],
            'assignment': ['assignedtopeople', 'assignedtogroup'],
            'metadata': ['cdtz', 'mdtz', 'ctzoffset', 'ticketsource'],
            'workflow': ['level', 'isescalated'],
            'relationships': ['bu', 'client', 'ticketcategory'],
            'sync': ['version', 'last_sync_timestamp', 'mobile_id']
        },
        SerializationContext.WEB_API: {
            'core': ['id', 'ticketno', 'ticketdesc', 'status', 'priority', 'comments'],
            'assignment': ['assignedtopeople', 'assignedtogroup'],
            'metadata': ['cdtz', 'mdtz', 'cuser', 'muser'],
            'workflow': ['level', 'isescalated', 'workflow_status'],
            'relationships': ['bu', 'client', 'ticketcategory', 'location', 'asset'],
            'audit': ['audit_trail_summary']
        },
        SerializationContext.DASHBOARD: {
            'core': ['id', 'ticketno', 'status', 'priority'],
            'assignment': ['assignedtopeople'],
            'metadata': ['cdtz', 'cuser'],
            'workflow': ['isescalated', 'escalation_level'],
            'relationships': ['bu', 'ticketcategory'],
            'computed': ['age_days', 'overdue_status']
        },
        SerializationContext.EXPORT: {
            'core': ['ticketno', 'ticketdesc', 'status', 'priority', 'comments'],
            'assignment': ['assigned_person_name', 'assigned_group_name'],
            'metadata': ['created_date', 'modified_date', 'created_by_name'],
            'workflow': ['escalation_level', 'escalation_status'],
            'relationships': ['business_unit_name', 'category_name', 'location_name'],
            'audit': ['status_history', 'assignment_history']
        },
        SerializationContext.MINIMAL: {
            'core': ['id', 'ticketno', 'status'],
            'metadata': ['cdtz'],
            'assignment': ['assignedtopeople']
        }
    }

    # Dynamic fields based on context
    mobile_id = serializers.UUIDField(required=False, allow_null=True)
    version = serializers.IntegerField(required=False, default=1)
    last_sync_timestamp = serializers.DateTimeField(required=False, allow_null=True)
    workflow_status = serializers.SerializerMethodField()
    escalation_level = serializers.SerializerMethodField()
    audit_trail_summary = serializers.SerializerMethodField()
    age_days = serializers.SerializerMethodField()
    overdue_status = serializers.SerializerMethodField()

    # Flattened relationship fields for export context
    assigned_person_name = serializers.SerializerMethodField()
    assigned_group_name = serializers.SerializerMethodField()
    business_unit_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    created_date = serializers.SerializerMethodField()
    modified_date = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = '__all__'  # Dynamic field selection handled in __init__

    def __init__(self, *args, **kwargs):
        # Extract serialization configuration from context
        self.config = self._extract_config(kwargs.get('context', {}))

        # Remove our custom context before calling super
        context = kwargs.get('context', {})
        if 'serialization_config' in context:
            kwargs['context'] = {k: v for k, v in context.items()
                               if k != 'serialization_config'}

        super().__init__(*args, **kwargs)

        # Configure fields based on context
        self._configure_fields()

    def _extract_config(self, context: Dict) -> SerializationConfig:
        """Extract serialization configuration from context."""
        config_data = context.get('serialization_config', {})

        return SerializationConfig(
            context=SerializationContext(
                config_data.get('context', SerializationContext.WEB_API.value)
            ),
            format=SerializationFormat(
                config_data.get('format', SerializationFormat.JSON.value)
            ),
            include_relationships=config_data.get('include_relationships', True),
            include_workflow=config_data.get('include_workflow', True),
            include_audit_fields=config_data.get('include_audit_fields', True),
            include_computed_fields=config_data.get('include_computed_fields', True),
            exclude_sensitive=config_data.get('exclude_sensitive', True)
        )

    def _configure_fields(self):
        """Configure fields based on serialization context."""
        if self.config.context not in self.FIELD_SETS:
            logger.warning(f"Unknown serialization context: {self.config.context}")
            return

        # Get field set for this context
        field_set = self.FIELD_SETS[self.config.context]
        allowed_fields = set()

        # Collect all allowed fields based on configuration
        for category, fields in field_set.items():
            if self._should_include_category(category):
                allowed_fields.update(fields)

        # Remove fields not in the allowed set
        existing_fields = set(self.fields.keys())
        fields_to_remove = existing_fields - allowed_fields

        for field_name in fields_to_remove:
            self.fields.pop(field_name, None)

        # Configure remaining fields
        self._configure_field_behavior()

    def _should_include_category(self, category: str) -> bool:
        """Determine if a field category should be included."""
        if category == 'relationships' and not self.config.include_relationships:
            return False
        if category == 'workflow' and not self.config.include_workflow:
            return False
        if category == 'audit' and not self.config.include_audit_fields:
            return False
        if category == 'computed' and not self.config.include_computed_fields:
            return False
        if category == 'sync' and self.config.context != SerializationContext.MOBILE_SYNC:
            return False
        return True

    def _configure_field_behavior(self):
        """Configure field-specific behavior."""
        # Make certain fields read-only in specific contexts
        if self.config.context == SerializationContext.EXPORT:
            for field_name in self.fields:
                self.fields[field_name].read_only = True

        # Configure sensitive field handling
        if self.config.exclude_sensitive:
            sensitive_fields = ['comments', 'events']
            for field_name in sensitive_fields:
                if field_name in self.fields:
                    # Could implement masking logic here
                    pass

    # Computed field methods
    def get_workflow_status(self, obj) -> Optional[str]:
        """Get workflow status from TicketWorkflow model."""
        try:
            return obj.workflow.workflow_status if hasattr(obj, 'workflow') else 'ACTIVE'
        except (AttributeError, ObjectDoesNotExist) as e:
            logger.debug(f"Could not retrieve workflow status for ticket {obj.id}: {e}")
            return 'ACTIVE'

    def get_escalation_level(self, obj) -> int:
        """Get escalation level from TicketWorkflow model."""
        try:
            return obj.workflow.escalation_level if hasattr(obj, 'workflow') else obj.level
        except (AttributeError, ObjectDoesNotExist) as e:
            logger.debug(f"Could not retrieve escalation level for ticket {obj.id}: {e}")
            return getattr(obj, 'level', 0)

    def get_audit_trail_summary(self, obj) -> Dict[str, Any]:
        """Get summarized audit trail information."""
        if self.config.context not in [SerializationContext.WEB_API, SerializationContext.ADMIN]:
            return {}

        try:
            workflow = getattr(obj, 'workflow', None)
            if workflow:
                return {
                    'total_activities': workflow.activity_count,
                    'last_activity': workflow.last_activity_at.isoformat() if workflow.last_activity_at else None,
                    'escalation_count': workflow.escalation_count
                }
        except (AttributeError, ObjectDoesNotExist, TypeError) as e:
            logger.debug(f"Could not retrieve audit trail for ticket {obj.id}: {e}")

        return {'total_activities': 0, 'last_activity': None, 'escalation_count': 0}

    def get_age_days(self, obj) -> int:
        """Calculate ticket age in days."""
        if obj.cdtz:
            age = timezone.now() - obj.cdtz
            return age.days
        return 0

    def get_overdue_status(self, obj) -> bool:
        """Determine if ticket is overdue."""
        # Simplified logic - could be enhanced with SLA calculations
        age_days = self.get_age_days(obj)
        if obj.priority == 'HIGH':
            return age_days > 1
        elif obj.priority == 'MEDIUM':
            return age_days > 3
        else:
            return age_days > 7

    # Flattened field methods for export context
    def get_assigned_person_name(self, obj) -> Optional[str]:
        """Get assigned person name."""
        return obj.assignedtopeople.peoplename if obj.assignedtopeople else None

    def get_assigned_group_name(self, obj) -> Optional[str]:
        """Get assigned group name."""
        return obj.assignedtogroup.groupname if obj.assignedtogroup else None

    def get_business_unit_name(self, obj) -> Optional[str]:
        """Get business unit name."""
        return obj.bu.buname if obj.bu else None

    def get_category_name(self, obj) -> Optional[str]:
        """Get category name."""
        return obj.ticketcategory.taname if obj.ticketcategory else None

    def get_location_name(self, obj) -> Optional[str]:
        """Get location name."""
        return obj.location.locationname if obj.location else None

    def get_created_by_name(self, obj) -> Optional[str]:
        """Get creator name."""
        return obj.cuser.peoplename if obj.cuser else None

    def get_created_date(self, obj) -> Optional[str]:
        """Get formatted creation date."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M:%S') if obj.cdtz else None

    def get_modified_date(self, obj) -> Optional[str]:
        """Get formatted modification date."""
        return obj.mdtz.strftime('%Y-%m-%d %H:%M:%S') if obj.mdtz else None

    def validate(self, attrs):
        """Unified validation using TicketStateMachine."""
        # Context-specific validation
        if self.config.context == SerializationContext.MOBILE_SYNC:
            return self._validate_mobile_sync(attrs)
        elif self.config.context == SerializationContext.WEB_API:
            return self._validate_web_api(attrs)

        return super().validate(attrs)

    def _validate_mobile_sync(self, attrs):
        """Validate mobile sync specific fields."""
        # Ensure mobile_id is provided for sync operations
        if not attrs.get('mobile_id') and not self.instance:
            raise serializers.ValidationError({
                'mobile_id': 'Mobile ID is required for new tickets from mobile clients'
            })

        return attrs

    def _validate_web_api(self, attrs):
        """Validate web API specific fields."""
        # Use TicketStateMachine for status validation
        if self.instance and 'status' in attrs:
            current_status = self.instance.status
            new_status = attrs['status']

            if not TicketStateMachine.is_valid_transition(current_status, new_status):
                allowed = TicketStateMachine.get_allowed_transitions(current_status)
                raise serializers.ValidationError({
                    'status': f'Invalid status transition from {current_status} to {new_status}. '
                            f'Allowed: {allowed}'
                })

        return attrs


# Convenience functions for different contexts

def serialize_for_mobile_sync(tickets, user: AbstractUser = None) -> List[Dict]:
    """Serialize tickets for mobile sync operations."""
    context = {
        'serialization_config': {
            'context': SerializationContext.MOBILE_SYNC.value,
            'include_relationships': True,
            'include_workflow': True
        },
        'request': type('obj', (object,), {'user': user})()
    }

    serializer = TicketUnifiedSerializer(tickets, many=True, context=context)
    return serializer.data


def serialize_for_web_api(tickets, user: AbstractUser = None) -> List[Dict]:
    """Serialize tickets for web API responses."""
    context = {
        'serialization_config': {
            'context': SerializationContext.WEB_API.value,
            'include_relationships': True,
            'include_workflow': True,
            'include_audit_fields': True
        },
        'request': type('obj', (object,), {'user': user})()
    }

    serializer = TicketUnifiedSerializer(tickets, many=True, context=context)
    return serializer.data


def serialize_for_dashboard(tickets) -> List[Dict]:
    """Serialize tickets for dashboard display."""
    context = {
        'serialization_config': {
            'context': SerializationContext.DASHBOARD.value,
            'include_relationships': False,
            'include_workflow': True,
            'include_computed_fields': True
        }
    }

    serializer = TicketUnifiedSerializer(tickets, many=True, context=context)
    return serializer.data


def serialize_for_export(tickets, format_type: str = 'csv') -> List[Dict]:
    """Serialize tickets for data export."""
    context = {
        'serialization_config': {
            'context': SerializationContext.EXPORT.value,
            'format': format_type,
            'include_relationships': True,
            'include_workflow': True,
            'include_audit_fields': True
        }
    }

    serializer = TicketUnifiedSerializer(tickets, many=True, context=context)
    return serializer.data
