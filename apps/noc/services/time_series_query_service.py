"""
Time-Series Query Service.

Intelligent query router for multi-resolution metric storage.
Automatically selects optimal resolution based on time range:
- Last 7 days: 5-minute resolution (highest granularity)
- 7-90 days: 1-hour resolution (medium granularity)
- 90+ days: 1-day resolution (trend analysis)

Returns unified data format regardless of underlying resolution.
Enables efficient querying of 2-year historical data with 90% storage savings.

@ontology(
    domain="noc",
    purpose="Intelligent time-series query routing with automatic resolution selection",
    query_strategy={
        "0-7 days": "5-minute snapshots",
        "7-90 days": "1-hour aggregates",
        "90+ days": "1-day aggregates"
    },
    tags=["noc", "metrics", "time-series", "query-optimization", "analytics"]
)

Follows .claude/rules.md Rule #12 (query optimization) and Rule #15 (service layer pattern).
"""

from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger('noc.time_series_query')

__all__ = ['TimeSeriesQueryService']


class TimeSeriesQueryService:
    """
    Intelligent query router for multi-resolution NOC metrics.

    Usage:
        # Query last 3 days (uses 5-min resolution)
        data = TimeSeriesQueryService.query_metrics(
            client=client,
            start_date=now - timedelta(days=3),
            end_date=now,
            metric_name='tickets_open'
        )

        # Query last 30 days (uses 1-hour resolution)
        data = TimeSeriesQueryService.query_metrics(
            client=client,
            start_date=now - timedelta(days=30),
            end_date=now,
            metric_name='attendance_present'
        )

        # Query 6 months (uses 1-day resolution)
        data = TimeSeriesQueryService.query_metrics(
            client=client,
            start_date=now - timedelta(days=180),
            end_date=now,
            metric_name='work_orders_pending'
        )
    """

    RESOLUTION_5MIN_DAYS = 7
    RESOLUTION_1HOUR_DAYS = 90

    # Metrics available in all resolutions
    SUPPORTED_METRICS = [
        'tickets_open',
        'tickets_overdue',
        'work_orders_pending',
        'work_orders_overdue',
        'attendance_present',
        'attendance_missing',
        'device_health_offline',
        'sync_health_score',
        'security_anomalies',
    ]

    @classmethod
    def query_metrics(
        cls,
        client,
        start_date: datetime,
        end_date: datetime,
        metric_name: str,
        aggregation: str = 'avg',
        bu=None,
        oic=None
    ) -> List[Dict[str, Any]]:
        """
        Query metrics with automatic resolution selection.

        Args:
            client: Client (Bt) instance
            start_date: Query start datetime (inclusive)
            end_date: Query end datetime (inclusive)
            metric_name: Base metric name (e.g., 'tickets_open')
            aggregation: Aggregation type for downsampled data ('avg', 'min', 'max')
            bu: Optional business unit filter
            oic: Optional officer-in-charge filter

        Returns:
            List of dicts with 'timestamp' and 'value' keys:
                [
                    {'timestamp': datetime, 'value': 42.5},
                    {'timestamp': datetime, 'value': 38.0},
                    ...
                ]

        Raises:
            ValueError: If metric_name is not supported
        """
        if metric_name not in cls.SUPPORTED_METRICS:
            raise ValueError(
                f"Unsupported metric: {metric_name}. "
                f"Supported metrics: {', '.join(cls.SUPPORTED_METRICS)}"
            )

        if aggregation not in ['avg', 'min', 'max']:
            raise ValueError(f"Unsupported aggregation: {aggregation}. Use 'avg', 'min', or 'max'")

        # Calculate date range
        days = (end_date - start_date).days

        # Select resolution and query
        if days <= cls.RESOLUTION_5MIN_DAYS:
            return cls._query_5min(client, start_date, end_date, metric_name, bu, oic)
        elif days <= cls.RESOLUTION_1HOUR_DAYS:
            return cls._query_1hour(client, start_date, end_date, metric_name, aggregation, bu, oic)
        else:
            return cls._query_1day(client, start_date, end_date, metric_name, aggregation, bu, oic)

    @classmethod
    def _query_5min(
        cls,
        client,
        start_date: datetime,
        end_date: datetime,
        metric_name: str,
        bu=None,
        oic=None
    ) -> List[Dict[str, Any]]:
        """Query 5-minute resolution snapshots."""
        from apps.noc.models import NOCMetricSnapshot

        logger.debug(
            f"Querying 5-min resolution for {client.buname}: "
            f"{start_date} to {end_date}, metric={metric_name}"
        )

        filters = Q(
            client=client,
            window_start__gte=start_date,
            window_start__lte=end_date
        )

        if bu:
            filters &= Q(bu=bu)
        if oic:
            filters &= Q(oic=oic)

        snapshots = NOCMetricSnapshot.objects.filter(filters).values(
            'window_start',
            metric_name
        ).order_by('window_start')

        return [
            {
                'timestamp': snapshot['window_start'],
                'value': snapshot[metric_name]
            }
            for snapshot in snapshots
        ]

    @classmethod
    def _query_1hour(
        cls,
        client,
        start_date: datetime,
        end_date: datetime,
        metric_name: str,
        aggregation: str,
        bu=None,
        oic=None
    ) -> List[Dict[str, Any]]:
        """Query 1-hour resolution snapshots."""
        from apps.noc.models import NOCMetricSnapshot1Hour

        logger.debug(
            f"Querying 1-hour resolution for {client.buname}: "
            f"{start_date} to {end_date}, metric={metric_name}_{aggregation}"
        )

        filters = Q(
            client=client,
            window_start__gte=start_date,
            window_start__lte=end_date
        )

        if bu:
            filters &= Q(bu=bu)
        if oic:
            filters &= Q(oic=oic)

        # Build field name with aggregation suffix
        field_name = f'{metric_name}_{aggregation}'

        snapshots = NOCMetricSnapshot1Hour.objects.filter(filters).values(
            'window_start',
            field_name
        ).order_by('window_start')

        return [
            {
                'timestamp': snapshot['window_start'],
                'value': snapshot[field_name]
            }
            for snapshot in snapshots
        ]

    @classmethod
    def _query_1day(
        cls,
        client,
        start_date: datetime,
        end_date: datetime,
        metric_name: str,
        aggregation: str,
        bu=None,
        oic=None
    ) -> List[Dict[str, Any]]:
        """Query 1-day resolution snapshots."""
        from apps.noc.models import NOCMetricSnapshot1Day

        logger.debug(
            f"Querying 1-day resolution for {client.buname}: "
            f"{start_date.date()} to {end_date.date()}, metric={metric_name}_{aggregation}"
        )

        filters = Q(
            client=client,
            date__gte=start_date.date(),
            date__lte=end_date.date()
        )

        if bu:
            filters &= Q(bu=bu)

        # Build field name with aggregation suffix
        field_name = f'{metric_name}_{aggregation}'

        snapshots = NOCMetricSnapshot1Day.objects.filter(filters).values(
            'date',
            field_name
        ).order_by('date')

        return [
            {
                'timestamp': datetime.combine(snapshot['date'], datetime.min.time()).replace(
                    tzinfo=timezone.get_current_timezone()
                ),
                'value': snapshot[field_name]
            }
            for snapshot in snapshots
        ]

    @classmethod
    def get_resolution_info(cls, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Get information about which resolution will be used for a date range.

        Args:
            start_date: Query start datetime
            end_date: Query end datetime

        Returns:
            Dict with resolution details:
                {
                    'resolution': '5min' | '1hour' | '1day',
                    'expected_data_points': int,
                    'storage_table': str,
                    'days': int
                }
        """
        days = (end_date - start_date).days

        if days <= cls.RESOLUTION_5MIN_DAYS:
            # 5-min resolution: 12 per hour × 24 hours × days
            expected_points = 12 * 24 * max(days, 1)
            return {
                'resolution': '5min',
                'expected_data_points': expected_points,
                'storage_table': 'noc_metric_snapshot',
                'days': days
            }
        elif days <= cls.RESOLUTION_1HOUR_DAYS:
            # 1-hour resolution: 24 per day × days
            expected_points = 24 * days
            return {
                'resolution': '1hour',
                'expected_data_points': expected_points,
                'storage_table': 'noc_metric_snapshot_1hour',
                'days': days
            }
        else:
            # 1-day resolution: 1 per day
            expected_points = days
            return {
                'resolution': '1day',
                'expected_data_points': expected_points,
                'storage_table': 'noc_metric_snapshot_1day',
                'days': days
            }

    @classmethod
    def query_multiple_metrics(
        cls,
        client,
        start_date: datetime,
        end_date: datetime,
        metric_names: List[str],
        aggregation: str = 'avg',
        bu=None,
        oic=None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Query multiple metrics in a single call.

        Args:
            client: Client (Bt) instance
            start_date: Query start datetime
            end_date: Query end datetime
            metric_names: List of metric names to query
            aggregation: Aggregation type for downsampled data
            bu: Optional business unit filter
            oic: Optional officer-in-charge filter

        Returns:
            Dict mapping metric names to their time series data:
                {
                    'tickets_open': [{'timestamp': ..., 'value': ...}, ...],
                    'attendance_present': [{'timestamp': ..., 'value': ...}, ...],
                }
        """
        results = {}

        for metric_name in metric_names:
            try:
                results[metric_name] = cls.query_metrics(
                    client=client,
                    start_date=start_date,
                    end_date=end_date,
                    metric_name=metric_name,
                    aggregation=aggregation,
                    bu=bu,
                    oic=oic
                )
            except ValueError as e:
                logger.warning(f"Skipping metric {metric_name}: {e}")
                results[metric_name] = []

        return results

    @classmethod
    def calculate_storage_savings(cls) -> Dict[str, Any]:
        """
        Calculate storage savings from downsampling strategy.

        Returns:
            Dict with storage analysis:
                {
                    'total_5min_records': int,
                    'total_1hour_records': int,
                    'total_1day_records': int,
                    'theoretical_5min_records': int,
                    'storage_reduction_percent': float,
                    'retention_days': dict
                }
        """
        from apps.noc.models import NOCMetricSnapshot, NOCMetricSnapshot1Hour, NOCMetricSnapshot1Day

        total_5min = NOCMetricSnapshot.objects.count()
        total_1hour = NOCMetricSnapshot1Hour.objects.count()
        total_1day = NOCMetricSnapshot1Day.objects.count()

        # Calculate theoretical 5-min records if we stored everything at 5-min resolution
        # 1 hour of 5-min data = 12 records
        # 1 day of 5-min data = 288 records
        theoretical_from_hourly = total_1hour * 12
        theoretical_from_daily = total_1day * 288

        theoretical_total = total_5min + theoretical_from_hourly + theoretical_from_daily
        actual_total = total_5min + total_1hour + total_1day

        if theoretical_total > 0:
            storage_reduction = ((theoretical_total - actual_total) / theoretical_total) * 100
        else:
            storage_reduction = 0.0

        return {
            'total_5min_records': total_5min,
            'total_1hour_records': total_1hour,
            'total_1day_records': total_1day,
            'actual_total_records': actual_total,
            'theoretical_5min_records': theoretical_total,
            'storage_reduction_percent': round(storage_reduction, 2),
            'retention_days': {
                '5min': cls.RESOLUTION_5MIN_DAYS,
                '1hour': cls.RESOLUTION_1HOUR_DAYS,
                '1day': 730  # 2 years
            }
        }
