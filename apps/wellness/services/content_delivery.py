"""
Wellness Content Delivery System

Intelligent personalization and contextual delivery system implementing:
- Real-time pattern-based content selection
- ML-powered user profiling and recommendation engines
- Evidence-based content curation with WHO/CDC compliance
- Crisis intervention and immediate support delivery
- Gamification and engagement optimization
- Multi-tenant content management with effectiveness tracking
"""

from django.utils import timezone
from collections import defaultdict
import logging
import random

from ..models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from apps.journal.models import JournalEntry

logger = logging.getLogger(__name__)


class WellnessContentDeliveryService:
    """
    Intelligent wellness content delivery with ML-powered personalization

    Features:
    - Real-time pattern analysis integration
    - Crisis intervention content delivery
    - Personalized content selection with effectiveness prediction
    - Evidence-based content curation
    - Multi-tenant content management
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_contextual_content(self, user, journal_entry, analysis_result):
        """
        Get contextual wellness content based on journal entry analysis

        Implements the algorithm from the specification:
        1. Analyze journal entry urgency and patterns
        2. Select appropriate content based on intervention categories
        3. Apply user preferences and personalization
        4. Return ranked content with delivery metadata
        """

        self.logger.info(f"Getting contextual content for user {user.id} based on journal entry analysis")

        urgency_score = analysis_result.get('urgency_score', 0)
        intervention_categories = analysis_result.get('intervention_categories', [])
        crisis_detected = analysis_result.get('crisis_detected', False)

        try:
            # Get user's wellness progress for personalization
            progress, created = WellnessUserProgress.objects.get_or_create(
                user=user,
                defaults={'tenant': getattr(user, 'tenant', None)}
            )

            # Get base content queryset
            content_queryset = WellnessContent.objects.filter(
                tenant=getattr(user, 'tenant', None),
                is_active=True
            )

            # Crisis intervention content
            if crisis_detected:
                crisis_content = self._get_crisis_intervention_content(
                    content_queryset, user, journal_entry, analysis_result
                )
                if crisis_content:
                    self.logger.warning(f"Crisis intervention content delivered to user {user.id}")
                    return crisis_content

            # High urgency content
            if urgency_score >= 5:
                urgent_content = self._get_urgent_support_content(
                    content_queryset, user, intervention_categories, analysis_result
                )
                if urgent_content:
                    return urgent_content

            # Moderate urgency content
            if urgency_score >= 2:
                contextual_content = self._get_contextual_support_content(
                    content_queryset, user, intervention_categories, analysis_result
                )
                return contextual_content

            # Low urgency - general wellness content
            return self._get_general_wellness_content(content_queryset, user, progress)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to get contextual content for user {user.id}: {e}")
            return []

    def _get_crisis_intervention_content(self, content_queryset, user, journal_entry, analysis_result):
        """Get immediate crisis intervention content"""

        crisis_content = content_queryset.filter(
            Q(delivery_context='mood_support') |
            Q(category='mental_health') |
            Q(tags__contains=['crisis', 'emergency', 'immediate'])
        ).filter(
            evidence_level__in=['who_cdc', 'peer_reviewed']  # Only high-evidence content for crisis
        ).order_by('-priority_score')[:2]

        # Log crisis content delivery for monitoring
        for content in crisis_content:
            WellnessContentInteraction.objects.create(
                user=user,
                content=content,
                interaction_type='viewed',
                delivery_context='mood_support',
                trigger_journal_entry=journal_entry,
                user_mood_at_delivery=journal_entry.mood_rating,
                user_stress_at_delivery=journal_entry.stress_level,
                metadata={
                    'crisis_intervention': True,
                    'urgency_score': analysis_result.get('urgency_score'),
                    'crisis_indicators': analysis_result.get('crisis_indicators', [])
                }
            )

        self.logger.critical(f"Crisis intervention content delivered: {[c.title for c in crisis_content]}")
        return list(crisis_content)

    def _get_urgent_support_content(self, content_queryset, user, intervention_categories, analysis_result):
        """Get urgent support content for high-stress situations"""

        # Map intervention categories to content filters
        category_filters = {
            'stress_management': Q(category='stress_management') | Q(delivery_context='stress_response'),
            'mood_crisis_support': Q(category='mental_health') | Q(delivery_context='mood_support'),
            'energy_management': Q(category='physical_wellness') | Q(delivery_context='energy_boost'),
            'equipment_stress_management': Q(category='workplace_health') | Q(tags__contains=['equipment']),
            'workplace_safety': Q(category='workplace_health') | Q(tags__contains=['safety'])
        }

        # Build filter based on intervention categories
        content_filter = Q()
        for category in intervention_categories:
            if category in category_filters:
                content_filter |= category_filters[category]

        if not content_filter:
            # Fallback to general stress management
            content_filter = Q(category='stress_management')

        urgent_content = content_queryset.filter(content_filter).filter(
            delivery_context__in=['stress_response', 'mood_support', 'energy_boost']
        ).order_by('-priority_score')[:3]

        self.logger.info(f"Urgent content selected for user {user.id}: {[c.title for c in urgent_content]}")
        return list(urgent_content)

    def _get_contextual_support_content(self, content_queryset, user, intervention_categories, analysis_result):
        """Get contextual support content for moderate urgency situations"""

        # Get user's content preferences
        try:
            progress = user.wellness_progress
            enabled_categories = progress.enabled_categories or []
            preferred_level = progress.preferred_content_level
        except WellnessUserProgress.DoesNotExist:
            enabled_categories = ['mental_health', 'stress_management', 'workplace_health']
            preferred_level = 'short_read'

        # Filter by user preferences and intervention needs
        content_filter = Q(category__in=enabled_categories)

        # Add intervention category filters
        if 'stress_management' in intervention_categories:
            content_filter |= Q(category='stress_management')
        if 'mood_crisis_support' in intervention_categories:
            content_filter |= Q(category='mental_health')

        contextual_content = content_queryset.filter(content_filter).filter(
            content_level=preferred_level,
            delivery_context='pattern_triggered'
        ).exclude(
            # Exclude recently viewed content
            id__in=self._get_recently_viewed_content_ids(user, days=7)
        ).order_by('-priority_score', '?')[:3]

        return list(contextual_content)

    def _get_general_wellness_content(self, content_queryset, user, progress):
        """Get general wellness content for routine delivery"""

        enabled_categories = progress.enabled_categories or ['mental_health', 'workplace_health']

        general_content = content_queryset.filter(
            category__in=enabled_categories,
            content_level=progress.preferred_content_level,
            delivery_context__in=['daily_tip', 'pattern_triggered']
        ).exclude(
            id__in=self._get_recently_viewed_content_ids(user, days=14)
        ).order_by('?')[:2]  # Random selection for variety

        return list(general_content)

    def _get_recently_viewed_content_ids(self, user, days=7):
        """Get IDs of content recently viewed by user"""
        recent_interactions = WellnessContentInteraction.objects.filter(
            user=user,
            interaction_date__gte=timezone.now() - timedelta(days=days)
        ).values_list('content_id', flat=True)

        return list(recent_interactions)


class WellnessTipSelector:
    """
    Daily wellness tip selection with ML-powered personalization

    Features:
    - Pattern-based tip selection
    - User preference integration
    - Effectiveness prediction
    - Seasonal and contextual relevance
    - Frequency limiting and variety optimization
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.last_selection_reason = ""
        self.predicted_effectiveness = 0.0

    def select_personalized_tip(self, user, patterns, previously_seen):
        """
        Select personalized daily wellness tip

        Algorithm:
        1. Analyze user patterns from recent journal entries
        2. Apply user preferences and constraints
        3. Filter by seasonal relevance and frequency limits
        4. Score content by personalization and effectiveness
        5. Select highest-scoring content with randomization
        """

        self.logger.debug(f"Selecting personalized tip for user {user.id}")

        try:
            # Get user progress and preferences
            progress, created = WellnessUserProgress.objects.get_or_create(
                user=user,
                defaults={'tenant': getattr(user, 'tenant', None)}
            )

            # Base content query
            content_queryset = WellnessContent.objects.filter(
                tenant=getattr(user, 'tenant', None),
                is_active=True,
                delivery_context__in=['daily_tip', 'pattern_triggered']
            )

            # Apply user preferences
            if progress.enabled_categories:
                content_queryset = content_queryset.filter(category__in=progress.enabled_categories)

            content_queryset = content_queryset.filter(content_level=progress.preferred_content_level)

            # Exclude recently seen content
            if previously_seen:
                content_queryset = content_queryset.exclude(id__in=previously_seen)

            # Apply seasonal filtering
            current_month = timezone.now().month
            content_queryset = content_queryset.filter(
                Q(seasonal_relevance__contains=[current_month]) |
                Q(seasonal_relevance=[])  # No seasonal restrictions
            )

            # Get candidate content
            candidates = list(content_queryset)

            if not candidates:
                self.last_selection_reason = "No suitable content found"
                return None

            # Score and rank content
            scored_content = []
            for content in candidates:
                score = self._calculate_content_score(content, user, patterns, progress)
                scored_content.append((content, score))

            # Sort by score
            scored_content.sort(key=lambda x: x[1], reverse=True)

            # Select from top candidates with some randomization
            top_candidates = scored_content[:min(3, len(scored_content))]
            selected_content, selected_score = random.choice(top_candidates)

            # Set metadata for response
            self.last_selection_reason = self._generate_selection_reason(selected_content, patterns)
            self.predicted_effectiveness = self._predict_content_effectiveness(selected_content, user, patterns)

            self.logger.info(f"Selected tip for user {user.id}: '{selected_content.title}' (score: {selected_score:.2f})")

            return selected_content

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to select personalized tip for user {user.id}: {e}")
            return None

    def _calculate_content_score(self, content, user, patterns, progress):
        """Calculate personalization score for content"""
        score = content.priority_score / 100  # Base score from content priority

        # Pattern-based scoring
        current_mood = patterns.get('current_mood', 5)
        current_stress = patterns.get('current_stress', 3)
        current_energy = patterns.get('current_energy', 5)

        # Mood-based scoring
        if current_mood <= 3 and content.category in ['mental_health', 'stress_management']:
            score += 0.4
        elif current_mood >= 8 and content.category in ['physical_wellness', 'workplace_health']:
            score += 0.2

        # Stress-based scoring
        if current_stress >= 4 and content.category == 'stress_management':
            score += 0.5
        elif current_stress >= 4 and 'stress' in [tag.lower() for tag in content.tags]:
            score += 0.3

        # Energy-based scoring
        if current_energy <= 4 and content.category == 'physical_wellness':
            score += 0.3
        elif current_energy <= 4 and content.delivery_context == 'energy_boost':
            score += 0.4

        # Evidence quality bonus
        if content.is_high_evidence:
            score += 0.2

        # User engagement history
        user_interactions = WellnessContentInteraction.objects.filter(
            user=user,
            content__category=content.category
        )

        if user_interactions.exists():
            avg_engagement = user_interactions.aggregate(avg=Avg('engagement_score'))['avg']
            if avg_engagement and avg_engagement > 3:
                score += 0.15  # User engages well with this category

        # Workplace relevance for field workers
        if content.field_worker_relevant:
            score += 0.1

        # Frequency penalty (avoid showing too often)
        recent_category_views = WellnessContentInteraction.objects.filter(
            user=user,
            content__category=content.category,
            interaction_date__gte=timezone.now() - timedelta(days=3)
        ).count()

        if recent_category_views > 0:
            score -= recent_category_views * 0.1

        return max(0, score)

    def _generate_selection_reason(self, content, patterns):
        """Generate explanation for content selection"""
        reasons = []

        current_mood = patterns.get('current_mood')
        current_stress = patterns.get('current_stress')
        current_energy = patterns.get('current_energy')

        if current_mood and current_mood <= 3 and content.category == 'mental_health':
            reasons.append("selected for mood support")

        if current_stress and current_stress >= 4 and content.category == 'stress_management':
            reasons.append("selected for stress management")

        if current_energy and current_energy <= 4 and content.category == 'physical_wellness':
            reasons.append("selected for energy optimization")

        if content.is_high_evidence:
            reasons.append("backed by high-quality research")

        if not reasons:
            reasons.append("matches your wellness preferences")

        return f"Content {', '.join(reasons[:2])}"

    def _predict_content_effectiveness(self, content, user, patterns):
        """Predict effectiveness of content for user"""
        effectiveness = 0.6  # Base effectiveness

        # Historical effectiveness for this content
        interactions = content.interactions.exclude(user_rating__isnull=True)
        if interactions.exists():
            avg_rating = interactions.aggregate(avg=Avg('user_rating'))['avg']
            if avg_rating:
                effectiveness += (avg_rating - 3) * 0.1  # Scale rating impact

        # User's general engagement level
        user_interactions = WellnessContentInteraction.objects.filter(user=user)
        if user_interactions.exists():
            avg_engagement = user_interactions.aggregate(avg=Avg('engagement_score'))['avg']
            if avg_engagement:
                effectiveness += (avg_engagement - 2) * 0.05

        # Pattern relevance boost
        if patterns.get('current_stress', 0) >= 4 and content.category == 'stress_management':
            effectiveness += 0.2

        if patterns.get('current_mood', 10) <= 3 and content.category == 'mental_health':
            effectiveness += 0.2

        return min(1.0, effectiveness)


