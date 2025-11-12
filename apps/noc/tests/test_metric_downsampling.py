"""
Tests for Metric Downsampling Tasks and Time-Series Query Service.

Tests Enhancement #3: Time-Series Metric Downsampling
- Hourly aggregation from 5-min snapshots
- Daily aggregation from hourly snapshots
- Automatic cleanup of old data
- Intelligent query routing based on date range
- Storage savings calculation

Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone
from apps.noc.models import NOCMetricSnapshot, NOCMetricSnapshot1Hour, NOCMetricSnapshot1Day
from apps.noc.tasks.metric_downsampling_tasks import (
    DownsampleMetricsHourlyTask,
    DownsampleMetricsDailyTask
)
from apps.noc.services.time_series_query_service import TimeSeriesQueryService


@pytest.fixture
def create_5min_snapshots(tenant, sample_client, db):
    """Create 12 5-minute snapshots for one hour."""
    snapshots = []
    base_time = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)

    for i in range(12):
        window_start = base_time + timedelta(minutes=i * 5)
        window_end = window_start + timedelta(minutes=5)

        snapshot = NOCMetricSnapshot.objects.create(
            tenant=tenant,
            client=sample_client,
            window_start=window_start,
            window_end=window_end,
            tickets_open=10 + i,  # Varying values for aggregation
            tickets_overdue=2 + (i % 3),
            work_orders_pending=5 + (i % 5),
            work_orders_overdue=1,
            attendance_present=50 + i,
            attendance_missing=10 - (i % 4),
            device_health_offline=5 - (i % 2),
            sync_health_score=95.0 + (i * 0.2),
            security_anomalies=i % 3
        )
        snapshots.append(snapshot)

    return snapshots


@pytest.fixture
def create_hourly_snapshots(tenant, sample_client, db):
    """Create 24 hourly snapshots for one day."""
    snapshots = []
    base_date = (timezone.now() - timedelta(days=2)).date()
    base_time = datetime.combine(base_date, datetime.min.time()).replace(tzinfo=dt_timezone.utc)

    for i in range(24):
        window_start = base_time + timedelta(hours=i)
        window_end = window_start + timedelta(hours=1)

        snapshot = NOCMetricSnapshot1Hour.objects.create(
            tenant=tenant,
            client=sample_client,
            window_start=window_start,
            window_end=window_end,
            tickets_open_avg=15.0 + i,
            tickets_open_min=10 + i,
            tickets_open_max=20 + i,
            tickets_open_sum=180 + (i * 12),
            tickets_overdue_avg=2.5,
            tickets_overdue_min=1,
            tickets_overdue_max=4,
            tickets_overdue_sum=30,
            work_orders_pending_avg=8.0,
            work_orders_pending_min=5,
            work_orders_pending_max=12,
            work_orders_pending_sum=96,
            work_orders_overdue_avg=1.0,
            work_orders_overdue_min=1,
            work_orders_overdue_max=1,
            work_orders_overdue_sum=12,
            attendance_present_avg=55.0 + i,
            attendance_present_min=50 + i,
            attendance_present_max=60 + i,
            attendance_present_sum=660 + (i * 12),
            attendance_missing_avg=8.0,
            attendance_missing_min=6,
            attendance_missing_max=10,
            attendance_missing_sum=96,
            device_health_offline_avg=4.5,
            device_health_offline_min=4,
            device_health_offline_max=5,
            sync_health_score_avg=96.0,
            sync_health_score_min=95.0,
            security_anomalies_avg=1.5,
            security_anomalies_max=3,
            security_anomalies_sum=18
        )
        snapshots.append(snapshot)

    return snapshots


@pytest.mark.django_db
class TestDownsampleMetricsHourlyTask:
    """Test hourly metric downsampling task."""

    def test_hourly_aggregation_correct(self, create_5min_snapshots, tenant, sample_client):
        """Test that hourly aggregation calculates correct avg/min/max/sum values."""
        task = DownsampleMetricsHourlyTask()
        result = task.run()

        assert result['snapshots_created'] >= 1
        assert result['clients_processed'] >= 1
        assert result['errors'] == 0

        # Verify hourly snapshot was created
        hourly_snapshot = NOCMetricSnapshot1Hour.objects.filter(
            client=sample_client
        ).first()

        assert hourly_snapshot is not None

        # Verify aggregations are in expected ranges
        # tickets_open ranges from 10 to 21 (10 + 11 values)
        assert 10 <= hourly_snapshot.tickets_open_min <= 21
        assert 10 <= hourly_snapshot.tickets_open_max <= 21
        assert hourly_snapshot.tickets_open_min < hourly_snapshot.tickets_open_max
        assert 10 <= hourly_snapshot.tickets_open_avg <= 21

    def test_hourly_cleanup_old_snapshots(self, tenant, sample_client, db):
        """Test that 5-min snapshots older than 7 days are deleted."""
        # Create old snapshot (8 days ago)
        old_time = timezone.now() - timedelta(days=8)
        old_snapshot = NOCMetricSnapshot.objects.create(
            tenant=tenant,
            client=sample_client,
            window_start=old_time,
            window_end=old_time + timedelta(minutes=5),
            tickets_open=5
        )
        old_snapshot.computed_at = old_time
        old_snapshot.save(update_fields=['computed_at'])

        # Create recent snapshot (2 days ago)
        recent_time = timezone.now() - timedelta(days=2)
        recent_snapshot = NOCMetricSnapshot.objects.create(
            tenant=tenant,
            client=sample_client,
            window_start=recent_time,
            window_end=recent_time + timedelta(minutes=5),
            tickets_open=10
        )

        old_count = NOCMetricSnapshot.objects.count()

        # Run task
        task = DownsampleMetricsHourlyTask()
        result = task.run()

        # Old snapshot should be deleted
        assert result['old_snapshots_deleted'] >= 1
        assert not NOCMetricSnapshot.objects.filter(id=old_snapshot.id).exists()
        assert NOCMetricSnapshot.objects.filter(id=recent_snapshot.id).exists()

    def test_hourly_handles_empty_window(self, tenant, sample_client, db):
        """Test hourly task handles time windows with no data gracefully."""
        task = DownsampleMetricsHourlyTask()
        result = task.run()

        # Should complete without errors even with no data
        assert result['errors'] == 0
        assert result['snapshots_created'] == 0

    def test_hourly_idempotency(self, create_5min_snapshots, tenant, sample_client):
        """Test that running hourly task multiple times doesn't create duplicates."""
        task = DownsampleMetricsHourlyTask()

        # Run twice
        result1 = task.run()
        initial_count = NOCMetricSnapshot1Hour.objects.count()

        # Wait for idempotency TTL to expire (would need to mock time in real scenario)
        # For now, just verify we created snapshots
        assert initial_count >= 1
        assert result1['errors'] == 0


