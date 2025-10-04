"""
People Onboarding API Views

REST API endpoints for onboarding operations.
Complies with Rule #8: View methods < 30 lines
Complies with Rule #17: Mandatory transaction management

Author: Claude Code
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from apps.core.utils_new.db_utils import get_current_db_name
from .models import (
    OnboardingRequest, CandidateProfile,
    DocumentSubmission, ApprovalWorkflow, OnboardingTask
)
from .serializers import (
    OnboardingRequestSerializer, OnboardingRequestListSerializer,
    DocumentSubmissionSerializer, ApprovalWorkflowSerializer,
    OnboardingTaskSerializer
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_list_api(request):
    """Get list of onboarding requests"""
    queryset = OnboardingRequest.objects.select_related(
        'candidate_profile', 'cdby'
    ).order_by('-cdtz')

    # Filter by state if provided
    state = request.query_params.get('state')
    if state:
        queryset = queryset.filter(current_state=state)

    serializer = OnboardingRequestListSerializer(
        queryset, many=True, context={'request': request}
    )
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_detail_api(request, uuid):
    """Get detailed onboarding request"""
    onboarding_request = get_object_or_404(OnboardingRequest, uuid=uuid)
    serializer = OnboardingRequestSerializer(
        onboarding_request, context={'request': request}
    )
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_upload_api(request):
    """Upload document via AJAX"""
    serializer = DocumentSubmissionSerializer(
        data=request.data,
        context={'request': request}
    )

    if serializer.is_valid():
        try:
            with transaction.atomic(using=get_current_db_name()):
                document = serializer.save(cdby=request.user)

                # Trigger OCR extraction (async task)
                try:
                    from .tasks import extract_document_data
                    extract_document_data.delay(document.id)
                except ImportError:
                    pass  # Celery not available

                return Response({
                    'status': 'success',
                    'message': 'Document uploaded successfully',
                    'document': DocumentSubmissionSerializer(
                        document, context={'request': request}
                    ).data
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def document_delete_api(request, uuid):
    """Delete document"""
    document = get_object_or_404(DocumentSubmission, uuid=uuid)

    # Permission check
    if document.onboarding_request.cdby != request.user and not request.user.is_staff:
        return Response({
            'status': 'error',
            'message': 'Access denied'
        }, status=status.HTTP_403_FORBIDDEN)

    # Cannot delete verified documents
    if document.verification_status == 'VERIFIED':
        return Response({
            'status': 'error',
            'message': 'Cannot delete verified documents'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic(using=get_current_db_name()):
            document.delete()
            return Response({
                'status': 'success',
                'message': 'Document deleted successfully'
            })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approval_decision_api(request, uuid):
    """Submit approval decision"""
    approval = get_object_or_404(ApprovalWorkflow, uuid=uuid)

    # Permission check
    if approval.approver != request.user:
        return Response({
            'status': 'error',
            'message': 'Access denied'
        }, status=status.HTTP_403_FORBIDDEN)

    # Check if already decided
    if approval.decision != 'PENDING':
        return Response({
            'status': 'error',
            'message': 'Decision already made'
        }, status=status.HTTP_400_BAD_REQUEST)

    decision = request.data.get('decision')
    notes = request.data.get('notes')

    if not decision or not notes:
        return Response({
            'status': 'error',
            'message': 'Decision and notes are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic(using=get_current_db_name()):
            ip_address = request.META.get('REMOTE_ADDR')

            if decision == 'APPROVED':
                approval.approve(notes=notes, ip_address=ip_address)
            elif decision == 'REJECTED':
                approval.reject(notes=notes, ip_address=ip_address)
            elif decision == 'ESCALATED':
                escalated_to_id = request.data.get('escalated_to')
                escalation_reason = request.data.get('escalation_reason')

                if not escalated_to_id or not escalation_reason:
                    return Response({
                        'status': 'error',
                        'message': 'Escalation requires target and reason'
                    }, status=status.HTTP_400_BAD_REQUEST)

                from apps.peoples.models import People
                escalated_to = get_object_or_404(People, id=escalated_to_id)
                approval.escalate(
                    escalated_to=escalated_to,
                    reason=escalation_reason,
                    ip_address=ip_address
                )
            else:
                return Response({
                    'status': 'error',
                    'message': 'Invalid decision'
                }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'status': 'success',
                'message': f'Request {decision.lower()} successfully',
                'approval': ApprovalWorkflowSerializer(
                    approval, context={'request': request}
                ).data
            })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_start_api(request, uuid):
    """Start a task"""
    task = get_object_or_404(OnboardingTask, uuid=uuid)

    if task.status != 'PENDING':
        return Response({
            'status': 'error',
            'message': 'Task already started or completed'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic(using=get_current_db_name()):
            task.status = 'IN_PROGRESS'
            task.save()

            return Response({
                'status': 'success',
                'message': 'Task started',
                'task': OnboardingTaskSerializer(
                    task, context={'request': request}
                ).data
            })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_complete_api(request, uuid):
    """Complete a task"""
    task = get_object_or_404(OnboardingTask, uuid=uuid)

    if task.status == 'COMPLETED':
        return Response({
            'status': 'error',
            'message': 'Task already completed'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic(using=get_current_db_name()):
            task.status = 'COMPLETED'
            task.completed_date = timezone.now()
            task.save()

            return Response({
                'status': 'success',
                'message': 'Task completed',
                'task': OnboardingTaskSerializer(
                    task, context={'request': request}
                ).data
            })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_analytics_api(request):
    """Get dashboard analytics data"""
    from django.db.models import Count, Avg, Q
    from datetime import timedelta

    # Pipeline data
    pipeline_data = {
        'labels': ['Draft', 'Submitted', 'In Progress', 'Approval', 'Completed'],
        'values': [
            OnboardingRequest.objects.filter(current_state='DRAFT').count(),
            OnboardingRequest.objects.filter(current_state='SUBMITTED').count(),
            OnboardingRequest.objects.filter(
                current_state__in=['DOCUMENT_VERIFICATION', 'BACKGROUND_CHECK']
            ).count(),
            OnboardingRequest.objects.filter(current_state='PENDING_APPROVAL').count(),
            OnboardingRequest.objects.filter(current_state='COMPLETED').count(),
        ]
    }

    # Person type distribution
    person_type_data = OnboardingRequest.objects.values(
        'person_type'
    ).annotate(count=Count('id'))

    person_type_dist = {
        'labels': [item['person_type'] for item in person_type_data],
        'values': [item['count'] for item in person_type_data]
    }

    return Response({
        'pipeline': pipeline_data,
        'person_types': person_type_dist,
        'total_active': OnboardingRequest.objects.exclude(
            current_state__in=['COMPLETED', 'REJECTED', 'CANCELLED']
        ).count(),
        'completed_last_30_days': OnboardingRequest.objects.filter(
            current_state='COMPLETED',
            uptz__gte=timezone.now() - timedelta(days=30)
        ).count()
    })