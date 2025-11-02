"""
NOC Alert Clustering Service for ML-Based Alert Grouping.

Implements industry-standard alert clustering using cosine similarity
for 70-90% noise reduction. Target: 10:1 alert-to-cluster ratio.
Follows .claude/rules.md Rule #8 (methods <50 lines), Rule #11 (specific exceptions).
"""

import hashlib
import logging
from datetime import timedelta
from typing import Dict, Any, Tuple, Optional, List
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.utils_new.db_utils import get_current_db_name
from ..models import NOCAlertEvent
from ..models.alert_cluster import AlertCluster
from ..constants import ALERT_TYPES

__all__ = ['AlertClusteringService']

logger = logging.getLogger('noc.clustering')


class AlertClusteringService:
    """
    ML-based alert clustering for noise reduction.

    Uses cosine similarity scoring to cluster related alerts.
    Industry target: 70-90% noise reduction, 10:1 alert-to-cluster ratio.
    """

    # Clustering configuration
    CLUSTERING_WINDOW_MINUTES = 30
    SIMILARITY_THRESHOLD = 0.75  # Minimum similarity to join cluster
    AUTO_SUPPRESS_THRESHOLD = 0.9  # Minimum similarity to auto-suppress
    MAX_ACTIVE_CLUSTERS = 1000  # Prevent unbounded memory growth

    # Severity scoring for priority calculation
    SEVERITY_SCORES = {
        'INFO': 1,
        'LOW': 2,
        'MEDIUM': 3,
        'HIGH': 4,
        'CRITICAL': 5,
    }

    @classmethod
    def cluster_alert(cls, new_alert: NOCAlertEvent) -> Tuple[AlertCluster, bool]:
        """
        Find or create cluster for new alert.

        Args:
            new_alert: NOCAlertEvent instance to cluster

        Returns:
            Tuple of (cluster, created) where created is True if new cluster

        Raises:
            DatabaseError: If database operation fails
        """
        features = cls._extract_features(new_alert)
        cluster_signature = cls._generate_signature(features)

        cutoff = timezone.now() - timedelta(minutes=cls.CLUSTERING_WINDOW_MINUTES)
        active_clusters = AlertCluster.objects.filter(
            tenant=new_alert.tenant,
            is_active=True,
            last_alert_at__gte=cutoff
        ).prefetch_related('related_alerts')[:cls.MAX_ACTIVE_CLUSTERS]

        best_cluster, best_score = cls._find_best_cluster(features, active_clusters)

        try:
            with transaction.atomic(using=get_current_db_name()):
                if best_cluster and best_score >= cls.SIMILARITY_THRESHOLD:
                    cls._add_alert_to_cluster(new_alert, best_cluster, best_score)
                    return best_cluster, False
                else:
                    new_cluster = cls._create_new_cluster(new_alert, features, cluster_signature)
                    return new_cluster, True
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error clustering alert {new_alert.id}", extra={'error': str(e)}, exc_info=True)
            raise

    @classmethod
    def _extract_features(cls, alert: NOCAlertEvent) -> Dict[str, Any]:
        """
        Extract 9 clustering features from alert.

        Features:
        1. alert_type_encoded: One-hot encoded alert type
        2. entity_type_encoded: One-hot encoded entity
        3. site_id: Affected site
        4. severity_score: CRITICAL=5, HIGH=4, etc.
        5. hour_of_day: Temporal feature (0-23)
        6. day_of_week: Weekly patterns (0-6)
        7. correlation_id_hash: Existing correlation
        8. time_since_last_alert: Recurrence speed (seconds)
        9. affected_entity_count: Blast radius
        """
        created_time = alert.cdtz if hasattr(alert, 'cdtz') else timezone.now()

        features = {
            'alert_type': alert.alert_type,
            'alert_type_encoded': cls._encode_alert_type(alert.alert_type),
            'entity_type': alert.entity_type,
            'entity_type_encoded': hash(alert.entity_type) % 1000,
            'site_id': alert.bu.id if alert.bu else 0,
            'severity_score': cls.SEVERITY_SCORES.get(alert.severity, 3),
            'hour_of_day': created_time.hour,
            'day_of_week': created_time.weekday(),
            'correlation_id_hash': hash(str(alert.correlation_id)) % 1000 if alert.correlation_id else 0,
            'time_since_last_alert': 0,  # Calculated during clustering
            'affected_entity_count': 1,
        }

        return features

    @classmethod
    def _encode_alert_type(cls, alert_type: str) -> int:
        """One-hot encode alert type into integer."""
        alert_types = list(ALERT_TYPES.keys())
        try:
            return alert_types.index(alert_type)
        except ValueError:
            return len(alert_types)  # Unknown type

    @classmethod
    def _generate_signature(cls, features: Dict[str, Any]) -> str:
        """Generate deterministic signature from features."""
        key_components = [
            features['alert_type'],
            str(features['entity_type']),
            str(features['site_id']),
            str(features['severity_score']),
        ]
        signature = ':'.join(key_components)
        return hashlib.md5(signature.encode()).hexdigest()[:16]

    @classmethod
    def _find_best_cluster(cls, features: Dict[str, Any], clusters) -> Tuple[Optional[AlertCluster], float]:
        """Find cluster with highest similarity score."""
        best_cluster = None
        best_score = 0.0

        for cluster in clusters:
            similarity = cls._calculate_similarity(features, cluster.feature_vector)
            if similarity > best_score:
                best_cluster = cluster
                best_score = similarity

        logger.debug(f"Best cluster similarity: {best_score:.3f}")
        return best_cluster, best_score

    @classmethod
    def _calculate_similarity(cls, features1: Dict[str, Any], features2: Dict[str, Any]) -> float:
        """
        Calculate cosine similarity between feature vectors.

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Extract comparable numeric features
        vec1 = cls._to_vector(features1)
        vec2 = cls._to_vector(features2)

        # Cosine similarity: dot(A,B) / (||A|| * ||B||)
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    @classmethod
    def _to_vector(cls, features: Dict[str, Any]) -> List[float]:
        """Convert feature dict to numeric vector."""
        return [
            float(features.get('alert_type_encoded', 0)),
            float(features.get('entity_type_encoded', 0)),
            float(features.get('site_id', 0)),
            float(features.get('severity_score', 0)),
            float(features.get('hour_of_day', 0)),
            float(features.get('day_of_week', 0)),
            float(features.get('correlation_id_hash', 0)),
            float(features.get('time_since_last_alert', 0)) / 3600,  # Normalize to hours
            float(features.get('affected_entity_count', 0)),
        ]

    @classmethod
    def _add_alert_to_cluster(cls, alert: NOCAlertEvent, cluster: AlertCluster, confidence: float):
        """Add alert to existing cluster and suppress if duplicate."""
        cluster.related_alerts.add(alert)
        cluster.last_alert_at = alert.cdtz if hasattr(alert, 'cdtz') else timezone.now()
        cluster.alert_count += 1

        # Auto-suppress if very similar (confidence > 0.9)
        if confidence >= cls.AUTO_SUPPRESS_THRESHOLD:
            alert.status = 'SUPPRESSED'
            alert.metadata = alert.metadata or {}
            alert.metadata['suppression_reason'] = f'Clustered with {cluster.primary_alert.id}'
            alert.metadata['cluster_similarity'] = round(confidence, 3)
            alert.save(update_fields=['status', 'metadata'])
            cluster.suppressed_alert_count += 1
            logger.info(f"Alert {alert.id} auto-suppressed (similarity: {confidence:.3f})")

        # Update cluster severity to max
        if cls._severity_score(alert.severity) > cls._severity_score(cluster.combined_severity):
            cluster.combined_severity = alert.severity

        # Update affected resources
        if alert.bu and alert.bu.id not in cluster.affected_sites:
            cluster.affected_sites.append(alert.bu.id)

        cluster.save()
        logger.info(f"Alert {alert.id} added to cluster {cluster.cluster_id} (confidence: {confidence:.3f})")

    @classmethod
    def _create_new_cluster(cls, alert: NOCAlertEvent, features: Dict[str, Any], signature: str) -> AlertCluster:
        """Create new cluster from alert."""
        alert_time = alert.cdtz if hasattr(alert, 'cdtz') else timezone.now()

        cluster = AlertCluster.objects.create(
            tenant=alert.tenant,
            cluster_signature=signature,
            primary_alert=alert,
            cluster_confidence=1.0,
            cluster_method='cosine_similarity',
            feature_vector=features,
            combined_severity=alert.severity,
            affected_sites=[alert.bu.id] if alert.bu else [],
            affected_people=[],
            alert_types_in_cluster=[alert.alert_type],
            first_alert_at=alert_time,
            last_alert_at=alert_time,
            alert_count=1,
            is_active=True,
            suppressed_alert_count=0,
            cuser=alert.cuser,
            muser=alert.muser,
        )
        cluster.related_alerts.add(alert)
        logger.info(f"Created new cluster {cluster.cluster_id} for alert {alert.id}")
        return cluster

    @classmethod
    def _severity_score(cls, severity: str) -> int:
        """Convert severity to numeric score."""
        return cls.SEVERITY_SCORES.get(severity, 3)

    @classmethod
    def deactivate_old_clusters(cls, tenant, hours: int = 4):
        """Deactivate clusters older than specified hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        updated = AlertCluster.objects.filter(
            tenant=tenant,
            is_active=True,
            last_alert_at__lt=cutoff
        ).update(is_active=False)

        logger.info(f"Deactivated {updated} old clusters for tenant {tenant.id}")
        return updated
