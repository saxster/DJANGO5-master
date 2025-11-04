# Bounded Contexts Multimodal Refactoring - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor monolithic `apps/onboarding/` into 3 bounded contexts (client, site, worker) with shared multimodal voice/media platform.

**Architecture:** Extract 12 model files into 4 new apps (client_onboarding, site_onboarding, core_onboarding, enhanced people_onboarding). Delete apps/onboarding/ completely. Update 292+ import statements. Include security fixes (SSRF, UUID validation, DLQ race condition).

**Tech Stack:** Django 5.2.1, PostgreSQL, Celery, multimodal (voice/text + 0-N photos/videos), Vision API, LLM integration

---

## CRITICAL: Read Before Starting

**This is a Big Bang refactoring** - no backward compatibility. All imports updated, old app deleted.

**Security fixes included**:
- SSRF protection in document fetching
- UUID validation for knowledge_ids
- DLQ race condition fix with atomic Redis operations

**Testing requirement**: After each batch of tasks (every 5-10 tasks), run `python3 -m py_compile` on modified files.

---

## Pre-Implementation Checklist

- [ ] In worktree: `.worktrees/bounded-contexts/`
- [ ] Branch: `refactor/bounded-contexts-multimodal`
- [ ] Design doc read: `docs/plans/2025-11-03-bounded-contexts-refactoring-design.md`
- [ ] Baseline tests passing (or documented failures)

---

## BATCH 1: Create App Structures (Tasks 1-4)

### Task 1: Create client_onboarding app structure

**Files:**
- Create: `apps/client_onboarding/__init__.py`
- Create: `apps/client_onboarding/apps.py`
- Create: `apps/client_onboarding/models/__init__.py`
- Create: `apps/client_onboarding/services/__init__.py`
- Create: `apps/client_onboarding/handlers/__init__.py`
- Create: `apps/client_onboarding/api/__init__.py`
- Create: `apps/client_onboarding/admin/__init__.py`
- Create: `apps/client_onboarding/tests/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p apps/client_onboarding/{models,services,handlers,api,admin,tests,migrations}
```

**Step 2: Create apps.py**

File: `apps/client_onboarding/apps.py`
```python
from django.apps import AppConfig


class ClientOnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.client_onboarding'
    verbose_name = 'Client Onboarding'

    def ready(self):
        """Import signals when app is ready"""
        pass  # Signals imported here when needed
```

**Step 3: Create __init__.py files**

```bash
touch apps/client_onboarding/__init__.py
touch apps/client_onboarding/models/__init__.py
touch apps/client_onboarding/services/__init__.py
touch apps/client_onboarding/handlers/__init__.py
touch apps/client_onboarding/api/__init__.py
touch apps/client_onboarding/admin/__init__.py
touch apps/client_onboarding/tests/__init__.py
touch apps/client_onboarding/migrations/__init__.py
```

**Step 4: Verify structure**

Run: `tree apps/client_onboarding/ -I __pycache__`
Expected: Directory structure with 8 subdirectories

**Step 5: Commit**

```bash
git add apps/client_onboarding/
git commit -m "feat(refactor): create client_onboarding app structure"
```

---

### Task 2: Create site_onboarding app structure

**Files:**
- Create: `apps/site_onboarding/` (same structure as Task 1)

**Step 1: Create directory structure**

```bash
mkdir -p apps/site_onboarding/{models,services,handlers,api,admin,tests,migrations}
```

**Step 2: Create apps.py**

File: `apps/site_onboarding/apps.py`
```python
from django.apps import AppConfig


class SiteOnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.site_onboarding'
    verbose_name = 'Site Onboarding'

    def ready(self):
        """Import signals when app is ready"""
        pass
```

**Step 3: Create __init__.py files**

```bash
touch apps/site_onboarding/__init__.py
touch apps/site_onboarding/models/__init__.py
touch apps/site_onboarding/services/__init__.py
touch apps/site_onboarding/handlers/__init__.py
touch apps/site_onboarding/api/__init__.py
touch apps/site_onboarding/admin/__init__.py
touch apps/site_onboarding/tests/__init__.py
touch apps/site_onboarding/migrations/__init__.py
```

**Step 4: Commit**

```bash
git add apps/site_onboarding/
git commit -m "feat(refactor): create site_onboarding app structure"
```

---

### Task 3: Create core_onboarding app structure

**Files:**
- Create: `apps/core_onboarding/` with extended structure

**Step 1: Create directory structure**

```bash
mkdir -p apps/core_onboarding/{models,services/{llm,knowledge,translation,orchestration,media},handlers,api,admin,tests,background_tasks,migrations}
```

**Step 2: Create apps.py**

File: `apps/core_onboarding/apps.py`
```python
from django.apps import AppConfig


class CoreOnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core_onboarding'
    verbose_name = 'Core Onboarding Platform'

    def ready(self):
        """Import signals and initialize shared services"""
        pass
```

**Step 3: Create __init__.py files**

```bash
touch apps/core_onboarding/__init__.py
touch apps/core_onboarding/models/__init__.py
touch apps/core_onboarding/services/__init__.py
touch apps/core_onboarding/services/llm/__init__.py
touch apps/core_onboarding/services/knowledge/__init__.py
touch apps/core_onboarding/services/translation/__init__.py
touch apps/core_onboarding/services/orchestration/__init__.py
touch apps/core_onboarding/services/media/__init__.py
touch apps/core_onboarding/handlers/__init__.py
touch apps/core_onboarding/api/__init__.py
touch apps/core_onboarding/admin/__init__.py
touch apps/core_onboarding/tests/__init__.py
touch apps/core_onboarding/background_tasks/__init__.py
touch apps/core_onboarding/migrations/__init__.py
```

**Step 4: Commit**

```bash
git add apps/core_onboarding/
git commit -m "feat(refactor): create core_onboarding shared infrastructure"
```

---

### Task 4: Enhance people_onboarding app structure

**Files:**
- Create: `apps/people_onboarding/services/__init__.py`
- Create: `apps/people_onboarding/handlers/__init__.py`

**Step 1: Create missing directories**

```bash
mkdir -p apps/people_onboarding/services
mkdir -p apps/people_onboarding/handlers
```

**Step 2: Create __init__.py files**

```bash
touch apps/people_onboarding/services/__init__.py
touch apps/people_onboarding/handlers/__init__.py
```

**Step 3: Commit**

```bash
git add apps/people_onboarding/services/ apps/people_onboarding/handlers/
git commit -m "feat(refactor): add service and handler structure to people_onboarding"
```

---

## BATCH 2: Core Infrastructure - Multimodal Models (Tasks 5-9)

### Task 5: Create OnboardingMedia model (universal media storage)

**Files:**
- Create: `apps/core_onboarding/models/media.py`
- Create: `apps/core_onboarding/tests/test_media_model.py`

**Step 1: Write the failing test**

File: `apps/core_onboarding/tests/test_media_model.py`
```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.core_onboarding.models import OnboardingMedia
from apps.peoples.models import People


@pytest.mark.django_db
class TestOnboardingMedia:

    def test_create_photo_media(self, test_user):
        """Test creating photo media with GPS"""
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id='test-site-123',
            media_type='PHOTO',
            file=SimpleUploadedFile("test.jpg", b"fake image content", content_type="image/jpeg"),
            gps_latitude=12.9716,
            gps_longitude=77.5946,
            uploaded_by=test_user
        )

        assert media.media_id is not None
        assert media.context_type == 'SITE'
        assert media.media_type == 'PHOTO'
        assert media.gps_latitude == 12.9716

    def test_create_media_without_gps(self, test_user):
        """Test creating media without GPS (0-N media flexibility)"""
        media = OnboardingMedia.objects.create(
            context_type='WORKER',
            context_object_id='worker-456',
            media_type='DOCUMENT',
            file=SimpleUploadedFile("id.pdf", b"fake pdf", content_type="application/pdf"),
            uploaded_by=test_user
        )

        assert media.gps_latitude is None
        assert media.gps_longitude is None
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/core_onboarding/tests/test_media_model.py -v`
Expected: FAIL with "No module named 'apps.core_onboarding.models'"

**Step 3: Create conftest for test fixtures**

File: `apps/core_onboarding/tests/conftest.py`
```python
import pytest
from django.contrib.auth import get_user_model

People = get_user_model()


@pytest.fixture
def test_user(db):
    """Create test user"""
    return People.objects.create_user(
        peoplecode='TEST001',
        loginid='testuser',
        peoplename='Test User',
        email='test@example.com'
    )


@pytest.fixture
def test_client(db):
    """Create test client (will be in client_onboarding later)"""
    from apps.onboarding.models import Bt
    return Bt.objects.create(
        bucode='TESTCLIENT',
        buname='Test Client'
    )
```

**Step 4: Create OnboardingMedia model**

