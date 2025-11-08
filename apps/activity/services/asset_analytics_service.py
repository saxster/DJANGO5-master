"""
Asset Analytics Service (Sprint 4.5)

Provides analytics and insights for asset management:
- Health score calculation
- Utilization metrics
- Cost analysis
- Performance trending

Author: Development Team
Date: October 2025
"""

import logging
from datetime import timedelta, date
from typing import Dict, Any, List
from django.db import DatabaseError
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone

from apps.activity.models import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

    Asset,
    AssetHealthScore,
    AssetUtilizationMetric,
    MaintenanceCostTracking
)

logger = logging.getLogger(__name__)


class AssetAnalyticsService:
    """
    Service for asset analytics and insights.

    Calculates health scores, tracks utilization, and provides
    predictive analytics for asset management.
    """

    def calculate_health_score(
        self,
        asset_id: int,
        tenant_id: int
    ) -> float:
        """
        Calculate comprehensive health score for an asset.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID

        Returns:
            Health score (0-100, higher is better)
        """
        try:
            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)

            # Initialize score
            health_score = 100.0
            factors = {}

            # Factor 1: Asset age (newer is better)
            if asset.cdtz:
                age_days = (timezone.now() - asset.cdtz).days
                age_score = max(0, 100 - (age_days / 365 * 5))  # Degrade 5 points per year
                health_score = min(health_score, age_score)
                factors['age_score'] = age_score

            # Factor 2: Running status
            status_scores = {
                'WORKING': 100,
                'STANDBY': 80,
                'MAINTENANCE': 50,
                'SCRAPPED': 0
            }
            status_score = status_scores.get(asset.runningstatus, 75)
            health_score = min(health_score, status_score)
            factors['status_score'] = status_score

            # Factor 3: Maintenance frequency (recent maintenance is good)
            recent_maintenance = MaintenanceCostTracking.objects.filter(
                asset_id=asset_id,
                tenant_id=tenant_id,
                maintenance_date__gte=timezone.now().date() - timedelta(days=90)
            ).count()

            if recent_maintenance == 0:
                maintenance_score = 60  # No recent maintenance = concern
            elif recent_maintenance <= 2:
                maintenance_score = 100  # Optimal maintenance frequency
            else:
                maintenance_score = max(40, 100 - (recent_maintenance - 2) * 10)  # Too frequent = issues

            health_score = (health_score + maintenance_score) / 2
            factors['maintenance_score'] = maintenance_score

            # Factor 4: Critical asset flag
            if asset.iscritical:
                # Critical assets need higher standards
                health_score *= 0.95
                factors['critical_asset_penalty'] = 5

            # Calculate risk level
            if health_score >= 80:
                risk_level = 'LOW'
            elif health_score >= 60:
                risk_level = 'MEDIUM'
            elif health_score >= 40:
                risk_level = 'HIGH'
            else:
                risk_level = 'CRITICAL'

            # Save health score
            AssetHealthScore.objects.update_or_create(
                asset_id=asset_id,
                calculated_date=timezone.now().date(),
                tenant_id=tenant_id,
                defaults={
                    'health_score': health_score,
                    'risk_level': risk_level,
                    'factors': factors
                }
            )

            logger.info(f"Asset {asset.assetcode} health score: {health_score:.2f} ({risk_level})")

            return float(health_score)

        except Asset.DoesNotExist:
            logger.error(f"Asset not found: {asset_id}")
            return 0.0

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error calculating health score: {e}")
            return 0.0

    def get_analytics_summary(
        self,
        tenant_id: int,
        site_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Get analytics summary for assets.

        Args:
            tenant_id: Tenant ID
            site_ids: List of site/BU IDs to filter (optional)

        Returns:
            Dictionary with analytics summary
        """
        try:
            # Build query
            query = Asset.objects.filter(tenant_id=tenant_id, enable=True)
            if site_ids:
                query = query.filter(bu_id__in=site_ids)

            # Total assets
            total_assets = query.count()

            # Assets by status
            by_status = query.values('runningstatus').annotate(count=Count('id'))

            # Critical assets
            critical_count = query.filter(iscritical=True).count()

            # Health scores
            health_scores = AssetHealthScore.objects.filter(
                tenant_id=tenant_id,
                calculated_date=timezone.now().date()
            )

            if site_ids:
                health_scores = health_scores.filter(asset__bu_id__in=site_ids)

            avg_health = health_scores.aggregate(Avg('health_score'))['health_score__avg'] or 0

            # Risk distribution
            risk_distribution = health_scores.values('risk_level').annotate(
                count=Count('id')
            )

            # Recent maintenance costs (last 30 days)
            recent_costs = MaintenanceCostTracking.objects.filter(
                tenant_id=tenant_id,
                maintenance_date__gte=timezone.now().date() - timedelta(days=30)
            )

            if site_ids:
                recent_costs = recent_costs.filter(asset__bu_id__in=site_ids)

            total_cost = recent_costs.aggregate(Sum('cost'))['cost__sum'] or 0

            return {
                'total_assets': total_assets,
                'critical_assets': critical_count,
                'assets_by_status': list(by_status),
                'average_health_score': float(avg_health),
                'risk_distribution': list(risk_distribution),
                'recent_maintenance_cost_30days': float(total_cost),
                'summary_date': timezone.now().date().isoformat()
            }

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error getting analytics summary: {e}")
            return {
                'total_assets': 0,
                'error': str(e)
            }

    def analyze_maintenance_costs(
        self,
        asset_id: int,
        tenant_id: int,
        days: int = 365
    ) -> Dict[str, Any]:
        """
        Analyze maintenance costs for an asset.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            days: Number of days to analyze

        Returns:
            Dictionary with cost analysis
        """
        try:
            since_date = timezone.now().date() - timedelta(days=days)

            costs = MaintenanceCostTracking.objects.filter(
                asset_id=asset_id,
                tenant_id=tenant_id,
                maintenance_date__gte=since_date
            )

            # Total cost
            total_cost = costs.aggregate(Sum('cost'))['cost__sum'] or 0

            # Cost by type
            by_type = costs.values('cost_type').annotate(
                total=Sum('cost'),
                count=Count('id')
            )

            # Average cost per maintenance
            avg_cost = costs.aggregate(Avg('cost'))['cost__avg'] or 0

            # Maintenance frequency
            frequency = costs.count()

            return {
                'total_cost': float(total_cost),
                'average_cost': float(avg_cost),
                'maintenance_count': frequency,
                'cost_by_type': list(by_type),
                'period_days': days,
                'period_start': since_date.isoformat(),
                'period_end': timezone.now().date().isoformat()
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error analyzing maintenance costs: {e}")
            return {
                'total_cost': 0.0,
                'error': str(e)
            }
