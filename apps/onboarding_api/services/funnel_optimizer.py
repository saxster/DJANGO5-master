"""
Funnel Optimizer Service for Conversational Onboarding.

Analyzes drop-off points in the onboarding funnel and provides
actionable optimization recommendations to improve conversion rates.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #12: Query optimization with select_related/prefetch_related
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Avg, F, Q
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from apps.core_onboarding.models import ConversationSession

logger = logging.getLogger(__name__)


@dataclass
class DropOffInsight:
    """Represents a drop-off point analysis"""
    stage: str
    drop_off_rate: float
    sessions_dropped: int
    issue_category: str
    root_cause: str
    recommendation: str
    expected_improvement: str
    implementation_effort: str  # low, medium, high


@dataclass
class FunnelOptimizationReport:
    """Complete funnel optimization report"""
    period_start: datetime
    period_end: datetime
    total_sessions: int
    overall_conversion_rate: float
    drop_offs: List[DropOffInsight]
    quick_wins: List[Dict[str, Any]]
    high_impact_changes: List[Dict[str, Any]]
    estimated_roi: Dict[str, Any]


class FunnelOptimizerService:
    """
    Service for analyzing and optimizing onboarding funnel performance.

    Identifies drop-off points, diagnoses issues, and provides
    data-driven recommendations for improvement.
    """

    # Drop-off thresholds for alerts
    HIGH_DROP_OFF_THRESHOLD = 0.30  # 30% drop-off is concerning
    CRITICAL_DROP_OFF_THRESHOLD = 0.50  # 50% drop-off is critical

    # Issue categories for classification
    ISSUE_CATEGORIES = {
        'complexity': 'User confused by complexity',
        'performance': 'Slow response times',
        'technical': 'Technical errors',
        'ux': 'Poor user experience',
        'content': 'Unclear messaging'
    }

    def __init__(self):
        self.cache_timeout = 300  # 5 minutes

    def analyze_and_optimize(
        self,
        start_date: datetime,
        end_date: datetime,
        client_id: Optional[int] = None
    ) -> FunnelOptimizationReport:
        """
        Analyze funnel and provide optimization recommendations.

        Args:
            start_date: Analysis period start
            end_date: Analysis period end
            client_id: Optional client filter

        Returns:
            Complete optimization report with recommendations
        """
        try:
            # Get funnel data
            funnel_data = self._calculate_funnel_metrics(
                start_date, end_date, client_id
            )

            # Analyze drop-offs
            drop_offs = self._analyze_drop_offs(funnel_data)

            # Categorize recommendations
            quick_wins = [
                d for d in drop_offs
                if d.implementation_effort == 'low' and
                float(d.expected_improvement.strip('%')) > 10
            ]

            high_impact = [
                d for d in drop_offs
                if float(d.expected_improvement.strip('%')) > 20
            ]

            # Calculate estimated ROI
            roi = self._estimate_roi(funnel_data, drop_offs)

            return FunnelOptimizationReport(
                period_start=start_date,
                period_end=end_date,
                total_sessions=funnel_data['total_sessions'],
                overall_conversion_rate=funnel_data['conversion_rate'],
                drop_offs=drop_offs,
                quick_wins=self._format_recommendations(quick_wins),
                high_impact_changes=self._format_recommendations(high_impact),
                estimated_roi=roi
            )

        except (ValidationError, DatabaseError) as e:
            logger.error(f"Error analyzing funnel: {str(e)}", exc_info=True)
            raise

    def _calculate_funnel_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """Calculate basic funnel metrics"""
        try:
            # Build base queryset
            sessions_query = ConversationSession.objects.filter(
                cdtz__gte=start_date,
                cdtz__lte=end_date
            )

            if client_id:
                sessions_query = sessions_query.filter(client_id=client_id)

            # Count sessions by state
            state_counts = sessions_query.values('current_state').annotate(
                count=Count('session_id')
            )

            total_sessions = sessions_query.count()

            # Calculate stage progression
            started = sessions_query.filter(
                current_state=ConversationSession.StateChoices.STARTED
            ).count()

            in_progress = sessions_query.filter(
                current_state=ConversationSession.StateChoices.IN_PROGRESS
            ).count()

            awaiting_approval = sessions_query.filter(
                current_state=ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            ).count()

            completed = sessions_query.filter(
                current_state=ConversationSession.StateChoices.COMPLETED
            ).count()

            # Calculate conversion rate
            conversion_rate = (completed / total_sessions * 100) if total_sessions > 0 else 0

            return {
                'total_sessions': total_sessions,
                'started': started,
                'in_progress': in_progress,
                'awaiting_approval': awaiting_approval,
                'completed': completed,
                'conversion_rate': conversion_rate,
                'state_counts': list(state_counts)
            }

        except DatabaseError as e:
            logger.error(f"Database error calculating funnel metrics: {str(e)}")
            raise

    def _analyze_drop_offs(
        self,
        funnel_data: Dict[str, Any]
    ) -> List[DropOffInsight]:
        """Analyze drop-off points and diagnose issues"""
        drop_offs = []

        # Analyze Started -> In Progress
        if funnel_data['started'] > 0:
            drop_rate = 1 - (funnel_data['in_progress'] / funnel_data['started'])
            if drop_rate > self.HIGH_DROP_OFF_THRESHOLD:
                insight = self._diagnose_start_drop_off(drop_rate, funnel_data)
                drop_offs.append(insight)

        # Analyze In Progress -> Awaiting Approval
        if funnel_data['in_progress'] > 0:
            drop_rate = 1 - (funnel_data['awaiting_approval'] / funnel_data['in_progress'])
            if drop_rate > self.HIGH_DROP_OFF_THRESHOLD:
                insight = self._diagnose_progress_drop_off(drop_rate, funnel_data)
                drop_offs.append(insight)

        # Analyze Awaiting Approval -> Completed
        if funnel_data['awaiting_approval'] > 0:
            drop_rate = 1 - (funnel_data['completed'] / funnel_data['awaiting_approval'])
            if drop_rate > self.HIGH_DROP_OFF_THRESHOLD:
                insight = self._diagnose_approval_drop_off(drop_rate, funnel_data)
                drop_offs.append(insight)

        # Sort by impact (drop-off rate * sessions affected)
        drop_offs.sort(
            key=lambda x: x.drop_off_rate * x.sessions_dropped,
            reverse=True
        )

        return drop_offs

    def _diagnose_start_drop_off(
        self,
        drop_rate: float,
        funnel_data: Dict[str, Any]
    ) -> DropOffInsight:
        """Diagnose issues at start stage"""
        sessions_dropped = int(funnel_data['started'] * drop_rate)

        if drop_rate > self.CRITICAL_DROP_OFF_THRESHOLD:
            # Critical drop-off - likely UX or technical issue
            return DropOffInsight(
                stage='Started → In Progress',
                drop_off_rate=drop_rate,
                sessions_dropped=sessions_dropped,
                issue_category='ux',
                root_cause='Users abandoning immediately - unclear value proposition or confusing initial experience',
                recommendation='Simplify initial prompt, add progressive disclosure, improve loading time',
                expected_improvement='30-40%',
                implementation_effort='medium'
            )
        else:
            return DropOffInsight(
                stage='Started → In Progress',
                drop_off_rate=drop_rate,
                sessions_dropped=sessions_dropped,
                issue_category='content',
                root_cause='Initial engagement issue - users not understanding next steps',
                recommendation='Add guided hints, example inputs, or quick-start tutorial',
                expected_improvement='15-25%',
                implementation_effort='low'
            )

    def _diagnose_progress_drop_off(
        self,
        drop_rate: float,
        funnel_data: Dict[str, Any]
    ) -> DropOffInsight:
        """Diagnose issues during progress stage"""
        sessions_dropped = int(funnel_data['in_progress'] * drop_rate)

        if drop_rate > self.CRITICAL_DROP_OFF_THRESHOLD:
            return DropOffInsight(
                stage='In Progress → Awaiting Approval',
                drop_off_rate=drop_rate,
                sessions_dropped=sessions_dropped,
                issue_category='performance',
                root_cause='Long processing times causing user abandonment',
                recommendation='Implement streaming responses, add progress indicators, optimize LLM latency',
                expected_improvement='35-45%',
                implementation_effort='high'
            )
        else:
            return DropOffInsight(
                stage='In Progress → Awaiting Approval',
                drop_off_rate=drop_rate,
                sessions_dropped=sessions_dropped,
                issue_category='complexity',
                root_cause='Too many questions or unclear question flow',
                recommendation='Reduce question count, add skip options, implement smart defaults',
                expected_improvement='20-30%',
                implementation_effort='medium'
            )

    def _diagnose_approval_drop_off(
        self,
        drop_rate: float,
        funnel_data: Dict[str, Any]
    ) -> DropOffInsight:
        """Diagnose issues at approval stage"""
        sessions_dropped = int(funnel_data['awaiting_approval'] * drop_rate)

        if drop_rate > self.CRITICAL_DROP_OFF_THRESHOLD:
            return DropOffInsight(
                stage='Awaiting Approval → Completed',
                drop_off_rate=drop_rate,
                sessions_dropped=sessions_dropped,
                issue_category='content',
                root_cause='Generated recommendations not meeting user expectations',
                recommendation='Improve LLM prompts, add edit capabilities, show confidence scores',
                expected_improvement='40-50%',
                implementation_effort='medium'
            )
        else:
            return DropOffInsight(
                stage='Awaiting Approval → Completed',
                drop_off_rate=drop_rate,
                sessions_dropped=sessions_dropped,
                issue_category='ux',
                root_cause='Unclear approval process or final steps',
                recommendation='Add clear approval CTAs, explain what happens next, add preview mode',
                expected_improvement='15-25%',
                implementation_effort='low'
            )

    def _estimate_roi(
        self,
        funnel_data: Dict[str, Any],
        drop_offs: List[DropOffInsight]
    ) -> Dict[str, Any]:
        """Estimate ROI of implementing recommendations"""
        total_sessions = funnel_data['total_sessions']
        current_completion_rate = funnel_data['conversion_rate'] / 100

        # Calculate potential improvement
        total_potential_improvement = sum(
            float(d.expected_improvement.strip('%').split('-')[0]) / 100
            for d in drop_offs
        )

        # Estimate new completion rate (conservative estimate)
        estimated_new_rate = min(
            current_completion_rate + (total_potential_improvement * 0.5),
            0.95  # Cap at 95%
        )

        additional_completions = int(
            total_sessions * (estimated_new_rate - current_completion_rate)
        )

        return {
            'current_conversion_rate': f"{funnel_data['conversion_rate']:.1f}%",
            'estimated_new_rate': f"{estimated_new_rate * 100:.1f}%",
            'additional_completions_per_period': additional_completions,
            'improvement_percentage': f"{((estimated_new_rate / current_completion_rate - 1) * 100):.1f}%",
            'implementation_priority': self._prioritize_implementations(drop_offs)
        }

    def _prioritize_implementations(
        self,
        drop_offs: List[DropOffInsight]
    ) -> List[str]:
        """Prioritize implementations by ROI"""
        # Score each drop-off: (impact * expected_improvement) / effort
        scored = []
        effort_scores = {'low': 1, 'medium': 3, 'high': 5}

        for drop_off in drop_offs:
            impact = drop_off.drop_off_rate * drop_off.sessions_dropped
            improvement = float(drop_off.expected_improvement.strip('%').split('-')[0])
            effort = effort_scores.get(drop_off.implementation_effort, 3)

            score = (impact * improvement) / effort
            scored.append((score, drop_off.stage, drop_off.recommendation))

        # Sort by score descending
        scored.sort(reverse=True)

        return [f"{stage}: {rec}" for _, stage, rec in scored[:3]]

    def _format_recommendations(
        self,
        drop_offs: List[DropOffInsight]
    ) -> List[Dict[str, Any]]:
        """Format drop-offs as actionable recommendations"""
        return [
            {
                'stage': d.stage,
                'issue': d.root_cause,
                'action': d.recommendation,
                'expected_impact': d.expected_improvement,
                'effort': d.implementation_effort,
                'priority': 'high' if d.drop_off_rate > self.CRITICAL_DROP_OFF_THRESHOLD else 'medium'
            }
            for d in drop_offs
        ]
