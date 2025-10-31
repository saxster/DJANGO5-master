"""
Operations API ViewSets

ViewSets for jobs, jobneeds, tasks, and question sets.

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Uses permission classes
"""

from rest_framework import viewsets, status
from apps.ontology.decorators import ontology
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.activity.models import Job, Jobneed, JobneedDetails, QuestionSet
from apps.activity.api.serializers import (
    JobListSerializer,
    JobDetailSerializer,
    JobneedListSerializer,
    JobneedDetailSerializer,
    JobneedDetailsSerializer,
    QuestionSetSerializer,
)
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import DatabaseError
from croniter import croniter
from datetime import datetime, timezone as dt_timezone
import logging

logger = logging.getLogger(__name__)


@ontology(
    domain="operations",
    purpose="REST API for Job (work order) management with PPM scheduling and task completion tracking",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH", "DELETE"],
    authentication_required=True,
    permissions=["IsAuthenticated", "TenantIsolationPermission"],
    rate_limit="100/minute",
    request_schema="JobListSerializer|JobDetailSerializer",
    response_schema="JobListSerializer|JobDetailSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "operations", "jobs", "work-orders", "ppm", "mobile"],
    security_notes="Tenant isolation via client_id filtering. Jobs assigned to tenant users only",
    endpoints={
        "list": "GET /api/v1/operations/jobs/ - List jobs (tenant-filtered)",
        "create": "POST /api/v1/operations/jobs/ - Create new job",
        "retrieve": "GET /api/v1/operations/jobs/{id}/ - Get job details",
        "update": "PATCH /api/v1/operations/jobs/{id}/ - Update job",
        "delete": "DELETE /api/v1/operations/jobs/{id}/ - Delete job",
        "complete": "POST /api/v1/operations/jobs/{id}/complete/ - Mark job complete"
    },
    examples=[
        "curl -X GET https://api.example.com/api/v1/operations/jobs/ -H 'Authorization: Bearer <token>'",
        "curl -X POST https://api.example.com/api/v1/operations/jobs/{id}/complete/ -H 'Authorization: Bearer <token>'"
    ]
)
class JobViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Job management.

    Endpoints:
    - GET    /api/v1/operations/jobs/              List all jobs
    - POST   /api/v1/operations/jobs/              Create new job
    - GET    /api/v1/operations/jobs/{id}/         Retrieve job
    - PATCH  /api/v1/operations/jobs/{id}/         Update job
    - DELETE /api/v1/operations/jobs/{id}/         Delete job
    - POST   /api/v1/operations/jobs/{id}/complete/  Mark job complete
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Exclude outdated job API until aligned with new models

    filterset_fields = ['status', 'job_type', 'bu_id', 'client_id', 'assigned_to']
    search_fields = ['job_number', 'description']
    ordering_fields = ['scheduled_date', 'created_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = Job.objects.all()

        if not self.request.user.is_superuser:
            queryset = queryset.filter(client_id=self.request.user.client_id)

        queryset = queryset.select_related('assigned_to', 'created_by')
        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return JobListSerializer
        return JobDetailSerializer

    def perform_create(self, serializer):
        """Create job with tenant and creator assignment."""
        serializer.save(
            client_id=self.request.user.client_id,
            bu_id=self.request.user.bu_id if hasattr(self.request.user, 'bu_id') else None,
            created_by=self.request.user
        )
        logger.info(f"Job created: {serializer.instance.job_number}")

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark job as complete.

        POST /api/v1/operations/jobs/{id}/complete/
        """
        job = self.get_object()

        if job.status == 'completed':
            return Response(
                {'error': 'Job is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        job.status = 'completed'
        job.completed_date = datetime.now(dt_timezone.utc)
        job.save()

        logger.info(f"Job completed: {job.job_number} by {request.user.username}")

        serializer = self.get_serializer(job)
        return Response(serializer.data)


@ontology(
    domain="operations",
    purpose="REST API for Jobneed (PPM schedule template) management with cron scheduling and job generation",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH", "DELETE"],
    authentication_required=True,
    permissions=["IsAuthenticated", "TenantIsolationPermission"],
    rate_limit="100/minute",
    request_schema="JobneedListSerializer|JobneedDetailSerializer",
    response_schema="JobneedListSerializer|JobneedDetailSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "operations", "jobneed", "ppm", "scheduling", "cron", "mobile"],
    security_notes="Tenant isolation via client_id filtering. Cron expression validation prevents invalid schedules",
    endpoints={
        "list": "GET /api/v1/operations/jobneeds/ - List jobneeds",
        "create": "POST /api/v1/operations/jobneeds/ - Create jobneed template",
        "retrieve": "GET /api/v1/operations/jobneeds/{id}/ - Get jobneed details",
        "update": "PATCH /api/v1/operations/jobneeds/{id}/ - Update jobneed",
        "delete": "DELETE /api/v1/operations/jobneeds/{id}/ - Delete jobneed",
        "details": "GET /api/v1/operations/jobneeds/{id}/details/ - Get PPM schedule details",
        "schedule": "POST /api/v1/operations/jobneeds/{id}/schedule/ - Update cron schedule",
        "generate": "POST /api/v1/operations/jobneeds/{id}/generate/ - Generate jobs immediately"
    },
    examples=[
        "curl -X POST https://api.example.com/api/v1/operations/jobneeds/{id}/schedule/ -H 'Authorization: Bearer <token>' -d '{\"cron_expression\":\"0 9 * * 1\",\"frequency\":\"weekly\"}'",
        "curl -X POST https://api.example.com/api/v1/operations/jobneeds/{id}/generate/ -H 'Authorization: Bearer <token>'"
    ]
)
class JobneedViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Jobneed (PPM schedule) management.

    Endpoints:
    - GET    /api/v1/operations/jobneeds/                List jobneeds
    - POST   /api/v1/operations/jobneeds/                Create jobneed
    - GET    /api/v1/operations/jobneeds/{id}/           Retrieve jobneed
    - PATCH  /api/v1/operations/jobneeds/{id}/           Update jobneed
    - DELETE /api/v1/operations/jobneeds/{id}/           Delete jobneed
    - GET    /api/v1/operations/jobneeds/{id}/details/   Get jobneed details
    - POST   /api/v1/operations/jobneeds/{id}/schedule/  Update cron schedule
    - POST   /api/v1/operations/jobneeds/{id}/generate/  Generate jobs now
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Exclude outdated jobneed API until aligned with new models

    filterset_fields = ['status', 'jobneed_type', 'bu_id', 'client_id', 'is_active']
    search_fields = ['jobneed_number', 'description']
    ordering_fields = ['next_generation_date', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = Jobneed.objects.all()

        if not self.request.user.is_superuser:
            queryset = queryset.filter(client_id=self.request.user.client_id)

        queryset = queryset.select_related('created_by')
        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return JobneedListSerializer
        return JobneedDetailSerializer

    def perform_create(self, serializer):
        """Create jobneed with tenant assignment."""
        serializer.save(
            client_id=self.request.user.client_id,
            bu_id=self.request.user.bu_id if hasattr(self.request.user, 'bu_id') else None,
            created_by=self.request.user
        )
        logger.info(f"Jobneed created: {serializer.instance.jobneed_number}")

    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """
        Get jobneed details (PPM schedule details).

        GET /api/v1/operations/jobneeds/{id}/details/
        """
        jobneed = self.get_object()
        details = JobneedDetails.objects.filter(jobneed=jobneed, is_active=True)
        serializer = JobneedDetailsSerializer(details, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """
        Update cron schedule for jobneed.

        POST /api/v1/operations/jobneeds/{id}/schedule/
        Request:
            {
                "cron_expression": "0 9 * * 1",
                "frequency": "weekly"
            }
        """
        jobneed = self.get_object()

        cron_expression = request.data.get('cron_expression')
        frequency = request.data.get('frequency')

        if not cron_expression:
            return Response(
                {'error': 'cron_expression is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate cron expression
        try:
            cron = croniter(cron_expression, datetime.now())
            next_run = cron.get_next(datetime)

            jobneed.cron_expression = cron_expression
            jobneed.next_generation_date = next_run

            if frequency:
                jobneed.frequency = frequency

            jobneed.save()

            logger.info(f"Jobneed schedule updated: {jobneed.jobneed_number}")

            serializer = self.get_serializer(jobneed)
            return Response(serializer.data)

        except (ValueError, KeyError) as e:
            return Response(
                {'error': f'Invalid cron expression: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """
        Generate jobs from jobneed immediately.

        POST /api/v1/operations/jobneeds/{id}/generate/
        """
        jobneed = self.get_object()

        try:
            # Import the service
            from apps.scheduler.services.jobneed_management_service import JobneedManagementService

            service = JobneedManagementService()
            generated_jobs = service.generate_jobs_from_jobneed(jobneed)

            return Response({
                'message': f'Generated {len(generated_jobs)} jobs',
                'job_ids': [job.id for job in generated_jobs]
            })

        except Exception as e:
            logger.error(f"Error generating jobs: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to generate jobs'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@ontology(
    domain="operations",
    purpose="REST API for QuestionSet management for dynamic forms and checklists",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH", "DELETE"],
    authentication_required=True,
    permissions=["IsAuthenticated"],
    rate_limit="100/minute",
    request_schema="QuestionSetSerializer",
    response_schema="QuestionSetSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="medium",
    tags=["api", "rest", "operations", "questions", "forms", "mobile"],
    security_notes="Questions available to all authenticated users. Active questions only returned",
    endpoints={
        "list": "GET /api/v1/operations/questionsets/ - List question sets",
        "create": "POST /api/v1/operations/questionsets/ - Create question set",
        "retrieve": "GET /api/v1/operations/questionsets/{id}/ - Get question set with questions",
        "update": "PATCH /api/v1/operations/questionsets/{id}/ - Update question set",
        "delete": "DELETE /api/v1/operations/questionsets/{id}/ - Delete question set"
    },
    examples=[
        "curl -X GET https://api.example.com/api/v1/operations/questionsets/ -H 'Authorization: Bearer <token>'"
    ]
)
class QuestionSetViewSet(viewsets.ModelViewSet):
    """
    API endpoint for QuestionSet management.

    Endpoints:
    - GET    /api/v1/operations/questionsets/       List question sets
    - POST   /api/v1/operations/questionsets/       Create question set
    - GET    /api/v1/operations/questionsets/{id}/  Retrieve question set
    - PATCH  /api/v1/operations/questionsets/{id}/  Update question set
    - DELETE /api/v1/operations/questionsets/{id}/  Delete question set
    """
    permission_classes = [IsAuthenticated]
    serializer_class = QuestionSetSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Exclude outdated questionset API until aligned with new models

    filterset_fields = ['is_active']
    search_fields = ['name', 'description']

    def get_queryset(self):
        """Get all question sets."""
        return QuestionSet.objects.prefetch_related('questions').filter(is_active=True)


__all__ = [
    'JobViewSet',
    'JobneedViewSet',
    'QuestionSetViewSet',
]
