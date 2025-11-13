"""
Factory definitions for wellness app testing.

Uses factory_boy for generating WellnessContent, WellnessUserProgress,
and related data with realistic defaults and evidence-based content.

Complies with .claude/rules.md standards.
"""
import factory
from datetime import datetime, timezone as dt_timezone, timedelta
from factory.django import DjangoModelFactory
from apps.wellness.models.content_models import (
    WellnessContent,
    WellnessContentCategory,
    WellnessDeliveryContext,
    WellnessContentLevel,
    EvidenceLevel,
)
from apps.wellness.models.progress import WellnessUserProgress


class BtFactory(DjangoModelFactory):
    """Factory for creating test tenants (business units)."""

    class Meta:
        model = "client_onboarding.Bt"
        django_get_or_create = ("bucode",)

    bucode = factory.Sequence(lambda n: f"WELL{n:03d}")
    buname = factory.LazyAttribute(lambda obj: f"Wellness Tenant {obj.bucode}")
    enable = True


class PeopleFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = "peoples.People"
        django_get_or_create = ("loginid",)

    peoplecode = factory.Sequence(lambda n: f"WELLUSR{n:04d}")
    peoplename = factory.Faker("name")
    loginid = factory.LazyAttribute(lambda obj: obj.peoplename.lower().replace(" ", "_"))
    email = factory.LazyAttribute(lambda obj: f"{obj.loginid}@example.com")
    mobno = factory.Faker("numerify", text="##########")
    password = factory.django.Password("TestPass123!")
    client = factory.SubFactory(BtFactory)
    enable = True


class WellnessContentFactory(DjangoModelFactory):
    """
    Factory for creating WellnessContent instances with evidence-based content.

    Generates realistic wellness education content with:
    - Evidence-level tracking for medical compliance
    - Multi-category health education
    - Smart targeting and delivery context
    - Workplace-specific adaptations
    - Actionable tips and key takeaways
    """

    class Meta:
        model = WellnessContent

    tenant = factory.SubFactory(BtFactory)

    title = factory.Faker("sentence", nb_words=8)
    summary = factory.Faker("text", max_nb_chars=200)
    content = factory.Faker("text", max_nb_chars=1000)

    category = factory.Iterator([
        WellnessContentCategory.MENTAL_HEALTH,
        WellnessContentCategory.STRESS_MANAGEMENT,
        WellnessContentCategory.PHYSICAL_WELLNESS,
        WellnessContentCategory.WORKPLACE_HEALTH,
        WellnessContentCategory.SLEEP_HYGIENE,
    ])
    delivery_context = factory.Iterator([
        WellnessDeliveryContext.DAILY_TIP,
        WellnessDeliveryContext.STRESS_RESPONSE,
        WellnessDeliveryContext.MOOD_SUPPORT,
        WellnessDeliveryContext.ENERGY_BOOST,
        WellnessDeliveryContext.SHIFT_TRANSITION,
    ])
    content_level = factory.Iterator([
        WellnessContentLevel.QUICK_TIP,
        WellnessContentLevel.SHORT_READ,
        WellnessContentLevel.DEEP_DIVE,
    ])
    evidence_level = factory.Iterator([
        EvidenceLevel.WHO_CDC_GUIDELINE,
        EvidenceLevel.PEER_REVIEWED_RESEARCH,
        EvidenceLevel.PROFESSIONAL_CONSENSUS,
    ])

    tags = factory.LazyFunction(lambda: [
        "stress", "mindfulness", "wellbeing", "mental_health", "productivity"
    ][:factory.Faker("random_int", min=2, max=5).evaluate(None, None, {})])

    trigger_patterns = factory.LazyFunction(lambda: {
        "stress_level_min": 3,
        "mood_rating_max": 5,
        "energy_level_max": 4,
        "keywords": ["stress", "overwhelmed", "tired"]
    })

    workplace_specific = factory.Iterator([True, False])
    field_worker_relevant = factory.Iterator([True, False])

    action_tips = factory.LazyFunction(lambda: [
        "Take 5 deep breaths when feeling stressed",
        "Schedule short breaks every 2 hours",
        "Practice gratitude daily",
        "Stay hydrated throughout the day",
        "Get 7-9 hours of sleep each night"
    ][:factory.Faker("random_int", min=3, max=5).evaluate(None, None, {})])

    key_takeaways = factory.LazyFunction(lambda: [
        "Stress management is a skill that improves with practice",
        "Small daily habits compound into significant wellbeing improvements",
        "Self-care is essential, not selfish",
        "Mental health is as important as physical health"
    ][:factory.Faker("random_int", min=2, max=4).evaluate(None, None, {})])

    related_topics = factory.LazyFunction(list)

    source_name = factory.Iterator([
        "WHO - World Health Organization",
        "CDC - Centers for Disease Control",
        "Mayo Clinic",
        "National Institute of Mental Health",
        "American Psychological Association"
    ])
    source_url = factory.Faker("url")

    is_active = True


class MentalHealthContentFactory(WellnessContentFactory):
    """Factory for creating mental health specific content."""

    category = WellnessContentCategory.MENTAL_HEALTH
    evidence_level = EvidenceLevel.WHO_CDC_GUIDELINE
    title = factory.Iterator([
        "Understanding Anxiety: Signs and Coping Strategies",
        "Building Resilience in Challenging Times",
        "Depression Awareness: When to Seek Help",
        "Managing Workplace Stress Effectively"
    ])
    tags = ["mental_health", "anxiety", "depression", "resilience", "coping"]
    workplace_specific = True


