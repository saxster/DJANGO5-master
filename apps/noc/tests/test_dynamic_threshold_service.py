"""
Tests for DynamicThresholdService

Tests dynamic threshold calculation and anomaly detection including:
- Threshold calculation with historical data
- Anomaly detection algorithms
- Adaptive threshold adjustment
- Edge cases and data quality issues
"""

import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal

from apps.noc.services.dynamic_threshold_service import DynamicThresholdService
from apps.noc.models import NOCMetricSnapshot, NOCAlertEvent
from apps.tenants.models import Tenant
from apps.core.models import BusinessUnit


@pytest.fixture
def test_tenant():
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        is_active=True
    )


@pytest.fixture
def test_site(test_tenant):
    """Create test site."""
    return BusinessUnit.objects.create(
        buname="Test Site",
        bucode="TEST_SITE",
        client=test_tenant
    )


@pytest.fixture
def metric_snapshots(test_tenant, test_site):
    """Create sample metric snapshots for testing."""
    snapshots = []
    base_time = timezone.now() - timedelta(days=7)
    
    # Create 7 days of normal data (value around 50)
    for day in range(7):
        for hour in range(24):
            snapshot_time = base_time + timedelta(days=day, hours=hour)
            value = 50 + (day % 3) * 5  # Value between 45-60
            
            snapshot = NOCMetricSnapshot.objects.create(
                client=test_tenant,
                bu=test_site,
                metric_name='cpu_usage',
                metric_value=Decimal(str(value)),
                entity_type='server',
                entity_id='server_001',
                timestamp=snapshot_time
            )
            snapshots.append(snapshot)
    
    return snapshots


@pytest.mark.django_db
class TestThresholdCalculation:
    """Test threshold calculation logic."""
    
    def test_calculate_basic_threshold(self, test_tenant, test_site, metric_snapshots):
        """Test basic threshold calculation from historical data."""
        result = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='cpu_usage',
            entity_type='server',
            entity_id='server_001',
            lookback_days=7
        )
        
        assert 'mean' in result
        assert 'std_dev' in result
        assert 'threshold' in result
        assert result['mean'] > 0
        assert result['threshold'] > result['mean']
    
    def test_threshold_with_standard_deviation(self, test_tenant, test_site, metric_snapshots):
        """Test threshold uses mean + 2*std_dev formula."""
        result = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='cpu_usage',
            entity_type='server',
            entity_id='server_001',
            lookback_days=7,
            std_dev_multiplier=2.0
        )
        
        expected_threshold = result['mean'] + (2.0 * result['std_dev'])
        assert abs(result['threshold'] - expected_threshold) < 0.01
    
    def test_threshold_with_insufficient_data(self, test_tenant, test_site):
        """Test threshold calculation with insufficient historical data."""
        # Only create 2 data points
        base_time = timezone.now() - timedelta(hours=2)
        for hour in range(2):
            NOCMetricSnapshot.objects.create(
                client=test_tenant,
                bu=test_site,
                metric_name='memory_usage',
                metric_value=Decimal('75.0'),
                entity_type='server',
                entity_id='server_002',
                timestamp=base_time + timedelta(hours=hour)
            )
        
        result = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='memory_usage',
            entity_type='server',
            entity_id='server_002',
            lookback_days=7
        )
        
        # Should return a default threshold or indicate insufficient data
        assert 'insufficient_data' in result or result['threshold'] > 0
    
    def test_threshold_with_no_data(self, test_tenant, test_site):
        """Test threshold calculation with no historical data."""
        result = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='nonexistent_metric',
            entity_type='server',
            entity_id='server_999',
            lookback_days=7
        )
        
        # Should return default or null threshold
        assert result is None or 'default_threshold' in result


@pytest.mark.django_db
class TestAnomalyDetection:
    """Test anomaly detection algorithms."""
    
    def test_detect_anomaly_above_threshold(
        self, test_tenant, test_site, metric_snapshots
    ):
        """Test detection of value significantly above threshold."""
        # Calculate threshold from normal data
        threshold_data = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='cpu_usage',
            entity_type='server',
            entity_id='server_001',
            lookback_days=7
        )
        
        # Create anomalous data point (much higher than normal)
        anomalous_value = Decimal('95.0')  # Normal is around 50
        
        is_anomaly = DynamicThresholdService.is_anomaly(
            value=anomalous_value,
            threshold=threshold_data['threshold']
        )
        
        assert is_anomaly is True
    
    def test_normal_value_not_anomaly(
        self, test_tenant, test_site, metric_snapshots
    ):
        """Test normal values are not flagged as anomalies."""
        threshold_data = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='cpu_usage',
            entity_type='server',
            entity_id='server_001',
            lookback_days=7
        )
        
        # Normal value
        normal_value = Decimal('52.0')
        
        is_anomaly = DynamicThresholdService.is_anomaly(
            value=normal_value,
            threshold=threshold_data['threshold']
        )
        
        assert is_anomaly is False
    
    def test_detect_sudden_spike(self, test_tenant, test_site):
        """Test detection of sudden spike in metric."""
        base_time = timezone.now() - timedelta(hours=5)
        
        # Create gradual increase
        for hour in range(5):
            value = 50 + (hour * 2)  # Slow increase
            NOCMetricSnapshot.objects.create(
                client=test_tenant,
                bu=test_site,
                metric_name='disk_usage',
                metric_value=Decimal(str(value)),
                entity_type='server',
                entity_id='server_003',
                timestamp=base_time + timedelta(hours=hour)
            )
        
        # Create sudden spike
        spike_value = Decimal('95.0')
        
        is_spike = DynamicThresholdService.detect_spike(
            client=test_tenant,
            bu=test_site,
            metric_name='disk_usage',
            entity_type='server',
            entity_id='server_003',
            current_value=spike_value,
            spike_threshold=1.5  # 50% increase
        )
        
        assert is_spike is True
    
    def test_gradual_increase_not_spike(self, test_tenant, test_site):
        """Test gradual increase is not flagged as spike."""
        base_time = timezone.now() - timedelta(hours=5)
        
        # Create gradual increase
        for hour in range(5):
            value = 50 + (hour * 2)
            NOCMetricSnapshot.objects.create(
                client=test_tenant,
                bu=test_site,
                metric_name='network_traffic',
                metric_value=Decimal(str(value)),
                entity_type='server',
                entity_id='server_004',
                timestamp=base_time + timedelta(hours=hour)
            )
        
        # Next value continues gradual increase
        next_value = Decimal('60.0')
        
        is_spike = DynamicThresholdService.detect_spike(
            client=test_tenant,
            bu=test_site,
            metric_name='network_traffic',
            entity_type='server',
            entity_id='server_004',
            current_value=next_value,
            spike_threshold=1.5
        )
        
        assert is_spike is False


