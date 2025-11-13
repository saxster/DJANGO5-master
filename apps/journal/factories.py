"""
Factory definitions for journal app testing.

Uses factory_boy for generating JournalEntry and related data
with realistic defaults and comprehensive wellbeing metrics.

Complies with .claude/rules.md standards.
"""
import factory
from datetime import datetime, timezone as dt_timezone, timedelta
from factory.django import DjangoModelFactory
from apps.journal.models import JournalEntry
from apps.journal.models.enums import JournalEntryType, JournalPrivacyScope, JournalSyncStatus


class BtFactory(DjangoModelFactory):
    """Factory for creating test tenants (business units)."""

    class Meta:
        model = "client_onboarding.Bt"
        django_get_or_create = ("bucode",)

    bucode = factory.Sequence(lambda n: f"JRNL{n:03d}")
    buname = factory.LazyAttribute(lambda obj: f"Journal Tenant {obj.bucode}")
    enable = True


class PeopleFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = "peoples.People"
        django_get_or_create = ("loginid",)

    peoplecode = factory.Sequence(lambda n: f"JRNLUSR{n:04d}")
    peoplename = factory.Faker("name")
    loginid = factory.LazyAttribute(lambda obj: obj.peoplename.lower().replace(" ", "_"))
    email = factory.LazyAttribute(lambda obj: f"{obj.loginid}@example.com")
    mobno = factory.Faker("numerify", text="##########")
    password = factory.django.Password("TestPass123!")
    client = factory.SubFactory(BtFactory)
    enable = True


class JournalEntryFactory(DjangoModelFactory):
    """
    Factory for creating JournalEntry instances with realistic wellbeing data.

    Generates comprehensive journal entries with:
    - Wellbeing metrics (mood, stress, energy)
    - Positive psychology fields (gratitude, affirmations)
    - Privacy controls and consent tracking
    - Work performance metrics
    - Offline sync support
    """

    class Meta:
        model = JournalEntry

    user = factory.SubFactory(PeopleFactory)
    tenant = factory.LazyAttribute(lambda obj: obj.user.client)

    entry_type = factory.Iterator([
        JournalEntryType.PERSONAL_REFLECTION,
        JournalEntryType.MOOD_CHECK_IN,
        JournalEntryType.GRATITUDE,
        JournalEntryType.DAILY_AFFIRMATIONS,
        JournalEntryType.STRESS_LOG,
    ])
    title = factory.Faker("sentence", nb_words=6)
    subtitle = factory.Faker("sentence", nb_words=4)
    content = factory.Faker("text", max_nb_chars=500)
    timestamp = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc))
    duration_minutes = factory.Faker("random_int", min=5, max=60)

    # Privacy controls
    privacy_scope = JournalPrivacyScope.PRIVATE
    consent_given = True
    consent_timestamp = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc))
    sharing_permissions = factory.LazyFunction(list)

    # Wellbeing metrics
    mood_rating = factory.Faker("random_int", min=1, max=10)
    mood_description = factory.Iterator([
        "Happy", "Content", "Neutral", "Stressed", "Anxious",
        "Energized", "Calm", "Peaceful", "Overwhelmed", "Grateful"
    ])
    stress_level = factory.Faker("random_int", min=1, max=5)
    energy_level = factory.Faker("random_int", min=1, max=10)
    stress_triggers = factory.LazyFunction(lambda: [
        "Work deadline", "Team conflict", "Heavy workload"
    ][:factory.Faker("random_int", min=0, max=3).evaluate(None, None, {})])
    coping_strategies = factory.LazyFunction(lambda: [
        "Deep breathing", "Short walk", "Music break"
    ][:factory.Faker("random_int", min=0, max=3).evaluate(None, None, {})])

    # Positive psychology fields
    gratitude_items = factory.LazyFunction(lambda: [
        "Supportive team members",
        "Good health",
        "Meaningful work"
    ][:factory.Faker("random_int", min=1, max=3).evaluate(None, None, {})])
    daily_goals = factory.LazyFunction(lambda: [
        "Complete priority tasks",
        "Exercise for 30 minutes",
        "Connect with a friend"
    ][:factory.Faker("random_int", min=1, max=3).evaluate(None, None, {})])
    affirmations = factory.LazyFunction(lambda: [
        "I am capable and confident",
        "I handle challenges with grace",
        "I deserve success and happiness"
    ][:factory.Faker("random_int", min=1, max=3).evaluate(None, None, {})])
    achievements = factory.LazyFunction(lambda: [
        "Completed project milestone",
        "Helped colleague solve problem",
        "Maintained consistent routine"
    ][:factory.Faker("random_int", min=0, max=3).evaluate(None, None, {})])
    learnings = factory.LazyFunction(lambda: [
        "Better time management improves stress",
        "Short breaks increase productivity",
        "Communication prevents conflicts"
    ][:factory.Faker("random_int", min=0, max=3).evaluate(None, None, {})])
    challenges = factory.LazyFunction(lambda: [
        "Meeting tight deadline",
        "Learning new skill",
        "Managing multiple priorities"
    ][:factory.Faker("random_int", min=0, max=3).evaluate(None, None, {})])

    # Location and work context
    location_site_name = factory.Faker("company")
    location_address = factory.Faker("address")
    location_coordinates = factory.LazyFunction(lambda: {
        "lat": factory.Faker("latitude").evaluate(None, None, {}),
        "lng": factory.Faker("longitude").evaluate(None, None, {})
    })
    location_area_type = factory.Iterator(["office", "field", "client_site", "remote", "home"])
    team_members = factory.LazyFunction(lambda: [
        factory.Faker("name").evaluate(None, None, {})
        for _ in range(factory.Faker("random_int", min=0, max=5).evaluate(None, None, {}))
    ])

    # Categorization
    tags = factory.LazyFunction(lambda: [
        "wellbeing", "work", "reflection", "gratitude", "stress"
    ][:factory.Faker("random_int", min=1, max=5).evaluate(None, None, {})])
    priority = factory.Iterator(["low", "medium", "high"])
    severity = factory.Iterator(["", "low", "medium", "high"])

    # Work performance metrics
    completion_rate = factory.Faker("pyfloat", min_value=0.5, max_value=1.0, right_digits=2)
    efficiency_score = factory.Faker("pyfloat", min_value=5.0, max_value=10.0, right_digits=1)
    quality_score = factory.Faker("pyfloat", min_value=6.0, max_value=10.0, right_digits=1)
    items_processed = factory.Faker("random_int", min=1, max=50)

    # Entry state
    is_bookmarked = False
    is_draft = False
    is_deleted = False

    # Sync state
    sync_status = JournalSyncStatus.SYNCED
    mobile_id = factory.Faker("uuid4")
    version = 1
    last_sync_timestamp = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc))

    # Metadata
    metadata = factory.LazyFunction(lambda: {
        "device_type": "mobile",
        "app_version": "2.1.0",
        "platform": "android"
    })


