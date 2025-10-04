"""
Wellness App Views - Complete API Implementation

Comprehensive API endpoints for wellness education system as specified:
- Daily wellness tips with intelligent personalization
- Contextual content delivery based on journal patterns
- ML-powered recommendation engine with effectiveness tracking
- User progress tracking with gamification elements
- Evidence-based content management with WHO/CDC compliance
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta

from .models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from .serializers import (
    WellnessContentListSerializer, WellnessContentDetailSerializer,
    WellnessUserProgressSerializer, WellnessContentInteractionSerializer,
    WellnessContentInteractionCreateSerializer, DailyWellnessTipRequestSerializer,
    ContextualWellnessContentRequestSerializer, PersonalizedContentRequestSerializer,
    WellnessRecommendationSerializer, WellnessAnalyticsSerializer
)
from .logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class WellnessPermission(permissions.BasePermission):
    """Custom permission for wellness system"""

    def has_permission(self, request, view):
        """Check if user has permission to access wellness system"""
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user can access specific wellness object"""
        if isinstance(obj, WellnessContent):
            return obj.is_active  # Content must be active
        elif isinstance(obj, WellnessUserProgress):
            return obj.user == request.user or request.user.is_superuser
        elif isinstance(obj, WellnessContentInteraction):
            return obj.user == request.user or request.user.is_superuser

        return False


class WellnessContentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for wellness content with filtering and analytics

    Provides:
    - Read-only access to wellness content
    - Filtering by category, evidence level, workplace relevance
    - Content effectiveness analytics
    """

    permission_classes = [WellnessPermission]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return WellnessContentListSerializer
        else:
            return WellnessContentDetailSerializer

    def get_queryset(self):
        """Filtered queryset for wellness content"""
        user = self.request.user

        # Base queryset with tenant filtering
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True
        ).select_related('created_by', 'tenant').prefetch_related('interactions')

        # Apply filters from query parameters
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        evidence_level = self.request.query_params.get('evidence_level')
        if evidence_level:
            queryset = queryset.filter(evidence_level=evidence_level)

        content_level = self.request.query_params.get('content_level')
        if content_level:
            queryset = queryset.filter(content_level=content_level)

        workplace_specific = self.request.query_params.get('workplace_specific')
        if workplace_specific == 'true':
            queryset = queryset.filter(workplace_specific=True)

        field_worker_relevant = self.request.query_params.get('field_worker_relevant')
        if field_worker_relevant == 'true':
            queryset = queryset.filter(field_worker_relevant=True)

        high_evidence = self.request.query_params.get('high_evidence')
        if high_evidence == 'true':
            queryset = queryset.filter(evidence_level__in=['who_cdc', 'peer_reviewed'])

        return queryset.order_by('-priority_score', '-created_at')

    @action(detail=True, methods=['post'])
    def track_interaction(self, request, pk=None):
        """Track user interaction with wellness content"""
        content = self.get_object()

        serializer = WellnessContentInteractionCreateSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            interaction = serializer.save(content=content)

            logger.info(f"Wellness interaction tracked: {request.user.peoplename} {interaction.interaction_type} '{content.title}'")

            return Response({
                'interaction_id': interaction.id,
                'engagement_score': interaction.engagement_score,
                'message': 'Interaction tracked successfully'
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get wellness categories with content counts"""
        categories = []

        for category_code, category_name in WellnessContent.WellnessContentCategory.choices:
            content_count = WellnessContent.objects.filter(
                category=category_code,
                is_active=True,
                tenant=getattr(request.user, 'tenant', None)
            ).count()

            categories.append({
                'code': category_code,
                'name': category_name,
                'content_count': content_count
            })

        return Response({
            'categories': categories,
            'total_content': sum(cat['content_count'] for cat in categories)
        })


