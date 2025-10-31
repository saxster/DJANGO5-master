"""
Staff/Admin views for Conversational Onboarding Knowledge Management (Phase 2)
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, IntegrityError
from django.db.models import Avg
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.onboarding.models import (
    AuthoritativeKnowledge,
    AuthoritativeKnowledgeChunk,
    LLMRecommendation,
    ConversationSession,
    AIChangeSet,
    Bt
)
from apps.core.exceptions import LLMServiceException, IntegrationException
from .services.knowledge import get_knowledge_service
from .services.observability import get_cost_tracker, get_metrics_collector, get_alert_manager

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class KnowledgeManagementDashboard(APIView):
    """
    Knowledge base management dashboard for staff
    GET /api/v1/onboarding/admin/knowledge/dashboard/
    """

    def get(self, request):
        """Get knowledge base overview and statistics"""
        try:
            knowledge_service = get_knowledge_service()

            # Get comprehensive stats
            stats = knowledge_service.get_knowledge_stats()

            # Get recent activity
            recent_knowledge = AuthoritativeKnowledge.objects.filter(
                cdtz__gte=datetime.now() - timedelta(days=7)
            ).order_by('-cdtz')[:10]

            # Get chunk statistics
            chunk_stats = {
                'total_chunks': AuthoritativeKnowledgeChunk.objects.count(),
                'chunks_with_vectors': AuthoritativeKnowledgeChunk.objects.filter(
                    content_vector__isnull=False
                ).count(),
                'stale_chunks': AuthoritativeKnowledgeChunk.objects.filter(
                    last_verified__lt=datetime.now() - timedelta(days=90)
                ).count()
            }

            # Get authority level breakdown
            authority_breakdown = {}
            for level in ['low', 'medium', 'high', 'official']:
                count = AuthoritativeKnowledge.objects.filter(
                    authority_level=level,
                    is_current=True
                ).count()
                authority_breakdown[level] = count

            dashboard_data = {
                'overview': stats,
                'chunk_statistics': chunk_stats,
                'authority_breakdown': authority_breakdown,
                'recent_additions': [
                    {
                        'knowledge_id': str(k.knowledge_id),
                        'title': k.document_title,
                        'organization': k.source_organization,
                        'authority_level': k.authority_level,
                        'added_at': k.cdtz.isoformat()
                    }
                    for k in recent_knowledge
                ],
                'generated_at': datetime.now().isoformat()
            }

            return Response(dashboard_data)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error generating knowledge dashboard: {str(e)}")
            return Response(
                {"error": "Failed to load knowledge dashboard"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_embedding_progress(request):
    """
    Get embedding progress for all documents
    GET /api/v1/onboarding/admin/knowledge/embedding-progress/
    """
    try:
        # Get documents with their chunk counts
        documents = AuthoritativeKnowledge.objects.all().order_by('-cdtz')

        progress_data = []
        for doc in documents:
            chunks = AuthoritativeKnowledgeChunk.objects.filter(knowledge=doc)
            chunks_with_vectors = chunks.filter(content_vector__isnull=False)

            doc_progress = {
                'knowledge_id': str(doc.knowledge_id),
                'document_title': doc.document_title,
                'source_organization': doc.source_organization,
                'total_chunks': chunks.count(),
                'embedded_chunks': chunks_with_vectors.count(),
                'embedding_progress': (chunks_with_vectors.count() / max(1, chunks.count())) * 100,
                'last_verified': doc.last_verified.isoformat(),
                'is_current': doc.is_current,
                'authority_level': doc.authority_level
            }

            progress_data.append(doc_progress)

        return Response({
            'documents': progress_data,
            'total_documents': len(progress_data),
            'fully_embedded': len([d for d in progress_data if d['embedding_progress'] == 100]),
            'generated_at': datetime.now().isoformat()
        })

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
        logger.error(f"Error getting embedding progress: {str(e)}")
        return Response(
            {"error": "Failed to get embedding progress"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def batch_embed_documents(request):
    """
    Trigger batch embedding for selected documents
    POST /api/v1/onboarding/admin/knowledge/batch-embed/
    """
    if not getattr(settings, 'ENABLE_ONBOARDING_KB', False):
        return Response(
            {"error": "Knowledge base management is not enabled"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        knowledge_ids = request.data.get('knowledge_ids', [])
        if not knowledge_ids:
            return Response(
                {"error": "knowledge_ids list is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Import batch embedding task
        from background_tasks.onboarding_tasks_phase2 import batch_embed_documents_task

        # Start batch embedding
        result = batch_embed_documents_task.delay(knowledge_ids)

        return Response({
            "message": f"Batch embedding started for {len(knowledge_ids)} documents",
            "task_id": result.id,
            "document_count": len(knowledge_ids),
            "status_url": f"/api/v1/onboarding/tasks/{result.id}/status/"
        }, status=status.HTTP_202_ACCEPTED)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
        logger.error(f"Error starting batch embedding: {str(e)}")
        return Response(
            {"error": "Failed to start batch embedding"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@method_decorator(staff_member_required, name='dispatch')
class SystemMetricsView(APIView):
    """
    System metrics and monitoring dashboard for staff
    GET /api/v1/onboarding/admin/metrics/
    """

    def get(self, request):
        """Get comprehensive system metrics"""
        try:
            metrics_collector = get_metrics_collector()
            cost_tracker = get_cost_tracker()
            alert_manager = get_alert_manager()

            # Get metrics for different time windows
            metrics_24h = metrics_collector.get_metrics_summary(hours_back=24)
            metrics_7d = metrics_collector.get_metrics_summary(hours_back=168)  # 7 days

            # Get cost summaries
            daily_costs = cost_tracker.get_daily_cost_summary()

            # Get current alerts
            active_alerts = alert_manager.check_alerts()

            # Get system performance data
            performance_data = self._get_performance_metrics()

            dashboard_data = {
                'metrics': {
                    'last_24_hours': metrics_24h,
                    'last_7_days': metrics_7d
                },
                'costs': daily_costs,
                'alerts': {
                    'active_alerts': active_alerts,
                    'alert_count': len(active_alerts)
                },
                'performance': performance_data,
                'system_health': self._get_system_health(),
                'generated_at': datetime.now().isoformat()
            }

            return Response(dashboard_data)

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error generating metrics dashboard: {str(e)}")
            return Response(
                {"error": "Failed to load metrics dashboard"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the system"""
        try:
            cutoff = datetime.now() - timedelta(hours=24)

            # Query recent sessions and recommendations
            recent_sessions = ConversationSession.objects.filter(cdtz__gte=cutoff)
            recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

            performance = {
                'conversation_metrics': {
                    'total_sessions': recent_sessions.count(),
                    'completed_sessions': recent_sessions.filter(
                        current_state=ConversationSession.StateChoices.COMPLETED
                    ).count(),
                    'error_sessions': recent_sessions.filter(
                        current_state=ConversationSession.StateChoices.ERROR
                    ).count()
                },
                'recommendation_metrics': {
                    'total_recommendations': recent_recs.count(),
                    'approved_recommendations': recent_recs.filter(
                        user_decision=LLMRecommendation.UserDecisionChoices.APPROVED
                    ).count(),
                    'rejected_recommendations': recent_recs.filter(
                        user_decision=LLMRecommendation.UserDecisionChoices.REJECTED
                    ).count()
                }
            }

            # Calculate success rates
            if performance['conversation_metrics']['total_sessions'] > 0:
                performance['conversation_success_rate'] = (
                    performance['conversation_metrics']['completed_sessions'] /
                    performance['conversation_metrics']['total_sessions']
                ) * 100
            else:
                performance['conversation_success_rate'] = 0

            return performance

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            return {"error": str(e)}

    def _get_system_health(self) -> Dict[str, Any]:
        """Get overall system health indicators"""
        try:
            health = {
                'database_connectivity': 'healthy',
                'cache_connectivity': 'healthy',
                'knowledge_base_status': 'healthy',
                'task_queue_status': 'healthy'
            }

            # Test database
            try:
                ConversationSession.objects.count()
            except (ValueError, TypeError):
                health['database_connectivity'] = 'unhealthy'

            # Test cache
            try:
                from django.core.cache import cache
                cache.set('health_check', 'ok', 60)
                if cache.get('health_check') != 'ok':
                    health['cache_connectivity'] = 'unhealthy'
            except (ConnectionError, ValueError):
                health['cache_connectivity'] = 'unhealthy'

            # Test knowledge base
            try:
                chunk_count = AuthoritativeKnowledgeChunk.objects.filter(
                    content_vector__isnull=False
                ).count()
                if chunk_count == 0:
                    health['knowledge_base_status'] = 'warning'
            except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError):
                health['knowledge_base_status'] = 'unhealthy'

            # Overall health status
            unhealthy_services = [k for k, v in health.items() if v == 'unhealthy']
            if unhealthy_services:
                health['overall_status'] = 'unhealthy'
            elif any(v == 'warning' for v in health.values()):
                health['overall_status'] = 'warning'
            else:
                health['overall_status'] = 'healthy'

            return health

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error checking system health: {str(e)}")
            return {"overall_status": "error", "error": str(e)}


