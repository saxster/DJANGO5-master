"""
Recommendation Scoring Service - Calculate scores and effectiveness for content recommendations

Responsible for:
- Calculating personalization scores based on user preferences
- Predicting content effectiveness for users
- Generating recommendation explanations
- Applying diversity constraints to recommendations
- Calculating diversity metrics
"""

from django.db.models import Avg

from apps.wellness.logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class RecommendationScoringService:
    """Service for scoring and ranking content recommendations"""

    @staticmethod
    def calculate_personalization_score(content, user_profile):
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

    @staticmethod
    def predict_effectiveness(content, user_profile):
        """Predict effectiveness of content for user"""
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

    @staticmethod
    def generate_recommendation_reason(content, user_profile):
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

    @staticmethod
    def apply_diversity_constraints(recommendations, limit):
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

    @staticmethod
    def calculate_diversity_score(recommendations):
        """Calculate diversity score of recommendations"""
        if not recommendations:
            return 0.0

        categories = [rec['content'].category for rec in recommendations]
        unique_categories = len(set(categories))
        total_items = len(recommendations)

        return unique_categories / total_items if total_items > 0 else 0.0
