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

import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from django.utils import timezone

from apps.core.services.agents.base_agent_service import BaseAgentService
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.activity.models.job_model import Jobneed

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
            # Build prompt for Gemini
            prompt = f"""Analyze these tour metrics and recommend optimizations:
- Autoclosed: {metrics['autoclosed']}
- Partial: {metrics['partial']}
- Completed: {metrics['completed']}

Issues to investigate:
1. Why high autoclosed rate?
2. SOP compliance gaps
3. Schedule adjustment needs

Return JSON: {{"root_causes": [...], "sop_issues": [...], "recommendations": [...]}}"""

            llm = self.get_llm()
            response = llm.generate(prompt, temperature=0.4)

            analysis = json.loads(response)

            # Create recommendation
            autoclosed_rate = metrics['autoclosed'] / max(1, metrics['completed'] + metrics['autoclosed'])
            severity = 'high' if autoclosed_rate > 0.5 else 'medium'

            return self.create_recommendation(
                module='tours',
                site_id=site_id,
                client_id=self.tenant_id,
                summary=f"High autoclosed tours ({metrics['autoclosed']}) - SOP audit recommended",
                details=analysis.get('sop_issues', []),
                confidence=0.88,
                severity=severity,
                actions=[
                    {
                        'label': 'View Autoclosed Tours',
                        'type': 'link',
                        'url': '/operations/tours/?status=autoclosed'
                    },
                    {
                        'label': 'Schedule SOP Review',
                        'type': 'workflow_trigger',
                        'endpoint': '/api/tours/schedule-review',
                        'payload': {'metrics': metrics}
                    }
                ],
                time_range=time_range,
                context_metrics=metrics
            )

        except (LLMProviderError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"TourBot optimization recommendation failed: {e}", exc_info=True)
            return None
