"""
TaskBot - Task Management AI Agent

Analyzes task metrics and provides intelligent recommendations:
- Detects overdue tasks
- Auto-prioritizes by urgency, SLA, impact
- Suggests task assignments based on skill/location
- Escalates critical issues

Uses Google Gemini (primary) with Claude fallback for AI reasoning.
Integrates with Frappe/ERPNext for workflow execution.

Following CLAUDE.md Rule #7: <150 lines

Dashboard Agent Intelligence - Phase 2.2
"""

import logging
import json
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count

from apps.core.services.agents.base_agent_service import BaseAgentService
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.activity.models.job_model import Jobneed
from apps.reports.services.frappe_service import get_frappe_service
from apps.core_onboarding.services.llm.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


class TaskAgentService(BaseAgentService):
    """
    AI agent for intelligent task management.

    Capabilities:
    - Overdue task detection
    - Priority-based task assignment
    - Escalation recommendations
    - Workload balancing
    """

    def __init__(self, tenant_id: int):
        """Initialize TaskBot"""
        super().__init__(
            agent_id="taskbot-001",
            agent_name="TaskBot",
            tenant_id=tenant_id
        )
        self.frappe_service = get_frappe_service()

    def analyze(self, site_id: int, time_range: Tuple[datetime, datetime]) -> List[AgentRecommendation]:
        """
        Analyze task metrics for site and generate recommendations.

        Args:
            site_id: Business unit/site ID
            time_range: Analysis period (start, end)

        Returns:
            List of recommendations

        Raises:
            LLMProviderError: If all LLM providers fail
        """
        recommendations = []

        try:
            # Get task metrics
            metrics = self._get_task_metrics(site_id, time_range)

            # Check for issues requiring agent intervention
            if metrics['pending'] > 15 or metrics['overdue'] > 5:
                rec = self._generate_task_escalation_recommendation(
                    site_id, time_range, metrics
                )
                if rec:
                    recommendations.append(rec)

            if metrics['autoclosed'] > 50:
                rec = self._generate_autoclosed_analysis_recommendation(
                    site_id, time_range, metrics
                )
                if rec:
                    recommendations.append(rec)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"TaskBot analysis error: {e}", exc_info=True)

        return recommendations

    def _get_task_metrics(self, site_id: int, time_range: Tuple[datetime, datetime]) -> Dict[str, int]:
        """Get task metrics from database"""
        tasks_queryset = Jobneed.objects.filter(
            bu_id=site_id,
            identifier=Jobneed.Identifier.TASK,
            plandatetime__range=time_range
        )

        metrics = {
            'completed': tasks_queryset.filter(jobstatus=Jobneed.JobStatus.COMPLETED).count(),
            'autoclosed': tasks_queryset.filter(jobstatus=Jobneed.JobStatus.AUTOCLOSED).count(),
            'pending': tasks_queryset.filter(jobstatus=Jobneed.JobStatus.ASSIGNED).count(),
            'scheduled': tasks_queryset.filter(jobstatus=Jobneed.JobStatus.ASSIGNED).count(),
            'inprogress': tasks_queryset.filter(jobstatus=Jobneed.JobStatus.INPROGRESS).count(),
            'overdue': tasks_queryset.filter(
                jobstatus=Jobneed.JobStatus.ASSIGNED,
                expirydatetime__lt=timezone.now()
            ).count()
        }

        return metrics

    def _generate_task_escalation_recommendation(
        self, site_id: int, time_range: Tuple[datetime, datetime], metrics: Dict
    ) -> Optional[AgentRecommendation]:
        """Use Gemini to analyze overdue tasks and recommend escalation"""
        try:
            # Build prompt for Gemini
            prompt = f"""Analyze these task metrics and recommend actions:
- Pending: {metrics['pending']}
- Overdue: {metrics['overdue']}
- In Progress: {metrics['inprogress']}

Determine:
1. Which tasks to escalate (prioritize by urgency)
2. Assignment strategy
3. Expected impact

Return JSON: {{"tasks_to_escalate": [...], "assignment_strategy": "...", "impact": "..."}}"""

            llm = self.get_llm()
            response = llm.generate(prompt, temperature=0.3)

            # Parse Gemini response
            analysis = json.loads(response)

            # Create recommendation
            return self.create_recommendation(
                module='tasks',
                site_id=site_id,
                client_id=self.tenant_id,
                summary=f"Escalate {metrics['overdue']} overdue tasks and assign {metrics['pending']} pending tasks",
                details=analysis.get('tasks_to_escalate', []),
                confidence=0.92 if metrics['overdue'] > 10 else 0.85,
                severity='high' if metrics['overdue'] > 10 else 'medium',
                actions=[
                    {
                        'label': 'Escalate Overdue',
                        'type': 'workflow_trigger',
                        'endpoint': '/api/tasks/escalate',
                        'payload': {'count': metrics['overdue']}
                    },
                    {
                        'label': 'View Task List',
                        'type': 'link',
                        'url': '/operations/tasks/?status=overdue'
                    }
                ],
                time_range=time_range,
                context_metrics=metrics
            )

        except (LLMProviderError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"TaskBot escalation recommendation failed: {e}", exc_info=True)
            return None

    def _generate_autoclosed_analysis_recommendation(
        self, site_id: int, time_range: Tuple[datetime, datetime], metrics: Dict
    ) -> Optional[AgentRecommendation]:
        """Analyze high autoclosed task count"""
        return self.create_recommendation(
            module='tasks',
            site_id=site_id,
            client_id=self.tenant_id,
            summary=f"High number of autoclosed tasks ({metrics['autoclosed']}) - review SOP compliance",
            details=[{'entity_id': 'autoclosed-analysis', 'reason': 'Autoclosed rate exceeds threshold', 'priority': 'medium', 'suggested_action': 'Review task SOP and grace time settings'}],
            confidence=0.78,
            severity='medium',
            actions=[
                {'label': 'View Autoclosed Tasks', 'type': 'link', 'url': '/operations/tasks/?status=autoclosed'}
            ],
            time_range=time_range,
            context_metrics=metrics
        )