File: `apps/core_onboarding/models/media.py`
```python
"""
Multimodal Media Storage for Onboarding Platform

Supports universal media capture across all onboarding contexts:
- Client onboarding: Office photos, signage
- Site onboarding: Zone photos/videos, asset documentation
- Worker onboarding: ID documents, certificates, training videos

Features:
- 0 to N media per observation (flexible)
- GPS location capture
- AI analysis (Vision API, LLM processing)
- Context-agnostic (works with any entity)

Complies with:
- Rule #7: Model < 150 lines
- Rule #14: File upload security (filename sanitization)
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from apps.core.models import TenantAwareModel


class OnboardingMedia(TenantAwareModel):
    """
    Universal media storage for onboarding observations.

    Supports:
    - Photos (JPEG, PNG, WebP)
    - Videos (MP4, WebM, QuickTime)
    - Audio (MP3, WAV, WebM, OGG)
    - Documents (PDF, scanned images)

    Used by:
    - Client context: Office photos, signage
    - Site context: Zone documentation, asset photos
    - Worker context: ID scans, certificates
    """

    class MediaType(models.TextChoices):
        PHOTO = 'PHOTO', _('Photo')
        VIDEO = 'VIDEO', _('Video')
        AUDIO = 'AUDIO', _('Audio Recording')
        DOCUMENT = 'DOCUMENT', _('Document Scan')

    class ContextType(models.TextChoices):
        CLIENT = 'CLIENT', _('Client Setup')
        SITE = 'SITE', _('Site Survey')
        WORKER = 'WORKER', _('Worker Documents')

    # Identifiers
    media_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Context linkage (generic)
    context_type = models.CharField(
        _('Context Type'),
        max_length=20,
        choices=ContextType.choices,
        help_text=_('Which onboarding context this media belongs to')
    )
    context_object_id = models.CharField(
        _('Context Object ID'),
        max_length=100,
        help_text=_('UUID of the related object (site_id, request_id, etc.)')
    )

    # Media storage
    media_type = models.CharField(
        _('Media Type'),
        max_length=20,
        choices=MediaType.choices
    )
    file = models.FileField(
        _('File'),
        upload_to='onboarding_media/%Y/%m/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'jpg', 'jpeg', 'png', 'webp',  # Photos
                    'mp4', 'webm', 'mov',          # Videos
                    'mp3', 'wav', 'ogg',           # Audio
                    'pdf'                           # Documents
                ]
            )
        ]
    )
    thumbnail = models.ImageField(
        _('Thumbnail'),
        upload_to='onboarding_media/thumbnails/',
        null=True,
        blank=True,
        help_text=_('Auto-generated thumbnail for photos/videos')
    )

    # Geolocation (captured at upload time)
    gps_latitude = models.FloatField(_('GPS Latitude'), null=True, blank=True)
    gps_longitude = models.FloatField(_('GPS Longitude'), null=True, blank=True)
    gps_accuracy = models.FloatField(_('GPS Accuracy (meters)'), null=True, blank=True)
    compass_direction = models.FloatField(
        _('Compass Direction'),
        null=True,
        blank=True,
        help_text=_('Degrees (0-360) camera was facing')
    )

    # Voice/text annotation
    voice_transcript = models.TextField(
        _('Voice Transcript'),
        blank=True,
        help_text=_('Speech-to-text transcription if audio')
    )
    text_description = models.TextField(
        _('Text Description'),
        blank=True,
        help_text=_('User-provided text description')
    )
    translated_description = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Translations: {"es": "...", "hi": "...", "ta": "..."}')
    )

    # AI analysis
    ai_analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Vision API or LLM analysis results')
    )
    detected_objects = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Detected objects: ["camera", "door", "person"]')
    )
    safety_concerns = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Safety issues: ["no fire extinguisher", "blocked exit"]')
    )

    # Metadata
    uploaded_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.PROTECT,
        related_name='uploaded_media'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False, help_text=_('AI analysis completed'))

    class Meta:
        db_table = 'core_onboarding_media'
        verbose_name = 'Onboarding Media'
        verbose_name_plural = 'Onboarding Media'
        indexes = [
            models.Index(fields=['context_type', 'context_object_id'], name='media_context_idx'),
            models.Index(fields=['uploaded_at'], name='media_uploaded_idx'),
            models.Index(fields=['media_type'], name='media_type_idx'),
        ]
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_media_type_display()} - {self.context_type} ({self.uploaded_at})"
```

**Step 5: Update models __init__.py**

File: `apps/core_onboarding/models/__init__.py`
```python
from .media import OnboardingMedia

__all__ = ['OnboardingMedia']
```

**Step 6: Run test to verify**

Run: `pytest apps/core_onboarding/tests/test_media_model.py -v`
Expected: Tests should fail with database table doesn't exist (we'll create migrations later)

**Step 7: Validate syntax**

Run: `python3 -m py_compile apps/core_onboarding/models/media.py`
Expected: No output (success)

**Step 8: Commit**

```bash
git add apps/site_onboarding/ apps/core_onboarding/models/media.py apps/core_onboarding/models/__init__.py apps/core_onboarding/tests/
git commit -m "feat(refactor): create site_onboarding structure + OnboardingMedia model"
```

---

### Task 6: Create OnboardingObservation model (universal observation)

**Files:**
- Create: `apps/core_onboarding/models/observation.py`
- Create: `apps/core_onboarding/tests/test_observation_model.py`

**Step 1: Write the failing test**

File: `apps/core_onboarding/tests/test_observation_model.py`
```python
import pytest
from apps.core_onboarding.models import OnboardingObservation, OnboardingMedia


@pytest.mark.django_db
class TestOnboardingObservation:

    def test_create_text_observation_no_media(self, test_user):
        """Test text-only observation with 0 media (flexibility)"""
        obs = OnboardingObservation.objects.create(
            context_type='CLIENT',
            context_object_id='client-123',
            text_input='Client confirmed security requirements',
            created_by=test_user
        )

        assert obs.observation_id is not None
        assert obs.text_input == 'Client confirmed security requirements'
        assert obs.media.count() == 0  # Zero media

    def test_create_voice_observation_with_multiple_photos(self, test_user):
        """Test voice observation with N photos"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        obs = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id='site-789',
            audio_file=SimpleUploadedFile("voice.mp3", b"audio data"),
            original_transcript='Gate 3 has broken lock',
            created_by=test_user
        )

        # Add 3 photos
        for i in range(3):
            media = OnboardingMedia.objects.create(
                context_type='SITE',
                context_object_id='site-789',
                media_type='PHOTO',
                file=SimpleUploadedFile(f"photo{i}.jpg", b"image"),
                uploaded_by=test_user
            )
            obs.media.add(media)

        assert obs.media.count() == 3  # Multiple media
        assert obs.original_transcript == 'Gate 3 has broken lock'
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/core_onboarding/tests/test_observation_model.py -v`
Expected: FAIL with "No module named 'apps.core_onboarding.models.observation'"

**Step 3: Create OnboardingObservation model**

File: `apps/core_onboarding/models/observation.py`
```python
"""
Universal Observation Model for Multimodal Onboarding

Supports:
- Voice OR text input (user choice)
- 0 to N photos/videos per observation
- GPS location capture
- AI enhancement (LLM + Vision API)
- Entity extraction (NER)

Complies with Rule #7: Model < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantAwareModel


class OnboardingObservation(TenantAwareModel):
    """
    Universal observation for voice/text + media across all contexts.

    Input modes (mutually exclusive):
    - Voice: audio_file + original_transcript
    - Text: text_input only

    Media attachments (0 to N):
    - Photos, videos linked via ManyToMany
    - GPS captured per media
    """

    # Identifiers
    observation_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Context linkage
    context_type = models.CharField(
        _('Context Type'),
        max_length=20,
        choices=[
            ('CLIENT', _('Client Setup')),
            ('SITE', _('Site Survey')),
            ('WORKER', _('Worker Documents')),
        ]
    )
    context_object_id = models.CharField(
        _('Context Object ID'),
        max_length=100,
        help_text=_('UUID of related object')
    )

    # Conversation link (optional)
    conversation_session = models.ForeignKey(
        'core_onboarding.ConversationSession',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='observations'
    )

    # Voice input (Option 1: Voice OR text)
    audio_file = models.FileField(
        _('Audio File'),
        upload_to='observations/audio/',
        null=True,
        blank=True
    )
    original_transcript = models.TextField(
        _('Original Transcript'),
        blank=True,
        help_text=_('Raw speech-to-text output')
    )

    # Text input (Option 2: Voice OR text)
    text_input = models.TextField(
        _('Text Input'),
        blank=True,
        help_text=_('User-typed text (alternative to voice)')
    )

    # Enhanced by AI
    english_translation = models.TextField(
        _('English Translation'),
        blank=True
    )
    enhanced_observation = models.TextField(
        _('Enhanced Observation'),
        blank=True,
        help_text=_('LLM-enhanced version with context')
    )

    # Linked media (0 to N - ManyToMany for flexibility)
    media = models.ManyToManyField(
        'core_onboarding.OnboardingMedia',
        related_name='observations',
        blank=True,
        help_text=_('Photos/videos attached to this observation (0 to N)')
    )

    # Severity/classification
    severity = models.CharField(
        _('Severity'),
        max_length=20,
        choices=[
            ('CRITICAL', _('Critical Issue')),
            ('HIGH', _('High Priority')),
            ('MEDIUM', _('Medium Priority')),
            ('LOW', _('Low Priority')),
            ('INFO', _('Informational')),
        ],
        default='INFO'
    )
    confidence_score = models.FloatField(
        _('Confidence Score'),
        default=0.0,
        help_text=_('AI confidence (0.0-1.0)')
    )

    # Entity extraction (NER)
    entities = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Named entities: {"location": "Gate 3", "asset": "Camera #5"}')
    )

    # Metadata
    created_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.PROTECT,
        related_name='created_observations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_onboarding_observation'
        verbose_name = 'Onboarding Observation'
        verbose_name_plural = 'Onboarding Observations'
        indexes = [
            models.Index(fields=['context_type', 'context_object_id'], name='obs_context_idx'),
            models.Index(fields=['created_at'], name='obs_created_idx'),
            models.Index(fields=['severity'], name='obs_severity_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        input_type = 'Voice' if self.audio_file else 'Text'
        return f"{input_type} observation - {self.context_type} ({self.created_at})"

    def has_media(self) -> bool:
        """Check if observation has any media attachments"""
        return self.media.exists()

    def media_count(self) -> int:
        """Count of attached media"""
        return self.media.count()
```

**Step 4: Update models __init__.py**

File: `apps/core_onboarding/models/__init__.py`
```python
from .media import OnboardingMedia
from .observation import OnboardingObservation

__all__ = [
    'OnboardingMedia',
    'OnboardingObservation',
]
```

**Step 5: Validate syntax**

Run: `python3 -m py_compile apps/core_onboarding/models/observation.py`
Expected: No output (success)

**Step 6: Commit**

```bash
git add apps/core_onboarding/models/observation.py apps/core_onboarding/models/__init__.py apps/core_onboarding/tests/
git commit -m "feat(core): add OnboardingObservation model with 0-N media support"
```

---

### Task 7: Create ConversationSession model (extracted from apps/onboarding)

**Files:**
- Create: `apps/core_onboarding/models/conversation.py`
- Modify: `apps/onboarding/models/conversational_ai.py` (read source)

**Step 1: Read existing ConversationSession model**

Run: `cat apps/onboarding/models/conversational_ai.py | head -100`
Purpose: Understand current implementation before extraction

**Step 2: Create ConversationSession in core_onboarding**

