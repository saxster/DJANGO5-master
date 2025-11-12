"""
Unit Tests for Security Anomaly Orchestrator.

Tests end-to-end anomaly detection and NOC alert integration.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestSecurityAnomalyOrchestrator:
    """Test orchestrator service integration."""

    def test_process_attendance_creates_anomaly_log(
        self, security_config, attendance_event, other_person
    ):
        """Test that processing attendance creates anomaly logs."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import (
            ShiftScheduleCache,
            AttendanceAnomalyLog
        )

        ShiftScheduleCache.objects.create(
            tenant=attendance_event.tenant,
            person=other_person,
            site=attendance_event.bu,
            shift_date=attendance_event.datefor,
            scheduled_start=attendance_event.punchintime,
            scheduled_end=attendance_event.punchintime + timedelta(hours=8),
            cache_valid_until=timezone.now() + timedelta(days=1)
        )

        anomalies = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        assert len(anomalies) > 0
        assert AttendanceAnomalyLog.objects.filter(
            attendance_event=attendance_event
        ).count() > 0

    def test_process_attendance_creates_noc_alert(
        self, security_config, attendance_event, other_person
    ):
        """Test that processing creates NOC alerts."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import (
            ShiftScheduleCache,
            AttendanceAnomalyLog
        )

        ShiftScheduleCache.objects.create(
            tenant=attendance_event.tenant,
            person=other_person,
            site=attendance_event.bu,
            shift_date=attendance_event.datefor,
            scheduled_start=attendance_event.punchintime,
            scheduled_end=attendance_event.punchintime + timedelta(hours=8),
            cache_valid_until=timezone.now() + timedelta(days=1)
        )

        anomalies = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        for anomaly in anomalies:
            assert anomaly.noc_alert is not None
            assert anomaly.noc_alert.alert_type == 'SECURITY_ANOMALY'
            assert anomaly.noc_alert.severity == anomaly.severity

    def test_process_attendance_no_config_returns_empty(self, attendance_event):
        """Test that no config returns empty results."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator

        anomalies = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        assert len(anomalies) == 0

    def test_anomaly_log_status_updates(
        self, security_config, attendance_event, other_person, test_person
    ):
        """Test anomaly log status update methods."""
        from apps.noc.security_intelligence.models import AttendanceAnomalyLog

        anomaly_log = AttendanceAnomalyLog.objects.create(
            tenant=attendance_event.tenant,
            anomaly_type='WRONG_PERSON',
            severity='HIGH',
            person=attendance_event.people,
            site=attendance_event.bu,
            attendance_event=attendance_event,
            detected_at=timezone.now(),
            confidence_score=0.95,
            expected_person=other_person
        )

        anomaly_log.mark_confirmed(test_person, "Confirmed after investigation")

        assert anomaly_log.status == 'CONFIRMED'
        assert anomaly_log.investigated_by == test_person
        assert anomaly_log.investigated_at is not None
        assert 'investigation' in anomaly_log.investigation_notes.lower()

    def test_anomaly_log_false_positive(
        self, security_config, attendance_event, other_person, test_person
    ):
        """Test marking anomaly as false positive."""
        from apps.noc.security_intelligence.models import AttendanceAnomalyLog

        anomaly_log = AttendanceAnomalyLog.objects.create(
            tenant=attendance_event.tenant,
            anomaly_type='WRONG_PERSON',
            severity='HIGH',
            person=attendance_event.people,
            site=attendance_event.bu,
            attendance_event=attendance_event,
            detected_at=timezone.now(),
            confidence_score=0.95,
            expected_person=other_person
        )

        anomaly_log.mark_false_positive(test_person, "Schedule was updated")

        assert anomaly_log.status == 'FALSE_POSITIVE'
        assert anomaly_log.investigated_by == test_person

    def test_ml_prediction_called_for_attendance_event(
        self, security_config, attendance_event, mocker
    ):
        """Test that ML prediction is called when processing attendance."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator

        # Mock the ML predictor
        mock_predict = mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value={
                'fraud_probability': 0.3,
                'risk_level': 'MEDIUM',
                'model_confidence': 0.85,
                'behavioral_risk': 0.2,
                'features': {},
                'model_version': 'v1.0',
                'prediction_method': 'xgboost',
            }
        )
        mock_log = mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.log_prediction'
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify ML prediction was called
        assert mock_predict.call_count == 1
        call_kwargs = mock_predict.call_args.kwargs
        assert call_kwargs['person'] == attendance_event.people
        assert call_kwargs['site'] == attendance_event.bu
        assert call_kwargs['scheduled_time'] == attendance_event.punchintime

        # Verify prediction was logged
        assert mock_log.call_count == 1

    def test_high_risk_prediction_creates_alert(
        self, security_config, attendance_event, mocker
    ):
        """Test that HIGH risk predictions create alerts."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.models import NOCAlertEvent

        # Mock ML predictor to return HIGH risk
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value={
                'fraud_probability': 0.75,
                'risk_level': 'HIGH',
                'model_confidence': 0.92,
                'behavioral_risk': 0.6,
                'features': {'hour_of_day': 22, 'is_weekend': True},
                'model_version': 'v1.0',
                'prediction_method': 'xgboost',
            }
        )
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.log_prediction'
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify alert was created
        alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION',
            entity_id=attendance_event.id
        ).first()

        assert alert is not None
        assert alert.severity == 'HIGH'
        assert alert.metadata['ml_prediction']['fraud_probability'] == 0.75
        assert alert.metadata['person_id'] == attendance_event.people.id

    def test_critical_risk_prediction_creates_critical_alert(
        self, security_config, attendance_event, mocker
    ):
        """Test that CRITICAL risk predictions create CRITICAL alerts."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.models import NOCAlertEvent

        # Mock ML predictor to return CRITICAL risk
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value={
                'fraud_probability': 0.92,
                'risk_level': 'CRITICAL',
                'model_confidence': 0.95,
                'behavioral_risk': 0.85,
                'features': {'hour_of_day': 3, 'gps_drift_meters': 1500},
                'model_version': 'v1.0',
                'prediction_method': 'xgboost',
            }
        )
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.log_prediction'
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify CRITICAL alert was created
        alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION',
            entity_id=attendance_event.id
        ).first()

        assert alert is not None
        assert alert.severity == 'CRITICAL'
        assert alert.metadata['ml_prediction']['fraud_probability'] == 0.92

    def test_low_risk_prediction_no_alert(
        self, security_config, attendance_event, mocker
    ):
        """Test that LOW/MEDIUM risk predictions don't create alerts."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.models import NOCAlertEvent

        # Mock ML predictor to return LOW risk
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value={
                'fraud_probability': 0.25,
                'risk_level': 'LOW',
                'model_confidence': 0.85,
                'behavioral_risk': 0.1,
                'features': {},
                'model_version': 'v1.0',
                'prediction_method': 'xgboost',
            }
        )
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.log_prediction'
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify no ML prediction alert was created
        alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION',
            entity_id=attendance_event.id
        ).first()

        assert alert is None

    def test_ml_prediction_failure_continues_with_heuristics(
        self, security_config, attendance_event, mocker
    ):
        """Test that ML prediction failure doesn't stop heuristic detection."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator

        # Mock ML predictor to raise exception
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            side_effect=ValueError("Model not found")
        )

        # Should not raise exception - should continue with heuristics
        result = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Result should still be valid (empty or with heuristic anomalies)
        assert isinstance(result, dict)
        assert 'anomalies' in result

    def test_ml_prediction_disabled_via_config(
        self, security_config, attendance_event, mocker
    ):
        """Test that ML prediction can be disabled via config."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator

        # Disable predictive fraud
        security_config.predictive_fraud_enabled = False
        security_config.save()

        mock_predict = mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud'
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify ML prediction was NOT called
        assert mock_predict.call_count == 0


