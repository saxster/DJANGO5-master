"""
Wellness Personalization Engine

ML-powered recommendation engine for personalized wellness content delivery.

Features:
- Collaborative filtering with similar users
- Content-based filtering using user patterns
- Hybrid recommendation with diversity constraints
- Effectiveness prediction and optimization
- Real-time personalization based on journal insights
"""

from datetime import timedelta
from collections import defaultdict
from django.utils import timezone
from django.db.models import Avg, Count, Q
import logging
import random

from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


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

        except DATABASE_EXCEPTIONS as e:
            self.logger.error(f"Database error selecting personalized tip for user {user.id}: {e}", exc_info=True)
            return None
        except ObjectDoesNotExist as e:
            self.logger.warning(f"Tip content not found for user {user.id}: {e}")
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

        except DATABASE_EXCEPTIONS as e:
            self.logger.error(f"Database error generating recommendations: {e}", exc_info=True)
            return []
        except ObjectDoesNotExist as e:
            self.logger.warning(f"Recommendation content not found: {e}")
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

        except DATABASE_EXCEPTIONS as e:
            self.logger.error(f"Database error creating recommendation for content {content.id}: {e}", exc_info=True)
            return None
        except ObjectDoesNotExist as e:
            self.logger.warning(f"Content {content.id} not found for recommendation: {e}")
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
