"""
TourBot - Tour Optimization AI Agent

Analyzes tour patterns and provides intelligent recommendations:
- Detects autoclosed/partial tours
- Analyzes route inefficiencies
- Flags SOP deviations using semantic search (txtai)
- Recommends schedule adjustments

Uses Google Gemini for route optimization, txtai for SOP compliance.

Following CLAUDE.md Rule #7: <150 lines

Dashboard Agent Intelligence - Phase 2.3
"""

import json
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from django.utils import timezone

from apps.core.services.agents.base_agent_service import BaseAgentService
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.activity.models.job_model import Jobneed
from apps.core_onboarding.services.llm.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


class TourAgentService(BaseAgentService):
    """
    AI agent for tour optimization and SOP compliance.

    Capabilities:
    - Route efficiency analysis
    - SOP deviation detection
    - Schedule optimization
    - Tour pattern recognition
    """

    def __init__(self, tenant_id: int):
        """Initialize TourBot"""
        super().__init__(
            agent_id="tourbot-001",
            agent_name="TourBot",
            tenant_id=tenant_id
        )

    def analyze(self, site_id: int, time_range: Tuple[datetime, datetime]) -> List[AgentRecommendation]:
        """
        Analyze tour patterns and generate recommendations.

        Args:
            site_id: Business unit/site ID
            time_range: Analysis period (start, end)

        Returns:
            List of recommendations
        """
        recommendations = []

        try:
            # Get tour metrics
            metrics = self._get_tour_metrics(site_id, time_range)

            # High autoclosed rate = investigate
            if metrics['autoclosed'] > 100 or metrics['partial'] > 20:
                rec = self._generate_tour_optimization_recommendation(
                    site_id, time_range, metrics
                )
                if rec:
                    recommendations.append(rec)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"TourBot analysis error: {e}", exc_info=True)

        return recommendations

    def _get_tour_metrics(self, site_id: int, time_range: Tuple[datetime, datetime]) -> Dict[str, int]:
        """Get tour metrics from database"""
        tours_queryset = Jobneed.objects.filter(
            bu_id=site_id,
            identifier__in=[Jobneed.Identifier.INTERNALTOUR, Jobneed.Identifier.EXTERNALTOUR],
            plandatetime__range=time_range
        )

        metrics = {
            'completed': tours_queryset.filter(jobstatus=Jobneed.JobStatus.COMPLETED).count(),
            'autoclosed': tours_queryset.filter(jobstatus=Jobneed.JobStatus.AUTOCLOSED).count(),
            'inprogress': tours_queryset.filter(jobstatus=Jobneed.JobStatus.INPROGRESS).count(),
            'partial': tours_queryset.filter(jobstatus=Jobneed.JobStatus.PARTIALLYCOMPLETED).count(),
            'scheduled': tours_queryset.filter(jobstatus=Jobneed.JobStatus.ASSIGNED).count(),
        }

        return metrics

    def _generate_tour_optimization_recommendation(
        self, site_id: int, time_range: Tuple[datetime, datetime], metrics: Dict
    ) -> Optional[AgentRecommendation]:
        """Use Gemini to analyze tour patterns and recommend optimizations"""
        try:
            focus = (
                "Investigate why tours are being autoclosed or partially completed."
                " Identify the top root causes, which SOP steps fail most often,"
                " and provide concrete adjustments (route, staffing, schedule)."
                " Reference the metrics exactly and avoid repeating stale advice."
            )

            prompt_bundle = self._build_prompt_bundle(
                module='tours',
                site_id=site_id,
                client_id=self.tenant_id,
                metrics=metrics,
                time_range=time_range,
                focus=focus,
                additional_notes={'trigger': 'autoclosed_anomaly'}
            )

            schema = {
                'type': 'object',
                'properties': {
                    'summary': {'type': 'string'},
                    'severity': {'type': 'string', 'enum': ['low', 'medium', 'high', 'critical']},
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'sop_issues': {
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
                    'narrative_chunks': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    }
                },
                'required': ['summary', 'severity', 'confidence', 'sop_issues']
            }

            analysis = self._invoke_structured_llm(
                prompt_bundle,
                schema,
                generation_kwargs={'temperature': 0.5, 'max_tokens': 1600}
            )

            autoclosed_rate = metrics['autoclosed'] / max(1, metrics['completed'] + metrics['autoclosed'])
            fallback_severity = 'high' if autoclosed_rate > 0.5 else 'medium'

            summary = analysis.get('summary') or (
                f"High autoclosed tours ({metrics['autoclosed']}) - SOP audit recommended"
            )
            severity = analysis.get('severity', fallback_severity)
            confidence = float(analysis.get('confidence', 0.85))
            sop_issues = analysis.get('sop_issues', [])
            actions = analysis.get('actions') or [
                {
                    'label': 'View Autoclosed Tours',
                    'type': 'link',
                    'url': '/operations/tours/?status=autoclosed'
                }
            ]

            context_metrics = {
                **metrics,
                'prompt_context': prompt_bundle['metadata'],
                'schema': 'tourbot.optimization.v2',
            }
            if analysis.get('narrative_chunks'):
                context_metrics['narrative_chunks'] = analysis['narrative_chunks']

            return self.create_recommendation(
                module='tours',
                site_id=site_id,
                client_id=self.tenant_id,
                summary=summary,
                details=sop_issues,
                confidence=confidence,
                severity=severity,
                actions=actions,
                time_range=time_range,
                context_metrics=context_metrics
            )

        except (LLMProviderError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"TourBot optimization recommendation failed: {e}", exc_info=True)
            return None
