from rest_framework import serializers
from django.utils import timezone
from .models import Wom, WomDetails
from apps.core.serializers import ValidatedModelSerializer
import logging

logger = logging.getLogger(__name__)


class WomSerializers(ValidatedModelSerializer):
    """
    Secure Work Order Management serializer with comprehensive validation.

    Compliance with Rule #13: Form Validation Requirements
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        Wom.objects.select_related('asset', 'location', 'qset', 'vendor', 
                                    'parent', 'ticketcategory', 'bu', 'client', 
                                    'cuser', 'muser', 'performedby')
                   .prefetch_related('categories')
    """

    xss_protect_fields = ['description']

    class Meta:
        model = Wom
        fields = [
            'id',
            'description',
            'plandatetime',
            'expirydatetime',
            'asset',
            'location',
            'qset',
            'workpermit',
            'vendor',
            'performedby',
            'parent',
            'ticketcategory',
            'categories',
            'priority',
            'workstatus',
            'ismailsent',
            'identifier',
            'seqno',
            'bu',
            'client',
            'cuser',
            'muser',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'seqno', 'created_at', 'updated_at']

    def validate_description(self, value):
        """Validate work order description."""
        if not value or not value.strip():
            raise serializers.ValidationError("Description is required")

        if len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters")

        return value.strip()

    def validate(self, attrs):
        """Cross-field validation and business rules."""
        attrs = super().validate(attrs)

        plandatetime = attrs.get('plandatetime')
        expirydatetime = attrs.get('expirydatetime')

        if plandatetime and expirydatetime:
            if expirydatetime <= plandatetime:
                raise serializers.ValidationError(
                    {'expirydatetime': 'Expiry datetime must be after plan datetime'}
                )

        priority = attrs.get('priority')
        workstatus = attrs.get('workstatus')

        if priority == Wom.Priority.CRITICAL and workstatus != Wom.WorkStatus.NEW:
            logger.warning(
                "Critical priority work order not in NEW status",
                extra={'priority': priority, 'status': workstatus}
            )

        if self.instance and self.instance.pk:
            current_status = self.instance.workstatus
            new_status = attrs.get('workstatus', current_status)

            terminal_states = [Wom.WorkStatus.COMPLETED, Wom.WorkStatus.CANCELLED]
            if current_status in terminal_states and new_status != current_status:
                raise serializers.ValidationError(
                    f"Cannot modify work order in {current_status} status"
                )

        return attrs


class WomDetailsSerializers(ValidatedModelSerializer):
    """
    Secure Work Order Details serializer with comprehensive validation.
    
    N+1 Optimization: Use with queryset optimized via:
        WomDetails.objects.select_related('wom', 'question', 'qset', 'cuser', 'muser')
    """

    class Meta:
        model = WomDetails
        fields = [
            'id',
            'wom',
            'question',
            'qset',
            'seqno',
            'answertype',
            'answer',
            'options',
            'min',
            'max',
            'alerton',
            'isavpt',
            'avpttype',
            'ismandatory',
            'alerts',
            'attachmentcount',
            'cuser',
            'muser',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_seqno(self, value):
        """Validate sequence number is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Sequence number must be positive")
        return value

    def validate_attachmentcount(self, value):
        """Validate attachment count is not negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Attachment count cannot be negative")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        wom = attrs.get('wom')
        seqno = attrs.get('seqno')

        if wom and seqno:
            existing = WomDetails.objects.filter(
                wom=wom, seqno=seqno
            ).exclude(id=self.instance.id if self.instance else None)

            if existing.exists():
                raise serializers.ValidationError(
                    {'seqno': 'Sequence number already exists for this work order'}
                )

        return attrs