File: `apps/core_onboarding/models/conversation.py`
```python
"""
Conversation Session Model - Shared Kernel

Tracks conversational onboarding sessions across ALL contexts:
- Client setup conversations
- Site survey conversations
- Worker intake conversations

Features:
- Voice OR text input mode
- Multi-language support
- State machine (7 states)
- Audio transcript storage
- Context routing

Extracted from: apps/onboarding/models/conversational_ai.py
Complies with Rule #7: Model < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantAwareModel


class ConversationSession(TenantAwareModel):
    """
    Conversation session for multimodal onboarding.

    Used by all three contexts:
    - CLIENT: "Help me set up a new client"
    - SITE: "I want to survey this site"
    - WORKER: "Onboard a new security guard"
    """

    class ConversationType(models.TextChoices):
        INITIAL_SETUP = 'INITIAL_SETUP', _('Initial Setup')
        CONFIG_UPDATE = 'CONFIG_UPDATE', _('Configuration Update')
        TROUBLESHOOTING = 'TROUBLESHOOTING', _('Troubleshooting')
        FEATURE_REQUEST = 'FEATURE_REQUEST', _('Feature Request')

    class CurrentState(models.TextChoices):
        STARTED = 'STARTED', _('Started')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        GENERATING_RECOMMENDATIONS = 'GENERATING_RECOMMENDATIONS', _('Generating Recommendations')
        AWAITING_USER_APPROVAL = 'AWAITING_USER_APPROVAL', _('Awaiting User Approval')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')
        ERROR = 'ERROR', _('Error')

    class ContextType(models.TextChoices):
        CLIENT = 'CLIENT', _('Client Onboarding')
        SITE = 'SITE', _('Site Survey')
        WORKER = 'WORKER', _('Worker Intake')

    # Identifiers
    session_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Context routing (NEW: determines which handler to use)
    context_type = models.CharField(
        _('Context Type'),
        max_length=20,
        choices=ContextType.choices,
        help_text=_('Which bounded context this conversation is for')
    )
    context_object_id = models.CharField(
        _('Context Object ID'),
        max_length=100,
        blank=True,
        help_text=_('ID of created object (site_id, request_id, client_id)')
    )
    handler_class = models.CharField(
        _('Handler Class'),
        max_length=200,
        blank=True,
        help_text=_('Fully qualified handler class name')
    )

    # Session details
    initiated_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='initiated_sessions'
    )
    conversation_type = models.CharField(
        _('Conversation Type'),
        max_length=20,
        choices=ConversationType.choices,
        default=ConversationType.INITIAL_SETUP
    )
    current_state = models.CharField(
        _('Current State'),
        max_length=30,
        choices=CurrentState.choices,
        default=CurrentState.STARTED
    )

    # Context data
    context_data = models.JSONField(
        default=dict,
        help_text=_('Initial context: {"client_id": "...", "language": "en"}')
    )
    collected_data = models.JSONField(
        default=dict,
        help_text=_('Accumulated data from conversation')
    )

    # Voice support
    voice_enabled = models.BooleanField(
        default=False,
        help_text=_('Voice input enabled for this session')
    )
    audio_transcripts = models.JSONField(
        default=list,
        help_text=_('Array of voice interactions: [{"user": "...", "assistant": "..."}]')
    )

    # Language
    language = models.CharField(
        _('Language'),
        max_length=10,
        default='en',
        help_text=_('ISO 639-1 language code')
    )

    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    last_interaction_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_onboarding_conversation'
        verbose_name = 'Conversation Session'
        verbose_name_plural = 'Conversation Sessions'
        indexes = [
            models.Index(fields=['context_type', 'current_state'], name='conv_context_state_idx'),
            models.Index(fields=['initiated_by'], name='conv_user_idx'),
            models.Index(fields=['started_at'], name='conv_started_idx'),
        ]
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.get_context_type_display()} - {self.get_current_state_display()}"
```

**Step 3: Update __init__.py**

File: `apps/core_onboarding/models/__init__.py`
```python
from .media import OnboardingMedia
from .observation import OnboardingObservation
from .conversation import ConversationSession

__all__ = [
    'OnboardingMedia',
    'OnboardingObservation',
    'ConversationSession',
]
```

**Step 4: Validate syntax**

Run: `python3 -m py_compile apps/core_onboarding/models/conversation.py`

**Step 5: Commit**

```bash
git add apps/core_onboarding/models/conversation.py apps/core_onboarding/models/__init__.py
git commit -m "feat(core): add ConversationSession model with context routing"
```

---

### Task 8: Extract remaining shared models to core_onboarding

