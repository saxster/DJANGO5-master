"""
Factory classes for recommendation system testing
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
import random
import json
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta

from apps.core.models.recommendation import (
    UserBehaviorProfile, NavigationRecommendation, ContentRecommendation,
    UserSimilarity, RecommendationFeedback, RecommendationImplementation
)

fake = Faker()
User = get_user_model()


class UserBehaviorProfileFactory(DjangoModelFactory):
    """Factory for creating user behavior profiles"""
    class Meta:
        model = UserBehaviorProfile
    
    user = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    preferred_pages = factory.LazyFunction(
        lambda: {
            '/dashboard/': 45,
            '/assets/': 28,
            '/reports/': 15,
            '/settings/': 8,
            '/help/': 4
        }
    )
    common_paths = factory.LazyFunction(
        lambda: [
            ['/dashboard/', '/assets/', '/assets/detail/'],
            ['/dashboard/', '/reports/', '/reports/monthly/'],
            ['/dashboard/', '/settings/', '/settings/profile/']
        ]
    )
    session_duration_avg = factory.Faker('random_int', min=60, max=1800)  # 1-30 minutes
    click_patterns = factory.LazyFunction(
        lambda: {
            'top_left': 12,
            'center': 45,
            'bottom_right': 8,
            'navigation': 25,
            'buttons': 35
        }
    )
    preferred_device_type = factory.Faker('random_element', elements=['desktop', 'mobile', 'tablet'])
    timezone_preference = factory.Faker('timezone')
    language_preference = factory.Faker('language_code')
    exploration_tendency = factory.Faker('pyfloat', left_digits=0, right_digits=2, positive=True, min_value=0.0, max_value=1.0)
    task_completion_rate = factory.Faker('pyfloat', left_digits=0, right_digits=2, positive=True, min_value=0.0, max_value=1.0)
    feature_adoption_rate = factory.Faker('pyfloat', left_digits=0, right_digits=2, positive=True, min_value=0.0, max_value=1.0)
    preferred_content_types = factory.LazyFunction(
        lambda: random.sample(['dashboard', 'report', 'form', 'list', 'detail'], k=random.randint(2, 4))
    )
    interaction_frequency = factory.LazyFunction(
        lambda: {
            'clicks_per_session': random.randint(5, 50),
            'pages_per_session': random.randint(3, 15),
            'session_frequency': random.randint(1, 10)
        }
    )
    similarity_vector = factory.LazyFunction(
        lambda: [round(random.uniform(0, 1), 3) for _ in range(10)]
    )


class NavigationRecommendationFactory(DjangoModelFactory):
    """Factory for creating navigation recommendations"""
    class Meta:
        model = NavigationRecommendation
    
    recommendation_type = factory.Faker('random_element', elements=[
        'page_suggestion', 'menu_optimization', 'search_enhancement', 
        'layout_improvement', 'content_personalization'
    ])
    title = factory.Faker('sentence', nb_words=6)
    description = factory.Faker('text', max_nb_chars=200)
    target_page = factory.Faker('uri_path')
    target_element = factory.Faker('random_element', elements=[
        'main-menu', 'sidebar-nav', 'breadcrumb', 'search-box', 'user-menu'
    ])
    target_user_segment = factory.LazyFunction(
        lambda: {
            'device_types': random.sample(['desktop', 'mobile', 'tablet'], k=random.randint(1, 3)),
            'experience_levels': random.sample(['new', 'intermediate', 'expert'], k=random.randint(1, 2)),
            'usage_patterns': random.sample(['daily', 'weekly', 'occasional'], k=random.randint(1, 2))
        }
    )
    suggested_action = factory.Faker('text', max_nb_chars=300)
    implementation_details = factory.LazyFunction(
        lambda: {
            'css_changes': factory.Faker('text', max_nb_chars=100).generate(),
            'html_changes': factory.Faker('text', max_nb_chars=100).generate(),
            'js_changes': factory.Faker('text', max_nb_chars=100).generate(),
            'estimated_effort': random.choice(['low', 'medium', 'high'])
        }
    )
    expected_impact = factory.Faker('text', max_nb_chars=250)
    confidence_score = factory.Faker('pyfloat', left_digits=0, right_digits=2, positive=True, min_value=0.0, max_value=1.0)
    supporting_data = factory.LazyFunction(
        lambda: {
            'user_sessions_analyzed': random.randint(100, 1000),
            'conversion_impact': f"{random.randint(5, 25)}%",
            'data_sources': random.sample(['heatmap', 'a_b_test', 'user_feedback', 'analytics'], k=random.randint(2, 4))
        }
    )
    user_behavior_data = factory.LazyFunction(
        lambda: {
            'common_exit_points': ['/page1/', '/page2/', '/page3/'],
            'time_spent_sections': {'header': 15, 'content': 120, 'footer': 8},
            'interaction_patterns': {'clicks': 45, 'scrolls': 28, 'hovers': 12}
        }
    )
    priority = factory.Faker('random_element', elements=['low', 'medium', 'high', 'critical'])
    status = factory.Faker('random_element', elements=['pending', 'approved', 'implemented', 'rejected'])
    created_by = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    valid_until = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=random.randint(30, 90))
    )


class ContentRecommendationFactory(DjangoModelFactory):
    """Factory for creating content recommendations"""
    class Meta:
        model = ContentRecommendation
    
    user = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    content_type = factory.Faker('random_element', elements=['page', 'feature', 'tool', 'report', 'dashboard'])
    content_title = factory.Faker('sentence', nb_words=4)
    content_url = factory.Faker('uri_path')
    content_description = factory.Faker('text', max_nb_chars=200)
    reason = factory.Faker('text', max_nb_chars=150)
    relevance_score = factory.Faker('pyfloat', left_digits=0, right_digits=2, positive=True, min_value=0.0, max_value=1.0)
    recommendation_algorithm = factory.Faker('random_element', elements=[
        'collaborative_filtering', 'content_based', 'hybrid', 'popularity_based', 'behavioral'
    ])
    recommended_context = factory.LazyFunction(
        lambda: {
            'page_types': random.sample(['dashboard', 'list', 'detail', 'form'], k=random.randint(1, 3)),
            'user_actions': random.sample(['login', 'search', 'create', 'view'], k=random.randint(1, 2)),
            'time_of_day': random.sample(['morning', 'afternoon', 'evening'], k=random.randint(1, 2))
        }
    )
    display_conditions = factory.LazyFunction(
        lambda: {
            'min_session_duration': random.randint(30, 300),
            'required_permissions': random.sample(['read', 'write', 'admin'], k=random.randint(1, 2)),
            'exclude_pages': ['/admin/', '/api/']
        }
    )
    shown_count = factory.Faker('random_int', min=0, max=50)
    clicked_count = factory.Faker('random_int', min=0, max=10)
    dismissed_count = factory.Faker('random_int', min=0, max=5)
    last_shown = factory.LazyFunction(
        lambda: timezone.now() - timedelta(hours=random.randint(1, 72))
    )
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=random.randint(7, 30))
    )
    is_active = True


class UserSimilarityFactory(DjangoModelFactory):
    """Factory for creating user similarity records"""
    class Meta:
        model = UserSimilarity
    
    user1 = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    user2 = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    similarity_score = factory.Faker('pyfloat', left_digits=0, right_digits=3, positive=False, min_value=-1.0, max_value=1.0)
    calculation_method = factory.Faker('random_element', elements=[
        'cosine_similarity', 'pearson_correlation', 'jaccard_similarity', 'euclidean_distance'
    ])
    features_used = factory.LazyFunction(
        lambda: random.sample([
            'page_preferences', 'device_type', 'session_duration', 'click_patterns', 
            'navigation_paths', 'content_types', 'interaction_frequency'
        ], k=random.randint(3, 6))
    )


class RecommendationFeedbackFactory(DjangoModelFactory):
    """Factory for creating recommendation feedback"""
    class Meta:
        model = RecommendationFeedback
    
    user = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(ContentRecommendation)
    )
    object_id = factory.SelfAttribute('recommendation.id')
    recommendation = factory.SubFactory(ContentRecommendationFactory)
    feedback_type = factory.Faker('random_element', elements=['helpful', 'not_helpful', 'implemented', 'irrelevant'])
    rating = factory.Faker('random_int', min=1, max=5)
    comments = factory.Faker('text', max_nb_chars=300)


class RecommendationImplementationFactory(DjangoModelFactory):
    """Factory for creating recommendation implementations"""
    class Meta:
        model = RecommendationImplementation
    
    recommendation = factory.SubFactory(NavigationRecommendationFactory)
    implemented_by = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    implementation_notes = factory.Faker('text', max_nb_chars=500)
    implementation_method = factory.Faker('random_element', elements=[
        'css_update', 'template_change', 'javascript_modification', 'backend_logic', 'database_update'
    ])
    before_metrics = factory.LazyFunction(
        lambda: {
            'conversion_rate': round(random.uniform(0.05, 0.15), 3),
            'bounce_rate': round(random.uniform(0.3, 0.7), 3),
            'avg_session_duration': random.randint(120, 600),
            'pages_per_session': round(random.uniform(2.0, 8.0), 1)
        }
    )
    after_metrics = factory.LazyFunction(
        lambda: {
            'conversion_rate': round(random.uniform(0.08, 0.20), 3),
            'bounce_rate': round(random.uniform(0.2, 0.6), 3),
            'avg_session_duration': random.randint(150, 800),
            'pages_per_session': round(random.uniform(2.5, 10.0), 1)
        }
    )
    success_metrics = factory.LazyFunction(
        lambda: {
            'improvement_percentage': round(random.uniform(5.0, 30.0), 1),
            'statistical_significance': random.choice([True, False]),
            'user_satisfaction': round(random.uniform(3.5, 5.0), 1),
            'implementation_cost': random.choice(['low', 'medium', 'high'])
        }
    )
    is_successful = factory.LazyFunction(lambda: random.choice([True, False, None]))
    effectiveness_score = factory.Faker('pyfloat', left_digits=0, right_digits=2, positive=True, min_value=0.0, max_value=1.0)


# Utility functions for creating test data

def create_complete_user_profile(user=None, **kwargs):
    """Create a complete user behavior profile with realistic data"""
    if user is None:
        from tests.factories.heatmap_factories import UserFactory
        user = UserFactory()
    
    profile = UserBehaviorProfileFactory(user=user, **kwargs)
    
    # Create some similar users
    for _ in range(3):
        similar_user = UserFactory()
        similar_profile = UserBehaviorProfileFactory(user=similar_user)
        UserSimilarityFactory(
            user1=user,
            user2=similar_user,
            similarity_score=random.uniform(0.3, 0.9)
        )
    
    # Create some content recommendations
    for _ in range(5):
        ContentRecommendationFactory(user=user)
    
    return profile


def create_recommendation_with_feedback(user=None, **kwargs):
    """Create a content recommendation with associated feedback"""
    if user is None:
        from tests.factories.heatmap_factories import UserFactory
        user = UserFactory()
    
    recommendation = ContentRecommendationFactory(user=user, **kwargs)
    
    # Add some feedback
    RecommendationFeedbackFactory(
        user=user,
        recommendation=recommendation,
        content_type=ContentType.objects.get_for_model(ContentRecommendation),
        object_id=recommendation.id
    )
    
    return recommendation


def create_navigation_recommendation_with_implementation(**kwargs):
    """Create a navigation recommendation with implementation tracking"""
    recommendation = NavigationRecommendationFactory(status='approved', **kwargs)
    
    # Add implementation
    implementation = RecommendationImplementationFactory(
        recommendation=recommendation,
        is_successful=True
    )
    
    return recommendation, implementation


def create_recommendation_scenario(num_users=5, recommendations_per_user=3):
    """Create a complete recommendation scenario with multiple users and recommendations"""
    from tests.factories.heatmap_factories import UserFactory
    
    users = []
    profiles = []
    recommendations = []
    
    # Create users and profiles
    for i in range(num_users):
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        users.append(user)
        profiles.append(profile)
        
        # Create recommendations for each user
        user_recommendations = []
        for j in range(recommendations_per_user):
            rec = ContentRecommendationFactory(user=user)
            user_recommendations.append(rec)
        recommendations.extend(user_recommendations)
    
    # Create user similarities
    similarities = []
    for i, user1 in enumerate(users):
        for j, user2 in enumerate(users[i+1:], i+1):
            similarity = UserSimilarityFactory(
                user1=user1,
                user2=user2,
                similarity_score=random.uniform(0.1, 0.8)
            )
            similarities.append(similarity)
    
    # Create some navigation recommendations
    nav_recommendations = []
    for _ in range(3):
        nav_rec = NavigationRecommendationFactory()
        nav_recommendations.append(nav_rec)
    
    return {
        'users': users,
        'profiles': profiles,
        'content_recommendations': recommendations,
        'similarities': similarities,
        'navigation_recommendations': nav_recommendations
    }