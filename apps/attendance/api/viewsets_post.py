"""
Post Assignment API ViewSets

Comprehensive REST API for:
- Post (duty station) management
- PostAssignment (roster) CRUD
- PostOrderAcknowledgement (compliance)
- Worker-facing endpoints for mobile apps

Author: Claude Code
Created: 2025-11-03
Phase: 2 - Post Assignment Model
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from datetime import datetime, timedelta

from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement
from apps.attendance.api.serializers_post import (
    PostListSerializer,
    PostDetailSerializer,
    PostGeoSerializer,
    PostAssignmentListSerializer,
    PostAssignmentDetailSerializer,
    PostAssignmentCreateSerializer,
    PostOrderAcknowledgementSerializer,
    PostOrderAcknowledgementCreateSerializer,
    PostOrdersForWorkerSerializer,
)
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from apps.attendance.api.throttles import (
    PostManagementThrottle,
    PostAssignmentThrottle,
    PostOrderAcknowledgementThrottle,
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS
from django.core.exceptions import ValidationError, ObjectDoesNotExist

import logging

logger = logging.getLogger(__name__)


# ==================== POST VIEWSET ====================

class PostViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Post (duty station) management.

    Endpoints:
    - GET    /api/v1/posts/                List posts
    - POST   /api/v1/posts/                Create post
    - GET    /api/v1/posts/{id}/           Retrieve post
    - PATCH  /api/v1/posts/{id}/           Update post
    - DELETE /api/v1/posts/{id}/           Delete post
    - GET    /api/v1/posts/active/         List active posts
    - GET    /api/v1/posts/by-site/{site_id}/  Posts for specific site
    - GET    /api/v1/posts/coverage-gaps/  Posts with coverage gaps
    - GET    /api/v1/posts/geo/            GeoJSON for map display
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    throttle_classes = [PostManagementThrottle]  # 100/hour rate limit
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination

    filterset_fields = ['site', 'shift', 'post_type', 'risk_level', 'active', 'coverage_required']
    search_fields = ['post_code', 'post_name', 'site__buname']
    ordering_fields = ['post_code', 'post_name', 'risk_level', 'created_at']
    ordering = ['site', 'shift', 'post_code']

    def get_queryset(self):
        """Get queryset with tenant filtering and optimization"""
        queryset = Post.objects.select_related(
            'site', 'zone', 'shift', 'geofence', 'created_by', 'modified_by'
        ).prefetch_related('required_certifications')

        # Tenant filtering
        if not self.request.user.is_superuser:
            queryset = queryset.filter(tenant=self.request.tenant)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PostListSerializer
        elif self.action == 'geo':
            return PostGeoSerializer
        return PostDetailSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active posts"""
        posts = self.get_queryset().filter(active=True)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-site/(?P<site_id>[^/.]+)')
    def by_site(self, request, site_id=None):
        """Get posts for specific site"""
        posts = self.get_queryset().filter(site_id=site_id, active=True)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def coverage_gaps(self, request):
        """Get posts with coverage gaps (assigned < required)"""
        today = timezone.now().date()
        posts = self.get_queryset().filter(
            active=True,
            coverage_required=True
        )

        gaps = []
        for post in posts:
            is_met, assigned, required = post.is_coverage_met(today)
            if not is_met:
                gaps.append({
                    'post': PostListSerializer(post).data,
                    'gap': required - assigned,
                    'assigned': assigned,
                    'required': required,
                })

        return Response({
            'date': today.isoformat(),
            'gaps_count': len(gaps),
            'gaps': gaps
        })

    @action(detail=False, methods=['get'])
    def geo(self, request):
        """Get posts as GeoJSON for map display"""
        posts = self.get_queryset().filter(
            active=True,
            gps_coordinates__isnull=False
        )
        serializer = PostGeoSerializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def increment_post_orders_version(self, request, pk=None):
        """Increment post orders version (invalidates acknowledgements)"""
        post = self.get_object()

        # Increment version
        old_version = post.post_orders_version
        post.post_orders_version += 1
        post.save(update_fields=['post_orders_version', 'post_orders_last_updated'])

        # Invalidate all existing acknowledgements
        PostOrderAcknowledgement.bulk_invalidate_for_post(
            post,
            reason=f"Post orders updated from v{old_version} to v{post.post_orders_version}"
        )

        logger.info(f"Post {post.post_code} orders updated to v{post.post_orders_version}")

        return Response({
            'status': 'success',
            'message': f'Post orders updated to version {post.post_orders_version}',
            'old_version': old_version,
            'new_version': post.post_orders_version,
            'acknowledgements_invalidated': True,
        })