**Files to extract from apps/onboarding/models/**:
- `ai_changeset.py` → `apps/core_onboarding/models/changeset.py`
- `classification.py` (TypeAssist, GeofenceMaster) → `apps/core_onboarding/models/classification.py`
- `conversational_ai.py` (LLMRecommendation, AuthoritativeKnowledge) → `apps/core_onboarding/models/knowledge.py`
- `knowledge_source.py` → `apps/core_onboarding/models/knowledge_source.py`
- `knowledge_ingestion_job.py` → `apps/core_onboarding/models/ingestion.py`
- `knowledge_review.py` → `apps/core_onboarding/models/review.py`

**Step 1: Copy ai_changeset.py**

```bash
cp apps/onboarding/models/ai_changeset.py apps/core_onboarding/models/changeset.py
```

**Step 2: Update imports in changeset.py**

File: `apps/core_onboarding/models/changeset.py`

Find and replace:
- OLD: `class AIChangeSet(TenantAwareModel):`
- NEW: (keep as-is, just verify imports)

**Step 3: Copy classification.py**

```bash
cp apps/onboarding/models/classification.py apps/core_onboarding/models/classification.py
```

**Step 4: Extract LLMRecommendation and AuthoritativeKnowledge**

Read: `apps/onboarding/models/conversational_ai.py` lines 139-324
Copy to: `apps/core_onboarding/models/knowledge.py`

Update foreign keys:
- OLD: `conversation_session = models.ForeignKey('onboarding.ConversationSession', ...)`
- NEW: `conversation_session = models.ForeignKey('core_onboarding.ConversationSession', ...)`

**Step 5: Copy remaining knowledge models**

```bash
cp apps/onboarding/models/knowledge_source.py apps/core_onboarding/models/knowledge_source.py
cp apps/onboarding/models/knowledge_ingestion_job.py apps/core_onboarding/models/ingestion.py
cp apps/onboarding/models/knowledge_review.py apps/core_onboarding/models/review.py
```

**Step 6: Update core_onboarding models __init__.py**

File: `apps/core_onboarding/models/__init__.py`
```python
from .media import OnboardingMedia
from .observation import OnboardingObservation
from .conversation import ConversationSession
from .knowledge import LLMRecommendation, AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
from .changeset import AIChangeSet, AIChangeRecord, ChangeSetApproval
from .classification import TypeAssist, GeofenceMaster
from .knowledge_source import KnowledgeSource
from .ingestion import KnowledgeIngestionJob
from .review import KnowledgeReview

__all__ = [
    'OnboardingMedia',
    'OnboardingObservation',
    'ConversationSession',
    'LLMRecommendation',
    'AuthoritativeKnowledge',
    'AuthoritativeKnowledgeChunk',
    'AIChangeSet',
    'AIChangeRecord',
    'ChangeSetApproval',
    'TypeAssist',
    'GeofenceMaster',
    'KnowledgeSource',
    'KnowledgeIngestionJob',
    'KnowledgeReview',
]
```

**Step 7: Validate all model files**

```bash
for file in apps/core_onboarding/models/*.py; do
    python3 -m py_compile "$file" || echo "Failed: $file"
done
```

Expected: All files compile successfully

**Step 8: Commit**

```bash
git add apps/core_onboarding/models/
git commit -m "feat(core): extract shared kernel models from apps/onboarding"
```

---

## BATCH 3: Client Context Models (Tasks 9-11)

### Task 9: Extract BusinessUnit model to client_onboarding

**Files:**
- Copy: `apps/onboarding/models/business_unit.py` → `apps/client_onboarding/models/business_unit.py`
- Modify: Update imports and table name

**Step 1: Copy business_unit.py**

```bash
cp apps/onboarding/models/business_unit.py apps/client_onboarding/models/business_unit.py
```

**Step 2: Update table name and imports**

File: `apps/client_onboarding/models/business_unit.py`

Find: `db_table = 'onboarding_bt'`
Replace: `db_table = 'client_onboarding_businessunit'`

Find: `from apps.onboarding.models import TypeAssist`
Replace: `from apps.core_onboarding.models import TypeAssist`

**Step 3: Update model __init__.py**

File: `apps/client_onboarding/models/__init__.py`
```python
from .business_unit import Bt

__all__ = ['Bt']
```

**Step 4: Validate syntax**

Run: `python3 -m py_compile apps/client_onboarding/models/business_unit.py`

**Step 5: Commit**

```bash
git add apps/client_onboarding/models/
git commit -m "feat(client): extract BusinessUnit (Bt) model to client context"
```

---

### Task 10: Extract Contract and Subscription models

**Files:**
- Read: Search for Contract and Subscription models
- Extract: If found, move to client_onboarding

**Step 1: Search for Contract model**

```bash
grep -r "class Contract" apps/onboarding/ --include="*.py"
```

**Step 2: Search for Subscription model**

```bash
grep -r "class Subscription" apps/onboarding/ --include="*.py"
```

**Step 3: If found, extract to client_onboarding/models/**

If Contract exists:
```bash
# Find the file, copy to apps/client_onboarding/models/contract.py
# Update imports and table name
```

**Step 4: If not found, create placeholder**

This may be future work - skip if models don't exist

**Step 5: Commit (if changes made)**

```bash
git add apps/client_onboarding/models/
git commit -m "feat(client): extract contract/subscription models if present"
```

---

### Task 11: Extract Shift model to client_onboarding

**Files:**
- Copy: `apps/onboarding/models/scheduling.py` → `apps/client_onboarding/models/shift.py`

**Step 1: Copy scheduling.py**

```bash
cp apps/onboarding/models/scheduling.py apps/client_onboarding/models/shift.py
```

**Step 2: Update table name**

File: `apps/client_onboarding/models/shift.py`

Find: `db_table = 'onboarding_shift'`
Replace: `db_table = 'client_onboarding_shift'`

**Step 3: Update __init__.py**

File: `apps/client_onboarding/models/__init__.py`
```python
from .business_unit import Bt
from .shift import Shift

__all__ = ['Bt', 'Shift']
```

**Step 4: Commit**

```bash
git add apps/client_onboarding/models/shift.py apps/client_onboarding/models/__init__.py
git commit -m "feat(client): add Shift model to client context"
```

---

## BATCH 4: Site Context Models (Tasks 12-15)

### Task 12: Extract OnboardingSite and OnboardingZone models

**Files:**
- Read: `apps/onboarding/models/site_onboarding.py` (848 lines, multiple classes)
- Extract: OnboardingSite → `apps/site_onboarding/models/site.py`
- Extract: OnboardingZone → `apps/site_onboarding/models/zone.py`

**Step 1: Read site_onboarding.py to understand structure**

Run: `wc -l apps/onboarding/models/site_onboarding.py`
Run: `grep "^class " apps/onboarding/models/site_onboarding.py`

**Step 2: Extract OnboardingSite class**

File: `apps/site_onboarding/models/site.py`

Copy from apps/onboarding/models/site_onboarding.py (OnboardingSite class only)

Update:
- Table name: `db_table = 'site_onboarding_site'`
- Import: `from apps.client_onboarding.models import Bt`
- Import: `from apps.core_onboarding.models import ConversationSession`

**Step 3: Extract OnboardingZone class**

File: `apps/site_onboarding/models/zone.py`

Copy from apps/onboarding/models/site_onboarding.py (OnboardingZone class only)

Update:
- Table name: `db_table = 'site_onboarding_zone'`
- Import: `from .site import OnboardingSite`

**Step 4: Update __init__.py**

File: `apps/site_onboarding/models/__init__.py`
```python
from .site import OnboardingSite
from .zone import OnboardingZone

__all__ = [
    'OnboardingSite',
    'OnboardingZone',
]
```

**Step 5: Validate syntax**

```bash
python3 -m py_compile apps/site_onboarding/models/site.py
python3 -m py_compile apps/site_onboarding/models/zone.py
```

**Step 6: Commit**

```bash
git add apps/site_onboarding/models/
git commit -m "feat(site): extract OnboardingSite and OnboardingZone models"
```

---

### Task 13: Extract Observation, Asset, Checkpoint models

**Files:**
- Extract from: `apps/onboarding/models/site_onboarding.py`
- Create: `apps/site_onboarding/models/asset.py`
- Create: `apps/site_onboarding/models/checkpoint.py`

**Note**: Observation is now in core_onboarding as OnboardingObservation.
Old site-specific Observation will be migrated to use OnboardingObservation.

**Step 1: Extract Asset class**

File: `apps/site_onboarding/models/asset.py`

Copy Asset class from site_onboarding.py

Update:
- Table name: `db_table = 'site_onboarding_asset'`
- Import: `from .zone import OnboardingZone`

**Step 2: Extract Checkpoint class**

File: `apps/site_onboarding/models/checkpoint.py`

Copy Checkpoint class

Update:
- Table name: `db_table = 'site_onboarding_checkpoint'`
- Import: `from .zone import OnboardingZone`

**Step 3: Extract MeterPoint class**

File: `apps/site_onboarding/models/meter_point.py`

Copy MeterPoint class

Update table name

**Step 4: Update __init__.py**

File: `apps/site_onboarding/models/__init__.py`
```python
from .site import OnboardingSite
from .zone import OnboardingZone
from .asset import Asset
from .checkpoint import Checkpoint
from .meter_point import MeterPoint

__all__ = [
    'OnboardingSite',
    'OnboardingZone',
    'Asset',
    'Checkpoint',
    'MeterPoint',
]
```

**Step 5: Commit**

```bash
git add apps/site_onboarding/models/
git commit -m "feat(site): add Asset, Checkpoint, MeterPoint models"
```

---

### Task 14: Extract SOP and CoveragePlan models

**Files:**
- Extract: SOP → `apps/site_onboarding/models/sop.py`
- Extract: CoveragePlan → `apps/site_onboarding/models/coverage_plan.py`

**Step 1: Extract SOP class**

File: `apps/site_onboarding/models/sop.py`

Copy from site_onboarding.py

Update:
- Table name: `db_table = 'site_onboarding_sop'`
- Imports

**Step 2: Extract CoveragePlan class**

File: `apps/site_onboarding/models/coverage_plan.py`

Copy from site_onboarding.py

Update table name

**Step 3: Update __init__.py**

File: `apps/site_onboarding/models/__init__.py`
```python
from .site import OnboardingSite
from .zone import OnboardingZone
from .asset import Asset
from .checkpoint import Checkpoint
from .meter_point import MeterPoint
from .sop import SOP
from .coverage_plan import CoveragePlan

__all__ = [
    'OnboardingSite',
    'OnboardingZone',
    'Asset',
    'Checkpoint',
    'MeterPoint',
    'SOP',
    'CoveragePlan',
]
```

**Step 4: Commit**

```bash
git add apps/site_onboarding/models/
git commit -m "feat(site): add SOP and CoveragePlan models"
```

---

### Task 15: Create SitePhoto and SiteVideo wrappers

**Files:**
- Create: `apps/site_onboarding/models/site_media.py`

**Step 1: Create SitePhoto model**

File: `apps/site_onboarding/models/site_media.py`
```python
"""
Site-specific media wrappers for OnboardingMedia.

Links universal media storage to site-specific types and zones.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantAwareModel


class SitePhoto(TenantAwareModel):
    """
    Site-specific photo wrapper.
    Links OnboardingMedia to sites/zones with photo type classification.
    """

    class PhotoType(models.TextChoices):
        ZONE_OVERVIEW = 'ZONE_OVERVIEW', _('Zone Overview')
        ASSET = 'ASSET', _('Security Asset')
        VULNERABILITY = 'VULNERABILITY', _('Security Vulnerability')
        CHECKPOINT = 'CHECKPOINT', _('Checkpoint Location')
        ENTRY_EXIT = 'ENTRY_EXIT', _('Entry/Exit Point')
        EMERGENCY = 'EMERGENCY', _('Emergency Equipment')
        PERIMETER = 'PERIMETER', _('Perimeter View')
        INTERIOR = 'INTERIOR', _('Interior Space')

    photo_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    site = models.ForeignKey(
        'site_onboarding.OnboardingSite',
        on_delete=models.CASCADE,
        related_name='photos'
    )
    zone = models.ForeignKey(
        'site_onboarding.OnboardingZone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='photos'
    )
    media = models.OneToOneField(
        'core_onboarding.OnboardingMedia',
        on_delete=models.CASCADE
    )

    # Classification
    photo_type = models.CharField(
        _('Photo Type'),
        max_length=20,
        choices=PhotoType.choices
    )

    # Additional metadata
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'site_onboarding_photo'
        verbose_name = 'Site Photo'
        verbose_name_plural = 'Site Photos'
        ordering = ['-media__uploaded_at']

    def __str__(self):
        return f"{self.get_photo_type_display()} - {self.site.name}"


class SiteVideo(TenantAwareModel):
    """
    Site-specific video wrapper.
    """

    class VideoType(models.TextChoices):
        ZONE_WALKTHROUGH = 'ZONE_WALKTHROUGH', _('Zone Walkthrough')
        CAMERA_COVERAGE = 'CAMERA_COVERAGE', _('Camera Coverage Test')
        VULNERABILITY_DEMO = 'VULNERABILITY_DEMO', _('Vulnerability Demonstration')
        PATROL_ROUTE = 'PATROL_ROUTE', _('Patrol Route')
        EMERGENCY_PROCEDURE = 'EMERGENCY_PROCEDURE', _('Emergency Procedure')

    video_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    site = models.ForeignKey(
        'site_onboarding.OnboardingSite',
        on_delete=models.CASCADE,
        related_name='videos'
    )
    zone = models.ForeignKey(
        'site_onboarding.OnboardingZone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='videos'
    )
    media = models.OneToOneField(
        'core_onboarding.OnboardingMedia',
        on_delete=models.CASCADE
    )

    video_type = models.CharField(
        _('Video Type'),
        max_length=30,
        choices=VideoType.choices
    )

    duration_seconds = models.IntegerField(
        _('Duration (seconds)'),
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'site_onboarding_video'
        verbose_name = 'Site Video'
        verbose_name_plural = 'Site Videos'

    def __str__(self):
        return f"{self.get_video_type_display()} - {self.site.name}"
```

**Step 2: Update __init__.py**

File: `apps/site_onboarding/models/__init__.py`

Add imports:
```python
from .site_media import SitePhoto, SiteVideo
```

Add to __all__

**Step 3: Commit**

```bash
git add apps/site_onboarding/models/site_media.py apps/site_onboarding/models/__init__.py
git commit -m "feat(site): add SitePhoto and SiteVideo media wrappers"
```

---

## BATCH 5: Worker Context Enhancement (Tasks 16-17)

### Task 16: Create WorkerDocument model

**Files:**
- Create: `apps/people_onboarding/models/worker_document.py`

**Step 1: Create WorkerDocument model**

File: `apps/people_onboarding/models/worker_document.py`
```python
"""
Worker document wrapper for OnboardingMedia.

Supports worker onboarding document types:
- Government IDs (front/back)
- Training certificates
- Background check results
- Medical clearance
- Reference letters
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import EnhancedTenantModel


class WorkerDocument(EnhancedTenantModel):
    """
    Worker onboarding document linked to OnboardingMedia.

    Supports 0-N documents per onboarding request.
    """

    class DocumentType(models.TextChoices):
        PHOTO_ID = 'PHOTO_ID', _('Government Photo ID')
        CERTIFICATE = 'CERTIFICATE', _('Training Certificate')
        BACKGROUND_CHECK = 'BACKGROUND_CHECK', _('Background Check Results')
        MEDICAL = 'MEDICAL', _('Medical Clearance')
        UNIFORM_PHOTO = 'UNIFORM_PHOTO', _('Uniform Photo')
        REFERENCE_LETTER = 'REFERENCE_LETTER', _('Reference Letter')
        POLICE_VERIFICATION = 'POLICE_VERIFICATION', _('Police Verification')
        ADDRESS_PROOF = 'ADDRESS_PROOF', _('Address Proof')

    class VerificationStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending Verification')
        VERIFIED = 'VERIFIED', _('Verified')
        REJECTED = 'REJECTED', _('Rejected')
        EXPIRED = 'EXPIRED', _('Expired')

    document_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    media = models.OneToOneField(
        'core_onboarding.OnboardingMedia',
        on_delete=models.CASCADE
    )

    # Classification
    document_type = models.CharField(
        _('Document Type'),
        max_length=30,
        choices=DocumentType.choices
    )

    # Verification
    verification_status = models.CharField(
        _('Verification Status'),
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )
    verified_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    # Expiry (for certificates)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Expiration date for certificates/clearances')
    )

    # Rejection reason
    rejection_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'people_onboarding_document'
        verbose_name = 'Worker Document'
        verbose_name_plural = 'Worker Documents'
        indexes = [
            models.Index(fields=['onboarding_request'], name='workerdoc_request_idx'),
            models.Index(fields=['verification_status'], name='workerdoc_status_idx'),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.onboarding_request.request_number}"
```

**Step 2: Update people_onboarding models __init__.py**

File: `apps/people_onboarding/models/__init__.py`
```python
from .onboarding_request import OnboardingRequest
from .onboarding_task import OnboardingTask
from .worker_document import WorkerDocument

__all__ = [
    'OnboardingRequest',
    'OnboardingTask',
    'WorkerDocument',
]
```

**Step 3: Validate syntax**

Run: `python3 -m py_compile apps/people_onboarding/models/worker_document.py`

**Step 4: Commit**

```bash
git add apps/people_onboarding/models/
git commit -m "feat(worker): add WorkerDocument model for document uploads"
```

---

## BATCH 6: Service Layer (Tasks 18-21)

### Task 18: Create ClientService

**Files:**
- Create: `apps/client_onboarding/services/client_service.py`
- Create: `apps/client_onboarding/tests/test_client_service.py`

**Step 1: Write failing test**

File: `apps/client_onboarding/tests/test_client_service.py`
```python
import pytest
from apps.client_onboarding.services import ClientService


@pytest.mark.django_db
class TestClientService:

    def test_create_client_returns_uuid_string(self):
        """Test creating client returns UUID string, not model"""
        service = ClientService()

        client_id = service.create_client(
            name='Test Security Company',
            client_type='SECURITY_SERVICES',
            preferences={'timezone': 'Asia/Kolkata'}
        )

        # Should return string UUID, not model instance
        assert isinstance(client_id, str)
        assert len(client_id) == 36  # UUID format

    def test_get_client_details_returns_dict(self):
        """Test getting client returns dict, not model"""
        service = ClientService()

        client_id = service.create_client(
            name='Test Corp',
            client_type='CORPORATE',
            preferences={}
        )

        details = service.get_client_details(client_id)

        # Should return dict (DTO)
        assert isinstance(details, dict)
        assert details['id'] == client_id
        assert details['name'] == 'Test Corp'
        assert 'preferences' in details
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/client_onboarding/tests/test_client_service.py -v`
Expected: FAIL with "cannot import name 'ClientService'"

**Step 3: Create ClientService**

File: `apps/client_onboarding/services/client_service.py`
```python
"""
Client Onboarding Service - Public API

Provides bounded context interface for client operations.
Returns DTOs (dicts), not model instances.

Complies with Rule #7: Service methods < 150 lines
"""
from typing import Dict, List, Optional
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import ConversationSession


class ClientService:
    """
    Public service API for Client Onboarding context.

    All external access to client context goes through this service.
    Returns DTOs (dicts/strings), NOT Django model instances.
    """

    def create_client(
        self,
        name: str,
        client_type: str,
        preferences: dict,
        conversation_session_id: str = None,
        initial_media: List[str] = None
    ) -> str:
        """
        Create new client from conversation or direct API.

        Args:
            name: Client name
            client_type: Type of client
            preferences: Client preferences dict
            conversation_session_id: Optional conversation session UUID
            initial_media: List of OnboardingMedia UUIDs

        Returns:
            client_id (UUID string)
        """
        with transaction.atomic():
            # Create business unit
            bt = Bt.objects.create(
                buname=name,
                bucode=self._generate_bucode(name),
                bupreferences=preferences
            )

            # Link to conversation if provided
            if conversation_session_id:
                session = ConversationSession.objects.get(session_id=conversation_session_id)
                session.context_object_id = str(bt.id)
                session.save()

            return str(bt.id)

    def get_client_details(self, client_id: str) -> Dict:
        """
        Get client details as DTO.

        Args:
            client_id: Client UUID string

        Returns:
            Dict with client details
        """
        try:
            bt = Bt.objects.get(id=client_id)
        except ObjectDoesNotExist:
            raise ValidationError(f"Client not found: {client_id}")

        return {
            'id': str(bt.id),
            'code': bt.bucode,
            'name': bt.buname,
            'type': bt.butype.name if bt.butype else None,
            'preferences': bt.bupreferences or {},
            'created_at': bt.cdtz.isoformat() if bt.cdtz else None,
        }

    def update_client_preferences(
        self,
        client_id: str,
        preferences: dict
    ) -> Dict:
        """Update client preferences"""
        with transaction.atomic():
            bt = Bt.objects.select_for_update().get(id=client_id)
            bt.bupreferences = {**(bt.bupreferences or {}), **preferences}
            bt.save()

        return {'id': client_id, 'preferences': bt.bupreferences}

    def get_client_sites(self, client_id: str) -> List[str]:
        """
        Get list of site IDs for this client.

        Returns:
            List of site UUID strings (not model instances)
        """
        from apps.site_onboarding.models import OnboardingSite

        sites = OnboardingSite.objects.filter(
            business_unit_id=client_id
        ).values_list('site_id', flat=True)

        return [str(site_id) for site_id in sites]

    def _generate_bucode(self, name: str) -> str:
        """Generate unique business unit code from name"""
        import re
        # Take first 3 letters, uppercase, add counter
        code_base = re.sub(r'[^A-Z]', '', name.upper())[:3]
        counter = Bt.objects.filter(bucode__startswith=code_base).count() + 1
        return f"{code_base}{counter:03d}"
```

**Step 4: Update services __init__.py**

File: `apps/client_onboarding/services/__init__.py`
```python
from .client_service import ClientService

__all__ = ['ClientService']
```

**Step 5: Run test to verify it passes**

Run: `pytest apps/client_onboarding/tests/test_client_service.py -v`
Expected: May still fail due to missing migrations, but imports should work

**Step 6: Commit**

```bash
git add apps/client_onboarding/services/ apps/client_onboarding/tests/
git commit -m "feat(client): add ClientService with DTO-based public API"
```

---

### Task 19: Create SiteService

**Files:**
- Create: `apps/site_onboarding/services/site_service.py`
- Create: `apps/site_onboarding/tests/test_site_service.py`

**Step 1: Write failing test**

File: `apps/site_onboarding/tests/test_site_service.py`
```python
import pytest
from apps.site_onboarding.services import SiteService


@pytest.mark.django_db
class TestSiteService:

    def test_create_site_returns_uuid(self):
        """Test creating site returns UUID string"""
        from apps.client_onboarding.services import ClientService

        # Create client first
        client_service = ClientService()
        client_id = client_service.create_client(
            name='Test Client',
            client_type='CORPORATE',
            preferences={}
        )

        # Create site
        site_service = SiteService()
        site_id = site_service.create_site(
            client_id=client_id,
            name='Main Office',
            site_type='OFFICE'
        )

        assert isinstance(site_id, str)
        assert len(site_id) == 36

    def test_add_observation_with_zero_media(self):
        """Test adding text-only observation (0 media)"""
        site_service = SiteService()
        # ... test 0 media scenario

    def test_add_observation_with_multiple_media(self):
        """Test adding observation with N photos"""
        site_service = SiteService()
        # ... test N media scenario
```

**Step 2: Create SiteService (minimal implementation)**

File: `apps/site_onboarding/services/site_service.py`
```python
"""
Site Onboarding Service - Public API

Manages site surveys, zones, observations with multimodal capture.
"""
from typing import Dict, List
from django.db import transaction
from apps.site_onboarding.models import OnboardingSite, OnboardingZone
from apps.core_onboarding.models import ConversationSession, OnboardingObservation


class SiteService:
    """Public API for site onboarding context"""

    def create_site(
        self,
        client_id: str,
        name: str,
        site_type: str,
        conversation_session_id: str = None
    ) -> str:
        """
        Create new site for client.

        Args:
            client_id: Client UUID string (from client context)
            name: Site name
            site_type: Site type (OFFICE, WAREHOUSE, etc.)
            conversation_session_id: Optional conversation UUID

        Returns:
            site_id (UUID string)
        """
        with transaction.atomic():
            site = OnboardingSite.objects.create(
                business_unit_id=client_id,  # FK by ID
                name=name,
                site_type=site_type
            )

            # Link to conversation
            if conversation_session_id:
                session = ConversationSession.objects.get(session_id=conversation_session_id)
                session.context_object_id = str(site.site_id)
                session.save()

            return str(site.site_id)

    def add_observation(
        self,
        site_id: str,
        zone_id: str = None,
        observation_id: str = None,
        text_input: str = None,
        audio_file = None,
        media_ids: List[str] = None
    ) -> Dict:
        """
        Add observation to site with 0-N media attachments.

        Args:
            site_id: Site UUID
            zone_id: Optional zone UUID
            observation_id: Existing observation UUID, or create new
            text_input: Text description (if not voice)
            audio_file: Audio file (if not text)
            media_ids: List of OnboardingMedia UUIDs (0 to N)

        Returns:
            Dict with observation details
        """
        from apps.core_onboarding.models import OnboardingMedia

        if observation_id:
            obs = OnboardingObservation.objects.get(observation_id=observation_id)
        else:
            # Create new observation
            obs = OnboardingObservation.objects.create(
                context_type='SITE',
                context_object_id=site_id,
                text_input=text_input or '',
                audio_file=audio_file
            )

        # Link 0-N media
        if media_ids:
            media_objects = OnboardingMedia.objects.filter(media_id__in=media_ids)
            obs.media.add(*media_objects)

        return {
            'observation_id': str(obs.observation_id),
            'media_count': obs.media_count(),
            'has_media': obs.has_media()
        }
```

**Step 3: Update __init__.py**

File: `apps/site_onboarding/services/__init__.py`
```python
from .site_service import SiteService

__all__ = ['SiteService']
```

**Step 4: Commit**

```bash
git add apps/site_onboarding/services/ apps/site_onboarding/tests/
git commit -m "feat(site): add SiteService with multimodal observation support"
```

---

### Task 20: Create WorkerService

**Files:**
- Create: `apps/people_onboarding/services/worker_service.py`

**Step 1: Create WorkerService**

File: `apps/people_onboarding/services/worker_service.py`
```python
"""
Worker Onboarding Service - Public API

Manages worker intake, document verification, provisioning.
"""
from typing import Dict, List
from django.db import transaction
from apps.people_onboarding.models import OnboardingRequest, OnboardingTask, WorkerDocument


class WorkerService:
    """Public API for worker onboarding context"""

    def create_onboarding_request(
        self,
        person_type: str,
        client_id: str,
        site_id: str = None,
        conversation_session_id: str = None
    ) -> str:
        """
        Create worker onboarding request.

        Args:
            person_type: EMPLOYEE_FULLTIME, CONTRACTOR, etc.
            client_id: Client UUID (employer)
            site_id: Optional site UUID (assignment)
            conversation_session_id: Optional conversation UUID

        Returns:
            request_id (UUID string)
        """
        from apps.core_onboarding.models import ConversationSession

        with transaction.atomic():
            request = OnboardingRequest.objects.create(
                person_type=person_type,
                current_state='DRAFT'
            )

            # Store context
            request.context_data = {
                'client_id': client_id,
                'site_id': site_id
            }
            request.save()

            # Link conversation
            if conversation_session_id:
                session = ConversationSession.objects.get(session_id=conversation_session_id)
                request.conversation_session = session
                session.context_object_id = str(request.uuid)
                session.save()
                request.save()

            return str(request.uuid)

    def upload_document(
        self,
        request_id: str,
        document_type: str,
        media_id: str
    ) -> Dict:
        """
        Attach document to worker onboarding.

        Args:
            request_id: OnboardingRequest UUID
            document_type: PHOTO_ID, CERTIFICATE, etc.
            media_id: OnboardingMedia UUID

        Returns:
            Dict with document details
        """
        doc = WorkerDocument.objects.create(
            onboarding_request_id=request_id,
            document_type=document_type,
            media_id=media_id,
            verification_status='PENDING'
        )

        return {
            'document_id': str(doc.document_id),
            'type': document_type,
            'status': 'uploaded'
        }
```

**Step 2: Update __init__.py**

File: `apps/people_onboarding/services/__init__.py`
```python
from .worker_service import WorkerService

__all__ = ['WorkerService']
```

**Step 3: Commit**

```bash
git add apps/people_onboarding/services/
git commit -m "feat(worker): add WorkerService for worker intake operations"
```

---

### Task 21: Create MultimodalInputProcessor (core service)

**Files:**
- Create: `apps/core_onboarding/services/media/multimodal_processor.py`
- Create: `apps/core_onboarding/tests/test_multimodal_processor.py`

**Step 1: Write test**

File: `apps/core_onboarding/tests/test_multimodal_processor.py`
```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.core_onboarding.services.media import MultimodalInputProcessor


@pytest.mark.django_db
class TestMultimodalInputProcessor:

    def test_process_text_only_no_media(self, test_user):
        """Test text input with 0 media (minimum case)"""
        processor = MultimodalInputProcessor()

        result = processor.process_input(
            context_type='CLIENT',
            context_object_id='client-123',
            text_input='Client confirmed requirements',
            audio_file=None,
            photos=[],
            videos=[],
            created_by=test_user
        )

        assert result['observation_id'] is not None
        assert result['media_count'] == 0
        assert result['input_type'] == 'text'

    def test_process_voice_with_multiple_photos(self, test_user):
        """Test voice input with N photos"""
        processor = MultimodalInputProcessor()

        audio = SimpleUploadedFile("voice.mp3", b"audio data", content_type="audio/mp3")
        photos = [
            SimpleUploadedFile("photo1.jpg", b"image1", content_type="image/jpeg"),
            SimpleUploadedFile("photo2.jpg", b"image2", content_type="image/jpeg"),
            SimpleUploadedFile("photo3.jpg", b"image3", content_type="image/jpeg"),
        ]

        result = processor.process_input(
            context_type='SITE',
            context_object_id='site-789',
            text_input=None,
            audio_file=audio,
            photos=photos,
            videos=[],
            gps_location={'lat': 12.34, 'lng': 56.78},
            created_by=test_user
        )

        assert result['media_count'] == 3
        assert result['input_type'] == 'voice'

    def test_rejects_both_text_and_voice(self, test_user):
        """Test validation: cannot provide both text and voice"""
        processor = MultimodalInputProcessor()

        with pytest.raises(ValidationError, match='Provide text OR audio'):
            processor.process_input(
                context_type='SITE',
                context_object_id='site-123',
                text_input='Some text',
                audio_file=SimpleUploadedFile("voice.mp3", b"audio"),
                photos=[],
                videos=[],
                created_by=test_user
            )
```

**Step 2: Create MultimodalInputProcessor**

File: `apps/core_onboarding/services/media/multimodal_processor.py`
```python
"""
Multimodal Input Processor

Processes voice OR text + 0-N photos/videos for onboarding observations.
Works across all contexts (client, site, worker).

Features:
- Text OR voice input (validated)
- 0 to N media attachments (flexible)
- GPS location capture
- AI analysis (Vision API, speech-to-text, LLM enhancement)
- Security validation (file type, size, MIME)

Complies with Rule #7: Service < 150 lines
"""
from typing import Dict, List, Optional
from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError
from apps.core_onboarding.models import OnboardingMedia, OnboardingObservation
from apps.peoples.models import People


class MultimodalInputProcessor:
    """
    Processes multimodal input for onboarding observations.

    Input modes:
    - Text only (0 media)
    - Text + N photos/videos
    - Voice only (0 media)
    - Voice + N photos/videos

    NOT allowed:
    - Both text AND voice
    - Neither text NOR voice
    """

    def process_input(
        self,
        context_type: str,
        context_object_id: str,
        text_input: str = None,
        audio_file: UploadedFile = None,
        photos: List[UploadedFile] = None,
        videos: List[UploadedFile] = None,
        gps_location: Dict = None,
        created_by: People = None,
        conversation_session_id: str = None
    ) -> Dict:
        """
        Process multimodal input and create observation.

        Args:
            context_type: CLIENT, SITE, or WORKER
            context_object_id: UUID of related object
            text_input: Text description (if not voice)
            audio_file: Audio file (if not text)
            photos: List of 0-N photo files
            videos: List of 0-N video files
            gps_location: Optional {lat, lng, accuracy}
            created_by: User creating observation
            conversation_session_id: Optional conversation link

        Returns:
            Dict with observation_id, media_count, etc.
        """
        # Validation: Must have text OR audio (not both, not neither)
        has_text = bool(text_input and text_input.strip())
        has_audio = bool(audio_file)

        if has_text and has_audio:
            raise ValidationError("Provide text OR audio input, not both")
        if not has_text and not has_audio:
            raise ValidationError("Must provide either text or audio input")

        # Process media (0 to N)
        media_objects = []

        # Process photos
        for photo in (photos or []):
            media = OnboardingMedia.objects.create(
                context_type=context_type,
                context_object_id=context_object_id,
                media_type='PHOTO',
                file=photo,
                gps_latitude=gps_location.get('lat') if gps_location else None,
                gps_longitude=gps_location.get('lng') if gps_location else None,
                gps_accuracy=gps_location.get('accuracy') if gps_location else None,
                uploaded_by=created_by
            )
            media_objects.append(media)

        # Process videos
        for video in (videos or []):
            media = OnboardingMedia.objects.create(
                context_type=context_type,
                context_object_id=context_object_id,
                media_type='VIDEO',
                file=video,
                gps_latitude=gps_location.get('lat') if gps_location else None,
                gps_longitude=gps_location.get('lng') if gps_location else None,
                uploaded_by=created_by
            )
            media_objects.append(media)

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type=context_type,
            context_object_id=context_object_id,
            conversation_session_id=conversation_session_id,
            text_input=text_input if has_text else '',
            audio_file=audio_file if has_audio else None,
            created_by=created_by
        )

        # Link media (0 to N)
        if media_objects:
            observation.media.set(media_objects)

        return {
            'observation_id': str(observation.observation_id),
            'media_count': len(media_objects),
            'input_type': 'voice' if has_audio else 'text',
            'has_media': len(media_objects) > 0
        }
```

**Step 3: Update services __init__.py**

File: `apps/core_onboarding/services/media/__init__.py`
```python
from .multimodal_processor import MultimodalInputProcessor

__all__ = ['MultimodalInputProcessor']
```

**Step 4: Commit**

```bash
git add apps/site_onboarding/services/ apps/core_onboarding/services/media/
git commit -m "feat(core): add MultimodalInputProcessor for voice/text + 0-N media"
```

---

## BATCH 7: Background Tasks with Security Fixes (Tasks 22-25)

### Task 22: Move background tasks to core_onboarding with security fixes

**Files:**
- Move: `background_tasks/onboarding_base_task.py` → `apps/core_onboarding/background_tasks/base_task.py`
- Move: `background_tasks/onboarding_retry_strategies.py` → `apps/core_onboarding/background_tasks/retry_strategies.py`
- Move: `background_tasks/dead_letter_queue.py` → `apps/core_onboarding/background_tasks/dead_letter_queue.py` (with race condition fix)
- Move: `background_tasks/onboarding_tasks_phase2.py` → `apps/core_onboarding/background_tasks/conversation_tasks.py` (with SSRF and UUID fixes)

**Step 1: Move base_task.py**

```bash
cp background_tasks/onboarding_base_task.py apps/core_onboarding/background_tasks/base_task.py
```

**Step 2: Move retry_strategies.py**

```bash
cp background_tasks/onboarding_retry_strategies.py apps/core_onboarding/background_tasks/retry_strategies.py
```

**Step 3: Move dead_letter_queue.py WITH race condition fix**

```bash
cp background_tasks/dead_letter_queue.py apps/core_onboarding/background_tasks/dead_letter_queue.py
```

Note: This file already has the race condition fix from earlier (atomic Redis operations)

**Step 4: Move and rename onboarding_tasks_phase2.py WITH security fixes**

```bash
cp background_tasks/onboarding_tasks_phase2.py apps/core_onboarding/background_tasks/conversation_tasks.py
```

Note: This file already has:
- SSRF protection (validate_document_url function)
- UUID validation (_validate_knowledge_id function)
- Security fixes in ingest_document and refresh_documents tasks

**Step 5: Update imports in conversation_tasks.py**

File: `apps/core_onboarding/background_tasks/conversation_tasks.py`

Find and replace:
- OLD: `from apps.onboarding.models import ConversationSession`
- NEW: `from apps.core_onboarding.models import ConversationSession`

- OLD: `from apps.onboarding.models import AuthoritativeKnowledge`
- NEW: `from apps.core_onboarding.models import AuthoritativeKnowledge`

**Step 6: Update imports in base_task.py**

File: `apps/core_onboarding/background_tasks/base_task.py`

Find: `from background_tasks.onboarding_retry_strategies import`
Replace: `from apps.core_onboarding.background_tasks.retry_strategies import`

Find: `from background_tasks.dead_letter_queue import dlq_handler`
Replace: `from apps.core_onboarding.background_tasks.dead_letter_queue import dlq_handler`

**Step 7: Create __init__.py**

File: `apps/core_onboarding/background_tasks/__init__.py`
```python
from .base_task import OnboardingBaseTask
from .retry_strategies import (
    DATABASE_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    LLM_API_EXCEPTIONS,
    VALIDATION_EXCEPTIONS,
)
from .dead_letter_queue import dlq_handler

__all__ = [
    'OnboardingBaseTask',
    'DATABASE_EXCEPTIONS',
    'NETWORK_EXCEPTIONS',
    'LLM_API_EXCEPTIONS',
    'VALIDATION_EXCEPTIONS',
    'dlq_handler',
]
```

**Step 8: Validate all task files**

```bash
for file in apps/core_onboarding/background_tasks/*.py; do
    python3 -m py_compile "$file" || echo "Failed: $file"
done
```

**Step 9: Commit**

```bash
git add apps/core_onboarding/background_tasks/
git commit -m "feat(core): migrate background tasks with security fixes (SSRF, UUID, DLQ race)"
```

---

## BATCH 8: Update All Import Statements (Tasks 26-30)

### Task 26: Update imports in apps/onboarding_api/

**Files:**
- Modify: All files in `apps/onboarding_api/` that import from `apps.onboarding.models`

**Step 1: Find all import statements**

```bash
grep -r "from apps.onboarding.models import" apps/onboarding_api/ --include="*.py" -l | sort > /tmp/files_to_update.txt
cat /tmp/files_to_update.txt
```

**Step 2: Create update script**

File: `scripts/update_imports.py`
```python
#!/usr/bin/env python3
"""
Update imports from apps.onboarding.models to new contexts.

Mapping:
- Bt → apps.client_onboarding.models.Bt
- OnboardingSite → apps.site_onboarding.models.OnboardingSite
- ConversationSession → apps.core_onboarding.models.ConversationSession
- etc.
"""
import re
import sys
from pathlib import Path

IMPORT_MAPPINGS = {
    # Client context
    'Bt': 'apps.client_onboarding.models',
    'Shift': 'apps.client_onboarding.models',

    # Site context
    'OnboardingSite': 'apps.site_onboarding.models',
    'OnboardingZone': 'apps.site_onboarding.models',
    'Asset': 'apps.site_onboarding.models',
    'Checkpoint': 'apps.site_onboarding.models',
    'MeterPoint': 'apps.site_onboarding.models',
    'SOP': 'apps.site_onboarding.models',
    'CoveragePlan': 'apps.site_onboarding.models',
    'SitePhoto': 'apps.site_onboarding.models',
    'SiteVideo': 'apps.site_onboarding.models',

    # Core context (shared kernel)
    'ConversationSession': 'apps.core_onboarding.models',
    'OnboardingObservation': 'apps.core_onboarding.models',
    'OnboardingMedia': 'apps.core_onboarding.models',
    'LLMRecommendation': 'apps.core_onboarding.models',
    'AuthoritativeKnowledge': 'apps.core_onboarding.models',
    'AuthoritativeKnowledgeChunk': 'apps.core_onboarding.models',
    'AIChangeSet': 'apps.core_onboarding.models',
    'AIChangeRecord': 'apps.core_onboarding.models',
    'TypeAssist': 'apps.core_onboarding.models',
    'GeofenceMaster': 'apps.core_onboarding.models',
    'KnowledgeSource': 'apps.core_onboarding.models',
    'KnowledgeIngestionJob': 'apps.core_onboarding.models',
    'KnowledgeReview': 'apps.core_onboarding.models',

    # Worker context
    'OnboardingRequest': 'apps.people_onboarding.models',
    'OnboardingTask': 'apps.people_onboarding.models',
    'WorkerDocument': 'apps.people_onboarding.models',
}


def update_file_imports(filepath: Path) -> int:
    """Update imports in a single file. Returns number of changes."""
    content = filepath.read_text()
    original = content
    changes = 0

    # Pattern: from apps.onboarding.models import X, Y, Z
    pattern = r'from apps\.onboarding\.models import ([^;\n]+)'

    def replace_import(match):
        nonlocal changes
        imports_str = match.group(1)

        # Parse imported names
        imports = [i.strip() for i in imports_str.split(',')]

        # Group by destination module
        by_module = {}
        for imp in imports:
            # Handle "X as Y" syntax
            if ' as ' in imp:
                name = imp.split(' as ')[0].strip()
                alias = imp.split(' as ')[1].strip()
            else:
                name = imp.strip()
                alias = None

            dest_module = IMPORT_MAPPINGS.get(name, 'apps.onboarding.models')

            if dest_module not in by_module:
                by_module[dest_module] = []

            by_module[dest_module].append((name, alias))

        # Generate new import statements
        new_imports = []
        for module, items in sorted(by_module.items()):
            import_list = ', '.join(
                f"{name} as {alias}" if alias else name
                for name, alias in items
            )
            new_imports.append(f"from {module} import {import_list}")

        changes += 1
        return '\n'.join(new_imports)

    content = re.sub(pattern, replace_import, content)

    if content != original:
        filepath.write_text(content)
        return changes

    return 0


def main():
    files_to_update = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files_to_update:
        print("Usage: python scripts/update_imports.py <file1> <file2> ...")
        return

    total_changes = 0
    for filepath_str in files_to_update:
        filepath = Path(filepath_str)
        if filepath.exists():
            changes = update_file_imports(filepath)
            if changes > 0:
                print(f"✅ Updated {filepath}: {changes} import statements")
                total_changes += changes

    print(f"\nTotal: {total_changes} import statements updated across {len(files_to_update)} files")


if __name__ == '__main__':
    main()
```

**Step 3: Run update script on onboarding_api**

```bash
chmod +x scripts/update_imports.py
find apps/onboarding_api/ -name "*.py" -type f | xargs python3 scripts/update_imports.py
```

**Step 4: Verify no syntax errors**

```bash
find apps/onboarding_api/ -name "*.py" -type f | while read f; do
    python3 -m py_compile "$f" || echo "Error in $f"
done
```

**Step 5: Commit**

```bash
git add apps/onboarding_api/ scripts/update_imports.py
git commit -m "refactor: update imports in onboarding_api to new contexts"
```

---

### Task 27-30: Update imports in all other apps

**Repeat Task 26 pattern for**:
- Task 27: `apps/activity/`
- Task 28: `apps/peoples/`
- Task 29: `apps/attendance/`
- Task 30: All remaining apps

**Step 1: Update each app**

```bash
# For each app directory
for app in apps/*/; do
    find "$app" -name "*.py" -type f | xargs python3 scripts/update_imports.py
