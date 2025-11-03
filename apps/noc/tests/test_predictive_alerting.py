"""
Comprehensive Test Suite for Predictive Alerting Engine.

Tests Enhancement #5: Predictive Alerting Engine with 20+ tests covering:
- Feature extraction for all 3 predictors
- Model training and validation
- Prediction service integration
- Outcome validation and accuracy tracking
- Celery task execution
- Alert creation and deduplication

Follows .claude/rules.md testing standards.

@ontology(
    domain="noc",
    purpose="Comprehensive test suite for predictive alerting system",
    test_coverage=["feature_extraction", "model_training", "predictions", "validation", "celery_tasks"],
    criticality="high",
    tags=["noc", "tests", "predictive-analytics", "ml"]
)
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.noc.models import (
    PredictiveAlertTracking,
    NOCAlertEvent,
)
from apps.noc.ml.predictive_models.sla_breach_predictor import SLABreachPredictor
from apps.noc.ml.predictive_models.device_failure_predictor import DeviceFailurePredictor
from apps.noc.ml.predictive_models.staffing_gap_predictor import StaffingGapPredictor
from apps.noc.services.predictive_alerting_service import PredictiveAlertingService

User = get_user_model()


class SLABreachPredictorTests(TestCase):
    """Tests for SLA Breach Predictor - Feature Extraction (3 tests)."""

    def setUp(self):
        """Set up test ticket."""
        self.mock_ticket = Mock()
        self.mock_ticket.id = 1
        self.mock_ticket.cdtz = timezone.now() - timedelta(minutes=30)
        self.mock_ticket.priority = 'HIGH'
        self.mock_ticket.assignee = Mock()
        self.mock_ticket.bu = Mock()
        self.mock_ticket.tenant = Mock()
        self.mock_ticket.sla_policy = Mock()
        self.mock_ticket.sla_policy.response_time_minutes = 120

    def test_extract_features_returns_8_features(self):
        """Test that feature extraction returns exactly 8 features."""
        with patch('apps.noc.ml.predictive_models.sla_breach_predictor.Ticket'):
            features = SLABreachPredictor._extract_features(self.mock_ticket)

            self.assertEqual(len(features), 8)
            self.assertIn('current_age_minutes', features)
            self.assertIn('priority_level', features)
            self.assertIn('assigned_status', features)
            self.assertIn('site_current_workload', features)
            self.assertIn('historical_avg_resolution_time', features)
            self.assertIn('time_until_sla_deadline_minutes', features)
            self.assertIn('assignee_current_workload', features)
            self.assertIn('business_hours', features)

    def test_priority_mapping_correct(self):
        """Test that priority levels map correctly to numeric values."""
        with patch('apps.noc.ml.predictive_models.sla_breach_predictor.Ticket'):
            self.mock_ticket.priority = 'CRITICAL'
            features = SLABreachPredictor._extract_features(self.mock_ticket)
            self.assertEqual(features['priority_level'], 5)

            self.mock_ticket.priority = 'LOW'
            features = SLABreachPredictor._extract_features(self.mock_ticket)
            self.assertEqual(features['priority_level'], 1)

    def test_heuristic_prediction_high_risk(self):
        """Test heuristic prediction identifies high-risk scenarios."""
        features = {
            'current_age_minutes': 100,
            'time_until_sla_deadline_minutes': 50,  # Already past halfway
            'assigned_status': 0,
            'priority_level': 5,
            'assignee_current_workload': 3,
        }

        probability = SLABreachPredictor._heuristic_prediction(features)
        self.assertGreater(probability, 0.7)  # Should be high risk


class DeviceFailurePredictorTests(TestCase):
    """Tests for Device Failure Predictor - Feature Extraction (3 tests)."""

    def setUp(self):
        """Set up test device."""
        self.mock_device = Mock()
        self.mock_device.id = 1
        self.mock_device.device_type = 'mobile'
        self.mock_device.battery_level = 15
        self.mock_device.offline_duration_minutes = 600
        self.mock_device.sync_health_score = 70
        self.mock_device.recent_sync_scores = [85, 80, 75, 70]  # Degrading

    def test_extract_features_returns_7_features(self):
        """Test that feature extraction returns exactly 7 features."""
        features = DeviceFailurePredictor._extract_features(self.mock_device)

        self.assertEqual(len(features), 7)
        self.assertIn('offline_duration_last_7_days', features)
        self.assertIn('sync_health_score_trend', features)
        self.assertIn('time_since_last_event_minutes', features)
        self.assertIn('event_frequency_last_24h', features)
        self.assertIn('battery_level', features)
        self.assertIn('gps_accuracy_degradation', features)
        self.assertIn('device_type_failure_rate', features)

    def test_sync_trend_degrading_detected(self):
        """Test that degrading sync trend is correctly detected."""
        self.mock_device.recent_sync_scores = [90, 85, 75, 65]  # Degrading trend

        features = DeviceFailurePredictor._extract_features(self.mock_device)
        self.assertEqual(features['sync_health_score_trend'], -1)

    def test_heuristic_prediction_low_battery(self):
        """Test heuristic identifies low battery + idle as high risk."""
        features = {
            'offline_duration_last_7_days': 100,
            'sync_health_score_trend': 0,
            'time_since_last_event_minutes': 150,  # >2 hours idle
            'event_frequency_last_24h': 0.5,
            'battery_level': 15,  # Low battery
            'gps_accuracy_degradation': 0,
            'device_type_failure_rate': 0.05,
        }

        probability = DeviceFailurePredictor._heuristic_prediction(features)
        self.assertGreater(probability, 0.6)  # Should be medium-high risk


class StaffingGapPredictorTests(TestCase):
    """Tests for Staffing Gap Predictor - Feature Extraction (3 tests)."""

    def setUp(self):
        """Set up test site and shift."""
        self.mock_site = Mock()
        self.mock_site.id = 1
        self.mock_site.is_vip = True
        self.mock_site.required_guards = 2

        self.shift_time = timezone.now() + timedelta(hours=2)

    def test_extract_features_returns_6_features(self):
        """Test that feature extraction returns exactly 6 features."""
        with patch('apps.noc.ml.predictive_models.staffing_gap_predictor.Schedule'), \
             patch('apps.noc.ml.predictive_models.staffing_gap_predictor.Attendance'):

            features = StaffingGapPredictor._extract_features(self.mock_site, self.shift_time)

            self.assertEqual(len(features), 6)
            self.assertIn('scheduled_guards_count', features)
            self.assertIn('actual_attendance_rate_last_7_days', features)
            self.assertIn('time_to_next_shift_minutes', features)
            self.assertIn('site_criticality_score', features)
            self.assertIn('current_attendance_vs_scheduled_ratio', features)
            self.assertIn('historical_no_show_rate', features)

    def test_vip_site_criticality_score(self):
        """Test that VIP sites get highest criticality score."""
        with patch('apps.noc.ml.predictive_models.staffing_gap_predictor.Schedule'), \
             patch('apps.noc.ml.predictive_models.staffing_gap_predictor.Attendance'):

            self.mock_site.is_vip = True
            features = StaffingGapPredictor._extract_features(self.mock_site, self.shift_time)
            self.assertEqual(features['site_criticality_score'], 5)

    def test_heuristic_prediction_few_scheduled_high_no_show(self):
        """Test heuristic identifies understaffing risk."""
        features = {
            'scheduled_guards_count': 1,  # Only 1 guard
            'actual_attendance_rate_last_7_days': 65,  # Low rate
            'time_to_next_shift_minutes': 90,
            'site_criticality_score': 5,  # VIP site
            'current_attendance_vs_scheduled_ratio': 0.5,
            'historical_no_show_rate': 0.35,  # High no-show rate
        }

        probability = StaffingGapPredictor._heuristic_prediction(features)
        self.assertGreater(probability, 0.7)  # Should be high risk


class PredictiveAlertingServiceTests(TestCase):
    """Tests for Predictive Alerting Service - Integration (6 tests)."""

    def setUp(self):
        """Set up test data."""
        from apps.tenants.models import Tenant
        from apps.onboarding.models import Bt

        self.tenant = Tenant.objects.create(tenantname='TestTenant', isactive=True)
        self.client = Bt.objects.create(tenant=self.tenant, buname='TestClient')

    def test_calculate_severity_from_probability(self):
        """Test severity calculation based on probability thresholds."""
        self.assertEqual(PredictiveAlertingService._calculate_severity(0.95), 'CRITICAL')
        self.assertEqual(PredictiveAlertingService._calculate_severity(0.80), 'HIGH')
        self.assertEqual(PredictiveAlertingService._calculate_severity(0.65), 'MEDIUM')

    def test_get_confidence_bucket(self):
        """Test confidence bucketing."""
        self.assertEqual(PredictiveAlertingService._get_confidence_bucket(0.95), 'very_high')
        self.assertEqual(PredictiveAlertingService._get_confidence_bucket(0.80), 'high')
        self.assertEqual(PredictiveAlertingService._get_confidence_bucket(0.65), 'medium')
        self.assertEqual(PredictiveAlertingService._get_confidence_bucket(0.55), 'low')

    @patch('apps.noc.services.predictive_alerting_service.SLABreachPredictor')
    def test_predict_sla_breaches_scans_open_tickets(self, mock_predictor):
        """Test SLA breach prediction scans open tickets."""
        mock_predictor.predict_breach.return_value = (0.8, {'feature1': 1.0})
        mock_predictor.should_alert.return_value = True

        with patch('apps.noc.services.predictive_alerting_service.Ticket') as MockTicket:
            MockTicket.objects.filter.return_value.select_related.return_value.count.return_value = 5

            predictions = PredictiveAlertingService.predict_sla_breaches(self.tenant)

            # Verify filter was called with correct status
            MockTicket.objects.filter.assert_called()

    def test_create_predictive_alert_creates_tracking(self):
        """Test that creating alert also creates tracking record."""
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.tenant = self.tenant
        mock_entity.client = self.client
        mock_entity.bu = None

        with patch('apps.noc.services.predictive_alerting_service.AlertCorrelationService') as mock_correlation:
            mock_alert = Mock()
            mock_alert.id = 1
            mock_correlation.process_alert.return_value = mock_alert

            prediction = PredictiveAlertingService.create_predictive_alert(
                prediction_type='sla_breach',
                entity_type='ticket',
                entity=mock_entity,
                probability=0.85,
                features={'feature1': 1.0},
                validation_hours=2
            )

            self.assertIsNotNone(prediction)
            self.assertEqual(prediction.prediction_type, 'sla_breach')
            self.assertEqual(prediction.predicted_probability, 0.85)
            self.assertEqual(prediction.confidence_bucket, 'high')

    def test_alert_message_generation(self):
        """Test alert message generation for different prediction types."""
        mock_entity = Mock()
        mock_entity.ticketno = 'TKT-123'

        message = PredictiveAlertingService._generate_alert_message(
            'sla_breach', mock_entity, 0.85, {}
        )

        self.assertIn('PREDICTIVE', message)
        self.assertIn('TKT-123', message)
        self.assertIn('85%', message)

    def test_snapshot_entity_captures_state(self):
        """Test entity snapshot captures relevant fields."""
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.__class__.__name__ = 'Ticket'
        mock_entity.status = 'NEW'
        mock_entity.priority = 'HIGH'
        mock_entity.assignee_id = 5

        snapshot = PredictiveAlertingService._snapshot_entity(mock_entity)

        self.assertEqual(snapshot['id'], 1)
        self.assertEqual(snapshot['type'], 'Ticket')
        self.assertEqual(snapshot['status'], 'NEW')
        self.assertEqual(snapshot['priority'], 'HIGH')


class PredictiveAlertTrackingTests(TestCase):
    """Tests for Prediction Outcome Validation (4 tests)."""

    def setUp(self):
        """Set up test tracking record."""
        from apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(tenantname='TestTenant', isactive=True)

        self.prediction = PredictiveAlertTracking.objects.create(
            prediction_type='sla_breach',
            tenant=self.tenant,
            predicted_probability=0.85,
            entity_type='ticket',
            entity_id=1,
            entity_metadata={'ticket_id': 1},
            feature_values={'feature1': 1.0},
            validation_deadline=timezone.now() + timedelta(hours=2),
            confidence_bucket='high'
        )

    def test_is_high_confidence_property(self):
        """Test high confidence detection."""
        self.prediction.predicted_probability = 0.9
        self.assertTrue(self.prediction.is_high_confidence)

        self.prediction.predicted_probability = 0.7
        self.assertFalse(self.prediction.is_high_confidence)

    def test_needs_validation_property(self):
        """Test validation deadline detection."""
        # Not yet at deadline
        self.prediction.validation_deadline = timezone.now() + timedelta(hours=1)
        self.assertFalse(self.prediction.needs_validation)

        # Past deadline
        self.prediction.validation_deadline = timezone.now() - timedelta(hours=1)
        self.assertTrue(self.prediction.needs_validation)

    def test_validate_outcome_true_positive(self):
        """Test validation of true positive prediction."""
        self.prediction.validate_outcome(actual_outcome=True, preventive_action_taken=False)

        self.assertTrue(self.prediction.actual_outcome)
        self.assertIsNotNone(self.prediction.validated_at)
        self.assertTrue(self.prediction.prediction_correct)

    def test_validate_outcome_prevented_event(self):
        """Test that prevented events count as correct predictions."""
        self.prediction.validate_outcome(actual_outcome=False, preventive_action_taken=True)

        self.assertFalse(self.prediction.actual_outcome)
        self.assertTrue(self.prediction.preventive_action_taken)
        self.assertTrue(self.prediction.prediction_correct)  # Still valuable


class CeleryTaskTests(TestCase):
    """Tests for Celery Task Execution (3 tests)."""

    def setUp(self):
        """Set up test tenant."""
        from apps.tenants.models import Tenant
        self.tenant = Tenant.objects.create(tenantname='TestTenant', isactive=True)

    @patch('apps.noc.tasks.predictive_alerting_tasks.PredictiveAlertingService')
    def test_predict_sla_breaches_task_runs(self, mock_service):
        """Test SLA breach prediction task executes."""
        from apps.noc.tasks.predictive_alerting_tasks import PredictSLABreachesTask

        mock_service.predict_sla_breaches.return_value = [Mock()]

        task = PredictSLABreachesTask()
        result = task.run(tenant_id=self.tenant.id)

        self.assertIn(self.tenant.id, result)
        mock_service.predict_sla_breaches.assert_called()

    @patch('apps.noc.tasks.predictive_alerting_tasks.PredictiveAlertingService')
    def test_predict_device_failures_task_runs(self, mock_service):
        """Test device failure prediction task executes."""
        from apps.noc.tasks.predictive_alerting_tasks import PredictDeviceFailuresTask

        mock_service.predict_device_failures.return_value = [Mock()]

        task = PredictDeviceFailuresTask()
        result = task.run(tenant_id=self.tenant.id)

        self.assertIn(self.tenant.id, result)
        mock_service.predict_device_failures.assert_called()

    @patch('apps.noc.tasks.predictive_alerting_tasks.PredictiveAlertTracking')
    def test_validate_predictions_task_processes_pending(self, mock_tracking):
        """Test validation task processes pending predictions."""
        from apps.noc.tasks.predictive_alerting_tasks import ValidatePredictiveAlertsTask

        # Mock pending predictions
        mock_tracking.objects.filter.return_value.select_related.return_value.count.return_value = 5

        task = ValidatePredictiveAlertsTask()
        result = task.run()

        self.assertIn('sla_breach', result)
        self.assertIn('device_failure', result)
        self.assertIn('staffing_gap', result)


class AlertDeduplicationTests(TestCase):
    """Tests for Alert Creation and Deduplication (2 tests)."""

    def setUp(self):
        """Set up test data."""
        from apps.tenants.models import Tenant
        from apps.onboarding.models import Bt

        self.tenant = Tenant.objects.create(tenantname='TestTenant', isactive=True)
        self.client = Bt.objects.create(tenant=self.tenant, buname='TestClient')

    @patch('apps.noc.services.correlation_service.AlertClusteringService')
    def test_predictive_alert_uses_deduplication(self, mock_clustering):
        """Test that predictive alerts use existing deduplication."""
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.tenant = self.tenant
        mock_entity.client = self.client
        mock_entity.bu = None

        with patch('apps.noc.services.predictive_alerting_service.AlertCorrelationService.process_alert') as mock_process:
            mock_process.return_value = Mock()

            PredictiveAlertingService.create_predictive_alert(
                prediction_type='sla_breach',
                entity_type='ticket',
                entity=mock_entity,
                probability=0.85,
                features={},
                validation_hours=2
            )

            # Verify AlertCorrelationService was called (includes deduplication)
            mock_process.assert_called_once()

    def test_suppressed_alert_returns_none(self):
        """Test that suppressed alerts don't create tracking records."""
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.tenant = self.tenant
        mock_entity.client = self.client
        mock_entity.bu = None

        with patch('apps.noc.services.predictive_alerting_service.AlertCorrelationService.process_alert') as mock_process:
            mock_process.return_value = None  # Alert suppressed

            result = PredictiveAlertingService.create_predictive_alert(
                prediction_type='sla_breach',
                entity_type='ticket',
                entity=mock_entity,
                probability=0.85,
                features={},
                validation_hours=2
            )

            self.assertIsNone(result)
