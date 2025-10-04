"""
Knowledge Base Views

Handles authoritative knowledge management and validation.

Migrated from: apps/onboarding_api/views.py (lines 1073-1183)
Date: 2025-09-30
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.onboarding.models import AuthoritativeKnowledge
from ..serializers import AuthoritativeKnowledgeSerializer
import logging

logger = logging.getLogger(__name__)


class AuthoritativeKnowledgeViewSet(ModelViewSet):
    """ViewSet for managing authoritative knowledge (admin/staff only)"""
    queryset = AuthoritativeKnowledge.objects.all()
    serializer_class = AuthoritativeKnowledgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset for non-staff users"""
        if not self.request.user.is_staff:
            return AuthoritativeKnowledge.objects.none()
        return super().get_queryset()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_knowledge(request):
    """Validate knowledge against authoritative sources"""
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        data = request.data

        if 'recommendation' not in data:
            return Response(
                {"error": "Missing 'recommendation' field"},
                status=status.HTTP_400_BAD_REQUEST
            )

        recommendation = data['recommendation']
        context = data.get('context', {})

        from ..services.knowledge import get_knowledge_service
        knowledge_service = get_knowledge_service()

        validation_result = knowledge_service.validate_recommendation_against_knowledge(
            recommendation=recommendation,
            context=context
        )

        enhanced_result = {
            'validation_status': 'valid' if validation_result['is_valid'] else 'invalid',
            'confidence_score': validation_result['confidence_score'],
            'is_compliant': validation_result['is_valid'],
            'supporting_sources': validation_result['supporting_sources'],
            'potential_conflicts': validation_result['potential_conflicts'],
            'recommendations': validation_result.get('recommendations', []),
            'validation_details': {
                'sources_checked': len(validation_result['supporting_sources']),
                'conflicts_found': len(validation_result['potential_conflicts']),
                'validation_timestamp': timezone.now().isoformat(),
                'validated_by': request.user.email
            }
        }

        # Add risk assessment
        if validation_result['confidence_score'] < 0.6:
            enhanced_result['risk_level'] = 'high'
            enhanced_result['warning'] = 'Low confidence - manual review recommended'
        elif validation_result['confidence_score'] < 0.8:
            enhanced_result['risk_level'] = 'medium'
            enhanced_result['warning'] = 'Medium confidence - consider verification'
        else:
            enhanced_result['risk_level'] = 'low'

        return Response(enhanced_result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in knowledge validation: {str(e)}")
        return Response(
            {
                "error": "Knowledge validation failed",
                "details": str(e),
                "support_reference": timezone.now().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
