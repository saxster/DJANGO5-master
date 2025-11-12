from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.threat_intelligence.models import (
    IntelligenceAlert,
    TenantIntelligenceProfile,
    TenantLearningProfile,
    CollectiveIntelligencePattern,
)
from apps.threat_intelligence.v2_api.schemas import (
    AlertListResponseSchema,
    IntelligenceAlertSchema,
    AlertFeedbackSchema,
    TenantProfileSchema,
    TenantProfileUpdateSchema,
    LearningMetricsSchema,
    CollectivePatternSchema,
)
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)


class IntelligenceAlertListView(APIView):
    """List intelligence alerts for authenticated tenant."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/v2/threat-intelligence/alerts/
        
        Query params:
        - status: Filter by delivery_status
        - severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)
        - unacknowledged_only: bool
        - limit: int (default 50)
        - offset: int (default 0)
        """
        tenant = request.user.tenant
        
        queryset = IntelligenceAlert.objects.filter(
            tenant=tenant
        ).select_related(
            'threat_event',
            'intelligence_profile'
        ).order_by('-created_at')
        
        # Filters
        if request.GET.get('status'):
            queryset = queryset.filter(delivery_status=request.GET['status'])
        
        if request.GET.get('severity'):
            queryset = queryset.filter(severity=request.GET['severity'])
        
        if request.GET.get('unacknowledged_only') == 'true':
            queryset = queryset.filter(acknowledged_at__isnull=True)
        
        # Pagination
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        total_count = queryset.count()
        unacknowledged_count = queryset.filter(acknowledged_at__isnull=True).count()
        critical_count = queryset.filter(severity='CRITICAL').count()
        
        alerts = queryset[offset:offset + limit]
        
        # Serialize with Pydantic
        alert_schemas = [IntelligenceAlertSchema.model_validate(alert) for alert in alerts]
        
        response_data = AlertListResponseSchema(
            alerts=alert_schemas,
            total_count=total_count,
            unacknowledged_count=unacknowledged_count,
            critical_count=critical_count,
        )
        
        return Response(response_data.model_dump(), status=status.HTTP_200_OK)


class IntelligenceAlertDetailView(APIView):
    """Get or update a specific alert."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, alert_id):
        """GET /api/v2/threat-intelligence/alerts/{alert_id}/"""
        alert = get_object_or_404(
            IntelligenceAlert.objects.select_related('threat_event'),
            id=alert_id,
            tenant=request.user.tenant
        )
        
        schema = IntelligenceAlertSchema.model_validate(alert)
        return Response(schema.model_dump(), status=status.HTTP_200_OK)
    
    def post(self, request, alert_id):
        """
        POST /api/v2/threat-intelligence/alerts/{alert_id}/feedback/
        
        Submit feedback on alert (for ML learning).
        """
        alert = get_object_or_404(
            IntelligenceAlert,
            id=alert_id,
            tenant=request.user.tenant
        )
        
        try:
            feedback = AlertFeedbackSchema.model_validate(request.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update alert with feedback
        alert.tenant_response = feedback.response_type
        alert.response_timestamp = timezone.now()
        alert.response_notes = feedback.notes or ""
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save()
        
        # Update learning profile metrics
        learning_profile, _ = TenantLearningProfile.objects.get_or_create(
            tenant=request.user.tenant,
            intelligence_profile=alert.intelligence_profile
        )
        
        if feedback.response_type == 'ACTIONABLE':
            learning_profile.total_actionable += 1
        elif feedback.response_type == 'FALSE_POSITIVE':
            learning_profile.total_false_positives += 1
        elif feedback.response_type == 'MISSED':
            learning_profile.total_missed += 1
        
        learning_profile.save()
        
        logger.info(
            f"Feedback submitted for alert {alert_id} by {request.user.username}: "
            f"{feedback.response_type}"
        )
        
        schema = IntelligenceAlertSchema.model_validate(alert)
        return Response(schema.model_dump(), status=status.HTTP_200_OK)


class TenantIntelligenceProfileView(APIView):
    """Get or update tenant intelligence profile."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """GET /api/v2/threat-intelligence/profile/"""
        profile = get_object_or_404(
            TenantIntelligenceProfile,
            tenant=request.user.tenant,
            is_active=True
        )
        
        schema = TenantProfileSchema.model_validate(profile)
        return Response(schema.model_dump(), status=status.HTTP_200_OK)
    
    def patch(self, request):
        """
        PATCH /api/v2/threat-intelligence/profile/
        
        Update tenant intelligence preferences.
        """
        profile = get_object_or_404(
            TenantIntelligenceProfile,
            tenant=request.user.tenant,
            is_active=True
        )
        
        try:
            updates = TenantProfileUpdateSchema.model_validate(request.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # Apply updates
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)
        
        profile.save()
        
        logger.info(f"Intelligence profile updated for tenant {request.user.tenant.name}")
        
        schema = TenantProfileSchema.model_validate(profile)
        return Response(schema.model_dump(), status=status.HTTP_200_OK)


class LearningMetricsView(APIView):
    """Get ML learning metrics for tenant."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """GET /api/v2/threat-intelligence/metrics/"""
        profile = get_object_or_404(
            TenantIntelligenceProfile,
            tenant=request.user.tenant,
            is_active=True
        )
        
        learning_profile, _ = TenantLearningProfile.objects.get_or_create(
            tenant=request.user.tenant,
            intelligence_profile=profile
        )
        
        schema = LearningMetricsSchema.model_validate(learning_profile)
        return Response(schema.model_dump(), status=status.HTTP_200_OK)


class CollectivePatternsView(APIView):
    """Get collective intelligence patterns relevant to tenant."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/v2/threat-intelligence/patterns/
        
        Returns anonymized patterns from similar tenants/industries.
        """
        profile = get_object_or_404(
            TenantIntelligenceProfile,
            tenant=request.user.tenant,
            is_active=True
        )
        
        # Get patterns matching tenant's threat categories
        patterns = CollectiveIntelligencePattern.objects.filter(
            is_active=True,
            threat_category__in=profile.threat_categories
        ).order_by('-confidence_score', '-sample_size')[:20]
        
        schemas = [CollectivePatternSchema.model_validate(p) for p in patterns]
        
        return Response({
            'patterns': [s.model_dump() for s in schemas],
            'count': len(schemas)
        }, status=status.HTTP_200_OK)
