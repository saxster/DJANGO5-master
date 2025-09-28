"""
Asset-related query operations.

Handles asset status, asset logs, and asset duration calculations.
"""

from typing import List, Dict
from django.db.models import Q, F, Window
from django.db.models.functions import Lead
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AssetQueries:
    """Query repository for asset-related operations."""

    @staticmethod
    def asset_status_period(status: str, asset_id: int) -> Dict:
        """
        Calculate total duration for asset status using window functions.
        """
        from apps.activity.models.asset_model import AssetLog

        logs = (
            AssetLog.objects
            .filter(
                Q(oldstatus=status) | Q(newstatus=status),
                asset_id=asset_id
            )
            .annotate(
                next_cdtz=Window(
                    expression=Lead('cdtz'),
                    partition_by=[F('asset_id')],
                    order_by=[F('cdtz')]
                )
            )
            .order_by('cdtz')
        )

        total_seconds = 0
        for log in logs:
            if log.next_cdtz:
                duration = (log.next_cdtz - log.cdtz).total_seconds()
                total_seconds += duration

        return {
            'asset_id': asset_id,
            'total_duration': str(timedelta(seconds=int(total_seconds)))
        }

    @staticmethod
    def all_asset_status_duration(client_id: int, bu_id: int) -> List[Dict]:
        """
        Get duration for all asset statuses using window functions.
        """
        from apps.activity.models.asset_model import AssetLog

        logs = (
            AssetLog.objects
            .filter(client_id=client_id, bu_id=bu_id)
            .select_related('asset')
            .annotate(
                period_end=Window(
                    expression=Lead('cdtz'),
                    partition_by=[F('asset_id')],
                    order_by=[F('cdtz')]
                )
            )
            .order_by('asset_id', 'cdtz')
        )

        status_durations = {}
        now = timezone.now()

        for log in logs:
            key = (log.asset_id, log.asset.assetname, log.newstatus)
            if key not in status_durations:
                status_durations[key] = {
                    'asset_id': log.asset_id,
                    'assetname': log.asset.assetname,
                    'newstatus': log.newstatus,
                    'duration_seconds': 0,
                    'is_current': False
                }

            period_end = log.period_end or now
            duration = (period_end - log.cdtz).total_seconds()
            status_durations[key]['duration_seconds'] += duration

            if not log.period_end:
                status_durations[key]['is_current'] = True

        results = []
        for data in status_durations.values():
            duration_str = 'till_now' if data['is_current'] else str(
                timedelta(seconds=int(data['duration_seconds']))
            )

            results.append({
                'asset_id': data['asset_id'],
                'assetname': data['assetname'],
                'newstatus': data['newstatus'],
                'duration_seconds': data['duration_seconds'],
                'duration_interval': duration_str
            })

        return sorted(results, key=lambda x: (x['asset_id'], x['newstatus']))

    @staticmethod
    def all_asset_status_duration_count(client_id: int, bu_id: int) -> int:
        """Get count of asset status duration records."""
        results = AssetQueries.all_asset_status_duration(client_id, bu_id)
        return len(results)