@pytest.mark.django_db
class TestAdaptiveThresholdAdjustment:
    """Test adaptive threshold adjustment."""
    
    def test_threshold_adjusts_with_new_data(
        self, test_tenant, test_site, metric_snapshots
    ):
        """Test threshold adapts when data pattern changes."""
        # Calculate initial threshold
        initial_threshold = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='cpu_usage',
            entity_type='server',
            entity_id='server_001',
            lookback_days=7
        )
        
        # Add new data with higher baseline (simulating load increase)
        base_time = timezone.now()
        for hour in range(24):
            high_value = 75 + (hour % 3) * 5  # New baseline around 75-80
            NOCMetricSnapshot.objects.create(
                client=test_tenant,
                bu=test_site,
                metric_name='cpu_usage',
                metric_value=Decimal(str(high_value)),
                entity_type='server',
                entity_id='server_001',
                timestamp=base_time + timedelta(hours=hour)
            )
        
        # Recalculate threshold
        new_threshold = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='cpu_usage',
            entity_type='server',
            entity_id='server_001',
            lookback_days=1  # Only look at recent data
        )
        
        # New threshold should be higher
        assert new_threshold['threshold'] > initial_threshold['threshold']
    
    def test_threshold_learning_rate(self, test_tenant, test_site):
        """Test threshold adjusts gradually, not abruptly."""
        base_time = timezone.now() - timedelta(days=7)
        
        # Create baseline data
        for day in range(7):
            for hour in range(6):  # 6 data points per day
                value = 50
                NOCMetricSnapshot.objects.create(
                    client=test_tenant,
                    bu=test_site,
                    metric_name='response_time',
                    metric_value=Decimal(str(value)),
                    entity_type='api',
                    entity_id='api_001',
                    timestamp=base_time + timedelta(days=day, hours=hour)
                )
        
        initial = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='response_time',
            entity_type='api',
            entity_id='api_001',
            lookback_days=7
        )
        
        # Add one anomalous day
        anomaly_time = timezone.now()
        for hour in range(6):
            value = 100  # Double the normal
            NOCMetricSnapshot.objects.create(
                client=test_tenant,
                bu=test_site,
                metric_name='response_time',
                metric_value=Decimal(str(value)),
                entity_type='api',
                entity_id='api_001',
                timestamp=anomaly_time + timedelta(hours=hour)
            )
        
        adjusted = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='response_time',
            entity_type='api',
            entity_id='api_001',
            lookback_days=7
        )
        
        # Threshold should increase but not double
        assert adjusted['threshold'] > initial['threshold']
        assert adjusted['threshold'] < initial['threshold'] * 2


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and data quality issues."""
    
    def test_handles_null_values(self, test_tenant, test_site):
        """Test handling of null/missing values in data."""
        base_time = timezone.now() - timedelta(days=1)
        
        # Mix of valid and null values
        for hour in range(10):
            value = Decimal('50.0') if hour % 2 == 0 else None
            if value is not None:
                NOCMetricSnapshot.objects.create(
                    client=test_tenant,
                    bu=test_site,
                    metric_name='availability',
                    metric_value=value,
                    entity_type='service',
                    entity_id='service_001',
                    timestamp=base_time + timedelta(hours=hour)
                )
        
        result = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='availability',
            entity_type='service',
            entity_id='service_001',
            lookback_days=1
        )
        
        # Should handle gracefully
        assert result is not None
        assert result['mean'] > 0
    
    def test_handles_zero_variance(self, test_tenant, test_site):
        """Test handling of data with zero variance."""
        base_time = timezone.now() - timedelta(hours=10)
        
        # All same value
        for hour in range(10):
            NOCMetricSnapshot.objects.create(
                client=test_tenant,
                bu=test_site,
                metric_name='constant_metric',
                metric_value=Decimal('42.0'),
                entity_type='sensor',
                entity_id='sensor_001',
                timestamp=base_time + timedelta(hours=hour)
            )
        
        result = DynamicThresholdService.calculate_threshold(
            client=test_tenant,
            bu=test_site,
            metric_name='constant_metric',
            entity_type='sensor',
            entity_id='sensor_001',
            lookback_days=1
        )
        
        # Should set reasonable threshold even with zero variance
        assert result['std_dev'] == 0
        assert result['threshold'] >= result['mean']
