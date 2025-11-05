"""
Personalization Views - Daily wellness tips and contextual content delivery

Provides:
- Daily wellness tips with intelligent personalization
- Contextual content delivery based on journal entry analysis
- Real-time pattern analysis and urgency assessment
"""

from datetime import timedelta
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

from apps.wellness.models import WellnessUserProgress, WellnessContentInteraction
from apps.wellness.serializers import (
    WellnessContentDetailSerializer,
    DailyWellnessTipRequestSerializer,
    ContextualWellnessContentRequestSerializer
)
from apps.wellness.services.wellness import (
    PatternAnalysisService,
    PersonalizationService,
    UrgencyAnalysisService,
    ContentSelectionService
)
from apps.wellness.logging import get_wellness_logger
from .permissions import WellnessPermission

logger = get_wellness_logger(__name__)


class DailyWellnessTipView(APIView):
    """Daily wellness tip with intelligent personalization"""

    permission_classes = [WellnessPermission]

    def get(self, request):
        """Get personalized daily wellness tip for user"""
        user = request.user

        # Parse request parameters
        serializer = DailyWellnessTipRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = serializer.validated_data

        try:
            # Get or create user progress
            progress, created = WellnessUserProgress.objects.get_or_create(
                user=user,
                defaults={'tenant': getattr(user, 'tenant', None)}
            )

            # Analyze patterns and select tip
            user_patterns = PatternAnalysisService.analyze_recent_patterns(user)
            daily_tip = PersonalizationService.select_personalized_tip(user, progress, user_patterns, params)

            if daily_tip:
                return self._build_tip_response(user, daily_tip, user_patterns, request)
            else:
                return self._build_no_tip_response()

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to generate daily tip for user {user.id}: {e}")
            return Response({'error': 'Failed to generate daily tip'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _build_tip_response(self, user, daily_tip, user_patterns, request):
        """Build response with daily tip"""
        interaction = WellnessContentInteraction.objects.create(
            user=user,
            content=daily_tip,
            interaction_type='viewed',
            delivery_context='daily_tip',
            user_mood_at_delivery=user_patterns.get('current_mood'),
            user_stress_at_delivery=user_patterns.get('current_stress')
        )

        logger.info(f"Daily tip delivered to {user.peoplename}: '{daily_tip.title}'")

        return Response({
            'daily_tip': WellnessContentDetailSerializer(daily_tip, context={'request': request}).data,
            'personalization_metadata': {
                'user_patterns': user_patterns,
                'selection_reason': 'Pattern-based personalization',
                'effectiveness_prediction': 0.8
            },
            'next_tip_available_at': (timezone.now() + timedelta(days=1)).isoformat(),
            'interaction_id': interaction.id
        })

    def _build_no_tip_response(self):
        """Build response when no tip is available"""
        return Response({
            'daily_tip': None,
            'message': 'No suitable tip found for today. Try again tomorrow!',
            'next_tip_available_at': (timezone.now() + timedelta(days=1)).isoformat()
        })


class ContextualWellnessContentView(APIView):
    """Real-time contextual content delivery based on journal entries"""

    permission_classes = [WellnessPermission]

    def post(self, request):
        """Get contextual wellness content based on journal entry"""
        serializer = ContextualWellnessContentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user
        journal_entry_data = data['journal_entry']
        user_context = data.get('user_context', {})
        max_items = data.get('max_content_items', 3)

        try:
            # Analyze urgency and get content
            urgency_analysis = UrgencyAnalysisService.analyze_entry_urgency(journal_entry_data)
            immediate_content, follow_up_content = self._get_contextual_content(
                user, urgency_analysis, user_context, max_items
            )

            # Track delivery
            self._track_content_delivery(user, immediate_content, journal_entry_data, urgency_analysis)

            logger.info(f"Contextual content delivered to {user.peoplename}: "
                       f"{len(immediate_content)} immediate, {len(follow_up_content)} follow-up")

            return self._build_contextual_response(immediate_content, follow_up_content, urgency_analysis)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Contextual content delivery failed for user {user.id}: {e}")
            return Response({'error': 'Contextual content delivery failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_contextual_content(self, user, urgency_analysis, user_context, max_items):
        """Get immediate and follow-up content based on urgency"""
        immediate_content = []
        follow_up_content = []

        if urgency_analysis['urgency_score'] >= 5:
            immediate_content = ContentSelectionService.get_urgent_support_content(
                user, urgency_analysis, user_context, max_items
            )

        if urgency_analysis['urgency_score'] >= 2:
            follow_up_content = ContentSelectionService.get_follow_up_content(
                user, urgency_analysis, user_context, max_items
            )

        return immediate_content, follow_up_content

    def _track_content_delivery(self, user, content_list, journal_entry_data, urgency_analysis):
        """Track contextual content delivery"""
        for content in content_list:
            WellnessContentInteraction.objects.create(
                user=user,
                content=content,
                interaction_type='viewed',
                delivery_context='pattern_triggered',
                user_mood_at_delivery=journal_entry_data.get('mood_rating'),
                user_stress_at_delivery=journal_entry_data.get('stress_level'),
                metadata={'urgency_analysis': urgency_analysis}
            )

    def _build_contextual_response(self, immediate_content, follow_up_content, urgency_analysis):
        """Build contextual content response"""
        return Response({
            'immediate_content': WellnessContentDetailSerializer(immediate_content, many=True).data,
            'follow_up_content': WellnessContentDetailSerializer(follow_up_content, many=True).data,
            'urgency_analysis': urgency_analysis,
            'delivery_metadata': {
                'analysis_timestamp': timezone.now().isoformat(),
                'algorithm_version': '2.1.0',
                'user_pattern_confidence': urgency_analysis.get('confidence', 0.5)
            }
        })