@api_view(['POST'])
@permission_classes([IsAdminUser])
def invalidate_stale_knowledge(request):
    """
    Mark stale knowledge as invalid and trigger review
    POST /api/v1/onboarding/admin/knowledge/invalidate-stale/
    """
    try:
        days_threshold = request.data.get('days_threshold', 365)  # 1 year default

        cutoff_date = datetime.now() - timedelta(days=days_threshold)

        # Find stale documents
        stale_docs = AuthoritativeKnowledge.objects.filter(
            publication_date__lt=cutoff_date,
            is_current=True
        )

        stale_count = stale_docs.count()

        # Mark as not current
        stale_docs.update(is_current=False)

        # Also mark chunks as not current
        for doc in stale_docs:
            AuthoritativeKnowledgeChunk.objects.filter(knowledge=doc).update(is_current=False)

        logger.info(f"Invalidated {stale_count} stale knowledge documents")

        return Response({
            "message": f"Invalidated {stale_count} stale documents",
            "documents_invalidated": stale_count,
            "threshold_days": days_threshold,
            "cutoff_date": cutoff_date.isoformat()
        })

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error invalidating stale knowledge: {str(e)}")
        return Response(
            {"error": "Failed to invalidate stale knowledge"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_conversation_analytics(request):
    """
    Export conversation analytics data for analysis
    GET /api/v1/onboarding/admin/analytics/export/
    """
    try:
        # Date range from query params
        days_back = int(request.GET.get('days', 30))
        cutoff = datetime.now() - timedelta(days=days_back)

        # Export conversation data
        sessions = ConversationSession.objects.filter(cdtz__gte=cutoff)
        recommendations = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

        export_data = {
            'export_metadata': {
                'generated_at': datetime.now().isoformat(),
                'date_range_days': days_back,
                'cutoff_date': cutoff.isoformat(),
                'total_sessions': sessions.count(),
                'total_recommendations': recommendations.count()
            },
            'conversation_analytics': {
                'sessions_by_type': {},
                'sessions_by_state': {},
                'sessions_by_language': {},
                'average_session_duration': 0
            },
            'recommendation_analytics': {
                'recommendations_by_status': {},
                'recommendations_by_decision': {},
                'average_confidence': 0,
                'average_latency_ms': 0,
                'total_cost_cents': 0
            },
            'user_analytics': {
                'unique_users': sessions.values('user').distinct().count(),
                'most_active_users': []
            }
        }

        # Analyze sessions
        for session in sessions:
            conv_type = session.conversation_type
            state = session.current_state
            language = session.language

            export_data['conversation_analytics']['sessions_by_type'][conv_type] = \
                export_data['conversation_analytics']['sessions_by_type'].get(conv_type, 0) + 1

            export_data['conversation_analytics']['sessions_by_state'][state] = \
                export_data['conversation_analytics']['sessions_by_state'].get(state, 0) + 1

            export_data['conversation_analytics']['sessions_by_language'][language] = \
                export_data['conversation_analytics']['sessions_by_language'].get(language, 0) + 1

        # Analyze recommendations
        for rec in recommendations:
            status_val = rec.status
            decision = rec.user_decision

            export_data['recommendation_analytics']['recommendations_by_status'][status_val] = \
                export_data['recommendation_analytics']['recommendations_by_status'].get(status_val, 0) + 1

            export_data['recommendation_analytics']['recommendations_by_decision'][decision] = \
                export_data['recommendation_analytics']['recommendations_by_decision'].get(decision, 0) + 1

        # Calculate averages
        if recommendations.exists():
            from django.db.models import Avg, Sum
            aggregates = recommendations.aggregate(
                avg_confidence=Avg('confidence_score'),
                avg_latency=Avg('latency_ms'),
                total_cost=Sum('provider_cost_cents')
            )

            export_data['recommendation_analytics']['average_confidence'] = round(
                aggregates['avg_confidence'] or 0, 3
            )
            export_data['recommendation_analytics']['average_latency_ms'] = int(
                aggregates['avg_latency'] or 0
            )
            export_data['recommendation_analytics']['total_cost_cents'] = \
                aggregates['total_cost'] or 0

        return Response(export_data)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error exporting analytics: {str(e)}")
        return Response(
            {"error": "Failed to export analytics"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_system_alerts(request):
    """
    Get current system alerts and monitoring status
    GET /api/v1/onboarding/admin/alerts/
    """
    try:
        alert_manager = get_alert_manager()

        # Get current alerts
        alerts = alert_manager.check_alerts()

        # Categorize alerts by severity
        alert_summary = {
            'critical': [a for a in alerts if a.get('severity') == 'critical'],
            'warning': [a for a in alerts if a.get('severity') == 'warning'],
            'info': [a for a in alerts if a.get('severity') == 'info'],
            'total_alerts': len(alerts)
        }

        # Get alert history from cache (last 24 hours)
        alert_history = cache.get('alert_history_24h', [])

        return Response({
            'current_alerts': alert_summary,
            'alert_history': alert_history,
            'monitoring_status': 'active',
            'last_check': datetime.now().isoformat()
        })

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error getting system alerts: {str(e)}")
        return Response(
            {"error": "Failed to get system alerts"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_freshness_check(request):
    """
    Manually trigger knowledge freshness validation
    POST /api/v1/onboarding/admin/knowledge/freshness-check/
    """
    try:
        from background_tasks.onboarding_tasks_phase2 import validate_knowledge_freshness_task

        # Trigger freshness validation task
        result = validate_knowledge_freshness_task.delay()

        return Response({
            "message": "Knowledge freshness check triggered",
            "task_id": result.id,
            "status_url": f"/api/v1/onboarding/tasks/{result.id}/status/"
        }, status=status.HTTP_202_ACCEPTED)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error triggering freshness check: {str(e)}")
        return Response(
            {"error": "Failed to trigger freshness check"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_cost_analytics(request):
    """
    Get detailed cost analytics and trends
    GET /api/v1/onboarding/admin/costs/
    """
    try:
        cost_tracker = get_cost_tracker()

        # Get date range from query params
        days_back = int(request.GET.get('days', 30))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Get cost breakdown
        cost_breakdown = cost_tracker.get_cost_breakdown(start_date, end_date)

        # Get current daily summary
        daily_summary = cost_tracker.get_daily_cost_summary()

        analytics_data = {
            'cost_breakdown': cost_breakdown,
            'daily_summary': daily_summary,
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days_back
            },
            'cost_trends': {
                'daily_average': cost_breakdown['total_cost_cents'] / max(1, days_back),
                'cost_per_recommendation': (
                    cost_breakdown['total_cost_cents'] / max(1, cost_breakdown['total_recommendations'])
                ),
            },
            'generated_at': datetime.now().isoformat()
        }

        return Response(analytics_data)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error getting cost analytics: {str(e)}")
        return Response(
            {"error": "Failed to get cost analytics"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# ROLLOUT DASHBOARD WITH LIVE DATA INTEGRATION
# =============================================================================


class OnboardingRolloutDashboardView(View):
    """
    Enhanced rollout dashboard with live data and comprehensive metrics
    """

    @method_decorator(staff_member_required)
    def get(self, request):
        """Render rollout dashboard with live data"""
        try:
            # Get comprehensive dashboard data
            dashboard_data = self.get_live_dashboard_data()

            context = {
                'title': 'Conversational Onboarding Rollout Dashboard',
                'dashboard_data': dashboard_data,
                'last_updated': timezone.now().isoformat(),
                'auto_refresh_enabled': True,
                'refresh_interval_seconds': 30,
                'user': request.user
            }

            return render(request, 'admin/onboarding_rollout_dashboard.html', context)

        except (ValueError, TypeError) as e:
            logger.error(f"Error loading rollout dashboard: {str(e)}")
            context = {
                'title': 'Conversational Onboarding Rollout Dashboard',
                'error': str(e),
                'dashboard_data': None,
                'user': request.user
            }
            return render(request, 'admin/onboarding_rollout_dashboard.html', context)

    def get_live_dashboard_data(self) -> Dict[str, Any]:
        """Get live dashboard data with real metrics"""
        # Import services
        from .services.funnel_analytics import get_funnel_metrics_for_dashboard
        from .services.config_templates import get_template_service
        from .services.background_embedding_jobs import get_embedding_processing_status

        # Calculate time periods
        now = timezone.now()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)

        # Get funnel metrics
        funnel_metrics = get_funnel_metrics_for_dashboard()

        # Get template analytics
        template_service = get_template_service()
        template_analytics = template_service.get_template_analytics()

        # Get embedding processing status
        embedding_status = get_embedding_processing_status()

        # Get rollout progress
        rollout_progress = self.calculate_live_rollout_progress()

        # Get system performance
        performance_metrics = self.get_live_performance_metrics()

        # Get feature adoption
        feature_adoption = self.get_live_feature_adoption()

        # Get cost overview
        cost_overview = self.get_live_cost_overview()

        return {
            'rollout_overview': {
                'progress': rollout_progress,
                'current_stage': rollout_progress['rollout_stage'],
                'next_milestone': rollout_progress['next_milestone']
            },
            'funnel_analytics': funnel_metrics,
            'template_usage': {
                'analytics': template_analytics,
                'most_popular': template_analytics.get('most_popular_templates', [])[:5]
            },
            'system_performance': performance_metrics,
            'feature_adoption': feature_adoption,
            'embedding_processing': embedding_status,
            'cost_overview': cost_overview,
            'alerts_summary': self.get_alerts_summary(),
            'quick_actions': self.get_quick_actions(),
            'last_updated': timezone.now().isoformat()
        }

    def calculate_live_rollout_progress(self) -> Dict[str, Any]:
        """Calculate live rollout progress with real data"""
        # Total active clients
        total_clients = Bt.objects.filter(enable=True).count()

        # Clients with onboarding activity
        clients_with_sessions = ConversationSession.objects.values('client').distinct().count()

        # Clients with completed onboarding
        clients_completed = ConversationSession.objects.filter(
            current_state=ConversationSession.StateChoices.COMPLETED
        ).values('client').distinct().count()

        # Clients using templates
        clients_using_templates = ConversationSession.objects.filter(
            context_data__has_key='template_deployment'
        ).values('client').distinct().count()

        # Calculate percentages
        adoption_rate = (clients_with_sessions / max(1, total_clients)) * 100
        completion_rate = (clients_completed / max(1, clients_with_sessions)) * 100
        template_usage_rate = (clients_using_templates / max(1, clients_with_sessions)) * 100

        # Determine rollout stage
        if adoption_rate < 5:
            stage = 'pilot'
        elif adoption_rate < 25:
            stage = 'early_rollout'
        elif adoption_rate < 75:
            stage = 'active_rollout'
        elif adoption_rate < 95:
            stage = 'late_rollout'
        else:
            stage = 'complete'

        return {
            'total_clients': total_clients,
            'clients_with_sessions': clients_with_sessions,
            'clients_completed': clients_completed,
            'clients_using_templates': clients_using_templates,
            'adoption_rate': adoption_rate,
            'completion_rate': completion_rate,
            'template_usage_rate': template_usage_rate,
            'rollout_stage': stage,
            'next_milestone': self.get_next_rollout_milestone(adoption_rate)
        }

    def get_next_rollout_milestone(self, current_rate: float) -> Dict[str, Any]:
        """Get next rollout milestone"""
        milestones = [
            (10, 'Complete pilot phase with key clients'),
            (25, 'Achieve early adoption across client base'),
            (50, 'Reach majority adoption milestone'),
            (75, 'Approach full deployment readiness'),
            (95, 'Complete rollout to all active clients'),
            (100, 'Full deployment achieved')
        ]

        for percentage, description in milestones:
            if current_rate < percentage:
                return {
                    'target_percentage': percentage,
                    'description': description,
                    'clients_to_target': int((percentage - current_rate) / 100 * total_clients) if 'total_clients' in locals() else 0
                }

        return {
            'target_percentage': 100,
            'description': 'Rollout complete - focus on optimization',
            'clients_to_target': 0
        }

    def get_live_performance_metrics(self) -> Dict[str, Any]:
        """Get live system performance metrics"""
        # Last 24 hours
        last_24h = timezone.now() - timedelta(hours=24)

        sessions_24h = ConversationSession.objects.filter(cdtz__gte=last_24h)
        recommendations_24h = LLMRecommendation.objects.filter(cdtz__gte=last_24h)

        # Calculate performance metrics
        total_sessions = sessions_24h.count()
        completed_sessions = sessions_24h.filter(
            current_state=ConversationSession.StateChoices.COMPLETED
        ).count()
        error_sessions = sessions_24h.filter(
            current_state=ConversationSession.StateChoices.ERROR
        ).count()

        # Success rates
        completion_rate = (completed_sessions / max(1, total_sessions)) * 100
        error_rate = (error_sessions / max(1, total_sessions)) * 100

        # Average response times
        avg_recommendation_latency = recommendations_24h.aggregate(
            avg_latency=Avg('latency_ms')
        )['avg_latency'] or 0

        return {
            'last_24_hours': {
                'total_sessions': total_sessions,
                'completion_rate': completion_rate,
                'error_rate': error_rate,
                'avg_recommendation_latency_ms': int(avg_recommendation_latency)
            },
            'current_system_load': {
                'active_sessions': sessions_24h.filter(
                    current_state__in=[
                        ConversationSession.StateChoices.STARTED,
                        ConversationSession.StateChoices.IN_PROGRESS,
                        ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
                    ]
                ).count(),
                'pending_approvals': sessions_24h.filter(
                    current_state=ConversationSession.StateChoices.AWAITING_USER_APPROVAL
                ).count()
            },
            'quality_metrics': {
                'avg_confidence_score': recommendations_24h.aggregate(
                    avg_confidence=Avg('confidence_score')
                )['avg_confidence'] or 0,
                'high_confidence_rate': (
                    recommendations_24h.filter(confidence_score__gte=0.8).count() /
                    max(1, recommendations_24h.count())
                ) * 100
            }
        }

    def get_live_feature_adoption(self) -> Dict[str, Any]:
        """Get live feature adoption metrics"""
        last_30_days = timezone.now() - timedelta(days=30)

        # Feature usage tracking
        total_sessions = ConversationSession.objects.filter(cdtz__gte=last_30_days).count()

        template_usage = ConversationSession.objects.filter(
            cdtz__gte=last_30_days,
            context_data__has_key='template_deployment'
        ).count()

        ai_approvals = AIChangeSet.objects.filter(
            cdtz__gte=last_30_days,
            status=AIChangeSet.StatusChoices.APPLIED
        ).count()

        # Knowledge base usage
        knowledge_validations = LLMRecommendation.objects.filter(
            cdtz__gte=last_30_days,
            authoritative_sources__isnull=False
        ).count()

        return {
            'template_adoption': {
                'usage_count': template_usage,
                'adoption_rate': (template_usage / max(1, total_sessions)) * 100
            },
            'ai_approval_usage': {
                'approval_count': ai_approvals,
                'usage_rate': (ai_approvals / max(1, total_sessions)) * 100
            },
            'knowledge_base_usage': {
                'validation_count': knowledge_validations,
                'usage_rate': (knowledge_validations / max(1, total_sessions)) * 100
            },
            'feature_flags_status': {
                'conversational_onboarding': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False),
                'production_embeddings': getattr(settings, 'ENABLE_PRODUCTION_EMBEDDINGS', False),
                'webhook_notifications': getattr(settings, 'ENABLE_WEBHOOK_NOTIFICATIONS', False),
                'production_llm': getattr(settings, 'ENABLE_PRODUCTION_LLM', False)
            }
        }

    def get_live_cost_overview(self) -> Dict[str, Any]:
        """Get live cost overview"""
        # This would integrate with actual cost tracking services
        # For now, return structure for future implementation
        return {
            'daily_costs': {
                'llm_costs_cents': 0,
                'embedding_costs_cents': 0,
                'total_costs_cents': 0
            },
            'monthly_projection': {
                'projected_costs_cents': 0,
                'budget_utilization_percentage': 0.0
            },
            'cost_per_session': 0.0,
            'cost_optimization_opportunities': [
                'Enable caching to reduce duplicate LLM calls',
                'Use local embedding models for non-critical content',
                'Implement smart batching for bulk operations'
            ]
        }

    def get_alerts_summary(self) -> Dict[str, Any]:
        """Get summary of active alerts"""
        # This would integrate with actual alerting system
        return {
            'critical_alerts': 0,
            'warning_alerts': 0,
            'info_alerts': 0,
            'last_alert': None,
            'alerts_trend': 'stable'
        }

    def get_quick_actions(self) -> List[Dict[str, Any]]:
        """Get quick actions for admins"""
        return [
            {
                'id': 'refresh_embeddings',
                'title': 'Refresh Knowledge Embeddings',
                'description': 'Trigger background embedding generation for new knowledge',
                'action_url': '/api/v1/onboarding/admin/trigger-jobs/',
                'method': 'POST',
                'data': {'job_type': 'embedding_queue'},
                'estimated_time': '5-10 minutes'
            },
            {
                'id': 'export_analytics',
                'title': 'Export Analytics Report',
                'description': 'Generate comprehensive analytics export',
                'action_url': '/api/v1/onboarding/admin/analytics/export/',
                'method': 'GET',
                'estimated_time': '1-2 minutes'
            },
            {
                'id': 'check_system_health',
                'title': 'Run System Health Check',
                'description': 'Validate all system components and dependencies',
                'action_url': '/api/v1/onboarding/health/system/',
                'method': 'GET',
                'estimated_time': '30 seconds'
            },
            {
                'id': 'optimize_queue',
                'title': 'Optimize Processing Queue',
                'description': 'Re-prioritize background jobs based on authority and age',
                'action_url': '/api/v1/onboarding/admin/trigger-jobs/',
                'method': 'POST',
                'data': {'job_type': 'queue_prioritization'},
                'estimated_time': '1 minute'
            }
        ]


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_rollout_dashboard_data(request):
    """
    API endpoint for rollout dashboard data (for AJAX updates)
    GET /api/v1/onboarding/admin/rollout-dashboard-data/
    """
    try:
        dashboard_view = OnboardingRolloutDashboardView()
        data = dashboard_view.get_live_dashboard_data()

        return Response(data)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error getting rollout dashboard data: {str(e)}")
        return Response(
            {'error': 'Failed to load dashboard data'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def control_rollout_phase(request):
    """
    Control rollout phase and deployment strategy
    POST /api/v1/onboarding/admin/control-rollout/
    """
    try:
        action = request.data.get('action')
        target_clients = request.data.get('target_clients', [])
        rollout_config = request.data.get('config', {})

        valid_actions = ['enable_pilot', 'expand_rollout', 'pause_rollout', 'complete_rollout']

        if action not in valid_actions:
            return Response(
                {'error': f'Invalid action. Valid options: {valid_actions}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Execute rollout control action
        result = self.execute_rollout_action(action, target_clients, rollout_config, request.user)

        logger.info(f"Rollout action {action} executed by {request.user.email}")

        return Response({
            'action': action,
            'executed_by': request.user.email,
            'executed_at': timezone.now().isoformat(),
            'result': result,
            'target_clients': target_clients
        })

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error controlling rollout: {str(e)}")
        return Response(
            {'error': 'Failed to control rollout'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    def execute_rollout_action(self, action: str, target_clients: List[int],
                             config: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute rollout control action"""
        if action == 'enable_pilot':
            return self.enable_pilot_for_clients(target_clients, config)
        elif action == 'expand_rollout':
            return self.expand_rollout_to_clients(target_clients, config)
        elif action == 'pause_rollout':
            return self.pause_rollout_for_clients(target_clients)
        elif action == 'complete_rollout':
            return self.complete_rollout_for_clients(target_clients)
        else:
            return {'error': f'Unknown action: {action}'}

    def enable_pilot_for_clients(self, client_ids: List[int], config: Dict[str, Any]) -> Dict[str, Any]:
        """Enable pilot program for specific clients"""
        # This would set client-specific feature flags
        return {
            'action': 'pilot_enabled',
            'clients_affected': len(client_ids),
            'pilot_config': config,
            'note': 'Pilot configuration would be applied to specified clients'
        }

    def expand_rollout_to_clients(self, client_ids: List[int], config: Dict[str, Any]) -> Dict[str, Any]:
        """Expand rollout to additional clients"""
        return {
            'action': 'rollout_expanded',
            'clients_affected': len(client_ids),
            'expansion_config': config,
            'note': 'Rollout expansion would be applied to specified clients'
        }

    def pause_rollout_for_clients(self, client_ids: List[int]) -> Dict[str, Any]:
        """Pause rollout for specific clients"""
        return {
            'action': 'rollout_paused',
            'clients_affected': len(client_ids),
            'note': 'Rollout pause would be applied to specified clients'
        }

    def complete_rollout_for_clients(self, client_ids: List[int]) -> Dict[str, Any]:
        """Complete rollout for specific clients"""
        return {
            'action': 'rollout_completed',
            'clients_affected': len(client_ids),
            'note': 'Rollout completion would be applied to specified clients'
        }