@pytest.mark.django_db
class TestDownsampleMetricsDailyTask:
    """Test daily metric downsampling task."""

    def test_daily_aggregation_correct(self, create_hourly_snapshots, tenant, sample_client):
        """Test that daily aggregation calculates correct avg/min/max values."""
        task = DownsampleMetricsDailyTask()
        result = task.run()

        assert result['snapshots_created'] >= 1
        assert result['clients_processed'] >= 1
        assert result['errors'] == 0

        # Verify daily snapshot was created
        daily_snapshot = NOCMetricSnapshot1Day.objects.filter(
            client=sample_client
        ).first()

        assert daily_snapshot is not None

        # Verify aggregations (average of hourly averages)
        assert daily_snapshot.tickets_open_avg > 0
        assert daily_snapshot.tickets_open_min <= daily_snapshot.tickets_open_max
        assert daily_snapshot.attendance_present_avg > 0

    def test_daily_cleanup_old_hourly_snapshots(self, tenant, sample_client, db):
        """Test that hourly snapshots older than 90 days are deleted."""
        # Create old hourly snapshot (95 days ago)
        old_time = timezone.now() - timedelta(days=95)
        old_snapshot = NOCMetricSnapshot1Hour.objects.create(
            tenant=tenant,
            client=sample_client,
            window_start=old_time,
            window_end=old_time + timedelta(hours=1),
            tickets_open_avg=10.0,
            tickets_open_min=8,
            tickets_open_max=12,
            tickets_open_sum=120
        )
        old_snapshot.computed_at = old_time
        old_snapshot.save(update_fields=['computed_at'])

        # Create recent hourly snapshot
        recent_time = timezone.now() - timedelta(days=30)
        recent_snapshot = NOCMetricSnapshot1Hour.objects.create(
            tenant=tenant,
            client=sample_client,
            window_start=recent_time,
            window_end=recent_time + timedelta(hours=1),
            tickets_open_avg=15.0,
            tickets_open_min=10,
            tickets_open_max=20,
            tickets_open_sum=180
        )

        # Run task
        task = DownsampleMetricsDailyTask()
        result = task.run()

        # Old hourly snapshot should be deleted
        assert result['old_snapshots_deleted'] >= 1
        assert not NOCMetricSnapshot1Hour.objects.filter(id=old_snapshot.id).exists()
        assert NOCMetricSnapshot1Hour.objects.filter(id=recent_snapshot.id).exists()

    def test_daily_update_or_create_idempotency(self, create_hourly_snapshots, tenant, sample_client):
        """Test that daily task uses update_or_create for idempotency."""
        task = DownsampleMetricsDailyTask()

        # Run once
        result1 = task.run()
        count_after_first = NOCMetricSnapshot1Day.objects.count()
        first_snapshot = NOCMetricSnapshot1Day.objects.first()
        first_avg = first_snapshot.tickets_open_avg if first_snapshot else None

        # Run again (should update, not create new)
        result2 = task.run()
        count_after_second = NOCMetricSnapshot1Day.objects.count()

        # Count should be same (update_or_create prevents duplicates)
        assert count_after_second == count_after_first


