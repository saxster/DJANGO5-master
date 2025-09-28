"""
API Deprecation Registry Models
Tracks deprecated API endpoints and their lifecycle.

Compliance with .claude/rules.md:
- Rule #7: Model < 150 lines (split into multiple models)
- Rule #11: Specific exception handling
"""

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.tenants.models import BaseModel, TenantAwareModel
import logging

logger = logging.getLogger('api.deprecation')


class APIDeprecation(BaseModel, TenantAwareModel):
    """
    Tracks deprecated API endpoints with RFC-compliant lifecycle management.
    Supports RFC 9745 (Deprecation Header) and RFC 8594 (Sunset Header) standards.
    """

    API_TYPE_CHOICES = [
        ('rest', 'REST API'),
        ('graphql_query', 'GraphQL Query'),
        ('graphql_mutation', 'GraphQL Mutation'),
        ('graphql_field', 'GraphQL Field'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active - No deprecation'),
        ('deprecated', 'Deprecated - Still functional'),
        ('sunset_warning', 'Sunset Warning - Removal imminent'),
        ('removed', 'Removed - No longer available'),
    ]

    endpoint_pattern = models.CharField(max_length=255, help_text="URL pattern or GraphQL field path")
    api_type = models.CharField(max_length=20, choices=API_TYPE_CHOICES, default='rest')
    version_deprecated = models.CharField(max_length=10, help_text="Version when deprecated")
    version_removed = models.CharField(max_length=10, null=True, blank=True, help_text="Version when removed")
    deprecated_date = models.DateTimeField(default=timezone.now)
    sunset_date = models.DateTimeField(null=True, blank=True, help_text="RFC 8594 sunset date")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    replacement_endpoint = models.CharField(max_length=255, null=True, blank=True)
    migration_url = models.URLField(max_length=500, null=True, blank=True)
    deprecation_reason = models.TextField()
    notify_on_usage = models.BooleanField(default=True)

    class Meta:
        db_table = 'api_deprecation'
        verbose_name = 'API Deprecation'
        verbose_name_plural = 'API Deprecations'
        indexes = [
            models.Index(fields=['endpoint_pattern', 'status']),
            models.Index(fields=['sunset_date']),
            models.Index(fields=['api_type', 'status']),
        ]
        unique_together = [['endpoint_pattern', 'version_deprecated']]

    def __str__(self):
        return f"{self.endpoint_pattern} (deprecated in {self.version_deprecated})"

    def clean(self):
        if self.sunset_date and self.sunset_date < self.deprecated_date:
            raise ValidationError("Sunset date cannot be before deprecation date")
        if self.status == 'deprecated' and not self.replacement_endpoint:
            raise ValidationError("Replacement endpoint required for deprecated APIs")

    def is_sunset_warning_period(self):
        """Check if we're in the sunset warning period (30 days before sunset)."""
        if not self.sunset_date:
            return False
        days_until_sunset = (self.sunset_date - timezone.now()).days
        return 0 < days_until_sunset <= 30

    def update_status(self):
        """Automatically update status based on dates."""
        if self.sunset_date and timezone.now() >= self.sunset_date:
            self.status = 'removed'
        elif self.is_sunset_warning_period():
            self.status = 'sunset_warning'
        elif timezone.now() >= self.deprecated_date:
            self.status = 'deprecated'

    def get_deprecation_header(self):
        """Get RFC 9745 compliant Deprecation header value (Unix timestamp)."""
        return f"@{int(self.deprecated_date.timestamp())}"

    def get_sunset_header(self):
        """Get RFC 8594 compliant Sunset header value (HTTP date format)."""
        if not self.sunset_date:
            return None
        return self.sunset_date.strftime('%a, %d %b %Y %H:%M:%S GMT')

    def get_warning_header(self):
        """Get RFC 7234 Warning header (299 for deprecation warnings)."""
        if self.status == 'deprecated':
            return f'299 - "Deprecated API. Use {self.replacement_endpoint} instead."'
        elif self.status == 'sunset_warning':
            days = (self.sunset_date - timezone.now()).days
            return f'299 - "API will be removed in {days} days on {self.sunset_date.date()}"'
        return None

    def get_link_header(self):
        """Get Link header pointing to migration documentation."""
        if self.migration_url:
            return f'<{self.migration_url}>; rel="deprecation"; type="text/html"'
        return None


class APIDeprecationUsage(BaseModel):
    """
    Tracks usage of deprecated API endpoints for analytics.
    """

    deprecation = models.ForeignKey(APIDeprecation, on_delete=models.CASCADE, related_name='usage_logs')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user_id = models.IntegerField(null=True, blank=True)
    client_version = models.CharField(max_length=50, null=True, blank=True, help_text="Mobile SDK version")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'api_deprecation_usage'
        verbose_name = 'API Deprecation Usage'
        verbose_name_plural = 'API Deprecation Usage Logs'
        indexes = [
            models.Index(fields=['deprecation', 'timestamp']),
            models.Index(fields=['client_version']),
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        return f"Usage of {self.deprecation.endpoint_pattern} at {self.timestamp}"


__all__ = ['APIDeprecation', 'APIDeprecationUsage']