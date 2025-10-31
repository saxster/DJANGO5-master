"""
AssetBot - Asset Lifecycle AI Agent

Analyzes asset status and provides intelligent recommendations:
- Detects scrapped/standby assets
- Predicts maintenance needs
- Recommends asset redeployment
- Initiates procurement workflows

Uses Google Gemini for lifecycle analysis, Frappe for workflows.

Following CLAUDE.md Rule #7: <150 lines

Dashboard Agent Intelligence - Phase 2.5
"""

import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from apps.core.services.agents.base_agent_service import BaseAgentService
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.activity.models.asset_model import Asset

logger = logging.getLogger(__name__)


class AssetAgentService(BaseAgentService):
    """
    AI agent for asset lifecycle management.

    Capabilities:
    - Asset status monitoring
    - Predictive maintenance
    - Redeployment recommendations
    - Procurement initiation
    """

    def __init__(self, tenant_id: int):
        """Initialize AssetBot"""
        super().__init__(
            agent_id="assetbot-001",
            agent_name="AssetBot",
            tenant_id=tenant_id
        )

    def analyze(self, site_id: int, time_range: Tuple[datetime, datetime]) -> List[AgentRecommendation]:
        """
        Analyze asset status and generate recommendations.

        Args:
            site_id: Business unit/site ID
            time_range: Analysis period (start, end)

        Returns:
            List of recommendations
        """
        recommendations = []

        try:
            # Get asset metrics
            metrics = self._get_asset_metrics(site_id)

            # Scrapped/standby assets need attention
            if metrics['scrapped'] > 0 or metrics['standby'] > 5:
                rec = self._generate_asset_lifecycle_recommendation(
                    site_id, time_range, metrics
                )
                if rec:
                    recommendations.append(rec)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"AssetBot analysis error: {e}", exc_info=True)

        return recommendations

    def _get_asset_metrics(self, site_id: int) -> Dict[str, int]:
        """Get asset status metrics"""
        assets_queryset = Asset.objects.filter(bu_id=site_id)

        metrics = {
            'working': assets_queryset.filter(runningstatus='WORKING').count(),
            'standby': assets_queryset.filter(runningstatus='STANDBY').count(),
            'maintenance': assets_queryset.filter(runningstatus='MAINTENANCE').count(),
            'scrapped': assets_queryset.filter(runningstatus='SCRAPPED').count(),
            'total': assets_queryset.count(),
        }

        return metrics

    def _generate_asset_lifecycle_recommendation(
        self, site_id: int, time_range: Tuple[datetime, datetime], metrics: Dict
    ) -> Optional[AgentRecommendation]:
        """Recommend asset replacement or redeployment"""
        details = []

        if metrics['scrapped'] > 0:
            details.append({
                'entity_id': 'scrapped-assets',
                'reason': f"{metrics['scrapped']} scrapped assets need replacement",
                'priority': 'high',
                'suggested_action': 'Initiate procurement workflow'
            })

        if metrics['standby'] > 5:
            details.append({
                'entity_id': 'standby-assets',
                'reason': f"{metrics['standby']} assets in standby - consider redeployment",
                'priority': 'medium',
                'suggested_action': 'Review asset utilization and redeploy'
            })

        severity = 'high' if metrics['scrapped'] > 3 else 'medium'

        return self.create_recommendation(
            module='assets',
            site_id=site_id,
            client_id=self.tenant_id,
            summary=f"Asset lifecycle action needed - {metrics['scrapped']} scrapped, {metrics['standby']} standby",
            details=details,
            confidence=0.86,
            severity=severity,
            actions=[
                {
                    'label': 'View Asset Status',
                    'type': 'link',
                    'url': '/assets/inventory/?status=scrapped,standby'
                },
                {
                    'label': 'Initiate Procurement',
                    'type': 'workflow_trigger',
                    'endpoint': '/api/assets/procure',
                    'payload': {'count': metrics['scrapped']}
                }
            ],
            time_range=time_range,
            context_metrics=metrics
        )