done
```

**Step 2: Update background_tasks/ (if any remaining files reference old imports)**

```bash
find background_tasks/ -name "*.py" -type f | xargs python3 scripts/update_imports.py
```

**Step 3: Verify all Python files compile**

```bash
find apps/ -name "*.py" -type f | while read f; do
    python3 -m py_compile "$f" 2>&1 | grep -v "^$" && echo "Error: $f"
done
```

Expected: No errors

**Step 4: Commit**

```bash
git add apps/ background_tasks/
git commit -m "refactor: update all imports to new bounded contexts (292+ files)"
```

---

## BATCH 9: Settings and URL Configuration (Tasks 31-33)

### Task 31: Update INSTALLED_APPS

**Files:**
- Modify: `intelliwiz_config/settings/base.py`

**Step 1: Read current INSTALLED_APPS**

Run: `grep -A 50 "INSTALLED_APPS = \[" intelliwiz_config/settings/base.py | head -60`

**Step 2: Update INSTALLED_APPS**

File: `intelliwiz_config/settings/base.py`

Find the INSTALLED_APPS list and modify:

Remove:
```python
'apps.onboarding',
'apps.onboarding_api',
```

Add (in appropriate location):
```python
# Onboarding - Bounded Contexts
'apps.core_onboarding',
'apps.client_onboarding',
'apps.site_onboarding',
'apps.people_onboarding',
```

**Step 3: Verify settings load**

Run: `python3 manage.py check --settings=intelliwiz_config.settings.base`
Expected: System check identified no issues

**Step 4: Commit**

```bash
git add intelliwiz_config/settings/base.py
git commit -m "refactor(settings): update INSTALLED_APPS for bounded contexts"
```

---

### Task 32: Update URL routing

**Files:**
- Modify: `intelliwiz_config/urls_optimized.py`
- Create: `apps/client_onboarding/urls.py`
- Create: `apps/site_onboarding/urls.py`
- Create: `apps/core_onboarding/urls.py`

**Step 1: Create client_onboarding URLs**

File: `apps/client_onboarding/urls.py`
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'client_onboarding'

router = DefaultRouter()
# Add viewsets here when created

urlpatterns = [
    path('api/', include(router.urls)),
]
```

