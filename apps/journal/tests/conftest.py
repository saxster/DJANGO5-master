"""
Fixtures for journal app testing

Provides factories and fixtures for:
- JournalEntry models
- JournalMediaAttachment models
- JournalPrivacySettings models
- Test users and tenants
- API client setup
"""
import pytest
from django.test import RequestFactory
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from rest_framework.test import APIClient
from uuid import uuid4

from apps.journal.models import JournalEntry, JournalMediaAttachment, JournalPrivacySettings
from apps.journal.models.enums import (
    JournalEntryType,
    JournalPrivacyScope,
    JournalSyncStatus,
)
from apps.tenants.models import Tenant

User = get_user_model()


# ============================================================================
# Tenant Fixtures
# ============================================================================


@pytest.fixture
def test_tenant():
    """Create a test tenant for multi-tenant isolation"""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        schema_name="test_tenant",
        is_active=True,
    )


# ============================================================================
# User Fixtures
# ============================================================================


@pytest.fixture
def test_user(test_tenant):
    """Create a test user"""
    return User.objects.create_user(
        peoplecode="TEST001",
        peoplename="Test User",
        loginid="testuser",
        email="testuser@example.com",
        password="testpass123",
        dateofbirth="1990-01-01",
        dateofjoin="2023-01-01",
        tenant=test_tenant,
        isverified=True,
        enable=True,
    )


@pytest.fixture
def test_user2(test_tenant):
    """Create a second test user for sharing/permission tests"""
    return User.objects.create_user(
        peoplecode="TEST002",
        peoplename="Test User 2",
        loginid="testuser2",
        email="testuser2@example.com",
        password="testpass123",
        dateofbirth="1992-05-15",
        dateofjoin="2023-06-01",
        tenant=test_tenant,
        isverified=True,
        enable=True,
    )


# ============================================================================
# Journal Entry Fixtures
# ============================================================================


@pytest.fixture
def test_journal_entry(test_user, test_tenant):
    """Create a basic journal entry"""
    return JournalEntry.objects.create(
        user=test_user,
        tenant=test_tenant,
        entry_type=JournalEntryType.PERSONAL_REFLECTION,
        title="Test Journal Entry",
        subtitle="A test entry",
        content="This is test content for the journal entry.",
        timestamp=timezone.now(),
        privacy_scope=JournalPrivacyScope.PRIVATE,
        consent_given=True,
        consent_timestamp=timezone.now(),
        mood_rating=7,
        stress_level=2,
        energy_level=8,
        is_draft=False,
    )


@pytest.fixture
def wellbeing_journal_entry(test_user, test_tenant):
    """Create a wellbeing-focused journal entry with mood/stress metrics"""
    return JournalEntry.objects.create(
        user=test_user,
        tenant=test_tenant,
        entry_type=JournalEntryType.MOOD_CHECK_IN,
        title="Morning Mood Check",
        content="Feeling good this morning, ready to tackle the day",
        timestamp=timezone.now(),
        privacy_scope=JournalPrivacyScope.PRIVATE,
        consent_given=True,
        consent_timestamp=timezone.now(),
        mood_rating=8,
        stress_level=1,
        energy_level=9,
        mood_description="Optimistic and energized",
        stress_triggers=["deadline", "meetings"],
        coping_strategies=["meditation", "exercise"],
        gratitude_items=["good health", "supportive team"],
        is_draft=False,
    )


@pytest.fixture
def work_journal_entry(test_user, test_tenant):
    """Create a work-focused journal entry with performance metrics"""
    return JournalEntry.objects.create(
        user=test_user,
        tenant=test_tenant,
        entry_type=JournalEntryType.SITE_INSPECTION,
        title="Site Inspection Report",
        content="Completed routine site inspection. All systems operational.",
        timestamp=timezone.now(),
        privacy_scope=JournalPrivacyScope.PRIVATE,
        consent_given=True,
        consent_timestamp=timezone.now(),
        location_site_name="Main Office",
        location_address="123 Business St, City, State 12345",
        location_coordinates={"lat": 40.7128, "lng": -74.0060},
        team_members=["Alice Johnson", "Bob Smith"],
        completion_rate=0.95,
        efficiency_score=8.5,
        quality_score=9.0,
        items_processed=25,
        tags=["inspection", "routine", "safety"],
        priority="high",
        severity="low",
        is_draft=False,
    )


@pytest.fixture
def draft_journal_entry(test_user, test_tenant):
    """Create a draft journal entry"""
    return JournalEntry.objects.create(
        user=test_user,
        tenant=test_tenant,
        entry_type=JournalEntryType.PERSONAL_REFLECTION,
        title="Draft Entry",
        content="This is incomplete...",
        timestamp=timezone.now(),
        is_draft=True,
        privacy_scope=JournalPrivacyScope.PRIVATE,
        consent_given=False,
    )


