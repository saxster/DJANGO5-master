"""
Additional People Serializers

Serializers for groups (Pgroup).

Compliance with .claude/rules.md:
- Serializers < 100 lines
"""

from rest_framework import serializers


class PgroupSerializer(serializers.Serializer):
    """Serializer for people groups."""

    id = serializers.IntegerField()
    pgroupname = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    modified_at = serializers.DateTimeField()


__all__ = ['PgroupSerializer']