**Step 2: Create site_onboarding URLs**

File: `apps/site_onboarding/urls.py`
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'site_onboarding'

router = DefaultRouter()

urlpatterns = [
    path('api/', include(router.urls)),
]
```

**Step 3: Create core_onboarding URLs**

File: `apps/core_onboarding/urls.py`
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'core_onboarding'

router = DefaultRouter()

urlpatterns = [
    path('api/', include(router.urls)),
]
```

**Step 4: Update main URLs**

File: `intelliwiz_config/urls_optimized.py`

Find the onboarding URL patterns and replace:

OLD:
```python
path('onboarding/', include('apps.onboarding.urls')),
path('api/onboarding/', include('apps.onboarding_api.urls')),
```

NEW:
```python
# Bounded Context APIs
path('api/v2/client-onboarding/', include('apps.client_onboarding.urls')),
path('api/v2/site-onboarding/', include('apps.site_onboarding.urls')),
path('api/v2/worker-onboarding/', include('apps.people_onboarding.urls')),
path('api/v2/conversation/', include('apps.core_onboarding.urls')),
```

**Step 5: Verify URL configuration**

Run: `python3 manage.py show_urls | grep onboarding`
Expected: New URL patterns shown

**Step 6: Commit**

```bash
git add apps/*/urls.py intelliwiz_config/urls_optimized.py
git commit -m "refactor(urls): add context-specific URL routing"
```