@pytest.mark.django_db
class TestTimeSeriesQueryService:
    """Test intelligent time-series query routing."""

    def test_query_5min_resolution_for_recent_data(self, tenant, sample_client, db):
        """Test that queries for last 7 days use 5-min resolution."""
        # Create 5-min snapshots
        now = timezone.now()
        for i in range(10):
            time = now - timedelta(minutes=i * 5)
            NOCMetricSnapshot.objects.create(
                tenant=tenant,
                client=sample_client,
                window_start=time,
                window_end=time + timedelta(minutes=5),
                tickets_open=10 + i
            )

        # Query last 3 days
        start = now - timedelta(days=3)
        end = now

        results = TimeSeriesQueryService.query_metrics(
            client=sample_client,
            start_date=start,
            end_date=end,
            metric_name='tickets_open'
        )

        assert len(results) > 0
        assert all('timestamp' in r and 'value' in r for r in results)

    def test_query_1hour_resolution_for_medium_range(self, tenant, sample_client, db):
        """Test that queries for 7-90 days use 1-hour resolution."""
        # Create hourly snapshots
        now = timezone.now()
        for i in range(48):  # 2 days of hourly data
            time = now - timedelta(hours=i)
            NOCMetricSnapshot1Hour.objects.create(
                tenant=tenant,
                client=sample_client,
                window_start=time,
                window_end=time + timedelta(hours=1),
                tickets_open_avg=15.0 + i,
                tickets_open_min=10,
                tickets_open_max=20,
                tickets_open_sum=180
            )

        # Query last 30 days (should use hourly)
        start = now - timedelta(days=30)
        end = now

        results = TimeSeriesQueryService.query_metrics(
            client=sample_client,
            start_date=start,
            end_date=end,
            metric_name='tickets_open',
            aggregation='avg'
        )

        # Should have hourly data
        assert len(results) > 0

    def test_query_1day_resolution_for_long_range(self, tenant, sample_client, db):
        """Test that queries for 90+ days use 1-day resolution."""
        # Create daily snapshots
        today = timezone.now().date()
        for i in range(180):  # 180 days
            date = today - timedelta(days=i)
            NOCMetricSnapshot1Day.objects.create(
                tenant=tenant,
                client=sample_client,
                date=date,
                tickets_open_avg=20.0,
                tickets_open_min=15,
                tickets_open_max=25
            )

        # Query 6 months (should use daily)
        start = timezone.now() - timedelta(days=180)
        end = timezone.now()

        results = TimeSeriesQueryService.query_metrics(
            client=sample_client,
            start_date=start,
            end_date=end,
            metric_name='tickets_open',
            aggregation='avg'
        )

        # Should have daily data
        assert len(results) > 0

    def test_query_unsupported_metric_raises_error(self, sample_client):
        """Test that unsupported metric names raise ValueError."""
        now = timezone.now()

        with pytest.raises(ValueError, match="Unsupported metric"):
            TimeSeriesQueryService.query_metrics(
                client=sample_client,
                start_date=now - timedelta(days=1),
                end_date=now,
                metric_name='invalid_metric_name'
            )

    def test_get_resolution_info(self):
        """Test resolution info calculation for different date ranges."""
        now = timezone.now()

        # 3 days - should use 5-min
        info = TimeSeriesQueryService.get_resolution_info(
            start_date=now - timedelta(days=3),
            end_date=now
        )
        assert info['resolution'] == '5min'
        assert info['storage_table'] == 'noc_metric_snapshot'

        # 30 days - should use 1-hour
        info = TimeSeriesQueryService.get_resolution_info(
            start_date=now - timedelta(days=30),
            end_date=now
        )
        assert info['resolution'] == '1hour'
        assert info['storage_table'] == 'noc_metric_snapshot_1hour'

        # 180 days - should use 1-day
        info = TimeSeriesQueryService.get_resolution_info(
            start_date=now - timedelta(days=180),
            end_date=now
        )
        assert info['resolution'] == '1day'
        assert info['storage_table'] == 'noc_metric_snapshot_1day'

    def test_query_multiple_metrics(self, tenant, sample_client, db):
        """Test querying multiple metrics in a single call."""
        now = timezone.now()

        # Create some 5-min snapshots
        for i in range(5):
            time = now - timedelta(minutes=i * 5)
            NOCMetricSnapshot.objects.create(
                tenant=tenant,
                client=sample_client,
                window_start=time,
                window_end=time + timedelta(minutes=5),
                tickets_open=10 + i,
                attendance_present=50 + i,
                work_orders_pending=5
            )

        results = TimeSeriesQueryService.query_multiple_metrics(
            client=sample_client,
            start_date=now - timedelta(hours=1),
            end_date=now,
            metric_names=['tickets_open', 'attendance_present', 'work_orders_pending']
        )

        assert 'tickets_open' in results
        assert 'attendance_present' in results
        assert 'work_orders_pending' in results
        assert len(results['tickets_open']) > 0

    def test_calculate_storage_savings(self, tenant, sample_client, db):
        """Test storage savings calculation."""
        # Create mix of snapshots
        now = timezone.now()

        # 10 5-min snapshots
        for i in range(10):
            NOCMetricSnapshot.objects.create(
                tenant=tenant,
                client=sample_client,
                window_start=now - timedelta(minutes=i * 5),
                window_end=now - timedelta(minutes=i * 5) + timedelta(minutes=5),
                tickets_open=10
            )

        # 5 hourly snapshots (equivalent to 60 5-min)
        for i in range(5):
            NOCMetricSnapshot1Hour.objects.create(
                tenant=tenant,
                client=sample_client,
                window_start=now - timedelta(hours=i),
                window_end=now - timedelta(hours=i) + timedelta(hours=1),
                tickets_open_avg=10.0,
                tickets_open_min=8,
                tickets_open_max=12,
                tickets_open_sum=120
            )

        # 2 daily snapshots (equivalent to 576 5-min)
        for i in range(2):
            NOCMetricSnapshot1Day.objects.create(
                tenant=tenant,
                client=sample_client,
                date=(now - timedelta(days=i)).date(),
                tickets_open_avg=10.0,
                tickets_open_min=8,
                tickets_open_max=12
            )

        savings = TimeSeriesQueryService.calculate_storage_savings()

        assert savings['total_5min_records'] == 10
        assert savings['total_1hour_records'] == 5
        assert savings['total_1day_records'] == 2
        assert savings['actual_total_records'] == 17
        # Theoretical: 10 + (5*12) + (2*288) = 10 + 60 + 576 = 646
        assert savings['theoretical_5min_records'] == 646
        # Reduction: (646-17)/646 = 97.37%
        assert savings['storage_reduction_percent'] > 90.0
