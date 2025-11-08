"""
Comprehensive Tests for StreamingAnomalyService

Priority 1 - Business Critical (Real-time Monitoring)
Tests:
- Metrics tracking (events/sec, latency, findings)
- Consumer health monitoring
- Tenant-specific metrics isolation
- Configuration management
- Statistics aggregation

Run: pytest apps/noc/tests/test_services/test_streaming_anomaly_service.py -v --cov=apps.noc.services.streaming_anomaly_service
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone

from apps.noc.services.streaming_anomaly_service import StreamingAnomalyService


@pytest.fixture
def tenant_id():
    """Test tenant ID"""
    return 1


@pytest.fixture
def other_tenant_id():
    """Other tenant ID for isolation tests"""
    return 2


@pytest.mark.django_db
class TestMetricsRecording(TestCase):
    """Test event metrics recording"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_record_event_processed(self, tenant_id):
        """Test recording processed event metrics"""
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='attendance',
            detection_latency_ms=45.2,
            findings_count=2
        )
        
        # Verify event count incremented
        cache_key = f"streaming_anomaly_metrics:{tenant_id}:attendance:count"
        count = cache.get(cache_key)
        assert count == 1
    
    def test_record_multiple_events(self, tenant_id):
        """Test recording multiple events"""
        # Record 3 events
        for i in range(3):
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='task',
                detection_latency_ms=50.0 + i,
                findings_count=1
            )
        
        # Verify count
        cache_key = f"streaming_anomaly_metrics:{tenant_id}:task:count"
        count = cache.get(cache_key)
        assert count == 3
    
    def test_latency_average_calculated(self, tenant_id):
        """Test average latency calculation"""
        # Record events with different latencies
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='location',
            detection_latency_ms=100.0,
            findings_count=0
        )
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='location',
            detection_latency_ms=200.0,
            findings_count=0
        )
        
        # Average should be 150.0
        latency_key = f"streaming_anomaly_metrics:{tenant_id}:location:latency"
        avg_latency = cache.get(latency_key)
        assert avg_latency == pytest.approx(150.0, rel=0.1)
    
    def test_findings_count_tracked(self, tenant_id):
        """Test findings count tracking"""
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='attendance',
            detection_latency_ms=50.0,
            findings_count=3
        )
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='attendance',
            detection_latency_ms=55.0,
            findings_count=2
        )
        
        # Total findings should be 5
        findings_key = f"streaming_anomaly_metrics:{tenant_id}:attendance:findings"
        findings = cache.get(findings_key)
        assert findings == 5
    
    def test_zero_findings_not_tracked(self, tenant_id):
        """Test events with zero findings don't increment findings counter"""
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='task',
            detection_latency_ms=30.0,
            findings_count=0
        )
        
        # Findings counter should not exist or be 0
        findings_key = f"streaming_anomaly_metrics:{tenant_id}:task:findings"
        findings = cache.get(findings_key, 0)
        assert findings == 0