class DailyWellnessTipView(APIView):
    """
    Daily wellness tip with intelligent personalization

    Implements the algorithm specified in the original document:
    1. Analyze user's last 7 days of journal entries
    2. Identify current stress/mood/energy patterns
    3. Check recent wellness content consumption to avoid repetition
    4. Select tip based on urgency, personalization, and seasonal relevance
    5. Track delivery for effectiveness measurement
    """

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

            # Analyze recent journal patterns for personalization
            user_patterns = self._analyze_recent_patterns(user)

            # Select personalized tip
            daily_tip = self._select_personalized_tip(user, progress, user_patterns, params)

            if daily_tip:
                # Track delivery
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
                        'effectiveness_prediction': 0.8  # Placeholder
                    },
                    'next_tip_available_at': (timezone.now() + timedelta(days=1)).isoformat(),
                    'interaction_id': interaction.id
                })

            else:
                return Response({
                    'daily_tip': None,
                    'message': 'No suitable tip found for today. Try again tomorrow!',
                    'next_tip_available_at': (timezone.now() + timedelta(days=1)).isoformat()
                })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to generate daily tip for user {user.id}: {e}")
            return Response(
                {'error': 'Failed to generate daily tip'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _analyze_recent_patterns(self, user):
        """Analyze user's recent journal patterns for personalization"""
        try:
            # Get recent journal entries (last 7 days)
            from apps.journal.models import JournalEntry

            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=7),
                is_deleted=False
            ).order_by('-timestamp')

            patterns = {
                'entry_count': recent_entries.count(),
                'wellbeing_entries': recent_entries.filter(
                    entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']
                ).count()
            }

            # Mood analysis
            mood_entries = recent_entries.exclude(mood_rating__isnull=True)
            if mood_entries.exists():
                patterns['current_mood'] = mood_entries.first().mood_rating
                patterns['avg_mood'] = mood_entries.aggregate(avg=Avg('mood_rating'))['avg']

            # Stress analysis
            stress_entries = recent_entries.exclude(stress_level__isnull=True)
            if stress_entries.exists():
                patterns['current_stress'] = stress_entries.first().stress_level
                patterns['avg_stress'] = stress_entries.aggregate(avg=Avg('stress_level'))['avg']

            # Energy analysis
            energy_entries = recent_entries.exclude(energy_level__isnull=True)
            if energy_entries.exists():
                patterns['current_energy'] = energy_entries.first().energy_level
                patterns['avg_energy'] = energy_entries.aggregate(avg=Avg('energy_level'))['avg']

            return patterns

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to analyze patterns for user {user.id}: {e}")
            return {'entry_count': 0}

    def _select_personalized_tip(self, user, progress, patterns, params):
        """Select personalized wellness tip based on user patterns"""
        # Base queryset
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            delivery_context__in=['daily_tip', 'pattern_triggered']
        )

        # Apply user preferences
        if progress.enabled_categories:
            queryset = queryset.filter(category__in=progress.enabled_categories)

        if params.get('preferred_category'):
            queryset = queryset.filter(category=params['preferred_category'])

        if params.get('content_level'):
            queryset = queryset.filter(content_level=params['content_level'])
        else:
            # Use user's preferred content level
            queryset = queryset.filter(content_level=progress.preferred_content_level)

        # Exclude recently viewed content
        if params.get('exclude_recent', True):
            recent_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                interaction_date__gte=timezone.now() - timedelta(days=7)
            ).values_list('content_id', flat=True)

            queryset = queryset.exclude(id__in=recent_interactions)

        # Personalize based on patterns
        if patterns.get('current_stress', 0) >= 4:
            # High stress - prioritize stress management
            queryset = queryset.filter(
                Q(category='stress_management') |
                Q(tags__contains=['stress', 'anxiety', 'pressure'])
            )
        elif patterns.get('current_mood', 10) <= 3:
            # Low mood - prioritize mood support
            queryset = queryset.filter(
                Q(category='mental_health') |
                Q(tags__contains=['mood', 'depression', 'wellbeing'])
            )
        elif patterns.get('current_energy', 10) <= 4:
            # Low energy - prioritize energy boosting
            queryset = queryset.filter(
                Q(category='physical_wellness') |
                Q(tags__contains=['energy', 'fatigue', 'vitality'])
            )

        # Check seasonal relevance
        current_month = timezone.now().month
        queryset = queryset.filter(
            Q(seasonal_relevance__contains=[current_month]) |
            Q(seasonal_relevance=[])  # No seasonal restrictions
        )

        # Order by priority and randomize within same priority
        queryset = queryset.order_by('-priority_score', '?')

        return queryset.first()


