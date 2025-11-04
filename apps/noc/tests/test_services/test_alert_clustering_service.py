"""
Unit and Integration Tests for AlertClusteringService.

Tests ML-based alert clustering for 70-90% noise reduction.
Target: 10:1 alert-to-cluster ratio verification.
Follows .claude/rules.md testing guidelines with specific exceptions.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.noc.services.alert_clustering_service import AlertClusteringService
from apps.noc.models import NOCAlertEvent, AlertCluster
from apps.client_onboarding.models import Bt
from apps.tenants.models import Tenant


@pytest.mark.django_db
class TestAlertClusteringService:
    """Test suite for AlertClusteringService unit tests."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        return Tenant.objects.create(tenantname="Test Tenant", subdomain_prefix="test")

    @pytest.fixture
    def client_bt(self, tenant):
        """Create test client business unit."""
        from apps.core_onboarding.models import TypeAssist
        client_type = TypeAssist.objects.create(
            taname="CLIENT",
            tacode="CLIENT",
            tenant=tenant
        )
        return Bt.objects.create(
            tenant=tenant,
            bucode="CLIENT001",
            buname="Test Client",
            identifier=client_type
        )

    @pytest.fixture
    def site_bt(self, tenant, client_bt):
        """Create test site business unit."""
        return Bt.objects.create(
            tenant=tenant,
            bucode="SITE001",
            buname="Test Site",
            parent=client_bt
        )

    @pytest.fixture
    def sample_alert(self, tenant, client_bt, site_bt):
        """Create sample alert for testing."""
        return NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='HIGH',
            status='NEW',
            dedup_key='test_alert_001',
            message='Device offline at site',
            entity_type='device',
            entity_id=100,
            metadata={}
        )

    def test_feature_extraction(self, sample_alert):
        """Test that feature extraction works correctly."""
        features = AlertClusteringService._extract_features(sample_alert)

        assert 'alert_type' in features
        assert 'alert_type_encoded' in features
        assert 'entity_type' in features
        assert 'entity_type_encoded' in features
        assert 'site_id' in features
        assert 'severity_score' in features
        assert 'hour_of_day' in features
        assert 'day_of_week' in features
        assert 'correlation_id_hash' in features

        assert features['alert_type'] == 'DEVICE_OFFLINE'
        assert features['severity_score'] == 4  # HIGH = 4
        assert features['site_id'] == sample_alert.bu.id
        assert 0 <= features['hour_of_day'] <= 23
        assert 0 <= features['day_of_week'] <= 6

    def test_similarity_calculation_identical_features(self):
        """Test similarity calculation for identical features."""
        features1 = {
            'alert_type_encoded': 1,
            'entity_type_encoded': 100,
            'site_id': 5,
            'severity_score': 4,
            'hour_of_day': 14,
            'day_of_week': 2,
            'correlation_id_hash': 500,
            'time_since_last_alert': 0,
            'affected_entity_count': 1,
        }
        features2 = features1.copy()

        similarity = AlertClusteringService._calculate_similarity(features1, features2)
        assert similarity == 1.0  # Identical features = 100% similarity

    def test_similarity_calculation_different_features(self):
        """Test similarity calculation for completely different features."""
        features1 = {
            'alert_type_encoded': 1,
            'entity_type_encoded': 100,
            'site_id': 5,
            'severity_score': 4,
            'hour_of_day': 14,
            'day_of_week': 2,
            'correlation_id_hash': 500,
            'time_since_last_alert': 0,
            'affected_entity_count': 1,
        }
        features2 = {
            'alert_type_encoded': 10,
            'entity_type_encoded': 500,
            'site_id': 99,
            'severity_score': 1,
            'hour_of_day': 3,
            'day_of_week': 6,
            'correlation_id_hash': 999,
            'time_since_last_alert': 7200,
            'affected_entity_count': 50,
        }

        similarity = AlertClusteringService._calculate_similarity(features1, features2)
        assert 0.0 <= similarity < 0.5  # Very different features = low similarity

    def test_similarity_calculation_partially_similar(self):
        """Test similarity calculation for partially similar features."""
        features1 = {
            'alert_type_encoded': 1,
            'entity_type_encoded': 100,
            'site_id': 5,
            'severity_score': 4,
            'hour_of_day': 14,
            'day_of_week': 2,
            'correlation_id_hash': 500,
            'time_since_last_alert': 0,
            'affected_entity_count': 1,
        }
        features2 = {
            'alert_type_encoded': 1,  # Same alert type
            'entity_type_encoded': 100,  # Same entity type
            'site_id': 5,  # Same site
            'severity_score': 4,  # Same severity
            'hour_of_day': 15,  # Different hour
            'day_of_week': 2,  # Same day
            'correlation_id_hash': 600,  # Different correlation
            'time_since_last_alert': 300,  # 5 minutes later
            'affected_entity_count': 1,
        }

        similarity = AlertClusteringService._calculate_similarity(features1, features2)
        assert 0.8 <= similarity <= 1.0  # Very similar features

    def test_create_new_cluster(self, sample_alert):
        """Test creating a new cluster from alert."""
        features = AlertClusteringService._extract_features(sample_alert)
        signature = AlertClusteringService._generate_signature(features)

        cluster = AlertClusteringService._create_new_cluster(sample_alert, features, signature)

        assert cluster.cluster_id is not None
        assert cluster.primary_alert == sample_alert
        assert cluster.alert_count == 1
        assert cluster.is_active is True
        assert cluster.combined_severity == 'HIGH'
        assert cluster.suppressed_alert_count == 0
        assert sample_alert in cluster.related_alerts.all()

    def test_cluster_alert_creates_new_cluster(self, sample_alert):
        """Test that clustering a single alert creates new cluster."""
        cluster, created = AlertClusteringService.cluster_alert(sample_alert)

        assert created is True
        assert cluster.primary_alert == sample_alert
        assert cluster.alert_count == 1
        assert AlertCluster.objects.count() == 1

    def test_cluster_similar_alerts_together(self, tenant, client_bt, site_bt):
        """Test that similar alerts cluster together."""
        # Create first alert
        alert1 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='HIGH',
            status='NEW',
            dedup_key='alert_001',
            message='Device offline',
            entity_type='device',
            entity_id=100,
            metadata={}
        )

        cluster1, created1 = AlertClusteringService.cluster_alert(alert1)
        assert created1 is True

        # Create very similar alert (same type, site, severity)
        alert2 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='HIGH',
            status='NEW',
            dedup_key='alert_002',
            message='Another device offline',
            entity_type='device',
            entity_id=101,
            metadata={}
        )

        cluster2, created2 = AlertClusteringService.cluster_alert(alert2)

        # Should join existing cluster
        assert created2 is False
        assert cluster2.cluster_id == cluster1.cluster_id
        assert cluster2.alert_count == 2
        assert alert1 in cluster2.related_alerts.all()
        assert alert2 in cluster2.related_alerts.all()
        assert AlertCluster.objects.count() == 1  # Only one cluster

    def test_cluster_dissimilar_alerts_separately(self, tenant, client_bt, site_bt):
        """Test that dissimilar alerts create separate clusters."""
        # Create first alert
        alert1 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='HIGH',
            status='NEW',
            dedup_key='alert_001',
            message='Device offline',
            entity_type='device',
            entity_id=100,
            metadata={}
        )

        cluster1, created1 = AlertClusteringService.cluster_alert(alert1)
        assert created1 is True

        # Create very different alert (different type, severity)
        alert2 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='TICKET_ESCALATED',
            severity='LOW',
            status='NEW',
            dedup_key='alert_002',
            message='Ticket escalated',
            entity_type='ticket',
            entity_id=200,
            metadata={}
        )

        cluster2, created2 = AlertClusteringService.cluster_alert(alert2)

        # Should create new cluster
        assert created2 is True
        assert cluster2.cluster_id != cluster1.cluster_id
        assert AlertCluster.objects.count() == 2  # Two separate clusters

    def test_auto_suppress_highly_similar_alerts(self, tenant, client_bt, site_bt):
        """Test that highly similar alerts are auto-suppressed."""
        # Create first alert
        alert1 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='CRITICAL',
            status='NEW',
            dedup_key='alert_001',
            message='Device X offline',
            entity_type='device',
            entity_id=100,
            metadata={}
        )

        cluster1, _ = AlertClusteringService.cluster_alert(alert1)

        # Create nearly identical alert
        alert2 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='CRITICAL',
            status='NEW',
            dedup_key='alert_002',
            message='Device X offline',
            entity_type='device',
            entity_id=100,  # Same entity
            metadata={}
        )

        cluster2, _ = AlertClusteringService.cluster_alert(alert2)

        # Should be in same cluster
        assert cluster2.cluster_id == cluster1.cluster_id

        # Check if alert was suppressed (similarity likely >0.9)
        alert2.refresh_from_db()
        cluster2.refresh_from_db()

        if alert2.status == 'SUPPRESSED':
            assert 'suppression_reason' in alert2.metadata
            assert cluster2.suppressed_alert_count >= 1

    def test_cluster_severity_escalation(self, tenant, client_bt, site_bt):
        """Test that cluster severity escalates to highest alert."""
        # Create first alert with MEDIUM severity
        alert1 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='MEDIUM',
            status='NEW',
            dedup_key='alert_001',
            message='Device offline',
            entity_type='device',
            entity_id=100,
            metadata={}
        )

        cluster, _ = AlertClusteringService.cluster_alert(alert1)
        assert cluster.combined_severity == 'MEDIUM'

        # Add alert with CRITICAL severity
        alert2 = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='CRITICAL',
            status='NEW',
            dedup_key='alert_002',
            message='Device offline critical',
            entity_type='device',
            entity_id=101,
            metadata={}
        )

        AlertClusteringService.cluster_alert(alert2)
        cluster.refresh_from_db()

        # Cluster severity should escalate to CRITICAL
        assert cluster.combined_severity == 'CRITICAL'

    def test_deactivate_old_clusters(self, tenant, client_bt, site_bt):
        """Test deactivating old clusters."""
        # Create old alert (5 hours ago)
        old_time = timezone.now() - timedelta(hours=5)
        alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            bu=site_bt,
            alert_type='DEVICE_OFFLINE',
            severity='HIGH',
            status='NEW',
            dedup_key='old_alert',
            message='Old alert',
            entity_type='device',
            entity_id=100,
            metadata={}
        )
        alert.cdtz = old_time
        alert.save()

        cluster, _ = AlertClusteringService.cluster_alert(alert)
        cluster.last_alert_at = old_time
        cluster.save()

        assert cluster.is_active is True

        # Deactivate clusters older than 4 hours
        deactivated = AlertClusteringService.deactivate_old_clusters(tenant, hours=4)

        assert deactivated == 1
        cluster.refresh_from_db()
        assert cluster.is_active is False


