"""
NOC Alert Cluster Model for ML-Based Alert Grouping.

Implements industry-standard alert clustering for 70-90% noise reduction.
Target: 10:1 alert-to-cluster ratio for improved signal-to-noise.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel
from ..constants import ALERT_SEVERITIES

__all__ = ['AlertCluster']


class AlertCluster(TenantAwareModel, BaseModel):
    """
    ML-clustered alert group representing single incident.

    Uses cosine similarity on 9 features. Target: 10:1 alert-to-cluster ratio.
    Similarity >=0.75: joins cluster, >=0.9: auto-suppressed.
    Business impact: 70-90% alert volume reduction.
    """

    SEVERITY_CHOICES = ALERT_SEVERITIES
    CLUSTERING_METHOD_CHOICES = [
        ('cosine_similarity', 'Cosine Similarity'),
        ('xgboost_similarity', 'XGBoost Similarity'),
        ('manual', 'Manual Grouping'),
    ]

    cluster_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("Cluster ID")
    )
    cluster_signature = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name=_("Cluster Signature"),
        help_text=_("ML-generated signature for cluster identification")
    )

    # Primary alert is the first alert that created this cluster
    primary_alert = models.ForeignKey(
        'NOCAlertEvent',
        on_delete=models.CASCADE,
        related_name='primary_for_cluster',
        verbose_name=_("Primary Alert")
    )
    # Related alerts are all alerts in this cluster (including primary)
    related_alerts = models.ManyToManyField(
        'NOCAlertEvent',
        related_name='alert_clusters',
        verbose_name=_("Related Alerts")
    )

    # ML clustering metadata
    cluster_confidence = models.FloatField(
        default=0.0,
        verbose_name=_("Cluster Confidence"),
        help_text=_("0-1.0 confidence score for cluster quality")
    )
    cluster_method = models.CharField(
        max_length=50,
        choices=CLUSTERING_METHOD_CHOICES,
        default='cosine_similarity',
        verbose_name=_("Clustering Method")
    )
    feature_vector = models.JSONField(
        default=dict,
        verbose_name=_("Feature Vector"),
        help_text=_("Clustering features used for similarity calculation")
    )

    # Cluster characteristics
    combined_severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        verbose_name=_("Combined Severity"),
        help_text=_("Maximum severity from all alerts in cluster")
    )
    affected_sites = models.JSONField(
        default=list,
        verbose_name=_("Affected Sites"),
        help_text=_("List of site IDs affected by this cluster")
    )
    affected_people = models.JSONField(
        default=list,
        verbose_name=_("Affected People"),
        help_text=_("List of person IDs affected by this cluster")
    )
    alert_types_in_cluster = models.JSONField(
        default=list,
        verbose_name=_("Alert Types"),
        help_text=_("List of alert types present in this cluster")
    )

    # Lifecycle tracking
    first_alert_at = models.DateTimeField(
        db_index=True,
        verbose_name=_("First Alert Time"),
        help_text=_("Timestamp of first alert in cluster")
    )
    last_alert_at = models.DateTimeField(
        verbose_name=_("Last Alert Time"),
        help_text=_("Timestamp of most recent alert in cluster")
    )
    alert_count = models.IntegerField(
        default=1,
        verbose_name=_("Alert Count"),
        help_text=_("Total number of alerts in cluster")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether cluster is still accepting new alerts")
    )

    # Auto-suppression tracking
    suppressed_alert_count = models.IntegerField(
        default=0,
        verbose_name=_("Suppressed Alert Count"),
        help_text=_("Number of alerts auto-suppressed (similarity >0.9)")
    )

    class Meta:
        db_table = 'noc_alert_cluster'
        verbose_name = _("NOC Alert Cluster")
        verbose_name_plural = _("NOC Alert Clusters")
        indexes = [
            models.Index(
                fields=['tenant', 'is_active', '-last_alert_at'],
                name='noc_cluster_active'
            ),
            models.Index(
                fields=['cluster_signature'],
                name='noc_cluster_signature'
            ),
            models.Index(
                fields=['tenant', '-cdtz'],
                name='noc_cluster_tenant'
            ),
        ]
        ordering = ['-last_alert_at']

    def __str__(self) -> str:
        return f"Cluster {self.cluster_signature} ({self.alert_count} alerts)"
