"""
Tests for Alert Priority Scoring (Enhancement #7).

Covers:
- Feature extraction
- Priority calculation (heuristic)
- Model training (if data available)
- Dashboard sorting by priority
- VIP client priority boost
- Business hours boost
- Integration with AlertCorrelationService
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone
from django.test import TestCase
from apps.noc.models import NOCAlertEvent
from apps.noc.services.alert_priority_scorer import AlertPriorityScorer
from apps.noc.services.correlation_service import AlertCorrelationService
from apps.noc.ml.priority_model_trainer import PriorityModelTrainer
from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt
from apps.peoples.models import People


@pytest.mark.django_db
class TestAlertPriorityScorer(TestCase):
    """Test AlertPriorityScorer service."""

    def setUp(self):
        """Create test data."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            tenantname='Test Tenant',
            subdomain='test'
        )

        # Create client (business unit)
        self.client = Bt.objects.create(
            tenant=self.tenant,
            buname='Test Client',
            bucode='TC001',
            preferences={'tier': 'STANDARD'}
        )

        self.vip_client = Bt.objects.create(
            tenant=self.tenant,
            buname='VIP Client',
            bucode='VIP001',
            preferences={'tier': 'VIP'}
        )

        # Create business unit (site)
        self.site = Bt.objects.create(
            tenant=self.tenant,
            buname='Test Site',
            bucode='TS001',
            client=self.client
        )

    def test_feature_extraction(self):
        """Test feature extraction from alert."""
        alert = NOCAlertEvent.objects.create(
            tenant=self.tenant,
            client=self.client,
            bu=self.site,
            alert_type='ATTENDANCE_ANOMALY',
            severity='HIGH',
            message='Test alert',
            entity_type='person',
            entity_id=1,
            dedup_key='test_key_001',
        )

        features = AlertPriorityScorer._extract_features(alert)

        # Verify all 9 features extracted
        assert 'severity_level' in features
        assert 'affected_sites_count' in features
        assert 'business_hours' in features
        assert 'client_tier' in features
        assert 'historical_impact' in features
        assert 'recurrence_rate' in features
        assert 'avg_resolution_time' in features
        assert 'current_site_workload' in features
        assert 'on_call_availability' in features

        # Verify severity mapping
        assert features['severity_level'] == 4  # HIGH = 4

        # Verify site count
        assert features['affected_sites_count'] == 1

        # Verify client tier
        assert features['client_tier'] == 3  # STANDARD = 3

    def test_heuristic_priority_calculation(self):
        """Test heuristic priority scoring (fallback)."""
        alert = NOCAlertEvent.objects.create(
            tenant=self.tenant,
            client=self.client,
            bu=self.site,
            alert_type='CRITICAL_SYSTEM',
            severity='CRITICAL',
            message='Critical system alert',
            entity_type='system',
            entity_id=1,
            dedup_key='test_key_002',
        )

        priority_score, features = AlertPriorityScorer.calculate_priority(alert)

        # Priority should be 0-100
        assert 0 <= priority_score <= 100

        # CRITICAL severity should result in higher priority
        assert priority_score > 50

        # Features should be stored
        assert len(features) == 9

    def test_vip_client_priority_boost(self):
        """Test VIP clients get higher priority than standard clients."""
        # Standard client alert
        standard_alert = NOCAlertEvent.objects.create(
            tenant=self.tenant,
            client=self.client,
            alert_type='ATTENDANCE_ANOMALY',
            severity='MEDIUM',
            message='Standard client alert',
            entity_type='person',
            entity_id=1,
            dedup_key='test_key_003',
        )

        # VIP client alert
        vip_alert = NOCAlertEvent.objects.create(
            tenant=self.tenant,
            client=self.vip_client,
            alert_type='ATTENDANCE_ANOMALY',
            severity='MEDIUM',
            message='VIP client alert',
            entity_type='person',
            entity_id=2,
            dedup_key='test_key_004',
        )

        standard_priority, _ = AlertPriorityScorer.calculate_priority(standard_alert)
        vip_priority, _ = AlertPriorityScorer.calculate_priority(vip_alert)

        # VIP should have higher priority
        assert vip_priority > standard_priority

    @patch('apps.noc.services.alert_priority_scorer.timezone')
    def test_business_hours_boost(self, mock_timezone):
        """Test alerts during business hours get priority boost."""
        # Mock business hours (10 AM)
        business_hour = MagicMock()
        business_hour.hour = 10
        mock_timezone.now.return_value = business_hour

        alert = NOCAlertEvent.objects.create(
            tenant=self.tenant,
            client=self.client,
            alert_type='ATTENDANCE_ANOMALY',
            severity='MEDIUM',
            message='Business hours alert',
            entity_type='person',
            entity_id=1,
            dedup_key='test_key_005',
        )

        features_business = AlertPriorityScorer._extract_features(alert)

        # Mock non-business hours (11 PM)
        non_business_hour = MagicMock()
        non_business_hour.hour = 23
        mock_timezone.now.return_value = non_business_hour

        features_non_business = AlertPriorityScorer._extract_features(alert)

        # Business hours should have flag set
        assert features_business['business_hours'] == 1
        assert features_non_business['business_hours'] == 0

    def test_site_workload_calculation(self):
        """Test current site workload feature extraction."""
        # Create multiple active alerts at same site
        for i in range(3):
            NOCAlertEvent.objects.create(
                tenant=self.tenant,
                client=self.client,
                bu=self.site,
                alert_type='ATTENDANCE_ANOMALY',
                severity='MEDIUM',
                message=f'Alert {i}',
                entity_type='person',
                entity_id=i,
                dedup_key=f'test_key_workload_{i}',
                status='NEW'
            )

        # New alert at same site
        new_alert = NOCAlertEvent.objects.create(
            tenant=self.tenant,
            client=self.client,
            bu=self.site,
            alert_type='ATTENDANCE_ANOMALY',
            severity='HIGH',
            message='New alert',
            entity_type='person',
            entity_id=100,
            dedup_key='test_key_workload_new',
        )

        features = AlertPriorityScorer._extract_features(new_alert)

        # Should count the 3 existing alerts (not the new one)
        assert features['current_site_workload'] == 3

    def test_integration_with_correlation_service(self):
        """Test priority is calculated when alert created via correlation service."""
        alert_data = {
            'tenant': self.tenant,
            'client': self.client,
            'bu': self.site,
            'alert_type': 'ATTENDANCE_ANOMALY',
            'severity': 'HIGH',
            'message': 'Integration test alert',
            'entity_type': 'person',
            'entity_id': 999,
            'metadata': {},
        }

        alert = AlertCorrelationService.process_alert(alert_data)

        # Alert should have priority calculated
        assert alert is not None
        assert alert.calculated_priority is not None
        assert 0 <= alert.calculated_priority <= 100
        assert alert.priority_features is not None
        assert len(alert.priority_features) == 9

    def test_dashboard_sorting_by_priority(self):
        """Test alerts can be sorted by priority for dashboard display."""
        # Create alerts with different severities
        alerts = []
        for severity, score in [('CRITICAL', 5), ('HIGH', 4), ('MEDIUM', 3), ('LOW', 2)]:
            alert = NOCAlertEvent.objects.create(
                tenant=self.tenant,
                client=self.client,
                alert_type='ATTENDANCE_ANOMALY',
                severity=severity,
                message=f'{severity} alert',
                entity_type='person',
                entity_id=score,
                dedup_key=f'test_key_sort_{score}',
            )
            priority, features = AlertPriorityScorer.calculate_priority(alert)
            alert.calculated_priority = priority
            alert.priority_features = features
            alert.save()
            alerts.append(alert)

        # Query alerts sorted by priority (descending)
        sorted_alerts = NOCAlertEvent.objects.filter(
            tenant=self.tenant
        ).order_by('-calculated_priority', '-cdtz')

        # Critical should be first
        assert sorted_alerts[0].severity == 'CRITICAL'
        
        # Priorities should be descending
        priorities = [a.calculated_priority for a in sorted_alerts]
        assert priorities == sorted(priorities, reverse=True)

    def test_historical_impact_calculation(self):
        """Test historical impact feature based on similar alerts."""
        # Create some resolved alerts with resolution times
        for i in range(5):
            resolved_alert = NOCAlertEvent.objects.create(
                tenant=self.tenant,
                client=self.client,
                alert_type='ATTENDANCE_ANOMALY',
                severity='MEDIUM',
                message=f'Resolved alert {i}',
                entity_type='person',
                entity_id=i,
                dedup_key=f'resolved_{i}',
                status='RESOLVED',
                resolved_at=timezone.now(),
                time_to_resolve=timedelta(minutes=30 + i * 10)
            )

        # New alert of same type
        new_alert = NOCAlertEvent.objects.create(
            tenant=self.tenant,
            client=self.client,
            alert_type='ATTENDANCE_ANOMALY',
            severity='MEDIUM',
            message='New alert for impact test',
            entity_type='person',
            entity_id=100,
            dedup_key='impact_test',
        )

        features = AlertPriorityScorer._extract_features(new_alert)

        # Historical impact should be calculated from resolved alerts
        # Average: (30 + 40 + 50 + 60 + 70) / 5 = 50 minutes
        assert features['historical_impact'] > 0
        assert 40 <= features['historical_impact'] <= 60  # Allow some variance


@pytest.mark.django_db
class TestPriorityModelTrainer(TestCase):
    """Test ML model training."""

    def setUp(self):
        """Create test data."""
        self.tenant = Tenant.objects.create(
            tenantname='Test Tenant',
            subdomain='test'
        )

        self.client = Bt.objects.create(
            tenant=self.tenant,
            buname='Test Client',
            bucode='TC001',
        )

    def test_insufficient_data_raises_error(self):
        """Test training fails with insufficient data."""
        # Create only 10 alerts (less than MIN_TRAINING_SAMPLES)
        for i in range(10):
            NOCAlertEvent.objects.create(
                tenant=self.tenant,
                client=self.client,
                alert_type='ATTENDANCE_ANOMALY',
                severity='MEDIUM',
                message=f'Alert {i}',
                entity_type='person',
                entity_id=i,
                dedup_key=f'train_test_{i}',
                status='RESOLVED',
                resolved_at=timezone.now(),
                time_to_resolve=timedelta(minutes=30)
            )

        with pytest.raises(ValueError, match='Insufficient training data'):
            PriorityModelTrainer.train_model()
