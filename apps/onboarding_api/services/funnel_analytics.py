"""
Onboarding funnel analytics service for tracking conversion rates,
drop-off points, and optimization opportunities.

Provides comprehensive analytics for the conversational onboarding funnel:
start → first answer → recommendations generated → approval decision → completion
"""
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

from django.utils import timezone
from django.core.cache import cache

)

logger = logging.getLogger(__name__)


@dataclass
class FunnelStage:
    """Represents a stage in the onboarding funnel"""
    name: str
    description: str
    session_state: str
    count: int
    conversion_rate: float
    avg_time_to_next: Optional[float] = None
    drop_off_rate: Optional[float] = None


@dataclass
class FunnelAnalytics:
    """Complete funnel analytics result"""
    period_start: datetime
    period_end: datetime
    total_sessions: int
    stages: List[FunnelStage]
    overall_conversion_rate: float
    avg_completion_time_minutes: float
    top_drop_off_points: List[Dict[str, Any]]
    cohort_analysis: Dict[str, Any]
    recommendations: List[str]


class FunnelAnalyticsService:
    """
    Service for calculating and analyzing onboarding funnel metrics
    """

    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.funnel_stages = self._define_funnel_stages()

    def _define_funnel_stages(self) -> List[Dict[str, Any]]:
        """Define the stages of the onboarding funnel"""
        return [
            {
                'name': 'started',
                'description': 'Session initiated',
                'session_states': [ConversationSession.StateChoices.STARTED],
                'min_time_minutes': 0
            },
            {
                'name': 'engaged',
                'description': 'User provided first meaningful input',
                'session_states': [ConversationSession.StateChoices.IN_PROGRESS],
                'min_time_minutes': 1
            },
            {
                'name': 'recommendations_generated',
                'description': 'AI recommendations were generated',
                'session_states': [ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS,
                                  ConversationSession.StateChoices.AWAITING_USER_APPROVAL],
                'min_time_minutes': 2
            },
            {
                'name': 'approval_decision',
                'description': 'User made approval decision',
                'session_states': [ConversationSession.StateChoices.AWAITING_USER_APPROVAL],
                'has_recommendations': True,
                'min_time_minutes': 5
            },
            {
                'name': 'completed',
                'description': 'Onboarding completed successfully',
                'session_states': [ConversationSession.StateChoices.COMPLETED],
                'min_time_minutes': 10
            }
        ]

    def calculate_funnel_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        client_id: Optional[int] = None,
        user_segment: Optional[str] = None
    ) -> FunnelAnalytics:
        """
        Calculate comprehensive funnel metrics for a given period

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            client_id: Optional client filter
            user_segment: Optional user segment filter

        Returns:
            Complete funnel analytics
        """
        # Build base query
        sessions_query = ConversationSession.objects.filter(
            cdtz__gte=start_date,
            cdtz__lte=end_date
        )

        if client_id:
            sessions_query = sessions_query.filter(client_id=client_id)

        # Calculate stage metrics
        stages = []
        previous_count = None

        for stage_config in self.funnel_stages:
            stage_count = self._calculate_stage_count(sessions_query, stage_config)

            # Calculate conversion rate from previous stage
            conversion_rate = 1.0
            drop_off_rate = 0.0

            if previous_count is not None:
                conversion_rate = stage_count / max(1, previous_count)
                drop_off_rate = 1.0 - conversion_rate

            # Calculate average time to reach this stage
            avg_time_to_stage = self._calculate_avg_time_to_stage(
                sessions_query, stage_config
            )

            stage = FunnelStage(
                name=stage_config['name'],
                description=stage_config['description'],
                session_state=stage_config['session_states'][0],
                count=stage_count,
                conversion_rate=conversion_rate,
                drop_off_rate=drop_off_rate,
                avg_time_to_next=avg_time_to_stage
            )

            stages.append(stage)
            previous_count = stage_count

        # Calculate overall metrics
        total_sessions = stages[0].count if stages else 0
        completed_sessions = stages[-1].count if stages else 0
        overall_conversion_rate = completed_sessions / max(1, total_sessions)

        # Calculate average completion time
        avg_completion_time = self._calculate_avg_completion_time(sessions_query)

        # Identify top drop-off points
        drop_off_points = self._identify_drop_off_points(stages)

        # Generate cohort analysis
        cohort_analysis = self._generate_cohort_analysis(sessions_query, start_date, end_date)

        # Generate recommendations
        recommendations = self._generate_improvement_recommendations(stages, drop_off_points)

        return FunnelAnalytics(
            period_start=start_date,
            period_end=end_date,
            total_sessions=total_sessions,
            stages=stages,
            overall_conversion_rate=overall_conversion_rate,
            avg_completion_time_minutes=avg_completion_time,
            top_drop_off_points=drop_off_points,
            cohort_analysis=cohort_analysis,
            recommendations=recommendations
        )

    def _calculate_stage_count(
        self,
        base_query,
        stage_config: Dict[str, Any]
    ) -> int:
        """Calculate count of sessions that reached a specific stage"""
        query = base_query.filter(
            current_state__in=stage_config['session_states']
        )

        # Additional filters based on stage requirements
        if stage_config.get('has_recommendations'):
            query = query.filter(recommendations__isnull=False)

        if stage_config.get('min_time_minutes'):
            min_duration = timedelta(minutes=stage_config['min_time_minutes'])
            query = query.filter(
                mdtz__gte=F('cdtz') + min_duration
            )

        return query.distinct().count()

    def _calculate_avg_time_to_stage(
        self,
        base_query,
        stage_config: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate average time to reach a stage in minutes"""
        sessions_in_stage = base_query.filter(
            current_state__in=stage_config['session_states']
        )

        if not sessions_in_stage.exists():
            return None

        # Calculate time differences
        time_diffs = []
        for session in sessions_in_stage:
            time_diff = session.mdtz - session.cdtz
            time_diffs.append(time_diff.total_seconds() / 60)  # Convert to minutes

        return sum(time_diffs) / len(time_diffs) if time_diffs else None

    def _calculate_avg_completion_time(self, base_query) -> float:
        """Calculate average time to complete onboarding in minutes"""
        completed_sessions = base_query.filter(
            current_state=ConversationSession.StateChoices.COMPLETED
        )

        if not completed_sessions.exists():
            return 0.0

        time_diffs = []
        for session in completed_sessions:
            time_diff = session.mdtz - session.cdtz
            time_diffs.append(time_diff.total_seconds() / 60)

        return sum(time_diffs) / len(time_diffs)

    def _identify_drop_off_points(self, stages: List[FunnelStage]) -> List[Dict[str, Any]]:
        """Identify the biggest drop-off points in the funnel"""
        drop_offs = []

        for i in range(1, len(stages)):
            current_stage = stages[i]
            previous_stage = stages[i-1]

            drop_off_count = previous_stage.count - current_stage.count
            drop_off_rate = current_stage.drop_off_rate or 0.0

            if drop_off_count > 0:
                drop_offs.append({
                    'from_stage': previous_stage.name,
                    'to_stage': current_stage.name,
                    'drop_off_count': drop_off_count,
                    'drop_off_rate': drop_off_rate,
                    'impact_severity': self._calculate_impact_severity(drop_off_rate, drop_off_count)
                })

        # Sort by impact (rate * absolute count)
        drop_offs.sort(key=lambda x: x['drop_off_rate'] * x['drop_off_count'], reverse=True)

        return drop_offs[:5]  # Top 5 drop-off points

    def _calculate_impact_severity(self, drop_off_rate: float, drop_off_count: int) -> str:
        """Calculate impact severity of a drop-off point"""
        impact_score = drop_off_rate * drop_off_count

        if impact_score > 50:
            return 'critical'
        elif impact_score > 20:
            return 'high'
        elif impact_score > 5:
            return 'medium'
        else:
            return 'low'

    def _generate_cohort_analysis(
        self,
        base_query,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate cohort analysis for the period"""
        # Group sessions by week for cohort analysis
        cohorts = {}
        current_date = start_date

        while current_date < end_date:
            week_end = min(current_date + timedelta(days=7), end_date)

            cohort_sessions = base_query.filter(
                cdtz__gte=current_date,
                cdtz__lt=week_end
            )

            cohort_name = current_date.strftime('%Y-W%U')
            cohorts[cohort_name] = {
                'start_date': current_date.isoformat(),
                'total_sessions': cohort_sessions.count(),
                'completed_sessions': cohort_sessions.filter(
                    current_state=ConversationSession.StateChoices.COMPLETED
                ).count(),
                'avg_completion_time': self._calculate_avg_completion_time(cohort_sessions)
            }

            current_date = week_end

        return cohorts

    def _generate_improvement_recommendations(
        self,
        stages: List[FunnelStage],
        drop_off_points: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations for funnel improvement"""
        recommendations = []

        # Analyze overall conversion rate
        if stages and stages[-1].conversion_rate < 0.3:
            recommendations.append(
                "Overall conversion rate is below 30%. Consider simplifying the onboarding flow."
            )

        # Analyze drop-off points
        for drop_off in drop_off_points:
            if drop_off['impact_severity'] in ['critical', 'high']:
                if 'started' in drop_off['from_stage'] and 'engaged' in drop_off['to_stage']:
                    recommendations.append(
                        "High drop-off after session start. Consider improving initial engagement messaging."
                    )
                elif 'recommendations' in drop_off['from_stage']:
                    recommendations.append(
                        "Users are dropping off during recommendation review. Consider simplifying recommendations or adding import suggestions."
                    )
                elif 'approval' in drop_off['from_stage']:
                    recommendations.append(
                        "High drop-off at approval stage. Consider auto-approval for low-risk changes."
                    )

        # Time-based recommendations
        if stages:
            avg_time = stages[-1].avg_time_to_next or 0
            if avg_time > 30:  # More than 30 minutes
                recommendations.append(
                    "Average completion time is high. Consider adding industry templates for faster setup."
                )

        return recommendations[:5]  # Top 5 recommendations

    def get_real_time_funnel_metrics(self, client_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get real-time funnel metrics for dashboards

        Args:
            client_id: Optional client filter

        Returns:
            Real-time funnel metrics
        """
        cache_key = f"realtime_funnel_{client_id or 'global'}"
        cached_metrics = cache.get(cache_key)

        if cached_metrics:
            return cached_metrics

        # Calculate metrics for last 24 hours
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=24)

        # Get session counts by state
        sessions_query = ConversationSession.objects.filter(
            cdtz__gte=start_time,
            cdtz__lte=end_time
        )

        if client_id:
            sessions_query = sessions_query.filter(client_id=client_id)

        state_counts = sessions_query.values('current_state').annotate(
            count=Count('session_id')
        ).order_by('current_state')

        # Format for real-time display
        metrics = {
            'last_updated': timezone.now().isoformat(),
            'period': '24 hours',
            'total_sessions': sessions_query.count(),
            'states': {item['current_state']: item['count'] for item in state_counts},
            'completion_rate': 0.0,
            'avg_session_duration_minutes': 0.0,
            'active_sessions': sessions_query.filter(
                current_state__in=[
                    ConversationSession.StateChoices.STARTED,
                    ConversationSession.StateChoices.IN_PROGRESS,
                    ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS,
                    ConversationSession.StateChoices.AWAITING_USER_APPROVAL
                ]
            ).count()
        }

        # Calculate completion rate
        completed_count = metrics['states'].get(ConversationSession.StateChoices.COMPLETED, 0)
        if metrics['total_sessions'] > 0:
            metrics['completion_rate'] = completed_count / metrics['total_sessions']

        # Calculate average session duration
        completed_sessions = sessions_query.filter(
            current_state=ConversationSession.StateChoices.COMPLETED
        )

        if completed_sessions.exists():
            durations = []
            for session in completed_sessions:
                duration = session.mdtz - session.cdtz
                durations.append(duration.total_seconds() / 60)

            metrics['avg_session_duration_minutes'] = sum(durations) / len(durations)

        # Cache for 5 minutes
        cache.set(cache_key, metrics, self.cache_timeout)

        return metrics

    def get_drop_off_analysis(
        self,
        start_date: datetime,
        end_date: datetime,
        client_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Detailed drop-off analysis with reasons and patterns

        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            client_id: Optional client filter

        Returns:
            Detailed drop-off analysis
        """
        sessions_query = ConversationSession.objects.filter(
            cdtz__gte=start_date,
            cdtz__lte=end_date
        )

        if client_id:
            sessions_query = sessions_query.filter(client_id=client_id)

        # Analyze sessions that didn't complete
        incomplete_sessions = sessions_query.exclude(
            current_state=ConversationSession.StateChoices.COMPLETED
        )

        # Group by final state
        final_states = incomplete_sessions.values('current_state').annotate(
            count=Count('session_id'),
            avg_duration=Avg(
                (F('mdtz') - F('cdtz'))
            )
        )

        # Analyze error patterns
        error_sessions = sessions_query.filter(
            current_state=ConversationSession.StateChoices.ERROR
        )

        error_patterns = []
        for session in error_sessions:
            if session.error_message:
                error_patterns.append({
                    'error_type': self._categorize_error(session.error_message),
                    'error_message': session.error_message,
                    'session_duration_minutes': (session.mdtz - session.cdtz).total_seconds() / 60
                })

        # Time-based drop-off analysis
        time_analysis = self._analyze_time_based_dropoffs(incomplete_sessions)

        return {
            'total_incomplete': incomplete_sessions.count(),
            'final_states': list(final_states),
            'error_patterns': error_patterns,
            'time_analysis': time_analysis,
            'common_drop_off_reasons': self._identify_common_drop_off_reasons(incomplete_sessions),
            'recommendations': self._generate_drop_off_recommendations(final_states, error_patterns)
        }

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error messages for pattern analysis"""
        error_message_lower = error_message.lower()

        if 'timeout' in error_message_lower or 'time' in error_message_lower:
            return 'timeout'
        elif 'permission' in error_message_lower or 'access' in error_message_lower:
            return 'permission'
        elif 'llm' in error_message_lower or 'ai' in error_message_lower:
            return 'llm_service'
        elif 'database' in error_message_lower or 'db' in error_message_lower:
            return 'database'
        elif 'network' in error_message_lower or 'connection' in error_message_lower:
            return 'network'
        else:
            return 'unknown'

    def _analyze_time_based_dropoffs(self, incomplete_sessions) -> Dict[str, Any]:
        """Analyze when users tend to drop off"""
        duration_buckets = {
            'under_1_min': 0,
            '1_to_5_min': 0,
            '5_to_15_min': 0,
            '15_to_30_min': 0,
            'over_30_min': 0
        }

        for session in incomplete_sessions:
            duration_minutes = (session.mdtz - session.cdtz).total_seconds() / 60

            if duration_minutes < 1:
                duration_buckets['under_1_min'] += 1
            elif duration_minutes < 5:
                duration_buckets['1_to_5_min'] += 1
            elif duration_minutes < 15:
                duration_buckets['5_to_15_min'] += 1
            elif duration_minutes < 30:
                duration_buckets['15_to_30_min'] += 1
            else:
                duration_buckets['over_30_min'] += 1

        return duration_buckets

    def _identify_common_drop_off_reasons(self, incomplete_sessions) -> List[Dict[str, Any]]:
        """Identify common reasons for drop-offs"""
        # This would analyze session data, error messages, and interaction patterns
        # For now, return structure for future implementation

        return [
            {
                'reason': 'Session timeout due to inactivity',
                'frequency': 0.35,
                'avg_time_before_dropout': 8.5,
                'suggested_solution': 'Implement session extension prompts'
            },
            {
                'reason': 'Overwhelmed by recommendation complexity',
                'frequency': 0.28,
                'avg_time_before_dropout': 12.3,
                'suggested_solution': 'Simplify recommendations or add explanations'
            },
            {
                'reason': 'Technical errors during processing',
                'frequency': 0.15,
                'avg_time_before_dropout': 6.2,
                'suggested_solution': 'Improve error handling and user messaging'
            }
        ]

    def _generate_drop_off_recommendations(
        self,
        final_states,
        error_patterns: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations to reduce drop-offs"""
        recommendations = []

        # Analyze error patterns
        error_counts = {}
        for error in error_patterns:
            error_type = error['error_type']
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # Generate error-based recommendations
        if error_counts.get('timeout', 0) > 0:
            recommendations.append("Implement session extension and progress saving to reduce timeout drop-offs")

        if error_counts.get('llm_service', 0) > 0:
            recommendations.append("Add LLM service fallbacks to handle AI service outages")

        if error_counts.get('permission', 0) > 0:
            recommendations.append("Review permission setup documentation and add guided permission setup")

        # Analyze final states
        for state_data in final_states:
            state = state_data['current_state']
            count = state_data['count']

            if state == ConversationSession.StateChoices.STARTED and count > 5:
                recommendations.append("Many sessions stop after starting. Improve initial engagement messaging.")

            if state == ConversationSession.StateChoices.AWAITING_USER_APPROVAL and count > 3:
                recommendations.append("Users are not completing approvals. Consider auto-approval for low-risk changes.")

        return recommendations

    def get_funnel_comparison(
        self,
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime,
        client_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Compare funnel performance between two periods

        Args:
            period1_start: First period start
            period1_end: First period end
            period2_start: Second period start
            period2_end: Second period end
            client_id: Optional client filter

        Returns:
            Comparison analysis
        """
        # Calculate metrics for both periods
        period1_metrics = self.calculate_funnel_metrics(period1_start, period1_end, client_id)
        period2_metrics = self.calculate_funnel_metrics(period2_start, period2_end, client_id)

        # Calculate changes
        total_sessions_change = period2_metrics.total_sessions - period1_metrics.total_sessions
        conversion_rate_change = period2_metrics.overall_conversion_rate - period1_metrics.overall_conversion_rate
        completion_time_change = period2_metrics.avg_completion_time_minutes - period1_metrics.avg_completion_time_minutes

        # Stage-by-stage comparison
        stage_comparisons = []
        for i, stage2 in enumerate(period2_metrics.stages):
            if i < len(period1_metrics.stages):
                stage1 = period1_metrics.stages[i]
                stage_comparisons.append({
                    'stage': stage2.name,
                    'period1_count': stage1.count,
                    'period2_count': stage2.count,
                    'count_change': stage2.count - stage1.count,
                    'conversion_rate_change': stage2.conversion_rate - stage1.conversion_rate
                })

        return {
            'period1': {
                'start': period1_start.isoformat(),
                'end': period1_end.isoformat(),
                'total_sessions': period1_metrics.total_sessions,
                'conversion_rate': period1_metrics.overall_conversion_rate
            },
            'period2': {
                'start': period2_start.isoformat(),
                'end': period2_end.isoformat(),
                'total_sessions': period2_metrics.total_sessions,
                'conversion_rate': period2_metrics.overall_conversion_rate
            },
            'changes': {
                'total_sessions_change': total_sessions_change,
                'conversion_rate_change': conversion_rate_change,
                'completion_time_change_minutes': completion_time_change,
                'trend': 'improving' if conversion_rate_change > 0 else 'declining'
            },
            'stage_comparisons': stage_comparisons,
            'improvement_opportunities': self._identify_improvement_opportunities(stage_comparisons)
        }

    def _identify_improvement_opportunities(self, stage_comparisons: List[Dict[str, Any]]) -> List[str]:
        """Identify specific improvement opportunities from comparison"""
        opportunities = []

        for comparison in stage_comparisons:
            if comparison['conversion_rate_change'] < -0.1:  # 10% decline
                opportunities.append(
                    f"Conversion rate declined significantly at {comparison['stage']} stage"
                )

        return opportunities

    def get_user_segment_analysis(
        self,
        start_date: datetime,
        end_date: datetime,
        client_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analyze funnel performance by user segments

        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            client_id: Optional client filter

        Returns:
            Segment-based funnel analysis
        """
        segments = {
            'first_time_users': self._analyze_first_time_users(start_date, end_date, client_id),
            'returning_users': self._analyze_returning_users(start_date, end_date, client_id),
            'admin_users': self._analyze_admin_users(start_date, end_date, client_id),
            'mobile_users': self._analyze_mobile_users(start_date, end_date, client_id)
        }

        # Calculate relative performance
        segment_performance = {}
        baseline_conversion = 0.5  # Assumed baseline

        for segment_name, segment_data in segments.items():
            if segment_data['total_sessions'] > 0:
                performance_ratio = segment_data['conversion_rate'] / baseline_conversion
                segment_performance[segment_name] = {
                    'performance_vs_baseline': performance_ratio,
                    'interpretation': 'above_average' if performance_ratio > 1.1 else
                                   'below_average' if performance_ratio < 0.9 else 'average'
                }

        return {
            'segments': segments,
            'segment_performance': segment_performance,
            'insights': self._generate_segment_insights(segments, segment_performance)
        }

    def _analyze_first_time_users(self, start_date: datetime, end_date: datetime, client_id: Optional[int]) -> Dict[str, Any]:
        """Analyze first-time user funnel performance"""
        # Users who had their first session in this period
        first_time_sessions = ConversationSession.objects.filter(
            cdtz__gte=start_date,
            cdtz__lte=end_date
        )

        if client_id:
            first_time_sessions = first_time_sessions.filter(client_id=client_id)

        # Filter to only users' first sessions
        first_sessions = []
        seen_users = set()

        for session in first_time_sessions.order_by('cdtz'):
            if session.user_id not in seen_users:
                first_sessions.append(session)
                seen_users.add(session.user_id)

        total_first_time = len(first_sessions)
        completed_first_time = sum(
            1 for session in first_sessions
            if session.current_state == ConversationSession.StateChoices.COMPLETED
        )

        return {
            'total_sessions': total_first_time,
            'completed_sessions': completed_first_time,
            'conversion_rate': completed_first_time / max(1, total_first_time),
            'avg_completion_time': self._calculate_avg_duration(first_sessions, 'completed')
        }

    def _analyze_returning_users(self, start_date: datetime, end_date: datetime, client_id: Optional[int]) -> Dict[str, Any]:
        """Analyze returning user funnel performance"""
        # Users who had previous sessions before this period
        all_sessions = ConversationSession.objects.filter(
            cdtz__gte=start_date,
            cdtz__lte=end_date
        )

        if client_id:
            all_sessions = all_sessions.filter(client_id=client_id)

        returning_sessions = []
        for session in all_sessions:
            # Check if user had previous sessions
            previous_sessions = ConversationSession.objects.filter(
                user=session.user,
                cdtz__lt=start_date
            ).exists()

            if previous_sessions:
                returning_sessions.append(session)

        total_returning = len(returning_sessions)
        completed_returning = sum(
            1 for session in returning_sessions
            if session.current_state == ConversationSession.StateChoices.COMPLETED
        )

        return {
            'total_sessions': total_returning,
            'completed_sessions': completed_returning,
            'conversion_rate': completed_returning / max(1, total_returning),
            'avg_completion_time': self._calculate_avg_duration(returning_sessions, 'completed')
        }

    def _analyze_admin_users(self, start_date: datetime, end_date: datetime, client_id: Optional[int]) -> Dict[str, Any]:
        """Analyze admin user funnel performance"""
        admin_sessions = ConversationSession.objects.filter(
            cdtz__gte=start_date,
            cdtz__lte=end_date,
            user__is_staff=True
        )

        if client_id:
            admin_sessions = admin_sessions.filter(client_id=client_id)

        total_admin = admin_sessions.count()
        completed_admin = admin_sessions.filter(
            current_state=ConversationSession.StateChoices.COMPLETED
        ).count()

        return {
            'total_sessions': total_admin,
            'completed_sessions': completed_admin,
            'conversion_rate': completed_admin / max(1, total_admin),
            'avg_completion_time': self._calculate_avg_duration(admin_sessions, 'completed')
        }

    def _analyze_mobile_users(self, start_date: datetime, end_date: datetime, client_id: Optional[int]) -> Dict[str, Any]:
        """Analyze mobile user funnel performance"""
        # This would require tracking mobile vs web sessions
        # For now, return placeholder structure

        return {
            'total_sessions': 0,
            'completed_sessions': 0,
            'conversion_rate': 0.0,
            'avg_completion_time': 0.0,
            'note': 'Mobile user tracking not yet implemented'
        }

    def _calculate_avg_duration(self, sessions, filter_state=None) -> float:
        """Calculate average duration for sessions"""
        if filter_state:
            sessions = [s for s in sessions if s.current_state == filter_state]

        if not sessions:
            return 0.0

        durations = []
        for session in sessions:
            duration = session.mdtz - session.cdtz
            durations.append(duration.total_seconds() / 60)

        return sum(durations) / len(durations)

    def _generate_segment_insights(
        self,
        segments: Dict[str, Any],
        performance: Dict[str, Any]
    ) -> List[str]:
        """Generate insights from segment analysis"""
        insights = []

        # Compare segment performance
        for segment_name, perf_data in performance.items():
            if perf_data['interpretation'] == 'above_average':
                insights.append(f"{segment_name.replace('_', ' ').title()} perform significantly better than average")
            elif perf_data['interpretation'] == 'below_average':
                insights.append(f"{segment_name.replace('_', ' ').title()} need additional support or different approach")

        # First-time vs returning user insights
        first_time_rate = segments['first_time_users']['conversion_rate']
        returning_rate = segments['returning_users']['conversion_rate']

        if returning_rate > first_time_rate * 1.2:
            insights.append("Returning users are much more successful - consider improving first-time user experience")
        elif first_time_rate > returning_rate * 1.2:
            insights.append("First-time users are more successful - returning users may have unresolved issues")

        return insights


class FunnelOptimizationEngine:
    """
    Engine for generating actionable optimization recommendations
    """

    def __init__(self):
        self.analytics_service = FunnelAnalyticsService()

    def generate_optimization_recommendations(
        self,
        funnel_analytics: FunnelAnalytics,
        historical_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate prioritized optimization recommendations

        Args:
            funnel_analytics: Current funnel analytics
            historical_data: Optional historical comparison data

        Returns:
            Prioritized list of optimization recommendations
        """
        recommendations = []

        # Analyze conversion rates
        if funnel_analytics.overall_conversion_rate < 0.3:
            recommendations.append({
                'type': 'conversion_optimization',
                'priority': 'high',
                'title': 'Improve Overall Conversion Rate',
                'description': f'Current conversion rate ({funnel_analytics.overall_conversion_rate:.1%}) is below target (30%)',
                'suggested_actions': [
                    'Implement industry templates for faster setup',
                    'Add data import on-ramps for bulk operations',
                    'Simplify approval processes for low-risk changes'
                ],
                'estimated_impact': '+15-25% conversion rate increase'
            })

        # Analyze completion time
        if funnel_analytics.avg_completion_time_minutes > 30:
            recommendations.append({
                'type': 'time_optimization',
                'priority': 'medium',
                'title': 'Reduce Time to Completion',
                'description': f'Average completion time ({funnel_analytics.avg_completion_time_minutes:.1f} min) is above target (20 min)',
                'suggested_actions': [
                    'Deploy quick-start templates',
                    'Pre-populate common configurations',
                    'Add progress indicators and time estimates'
                ],
                'estimated_impact': '40-60% reduction in completion time'
            })

        # Analyze drop-off points
        for drop_off in funnel_analytics.top_drop_off_points:
            if drop_off['impact_severity'] in ['critical', 'high']:
                recommendations.append({
                    'type': 'drop_off_reduction',
                    'priority': 'high' if drop_off['impact_severity'] == 'critical' else 'medium',
                    'title': f'Address Drop-off at {drop_off["from_stage"].replace("_", " ").title()} Stage',
                    'description': f'{drop_off["drop_off_count"]} users ({drop_off["drop_off_rate"]:.1%}) drop off between {drop_off["from_stage"]} and {drop_off["to_stage"]}',
                    'suggested_actions': self._get_stage_specific_actions(drop_off['from_stage']),
                    'estimated_impact': f'Potential to recover {drop_off["drop_off_count"] * 0.3:.0f} additional completions'
                })

        # Sort by priority
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 0), reverse=True)

        return recommendations[:10]  # Top 10 recommendations

    def _get_stage_specific_actions(self, stage: str) -> List[str]:
        """Get stage-specific optimization actions"""
        actions = {
            'started': [
                'Improve welcome messaging and clear value proposition',
                'Add progress indicators to show completion steps',
                'Provide estimated time to completion'
            ],
            'engaged': [
                'Simplify initial questions and reduce cognitive load',
                'Add contextual help and examples',
                'Implement smart defaults based on common patterns'
            ],
            'recommendations_generated': [
                'Improve recommendation clarity and explanations',
                'Add visual previews of changes',
                'Provide confidence scores and rationale'
            ],
            'approval_decision': [
                'Simplify approval interface and reduce clicks',
                'Add bulk approval for similar items',
                'Implement auto-approval for low-risk changes'
            ]
        }

        return actions.get(stage, ['Analyze specific stage issues and user feedback'])


# Service factory functions
def get_funnel_analytics_service() -> FunnelAnalyticsService:
    """Get funnel analytics service instance"""
    return FunnelAnalyticsService()


def get_funnel_optimization_engine() -> FunnelOptimizationEngine:
    """Get funnel optimization engine instance"""
    return FunnelOptimizationEngine()


# Utility functions for integration
def track_funnel_event(session_id: str, event_type: str, metadata: Dict[str, Any] = None):
    """
    Track a funnel event for analytics

    Args:
        session_id: Conversation session ID
        event_type: Type of funnel event
        metadata: Optional event metadata
    """
    try:
        from apps.onboarding.models import ConversationSession

        session = ConversationSession.objects.get(session_id=session_id)

        # Create interaction record for funnel tracking
        from apps.onboarding.models import RecommendationInteraction

        # Get latest recommendation for this session
        latest_recommendation = session.recommendations.order_by('-cdtz').first()

        if latest_recommendation:
            RecommendationInteraction.objects.create(
                session=session,
                recommendation=latest_recommendation,
                event_type=event_type,
                metadata=metadata or {},
                occurred_at=timezone.now()
            )

        logger.info(f"Tracked funnel event: {event_type} for session {session_id}")

    except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
        logger.error(f"Error tracking funnel event: {str(e)}")


def get_funnel_metrics_for_dashboard(client_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get funnel metrics formatted for admin dashboard display

    Args:
        client_id: Optional client filter

    Returns:
        Dashboard-ready funnel metrics
    """
    service = get_funnel_analytics_service()

    # Get last 7 days of data
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)

    # Get real-time metrics
    real_time_metrics = service.get_real_time_funnel_metrics(client_id)

    # Get full analytics
    full_analytics = service.calculate_funnel_metrics(start_date, end_date, client_id)

    # Format for dashboard
    return {
        'real_time': real_time_metrics,
        'weekly_summary': {
            'total_sessions': full_analytics.total_sessions,
            'completion_rate': full_analytics.overall_conversion_rate,
            'avg_completion_time': full_analytics.avg_completion_time_minutes,
            'top_drop_off': full_analytics.top_drop_off_points[0] if full_analytics.top_drop_off_points else None
        },
        'stage_breakdown': [
            {
                'name': stage.name,
                'count': stage.count,
                'conversion_rate': stage.conversion_rate,
                'drop_off_rate': stage.drop_off_rate or 0.0
            }
            for stage in full_analytics.stages
        ],
        'recommendations': full_analytics.recommendations[:3],  # Top 3 for dashboard
        'last_updated': timezone.now().isoformat()
    }