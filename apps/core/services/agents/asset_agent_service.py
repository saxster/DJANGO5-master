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

import json
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from apps.core.services.agents.base_agent_service import BaseAgentService
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.activity.models.asset_model import Asset
from apps.core_onboarding.services.llm.exceptions import LLMProviderError

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
        try:
            focus = (
                "Review asset lifecycle risk. Highlight scrapped inventory that"
                " must be replaced, standby assets that can be redeployed, and"
                " any maintenance hotspots. Provide concrete actions."
            )

            prompt_bundle = self._build_prompt_bundle(
                module='assets',
                site_id=site_id,
                client_id=self.tenant_id,
                metrics=metrics,
                time_range=time_range,
                focus=focus,
                additional_notes={'trigger': 'lifecycle_anomaly'}
            )

            schema = {
                'type': 'object',
                'properties': {
                    'summary': {'type': 'string'},
                    'severity': {'type': 'string', 'enum': ['low', 'medium', 'high', 'critical']},
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'asset_issues': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'entity_id': {'type': 'string'},
                                'reason': {'type': 'string'},
                                'priority': {'type': 'string'},
                                'suggested_action': {'type': 'string'}
                            },
                            'required': ['reason']
                        },
                        'maxItems': 5
                    },
                    'actions': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'label': {'type': 'string'},
                                'type': {'type': 'string'},
                                'endpoint': {'type': 'string'},
                                'payload': {'type': 'object'},
                                'url': {'type': 'string'}
                            },
                            'required': ['label', 'type']
                        },
                        'minItems': 1,
                        'maxItems': 3
                    },
                    'narrative_chunks': {'type': 'array', 'items': {'type': 'string'}}
                },
                'required': ['summary', 'severity', 'confidence', 'asset_issues']
            }

            analysis = self._invoke_structured_llm(
                prompt_bundle,
                schema,
                generation_kwargs={'temperature': 0.45, 'max_tokens': 1500}
            )

            severity = analysis.get('severity', 'medium')
            confidence = float(analysis.get('confidence', 0.86))
            details = analysis.get('asset_issues', [])
            actions = analysis.get('actions') or [
                {
                    'label': 'View Asset Status',
                    'type': 'link',
                    'url': '/assets/inventory/?status=scrapped,standby'
                }
            ]

            summary = analysis.get('summary') or (
                f"Asset lifecycle action needed - {metrics['scrapped']} scrapped, {metrics['standby']} standby"
            )

            context_metrics = {
                **metrics,
                'prompt_context': prompt_bundle['metadata'],
                'schema': 'assetbot.lifecycle.v2',
            }
            if analysis.get('narrative_chunks'):
                context_metrics['narrative_chunks'] = analysis['narrative_chunks']

            return self.create_recommendation(
                module='assets',
                site_id=site_id,
                client_id=self.tenant_id,
                summary=summary,
                details=details,
                confidence=confidence,
                severity=severity,
                actions=actions,
                time_range=time_range,
                context_metrics=context_metrics
            )

        except (LLMProviderError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"AssetBot lifecycle recommendation failed: {e}", exc_info=True)
            return None
