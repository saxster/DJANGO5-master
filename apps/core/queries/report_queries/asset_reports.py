"""
Asset-related report queries.

Handles asset-wise task status and people QR reports.
"""

from typing import List, Dict
from django.db.models import Q, F, Count
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AssetReports:
    """Report queries for assets."""

    @staticmethod
    def assetwisetaskstatus_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Asset-wise task status report."""
        from apps.activity.models.asset_model import Asset

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        asset_status = (
            Asset.objects
            .filter(
                identifier='ASSET',
                jobneed_assets__bu_id__in=site_id_list,
                jobneed_assets__plandatetime__date__range=[from_date, upto_date]
            )
            .exclude(id=1)
            .annotate(
                autoclosed_count=Count(
                    'jobneed_assets',
                    filter=Q(jobneed_assets__jobstatus='AUTOCLOSED')
                ),
                completed_count=Count(
                    'jobneed_assets',
                    filter=Q(jobneed_assets__jobstatus='COMPLETED')
                ),
                total_tasks=Count(
                    'jobneed_assets',
                    filter=Q(jobneed_assets__jobstatus__in=['AUTOCLOSED', 'COMPLETED'])
                )
            )
            .values('id', 'assetname', 'autoclosed_count', 'completed_count', 'total_tasks')
        )

        result = []
        for asset in asset_status:
            result.append({
                'id': asset['id'],
                'Asset Name': asset['assetname'],
                'AutoClosed': asset['autoclosed_count'],
                'Completed': asset['completed_count'],
                'Total Tasks': asset['total_tasks']
            })

        return result

    @staticmethod
    def peopleqr_report(client_id: int, additional_filter: str = '',
                       additional_filter2: str = '') -> List[Dict]:
        """Simple people QR report."""
        from apps.peoples.models import People

        queryset = People.objects.filter(client_id=client_id).distinct()

        return list(
            queryset.values('peoplename', 'peoplecode')
        )