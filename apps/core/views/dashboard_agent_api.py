"""
Dashboard Agent Intelligence API Views

REST API endpoints for agent recommendations and insights.

Following CLAUDE.md:
- Rule #7: Methods <30 lines each
- Rule #11: Specific exception handling
- LoginRequiredMixin for security
- Multi-tenant isolation

Dashboard Agent Intelligence - Phase 4
"""

import logging
from collections import defaultdict
from typing import Dict, Any, Tuple, List
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from apps.core.services.agents.agent_orchestrator import AgentOrchestrator
from apps.core.models.agent_recommendation import AgentRecommendation

logger = logging.getLogger(__name__)


class DashboardAgentInsightsView(LoginRequiredMixin, View):
    """
    API endpoint for agent recommendations.

    GET /api/dashboard/agent-insights/
    - Returns recommendations grouped by module
    - Includes agent status and summary

    POST /api/dashboard/agent-insights/
    - Executes recommended action
    """

    def get(self, request, *args, **kwargs):
        """
        Get agent recommendations for dashboard.

        Query params:
            from: Start date (YYYY-MM-DD)
            upto: End date (YYYY-MM-DD)

        Returns:
            JSON with grouped recommendations and summary
        """
        try:
            # Get tenant context
            site_id = request.session.get('bu_id')
            client_id = request.session.get('client_id')

            if not site_id or not client_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Missing tenant context'
                }, status=400)

            # Parse time range
            time_range = self._parse_time_range(request)

            # Run agent orchestration
            orchestrator = AgentOrchestrator(client_id)
            recommendations = orchestrator.process_dashboard_data(site_id, time_range)

            # Group by module
            grouped = defaultdict(list)
            for rec in recommendations:
                grouped[rec.module].append(rec.to_dict())

            # Generate summary
            summary = self._generate_summary(recommendations)

            return JsonResponse({
                'status': 'success',
                'agent_insights': dict(grouped),
                'summary': summary,
                'count': len(recommendations)
            })

        except (ValueError, KeyError) as e:
            logger.error(f"Agent insights API error: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request parameters'
            }, status=400)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Database error in agent insights: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Internal server error'
            }, status=500)

    def post(self, request, *args, **kwargs):
        """
        Execute agent recommendation action.

        POST params:
            recommendation_id: Recommendation ID
            action: Action type to execute

        Returns:
            Execution result
        """
        try:
            recommendation_id = request.POST.get('recommendation_id')
            action_type = request.POST.get('action')

            if not recommendation_id or not action_type:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Missing required parameters'
                }, status=400)

            client_id = request.session.get('client_id')
            orchestrator = AgentOrchestrator(client_id)

            result = orchestrator.execute_action(int(recommendation_id), action_type)

            return JsonResponse({
                'status': 'success',
                'result': result
            })

        except ValueError as e:
            logger.error(f"Action execution error: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Database error executing action: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Internal server error'
            }, status=500)

    def _parse_time_range(self, request) -> Tuple[datetime, datetime]:
        """Parse time range from request params"""
        from_date = request.GET.get('from')
        to_date = request.GET.get('upto')

        if from_date and to_date:
            start = datetime.fromisoformat(from_date)
            end = datetime.fromisoformat(to_date)
        else:
            # Default: last 7 days
            end = timezone.now()
            start = end - timedelta(days=7)

        return (start, end)

    def _generate_summary(self, recommendations: List[AgentRecommendation]) -> Dict[str, Any]:
        """Generate summary statistics"""
        if not recommendations:
            return {
                'total_recommendations': 0,
                'by_severity': {},
                'by_module': {},
                'llm_provider': None
            }

        # Count by severity
        by_severity = defaultdict(int)
        by_module = defaultdict(int)
        providers = defaultdict(int)

        for rec in recommendations:
            by_severity[rec.severity] += 1
            by_module[rec.module] += 1
            providers[rec.llm_provider] += 1

        # Find primary provider
        primary_provider = max(providers.items(), key=lambda x: x[1])[0] if providers else 'none'

        return {
            'total_recommendations': len(recommendations),
            'by_severity': dict(by_severity),
            'by_module': dict(by_module),
            'llm_provider': primary_provider,
            'providers_used': dict(providers)
        }


class AgentStatusView(LoginRequiredMixin, View):
    """
    API endpoint for agent status.

    GET /api/dashboard/agent-status/
    - Returns real-time agent activity status
    """

    def get(self, request, *args, **kwargs):
        """Get agent status and activity feed"""
        try:
            client_id = request.session.get('client_id')

            # Get recent recommendations (last hour)
            recent_recs = AgentRecommendation.objects.filter(
                client_id=client_id,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).order_by('-created_at')[:20]

            # Build agent status table
            agent_status = self._build_agent_status(recent_recs)

            # Build activity feed
            activity_feed = self._build_activity_feed(recent_recs)

            return JsonResponse({
                'status': 'success',
                'agent_status': agent_status,
                'activity_feed': activity_feed
            })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Agent status API error: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Internal server error'
            }, status=500)

    def _build_agent_status(self, recent_recs) -> List[Dict[str, Any]]:
        """Build agent status table"""
        agent_map = defaultdict(lambda: {'count': 0, 'last_action': None, 'avg_confidence': 0.0})

        for rec in recent_recs:
            agent_map[rec.agent_name]['count'] += 1
            agent_map[rec.agent_name]['last_action'] = rec.summary
            agent_map[rec.agent_name]['avg_confidence'] += rec.confidence

        # Calculate averages
        status = []
        for agent_name, data in agent_map.items():
            status.append({
                'agent': agent_name,
                'last_action': data['last_action'][:50] if data['last_action'] else 'No recent activity',
                'status': 'active' if data['count'] > 0 else 'idle',
                'confidence': f"{(data['avg_confidence'] / data['count']) * 100:.0f}%" if data['count'] > 0 else 'N/A'
            })

        return status

    def _build_activity_feed(self, recent_recs) -> List[Dict[str, str]]:
        """Build agent activity timeline"""
        return [
            {
                'timestamp': rec.created_at.strftime('%I:%M %p'),
                'agent': rec.agent_name,
                'action': rec.summary,
                'severity': rec.severity
            }
            for rec in recent_recs[:10]
        ]
