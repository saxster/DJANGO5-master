"""
Views for Report Generation API

Provides REST API endpoints for intelligent report generation with
self-improving AI guidance.
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from apps.report_generation.models import (
    ReportTemplate,
    GeneratedReport,
    ReportExemplar,
    ReportIncidentTrend,
)
from apps.report_generation.serializers import (
    ReportTemplateSerializer,
    GeneratedReportSerializer,
    GeneratedReportDetailSerializer,
    GeneratedReportCreateSerializer,
    GeneratedReportUpdateSerializer,
    ReportExemplarSerializer,
    ReportIncidentTrendSerializer,
    AskQuestionSerializer,
    QuestionResponseSerializer,
    SubmitReportSerializer,
    ApproveReportSerializer,
    MarkExemplarSerializer,
)
from apps.report_generation.services import (
    SocraticQuestioningService,
    QualityGateService,
    ContextAutoPopulationService,
    ReportLearningService,
)

logger = logging.getLogger(__name__)


class ReportTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for report templates.
    
    Endpoints:
    - list: Get all templates
    - retrieve: Get template detail
    - create: Create custom template
    - update/patch: Update template
    - delete: Delete custom template (system templates protected)
    """
    
    serializer_class = ReportTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by tenant."""
        return ReportTemplate.objects.filter(
            tenant=self.request.user.tenant,
            is_active=True
        ).select_related('created_by', 'approved_by')
    
    def perform_create(self, serializer):
        """Create template with current user and tenant."""
        serializer.save(
            created_by=self.request.user,
            tenant=self.request.user.tenant
        )
    
    def perform_destroy(self, instance):
        """Prevent deletion of system templates."""
        if instance.is_system_template:
            raise ValueError("System templates cannot be deleted")
        super().perform_destroy(instance)


class GeneratedReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for generated reports with AI-powered assistance.
    
    Key endpoints:
    - start_report: Create new report with auto-population
    - ask_question: Get AI-generated question
    - validate: Check quality gates
    - submit: Submit for review
    - approve/reject: Supervisor actions
    - mark_exemplar: Mark as learning example
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter reports by tenant and user permissions."""
        user = self.request.user
        queryset = GeneratedReport.objects.filter(tenant=user.tenant)
        
        # Non-supervisors only see their own reports
        if not user.is_supervisor:
            queryset = queryset.filter(author=user)
        
        return queryset.select_related(
            'template', 'author', 'reviewed_by'
        ).prefetch_related(
            'ai_interactions_detailed'
        )
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create' or self.action == 'start_report':
            return GeneratedReportCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return GeneratedReportUpdateSerializer
        elif self.action == 'retrieve':
            return GeneratedReportDetailSerializer
        return GeneratedReportSerializer
    
    @action(detail=False, methods=['post'])
    def start_report(self, request):
        """
        Start a new report with auto-population from related entity.
        
        POST data:
        {
            "template_id": 1,
            "title": "Report title",
            "related_entity_type": "workorder",
            "related_entity_id": 123
        }
        """
        template_id = request.data.get('template_id')
        related_type = request.data.get('related_entity_type')
        related_id = request.data.get('related_entity_id')
        
        if not template_id:
            return Response(
                {'error': 'template_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            template = ReportTemplate.objects.get(
                id=template_id,
                tenant=request.user.tenant
            )
        except ReportTemplate.DoesNotExist:
            return Response(
                {'error': 'Template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Auto-populate data
        auto_data = {}
        if related_type and related_id:
            if related_type == 'workorder':
                auto_data = ContextAutoPopulationService.populate_from_work_order(related_id)
            elif related_type == 'incident':
                auto_data = ContextAutoPopulationService.populate_from_incident(related_id)
            elif related_type == 'asset':
                auto_data = ContextAutoPopulationService.populate_from_asset(related_id)
        
        # Create report
        report = GeneratedReport.objects.create(
            template=template,
            title=request.data.get('title', f"New {template.name}"),
            author=request.user,
            tenant=request.user.tenant,
            report_data=auto_data
        )
        
        serializer = GeneratedReportDetailSerializer(report)
        
        return Response({
            'report': serializer.data,
            'message': f'Auto-populated {len(auto_data)} fields',
            'next_action': 'Call ask_question to start AI guidance'
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def ask_question(self, request, pk=None):
        """
        Get next AI-generated question based on report state.
        
        POST data:
        {
            "context": {...},
            "framework": "5_whys" (optional)
        }
        """
        report = self.get_object()
        
        if report.status not in ['draft', 'pending_review']:
            return Response(
                {'error': 'Report is not editable'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AskQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        context = serializer.validated_data.get('context', {})
        framework = serializer.validated_data.get('framework', 'auto')
        
        if framework == 'auto':
            framework = None
        
        # Generate question
        question_text, question_type = SocraticQuestioningService.generate_next_question(
            report, context, framework
        )
        
        # Get current iteration count
        iteration = report.ai_interactions_detailed.count() + 1
        
        # Create interaction record
        from apps.report_generation.models import ReportAIInteraction
        interaction = ReportAIInteraction.objects.create(
            report=report,
            question=question_text,
            question_type=question_type,
            iteration=iteration
        )
        
        response_data = {
            'question': question_text,
            'question_type': question_type,
            'iteration': iteration,
            'context_help': cls._get_context_help(question_type)
        }
        
        return Response(response_data)
    
    @action(detail=True, methods=['post'])
    def answer_question(self, request, pk=None):
        """
        Submit answer to AI question.
        
        POST data:
        {
            "interaction_id": 123,
            "answer": "User's answer"
        }
        """
        report = self.get_object()
        interaction_id = request.data.get('interaction_id')
        answer = request.data.get('answer')
        
        if not interaction_id or not answer:
            return Response(
                {'error': 'interaction_id and answer are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.report_generation.models import ReportAIInteraction
            interaction = ReportAIInteraction.objects.get(
                id=interaction_id,
                report=report
            )
        except ReportAIInteraction.DoesNotExist:
            return Response(
                {'error': 'Interaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Save answer
        interaction.answer = answer
        interaction.save()
        
        # Update report data if needed
        report_data = report.report_data.copy()
        # Logic to update specific fields based on question type
        report.report_data = report_data
        report.save()
        
        # Recalculate quality
        metrics = QualityGateService.calculate_quality_metrics(report)
        
        return Response({
            'message': 'Answer recorded',
            'quality_metrics': metrics,
            'next_action': 'Call ask_question for next guidance'
        })
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Check if report meets quality gates for submission.
        """
        report = self.get_object()
        
        can_submit, issues = QualityGateService.can_submit(report)
        metrics = QualityGateService.calculate_quality_metrics(report)
        
        return Response({
            'can_submit': can_submit,
            'issues': issues,
            'quality_metrics': metrics,
            'quality_score': report.quality_score,
            'completeness_score': report.completeness_score,
            'clarity_score': report.clarity_score
        })
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Submit report for supervisor review.
        """
        report = self.get_object()
        
        if report.author != request.user:
            return Response(
                {'error': 'You can only submit your own reports'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status != 'draft':
            return Response(
                {'error': 'Report is not in draft status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check quality gates
        can_submit, issues = report.can_submit()
        
        if not can_submit:
            return Response({
                'error': 'Report does not meet quality standards',
                'issues': issues
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Submit
        from django.utils import timezone
        report.status = 'pending_review'
        report.submitted_at = timezone.now()
        report.save()
        
        return Response({
            'message': 'Report submitted for review',
            'status': report.status
        })
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve report (supervisor only).
        """
        report = self.get_object()
        
        if not request.user.is_supervisor:
            return Response(
                {'error': 'Only supervisors can approve reports'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ApproveReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        from django.utils import timezone
        report.status = 'approved'
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.supervisor_feedback = serializer.validated_data.get('feedback', '')
        report.save()
        
        # Mark as exemplar if requested
        if serializer.validated_data.get('mark_as_exemplar'):
            report.is_exemplar = True
            report.exemplar_category = serializer.validated_data.get('exemplar_category', '')
            report.save()
        
        # Learn from this approval
        if report.quality_score >= 80:
            logger.info(f"High-quality report approved: {report.id}")
        
        return Response({
            'message': 'Report approved',
            'is_exemplar': report.is_exemplar
        })
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject report with feedback (supervisor only).
        """
        report = self.get_object()
        
        if not request.user.is_supervisor:
            return Response(
                {'error': 'Only supervisors can reject reports'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        feedback = request.data.get('feedback')
        if not feedback:
            return Response(
                {'error': 'Feedback is required for rejection'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        report.status = 'rejected'
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.supervisor_feedback = feedback
        report.save()
        
        # Learn from rejection
        ReportLearningService.learn_from_supervisor_feedback(
            report, feedback, {}
        )
        
        return Response({
            'message': 'Report rejected with feedback',
            'feedback': feedback
        })
    
    @action(detail=True, methods=['post'])
    def mark_exemplar(self, request, pk=None):
        """
        Mark report as exemplar for learning (supervisor only).
        """
        report = self.get_object()
        
        if not request.user.is_supervisor:
            return Response(
                {'error': 'Only supervisors can mark exemplars'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status != 'approved':
            return Response(
                {'error': 'Only approved reports can be marked as exemplars'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = MarkExemplarSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Create exemplar
        exemplar, created = ReportExemplar.objects.update_or_create(
            report=report,
            defaults={
                'exemplar_category': serializer.validated_data['exemplar_category'],
                'why_exemplar': serializer.validated_data['why_exemplar'],
                'learning_points': serializer.validated_data['learning_points'],
                'demonstrates_frameworks': serializer.validated_data['demonstrates_frameworks'],
                'narrative_quality': serializer.validated_data['narrative_quality'],
                'root_cause_depth': serializer.validated_data['root_cause_depth'],
                'approved_by': request.user,
            }
        )
        
        report.is_exemplar = True
        report.exemplar_category = serializer.validated_data['exemplar_category']
        report.save()
        
        # Trigger learning from this exemplar
        patterns = ReportLearningService.analyze_exemplar_reports(
            report.template.category,
            report.tenant.id
        )
        
        return Response({
            'message': 'Report marked as exemplar',
            'exemplar_id': exemplar.id,
            'learning_triggered': True,
            'patterns_extracted': len(patterns)
        })
    
    @staticmethod
    def _get_context_help(question_type: str) -> str:
        """Get contextual help for question type."""
        help_text = {
            '5_whys': 'Answer with the immediate cause. We will dig deeper together.',
            'sbar': 'Be specific and factual. Include dates, times, locations, and names.',
            '5w1h': 'Provide complete details. Avoid vague terms like "soon", "many", or "issue".',
            'ishikawa': 'Consider all factors in this category. Were there any issues?',
            'star': 'Describe what actually happened in sequence.',
            'clarification': 'Replace vague language with specific details (numbers, names, times).',
            'validation': 'Ensure your recommendations are SMART: Specific, Measurable, Assigned, Relevant, Time-bound.'
        }
        return help_text.get(question_type, 'Provide clear, specific details.')


class ReportExemplarViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for exemplar reports (read-only for users, managed by supervisors).
    """
    
    serializer_class = ReportExemplarSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by tenant."""
        return ReportExemplar.objects.filter(
            report__tenant=self.request.user.tenant
        ).select_related('report', 'approved_by')
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get exemplars filtered by category."""
        category = request.query_params.get('category')
        
        if not category:
            return Response(
                {'error': 'category parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        exemplars = self.get_queryset().filter(
            exemplar_category=category
        )
        
        serializer = self.get_serializer(exemplars, many=True)
        return Response(serializer.data)


class ReportIncidentTrendViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for incident trends (system-generated insights).
    """
    
    serializer_class = ReportIncidentTrendSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by tenant."""
        return ReportIncidentTrend.objects.filter(
            tenant=self.request.user.tenant,
            is_active=True
        ).prefetch_related('related_reports')
    
    @action(detail=False, methods=['post'])
    def analyze(self, request):
        """
        Trigger trend analysis (supervisor only).
        """
        if not request.user.is_supervisor:
            return Response(
                {'error': 'Only supervisors can trigger trend analysis'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        days_back = int(request.data.get('days_back', 90))
        
        trends = ReportLearningService.identify_incident_trends(
            request.user.tenant.id,
            days_back
        )
        
        serializer = self.get_serializer(trends, many=True)
        
        return Response({
            'message': f'Analyzed reports from last {days_back} days',
            'trends_identified': len(trends),
            'trends': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def mark_addressed(self, request, pk=None):
        """
        Mark trend as addressed (supervisor only).
        """
        if not request.user.is_supervisor:
            return Response(
                {'error': 'Only supervisors can mark trends as addressed'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        trend = self.get_object()
        
        from django.utils import timezone
        trend.is_addressed = True
        trend.addressed_by = request.user
        trend.addressed_at = timezone.now()
        trend.save()
        
        return Response({
            'message': 'Trend marked as addressed',
            'trend_id': trend.id
        })


class ReportAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for report analytics and learning statistics.
    """
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def learning_stats(self, request):
        """Get system learning statistics."""
        stats = ReportLearningService.get_learning_statistics(
            request.user.tenant.id
        )
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def quality_trends(self, request):
        """Get quality trends over time."""
        from datetime import datetime, timedelta
        from django.db.models import Avg
        
        # Last 6 months, grouped by month
        trends = []
        for i in range(6):
            month_start = datetime.now() - timedelta(days=30 * (i + 1))
            month_end = datetime.now() - timedelta(days=30 * i)
            
            avg_quality = GeneratedReport.objects.filter(
                tenant=request.user.tenant,
                status='approved',
                created_at__gte=month_start,
                created_at__lt=month_end
            ).aggregate(Avg('quality_score'))['quality_score__avg'] or 0
            
            trends.append({
                'month': month_start.strftime('%B %Y'),
                'average_quality': round(avg_quality, 1)
            })
        
        return Response({
            'trends': list(reversed(trends))
        })
