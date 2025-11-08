"""
Comprehensive tests for Device Health Service.

Tests health score computation, component scoring (battery, signal, uptime,
temperature), and proactive alert generation for device failure prediction.

Coverage target: 80%+
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase

from apps.monitoring.services.device_health_service import DeviceHealthService


@pytest.fixture
def mock_telemetry_data():
    """Create mock telemetry data for testing."""
    def create_telemetry(
        device_id="GPS-001",
        battery_level=80,
        signal_strength=75,
        status='online',
        temperature=25,
        tenant_id=1,
        hours_ago=0
    ):
        telemetry = Mock()
        telemetry.device_id = device_id
        telemetry.battery_level = battery_level
        telemetry.signal_strength = signal_strength
        telemetry.status = status
        telemetry.temperature = temperature
        telemetry.tenant_id = tenant_id
        telemetry.timestamp = timezone.now() - timedelta(hours=hours_ago)
        return telemetry
    
    return create_telemetry


@pytest.fixture
def healthy_telemetry_sequence(mock_telemetry_data):
    """Create sequence of healthy telemetry readings."""
    return [
        mock_telemetry_data(battery_level=85, signal_strength=80, hours_ago=i)
        for i in range(10)
    ]


@pytest.fixture
def degrading_battery_sequence(mock_telemetry_data):
    """Create sequence showing battery degradation."""
    return [
        mock_telemetry_data(
            battery_level=90 - (i * 5),  # Battery declining
            signal_strength=75,
            hours_ago=i
        )
        for i in range(10)
    ]


class TestHealthScoreComputation:
    """Test overall health score calculation."""

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_compute_health_score_healthy_device(
        self,
        mock_telemetry_model,
        healthy_telemetry_sequence
    ):
        """Test health score for healthy device."""
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = healthy_telemetry_sequence
        
        result = DeviceHealthService.compute_health_score("GPS-001")
        
        assert result['device_id'] == "GPS-001"
        assert result['health_score'] >= 80
        assert result['status'] == 'HEALTHY'
        assert 'components' in result

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_compute_health_score_no_telemetry(self, mock_telemetry_model):
        """Test health score when no telemetry available."""
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = []
        
        result = DeviceHealthService.compute_health_score("GPS-999")
        
        assert result['device_id'] == "GPS-999"
        assert result['health_score'] == 50
        assert result['status'] == 'UNKNOWN'
        assert 'No recent telemetry' in result['message']

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_compute_health_score_critical_device(
        self,
        mock_telemetry_model,
        mock_telemetry_data
    ):
        """Test health score for critical device."""
        critical_telemetry = [
            mock_telemetry_data(
                battery_level=15,  # Low battery
                signal_strength=25,  # Weak signal
                status='offline',  # Offline
                temperature=50,  # High temp
                hours_ago=i
            )
            for i in range(10)
        ]
        
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = critical_telemetry
        
        result = DeviceHealthService.compute_health_score("GPS-002")
        
        assert result['health_score'] < DeviceHealthService.HEALTH_CRITICAL
        assert result['status'] == 'CRITICAL'

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_compute_health_score_warning_device(
        self,
        mock_telemetry_model,
        mock_telemetry_data
    ):
        """Test health score for device in warning state."""
        warning_telemetry = [
            mock_telemetry_data(
                battery_level=45,  # Medium battery
                signal_strength=50,  # Medium signal
                hours_ago=i
            )
            for i in range(10)
        ]
        
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = warning_telemetry
        
        result = DeviceHealthService.compute_health_score("GPS-003")
        
        assert DeviceHealthService.HEALTH_CRITICAL <= result['health_score'] < DeviceHealthService.HEALTH_WARNING
        assert result['status'] == 'WARNING'

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_compute_health_score_with_tenant_filter(
        self,
        mock_telemetry_model,
        healthy_telemetry_sequence
    ):
        """Test health score computation with tenant filtering."""
        mock_filter = Mock()
        mock_telemetry_model.objects.filter.return_value = mock_filter
        mock_filter.order_by.return_value.__getitem__.return_value = healthy_telemetry_sequence
        
        DeviceHealthService.compute_health_score("GPS-001", tenant_id=5)
        
        # Verify tenant_id was included in query
        call_args = mock_telemetry_model.objects.filter.call_args[0][0]
        assert 'tenant_id' in str(call_args)


class TestBatteryScore:
    """Test battery health score calculation."""

    def test_battery_score_full_battery(self):
        """Test battery score with full battery."""
        telemetry = [Mock(battery_level=95) for _ in range(10)]
        
        score = DeviceHealthService._compute_battery_score(telemetry)
        
        assert score == 100

    def test_battery_score_low_battery(self):
        """Test battery score with low battery."""
        telemetry = [Mock(battery_level=15) for _ in range(10)]
        
        score = DeviceHealthService._compute_battery_score(telemetry)
        
        assert score <= 40

    def test_battery_score_declining_trend_penalty(self):
        """Test battery score penalty for declining trend."""
        # Recent readings lower than older readings
        telemetry = [
            Mock(battery_level=50),  # Recent
            Mock(battery_level=51),
            Mock(battery_level=52),
            Mock(battery_level=53),
            Mock(battery_level=54),
            Mock(battery_level=75),  # Older
            Mock(battery_level=76),
            Mock(battery_level=77),
            Mock(battery_level=78),
            Mock(battery_level=79),
        ]
        
        score = DeviceHealthService._compute_battery_score(telemetry)
        
        # Should apply declining trend penalty
        assert score < 80

    def test_battery_score_no_battery_data(self):
        """Test battery score when no battery data available."""
        telemetry = [Mock(battery_level=None) for _ in range(10)]
        
        score = DeviceHealthService._compute_battery_score(telemetry)
        
        assert score == 50.0  # Unknown

    def test_battery_score_stable_medium_battery(self):
        """Test battery score with stable medium battery."""
        telemetry = [Mock(battery_level=55) for _ in range(10)]
        
        score = DeviceHealthService._compute_battery_score(telemetry)
        
        assert 70 <= score <= 90


class TestSignalScore:
    """Test signal strength stability score calculation."""

    def test_signal_score_excellent_stable(self):
        """Test signal score with excellent stable signal."""
        telemetry = [Mock(signal_strength=85) for _ in range(10)]
        
        score = DeviceHealthService._compute_signal_score(telemetry)
        
        assert score == 100.0

    def test_signal_score_good_stable(self):
        """Test signal score with good stable signal."""
        telemetry = [Mock(signal_strength=65) for _ in range(10)]
        
        score = DeviceHealthService._compute_signal_score(telemetry)
        
        assert score >= 60

    def test_signal_score_poor_signal(self):
        """Test signal score with poor signal."""
        telemetry = [Mock(signal_strength=30) for _ in range(10)]
        
        score = DeviceHealthService._compute_signal_score(telemetry)
        
        assert score <= 60

    def test_signal_score_high_variability_penalty(self):
        """Test signal score penalty for high variability."""
        # High variability (jumps between 40 and 80)
        telemetry = [Mock(signal_strength=40 if i % 2 == 0 else 80) for i in range(10)]
        
        score = DeviceHealthService._compute_signal_score(telemetry)
        
        # Should penalize high variability
        assert score < 100

    def test_signal_score_no_signal_data(self):
        """Test signal score when no signal data available."""
        telemetry = [Mock(signal_strength=None) for _ in range(10)]
        
        score = DeviceHealthService._compute_signal_score(telemetry)
        
        assert score == 50.0  # Unknown


class TestUptimeScore:
    """Test uptime/connectivity score calculation."""

    def test_uptime_score_always_online(self):
        """Test uptime score when device always online."""
        telemetry = [Mock(status='online') for _ in range(10)]
        
        score = DeviceHealthService._compute_uptime_score(telemetry)
        
        assert score == 100.0

    def test_uptime_score_always_offline(self):
        """Test uptime score when device always offline."""
        telemetry = [Mock(status='offline') for _ in range(10)]
        
        score = DeviceHealthService._compute_uptime_score(telemetry)
        
        assert score == 0.0

    def test_uptime_score_intermittent_connectivity(self):
        """Test uptime score with intermittent connectivity."""
        telemetry = [
            Mock(status='online' if i % 2 == 0 else 'offline')
            for i in range(10)
        ]
        
        score = DeviceHealthService._compute_uptime_score(telemetry)
        
        assert 40 <= score <= 60  # ~50% uptime

    def test_uptime_score_no_telemetry(self):
        """Test uptime score with no telemetry."""
        score = DeviceHealthService._compute_uptime_score([])
        
        assert score == 50.0  # Unknown


class TestTemperatureScore:
    """Test temperature health score calculation."""

    def test_temperature_score_ideal_range(self):
        """Test temperature score in ideal range (15-35°C)."""
        telemetry = [Mock(temperature=25) for _ in range(10)]
        
        score = DeviceHealthService._compute_temperature_score(telemetry)
        
        assert score == 100.0

    def test_temperature_score_acceptable_range(self):
        """Test temperature score in acceptable range (10-40°C)."""
        telemetry = [Mock(temperature=12) for _ in range(10)]
        
        score = DeviceHealthService._compute_temperature_score(telemetry)
        
        assert score == 80.0

    def test_temperature_score_marginal_range(self):
        """Test temperature score in marginal range (5-45°C)."""
        telemetry = [Mock(temperature=7) for _ in range(10)]
        
        score = DeviceHealthService._compute_temperature_score(telemetry)
        
        assert score == 60.0

    def test_temperature_score_too_hot(self):
        """Test temperature score when too hot."""
        telemetry = [Mock(temperature=50) for _ in range(10)]
        
        score = DeviceHealthService._compute_temperature_score(telemetry)
        
        assert score == 40.0

    def test_temperature_score_too_cold(self):
        """Test temperature score when too cold."""
        telemetry = [Mock(temperature=-5) for _ in range(10)]
        
        score = DeviceHealthService._compute_temperature_score(telemetry)
        
        assert score == 40.0

    def test_temperature_score_no_temperature_data(self):
        """Test temperature score with no data."""
        telemetry = [Mock(temperature=None) for _ in range(10)]
        
        score = DeviceHealthService._compute_temperature_score(telemetry)
        
        assert score == 100.0  # Assume OK


class TestComponentWeighting:
    """Test component score weighting in overall health."""

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_battery_has_highest_weight(
        self,
        mock_telemetry_model,
        mock_telemetry_data
    ):
        """Test battery score has 40% weight in overall health."""
        # Low battery, everything else perfect
        telemetry = [
            mock_telemetry_data(
                battery_level=20,  # Low
                signal_strength=90,  # Perfect
                status='online',  # Perfect
                temperature=25,  # Perfect
                hours_ago=i
            )
            for i in range(10)
        ]
        
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = telemetry
        
        result = DeviceHealthService.compute_health_score("GPS-001")
        
        # Low battery should significantly impact overall score
        assert result['health_score'] < 70

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_component_scores_returned(
        self,
        mock_telemetry_model,
        healthy_telemetry_sequence
    ):
        """Test all component scores are returned."""
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = healthy_telemetry_sequence
        
        result = DeviceHealthService.compute_health_score("GPS-001")
        
        components = result['components']
        assert 'battery' in components
        assert 'signal' in components
        assert 'uptime' in components
        assert 'temperature' in components


class TestProactiveAlerts:
    """Test proactive alert generation for predicted failures."""

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    @patch('apps.monitoring.services.device_health_service.DeviceFailurePredictor')
    @patch('apps.monitoring.services.device_health_service.NOCAlertEvent')
    def test_create_proactive_alerts_low_battery(
        self,
        mock_noc_alert,
        mock_predictor,
        mock_telemetry_model,
        mock_telemetry_data
    ):
        """Test proactive alert creation for low battery prediction."""
        # Setup telemetry
        low_battery_telemetry = mock_telemetry_data(battery_level=25)
        mock_telemetry_model.objects.filter.return_value.values.return_value.distinct.return_value = [
            {'device_id': 'GPS-001'}
        ]
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.first.return_value = low_battery_telemetry
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = [
            low_battery_telemetry
        ] * 10
        
        # Mock high failure probability
        mock_predictor.predict_failure.return_value = (0.75, {})
        
        with patch.object(DeviceHealthService, 'compute_health_score') as mock_health:
            mock_health.return_value = {
                'health_score': 35,
                'components': {
                    'battery': 30,
                    'signal': 80,
                    'uptime': 90,
                    'temperature': 100
                }
            }
            
            result = DeviceHealthService.create_proactive_alerts()
        
        assert result['low_battery'] > 0

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    @patch('apps.monitoring.services.device_health_service.DeviceFailurePredictor')
    @patch('apps.monitoring.services.device_health_service.NOCAlertEvent')
    def test_create_proactive_alerts_skips_healthy_devices(
        self,
        mock_noc_alert,
        mock_predictor,
        mock_telemetry_model,
        mock_telemetry_data,
        healthy_telemetry_sequence
    ):
        """Test that healthy devices don't generate alerts."""
        mock_telemetry_model.objects.filter.return_value.values.return_value.distinct.return_value = [
            {'device_id': 'GPS-001'}
        ]
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.first.return_value = healthy_telemetry_sequence[0]
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = healthy_telemetry_sequence
        
        with patch.object(DeviceHealthService, 'compute_health_score') as mock_health:
            mock_health.return_value = {
                'health_score': 95,  # Healthy
                'components': {'battery': 100, 'signal': 100, 'uptime': 100, 'temperature': 100}
            }
            
            result = DeviceHealthService.create_proactive_alerts()
        
        # Should not create alerts for healthy devices
        assert result['low_battery'] == 0
        assert result['offline_risk'] == 0

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_create_proactive_alerts_with_tenant_filter(
        self,
        mock_telemetry_model
    ):
        """Test proactive alerts with tenant filtering."""
        mock_telemetry_model.objects.filter.return_value.values.return_value.distinct.return_value = []
        
        DeviceHealthService.create_proactive_alerts(tenant_id=7)
        
        # Verify tenant filter was applied
        call_args = mock_telemetry_model.objects.filter.call_args[0][0]
        assert 'tenant_id' in str(call_args)