---

## BATCH 10: Database Migrations (Tasks 33-36)

### Task 33: Create initial migrations for core_onboarding

**Files:**
- Create: `apps/core_onboarding/migrations/0001_initial.py`

**Step 1: Generate migration**

```bash
python3 manage.py makemigrations core_onboarding
```

Expected: Creates 0001_initial.py with all shared models

**Step 2: Review migration**

Run: `cat apps/core_onboarding/migrations/0001_initial.py | head -50`

Verify it includes:
- OnboardingMedia
- OnboardingObservation
- ConversationSession
- LLMRecommendation
- AuthoritativeKnowledge
- AIChangeSet
- TypeAssist
- etc.

**Step 3: Commit**

```bash
git add apps/core_onboarding/migrations/
git commit -m "migration(core): create initial migration for shared kernel"
```

---

### Task 34: Create migrations for client_onboarding

**Step 1: Generate migration**

```bash
python3 manage.py makemigrations client_onboarding
```

**Step 2: Review and commit**

```bash
git add apps/client_onboarding/migrations/
git commit -m "migration(client): create initial migration for client context"
```

---

### Task 35: Create migrations for site_onboarding

**Step 1: Generate migration**

```bash
python3 manage.py makemigrations site_onboarding
```

**Step 2: Review and commit**

```bash
git add apps/site_onboarding/migrations/
git commit -m "migration(site): create initial migration for site context"
```

---

### Task 36: Create migration for people_onboarding (WorkerDocument)

**Step 1: Generate migration**

```bash
python3 manage.py makemigrations people_onboarding
```

**Step 2: Review and commit**

```bash
git add apps/people_onboarding/migrations/
git commit -m "migration(worker): add WorkerDocument model migration"
```

---

## BATCH 11: Delete Old Apps (Tasks 37-38)

### Task 37: Delete apps/onboarding/ completely

**Files:**
- Delete: `apps/onboarding/` (entire directory)

**Step 1: Verify all models extracted**

Run these checks to ensure nothing is left behind:

```bash
# Check no remaining imports
grep -r "from apps.onboarding.models import" apps/ --include="*.py" && echo "❌ Found remaining imports!" || echo "✅ All imports updated"

# Check no remaining foreign keys to old tables
grep -r "onboarding\." apps/ --include="*.py" | grep -v "client_onboarding\|site_onboarding\|people_onboarding\|core_onboarding" || echo "✅ No old FK references"
```

