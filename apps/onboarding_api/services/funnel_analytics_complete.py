"""
COMPLETE Funnel Analytics Implementation
Helper methods to add to funnel_analytics.py

These methods complete the FunnelAnalyticsService class.
Copy these into apps/onboarding_api/services/funnel_analytics.py after line 139.
"""

def _calculate_stage_count(self, sessions_query, stage_config):
    """Calculate number of sessions at this stage"""
    stage_sessions = sessions_query.filter(
        current_state__in=stage_config['session_states']
    )
    return stage_sessions.count()

def _calculate_avg_time_to_stage(self, sessions_query, stage_config):
    """Calculate average time to reach this stage (in seconds)"""
    try:
        stage_sessions = sessions_query.filter(
            current_state__in=stage_config['session_states']
        ).exclude(cdtz=None).exclude(mdtz=None)

        if not stage_sessions.exists():
            return None

        # Calculate time delta from session start to last modification
        total_time = 0
        count = 0

        for session in stage_sessions:
            time_delta = (session.mdtz - session.cdtz).total_seconds()
            if time_delta > 0:
                total_time += time_delta
                count += 1

        return total_time / count if count > 0 else None

    except (AttributeError, TypeError, ValueError) as e:
        logger.warning(f"Error calculating avg time to stage: {str(e)}")
        return None

def _calculate_drop_off_rate(self, stage_config, all_sessions, stage_index):
    """Calculate drop-off rate for this stage"""
    if stage_index == 0:
        return 0.0  # First stage has no drop-off

    try:
        current_stage_sessions = all_sessions.filter(
            current_state__in=stage_config['session_states']
        ).count()

        # Get previous stage count
        previous_stage_config = self.funnel_stages[stage_index - 1]
        previous_stage_sessions = all_sessions.filter(
            current_state__in=previous_stage_config['session_states']
        ).count()

        if previous_stage_sessions == 0:
            return 0.0

        drop_off_count = previous_stage_sessions - current_stage_sessions
        drop_off_rate = drop_off_count / previous_stage_sessions

        return max(0.0, min(1.0, drop_off_rate))  # Clamp between 0-1

    except (ZeroDivisionError, IndexError, AttributeError) as e:
        logger.warning(f"Error calculating drop-off rate: {str(e)}")
        return 0.0

def _calculate_overall_conversion(self, sessions):
    """Calculate overall conversion rate (% completing full onboarding)"""
    try:
        total_sessions = sessions.count()
        if total_sessions == 0:
            return 0.0

        completed_sessions = sessions.filter(
            current_state=ConversationSession.StateChoices.COMPLETED
        ).count()

        return (completed_sessions / total_sessions) * 100.0

    except (ZeroDivisionError, AttributeError) as e:
        logger.warning(f"Error calculating overall conversion: {str(e)}")
        return 0.0

def _calculate_avg_completion_time(self, sessions):
    """Calculate average time from start to completion (in minutes)"""
    try:
        completed_sessions = sessions.filter(
            current_state=ConversationSession.StateChoices.COMPLETED
        ).exclude(cdtz=None).exclude(mdtz=None)

        if not completed_sessions.exists():
            return 0.0

        total_time = 0
        count = 0

        for session in completed_sessions:
            time_delta = (session.mdtz - session.cdtz).total_seconds() / 60.0  # Convert to minutes
            if time_delta > 0:
                total_time += time_delta
                count += 1

        return total_time / count if count > 0 else 0.0

    except (AttributeError, TypeError, ValueError) as e:
        logger.warning(f"Error calculating avg completion time: {str(e)}")
        return 0.0

def _identify_top_drop_off_points(self, stages_data):
    """Identify stages with highest drop-off rates"""
    try:
        # Sort stages by drop-off rate (descending)
        sorted_stages = sorted(
            [s for s in stages_data if s.drop_off_rate is not None],
            key=lambda x: x.drop_off_rate,
            reverse=True
        )

        # Return top 3 drop-off points
        top_drop_offs = []
        for stage in sorted_stages[:3]:
            if stage.drop_off_rate > 0:
                top_drop_offs.append({
                    'stage': stage.name,
                    'drop_off_rate': round(stage.drop_off_rate * 100, 1),
                    'description': stage.description,
                    'severity': 'high' if stage.drop_off_rate > 0.3 else 'medium' if stage.drop_off_rate > 0.15 else 'low'
                })

        return top_drop_offs

    except (AttributeError, TypeError) as e:
        logger.warning(f"Error identifying top drop-off points: {str(e)}")
        return []