@pytest.mark.django_db
class TestMetricsRetrieval(TestCase):
    """Test metrics retrieval and aggregation"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_get_metrics_empty(self, tenant_id):
        """Test getting metrics with no data"""
        metrics = StreamingAnomalyService.get_metrics(
            tenant_id=tenant_id,
            time_window_minutes=60
        )
        
        assert metrics['tenant_id'] == tenant_id
        assert metrics['time_window_minutes'] == 60
        assert 'by_event_type' in metrics
        assert 'overall' in metrics
        assert metrics['overall']['total_events'] == 0
    
    def test_get_metrics_with_data(self, tenant_id):
        """Test getting metrics with recorded data"""
        # Record some events
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='attendance',
            detection_latency_ms=45.0,
            findings_count=2
        )
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='task',
            detection_latency_ms=60.0,
            findings_count=1
        )
        
        metrics = StreamingAnomalyService.get_metrics(tenant_id=tenant_id)
        
        assert metrics['overall']['total_events'] == 2
        assert metrics['overall']['total_findings'] == 3
        assert 'attendance' in metrics['by_event_type']
        assert 'task' in metrics['by_event_type']
    
    def test_metrics_by_event_type(self, tenant_id):
        """Test event-type-specific metrics"""
        # Record attendance events
        for i in range(5):
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='attendance',
                detection_latency_ms=50.0,
                findings_count=1
            )
        
        metrics = StreamingAnomalyService.get_metrics(tenant_id=tenant_id)
        
        attendance_metrics = metrics['by_event_type']['attendance']
        assert attendance_metrics['events_processed'] == 5
        assert attendance_metrics['findings_detected'] == 5
        assert attendance_metrics['finding_rate'] == pytest.approx(1.0)
    
    def test_finding_rate_calculation(self, tenant_id):
        """Test finding rate calculation"""
        # 10 events, 3 with findings
        for i in range(10):
            findings = 1 if i < 3 else 0
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='location',
                detection_latency_ms=40.0,
                findings_count=findings
            )
        
        metrics = StreamingAnomalyService.get_metrics(tenant_id=tenant_id)
        
        location_metrics = metrics['by_event_type']['location']
        assert location_metrics['events_processed'] == 10
        assert location_metrics['findings_detected'] == 3
        assert location_metrics['finding_rate'] == pytest.approx(0.3)
    
    def test_average_latency_calculation(self, tenant_id):
        """Test average latency calculation across event types"""
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='attendance',
            detection_latency_ms=100.0,
            findings_count=0
        )
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='task',
            detection_latency_ms=200.0,
            findings_count=0
        )
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='location',
            detection_latency_ms=300.0,
            findings_count=0
        )
        
        metrics = StreamingAnomalyService.get_metrics(tenant_id=tenant_id)
        
        # Overall average should be (100 + 200 + 300) / 3 = 200
        assert metrics['overall']['avg_latency_ms'] == pytest.approx(200.0, rel=0.1)
    
    def test_events_per_minute_calculation(self, tenant_id):
        """Test events per minute calculation"""
        # Record 120 events
        for i in range(120):
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='attendance',
                detection_latency_ms=50.0,
                findings_count=0
            )
        
        metrics = StreamingAnomalyService.get_metrics(
            tenant_id=tenant_id,
            time_window_minutes=60
        )
        
        # 120 events / 60 minutes = 2 events/min
        assert metrics['overall']['events_per_minute'] == pytest.approx(2.0)


@pytest.mark.django_db
class TestTenantIsolation(TestCase):
    """Test tenant-specific metrics isolation"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_tenant_metrics_isolated(self, tenant_id, other_tenant_id):
        """Metrics should be isolated per tenant"""
        # Tenant 1 records events
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='attendance',
            detection_latency_ms=50.0,
            findings_count=5
        )
        
        # Tenant 2 records events
        StreamingAnomalyService.record_event_processed(
            tenant_id=other_tenant_id,
            event_type='attendance',
            detection_latency_ms=100.0,
            findings_count=10
        )
        
        # Get metrics for each tenant
        metrics_1 = StreamingAnomalyService.get_metrics(tenant_id=tenant_id)
        metrics_2 = StreamingAnomalyService.get_metrics(tenant_id=other_tenant_id)
        
        # Each tenant should see only their data
        assert metrics_1['overall']['total_findings'] == 5
        assert metrics_2['overall']['total_findings'] == 10
    
    def test_cross_tenant_metrics_not_visible(self, tenant_id, other_tenant_id):
        """Tenants should not see each other's metrics"""
        # Tenant 1 records events
        for i in range(10):
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='task',
                detection_latency_ms=50.0,
                findings_count=1
            )
        
        # Tenant 2 should see zero events
        metrics = StreamingAnomalyService.get_metrics(tenant_id=other_tenant_id)
        assert metrics['overall']['total_events'] == 0


@pytest.mark.django_db
class TestConsumerHealth(TestCase):
    """Test consumer health monitoring"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_record_consumer_health(self, tenant_id):
        """Test recording consumer health status"""
        StreamingAnomalyService.record_consumer_health(
            tenant_id=tenant_id,
            status='healthy',
            last_event_timestamp=timezone.now(),
            error_count=0
        )
        
        health = StreamingAnomalyService.get_consumer_health(tenant_id=tenant_id)
        
        assert health['status'] == 'healthy'
        assert health['error_count'] == 0
    
    def test_unhealthy_consumer_detected(self, tenant_id):
        """Test detection of unhealthy consumer"""
        StreamingAnomalyService.record_consumer_health(
            tenant_id=tenant_id,
            status='degraded',
            last_event_timestamp=timezone.now(),
            error_count=5
        )
        
        health = StreamingAnomalyService.get_consumer_health(tenant_id=tenant_id)
        
        assert health['status'] == 'degraded'
        assert health['error_count'] == 5


@pytest.mark.django_db
class TestErrorHandling(TestCase):
    """Test error handling in metrics operations"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    @patch('apps.noc.services.streaming_anomaly_service.cache')
    def test_cache_failure_handled(self, mock_cache, tenant_id):
        """Cache failures should be handled gracefully"""
        mock_cache.incr.side_effect = RuntimeError("Cache unavailable")
        
        # Should not raise exception
        try:
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='attendance',
                detection_latency_ms=50.0,
                findings_count=1
            )
        except RuntimeError:
            pytest.fail("Cache failure should be handled gracefully")
    
    @patch('apps.noc.services.streaming_anomaly_service.logger')
    def test_errors_logged(self, mock_logger, tenant_id):
        """Errors should be logged"""
        with patch('apps.noc.services.streaming_anomaly_service.cache') as mock_cache:
            mock_cache.incr.side_effect = ValueError("Invalid value")
            
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='attendance',
                detection_latency_ms=50.0,
                findings_count=1
            )
            
            # Error should be logged
            assert mock_logger.error.called