@pytest.fixture
def shared_journal_entry(test_user, test_user2, test_tenant):
    """Create a shared journal entry"""
    return JournalEntry.objects.create(
        user=test_user,
        tenant=test_tenant,
        entry_type=JournalEntryType.TEAM_COLLABORATION,
        title="Team Collaboration Report",
        content="Collaborated with team on project X",
        timestamp=timezone.now(),
        privacy_scope=JournalPrivacyScope.SHARED,
        sharing_permissions=[str(test_user2.id)],
        consent_given=True,
        consent_timestamp=timezone.now(),
        team_members=["Test User", "Test User 2"],
        is_draft=False,
    )


# ============================================================================
# Journal Media Attachment Fixtures
# ============================================================================


@pytest.fixture
def test_media_attachment(test_journal_entry, tmp_path):
    """Create a test media attachment"""
    # Create a temporary file for testing
    test_file = tmp_path / "test_image.jpg"
    test_file.write_bytes(b"fake image data")

    with open(test_file, 'rb') as f:
        from django.core.files.uploadedfile import SimpleUploadedFile
        uploaded_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake image data",
            content_type="image/jpeg"
        )

        return JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=uploaded_file,
            original_filename="test_image.jpg",
            mime_type="image/jpeg",
            file_size=len(b"fake image data"),
            caption="Test photo caption",
            display_order=1,
            is_hero_image=True,
        )


@pytest.fixture
def test_video_attachment(test_journal_entry):
    """Create a test video attachment"""
    from django.core.files.uploadedfile import SimpleUploadedFile

    uploaded_file = SimpleUploadedFile(
        "test_video.mp4",
        b"fake video data",
        content_type="video/mp4"
    )

    return JournalMediaAttachment.objects.create(
        journal_entry=test_journal_entry,
        media_type="VIDEO",
        file=uploaded_file,
        original_filename="test_video.mp4",
        mime_type="video/mp4",
        file_size=len(b"fake video data"),
        caption="Test video caption",
        display_order=2,
    )


# ============================================================================
# Privacy Settings Fixtures
# ============================================================================


@pytest.fixture
def test_privacy_settings(test_user):
    """Create privacy settings for a user"""
    return JournalPrivacySettings.objects.create(
        user=test_user,
        default_privacy_scope=JournalPrivacyScope.PRIVATE,
        wellbeing_sharing_consent=False,
        manager_access_consent=False,
        analytics_consent=False,
        crisis_intervention_consent=False,
        data_retention_days=365,
        auto_delete_enabled=False,
        consent_timestamp=timezone.now(),
    )


@pytest.fixture
def permissive_privacy_settings(test_user):
    """Create privacy settings with all consents given"""
    return JournalPrivacySettings.objects.create(
        user=test_user,
        default_privacy_scope=JournalPrivacyScope.SHARED,
        wellbeing_sharing_consent=True,
        manager_access_consent=True,
        analytics_consent=True,
        crisis_intervention_consent=True,
        data_retention_days=1095,  # 3 years
        auto_delete_enabled=False,
        consent_timestamp=timezone.now(),
    )


# ============================================================================
# Request and API Client Fixtures
# ============================================================================


@pytest.fixture
def rf():
    """Django request factory for creating test requests"""
    return RequestFactory()


@pytest.fixture
def api_client():
    """DRF API client for endpoint testing"""
    return APIClient()


@pytest.fixture
def authenticated_api_client(test_user):
    """API client authenticated as test_user"""
    client = APIClient()
    client.force_authenticate(user=test_user)
    return client


@pytest.fixture
def authenticated_api_client_2(test_user2):
    """API client authenticated as test_user2"""
    client = APIClient()
    client.force_authenticate(user=test_user2)
    return client


@pytest.fixture
def request_with_user(rf, test_user):
    """Create a request with an authenticated user"""
    request = rf.get('/')
    request.user = test_user

    # Add session
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()

    return request


# ============================================================================
# Factory Fixtures for Bulk Creation
# ============================================================================


@pytest.fixture
def journal_entry_factory(test_user, test_tenant):
    """Factory for creating multiple journal entries"""
    def _create_entry(
        entry_type=JournalEntryType.PERSONAL_REFLECTION,
        title="Factory Entry",
        content="Factory created content",
        mood_rating=None,
        stress_level=None,
        energy_level=None,
        privacy_scope=JournalPrivacyScope.PRIVATE,
        **kwargs
    ):
        return JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=entry_type,
            title=title,
            content=content,
            mood_rating=mood_rating,
            stress_level=stress_level,
            energy_level=energy_level,
            privacy_scope=privacy_scope,
            timestamp=timezone.now(),
            consent_given=True,
            consent_timestamp=timezone.now(),
            **kwargs
        )
    return _create_entry


@pytest.fixture
def media_attachment_factory(test_journal_entry):
    """Factory for creating multiple media attachments"""
    def _create_attachment(
        media_type="PHOTO",
        filename="test.jpg",
        mime_type="image/jpeg",
        **kwargs
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile

        uploaded_file = SimpleUploadedFile(
            filename,
            b"fake file data",
            content_type=mime_type
        )

        return JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type=media_type,
            file=uploaded_file,
            original_filename=filename,
            mime_type=mime_type,
            file_size=len(b"fake file data"),
            **kwargs
        )
    return _create_attachment