**Step 2: Delete apps/onboarding/**

```bash
git rm -r apps/onboarding/
```

**Step 3: Commit**

```bash
git commit -m "refactor: delete apps/onboarding/ (extracted to bounded contexts)"
```

---

### Task 38: Delete apps/onboarding_api/ (move functionality to contexts)

**Files:**
- Delete: `apps/onboarding_api/` after moving functionality

**Step 1: Verify services moved to core_onboarding**

Check that all needed services are in:
- `apps/core_onboarding/services/llm/`
- `apps/core_onboarding/services/knowledge/`
- `apps/core_onboarding/services/translation/`

**Step 2: Move any remaining views**

If any views in apps/onboarding_api/views/ are still needed:
```bash
cp apps/onboarding_api/views/*.py apps/core_onboarding/views/
```

**Step 3: Delete apps/onboarding_api/**

```bash
git rm -r apps/onboarding_api/
```

**Step 4: Commit**

```bash
git commit -m "refactor: delete apps/onboarding_api/ (moved to core_onboarding)"
```

---

## BATCH 12: Testing (Tasks 39-42)

### Task 39: Run model tests

**Step 1: Run core_onboarding model tests**

Run: `pytest apps/core_onboarding/tests/test_media_model.py apps/core_onboarding/tests/test_observation_model.py -v`

**Step 2: Run client tests**

Run: `pytest apps/client_onboarding/tests/ -v`

**Step 3: Run site tests**

Run: `pytest apps/site_onboarding/tests/ -v`

**Step 4: Run worker tests**

Run: `pytest apps/people_onboarding/tests/ -v`

**Step 5: Fix any failures**

For each failure:
- Investigate root cause
- Fix model/service/test
- Re-run tests
- Commit fix

---

### Task 40: Run integration tests

**Step 1: Create integration test**

File: `apps/core_onboarding/tests/test_cross_context_integration.py`
```python
"""
Integration tests for cross-context operations.

Tests complete flow:
1. Create client (client context)
2. Create site for client (site context)
3. Create worker for site (worker context)
4. Add observations with media to each
"""
import pytest
from apps.client_onboarding.services import ClientService
from apps.site_onboarding.services import SiteService
from apps.people_onboarding.services import WorkerService
from apps.core_onboarding.services.media import MultimodalInputProcessor


@pytest.mark.django_db
class TestCrossContextIntegration:

    def test_complete_onboarding_flow(self, test_user):
        """Test full onboarding: client → site → worker"""

        # Step 1: Create client
        client_service = ClientService()
        client_id = client_service.create_client(
            name='Test Security Corp',
            client_type='SECURITY_SERVICES',
            preferences={'timezone': 'Asia/Kolkata'}
        )
        assert client_id is not None

        # Step 2: Create site for client
        site_service = SiteService()
        site_id = site_service.create_site(
            client_id=client_id,
            name='Downtown Office',
            site_type='OFFICE'
        )
        assert site_id is not None

        # Step 3: Create worker onboarding
        worker_service = WorkerService()
        request_id = worker_service.create_onboarding_request(
            person_type='EMPLOYEE_FULLTIME',
            client_id=client_id,
            site_id=site_id
        )
        assert request_id is not None

        # Step 4: Add observations with media
        processor = MultimodalInputProcessor()

        # Text observation with 0 media
        result1 = processor.process_input(
            context_type='CLIENT',
            context_object_id=client_id,
            text_input='Client confirmed 24/7 security needed',
            photos=[],
            videos=[],
            created_by=test_user
        )
        assert result1['media_count'] == 0

        # Verify cross-context relationships
        client_details = client_service.get_client_details(client_id)
        site_ids = client_service.get_client_sites(client_id)

        assert site_id in site_ids
        assert client_details['id'] == client_id
```

**Step 2: Run integration tests**

Run: `pytest apps/core_onboarding/tests/test_cross_context_integration.py -v`

**Step 3: Fix any failures and commit**

---

### Task 41: Run full test suite

**Step 1: Run all tests**

```bash
python3 -m pytest apps/core_onboarding/ apps/client_onboarding/ apps/site_onboarding/ apps/people_onboarding/ -v --tb=short
```

**Step 2: Check coverage**

```bash
python3 -m pytest apps/core_onboarding/ apps/client_onboarding/ apps/site_onboarding/ apps/people_onboarding/ --cov=apps.core_onboarding --cov=apps.client_onboarding --cov=apps.site_onboarding --cov=apps.people_onboarding --cov-report=term-missing
```

Target: >80% coverage

**Step 3: Fix all failures**

Systematically fix each failure until all tests pass

**Step 4: Commit**

```bash
git add apps/
git commit -m "test: fix all test failures after refactoring"
```

---

## BATCH 13: Final Verification (Tasks 42-45)

### Task 42: Verify no remaining references to apps/onboarding

**Step 1: Search for old imports**

```bash
grep -r "from apps\.onboarding\.models import" apps/ --include="*.py" && echo "❌ Found old imports!" || echo "✅ All imports updated"
```

**Step 2: Search for old app references**

```bash
grep -r "apps\.onboarding\." apps/ --include="*.py" | grep -v "client_onboarding\|site_onboarding\|people_onboarding\|core_onboarding" || echo "✅ No old app references"
```

**Step 3: Search for old table names in migrations**

```bash
grep -r "onboarding_bt" apps/*/migrations/ --include="*.py" && echo "Found old table references" || echo "✅ Clean"
```

**Step 4: If any found, fix them**

Update any remaining references using the import mapping script

---

### Task 43: Run Django system checks

**Step 1: Run full system check**

```bash
python3 manage.py check
```

Expected: System check identified no issues (0 errors, 0 warnings)

**Step 2: Check migrations**

```bash
python3 manage.py makemigrations --check --dry-run
```

Expected: No changes detected

**Step 3: If issues found, fix them**

Common issues:
- Missing foreign key migrations
- Incorrect table names
- Missing indexes

---

### Task 44: Update documentation

**Files:**
- Update: `CLAUDE.md`
- Update: `docs/architecture/SYSTEM_ARCHITECTURE.md`
- Create: `apps/client_onboarding/README.md`
- Create: `apps/site_onboarding/README.md`
- Create: `apps/core_onboarding/README.md`

**Step 1: Update CLAUDE.md**

File: `CLAUDE.md`

Find "Core Business Domains" section and update:

```markdown
### Core Business Domains

| Domain | Primary Apps | Purpose |
|--------|-------------|---------|
| **Client Management** | `client_onboarding` | Business relationships, contracts |
| **Site Operations** | `site_onboarding` | Physical location surveys, SOPs |
| **Worker Management** | `people_onboarding` | Worker intake, provisioning |
| **Onboarding Platform** | `core_onboarding` | Multimodal voice/media, AI orchestration |
```

**Step 2: Create context README files**

File: `apps/client_onboarding/README.md`
```markdown
# Client Onboarding Context

## Purpose
Manage business relationships and client setup for facility management.

## Bounded Models
- **BusinessUnit (Bt)**: Client hierarchy (parent-child relationships)
- **Contract**: Service agreements
- **Subscription**: Billing and subscription management
- **Shift**: Work shift definitions

## Public API
- **ClientService**: Create clients, update preferences, get site lists

## Dependencies
- **Upstream**: None (entry point for onboarding)
- **Downstream**: Site context (clients have sites)
- **Shared Kernel**: ConversationSession, TypeAssist, OnboardingObservation

## Multimodal Support
- Voice OR text for client setup conversations
- Photos: Office exterior, signage, facilities
- Videos: Office tours, facility walkthroughs
```

**Step 3: Commit**

```bash
git add CLAUDE.md apps/*/README.md docs/
git commit -m "docs: update documentation for bounded contexts"
```

---

### Task 45: Final validation and summary

**Step 1: Run complete test suite**

```bash
python3 -m pytest --tb=short -v
```

Target: All tests passing

**Step 2: Run Django checks**

```bash
python3 manage.py check
python3 manage.py check --deploy
```

**Step 3: Verify app structure**

```bash
ls -la apps/ | grep onboarding
```

Expected output:
```
client_onboarding/
core_onboarding/
people_onboarding/
site_onboarding/
```

NOT expected:
```
onboarding/        # Should be deleted
onboarding_api/    # Should be deleted
```

**Step 4: Create summary**

File: `BOUNDED_CONTEXTS_REFACTORING_COMPLETE.md`

```markdown
# Bounded Contexts Refactoring - Completion Report

**Date**: November 3, 2025
**Branch**: refactor/bounded-contexts-multimodal
**Type**: Big Bang Architecture Refactoring

## Summary

Successfully refactored monolithic `apps/onboarding/` into 3 bounded contexts with shared multimodal platform.

### New Structure

- ✅ `apps/client_onboarding/` - Business relationships (Bt, Contract, Shift)
- ✅ `apps/site_onboarding/` - Physical location surveys (Site, Zone, Asset, SOP)
- ✅ `apps/people_onboarding/` - Worker intake (enhanced with WorkerDocument)
- ✅ `apps/core_onboarding/` - Shared voice/media/AI platform

### Deleted

- ❌ `apps/onboarding/` - Completely removed
- ❌ `apps/onboarding_api/` - Moved to core_onboarding

### Security Fixes Included

- ✅ SSRF protection in document fetching
- ✅ UUID validation for knowledge_ids
- ✅ DLQ race condition fix with atomic Redis operations

### Statistics

- **Apps created**: 3 (client_onboarding, site_onboarding, core_onboarding)
- **Apps enhanced**: 1 (people_onboarding)
- **Apps deleted**: 2 (onboarding, onboarding_api)
- **Models migrated**: 12+
- **Import statements updated**: 292+
- **Tests passing**: X/X
- **Test coverage**: >80%

### Multimodal Capabilities

**All contexts support**:
- Voice OR text input (user choice)
- 0 to N photos per observation
- 0 to N videos per observation
- GPS location capture
- AI analysis (Vision API + LLM)

### Next Steps

1. Review this branch
2. Run full test suite in CI/CD
3. Merge to main
4. Deploy to staging
5. Run smoke tests
6. Deploy to production
```

**Step 5: Final commit**

```bash
git add BOUNDED_CONTEXTS_REFACTORING_COMPLETE.md
git commit -m "docs: refactoring completion report"
```

---

## Execution Notes

### Critical Reminders

1. **This is Big Bang**: All changes at once, no backward compatibility
2. **Security fixes included**: SSRF, UUID validation, DLQ race condition
3. **Test after each batch**: Run `python3 -m py_compile` on modified files
4. **Commit frequently**: After each task (45+ commits total)
5. **292+ import statements**: Use automated script (Task 26-30)

### Estimated Timeline

- **Batch 1-2** (App structures + core models): 2-3 days
- **Batch 3-4** (Context models): 2-3 days
- **Batch 5-6** (Worker + Services): 2-3 days
- **Batch 7-8** (Background tasks + Imports): 3-4 days
- **Batch 9-10** (Settings + Migrations): 1-2 days
- **Batch 11-13** (Delete + Test + Verify): 2-3 days

**Total**: 12-18 days (2-3 weeks)

### Success Criteria

- [ ] All tests passing
- [ ] `apps/onboarding/` deleted
- [ ] `apps/onboarding_api/` deleted
- [ ] 4 new apps created
- [ ] 292+ imports updated
- [ ] Security fixes included
- [ ] Multimodal support working (voice OR text + 0-N media)
- [ ] Django check passes
- [ ] Documentation updated

---

## Post-Implementation

After completing all tasks:

1. **Run full test suite**: `pytest --cov=apps -v`
2. **Run Django checks**: `python3 manage.py check --deploy`
3. **Review changes**: `git diff feature/complete-all-gaps...HEAD --stat`
4. **Create PR**: Use GitHub to create pull request
5. **Get code review**: Have team review the bounded context separation
6. **Merge to main**: After approval
7. **Deploy to staging**: Test in staging environment
8. **Deploy to production**: After staging validation

---

**Plan complete. Ready for execution.**