@pytest.mark.django_db
class TestFraudTicketAutoCreation:
    """Test fraud ticket auto-creation (Gap #9)."""

    def test_high_fraud_score_creates_ticket(
        self, security_config, attendance_event, mocker, settings
    ):
        """Test that fraud score >= 0.80 creates ticket."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.y_helpdesk.models import Ticket

        # Set fraud threshold to 0.80
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80

        # Mock fraud score calculation
        fraud_score_result = {
            'fraud_score': 0.85,
            'risk_level': 'HIGH',
            'fraud_types': ['buddy_punching', 'gps_spoofing'],
            'evidence': {
                'buddy_punching': {'confidence': 0.9},
                'gps_spoofing': {'distance_meters': 500}
            }
        }

        # Process attendance with high fraud score
        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify ticket was created
        ticket = Ticket.objects.filter(
            bu=attendance_event.bu,
            ticketdesc__icontains='FRAUD ALERT'
        ).first()

        assert ticket is not None
        assert ticket.priority == Ticket.Priority.HIGH
        assert ticket.status == Ticket.Status.NEW
        assert ticket.ticketsource == Ticket.TicketSource.SYSTEMGENERATED

        # Verify metadata
        workflow = ticket.get_or_create_workflow()
        assert workflow.workflow_data['fraud_score'] == 0.85
        assert workflow.workflow_data['fraud_type'] == 'buddy_punching'
        assert workflow.workflow_data['auto_created'] is True
        assert workflow.workflow_data['created_by'] == 'SecurityAnomalyOrchestrator'
        assert workflow.workflow_data['person_id'] == attendance_event.people.id

    def test_low_fraud_score_no_ticket(
        self, security_config, attendance_event, mocker, settings
    ):
        """Test that fraud score < 0.80 does not create ticket."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.y_helpdesk.models import Ticket

        # Set fraud threshold to 0.80
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80

        # Mock fraud score calculation with low score
        fraud_score_result = {
            'fraud_score': 0.65,
            'risk_level': 'MEDIUM',
            'fraud_types': ['geofence_violation'],
            'evidence': {'geofence_violation': {}}
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result
        )

        initial_ticket_count = Ticket.objects.count()
        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify no ticket was created
        final_ticket_count = Ticket.objects.count()
        assert final_ticket_count == initial_ticket_count

    def test_deduplication_prevents_duplicate_tickets(
        self, security_config, attendance_event, mocker, settings
    ):
        """Test that deduplication prevents multiple tickets within 24h."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.y_helpdesk.models import Ticket

        # Set fraud threshold and deduplication window
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80
        settings.NOC_CONFIG['FRAUD_DEDUPLICATION_HOURS'] = 24

        # Mock fraud score calculation
        fraud_score_result = {
            'fraud_score': 0.85,
            'risk_level': 'HIGH',
            'fraud_types': ['buddy_punching'],
            'evidence': {'buddy_punching': {'confidence': 0.9}}
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result
        )

        # First call - should create ticket
        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)
        first_ticket_count = Ticket.objects.filter(
            bu=attendance_event.bu,
            ticketdesc__icontains='FRAUD ALERT'
        ).count()
        assert first_ticket_count == 1

        # Second call - should NOT create duplicate ticket
        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)
        second_ticket_count = Ticket.objects.filter(
            bu=attendance_event.bu,
            ticketdesc__icontains='FRAUD ALERT'
        ).count()
        assert second_ticket_count == 1  # Still only 1 ticket

    def test_different_fraud_type_creates_separate_ticket(
        self, security_config, attendance_event, mocker, settings
    ):
        """Test that different fraud types create separate tickets."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.y_helpdesk.models import Ticket

        # Set fraud threshold
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80

        # First fraud type: buddy_punching
        fraud_score_result_1 = {
            'fraud_score': 0.85,
            'risk_level': 'HIGH',
            'fraud_types': ['buddy_punching'],
            'evidence': {'buddy_punching': {'confidence': 0.9}}
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result_1
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Second fraud type: gps_spoofing
        fraud_score_result_2 = {
            'fraud_score': 0.88,
            'risk_level': 'HIGH',
            'fraud_types': ['gps_spoofing'],
            'evidence': {'gps_spoofing': {'distance_meters': 1000}}
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result_2
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify two tickets were created
        tickets = Ticket.objects.filter(
            bu=attendance_event.bu,
            ticketdesc__icontains='FRAUD ALERT'
        )
        assert tickets.count() == 2

    def test_ticket_assigned_to_security_manager(
        self, security_config, attendance_event, mocker, settings, test_person
    ):
        """Test that ticket is assigned to security_manager if available."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.y_helpdesk.models import Ticket

        # Set security manager on site
        attendance_event.bu.security_manager = test_person
        attendance_event.bu.save()

        # Set fraud threshold
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80

        # Mock fraud score calculation
        fraud_score_result = {
            'fraud_score': 0.85,
            'risk_level': 'HIGH',
            'fraud_types': ['buddy_punching'],
            'evidence': {'buddy_punching': {'confidence': 0.9}}
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify ticket assigned to security manager
        ticket = Ticket.objects.filter(
            bu=attendance_event.bu,
            ticketdesc__icontains='FRAUD ALERT'
        ).first()

        assert ticket.assignedtopeople == test_person

    def test_ticket_metadata_complete(
        self, security_config, attendance_event, mocker, settings
    ):
        """Test that ticket metadata includes all required fields."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.y_helpdesk.models import Ticket

        # Set fraud threshold
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80

        # Mock fraud score calculation
        fraud_score_result = {
            'fraud_score': 0.92,
            'risk_level': 'CRITICAL',
            'fraud_types': ['buddy_punching', 'gps_spoofing'],
            'evidence': {
                'buddy_punching': {'confidence': 0.95},
                'gps_spoofing': {'distance_meters': 2000}
            }
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result
        )

        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify ticket metadata
        ticket = Ticket.objects.filter(
            bu=attendance_event.bu,
            ticketdesc__icontains='FRAUD ALERT'
        ).first()

        workflow = ticket.get_or_create_workflow()
        metadata = workflow.workflow_data

        # Verify all required metadata fields
        assert 'fraud_score' in metadata
        assert metadata['fraud_score'] == 0.92
        assert 'fraud_type' in metadata
        assert metadata['fraud_type'] == 'buddy_punching'
        assert 'fraud_types' in metadata
        assert len(metadata['fraud_types']) == 2
        assert 'auto_created' in metadata
        assert metadata['auto_created'] is True
        assert 'created_by' in metadata
        assert metadata['created_by'] == 'SecurityAnomalyOrchestrator'
        assert 'person_id' in metadata
        assert metadata['person_id'] == attendance_event.people.id
        assert 'person_name' in metadata
        assert metadata['person_name'] == attendance_event.people.peoplename
        assert 'attendance_event_id' in metadata
        assert metadata['attendance_event_id'] == attendance_event.id
        assert 'evidence' in metadata


@pytest.mark.django_db
class TestFraudDetectionWorkflowIntegration:
    """Integration test for full fraud detection → alert → ticket workflow."""

    def test_full_fraud_workflow(
        self, security_config, attendance_event, mocker, settings, test_person
    ):
        """
        Integration test: Fraud detection → Alert → Ticket workflow.

        Verifies:
        1. High fraud score triggers fraud alert
        2. Alert is created with correct metadata
        3. Ticket is auto-created
        4. Ticket is assigned correctly
        5. All metadata is linked properly
        """
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.models import NOCAlertEvent
        from apps.y_helpdesk.models import Ticket

        # Set up configuration
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80
        settings.NOC_CONFIG['FRAUD_DEDUPLICATION_HOURS'] = 24
        attendance_event.bu.security_manager = test_person
        attendance_event.bu.save()

        # Mock fraud detection with high score
        fraud_score_result = {
            'fraud_score': 0.87,
            'risk_level': 'HIGH',
            'fraud_types': ['buddy_punching', 'geofence_violation'],
            'evidence': {
                'buddy_punching': {'confidence': 0.92, 'face_match_score': 0.45},
                'geofence_violation': {'distance_meters': 1200}
            }
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result
        )

        # Process attendance event
        result = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify alert was created
        alert = NOCAlertEvent.objects.filter(
            entity_type='attendance_fraud',
            entity_id=attendance_event.id
        ).first()

        assert alert is not None
        assert alert.severity == 'HIGH'
        assert alert.metadata['fraud_score'] == 0.87
        assert alert.metadata['person_id'] == attendance_event.people.id
        assert len(alert.metadata['fraud_types']) == 2

        # Verify ticket was created
        ticket = Ticket.objects.filter(
            bu=attendance_event.bu,
            ticketdesc__icontains='FRAUD ALERT'
        ).first()

        assert ticket is not None
        assert ticket.assignedtopeople == test_person
        assert ticket.priority == Ticket.Priority.HIGH
        assert ticket.status == Ticket.Status.NEW

        # Verify ticket metadata links to alert
        workflow = ticket.get_or_create_workflow()
        assert str(alert.id) in workflow.workflow_data['alert_id']
        assert workflow.workflow_data['fraud_score'] == 0.87
        assert workflow.workflow_data['person_id'] == attendance_event.people.id
        assert workflow.workflow_data['attendance_event_id'] == attendance_event.id

        # Verify ticket description contains all key information
        assert attendance_event.people.peoplename in ticket.ticketdesc
        assert 'buddy_punching' in ticket.ticketdesc
        assert '0.87' in ticket.ticketdesc or '87%' in ticket.ticketdesc

    def test_fraud_workflow_with_ml_prediction(
        self, security_config, attendance_event, mocker, settings
    ):
        """
        Integration test: ML prediction + fraud detection workflow.

        Tests both ML prediction alert AND fraud score ticket creation.
        """
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.models import NOCAlertEvent
        from apps.y_helpdesk.models import Ticket

        # Set configuration
        settings.NOC_CONFIG['FRAUD_SCORE_TICKET_THRESHOLD'] = 0.80

        # Mock ML prediction with HIGH risk
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value={
                'fraud_probability': 0.78,
                'risk_level': 'HIGH',
                'model_confidence': 0.91,
                'behavioral_risk': 0.65,
                'features': {'hour_of_day': 23, 'is_weekend': True},
                'model_version': 'v1.0',
                'prediction_method': 'xgboost',
            }
        )
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.log_prediction'
        )

        # Mock fraud score calculation
        fraud_score_result = {
            'fraud_score': 0.85,
            'risk_level': 'HIGH',
            'fraud_types': ['buddy_punching'],
            'evidence': {'buddy_punching': {'confidence': 0.88}}
        }

        mocker.patch(
            'apps.noc.security_intelligence.services.fraud_score_calculator.FraudScoreCalculator.calculate_fraud_score',
            return_value=fraud_score_result
        )

        # Process event
        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify ML prediction alert created
        ml_alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION'
        ).first()
        assert ml_alert is not None

        # Verify fraud alert created
        fraud_alert = NOCAlertEvent.objects.filter(
            entity_type='attendance_fraud'
        ).first()
        assert fraud_alert is not None

        # Verify ticket created for fraud score
        ticket = Ticket.objects.filter(
            ticketdesc__icontains='FRAUD ALERT'
        ).first()
        assert ticket is not None

        # Both alerts should exist independently
        assert NOCAlertEvent.objects.count() >= 2