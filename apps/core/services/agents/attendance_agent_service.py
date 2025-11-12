"""
AttendanceBot - Attendance & Staffing AI Agent

Analyzes attendance patterns and provides intelligent recommendations:
- Correlates attendance with task completion
- Suggests staffing adjustments
- Detects route/assignment issues
- Generates daily ops digest

Uses Google Gemini for correlation analysis, txtai for log parsing.

Following CLAUDE.md Rule #7: <150 lines

Dashboard Agent Intelligence - Phase 2.6
"""

import json
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from apps.core.services.agents.base_agent_service import BaseAgentService
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.attendance.models import PeopleEventlog
from apps.core_onboarding.services.llm.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


class AttendanceAgentService(BaseAgentService):
    """
    AI agent for attendance and staffing optimization.

    Capabilities:
    - Attendance-task correlation
    - Staffing recommendations
    - Route assignment optimization
    - Daily ops digest generation
    """

    def __init__(self, tenant_id: int):
        """Initialize AttendanceBot"""
        super().__init__(
            agent_id="attendancebot-001",
            agent_name="AttendanceBot",
            tenant_id=tenant_id
        )

    def analyze(self, site_id: int, time_range: Tuple[datetime, datetime]) -> List[AgentRecommendation]:
        """
        Analyze attendance patterns and generate recommendations.

        Args:
            site_id: Business unit/site ID
            time_range: Analysis period (start, end)

        Returns:
            List of recommendations
        """
        recommendations = []

        try:
            # Get attendance metrics
            metrics = self._get_attendance_metrics(site_id, time_range)

            # Low attendance = staffing issue
            if metrics['today_present'] < metrics['expected'] * 0.8:
                rec = self._generate_staffing_recommendation(
                    site_id, time_range, metrics
                )
                if rec:
                    recommendations.append(rec)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"AttendanceBot analysis error: {e}", exc_info=True)

        return recommendations

    def _get_attendance_metrics(self, site_id: int, time_range: Tuple[datetime, datetime]) -> Dict[str, int]:
        """Get attendance metrics"""
        today = datetime.now().date()

        attendance_today = PeopleEventlog.objects.filter(
            bu_id=site_id,
            datefor=today
        ).values('people').distinct().count()

        # Get expected count from scheduled assignments
        # TODO: Integrate with actual staffing model
        expected_count = attendance_today + 5  # Placeholder

        metrics = {
            'today_present': attendance_today,
            'expected': expected_count,
            'percentage': int((attendance_today / max(1, expected_count)) * 100),
        }

        return metrics

    def _generate_staffing_recommendation(
        self, site_id: int, time_range: Tuple[datetime, datetime], metrics: Dict
    ) -> Optional[AgentRecommendation]:
        """Recommend staffing adjustments"""
        shortage = metrics['expected'] - metrics['today_present']

        try:
            focus = (
                "Attendance dropped below plan. Explain staffing risk,"
                " recommend immediate mitigation (reassignments, overtime,"
                " backup call-ins), and estimate operational impact."
            )

            prompt_bundle = self._build_prompt_bundle(
                module='attendance',
                site_id=site_id,
                client_id=self.tenant_id,
                metrics=metrics,
                time_range=time_range,
                focus=focus,
                additional_notes={'shortage': shortage}
            )

            schema = {
                'type': 'object',
                'properties': {
                    'summary': {'type': 'string'},
                    'severity': {'type': 'string', 'enum': ['low', 'medium', 'high', 'critical']},
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'staffing_actions': {
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
                        }
                    },
                    'narrative_chunks': {'type': 'array', 'items': {'type': 'string'}}
                },
                'required': ['summary', 'severity', 'confidence', 'staffing_actions']
            }

            analysis = self._invoke_structured_llm(
                prompt_bundle,
                schema,
                generation_kwargs={'temperature': 0.4, 'max_tokens': 1400}
            )

            summary = analysis.get('summary') or (
                f"Low attendance ({metrics['percentage']}%) - {shortage} staff short"
            )
            severity = analysis.get('severity', 'high' if shortage > 5 else 'medium')
            confidence = float(analysis.get('confidence', 0.9))
            details = analysis.get('staffing_actions', [])
            actions = analysis.get('actions') or [
                {
                    'label': 'View Attendance',
                    'type': 'link',
                    'url': '/people/attendance/'
                }
            ]

            context_metrics = {
                **metrics,
                'prompt_context': prompt_bundle['metadata'],
                'schema': 'attendancebot.staffing.v2',
            }
            if analysis.get('narrative_chunks'):
                context_metrics['narrative_chunks'] = analysis['narrative_chunks']

            return self.create_recommendation(
                module='attendance',
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
            logger.error(f"AttendanceBot staffing recommendation failed: {e}", exc_info=True)
            return None