# ==================== POST ASSIGNMENT VIEWSET ====================

class PostAssignmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for PostAssignment (roster) management.

    Endpoints:
    - GET    /api/v1/post-assignments/            List assignments
    - POST   /api/v1/post-assignments/            Create assignment
    - GET    /api/v1/post-assignments/{id}/       Retrieve assignment
    - PATCH  /api/v1/post-assignments/{id}/       Update assignment
    - DELETE /api/v1/post-assignments/{id}/       Delete assignment
    - GET    /api/v1/post-assignments/my-assignments/  Worker's assignments
    - GET    /api/v1/post-assignments/today/      Today's assignments
    - POST   /api/v1/post-assignments/{id}/confirm/  Confirm assignment
    - POST   /api/v1/post-assignments/{id}/cancel/   Cancel assignment
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    throttle_classes = [PostAssignmentThrottle]  # 200/hour rate limit
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination

    filterset_fields = ['worker', 'post', 'site', 'shift', 'assignment_date', 'status', 'is_override']
    search_fields = ['worker__username', 'post__post_code', 'site__buname']
    ordering_fields = ['assignment_date', 'start_time', 'status', 'created_at']
    ordering = ['-assignment_date', 'start_time']

    def get_queryset(self):
        """Get queryset with tenant filtering and optimization"""
        queryset = PostAssignment.objects.select_related(
            'worker', 'post', 'shift', 'site', 'assigned_by', 'approved_by', 'attendance_record'
        )

        # Tenant filtering
        if not self.request.user.is_superuser:
            queryset = queryset.filter(tenant=self.request.tenant)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return PostAssignmentCreateSerializer
        elif self.action == 'list':
            return PostAssignmentListSerializer
        return PostAssignmentDetailSerializer

    @action(detail=False, methods=['get'])
    def my_assignments(self, request):
        """Get logged-in worker's assignments"""
        worker_id = request.user.id
        assignments = self.get_queryset().filter(worker_id=worker_id)

        # Optional date filtering
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if date_from:
            assignments = assignments.filter(assignment_date__gte=date_from)
        if date_to:
            assignments = assignments.filter(assignment_date__lte=date_to)
        else:
            # Default: next 7 days
            today = timezone.now().date()
            assignments = assignments.filter(
                assignment_date__gte=today,
                assignment_date__lte=today + timedelta(days=7)
            )

        serializer = self.get_serializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's assignments (for supervisor dashboard)"""
        today = timezone.now().date()
        assignments = self.get_queryset().filter(assignment_date=today)

        # Optional site filtering
        site_id = request.query_params.get('site_id')
        if site_id:
            assignments = assignments.filter(site_id=site_id)

        # Optional status filtering
        status_filter = request.query_params.get('status')
        if status_filter:
            assignments = assignments.filter(status=status_filter)

        serializer = self.get_serializer(assignments, many=True)
        return Response({
            'date': today.isoformat(),
            'count': assignments.count(),
            'assignments': serializer.data
        })

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Worker confirms they will attend this assignment"""
        assignment = self.get_object()

        # Validate worker is the assigned worker
        if assignment.worker.id != request.user.id:
            return Response({
                'error': 'UNAUTHORIZED',
                'message': 'You can only confirm your own assignments'
            }, status=status.HTTP_403_FORBIDDEN)

        # Validate assignment can be confirmed
        if not assignment.can_check_in():
            return Response({
                'error': 'INVALID_STATUS',
                'message': f'Assignment cannot be confirmed (current status: {assignment.status})'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Mark as confirmed
        assignment.mark_confirmed()

        logger.info(f"Worker {request.user.id} confirmed assignment {assignment.id}")

        return Response({
            'status': 'success',
            'message': 'Assignment confirmed',
            'assignment': PostAssignmentDetailSerializer(assignment).data
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel assignment (supervisor only)"""
        assignment = self.get_object()

        # Check permissions (supervisor or admin)
        if not (request.user.is_staff or request.user == assignment.assigned_by):
            return Response({
                'error': 'PERMISSION_DENIED',
                'message': 'Only supervisors can cancel assignments'
            }, status=status.HTTP_403_FORBIDDEN)

        # Validate can be cancelled
        if assignment.status not in ['SCHEDULED', 'CONFIRMED']:
            return Response({
                'error': 'INVALID_STATUS',
                'message': f'Assignment cannot be cancelled (current status: {assignment.status})'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Cancel assignment
        assignment.status = 'CANCELLED'
        assignment.save(update_fields=['status'])

        logger.info(f"Assignment {assignment.id} cancelled by {request.user.id}")

        return Response({
            'status': 'success',
            'message': 'Assignment cancelled'
        })


# ==================== POST ORDER ACKNOWLEDGEMENT VIEWSET ====================

class PostOrderAcknowledgementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for PostOrderAcknowledgement management.

    Endpoints:
    - GET    /api/v1/post-acknowledgements/       List acknowledgements
    - POST   /api/v1/post-acknowledgements/       Create acknowledgement
    - GET    /api/v1/post-acknowledgements/{id}/  Retrieve acknowledgement
    - GET    /api/v1/post-acknowledgements/my-acknowledgements/  Worker's acknowledgements
    - POST   /api/v1/post-acknowledgements/acknowledge-post/     Acknowledge from mobile
    - GET    /api/v1/post-acknowledgements/post-orders-for-worker/  Get post orders to read
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    throttle_classes = [PostOrderAcknowledgementThrottle]  # 50/hour rate limit
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination

    filterset_fields = ['worker', 'post', 'post_assignment', 'is_valid', 'acknowledgement_date']
    search_fields = ['worker__username', 'post__post_code']
    ordering_fields = ['acknowledged_at', 'acknowledgement_date']
    ordering = ['-acknowledged_at']

    def get_queryset(self):
        """Get queryset with tenant filtering"""
        queryset = PostOrderAcknowledgement.objects.select_related(
            'worker', 'post', 'post_assignment', 'verified_by'
        )

        # Tenant filtering
        if not self.request.user.is_superuser:
            queryset = queryset.filter(tenant=self.request.tenant)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer"""
        if self.action == 'create' or self.action == 'acknowledge_post':
            return PostOrderAcknowledgementCreateSerializer
        return PostOrderAcknowledgementSerializer

    @action(detail=False, methods=['get'])
    def my_acknowledgements(self, request):
        """Get logged-in worker's acknowledgements"""
        worker_id = request.user.id
        acknowledgements = self.get_queryset().filter(worker_id=worker_id)

        # Optional date filtering
        date_from = request.query_params.get('date_from')
        if date_from:
            acknowledgements = acknowledgements.filter(acknowledgement_date__gte=date_from)

        serializer = self.get_serializer(acknowledgements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def acknowledge_post(self, request):
        """
        Worker acknowledges post orders (mobile app endpoint).

        Request:
        {
            "post_id": 123,
            "post_assignment_id": 456,  # optional
            "device_id": "device-uuid",
            "gps_location": {"lat": 28.6139, "lng": 77.2090},
            "time_to_acknowledge_seconds": 45,
            "digital_signature": "base64...",  # optional
            "worker_comments": "Understood all procedures"  # optional
        }
        """
        try:
            post_id = request.data.get('post_id')
            if not post_id:
                return Response({
                    'error': 'MISSING_POST_ID',
                    'message': 'post_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get post
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({
                    'error': 'POST_NOT_FOUND',
                    'message': f'Post {post_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if already acknowledged current version today
            today = timezone.now().date()
            existing = PostOrderAcknowledgement.has_valid_acknowledgement(
                worker=request.user,
                post=post,
                date=today
            )

            if existing:
                return Response({
                    'error': 'ALREADY_ACKNOWLEDGED',
                    'message': f'You have already acknowledged post orders for {post.post_code} today (v{post.post_orders_version})'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create acknowledgement
            serializer = PostOrderAcknowledgementCreateSerializer(
                data=request.data,
                context={'request': request}
            )

            if serializer.is_valid():
                acknowledgement = serializer.save()

                # If linked to post assignment, update assignment
                post_assignment_id = request.data.get('post_assignment_id')
                if post_assignment_id:
                    try:
                        assignment = PostAssignment.objects.get(
                            id=post_assignment_id,
                            worker=request.user
                        )
                        assignment.acknowledge_post_orders(post.post_orders_version)
                        logger.info(f"Updated PostAssignment {assignment.id} with acknowledgement")
                    except PostAssignment.DoesNotExist:
                        logger.warning(f"PostAssignment {post_assignment_id} not found for acknowledgement link")

                logger.info(
                    f"Worker {request.user.id} acknowledged post orders for {post.post_code} v{post.post_orders_version}"
                )

                return Response({
                    'status': 'success',
                    'message': 'Post orders acknowledged successfully',
                    'acknowledgement': PostOrderAcknowledgementSerializer(acknowledgement).data
                }, status=status.HTTP_201_CREATED)

            return Response({
                'error': 'VALIDATION_ERROR',
                'message': 'Invalid acknowledgement data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error creating acknowledgement: {e}", exc_info=True)
            return Response({
                'error': 'SERVER_ERROR',
                'message': 'Failed to create acknowledgement. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def post_orders_for_worker(self, request):
        """
        Get post orders that worker needs to acknowledge.

        Returns post orders for worker's upcoming assignments that haven't been acknowledged.

        Query params:
        - date: Date to check (defaults to today)
        """
        worker_id = request.user.id
        target_date = request.query_params.get('date')

        if target_date:
            try:
                from datetime import datetime
                target_date = datetime.fromisoformat(target_date).date()
            except ValueError:
                return Response({
                    'error': 'INVALID_DATE',
                    'message': 'Invalid date format. Use ISO format (YYYY-MM-DD)'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = timezone.now().date()

        # Get worker's assignments for target date
        assignments = PostAssignment.objects.filter(
            worker_id=worker_id,
            assignment_date=target_date,
            status__in=['SCHEDULED', 'CONFIRMED']
        ).select_related('post', 'shift')

        post_orders_list = []

        for assignment in assignments:
            post = assignment.post

            # Check if already acknowledged
            acknowledged = PostOrderAcknowledgement.has_valid_acknowledgement(
                worker=worker_id,
                post=post,
                date=target_date
            )

            # Get latest acknowledgement details
            latest_ack = PostOrderAcknowledgement.get_latest_acknowledgement(
                worker=worker_id,
                post=post
            )

            post_orders_list.append({
                'post_id': post.id,
                'post_code': post.post_code,
                'post_name': post.post_name,
                'post_type': post.post_type,
                'risk_level': post.risk_level,

                # Post orders content
                'post_orders': post.post_orders,
                'post_orders_version': post.post_orders_version,
                'post_orders_last_updated': post.post_orders_last_updated.isoformat() if post.post_orders_last_updated else None,
                'duties_summary': post.duties_summary,
                'emergency_procedures': post.emergency_procedures,
                'reporting_instructions': post.reporting_instructions,

                # Assignment details
                'assignment_id': assignment.id,
                'assignment_date': assignment.assignment_date.isoformat(),
                'shift_start_time': assignment.start_time.isoformat(),
                'shift_end_time': assignment.end_time.isoformat(),

                # Acknowledgement status
                'already_acknowledged': acknowledged,
                'acknowledged_version': latest_ack.post_orders_version if latest_ack else None,
                'must_acknowledge': not acknowledged and post.risk_level in ['CRITICAL', 'HIGH'],

                # Requirements
                'armed_required': post.armed_required,
                'required_certifications': post.get_required_certifications_list(),
            })

        return Response({
            'date': target_date.isoformat(),
            'worker_id': worker_id,
            'assignments_count': len(post_orders_list),
            'post_orders': post_orders_list,
            'requires_acknowledgement': any(p['must_acknowledge'] for p in post_orders_list),
        })


# ==================== WORKER-FACING ENDPOINTS ====================

class WorkerPostViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Worker-facing API for viewing their assigned posts.

    Mobile app endpoints for workers to:
    - View their assigned posts
    - Read post orders
    - Acknowledge post orders
    - View their schedule
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PostListSerializer

    def get_queryset(self):
        """Get posts assigned to logged-in worker"""
        worker_id = self.request.user.id
        today = timezone.now().date()

        # Get posts where worker has assignments
        assigned_post_ids = PostAssignment.objects.filter(
            worker_id=worker_id,
            assignment_date__gte=today,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).values_list('post_id', flat=True)

        return Post.objects.filter(
            id__in=assigned_post_ids,
            active=True
        ).select_related('site', 'shift', 'zone')

    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        """Get post orders for specific post"""
        post = self.get_object()

        # Check if worker has assignment for this post
        has_assignment = PostAssignment.objects.filter(
            worker=request.user,
            post=post,
            assignment_date__gte=timezone.now().date()
        ).exists()

        if not has_assignment:
            return Response({
                'error': 'NO_ASSIGNMENT',
                'message': 'You are not assigned to this post'
            }, status=status.HTTP_403_FORBIDDEN)

        return Response(post.get_post_orders_dict())
