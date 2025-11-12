"""
AlertBot - Alert Intelligence AI Agent

Analyzes alert patterns and system health:
- Validates sensor/data pipeline health
- Detects missing alerts (system integrity issues)
- Flags alert anomalies
- Recommends recalibration

Uses Google Gemini for reasoning, txtai for log analysis.

Following CLAUDE.md Rule #7: <150 lines

Dashboard Agent Intelligence - Phase 2.4
"""

import json
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from apps.core.services.agents.base_agent_service import BaseAgentService
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.core_onboarding.services.llm.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


class AlertAgentService(BaseAgentService):
    """
    AI agent for alert intelligence and system health.

    Capabilities:
    - Alert pipeline validation
    - Anomaly detection
    - System health recommendations
    """

    def __init__(self, tenant_id: int):
        """Initialize AlertBot"""
        super().__init__(
            agent_id="alertbot-001",
            agent_name="AlertBot",
            tenant_id=tenant_id
        )

    def analyze(self, site_id: int, time_range: Tuple[datetime, datetime]) -> List[AgentRecommendation]:
        """
        Analyze alert patterns for site.

        Args:
            site_id: Business unit/site ID
            time_range: Analysis period (start, end)

        Returns:
            List of recommendations
        """
        recommendations = []

        try:
            # Get alert metrics
            metrics = self._get_alert_metrics(site_id, time_range)

            # No alerts = validate system health
            if metrics['total'] == 0:
                rec = self._generate_no_alerts_recommendation(
                    site_id, time_range, metrics
                )
                if rec:
                    recommendations.append(rec)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"AlertBot analysis error: {e}", exc_info=True)

        return recommendations

    def _get_alert_metrics(self, site_id: int, time_range: Tuple[datetime, datetime]) -> Dict[str, int]:
        """
        Get alert metrics.

        TODO: Integrate with actual alert model when available
        For now, return placeholder metrics
        """
        return {
            'total': 0,  # Placeholder - integrate with alert model
            'critical': 0,
            'warning': 0,
            'info': 0,
        }

    def _generate_no_alerts_recommendation(
        self, site_id: int, time_range: Tuple[datetime, datetime], metrics: Dict
    ) -> Optional[AgentRecommendation]:
        """Recommend system health check when no alerts found"""
        try:
            focus = (
                "Zero alerts were emitted. Determine whether this is a positive"
                " signal or a system failure. Provide diagnostic steps for"
                " sensors, ingestion, and notification channels."
            )

            prompt_bundle = self._build_prompt_bundle(
                module='alerts',
                site_id=site_id,
                client_id=self.tenant_id,
                metrics=metrics,
                time_range=time_range,
                focus=focus,
                additional_notes={'trigger': 'no_alerts'}
            )

            schema = {
                'type': 'object',
                'properties': {
                    'summary': {'type': 'string'},
                    'severity': {'type': 'string', 'enum': ['low', 'medium', 'high', 'critical']},
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'diagnostics': {
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
                        }
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
                        }
                    },
                    'narrative_chunks': {'type': 'array', 'items': {'type': 'string'}}
                },
                'required': ['summary', 'severity', 'confidence', 'diagnostics']
            }

            analysis = self._invoke_structured_llm(
                prompt_bundle,
                schema,
                generation_kwargs={'temperature': 0.35, 'max_tokens': 1200}
            )

            summary = analysis.get('summary') or (
                "No alerts generated - validate sensor and data pipeline integrity"
            )
            severity = analysis.get('severity', 'medium')
            confidence = float(analysis.get('confidence', 0.75))
            diagnostics = analysis.get('diagnostics', [])
            actions = analysis.get('actions') or [
                {
                    'label': 'Run Diagnostics',
                    'type': 'workflow_trigger',
                    'endpoint': '/api/system/diagnostics',
                    'payload': {'check_type': 'alert_pipeline'}
                }
            ]

            context_metrics = {
                **metrics,
                'prompt_context': prompt_bundle['metadata'],
                'schema': 'alertbot.healthcheck.v2',
            }
            if analysis.get('narrative_chunks'):
                context_metrics['narrative_chunks'] = analysis['narrative_chunks']

            return self.create_recommendation(
                module='alerts',
                site_id=site_id,
                client_id=self.tenant_id,
                summary=summary,
                details=diagnostics,
                confidence=confidence,
                severity=severity,
                actions=actions,
                time_range=time_range,
                context_metrics=context_metrics
            )

        except (LLMProviderError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"AlertBot health-check recommendation failed: {e}", exc_info=True)
            return None