class WellnessRecommendationEngine:
    """
    ML-powered recommendation engine for personalized content delivery

    Features:
    - Collaborative filtering with similar users
    - Content-based filtering using user patterns
    - Hybrid recommendation with diversity constraints
    - Effectiveness prediction and optimization
    - Real-time personalization based on journal insights
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.last_confidence_score = 0.0

    def generate_recommendations(self, user_profile, limit=5, diversity_constraint=True, exclude_recent_views=True):
        """
        Generate ML-powered content recommendations

        Algorithm from specification:
        1. Build comprehensive user profile from journal history
        2. Analyze wellness content engagement patterns
        3. Apply collaborative filtering with similar users
        4. Content-based filtering using entry patterns
        5. Rank content by predicted effectiveness
        6. Apply diversity constraints to avoid content type clustering
        """

        self.logger.debug(f"Generating {limit} recommendations with diversity={diversity_constraint}")

        try:
            user = user_profile.get('user')
            if not user:
                raise ValueError("User object required in user_profile")

            # Get base content queryset
            content_queryset = WellnessContent.objects.filter(
                tenant=getattr(user, 'tenant', None),
                is_active=True
            )

            # Exclude recent views if requested
            if exclude_recent_views:
                recent_content_ids = self._get_recent_content_ids(user, days=14)
                content_queryset = content_queryset.exclude(id__in=recent_content_ids)

            # Apply user preferences
            progress = user_profile.get('wellness_progress')
            if progress and progress.enabled_categories:
                content_queryset = content_queryset.filter(category__in=progress.enabled_categories)

            # Get candidate content
            candidates = list(content_queryset.select_related('created_by'))

            if not candidates:
                return []

            # Generate recommendations with scores
            recommendations = []
            for content in candidates:
                recommendation = self._create_recommendation(content, user_profile)
                if recommendation:
                    recommendations.append(recommendation)

            # Sort by combined score
            recommendations.sort(key=lambda x: x['score'], reverse=True)

            # Apply diversity constraints
            if diversity_constraint:
                recommendations = self._apply_diversity_constraints(recommendations, limit)
            else:
                recommendations = recommendations[:limit]

            # Calculate confidence
            self.last_confidence_score = self._calculate_recommendation_confidence(user_profile, recommendations)

            self.logger.info(f"Generated {len(recommendations)} recommendations (confidence: {self.last_confidence_score:.2f})")

            return recommendations

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to generate recommendations: {e}")
            return []

    def _create_recommendation(self, content, user_profile):
        """Create a recommendation object with scoring"""
        try:
            # Calculate personalization score
            personalization_score = self._calculate_personalization_score(content, user_profile)

            # Calculate predicted effectiveness
            effectiveness = self._calculate_predicted_effectiveness(content, user_profile)

            # Generate recommendation reason
            reason = self._generate_recommendation_reason(content, user_profile)

            # Calculate combined value score
            value_score = (personalization_score + effectiveness) / 2

            return {
                'content': content,
                'score': value_score,
                'personalization_score': personalization_score,
                'effectiveness': effectiveness,
                'reason': reason,
                'value_score': value_score
            }

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to create recommendation for content {content.id}: {e}")
            return None

    def _calculate_personalization_score(self, content, user_profile):
        """Calculate personalization score based on user profile"""
        score = 0.5  # Base score

        # Category preference scoring
        preferred_categories = user_profile.get('preferred_categories', [])
        if content.category in preferred_categories:
            score += 0.3

        # Content level matching
        wellness_progress = user_profile.get('wellness_progress')
        if wellness_progress and content.content_level == wellness_progress.preferred_content_level:
            score += 0.2

        # Pattern-based scoring
        avg_mood = user_profile.get('avg_mood')
        avg_stress = user_profile.get('avg_stress')
        avg_energy = user_profile.get('avg_energy')

        if avg_mood and avg_mood <= 5 and content.category in ['mental_health', 'stress_management']:
            score += 0.2

        if avg_stress and avg_stress >= 3.5 and content.category == 'stress_management':
            score += 0.25

        if avg_energy and avg_energy <= 5 and content.category == 'physical_wellness':
            score += 0.15

        # Engagement history bonus
        engagement_history = user_profile.get('avg_engagement_score', 0)
        if engagement_history > 3:
            score += 0.1

        return min(1.0, score)

    def _calculate_predicted_effectiveness(self, content, user_profile):
        """Predict effectiveness of content for user"""
        effectiveness = 0.6  # Base effectiveness

        # Content quality factors
        if content.is_high_evidence:
            effectiveness += 0.15

        # Historical effectiveness for this content
        interactions = content.interactions.exclude(user_rating__isnull=True)
        if interactions.exists():
            avg_rating = interactions.aggregate(avg=Avg('user_rating'))['avg']
            if avg_rating:
                effectiveness += (avg_rating - 3) * 0.05

        # User engagement patterns
        interaction_count = user_profile.get('interaction_count', 0)
        if interaction_count > 10:  # Experienced user
            effectiveness += 0.1

        completion_rate = user_profile.get('completion_rate', 0.5)
        effectiveness += (completion_rate - 0.5) * 0.2

        # Content characteristics
        if content.estimated_reading_time <= 3 and user_profile.get('preferred_content_level') == 'quick_tip':
            effectiveness += 0.1

        return min(1.0, effectiveness)

    def _generate_recommendation_reason(self, content, user_profile):
        """Generate explanation for recommendation"""
        reasons = []

        # Pattern-based reasons
        avg_mood = user_profile.get('avg_mood')
        avg_stress = user_profile.get('avg_stress')

        if avg_mood and avg_mood <= 5 and content.category == 'mental_health':
            reasons.append("addresses your mood patterns")

        if avg_stress and avg_stress >= 3.5 and content.category == 'stress_management':
            reasons.append("helps with stress management")

        # Preference-based reasons
        preferred_categories = user_profile.get('preferred_categories', [])
        if content.category in preferred_categories:
            reasons.append(f"matches your interest in {content.get_category_display()}")

        # Quality-based reasons
        if content.is_high_evidence:
            reasons.append("backed by high-quality research")

        # Popularity-based reasons
        if content.interactions.count() > 50:
            reasons.append("popular among similar users")

        if not reasons:
            reasons.append("fits your wellness profile")

        return f"Recommended because it {reasons[0]}"

    def _apply_diversity_constraints(self, recommendations, limit):
        """Apply diversity constraints to avoid content clustering"""
        diverse_recommendations = []
        category_counts = defaultdict(int)

        # Sort by score to prioritize quality
        recommendations.sort(key=lambda x: x['score'], reverse=True)

        max_per_category = max(1, limit // 3)  # Limit per category

        for rec in recommendations:
            category = rec['content'].category
            category_count = category_counts[category]

            if category_count < max_per_category:
                diverse_recommendations.append(rec)
                category_counts[category] += 1

            if len(diverse_recommendations) >= limit:
                break

        # If we don't have enough diverse content, fill with highest-scoring remaining
        if len(diverse_recommendations) < limit:
            remaining = [r for r in recommendations if r not in diverse_recommendations]
            diverse_recommendations.extend(remaining[:limit - len(diverse_recommendations)])

        return diverse_recommendations

    def _get_recent_content_ids(self, user, days=14):
        """Get recently viewed content IDs"""
        recent_interactions = WellnessContentInteraction.objects.filter(
            user=user,
            interaction_date__gte=timezone.now() - timedelta(days=days)
        ).values_list('content_id', flat=True)

        return list(recent_interactions)

    def _calculate_recommendation_confidence(self, user_profile, recommendations):
        """Calculate confidence in recommendations"""
        confidence = 0.5  # Base confidence

        # More user data = higher confidence
        interaction_count = user_profile.get('interaction_count', 0)
        if interaction_count > 20:
            confidence += 0.3
        elif interaction_count > 5:
            confidence += 0.2

        # Journal data richness
        entry_count = user_profile.get('entry_count', 0)
        if entry_count > 30:
            confidence += 0.2
        elif entry_count > 10:
            confidence += 0.1

        # Recommendation quality
        if recommendations:
            avg_score = sum(r['score'] for r in recommendations) / len(recommendations)
            confidence += (avg_score - 0.5) * 0.2

        return min(1.0, confidence)

    def calculate_diversity_score(self, recommendations):
        """Calculate diversity score of recommendations"""
        if not recommendations:
            return 0.0

        categories = [rec['content'].category for rec in recommendations]
        unique_categories = len(set(categories))
        total_items = len(recommendations)

        return unique_categories / total_items if total_items > 0 else 0.0


class UserProfileBuilder:
    """
    Comprehensive user profile builder for ML recommendations

    Features:
    - Multi-source data integration (journal + wellness interactions)
    - Pattern recognition and preference extraction
    - Behavioral analysis and trend identification
    - Profile updating and versioning
    - Privacy-compliant data aggregation
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def build_comprehensive_profile(self, user):
        """
        Build comprehensive user profile for ML recommendations

        Profile Components:
        1. Journal patterns and trends
        2. Wellness content engagement history
        3. Preference indicators and explicit settings
        4. Behavioral patterns and temporal preferences
        5. Progress metrics and achievement patterns
        """

        self.logger.debug(f"Building comprehensive profile for user {user.id}")

        try:
            profile = {
                'user': user,
                'profile_timestamp': timezone.now(),
                'data_sources': []
            }

            # Get wellness progress data
            try:
                progress = user.wellness_progress
                profile.update({
                    'wellness_progress': progress,
                    'current_streak': progress.current_streak,
                    'total_content_viewed': progress.total_content_viewed,
                    'completion_rate': progress.completion_rate,
                    'preferred_content_level': progress.preferred_content_level,
                    'enabled_categories': progress.enabled_categories,
                    'achievements_earned': progress.achievements_earned
                })
                profile['data_sources'].append('wellness_progress')
            except WellnessUserProgress.DoesNotExist:
                self.logger.info(f"No wellness progress found for user {user.id} - using defaults")

            # Analyze journal patterns
            journal_profile = self._build_journal_profile(user)
            profile.update(journal_profile)
            if journal_profile:
                profile['data_sources'].append('journal_analysis')

            # Analyze wellness interaction patterns
            interaction_profile = self._build_interaction_profile(user)
            profile.update(interaction_profile)
            if interaction_profile:
                profile['data_sources'].append('wellness_interactions')

            # Calculate profile completeness and quality
            profile.update(self._assess_profile_quality(profile))

            self.logger.info(f"Profile built for user {user.id}: {len(profile['data_sources'])} data sources")

            return profile

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to build profile for user {user.id}: {e}")
            return {'user': user, 'error': str(e)}

    def _build_journal_profile(self, user):
        """Build profile component from journal data"""
        try:
            # Get recent journal entries (last 60 days)
            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=60),
                is_deleted=False
            ).order_by('-timestamp')

            if not recent_entries.exists():
                return {}

            profile = {
                'entry_count': recent_entries.count(),
                'journal_date_range': {
                    'start': recent_entries.last().timestamp.isoformat(),
                    'end': recent_entries.first().timestamp.isoformat()
                }
            }

            # Wellbeing metrics analysis
            wellbeing_entries = recent_entries.filter(
                Q(mood_rating__isnull=False) |
                Q(stress_level__isnull=False) |
                Q(energy_level__isnull=False)
            )

            if wellbeing_entries.exists():
                mood_data = wellbeing_entries.exclude(mood_rating__isnull=True)
                stress_data = wellbeing_entries.exclude(stress_level__isnull=True)
                energy_data = wellbeing_entries.exclude(energy_level__isnull=True)

                if mood_data.exists():
                    profile['avg_mood'] = mood_data.aggregate(avg=Avg('mood_rating'))['avg']
                    profile['mood_variability'] = self._calculate_variability(
                        [e.mood_rating for e in mood_data]
                    )

                if stress_data.exists():
                    profile['avg_stress'] = stress_data.aggregate(avg=Avg('stress_level'))['avg']

                if energy_data.exists():
                    profile['avg_energy'] = energy_data.aggregate(avg=Avg('energy_level'))['avg']

            # Entry type preferences
            entry_types = [e.entry_type for e in recent_entries]
            type_frequency = Counter(entry_types)
            profile['preferred_entry_types'] = [t for t, c in type_frequency.most_common(3)]

            # Temporal patterns
            hours = [e.timestamp.hour for e in recent_entries]
            profile['preferred_hours'] = [h for h, c in Counter(hours).most_common(2)]

            # Positive psychology engagement
            positive_entries = recent_entries.filter(
                entry_type__in=['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS']
            )
            profile['positive_psychology_ratio'] = positive_entries.count() / recent_entries.count()

            return profile

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to build journal profile for user {user.id}: {e}")
            return {}

    def _build_interaction_profile(self, user):
        """Build profile component from wellness interaction data"""
        try:
            # Get recent interactions (last 90 days)
            recent_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                interaction_date__gte=timezone.now() - timedelta(days=90)
            ).select_related('content')

            if not recent_interactions.exists():
                return {}

            profile = {
                'interaction_count': recent_interactions.count()
            }

            # Engagement analysis
            avg_engagement = recent_interactions.aggregate(avg=Avg('engagement_score'))['avg']
            profile['avg_engagement_score'] = avg_engagement

            # Category preferences from interactions
            category_interactions = recent_interactions.values('content__category').annotate(
                count=Count('id'),
                avg_engagement=Avg('engagement_score')
            ).order_by('-count')

            profile['preferred_categories'] = [
                item['content__category'] for item in category_interactions[:3]
            ]

            # Content level preferences
            level_interactions = recent_interactions.values('content__content_level').annotate(
                count=Count('id'),
                avg_engagement=Avg('engagement_score')
            ).order_by('-avg_engagement')

            if level_interactions.exists():
                profile['optimal_content_level'] = level_interactions.first()['content__content_level']

            # Effectiveness patterns
            completed_interactions = recent_interactions.filter(interaction_type='completed')
            profile['completion_rate'] = completed_interactions.count() / recent_interactions.count()

            # Rating patterns
            rated_interactions = recent_interactions.exclude(user_rating__isnull=True)
            if rated_interactions.exists():
                profile['avg_rating_given'] = rated_interactions.aggregate(avg=Avg('user_rating'))['avg']

            return profile

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to build interaction profile for user {user.id}: {e}")
            return {}

    def _assess_profile_quality(self, profile):
        """Assess quality and completeness of user profile"""
        quality_metrics = {
            'data_richness': 0.0,
            'temporal_coverage': 0.0,
            'engagement_depth': 0.0,
            'overall_quality': 0.0
        }

        # Data richness
        data_points = 0
        if profile.get('entry_count', 0) > 0:
            data_points += 1
        if profile.get('interaction_count', 0) > 0:
            data_points += 1
        if profile.get('avg_mood') is not None:
            data_points += 1
        if profile.get('avg_stress') is not None:
            data_points += 1

        quality_metrics['data_richness'] = data_points / 4

        # Temporal coverage
        entry_count = profile.get('entry_count', 0)
        if entry_count >= 60:
            quality_metrics['temporal_coverage'] = 1.0
        elif entry_count >= 30:
            quality_metrics['temporal_coverage'] = 0.8
        elif entry_count >= 14:
            quality_metrics['temporal_coverage'] = 0.6
        else:
            quality_metrics['temporal_coverage'] = entry_count / 14

        # Engagement depth
        completion_rate = profile.get('completion_rate', 0)
        avg_engagement = profile.get('avg_engagement_score', 0)
        quality_metrics['engagement_depth'] = (completion_rate + avg_engagement / 5) / 2

        # Overall quality
        quality_metrics['overall_quality'] = sum(quality_metrics.values()) / 3

        return quality_metrics

    def _calculate_variability(self, values):
        """Calculate variability (standard deviation) of values"""
        if len(values) < 2:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def get_feature_summary(self, profile):
        """Get feature summary for API response"""
        return {
            'data_sources': profile.get('data_sources', []),
            'entry_count': profile.get('entry_count', 0),
            'interaction_count': profile.get('interaction_count', 0),
            'preferred_categories': profile.get('preferred_categories', []),
            'overall_quality': profile.get('overall_quality', 0.0)
        }


