"""
Onboarding & Admin API Serializers

Serializers for business units, locations, shifts, and type assistance.

Compliance with .claude/rules.md:
- Serializers < 100 lines each
- Specific validation
"""

from rest_framework import serializers
import logging

logger = logging.getLogger(__name__)


class BtSerializer(serializers.Serializer):
    """Serializer for business units (sites)."""

    id = serializers.IntegerField()
    buname = serializers.CharField()
    bucode = serializers.CharField()
    buaddress = serializers.CharField(required=False)
    client = serializers.IntegerField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    modified_at = serializers.DateTimeField()


class LocationSerializer(serializers.Serializer):
    """Serializer for locations."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    bu = serializers.IntegerField()
    client = serializers.IntegerField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    modified_at = serializers.DateTimeField()


class ShiftSerializer(serializers.Serializer):
    """Serializer for shifts."""

    id = serializers.IntegerField()
    shift_name = serializers.CharField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    bu = serializers.IntegerField()
    client = serializers.IntegerField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    modified_at = serializers.DateTimeField()


class TypeAssistSerializer(serializers.Serializer):
    """Serializer for type assistance (lookup data)."""

    id = serializers.IntegerField()
    type_name = serializers.CharField()
    type_category = serializers.CharField()
    type_value = serializers.CharField()
    client = serializers.IntegerField()
    is_active = serializers.BooleanField()
    modified_at = serializers.DateTimeField()


__all__ = [
    'BtSerializer',
    'LocationSerializer',
    'ShiftSerializer',
    'TypeAssistSerializer',
]