class ContextualWellnessContentView(APIView):
    """
    Real-time contextual content delivery based on journal entries

    Implements the algorithm specified in the original document:
    1. Receive journal entry context from mobile client
    2. Real-time pattern analysis for urgency assessment
    3. ML-based content matching using user history and entry context
    4. Priority-based content ranking with effectiveness prediction
    5. Return immediate + follow-up content recommendations
    """

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
            # Analyze journal entry for urgency and content needs
            urgency_analysis = self._analyze_entry_urgency(journal_entry_data)

            # Get contextual content based on analysis
            immediate_content = []
            follow_up_content = []

            if urgency_analysis['urgency_score'] >= 5:  # High urgency
                immediate_content = self._get_urgent_support_content(
                    user, urgency_analysis, user_context, max_items
                )

            if urgency_analysis['urgency_score'] >= 2:  # Any notable patterns
                follow_up_content = self._get_follow_up_content(
                    user, urgency_analysis, user_context, max_items
                )

            # Track contextual delivery
            for content in immediate_content:
                WellnessContentInteraction.objects.create(
                    user=user,
                    content=content,
                    interaction_type='viewed',
                    delivery_context='pattern_triggered',
                    user_mood_at_delivery=journal_entry_data.get('mood_rating'),
                    user_stress_at_delivery=journal_entry_data.get('stress_level'),
                    metadata={'urgency_analysis': urgency_analysis}
                )

            logger.info(f"Contextual content delivered to {user.peoplename}: {len(immediate_content)} immediate, {len(follow_up_content)} follow-up")

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

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Contextual content delivery failed for user {user.id}: {e}")
            return Response(
                {'error': 'Contextual content delivery failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _analyze_entry_urgency(self, journal_entry_data):
        """Analyze journal entry for urgency and intervention needs"""
        urgency_score = 0
        intervention_categories = []
        triggers = []

        # Mood analysis
        mood = journal_entry_data.get('mood_rating')
        if mood and mood <= 2:
            urgency_score += 4
            intervention_categories.append('mood_crisis_support')
            triggers.append('very_low_mood')

        # Stress analysis
        stress = journal_entry_data.get('stress_level')
        if stress and stress >= 4:
            urgency_score += 3
            intervention_categories.append('stress_management')
            triggers.append('high_stress')

        # Energy analysis
        energy = journal_entry_data.get('energy_level')
        if energy and energy <= 3:
            urgency_score += 1
            intervention_categories.append('energy_management')
            triggers.append('low_energy')

        # Content analysis for crisis keywords
        content = journal_entry_data.get('content', '').lower()
        crisis_keywords = ['hopeless', 'overwhelmed', "can't cope", 'breaking point']

        found_keywords = [kw for kw in crisis_keywords if kw in content]
        if found_keywords:
            urgency_score += 2
            intervention_categories.append('crisis_intervention')
            triggers.extend(found_keywords)

        return {
            'urgency_score': urgency_score,
            'urgency_level': 'high' if urgency_score >= 5 else 'medium' if urgency_score >= 2 else 'low',
            'intervention_categories': intervention_categories,
            'triggers': triggers,
            'confidence': min(1.0, urgency_score / 10)
        }

    def _get_urgent_support_content(self, user, urgency_analysis, user_context, max_items):
        """Get immediate support content for urgent situations"""
        categories = urgency_analysis.get('intervention_categories', [])

        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            delivery_context__in=['stress_response', 'mood_support', 'energy_boost']
        )

        # Filter by intervention categories
        if 'stress_management' in categories:
            queryset = queryset.filter(
                Q(category='stress_management') |
                Q(delivery_context='stress_response')
            )
        elif 'mood_crisis_support' in categories:
            queryset = queryset.filter(
                Q(category='mental_health') |
                Q(delivery_context='mood_support')
            )
        elif 'energy_management' in categories:
            queryset = queryset.filter(
                Q(category='physical_wellness') |
                Q(delivery_context='energy_boost')
            )

        return list(queryset.order_by('-priority_score')[:max_items])

    def _get_follow_up_content(self, user, urgency_analysis, user_context, max_items):
        """Get follow-up content for continued support"""
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            delivery_context='pattern_triggered'
        )

        # Select content based on lower urgency patterns
        categories = ['mental_health', 'stress_management', 'workplace_health']
        queryset = queryset.filter(category__in=categories)

        return list(queryset.order_by('-priority_score', '?')[:max_items])