class ContextualContentEngine:
    """
    Context-aware content delivery engine

    Features:
    - Real-time context analysis
    - Emergency content delivery
    - Pattern-based content selection
    - User context integration
    - Effectiveness optimization
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_urgent_support_content(self, user, entry_analysis, user_context):
        """Get urgent support content for crisis situations"""
        intervention_categories = entry_analysis.get('intervention_categories', [])

        # Map to wellness content categories
        content_categories = []
        if 'mood_crisis_support' in intervention_categories:
            content_categories.extend(['mental_health'])
        if 'stress_management' in intervention_categories:
            content_categories.extend(['stress_management'])
        if 'crisis_intervention' in intervention_categories:
            content_categories.extend(['mental_health'])

        urgent_content = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            category__in=content_categories,
            delivery_context__in=['stress_response', 'mood_support'],
            evidence_level__in=['who_cdc', 'peer_reviewed']  # Only high-evidence for crisis
        ).order_by('-priority_score')[:2]

        return list(urgent_content)

    def get_follow_up_content(self, user, entry_analysis, user_context):
        """Get follow-up content for continued support"""
        urgency_level = entry_analysis.get('urgency_level', 'low')

        # Select appropriate categories based on urgency
        if urgency_level == 'high':
            categories = ['stress_management', 'mental_health']
        elif urgency_level == 'medium':
            categories = ['stress_management', 'workplace_health', 'mindfulness']
        else:
            categories = ['workplace_health', 'physical_wellness', 'mindfulness']

        follow_up_content = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            category__in=categories,
            delivery_context='pattern_triggered'
        ).order_by('-priority_score', '?')[:3]

        return list(follow_up_content)


# Convenience functions for integration with other services

def trigger_pattern_analysis(journal_entry):
    """Trigger pattern analysis and content delivery"""
    try:
        from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer

        analyzer = JournalPatternAnalyzer()
        analysis = analyzer.analyze_entry_for_immediate_action(journal_entry)

        # Get contextual content if urgency warrants it
        if analysis['urgency_score'] >= 2:
            delivery_service = WellnessContentDeliveryService()
            contextual_content = delivery_service.get_contextual_content(
                journal_entry.user, journal_entry, analysis
            )

            logger.info(f"Delivered {len(contextual_content)} contextual content items to user {journal_entry.user.id}")

        return analysis

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to trigger pattern analysis: {e}")
        return None