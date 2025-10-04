"""
NOC Audit Log Serializers.

DRF serializers for audit trail and compliance reporting.
Follows .claude/rules.md Rule #7 (<150 lines).
"""

from rest_framework import serializers
from apps.noc.models import NOCAuditLog
from apps.noc.services import NOCPrivacyService

__all__ = [
    'NOCAuditLogSerializer',
]


class NOCAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for NOC audit logs."""

    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = NOCAuditLog
        fields = [
            'id', 'action', 'actor_name', 'entity_type', 'entity_id',
            'metadata', 'ip_address', 'cdtz'
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor:
            return NOCPrivacyService.mask_pii(
                {'name': obj.actor.peoplename},
                self.context.get('user', None)
            ).get('name')
        return None