class StressManagementContentFactory(WellnessContentFactory):
    """Factory for creating stress management content."""

    category = WellnessContentCategory.STRESS_MANAGEMENT
    delivery_context = WellnessDeliveryContext.STRESS_RESPONSE
    content_level = WellnessContentLevel.QUICK_TIP
    title = factory.Iterator([
        "5-Minute Stress Relief Techniques",
        "Breathing Exercises for Instant Calm",
        "Recognizing Your Stress Triggers",
        "Creating a Personal Stress Management Plan"
    ])
    tags = ["stress", "relaxation", "breathing", "mindfulness"]
    field_worker_relevant = True


class WorkplaceHealthContentFactory(WellnessContentFactory):
    """Factory for creating workplace-specific health content."""

    category = WellnessContentCategory.WORKPLACE_HEALTH
    delivery_context = WellnessDeliveryContext.WORKPLACE_SPECIFIC
    workplace_specific = True
    field_worker_relevant = True
    title = factory.Iterator([
        "Ergonomics for Field Workers",
        "Preventing Workplace Injuries",
        "Managing Fatigue During Long Shifts",
        "Healthy Eating on the Go"
    ])
    tags = ["workplace_health", "safety", "ergonomics", "injury_prevention"]


class SleepHygieneContentFactory(WellnessContentFactory):
    """Factory for creating sleep hygiene content."""

    category = WellnessContentCategory.SLEEP_HYGIENE
    delivery_context = WellnessDeliveryContext.SHIFT_TRANSITION
    title = factory.Iterator([
        "Sleep Basics: Why 7-9 Hours Matters",
        "Creating Your Ideal Sleep Environment",
        "Managing Shift Work and Sleep",
        "Natural Ways to Improve Sleep Quality"
    ])
    tags = ["sleep", "rest", "recovery", "circadian_rhythm"]


class WellnessUserProgressFactory(DjangoModelFactory):
    """
    Factory for creating WellnessUserProgress instances.

    Generates realistic user progress data with:
    - Streak tracking for engagement
    - Category-specific progress
    - Learning metrics
    - Achievement milestones
    - Preference management
    """

    class Meta:
        model = WellnessUserProgress

    user = factory.SubFactory(PeopleFactory)
    tenant = factory.LazyAttribute(lambda obj: obj.user.client)

    # Streak tracking
    current_streak = factory.Faker("random_int", min=0, max=30)
    longest_streak = factory.LazyAttribute(
        lambda obj: max(obj.current_streak, factory.Faker("random_int", min=0, max=100).evaluate(None, None, {}))
    )
    last_activity_date = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(days=factory.Faker("random_int", min=0, max=3).evaluate(None, None, {}))
    )

    # Learning metrics
    total_content_viewed = factory.Faker("random_int", min=10, max=100)
    total_content_completed = factory.LazyAttribute(
        lambda obj: int(obj.total_content_viewed * 0.7)  # 70% completion rate
    )
    total_time_spent_minutes = factory.Faker("random_int", min=100, max=1000)
    total_score = factory.Faker("random_int", min=100, max=5000)

    # Category progress (JSON field)
    category_progress = factory.LazyFunction(lambda: {
        "mental_health": {"viewed": 15, "completed": 10},
        "stress_management": {"viewed": 20, "completed": 15},
        "physical_wellness": {"viewed": 10, "completed": 8},
        "workplace_health": {"viewed": 12, "completed": 9},
        "sleep_hygiene": {"viewed": 8, "completed": 6}
    })

    # Achievements
    achievements_earned = factory.LazyFunction(lambda: [
        {"name": "First Step", "earned_at": (datetime.now(dt_timezone.utc) - timedelta(days=30)).isoformat()},
        {"name": "Weekly Warrior", "earned_at": (datetime.now(dt_timezone.utc) - timedelta(days=14)).isoformat()},
        {"name": "Stress Master", "earned_at": (datetime.now(dt_timezone.utc) - timedelta(days=7)).isoformat()},
    ])

    # Preferences
    preferred_categories = factory.LazyFunction(lambda: [
        "mental_health", "stress_management", "mindfulness"
    ])
    preferred_time_of_day = factory.Iterator(["morning", "afternoon", "evening", "night"])
    preferred_content_length = factory.Iterator([
        WellnessContentLevel.QUICK_TIP,
        WellnessContentLevel.SHORT_READ,
    ])
    notifications_enabled = True


class ActiveUserProgressFactory(WellnessUserProgressFactory):
    """Factory for creating active user progress with high engagement."""

    current_streak = factory.Faker("random_int", min=7, max=30)
    total_content_viewed = factory.Faker("random_int", min=50, max=200)
    total_score = factory.Faker("random_int", min=1000, max=10000)
    last_activity_date = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc))


class NewUserProgressFactory(WellnessUserProgressFactory):
    """Factory for creating new user progress with minimal engagement."""

    current_streak = 0
    longest_streak = 0
    total_content_viewed = factory.Faker("random_int", min=1, max=5)
    total_content_completed = 0
    total_time_spent_minutes = factory.Faker("random_int", min=5, max=20)
    total_score = factory.Faker("random_int", min=10, max=100)
    achievements_earned = factory.LazyFunction(list)


__all__ = [
    'WellnessContentFactory',
    'MentalHealthContentFactory',
    'StressManagementContentFactory',
    'WorkplaceHealthContentFactory',
    'SleepHygieneContentFactory',
    'WellnessUserProgressFactory',
    'ActiveUserProgressFactory',
    'NewUserProgressFactory',
    'BtFactory',
    'PeopleFactory',
]