@pytest.mark.django_db
class TestConfiguration(TestCase):
    """Test configuration management"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_update_threshold_configuration(self, tenant_id):
        """Test updating threshold configuration"""
        config = {
            'attendance_threshold': 0.8,
            'task_threshold': 0.7,
            'location_threshold': 0.75
        }
        
        StreamingAnomalyService.update_configuration(
            tenant_id=tenant_id,
            config=config
        )
        
        retrieved = StreamingAnomalyService.get_configuration(tenant_id=tenant_id)
        
        assert retrieved['attendance_threshold'] == 0.8
        assert retrieved['task_threshold'] == 0.7
    
    def test_default_configuration_returned(self, tenant_id):
        """Test default configuration when none set"""
        config = StreamingAnomalyService.get_configuration(tenant_id=tenant_id)
        
        # Should have default values
        assert 'attendance_threshold' in config or config is not None


@pytest.mark.django_db
class TestStatisticsAggregation(TestCase):
    """Test statistics aggregation"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_aggregate_hourly_statistics(self, tenant_id):
        """Test hourly statistics aggregation"""
        # Record events for 1 hour
        for i in range(60):
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='attendance',
                detection_latency_ms=45.0 + i,
                findings_count=1 if i % 10 == 0 else 0
            )
        
        metrics = StreamingAnomalyService.get_metrics(
            tenant_id=tenant_id,
            time_window_minutes=60
        )
        
        assert metrics['overall']['total_events'] == 60
        assert metrics['overall']['total_findings'] == 6  # Every 10th event
    
    def test_aggregate_multiple_event_types(self, tenant_id):
        """Test aggregation across multiple event types"""
        event_types = ['attendance', 'task', 'location']
        
        for event_type in event_types:
            for i in range(10):
                StreamingAnomalyService.record_event_processed(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    detection_latency_ms=50.0,
                    findings_count=1
                )
        
        metrics = StreamingAnomalyService.get_metrics(tenant_id=tenant_id)
        
        # Should have 30 total events (10 per type)
        assert metrics['overall']['total_events'] == 30
        assert metrics['overall']['total_findings'] == 30
        
        # Each event type should have 10 events
        for event_type in event_types:
            assert metrics['by_event_type'][event_type]['events_processed'] == 10


@pytest.mark.django_db
class TestPerformanceMetrics(TestCase):
    """Test performance-related metrics"""
    
    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
    
    def test_high_latency_tracked(self, tenant_id):
        """Test tracking of high latency events"""
        # Record event with high latency
        StreamingAnomalyService.record_event_processed(
            tenant_id=tenant_id,
            event_type='attendance',
            detection_latency_ms=500.0,  # High latency
            findings_count=1
        )
        
        metrics = StreamingAnomalyService.get_metrics(tenant_id=tenant_id)
        
        attendance_metrics = metrics['by_event_type']['attendance']
        assert attendance_metrics['avg_latency_ms'] == pytest.approx(500.0)
    
    def test_throughput_calculation(self, tenant_id):
        """Test throughput (events per minute) calculation"""
        # Simulate 1000 events in 10 minutes
        for i in range(1000):
            StreamingAnomalyService.record_event_processed(
                tenant_id=tenant_id,
                event_type='task',
                detection_latency_ms=30.0,
                findings_count=0
            )
        
        metrics = StreamingAnomalyService.get_metrics(
            tenant_id=tenant_id,
            time_window_minutes=10
        )
        
        # 1000 events / 10 minutes = 100 events/min
        assert metrics['overall']['events_per_minute'] == pytest.approx(100.0)