class MoodCheckInFactory(JournalEntryFactory):
    """Factory for creating mood check-in entries."""

    entry_type = JournalEntryType.MOOD_CHECK_IN
    title = "Daily Mood Check-in"
    privacy_scope = JournalPrivacyScope.PRIVATE
    mood_rating = factory.Faker("random_int", min=1, max=10)
    stress_level = factory.Faker("random_int", min=1, max=5)
    energy_level = factory.Faker("random_int", min=1, max=10)


class GratitudeEntryFactory(JournalEntryFactory):
    """Factory for creating gratitude journal entries."""

    entry_type = JournalEntryType.GRATITUDE
    title = "Things I'm Grateful For"
    privacy_scope = JournalPrivacyScope.PRIVATE
    gratitude_items = factory.LazyFunction(lambda: [
        "My health and wellbeing",
        "Supportive colleagues",
        "Opportunities to learn and grow"
    ])


class StressLogFactory(JournalEntryFactory):
    """Factory for creating stress log entries."""

    entry_type = JournalEntryType.STRESS_LOG
    title = "Stress Management Log"
    privacy_scope = JournalPrivacyScope.PRIVATE
    stress_level = factory.Faker("random_int", min=3, max=5)  # Higher stress
    stress_triggers = factory.LazyFunction(lambda: [
        "Tight deadline",
        "Unexpected issues",
        "High workload"
    ])
    coping_strategies = factory.LazyFunction(lambda: [
        "Deep breathing exercises",
        "Short meditation break",
        "Talk with colleague"
    ])


class WorkReflectionFactory(JournalEntryFactory):
    """Factory for creating work reflection entries."""

    entry_type = JournalEntryType.END_OF_SHIFT_REFLECTION
    title = "End of Shift Reflection"
    privacy_scope = JournalPrivacyScope.AGGREGATE_ONLY
    completion_rate = factory.Faker("pyfloat", min_value=0.7, max_value=1.0, right_digits=2)
    efficiency_score = factory.Faker("pyfloat", min_value=6.0, max_value=10.0, right_digits=1)
    quality_score = factory.Faker("pyfloat", min_value=7.0, max_value=10.0, right_digits=1)
    achievements = factory.LazyFunction(lambda: [
        "Completed all priority tasks",
        "Helped team member",
        "Improved process efficiency"
    ])


class DraftJournalEntryFactory(JournalEntryFactory):
    """Factory for creating draft journal entries."""

    is_draft = True
    sync_status = JournalSyncStatus.PENDING
    content = factory.Faker("text", max_nb_chars=200)  # Shorter for drafts


class SharedJournalEntryFactory(JournalEntryFactory):
    """Factory for creating shared journal entries."""

    privacy_scope = JournalPrivacyScope.SHARED
    sharing_permissions = factory.LazyFunction(lambda: [
        factory.Faker("uuid4").evaluate(None, None, {})
        for _ in range(factory.Faker("random_int", min=1, max=3).evaluate(None, None, {}))
    ])


__all__ = [
    'JournalEntryFactory',
    'MoodCheckInFactory',
    'GratitudeEntryFactory',
    'StressLogFactory',
    'WorkReflectionFactory',
    'DraftJournalEntryFactory',
    'SharedJournalEntryFactory',
    'BtFactory',
    'PeopleFactory',
]