class TestHealthConstants:
    """Test health score threshold constants."""

    def test_health_critical_threshold(self):
        """Test critical health threshold."""
        assert DeviceHealthService.HEALTH_CRITICAL == 40

    def test_health_warning_threshold(self):
        """Test warning health threshold."""
        assert DeviceHealthService.HEALTH_WARNING == 70

    def test_health_good_threshold(self):
        """Test good health threshold."""
        assert DeviceHealthService.HEALTH_GOOD == 70


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_database_error_handling(self, mock_telemetry_model):
        """Test handling of database errors."""
        from django.db import DatabaseError
        mock_telemetry_model.objects.filter.side_effect = DatabaseError("Connection lost")
        
        with pytest.raises(DatabaseError):
            DeviceHealthService.compute_health_score("GPS-001")

    def test_empty_telemetry_list(self):
        """Test handling empty telemetry list."""
        battery_score = DeviceHealthService._compute_battery_score([])
        signal_score = DeviceHealthService._compute_signal_score([])
        uptime_score = DeviceHealthService._compute_uptime_score([])
        temp_score = DeviceHealthService._compute_temperature_score([])
        
        # All should return default scores
        assert battery_score == 50.0
        assert signal_score == 50.0
        assert uptime_score == 50.0
        assert temp_score == 100.0


class TestDataIntegrity:
    """Test data validation and integrity."""

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_health_score_rounded(
        self,
        mock_telemetry_model,
        healthy_telemetry_sequence
    ):
        """Test health score is rounded to 1 decimal place."""
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = healthy_telemetry_sequence
        
        result = DeviceHealthService.compute_health_score("GPS-001")
        
        # Verify score is rounded
        assert result['health_score'] == round(result['health_score'], 1)

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_telemetry_count_accurate(
        self,
        mock_telemetry_model,
        healthy_telemetry_sequence
    ):
        """Test telemetry count is accurately reported."""
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = healthy_telemetry_sequence
        
        result = DeviceHealthService.compute_health_score("GPS-001")
        
        assert result['telemetry_count'] == len(healthy_telemetry_sequence)

    @patch('apps.monitoring.services.device_health_service.DeviceTelemetry')
    def test_last_reading_timestamp(
        self,
        mock_telemetry_model,
        healthy_telemetry_sequence
    ):
        """Test last reading timestamp is correctly captured."""
        mock_telemetry_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = healthy_telemetry_sequence
        
        result = DeviceHealthService.compute_health_score("GPS-001")
        
        assert result['last_reading'] == healthy_telemetry_sequence[0].timestamp
