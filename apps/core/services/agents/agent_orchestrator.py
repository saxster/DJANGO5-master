"""
Agent Orchestrator - Central Coordination for Dashboard Agents

Coordinates all dashboard AI agents in parallel:
- Runs TaskBot, TourBot, AlertBot, AssetBot, AttendanceBot concurrently
- Ranks recommendations by confidence, severity, impact
- Publishes to event bus for real-time updates
- Manages agent lifecycle and error recovery

Uses Google Gemini (primary) with Claude fallback via LLM router.

Following CLAUDE.md Rule #7: <150 lines

Dashboard Agent Intelligence - Phase 3.2
"""

import logging
from typing import List, Dict, Tuple, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from apps.core.services.agents.task_agent_service import TaskAgentService
from apps.core.services.agents.tour_agent_service import TourAgentService
from apps.core.services.agents.alert_agent_service import AlertAgentService
from apps.core.services.agents.asset_agent_service import AssetAgentService
from apps.core.services.agents.attendance_agent_service import AttendanceAgentService
from apps.core.services.agents.route_agent_service import RouteAgentService
from apps.core.services.agents.incident_agent_service import IncidentAgentService
from apps.core.services.agents.event_bus import RedisEventBus
from apps.core.models.agent_recommendation import AgentRecommendation

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Central orchestration for dashboard agents.

    Features:
    - Parallel agent execution
    - Intelligent recommendation ranking
    - Event bus integration
    - Error recovery and logging
    """

    # Severity weights for ranking
    SEVERITY_WEIGHTS = {
        'critical': 4.0,
        'high': 3.0,
        'medium': 2.0,
        'low': 1.0
    }

    def __init__(self, tenant_id: int):
        """
        Initialize orchestrator.

        Args:
            tenant_id: Tenant/client ID for multi-tenant isolation
        """
        self.tenant_id = tenant_id
        self.event_bus = RedisEventBus()

        # Initialize all agents
        self.agents = {
            'taskbot': TaskAgentService(tenant_id),
            'tourbot': TourAgentService(tenant_id),
            'alertbot': AlertAgentService(tenant_id),
            'assetbot': AssetAgentService(tenant_id),
            'attendancebot': AttendanceAgentService(tenant_id),
            'routebot': RouteAgentService(tenant_id),
            'incidentbot': IncidentAgentService(tenant_id),
        }

        logger.info(f"AgentOrchestrator initialized for tenant {tenant_id} with {len(self.agents)} agents")

    def process_dashboard_data(
        self, site_id: int, time_range: Tuple[datetime, datetime]
    ) -> List[AgentRecommendation]:
        """
        Run all agents in parallel and collect recommendations.

        Args:
            site_id: Business unit/site ID
            time_range: Analysis period (start, end)

        Returns:
            List of ranked recommendations
        """
        all_recommendations = []

        # Run agents in parallel
        with ThreadPoolExecutor(max_workers=len(self.agents), thread_name_prefix='agent-') as executor:
            # Submit all agent analysis tasks
            futures = {
                executor.submit(agent.analyze, site_id, time_range): name
                for name, agent in self.agents.items()
            }

            # Collect results as they complete
            for future in as_completed(futures):
                agent_name = futures[future]

                try:
                    recommendations = future.result(timeout=10)  # 10s timeout per agent
                    all_recommendations.extend(recommendations)

                    logger.info(
                        f"Agent {agent_name} completed: {len(recommendations)} recommendations"
                    )

                except (TimeoutError, ValueError, AttributeError) as e:
                    logger.error(f"Agent {agent_name} failed: {e}", exc_info=True)
                    # Continue with other agents - don't fail entirely

        # Rank and filter recommendations
        ranked_recommendations = self._rank_recommendations(all_recommendations)

        # Publish to event bus for real-time updates
        for rec in ranked_recommendations:
            self.event_bus.publish_recommendation(rec.to_dict())

        logger.info(
            f"Orchestrator completed: {len(ranked_recommendations)} recommendations "
            f"from {len(all_recommendations)} total"
        )

        return ranked_recommendations

    def _rank_recommendations(self, recommendations: List[AgentRecommendation]) -> List[AgentRecommendation]:
        """
        Rank recommendations by composite score.

        Score = (confidence * severity_weight * 10)

        Args:
            recommendations: Unranked recommendations

        Returns:
            Ranked list (highest score first)
        """
        if not recommendations:
            return []

        # Calculate composite scores
        for rec in recommendations:
            severity_weight = self.SEVERITY_WEIGHTS.get(rec.severity, 1.0)
            rec.composite_score = rec.confidence * severity_weight * 10

        # Sort by composite score descending
        return sorted(
            recommendations,
            key=lambda r: (r.composite_score, r.confidence, r.created_at),
            reverse=True
        )

    def execute_action(self, recommendation_id: int, action_type: str) -> Dict[str, Any]:
        """
        Route action execution to appropriate agent.

        Args:
            recommendation_id: AgentRecommendation ID
            action_type: Action type to execute

        Returns:
            Execution result dictionary

        Raises:
            ValueError: If recommendation not found
        """
        try:
            rec = AgentRecommendation.objects.get(id=recommendation_id)

            # Route to appropriate agent
            agent_type = rec.agent_id.split('-')[0]  # Extract 'taskbot' from 'taskbot-001'
            agent = self.agents.get(agent_type)

            if not agent:
                raise ValueError(f"Unknown agent type: {agent_type}")

            # Execute action (if agent supports it)
            result = agent.execute_action(recommendation_id, action_type)

            # Update recommendation status
            rec.status = 'auto_executed' if result.get('auto_executed') else 'accepted'
            rec.save()

            # Publish action event
            self.event_bus.publish_action_executed(recommendation_id, action_type, result)

            return result

        except AgentRecommendation.DoesNotExist as e:
            logger.error(f"Recommendation {recommendation_id} not found", exc_info=True)
            raise ValueError(f"Recommendation not found: {recommendation_id}")