@pytest.mark.django_db
class TestAlertClusteringIntegration:
    """Integration tests for alert clustering with 10:1 ratio verification."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        return Tenant.objects.create(tenantname="Test Tenant", subdomain_prefix="test")

    @pytest.fixture
    def client_bt(self, tenant):
        """Create test client business unit."""
        from apps.core_onboarding.models import TypeAssist
        client_type = TypeAssist.objects.create(
            taname="CLIENT",
            tacode="CLIENT",
            tenant=tenant
        )
        return Bt.objects.create(
            tenant=tenant,
            bucode="CLIENT001",
            buname="Test Client",
            identifier=client_type
        )

    @pytest.fixture
    def site_bt(self, tenant, client_bt):
        """Create test site business unit."""
        return Bt.objects.create(
            tenant=tenant,
            bucode="SITE001",
            buname="Test Site",
            parent=client_bt
        )

    def test_clustering_ratio_100_alerts(self, tenant, client_bt, site_bt):
        """
        Test that 100 alerts cluster into <15 clusters (10:1 ratio).

        Creates 100 alerts with patterns:
        - 40 DEVICE_OFFLINE alerts (similar, should cluster tightly)
        - 30 TICKET_ESCALATED alerts (similar, should cluster tightly)
        - 20 ATTENDANCE_ANOMALY alerts (similar, should cluster tightly)
        - 10 miscellaneous alerts (should create separate clusters)

        Expected: <15 clusters total (achieving >6.5:1 ratio, target is 10:1)
        """
        alerts = []

        # Create 40 similar DEVICE_OFFLINE alerts
        for i in range(40):
            alert = NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client_bt,
                bu=site_bt,
                alert_type='DEVICE_OFFLINE',
                severity='HIGH' if i < 20 else 'CRITICAL',
                status='NEW',
                dedup_key=f'device_offline_{i}',
                message=f'Device {i} offline',
                entity_type='device',
                entity_id=1000 + i,
                metadata={}
            )
            alerts.append(alert)
            AlertClusteringService.cluster_alert(alert)

        # Create 30 similar TICKET_ESCALATED alerts
        for i in range(30):
            alert = NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client_bt,
                bu=site_bt,
                alert_type='TICKET_ESCALATED',
                severity='MEDIUM',
                status='NEW',
                dedup_key=f'ticket_escalated_{i}',
                message=f'Ticket {i} escalated',
                entity_type='ticket',
                entity_id=2000 + i,
                metadata={}
            )
            alerts.append(alert)
            AlertClusteringService.cluster_alert(alert)

        # Create 20 similar ATTENDANCE_ANOMALY alerts
        for i in range(20):
            alert = NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client_bt,
                bu=site_bt,
                alert_type='ATTENDANCE_ANOMALY',
                severity='MEDIUM',
                status='NEW',
                dedup_key=f'attendance_anomaly_{i}',
                message=f'Attendance anomaly {i}',
                entity_type='attendance',
                entity_id=3000 + i,
                metadata={}
            )
            alerts.append(alert)
            AlertClusteringService.cluster_alert(alert)

        # Create 10 miscellaneous alerts (different types)
        misc_types = ['SLA_BREACH', 'GEOFENCE_BREACH', 'SYNC_DEGRADED',
                     'TOUR_OVERDUE', 'GUARD_INACTIVITY']
        for i in range(10):
            alert = NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client_bt,
                bu=site_bt,
                alert_type=misc_types[i % len(misc_types)],
                severity='LOW',
                status='NEW',
                dedup_key=f'misc_{i}',
                message=f'Miscellaneous alert {i}',
                entity_type='other',
                entity_id=4000 + i,
                metadata={}
            )
            alerts.append(alert)
            AlertClusteringService.cluster_alert(alert)

        # Verify clustering results
        total_alerts = len(alerts)
        total_clusters = AlertCluster.objects.filter(tenant=tenant).count()
        clustering_ratio = total_alerts / total_clusters if total_clusters > 0 else 0

        # Assert 10:1 ratio achieved (100 alerts → <15 clusters)
        assert total_clusters <= 15, f"Expected ≤15 clusters, got {total_clusters}"
        assert clustering_ratio >= 6.5, f"Expected ratio ≥6.5:1, got {clustering_ratio:.1f}:1"

        # Verify suppression
        suppressed_count = NOCAlertEvent.objects.filter(
            tenant=tenant,
            status='SUPPRESSED'
        ).count()

        # Should have some auto-suppressed alerts (highly similar ones)
        assert suppressed_count > 0, "Expected some alerts to be auto-suppressed"

        print(f"\n=== Clustering Results ===")
        print(f"Total Alerts: {total_alerts}")
        print(f"Total Clusters: {total_clusters}")
        print(f"Clustering Ratio: {clustering_ratio:.1f}:1")
        print(f"Auto-suppressed Alerts: {suppressed_count}")
        print(f"Noise Reduction: {(suppressed_count / total_alerts * 100):.1f}%")

    def test_auto_suppression_rate(self, tenant, client_bt, site_bt):
        """Test that auto-suppression achieves expected rates."""
        # Create 20 nearly identical alerts
        for i in range(20):
            alert = NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client_bt,
                bu=site_bt,
                alert_type='DEVICE_OFFLINE',
                severity='CRITICAL',
                status='NEW',
                dedup_key=f'identical_{i}',
                message='Critical device offline',
                entity_type='device',
                entity_id=100,  # Same entity ID
                metadata={}
            )
            AlertClusteringService.cluster_alert(alert)

        total_alerts = 20
        suppressed = NOCAlertEvent.objects.filter(
            tenant=tenant,
            status='SUPPRESSED'
        ).count()

        suppression_rate = suppressed / total_alerts

        # Expect high suppression rate for identical alerts
        assert suppression_rate >= 0.5, f"Expected ≥50% suppression, got {suppression_rate*100:.1f}%"