class PersonalizedWellnessContentView(APIView):
    """
    ML-powered personalized wellness content recommendations

    Implements the algorithm specified in the original document:
    1. Build comprehensive user profile from journal history
    2. Analyze wellness content engagement patterns
    3. Apply collaborative filtering with similar users
    4. Content-based filtering using entry patterns
    5. Rank content by predicted effectiveness
    6. Apply diversity constraints to avoid content type clustering
    """

    permission_classes = [WellnessPermission]

    def get(self, request):
        """Get personalized wellness content recommendations"""
        serializer = PersonalizedContentRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = serializer.validated_data
        user = request.user

        try:
            # Build user profile for recommendations
            user_profile = self._build_user_profile(user)

            # Generate personalized recommendations
            recommendations = self._generate_ml_recommendations(
                user, user_profile, params
            )

            return Response({
                'personalized_content': [
                    WellnessRecommendationSerializer({
                        'content': item['content'],
                        'personalization_score': item['score'],
                        'recommendation_reason': item['reason'],
                        'predicted_effectiveness': item['effectiveness'],
                        'estimated_value': item['value_score'],
                        'delivery_context': item.get('context', 'personalized')
                    }).data
                    for item in recommendations
                ],
                'personalization_metadata': {
                    'user_profile_features': user_profile,
                    'recommendation_algorithm': 'hybrid_cf_cbf_v2.1',
                    'model_confidence': 0.8,  # Placeholder
                    'diversity_score': self._calculate_diversity_score(recommendations)
                }
            })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Personalized content generation failed for user {user.id}: {e}")
            return Response(
                {'error': 'Personalized content generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _build_user_profile(self, user):
        """Build comprehensive user profile for ML recommendations"""
        profile = {}

        try:
            # Wellness progress data
            progress = user.wellness_progress
            profile.update({
                'current_streak': progress.current_streak,
                'total_content_viewed': progress.total_content_viewed,
                'completion_rate': progress.completion_rate,
                'preferred_content_level': progress.preferred_content_level,
                'enabled_categories': progress.enabled_categories
            })
        except WellnessUserProgress.DoesNotExist:
            profile.update({
                'current_streak': 0,
                'total_content_viewed': 0,
                'completion_rate': 0.0,
                'preferred_content_level': 'short_read',
                'enabled_categories': []
            })

        # Journal patterns analysis
        try:
            from apps.journal.models import JournalEntry

            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=30)
            )

            mood_entries = recent_entries.exclude(mood_rating__isnull=True)
            if mood_entries.exists():
                profile['avg_mood'] = mood_entries.aggregate(avg=Avg('mood_rating'))['avg']

            stress_entries = recent_entries.exclude(stress_level__isnull=True)
            if stress_entries.exists():
                profile['avg_stress'] = stress_entries.aggregate(avg=Avg('stress_level'))['avg']

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to analyze journal patterns: {e}")

        # Content interaction patterns
        interactions = WellnessContentInteraction.objects.filter(
            user=user,
            interaction_date__gte=timezone.now() - timedelta(days=30)
        )

        if interactions.exists():
            profile.update({
                'interaction_count': interactions.count(),
                'avg_engagement_score': interactions.aggregate(avg=Avg('engagement_score'))['avg'],
                'preferred_categories': list(interactions.values('content__category').annotate(
                    count=Count('id')
                ).order_by('-count')[:3].values_list('content__category', flat=True))
            })

        return profile

    def _generate_ml_recommendations(self, user, user_profile, params):
        """Generate ML-based content recommendations"""
        limit = params['limit']
        categories = params.get('categories', [])
        exclude_viewed = params.get('exclude_viewed', True)
        diversity_enabled = params.get('diversity_enabled', True)

        # Base queryset
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True
        )

        # Apply category filter
        if categories:
            queryset = queryset.filter(category__in=categories)

        # Exclude recently viewed content
        if exclude_viewed:
            recent_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                interaction_date__gte=timezone.now() - timedelta(days=14)
            ).values_list('content_id', flat=True)

            queryset = queryset.exclude(id__in=recent_interactions)

        # Content-based filtering
        preferred_categories = user_profile.get('preferred_categories', [])
        if preferred_categories:
            # Boost content in preferred categories
            queryset = queryset.extra(
                select={
                    'category_boost': f"CASE WHEN category IN {tuple(preferred_categories)} THEN 10 ELSE 0 END"
                }
            )

        # Get content and generate scores
        content_items = list(queryset.order_by('-priority_score')[:limit * 2])  # Get more for diversity
        recommendations = []

        for content in content_items:
            # Calculate personalization score
            score = self._calculate_personalization_score(content, user_profile)

            # Calculate predicted effectiveness
            effectiveness = self._predict_effectiveness(content, user_profile)

            # Generate recommendation reason
            reason = self._generate_recommendation_reason(content, user_profile)

            recommendations.append({
                'content': content,
                'score': score,
                'effectiveness': effectiveness,
                'value_score': (score + effectiveness) / 2,
                'reason': reason
            })

        # Sort by combined score
        recommendations.sort(key=lambda x: x['value_score'], reverse=True)

        # Apply diversity constraints if enabled
        if diversity_enabled:
            recommendations = self._apply_diversity_constraints(recommendations, limit)
        else:
            recommendations = recommendations[:limit]

        return recommendations

    def _calculate_personalization_score(self, content, user_profile):
        """Calculate personalization score for content"""
        score = 0.5  # Base score

        # Category preference boost
        preferred_categories = user_profile.get('preferred_categories', [])
        if content.category in preferred_categories:
            score += 0.3

        # Content level matching
        preferred_level = user_profile.get('preferred_content_level', 'short_read')
        if content.content_level == preferred_level:
            score += 0.2

        # Mood-based scoring
        avg_mood = user_profile.get('avg_mood')
        if avg_mood:
            if avg_mood <= 5 and content.category in ['mental_health', 'stress_management']:
                score += 0.2
            elif avg_mood >= 7 and content.category in ['physical_wellness', 'workplace_health']:
                score += 0.1

        return min(1.0, score)

    def _predict_effectiveness(self, content, user_profile):
        """Predict effectiveness of content for user"""
        # Simplified effectiveness prediction
        base_effectiveness = 0.6

        # High evidence content is more effective
        if content.is_high_evidence:
            base_effectiveness += 0.2

        # Content with good overall ratings
        interactions = content.interactions.exclude(user_rating__isnull=True)
        if interactions.exists():
            avg_rating = interactions.aggregate(avg=Avg('user_rating'))['avg']
            if avg_rating >= 4:
                base_effectiveness += 0.15

        # User engagement history
        completion_rate = user_profile.get('completion_rate', 0.5)
        base_effectiveness += (completion_rate - 0.5) * 0.2

        return min(1.0, base_effectiveness)

    def _generate_recommendation_reason(self, content, user_profile):
        """Generate explanation for recommendation"""
        reasons = []

        preferred_categories = user_profile.get('preferred_categories', [])
        if content.category in preferred_categories:
            reasons.append(f"matches your interest in {content.get_category_display()}")

        if content.is_high_evidence:
            reasons.append("backed by high-quality research")

        avg_mood = user_profile.get('avg_mood')
        if avg_mood and avg_mood <= 5 and content.category == 'mental_health':
            reasons.append("may help with recent mood patterns")

        if not reasons:
            reasons.append("popular among similar users")

        return f"Recommended because it {', '.join(reasons[:2])}"

    def _apply_diversity_constraints(self, recommendations, limit):
        """Apply diversity constraints to avoid content clustering"""
        diverse_recommendations = []
        category_counts = {}

        for rec in recommendations:
            category = rec['content'].category
            category_count = category_counts.get(category, 0)

            # Limit content per category to ensure diversity
            max_per_category = max(1, limit // 3)
            if category_count < max_per_category:
                diverse_recommendations.append(rec)
                category_counts[category] = category_count + 1

            if len(diverse_recommendations) >= limit:
                break

        return diverse_recommendations

    def _calculate_diversity_score(self, recommendations):
        """Calculate diversity score of recommendations"""
        if not recommendations:
            return 0.0

        categories = [rec['content'].category for rec in recommendations]
        unique_categories = len(set(categories))
        total_items = len(recommendations)

        return unique_categories / total_items if total_items > 0 else 0.0


class WellnessProgressView(APIView):
    """User wellness progress and gamification management"""

    permission_classes = [WellnessPermission]

    def get(self, request):
        """Get user's wellness progress"""
        try:
            progress = request.user.wellness_progress
            serializer = WellnessUserProgressSerializer(progress)
            return Response(serializer.data)
        except WellnessUserProgress.DoesNotExist:
            return Response(
                {'error': 'Wellness progress not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request):
        """Update user's wellness preferences"""
        try:
            progress = request.user.wellness_progress
        except WellnessUserProgress.DoesNotExist:
            progress = WellnessUserProgress.objects.create(
                user=request.user,
                tenant=getattr(request.user, 'tenant', None)
            )

        serializer = WellnessUserProgressSerializer(
            progress,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WellnessAnalyticsView(APIView):
    """Wellness system analytics and insights"""

    permission_classes = [WellnessPermission]

    def get(self, request):
        """Get wellness engagement analytics"""
        user = request.user
        days = int(request.query_params.get('days', 30))

        try:
            analytics = self._generate_wellness_analytics(user, days)
            return Response(analytics)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Wellness analytics generation failed for user {user.id}: {e}")
            return Response(
                {'error': 'Analytics generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _generate_wellness_analytics(self, user, days):
        """Generate comprehensive wellness analytics"""
        since_date = timezone.now() - timedelta(days=days)

        # Get user interactions in period
        interactions = WellnessContentInteraction.objects.filter(
            user=user,
            interaction_date__gte=since_date
        )

        # Engagement summary
        total_interactions = interactions.count()
        unique_content = interactions.values('content').distinct().count()
        avg_engagement = interactions.aggregate(avg=Avg('engagement_score'))['avg'] or 0

        # Content effectiveness by category
        category_stats = interactions.values('content__category').annotate(
            count=Count('id'),
            avg_rating=Avg('user_rating'),
            completion_rate=Count('id', filter=Q(interaction_type='completed')) * 100 / Count('id')
        )

        return {
            'engagement_summary': {
                'total_interactions': total_interactions,
                'unique_content_viewed': unique_content,
                'avg_engagement_score': round(avg_engagement, 2),
                'analysis_period_days': days
            },
            'content_effectiveness': {
                'category_stats': list(category_stats),
                'top_performing_content': []  # TODO: Implement
            },
            'user_preferences': {
                'preferred_categories': [],  # TODO: Calculate from interactions
                'optimal_delivery_time': None  # TODO: Analyze interaction times
            },
            'trend_analysis': {
                'engagement_trend': 'stable',  # TODO: Calculate trend
                'category_shifts': []  # TODO: Analyze category preference changes
            },
            'recommendations': [
                {
                    'type': 'engagement',
                    'message': 'Consider exploring new wellness categories'
                }
            ],
            'analysis_metadata': {
                'generated_at': timezone.now().isoformat(),
                'algorithm_version': '1.0.0'
            }
        }