def _perform_cohort_analysis(self, sessions):
    """Analyze conversion rates by user segments"""
    try:
        cohort_data = {}

        # Cohort by language
        language_cohorts = sessions.values('language').annotate(
            total=Count('session_id'),
            completed=Count('session_id', filter=Q(current_state=ConversationSession.StateChoices.COMPLETED))
        )

        cohort_data['by_language'] = [
            {
                'segment': cohort['language'],
                'total_sessions': cohort['total'],
                'completed_sessions': cohort['completed'],
                'conversion_rate': round((cohort['completed'] / cohort['total'] * 100), 1) if cohort['total'] > 0 else 0
            }
            for cohort in language_cohorts
        ]

        # Cohort by time of day (if we have timezone data)
        hourly_cohorts = sessions.annotate(
            hour=TruncHour('cdtz')
        ).values('hour').annotate(
            total=Count('session_id'),
            completed=Count('session_id', filter=Q(current_state=ConversationSession.StateChoices.COMPLETED))
        ).order_by('hour')

        cohort_data['by_hour'] = [
            {
                'hour': cohort['hour'].hour if cohort['hour'] else 0,
                'total_sessions': cohort['total'],
                'conversion_rate': round((cohort['completed'] / cohort['total'] * 100), 1) if cohort['total'] > 0 else 0
            }
            for cohort in hourly_cohorts[:24]  # Limit to 24 hours
        ]

        # Cohort by conversation type (if available)
        type_cohorts = sessions.values('conversation_type').annotate(
            total=Count('session_id'),
            completed=Count('session_id', filter=Q(current_state=ConversationSession.StateChoices.COMPLETED))
        )

        cohort_data['by_type'] = [
            {
                'type': cohort['conversation_type'],
                'total_sessions': cohort['total'],
                'conversion_rate': round((cohort['completed'] / cohort['total'] * 100), 1) if cohort['total'] > 0 else 0
            }
            for cohort in type_cohorts
        ]

        return cohort_data

    except (AttributeError, TypeError, ValueError) as e:
        logger.warning(f"Error performing cohort analysis: {str(e)}")
        return {}

def _generate_optimization_recommendations(self, stages_data):
    """Generate AI-powered optimization recommendations"""
    recommendations = []

    try:
        for stage in stages_data:
            # High drop-off (>30%)
            if stage.drop_off_rate and stage.drop_off_rate > 0.3:
                recommendations.append({
                    'priority': 'high',
                    'stage': stage.name,
                    'issue': f'{round(stage.drop_off_rate * 100, 1)}% drop-off rate',
                    'recommendation': f'Simplify {stage.description} - consider breaking into smaller steps or providing more guidance',
                    'expected_impact': '10-15% conversion improvement'
                })

            # Long average time (>10 minutes for any non-final stage)
            if stage.avg_time_to_next and stage.avg_time_to_next > 600 and stage.name != 'completed':
                recommendations.append({
                    'priority': 'medium',
                    'stage': stage.name,
                    'issue': f'{round(stage.avg_time_to_next / 60, 1)} minutes average time',
                    'recommendation': 'Consider adding progress indicators or intermediate saves to reduce perceived complexity',
                    'expected_impact': '5-8% conversion improvement'
                })

            # Low engagement (conversion rate < 50% from previous stage)
            if stage.conversion_rate and stage.conversion_rate < 0.5 and stage.name != 'started':
                recommendations.append({
                    'priority': 'medium',
                    'stage': stage.name,
                    'issue': f'Only {round(stage.conversion_rate * 100, 1)}% progressing to this stage',
                    'recommendation': 'Review user feedback and session replays to identify friction points',
                    'expected_impact': '8-12% conversion improvement'
                })

        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 99))

        return recommendations[:5]  # Return top 5 recommendations

    except (AttributeError, TypeError) as e:
        logger.warning(f"Error generating recommendations: {str(e)}")
        return []

def get_realtime_funnel_snapshot(self):
    """Get current funnel state for real-time dashboard"""
    try:
        # Get sessions from last 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        recent_sessions = ConversationSession.objects.filter(
            cdtz__gte=cutoff_time
        )

        snapshot = {
            'timestamp': timezone.now().isoformat(),
            'time_window': '24_hours',
            'total_sessions': recent_sessions.count(),
            'active_sessions': recent_sessions.exclude(
                current_state__in=[
                    ConversationSession.StateChoices.COMPLETED,
                    ConversationSession.StateChoices.ERROR
                ]
            ).count(),
            'stages': []
        }

        # Calculate stage counts
        for stage_config in self.funnel_stages:
            stage_count = recent_sessions.filter(
                current_state__in=stage_config['session_states']
            ).count()

            snapshot['stages'].append({
                'name': stage_config['name'],
                'count': stage_count,
                'percentage': round((stage_count / snapshot['total_sessions'] * 100), 1) if snapshot['total_sessions'] > 0 else 0
            })

        return snapshot

    except (AttributeError, TypeError) as e:
        logger.error(f"Error getting realtime snapshot: {str(e)}")
        return {'error': str(e)}


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

# Example 1: Get funnel metrics for last 7 days
service = FunnelAnalyticsService()
metrics = service.calculate_funnel_metrics(
    start_date=timezone.now() - timedelta(days=7),
    end_date=timezone.now(),
    client_id=None  # All clients
)

print(f"Overall Conversion: {metrics.overall_conversion_rate}%")
print(f"Avg Completion Time: {metrics.avg_completion_time_minutes} minutes")
print(f"Top Drop-Off Points: {metrics.top_drop_off_points}")
print(f"Recommendations: {metrics.recommendations}")


# Example 2: Real-time dashboard snapshot
snapshot = service.get_realtime_funnel_snapshot()
print(f"Active Sessions: {snapshot['active_sessions']}")
print(f"Stages: {snapshot['stages']}")


# Example 3: Cohort analysis by language
metrics = service.calculate_funnel_metrics(
    start_date=timezone.now() - timedelta(days=30),
    end_date=timezone.now()
)
print(f"Language Cohorts: {metrics.cohort_analysis['by_language']}")
