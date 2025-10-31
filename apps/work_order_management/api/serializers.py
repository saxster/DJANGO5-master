"""
Work Order Management API Serializers

Serializers for work permits, approvers, and vendors.

Compliance with .claude/rules.md:
- Serializers < 100 lines each
- Specific validation
"""

from rest_framework import serializers
from apps.work_order_management.models import Wom, Approver, Vendor, WomDetails
import logging

logger = logging.getLogger(__name__)


class WomListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for work permit list views."""

    class Meta:
        model = Wom
        fields = [
            'id', 'uuid', 'description', 'workstatus',
            'workpermit', 'plandatetime', 'expirydatetime',
            'priority', 'bu_id', 'client_id', 'vendor_id',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'modified_at']


class WomDetailSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for work permit detail views."""

    vendor_name = serializers.CharField(
        source='vendor.name',
        read_only=True
    )
    location_name = serializers.CharField(
        source='location.name',
        read_only=True
    )

    class Meta:
        model = Wom
        fields = [
            'id', 'uuid', 'description', 'workstatus',
            'workpermit', 'plandatetime', 'expirydatetime',
            'starttime', 'gpslocation', 'priority',
            'asset', 'location', 'location_name',
            'vendor', 'vendor_name', 'bu_id', 'client_id',
            'approvers', 'verifiers', 'ticketcategory',
            'other_data', 'qset',
            'created_at', 'modified_at', 'cuser', 'muser'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'modified_at']


class ApproverSerializer(serializers.ModelSerializer):
    """Serializer for approver operations."""

    people_name = serializers.CharField(
        source='people.get_full_name',
        read_only=True
    )

    class Meta:
        model = Approver
        fields = [
            'id', 'people', 'people_name',
            'bu', 'client', 'is_active',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class VendorSerializer(serializers.ModelSerializer):
    """Serializer for vendor operations."""

    class Meta:
        model = Vendor
        fields = [
            'id', 'name', 'contact_person', 'contact_number',
            'email', 'address', 'client', 'bu',
            'is_active', 'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class WomDetailsSerializer(serializers.ModelSerializer):
    """Serializer for work permit details (questionnaire answers)."""

    question_text = serializers.CharField(
        source='question.question_text',
        read_only=True
    )

    class Meta:
        model = WomDetails
        fields = [
            'id', 'wom', 'question', 'question_text',
            'qset', 'seqno', 'answertype', 'answer',
            'options', 'min', 'max', 'alerton',
            'ismandatory', 'isavpt', 'alerts',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


__all__ = [
    'WomListSerializer',
    'WomDetailSerializer',
    'ApproverSerializer',
    'VendorSerializer',
    'WomDetailsSerializer',
]
