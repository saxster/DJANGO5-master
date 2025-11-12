"""
Incident Context Model for Pre-Computed Context Caching.

Stores pre-computed incident context for faster retrieval and analytics.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel

__all__ = ['IncidentContext']


class IncidentContext(TenantAwareModel, BaseModel):
    """
    Pre-computed incident context for faster retrieval.

    Stores enrichment context with TTL for cache expiration.
    Enables historical context analysis and trend identification.
    """

    incident = models.OneToOneField(
        'noc.NOCIncident',
        on_delete=models.CASCADE,
        related_name='enrichment_context',
        verbose_name=_("Incident")
    )

    context_data = models.JSONField(
        verbose_name=_("Context Data"),
        help_text=_("Enriched context with 5 categories")
    )

    enriched_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Enriched At")
    )

    cache_expires_at = models.DateTimeField(
        db_index=True,
        verbose_name=_("Cache Expires At"),
        help_text=_("When this cached context expires")
    )

    # Context statistics for analytics
    related_alerts_count = models.IntegerField(
        default=0,
        verbose_name=_("Related Alerts Count")
    )
    recent_changes_count = models.IntegerField(
        default=0,
        verbose_name=_("Recent Changes Count")
    )
    historical_incidents_count = models.IntegerField(
        default=0,
        verbose_name=_("Historical Incidents Count")
    )
    affected_sites_count = models.IntegerField(
        default=0,
        verbose_name=_("Affected Sites Count")
    )
    affected_people_count = models.IntegerField(
        default=0,
        verbose_name=_("Affected People Count")
    )

    class Meta:
        db_table = 'noc_incident_context'
        verbose_name = _("Incident Context")
        verbose_name_plural = _("Incident Contexts")
        indexes = [
            models.Index(fields=['tenant', 'cache_expires_at'], name='noc_ctx_tenant_exp'),
            models.Index(fields=['incident'], name='noc_ctx_incident'),
        ]
        ordering = ['-enriched_at']

    def __str__(self) -> str:
        return f"Context for Incident #{self.incident_id} (enriched {self.enriched_at})"

    def save(self, *args, **kwargs):
        """Set cache expiration on creation."""
        if not self.cache_expires_at:
            self.cache_expires_at = timezone.now() + timedelta(minutes=5)

        # Update statistics from context_data
        if self.context_data:
            self.related_alerts_count = len(self.context_data.get('related_alerts', []))
            self.recent_changes_count = len(self.context_data.get('recent_changes', []))
            self.historical_incidents_count = len(
                self.context_data.get('historical_incidents', [])
            )

            resources = self.context_data.get('affected_resources', {})
            self.affected_sites_count = len(resources.get('sites', []))
            self.affected_people_count = len(resources.get('people', []))

        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        """Check if context cache has expired."""
        return timezone.now() > self.cache_expires_at

    def refresh_if_expired(self):
        """Refresh context if cache has expired."""
        if self.is_expired:
            from apps.noc.services.incident_context_service import IncidentContextService
            context = IncidentContextService.enrich_incident(self.incident)
            self.context_data = context
            self.enriched_at = timezone.now()
            self.cache_expires_at = timezone.now() + timedelta(minutes=5)
            self.save()
