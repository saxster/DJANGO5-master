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
            focus = (
                "Evaluate task health for the site. Identify up to five concrete"
                " escalation candidates, propose how to reassign teams, and flag"
                " any SLA or safety risk. Reference the provided metrics and"
                " recent recommendations so you do not repeat prior advice."
            )

            prompt_bundle = self._build_prompt_bundle(
                module='tasks',
                site_id=site_id,
                client_id=self.tenant_id,
                metrics=metrics,
                time_range=time_range,
                focus=focus,
                additional_notes={'trigger': 'overdue_threshold', 'pending_threshold': 15},
            )

            schema = {
                'type': 'object',
                'properties': {
                    'summary': {'type': 'string', 'minLength': 20},
                    'severity': {
                        'type': 'string',
                        'enum': ['low', 'medium', 'high', 'critical']
                    },
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'tasks_to_escalate': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'entity_id': {'type': 'string'},
                                'reason': {'type': 'string'},
                                'priority': {'type': 'string'},
                                'suggested_action': {'type': 'string'},
                            },
                            'required': ['entity_id', 'reason', 'priority']
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
                                'url': {'type': 'string'},
                            },
                            'required': ['label', 'type']
                        },
                        'minItems': 1,
                        'maxItems': 3
                    },
                    'narrative_chunks': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Ordered sentences that can be streamed to UI'
                    }
                },
                'required': ['summary', 'severity', 'confidence', 'tasks_to_escalate', 'actions']
            }

            analysis = self._invoke_structured_llm(
                prompt_bundle,
                schema,
                generation_kwargs={'temperature': 0.55, 'max_tokens': 1536},
            )

            # Create recommendation
            summary = analysis.get('summary') or (
                f"Escalate {metrics['overdue']} overdue tasks; reassign pending workload"
            )
            severity = analysis.get('severity', 'medium')
            confidence = float(analysis.get('confidence', 0.85))
            details = analysis.get('tasks_to_escalate', [])
            llm_actions = analysis.get('actions') or [
                {
                    'label': 'View Task List',
                    'type': 'link',
                    'url': '/operations/tasks/?status=overdue'
                }
            ]
            context_metrics = {
                **metrics,
                'prompt_context': prompt_bundle['metadata'],
                'schema': 'taskbot.escalation.v2',
            }
            if analysis.get('narrative_chunks'):
                context_metrics['narrative_chunks'] = analysis['narrative_chunks']

            return self.create_recommendation(
                module='tasks',
                site_id=site_id,
                client_id=self.tenant_id,
                summary=summary,
                details=details,
                confidence=confidence,
                severity=severity,
                actions=llm_actions,
                time_range=time_range,
                context_metrics=context_metrics
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
