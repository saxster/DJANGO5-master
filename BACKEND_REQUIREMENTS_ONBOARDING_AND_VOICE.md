# Backend Requirements: Onboarding & Voice Features API
**For: Django Backend Team**
**From: Mobile Development Team**
**Date:** 2025-11-12
**Priority:** HIGH
**Estimated Backend Effort:** 2-3 days

---

## 📋 Executive Summary

The mobile team has **COMPLETED** implementing a comprehensive onboarding flow with voice features. We need the backend team to add **5 new REST API endpoints**, **3 capability flags**, and **4 database fields** to support this feature.

**Mobile Implementation Status:** ✅ COMPLETE
- 34 files created (domain, data, presentation layers)
- 154 comprehensive tests (TDD approach)
- OnboardingManager, AudioRecorderManager, ViewModels, UI screens all implemented
- Build succeeding, all tests passing
- Ready for backend API integration

**Key Requirement:** The onboarding module is **capability-gated**. Only users with `canAccessOnboarding: true` should be able to access onboarding APIs. By default, this capability is `false`.

**This document provides EXACT specifications** to ensure perfect alignment with the mobile implementation.

---

## 🎯 Required Deliverables

### 1. Database Changes (1 Migration)

Add the following fields to existing models:

#### `peoples.People` Model

```python
class People(AbstractBaseUser, PermissionsMixin):
    # ... existing fields ...

    # NEW: Onboarding tracking fields
    first_login_completed = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True if user has completed their first login session'
    )

    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Timestamp when user completed onboarding flow'
    )

    onboarding_skipped = models.BooleanField(
        default=False,
        help_text='True if user explicitly skipped onboarding'
    )

    def has_completed_onboarding(self) -> bool:
        """Check if user has completed or skipped onboarding."""
        return self.onboarding_completed_at is not None or self.onboarding_skipped

    def can_access_onboarding(self) -> bool:
        """Check if user is authorized to access onboarding module."""
        capabilities = self.get_capabilities()
        return capabilities.get('canAccessOnboarding', False)
```

#### `peoples.PeopleProfile` Model

```python
class PeopleProfile(models.Model):
    # ... existing fields ...

    # NEW: Profile completion tracking
    profile_completion_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Calculated profile completion percentage (0-100)'
    )

    def calculate_completion_percentage(self) -> int:
        """
        Calculate profile completion based on required fields.

        Required fields:
        - peopleimg (profile image)
        - dateofbirth
        - dateofjoin
        - gender

        Returns: Integer 0-100
        """
        required_fields = ['peopleimg', 'dateofbirth', 'dateofjoin', 'gender']
        completed = sum(1 for field in required_fields if getattr(self, field, None))
        percentage = int((completed / len(required_fields)) * 100)

        # Update stored value
        if self.profile_completion_percentage != percentage:
            self.profile_completion_percentage = percentage
            self.save(update_fields=['profile_completion_percentage'])

        return percentage

    def get_missing_profile_fields(self) -> list:
        """
        Returns list of dicts with missing required fields.

        Returns: [{"field": "peopleimg", "display_name": "Profile Image"}, ...]
        """
        required = {
            'peopleimg': 'Profile Image',
            'dateofbirth': 'Date of Birth',
            'dateofjoin': 'Date of Joining',
            'gender': 'Gender',
        }

        return [
            {'field': k, 'display_name': v}
            for k, v in required.items()
            if not getattr(self, k, None)
        ]
```

---

### 2. Capability Flags

Add **3 new capability flags** to the capabilities system:

```python
# In apps/peoples/capabilities.py (or wherever capabilities are defined)

def get_default_capabilities() -> dict:
    """Default capabilities for new users."""
    return {
        # Existing capabilities
        'canAccessPeople': True,
        'canAccessAttendance': True,
        'canAccessOperations': True,
        'canAccessHelpdesk': True,
        'canAccessJournal': True,
        'canAccessReports': False,
        'canAccessCalendar': True,

        # NEW: Onboarding and voice capabilities (default OFF)
        'canAccessOnboarding': False,      # Onboarding module visibility
        'canUseVoiceFeatures': False,      # Voice notes in journal/helpdesk
        'canUseVoiceBiometrics': False,    # Voice-based authentication
    }


def get_admin_capabilities() -> dict:
    """Full capabilities for admin users."""
    capabilities = get_default_capabilities()
    capabilities.update({
        'canAccessReports': True,
        'canAccessOnboarding': True,      # Admins can access onboarding
        'canUseVoiceFeatures': True,      # Admins can use voice
        'canUseVoiceBiometrics': True,    # Admins can use voice biometrics
    })
    return capabilities
```

**Note:** When a user logs in, their JWT token or `/api/v2/auth/login/` response should include these capabilities in the `capabilities` JSON field.

---

### 3. Permission Classes

Create **3 new permission classes** in `apps/peoples/permissions.py`:

```python
from rest_framework import permissions


class HasOnboardingAccess(permissions.BasePermission):
    """
    Permission: User must have canAccessOnboarding capability.

    Returns 403 if user lacks this capability.
    Used for: All onboarding-related endpoints.
    """

    message = 'You do not have permission to access onboarding features.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        capabilities = request.user.get_capabilities()
        return capabilities.get('canAccessOnboarding', False)


class HasVoiceFeatureAccess(permissions.BasePermission):
    """
    Permission: User must have canUseVoiceFeatures capability.

    Returns 403 if user lacks this capability.
    Used for: Voice notes, voice input (non-biometric).
    """

    message = 'You do not have permission to use voice features.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        capabilities = request.user.get_capabilities()
        return capabilities.get('canUseVoiceFeatures', False)


class HasVoiceBiometricAccess(permissions.BasePermission):
    """
    Permission: User must have canUseVoiceBiometrics capability.

    Returns 403 if user lacks this capability.
    Used for: Voice biometric enrollment, voice-based check-in.
    """

    message = 'You do not have permission to use voice biometric features.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        capabilities = request.user.get_capabilities()
        return capabilities.get('canUseVoiceBiometrics', False)
```

---

### 4. Required API Endpoints (5 endpoints)

#### Endpoint 1: Get Current User Profile

```
GET /api/v2/profile/me/

Authentication: Required (Bearer token)
Permissions: IsAuthenticated

Response (200 OK):
{
    "id": 123,
    "username": "john.doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "phone": "+1234567890",
    "client_id": 1,
    "tenant_id": 1,
    "capabilities": {
        "canAccessPeople": true,
        "canAccessAttendance": true,
        "canAccessOperations": true,
        "canAccessHelpdesk": true,
        "canAccessJournal": true,
        "canAccessReports": false,
        "canAccessCalendar": true,
        "canAccessOnboarding": false,
        "canUseVoiceFeatures": false,
        "canUseVoiceBiometrics": false,
        "canApproveJobs": false,
        "canManageTeam": false,
        "canViewAnalytics": false
    },
    "profile": {
        "peopleimg": "https://cdn.intelliwiz.com/media/profiles/123.jpg",
        "dateofbirth": "1990-01-15",
        "dateofjoin": "2025-01-01",
        "gender": "MALE",
        "profile_completion_percentage": 75
    },
    "organizational": {
        "location": "Site A",
        "department": "Security",
        "designation": "Security Officer",
        "reportto": 456,
        "client": 1,
        "bu": "Operations"
    },
    "onboarding_status": {
        "first_login_completed": true,
        "onboarding_completed_at": "2025-11-10T14:30:00Z",
        "onboarding_skipped": false
    }
}

Error Response (404):
{
    "error": "User profile not fully initialized"
}
```

**Implementation Notes:**
- Joins `People`, `PeopleProfile`, and `PeopleOrganizational` tables
- Returns denormalized data (mobile needs single request)
- Calls `profile.calculate_completion_percentage()` before returning
- Should be accessible to ALL authenticated users (no special permission)

---

#### Endpoint 2: Update Current User Profile

```
PATCH /api/v2/profile/me/

Authentication: Required
Permissions: IsAuthenticated

Request Body (all fields optional):
{
    "email": "newemail@example.com",
    "mobno": "+9876543210",
    "profile": {
        "gender": "FEMALE",
        "dateofbirth": "1990-01-15",
        "dateofjoin": "2025-01-01",
        "dateofreport": "2025-01-15"
    },
    "organizational": {
        "location": 2,
        "department": 3,
        "designation": 5
    }
}

Response (200 OK):
(Same structure as GET /api/v2/profile/me/)

Error Response (400 Bad Request):
{
    "errors": {
        "dateofbirth": ["Date of birth cannot be in the future"],
        "dateofjoin": ["Date of joining cannot be before date of birth"]
    }
}
```

**Implementation Notes:**
- Use atomic transaction (`@transaction.atomic`)
- Update only provided fields (partial update)
- Re-calculate `profile_completion_percentage` after update
- Return updated profile (same as GET)
- Validate date logic (DOB < date of join)

---

#### Endpoint 3: Upload Profile Image

```
POST /api/v2/profile/me/image/

Authentication: Required
Permissions: IsAuthenticated
Content-Type: multipart/form-data

Request:
image: <file> (required)

Validation Rules:
- Max size: 5MB
- Allowed formats: image/jpeg, image/png, image/webp, image/gif
- Minimum dimensions: 200x200 pixels
- Maximum dimensions: 2048x2048 pixels

Response (200 OK):
{
    "image_url": "https://cdn.intelliwiz.com/media/profiles/123.jpg",
    "profile_completion_percentage": 100
}

Error Responses:
400 - "No image file provided"
400 - "Image file too large. Maximum size is 5MB"
400 - "Invalid file type. Allowed: image/jpeg, image/png, image/webp, image/gif"
400 - "Image dimensions too small. Minimum: 200x200 pixels"
400 - "Image dimensions too large. Maximum: 2048x2048 pixels"
```

**Implementation Notes:**
- Save to `PeopleProfile.peopleimg` field
- Use Pillow to validate dimensions
- Generate thumbnail (optional but recommended)
- Re-calculate completion percentage
- Use S3/CloudFront for storage (if configured)

---

#### Endpoint 4: Get Profile Completion Status

```
GET /api/v2/profile/completion-status/

Authentication: Required
Permissions: IsAuthenticated + HasOnboardingAccess

Response (200 OK):
{
    "is_complete": false,
    "completion_percentage": 60,
    "missing_fields": [
        {"field": "peopleimg", "display_name": "Profile Image"},
        {"field": "dateofjoin", "display_name": "Date of Joining"}
    ],
    "has_completed_onboarding": false,
    "onboarding_completed_at": null,
    "onboarding_skipped": false,
    "first_login_completed": true,
    "can_skip_onboarding": true,
    "required_documents": [],
    "onboarding_workflow_state": null
}

Error Response (403 Forbidden):
{
    "detail": "You do not have permission to access onboarding features."
}
```

**Implementation Notes:**
- **REQUIRES `canAccessOnboarding: true` capability**
- Returns 403 if user lacks capability
- Calls `profile.calculate_completion_percentage()`
- Calls `profile.get_missing_profile_fields()`
- Optionally includes `people_onboarding.OnboardingRequest` status
- `can_skip_onboarding` = true if completion >= 50%

---

#### Endpoint 5: Mark Onboarding Complete

```
POST /api/v2/profile/mark-onboarding-complete/

Authentication: Required
Permissions: IsAuthenticated + HasOnboardingAccess

Request Body:
{
    "skipped": false,
    "completed_steps": [
        "welcome",
        "permissions",
        "profile_setup",
        "safety_briefing",
        "feature_tour"
    ]
}

Response (200 OK):
{
    "success": true,
    "onboarding_completed_at": "2025-11-12T10:30:00Z",
    "onboarding_skipped": false,
    "first_login_completed": true
}

Error Response (403 Forbidden):
{
    "detail": "You do not have permission to access onboarding features."
}

Error Response (400 Bad Request):
{
    "errors": {
        "completed_steps": ["Invalid step: 'invalid_step'"]
    }
}
```

**Implementation Notes:**
- **REQUIRES `canAccessOnboarding: true` capability**
- Updates `first_login_completed = True`
- If `skipped = false`:
  - Set `onboarding_completed_at = timezone.now()`
  - Set `onboarding_skipped = False`
- If `skipped = true`:
  - Set `onboarding_completed_at = None`
  - Set `onboarding_skipped = True`
- Store `completed_steps` in `people_extras` JSON field:
  ```json
  {
      "onboarding": {
          "completed_steps": ["welcome", "permissions", ...],
          "completed_at": "2025-11-12T10:30:00Z",
          "skipped": false,
          "version": "1.0"
      }
  }
  ```
- Valid steps: `welcome`, `permissions`, `profile_setup`, `safety_briefing`, `feature_tour`, `voice_enrollment`

---

### 5. Journal Voice Notes API (Optional - If Not Already Implemented)

**Note:** The mobile app found that `JournalMediaAttachment` model exists with `MediaType.AUDIO` support, but we couldn't find REST API endpoints to create/retrieve journal entries. If these don't exist, please add:

#### Create Journal Entry with Media

```
POST /api/v2/journal/entries/

Authentication: Required
Permissions: IsAuthenticated
Content-Type: application/json

Request Body:
{
    "entry_type": "DAILY",
    "title": "My Day",
    "content": "Had a productive day today",
    "timestamp": "2025-11-12T18:00:00Z",
    "wellbeing_metrics": {
        "mood_rating": 8,
        "stress_level": 2,
        "energy_level": 7,
        "sleep_hours": 7.5
    },
    "privacy_scope": "PRIVATE",
    "consent_given": true
}

Response (201 Created):
{
    "id": 789,
    "entry_type": "DAILY",
    "title": "My Day",
    "content": "Had a productive day today",
    "timestamp": "2025-11-12T18:00:00Z",
    "user_id": 123,
    "tenant_id": 1,
    "wellbeing_metrics": {...},
    "privacy_scope": "PRIVATE",
    "media_attachments": [],
    "sync_status": "synced",
    "version": 1,
    "created_at": "2025-11-12T18:00:00Z"
}
```

#### Add Voice Note to Journal Entry

```
POST /api/v2/journal/entries/{entry_id}/media/

Authentication: Required
Permissions: IsAuthenticated + HasVoiceFeatureAccess (for AUDIO only)
Content-Type: multipart/form-data

Request:
file: <audio file>
media_type: "AUDIO"
caption: "Voice note from the field"
duration: 45

Validation:
- If media_type == "AUDIO": User must have canUseVoiceFeatures = true
- If media_type == "PHOTO/VIDEO": No special permission needed
- Max audio file size: 50MB
- Allowed audio formats: audio/mpeg, audio/wav, audio/m4a, audio/aac, audio/ogg
- Max duration: 300 seconds (5 minutes)

Response (201 Created):
{
    "id": 456,
    "journal_entry_id": 789,
    "media_type": "AUDIO",
    "file_url": "https://cdn.intelliwiz.com/media/journal/456.m4a",
    "caption": "Voice note from the field",
    "duration": 45,
    "file_size": 512000,
    "created_at": "2025-11-12T18:05:00Z"
}

Error Response (403 Forbidden) - If user lacks voice capability:
{
    "error": "You do not have permission to upload audio files"
}

Error Response (403 Forbidden) - If entry belongs to another user:
{
    "error": "You can only add media to your own journal entries"
}
```

**Security Requirements:**
- Verify `journal_entry.user_id == request.user.id` (prevent adding media to other users' entries)
- Verify `journal_entry.tenant_id == request.user.client_id` (multi-tenancy)
- For AUDIO files: Check `canUseVoiceFeatures` capability

#### List Journal Entry Media

```
GET /api/v2/journal/entries/{entry_id}/media/

Authentication: Required
Permissions: IsAuthenticated

Response (200 OK):
[
    {
        "id": 456,
        "media_type": "AUDIO",
        "file_url": "https://...",
        "caption": "Voice note",
        "duration": 45,
        "file_size": 512000,
        "created_at": "2025-11-12T18:05:00Z"
    },
    {
        "id": 457,
        "media_type": "PHOTO",
        "file_url": "https://...",
        "caption": "Field photo",
        "created_at": "2025-11-12T18:10:00Z"
    }
]
```

---

## 🔧 Existing API Modifications

### Modify Conversational Onboarding APIs

Add capability permission to existing onboarding conversation endpoints:

```python
# apps/onboarding_api/views/conversation_views.py

from apps.peoples.permissions import HasOnboardingAccess

class ConversationStartView(APIView):
    permission_classes = [IsAuthenticated, HasOnboardingAccess]  # ADD THIS

    def post(self, request):
        # ... existing implementation ...
        pass


class ConversationProcessView(APIView):
    permission_classes = [IsAuthenticated, HasOnboardingAccess]  # ADD THIS

    def post(self, request, conversation_id):
        # ... existing implementation ...
        pass


# apps/onboarding_api/views/voice_views.py

from apps.peoples.permissions import HasOnboardingAccess, HasVoiceFeatureAccess

class VoiceInputView(APIView):
    permission_classes = [IsAuthenticated, HasOnboardingAccess, HasVoiceFeatureAccess]  # ADD

    def post(self, request, conversation_id):
        # ... existing implementation ...
        pass
```

**Rationale:** Prevents unauthorized users from accessing onboarding conversation APIs.

---

### Modify Voice Biometric APIs

Add capability permission to voice biometric endpoints:

```python
# apps/voice_recognition/views.py

from apps.peoples.permissions import HasVoiceBiometricAccess

class VoiceEnrollmentView(APIView):
    permission_classes = [IsAuthenticated, HasVoiceBiometricAccess]  # ADD THIS

    def post(self, request):
        # ... existing implementation ...
        pass


class VoiceVerificationView(APIView):
    permission_classes = [IsAuthenticated, HasVoiceBiometricAccess]  # ADD THIS

    def post(self, request):
        # ... existing implementation ...
        pass
```

**Rationale:** Voice biometric is high-security feature, should be opt-in only.

---

## 📝 URL Routing

Add the following routes to `apps/peoples/api/v2/urls.py`:

```python
from django.urls import path
from apps.peoples.api.v2.views import profile_views

urlpatterns = [
    # ... existing routes ...

    # NEW: Current user profile endpoints
    path('profile/me/', profile_views.get_current_user_profile, name='profile-me'),
    path('profile/me/update/', profile_views.update_current_user_profile, name='profile-me-update'),
    path('profile/me/image/', profile_views.upload_profile_image, name='profile-image-upload'),

    # NEW: Onboarding endpoints (capability-gated)
    path('profile/completion-status/',
         profile_views.get_profile_completion_status,
         name='profile-completion'),
    path('profile/mark-onboarding-complete/',
         profile_views.mark_onboarding_complete,
         name='mark-onboarding-complete'),
]
```

If creating Journal API:

```python
# apps/journal/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.journal.api.v2.views import JournalEntryViewSet

router = DefaultRouter()
router.register(r'entries', JournalEntryViewSet, basename='journal-entry')

urlpatterns = [
    path('api/v2/journal/', include(router.urls)),
]
```

---

## 🧪 Required Tests (Minimum 25 Tests)

### Test Suite 1: Capability Tests (5 tests)

```python
# apps/peoples/tests/test_capabilities.py

def test_default_capabilities_exclude_onboarding():
    """Default users should NOT have onboarding access."""
    caps = get_default_capabilities()
    assert caps['canAccessOnboarding'] is False
    assert caps['canUseVoiceFeatures'] is False
    assert caps['canUseVoiceBiometrics'] is False

def test_admin_capabilities_include_onboarding():
    """Admin users should have onboarding access."""
    caps = get_admin_capabilities()
    assert caps['canAccessOnboarding'] is True
    assert caps['canUseVoiceFeatures'] is True
    assert caps['canUseVoiceBiometrics'] is True

def test_user_can_access_onboarding_when_capability_enabled():
    """Users with capability should pass permission check."""
    user = create_user(capabilities={'canAccessOnboarding': True})
    assert user.can_access_onboarding() is True

def test_user_cannot_access_onboarding_without_capability():
    """Users without capability should fail permission check."""
    user = create_user(capabilities={'canAccessOnboarding': False})
    assert user.can_access_onboarding() is False

def test_user_with_null_capabilities_cannot_access_onboarding():
    """Null capabilities should default to no access."""
    user = create_user(capabilities=None)
    assert user.can_access_onboarding() is False
```

---

### Test Suite 2: Profile API Tests (8 tests)

```python
# apps/peoples/api/v2/tests/test_profile_api.py

def test_get_current_user_profile_success(authenticated_client):
    """GET /api/v2/profile/me/ returns current user."""
    response = authenticated_client.get('/api/v2/profile/me/')
    assert response.status_code == 200
    assert 'id' in response.data
    assert 'capabilities' in response.data
    assert 'profile' in response.data

def test_get_current_user_profile_unauthenticated():
    """Unauthenticated requests return 401."""
    client = APIClient()
    response = client.get('/api/v2/profile/me/')
    assert response.status_code == 401

def test_update_profile_success(authenticated_client):
    """PATCH /api/v2/profile/me/ updates profile."""
    data = {'email': 'new@example.com', 'profile': {'gender': 'MALE'}}
    response = authenticated_client.patch('/api/v2/profile/me/update/', data)
    assert response.status_code == 200
    assert response.data['email'] == 'new@example.com'

def test_upload_profile_image_success(authenticated_client):
    """POST /api/v2/profile/me/image/ uploads image."""
    image = create_test_image()  # Helper to create PIL image
    response = authenticated_client.post('/api/v2/profile/me/image/', {'image': image})
    assert response.status_code == 200
    assert 'image_url' in response.data

def test_upload_image_too_large(authenticated_client):
    """Should reject images > 5MB."""
    large_file = create_large_file(6_000_000)  # 6MB
    response = authenticated_client.post('/api/v2/profile/me/image/', {'image': large_file})
    assert response.status_code == 400
    assert 'too large' in response.data['error'].lower()

def test_get_completion_status_without_capability(authenticated_client, user):
    """Should return 403 if user lacks canAccessOnboarding."""
    user.capabilities = {'canAccessOnboarding': False}
    user.save()

    response = authenticated_client.get('/api/v2/profile/completion-status/')
    assert response.status_code == 403

def test_get_completion_status_with_capability(authenticated_client, user):
    """Should return status if user has canAccessOnboarding."""
    user.capabilities = {'canAccessOnboarding': True}
    user.save()

    response = authenticated_client.get('/api/v2/profile/completion-status/')
    assert response.status_code == 200
    assert 'completion_percentage' in response.data

def test_mark_onboarding_complete_success(authenticated_client, user):
    """Should mark onboarding complete."""
    user.capabilities = {'canAccessOnboarding': True}
    user.save()

    data = {'skipped': False, 'completed_steps': ['welcome', 'profile']}
    response = authenticated_client.post('/api/v2/profile/mark-onboarding-complete/', data)

    assert response.status_code == 200
    assert response.data['success'] is True

    user.refresh_from_db()
    assert user.first_login_completed is True
    assert user.onboarding_completed_at is not None
```

---

### Test Suite 3: Journal Voice API Tests (7 tests)

```python
# apps/journal/api/v2/tests/test_journal_api.py

def test_create_journal_entry_success(authenticated_client):
    """Should create journal entry."""
    data = {
        'entry_type': 'DAILY',
        'title': 'Test',
        'content': 'Test content for journal',
        'privacy_scope': 'PRIVATE',
        'consent_given': True
    }
    response = authenticated_client.post('/api/v2/journal/entries/', data)
    assert response.status_code == 201

def test_add_voice_note_with_capability(authenticated_client, user, journal_entry):
    """Should accept voice note if user has capability."""
    user.capabilities = {'canUseVoiceFeatures': True}
    user.save()

    audio_file = create_test_audio_file()  # Helper
    data = {'file': audio_file, 'media_type': 'AUDIO', 'duration': 30}

    response = authenticated_client.post(
        f'/api/v2/journal/entries/{journal_entry.id}/media/',
        data
    )

    assert response.status_code == 201
    assert response.data['media_type'] == 'AUDIO'

def test_add_voice_note_without_capability(authenticated_client, user, journal_entry):
    """Should reject voice note if user lacks capability."""
    user.capabilities = {'canUseVoiceFeatures': False}
    user.save()

    audio_file = create_test_audio_file()
    data = {'file': audio_file, 'media_type': 'AUDIO'}

    response = authenticated_client.post(
        f'/api/v2/journal/entries/{journal_entry.id}/media/',
        data
    )

    assert response.status_code == 403
    assert 'do not have permission' in response.data['error'].lower()

def test_add_photo_without_voice_capability(authenticated_client, user, journal_entry):
    """Photos should work even without voice capability."""
    user.capabilities = {'canUseVoiceFeatures': False}
    user.save()

    photo_file = create_test_image()
    data = {'file': photo_file, 'media_type': 'PHOTO'}

    response = authenticated_client.post(
        f'/api/v2/journal/entries/{journal_entry.id}/media/',
        data
    )

    assert response.status_code == 201  # Should succeed

def test_cannot_add_media_to_other_users_entry(authenticated_client, other_user_entry):
    """Should prevent cross-user media uploads."""
    audio_file = create_test_audio_file()
    response = authenticated_client.post(
        f'/api/v2/journal/entries/{other_user_entry.id}/media/',
        {'file': audio_file, 'media_type': 'AUDIO'}
    )

    assert response.status_code == 403

def test_list_journal_media(authenticated_client, journal_entry_with_media):
    """Should list all media attachments."""
    response = authenticated_client.get(
        f'/api/v2/journal/entries/{journal_entry_with_media.id}/media/'
    )

    assert response.status_code == 200
    assert len(response.data) > 0

def test_audio_file_size_validation(authenticated_client, user, journal_entry):
    """Should reject audio files > 50MB."""
    user.capabilities = {'canUseVoiceFeatures': True}
    user.save()

    large_audio = create_large_audio_file(51_000_000)  # 51MB
    response = authenticated_client.post(
        f'/api/v2/journal/entries/{journal_entry.id}/media/',
        {'file': large_audio, 'media_type': 'AUDIO'}
    )

    assert response.status_code == 400
```

---

### Test Suite 4: Permission Class Tests (5 tests)

```python
# apps/peoples/tests/test_permissions.py

def test_has_onboarding_access_permission_granted():
    """Permission granted if capability is true."""
    user = create_user(capabilities={'canAccessOnboarding': True})
    request = create_mock_request(user)

    permission = HasOnboardingAccess()
    assert permission.has_permission(request, None) is True

def test_has_onboarding_access_permission_denied():
    """Permission denied if capability is false."""
    user = create_user(capabilities={'canAccessOnboarding': False})
    request = create_mock_request(user)

    permission = HasOnboardingAccess()
    assert permission.has_permission(request, None) is False

def test_has_voice_feature_access_permission_granted():
    """Voice feature permission granted if capability true."""
    user = create_user(capabilities={'canUseVoiceFeatures': True})
    request = create_mock_request(user)

    permission = HasVoiceFeatureAccess()
    assert permission.has_permission(request, None) is True

def test_has_voice_biometric_access_permission_denied():
    """Voice biometric permission denied if capability false."""
    user = create_user(capabilities={'canUseVoiceBiometrics': False})
    request = create_mock_request(user)

    permission = HasVoiceBiometricAccess()
    assert permission.has_permission(request, None) is False

def test_permission_denied_for_unauthenticated():
    """All custom permissions should deny unauthenticated users."""
    from django.contrib.auth.models import AnonymousUser
    request = create_mock_request(AnonymousUser())

    assert HasOnboardingAccess().has_permission(request, None) is False
    assert HasVoiceFeatureAccess().has_permission(request, None) is False
    assert HasVoiceBiometricAccess().has_permission(request, None) is False
```

---

## 📊 Schema Alignment with Mobile

### Mobile UserCapabilities Model (Kotlin)

The mobile app expects this exact structure in API responses:

```kotlin
@Serializable
data class UserCapabilities(
    val canAccessPeople: Boolean = true,
    val canAccessAttendance: Boolean = true,
    val canAccessOperations: Boolean = true,
    val canAccessHelpdesk: Boolean = true,
    val canAccessJournal: Boolean = true,
    val canAccessReports: Boolean = false,
    val canAccessCalendar: Boolean = true,
    val canAccessOnboarding: Boolean = false,
    val canUseVoiceFeatures: Boolean = false,
    val canUseVoiceBiometrics: Boolean = false,
    val canApproveJobs: Boolean = false,
    val canManageTeam: Boolean = false,
    val canViewAnalytics: Boolean = false
)
```

**Backend Must Return:**
The `capabilities` field in login response and profile response should be a JSON object with these exact keys (camelCase).

**Example Backend Serializer:**
```python
class UserProfileSerializer(serializers.ModelSerializer):
    capabilities = serializers.SerializerMethodField()

    def get_capabilities(self, obj):
        return obj.get_capabilities()  # Should return dict with exact keys above

    class Meta:
        model = People
        fields = ['id', 'username', 'email', 'full_name', 'capabilities', ...]
```

---

### Mobile ProfileCompletionStatus Model (Kotlin)

Mobile expects this structure from `GET /api/v2/profile/completion-status/`:

```kotlin
data class ProfileCompletionStatus(
    val isComplete: Boolean,
    val completionPercentage: Int,
    val missingFields: List<MissingField>,
    val hasCompletedOnboarding: Boolean,
    val onboardingCompletedAt: Instant?,
    val onboardingSkipped: Boolean,
    val firstLoginCompleted: Boolean,
    val canSkipOnboarding: Boolean,
    val requiredDocuments: List<String>,
    val onboardingWorkflowState: String?
)

data class MissingField(
    val field: String,
    val displayName: String
)
```

**Backend JSON Response Should Match:**
```json
{
    "is_complete": false,
    "completion_percentage": 60,
    "missing_fields": [
        {"field": "peopleimg", "display_name": "Profile Image"}
    ],
    "has_completed_onboarding": false,
    "onboarding_completed_at": null,
    "onboarding_skipped": false,
    "first_login_completed": false,
    "can_skip_onboarding": true,
    "required_documents": [],
    "onboarding_workflow_state": null
}
```

**Note:** Use snake_case for JSON keys (Django REST Framework convention). Mobile will map to camelCase.

---

## 🔐 Security Checklist for Backend Team

- [ ] All new endpoints use `@permission_classes` decorator
- [ ] Onboarding endpoints have `HasOnboardingAccess` permission
- [ ] Voice endpoints have `HasVoiceFeatureAccess` permission
- [ ] Voice biometric endpoints have `HasVoiceBiometricAccess` permission
- [ ] Profile update validates `user == request.user` (no editing other profiles)
- [ ] Journal media upload validates `entry.user == request.user`
- [ ] Multi-tenancy enforced: `journal_entry.tenant == request.user.client`
- [ ] File uploads validated (size, type, dimensions)
- [ ] Audit logging for permission denials
- [ ] Default capabilities are `False` for new features
- [ ] JWT includes updated capabilities on login

---

## 📋 Acceptance Criteria

### ✅ Backend Implementation Complete When:

**Database:**
- [ ] Migration adds 4 new fields to People and PeopleProfile
- [ ] Migration applies successfully on test database
- [ ] All existing data preserved

**Capabilities:**
- [ ] 3 new capability flags added to capabilities system
- [ ] Default capabilities exclude new features (all `False`)
- [ ] Admin capabilities include new features (all `True`)
- [ ] JWT token includes all 13 capability flags

**API Endpoints:**
- [ ] `GET /api/v2/profile/me/` returns current user profile
- [ ] `PATCH /api/v2/profile/me/` updates profile fields
- [ ] `POST /api/v2/profile/me/image/` accepts image uploads (max 5MB)
- [ ] `GET /api/v2/profile/completion-status/` returns completion (requires capability)
- [ ] `POST /api/v2/profile/mark-onboarding-complete/` marks complete (requires capability)
- [ ] Journal API endpoints created (if not existing)
- [ ] Journal media endpoint accepts voice notes (requires capability)

**Permissions:**
- [ ] All onboarding endpoints return 403 if `canAccessOnboarding = false`
- [ ] Voice note upload returns 403 if `canUseVoiceFeatures = false`
- [ ] Voice biometric endpoints return 403 if `canUseVoiceBiometrics = false`

**Tests:**
- [ ] All 25+ tests pass
- [ ] Test coverage > 90% for new code
- [ ] Integration tests verify capability enforcement
- [ ] Tests cover both authorized and unauthorized cases

**Documentation:**
- [ ] API documentation updated (OpenAPI schema)
- [ ] README updated with capability descriptions
- [ ] Migration notes added

---

## 📞 Communication Protocol

### Questions or Clarifications

**Mobile Team Contact:** [Your contact info]
**Slack Channel:** #mobile-backend-integration
**Response Time:** Within 24 hours

### Verification Before Handoff

Before marking backend work complete, please verify:

1. **Run all tests:** `pytest apps/peoples apps/journal -v`
2. **Test with Postman/cURL:**
   - Call each endpoint with valid credentials + capability
   - Call each endpoint without capability (should get 403)
3. **Generate updated OpenAPI schema:** Mobile team needs updated `openapi.yaml`
4. **Deploy to staging environment**
5. **Provide staging credentials** for mobile team testing

### Mobile Team Will Test

We will verify:
- [ ] All endpoints return expected JSON structure
- [ ] Capability enforcement works (403 responses)
- [ ] Multi-tenancy is enforced
- [ ] File uploads work with real files
- [ ] Completion percentage calculates correctly
- [ ] JWT includes new capability flags

---

## 🚀 Deployment Notes

### Environment Variables (If Needed)

```bash
# .env or settings

# Onboarding feature flags (optional - if you want server-side toggles)
ONBOARDING_MODULE_ENABLED=True
VOICE_FEATURES_ENABLED=True

# File upload settings
MAX_PROFILE_IMAGE_SIZE_MB=5
MAX_VOICE_NOTE_SIZE_MB=50

# Voice processing (if integrating with existing voice system)
GOOGLE_CLOUD_SPEECH_API_KEY=<your-key>
VOICE_SUPPORTED_LANGUAGES=en-US,hi-IN,mr-IN,ta-IN,te-IN
```

### Migration Deployment

```bash
# Apply migration
python manage.py migrate peoples

# Verify migration
python manage.py sqlmigrate peoples 00XX  # Check SQL

# Create test user with onboarding capability
python manage.py shell
>>> from apps.peoples.models import People
>>> user = People.objects.get(loginid='testuser')
>>> user.capabilities = {'canAccessOnboarding': True, 'canUseVoiceFeatures': True}
>>> user.save()
```

---

## 📚 Reference Materials

### Existing Backend Code to Reference

**Capabilities System:**
- `apps/peoples/models/user_model.py` - People model
- Existing `capabilities` JSONField
- Existing `get_capabilities()` method

**Similar Patterns:**
- `apps/onboarding_api/` - Existing conversational onboarding (reference for permission patterns)
- `apps/voice_recognition/` - Existing voice biometric system
- `apps/journal/models/media.py` - JournalMediaAttachment model

**Authentication:**
- `apps/peoples/api/v2/views/auth_views.py` - Login endpoint (add capabilities to response)
- JWT token generation - Include updated capabilities

---

## ⚠️ Important Notes

1. **Backward Compatibility:** Existing mobile apps won't have these capabilities. Ensure:
   - Missing capabilities default to `False`
   - Existing endpoints continue to work
   - Migration doesn't break existing user logins

2. **Performance:** Profile completion calculation should be fast:
   - Cache completion percentage in database field
   - Only recalculate when profile updated
   - Don't calculate on every API call

3. **Multi-Tenancy:** All new endpoints must enforce:
   - `journal_entry.tenant_id == request.user.client_id`
   - `profile.tenant_id == request.user.client_id`
   - Use existing tenant isolation patterns

4. **File Storage:** Use existing media storage configuration:
   - S3 bucket (if configured)
   - Local storage (for development)
   - Proper file permissions (private)

---

## 🎯 Success Metrics

After implementation, mobile team should be able to:

- [ ] GET current user profile with capabilities
- [ ] PATCH profile and see completion percentage update
- [ ] Upload profile image and verify it appears
- [ ] GET completion status (if capability enabled)
- [ ] Mark onboarding complete
- [ ] Create journal entry with voice note (if capability enabled)
- [ ] Get 403 errors when testing without capabilities
- [ ] Verify capabilities appear in login JWT response

---

## 📅 Timeline

**Requested Completion:** Within 3 business days
**Target Date:** 2025-11-15

**Breakdown:**
- Day 1: Database migration + capability flags + permission classes
- Day 2: Profile API endpoints + tests
- Day 3: Journal API (if needed) + tests + verification

**Handoff:** Once complete, notify mobile team via Slack with:
- Staging URL for testing
- Test credentials with `canAccessOnboarding: true`
- Updated OpenAPI schema
- Any known issues or limitations

---

## 📧 Contact Information

**For Technical Questions:**
- Mobile Team Lead: [Name/Email]
- Mobile Developer: [Name/Email]

**For Product/Requirements Questions:**
- Product Owner: [Name/Email]

**Slack Channels:**
- #mobile-backend-integration
- #api-development

---

---

## 📱 MOBILE IMPLEMENTATION DETAILS (For Reference)

### What's Been Built on Mobile Side

The mobile team has completed a comprehensive implementation that includes:

**1. Domain Layer:**
- `ProfileCompletionStatus` - Matches your completion-status API response exactly
- `OnboardingError` - Handles 403 NotAuthorized, network errors, etc.
- `AudioRecording` - Voice recording metadata model
- `OnboardingRepository` interface - Defines contract for API calls
- 2 Use cases with capability validation

**2. Data Layer:**
- `OnboardingRepositoryImpl` - Calls your APIs (waiting for implementation)
- `OnboardingManager` - Persists onboarding state locally
- `AudioRecorderManager` - Records voice using MediaRecorder
- `OnboardingApi` - Retrofit interface calling your endpoints
- 4 DTOs matching your response schemas exactly
- Mapper for DTO→Domain conversion

**3. Presentation Layer:**
- `OnboardingViewModel` - Orchestrates onboarding flow
- 5 UI screens (Welcome carousel, Permissions, Profile setup, etc.)
- `MainActivity` navigation - Routes based on capabilities

**4. Testing:**
- 154 comprehensive tests (all TDD)
- Integration tests for OnboardingManager
- Unit tests for all components
- Navigation tests for capability routing

### Mobile API Client Implementation

The mobile app makes API calls like this:

```kotlin
// OnboardingRepositoryImpl.kt
class OnboardingRepositoryImpl @Inject constructor(
    private val onboardingApi: OnboardingApi  // Retrofit interface
) : OnboardingRepository {

    override suspend fun getProfileCompletion(): Result<ProfileCompletionStatus> {
        try {
            val response = onboardingApi.getProfileCompletion()

            if (response.isSuccessful) {
                val dto = response.body()!!
                val domain = ProfileCompletionMapper.dtoToDomain(dto)
                return Result.success(domain)
            }

            return when (response.code()) {
                403 -> Result.failure(OnboardingError.NotAuthorized)
                400, 500 -> Result.failure(OnboardingError.NetworkError(...))
                else -> Result.failure(OnboardingError.Unknown(...))
            }
        } catch (e: IOException) {
            return Result.failure(OnboardingError.NetworkError(e.message ?: "Network error"))
        }
    }
}
```

**Your API must return:**
- Exact JSON structure defined in endpoint specifications above
- HTTP status codes as specified
- Error messages in expected format

### Critical Fields Mobile Expects

**Profile Completion Response:**
```json
{
    "is_complete": false,              // Boolean (required)
    "completion_percentage": 60,        // Integer 0-100 (required)
    "missing_fields": [                 // Array (required, can be empty)
        {
            "field": "peopleimg",       // String (required) - backend field name
            "display_name": "Profile Image"  // String (required) - human readable
        }
    ],
    "has_completed_onboarding": false,  // Boolean (required)
    "onboarding_completed_at": null,    // ISO 8601 string or null (required)
    "onboarding_skipped": false,        // Boolean (required)
    "first_login_completed": false,     // Boolean (required)
    "can_skip_onboarding": true,        // Boolean (required)
    "required_documents": [],           // Array of strings (required, can be empty)
    "onboarding_workflow_state": null   // String or null (required)
}
```

**Mobile DTO (ProfileCompletionDto.kt):**
```kotlin
@Serializable
data class ProfileCompletionDto(
    @SerialName("is_complete") val isComplete: Boolean,
    @SerialName("completion_percentage") val completionPercentage: Int,
    @SerialName("missing_fields") val missingFields: List<MissingFieldDto>,
    @SerialName("has_completed_onboarding") val hasCompletedOnboarding: Boolean,
    @SerialName("onboarding_completed_at") val onboardingCompletedAt: String?,
    @SerialName("onboarding_skipped") val onboardingSkipped: Boolean,
    @SerialName("first_login_completed") val firstLoginCompleted: Boolean,
    @SerialName("can_skip_onboarding") val canSkipOnboarding: Boolean,
    @SerialName("required_documents") val requiredDocuments: List<String> = emptyList(),
    @SerialName("onboarding_workflow_state") val onboardingWorkflowState: String? = null
)

@Serializable
data class MissingFieldDto(
    @SerialName("field") val field: String,
    @SerialName("display_name") val displayName: String
)
```

**CRITICAL:** Field names must match EXACTLY (snake_case in JSON, SerialName maps to camelCase)

### HTTP Headers Mobile Sends

All API requests include:
```
Authorization: Bearer <jwt_access_token>
Content-Type: application/json (or multipart/form-data for image upload)
```

Mobile expects backend to:
1. Validate JWT token
2. Extract user from token
3. Check user.capabilities['canAccessOnboarding']
4. Return 403 if capability is false or missing

### Error Handling Mobile Implements

Mobile maps HTTP status codes to domain errors:

```kotlin
when (response.code()) {
    403 -> OnboardingError.NotAuthorized
        // User lacks canAccessOnboarding capability
        // Mobile shows: "You don't have access to onboarding features"

    400 -> OnboardingError.ImageUploadFailed(reason)
        // Bad request (file too large, invalid format, etc.)
        // Mobile shows specific error from response.body().error

    500, 502, 503 -> OnboardingError.NetworkError("Server error")
        // Server errors
        // Mobile shows: "Server is experiencing issues. Please try again later."

    else -> OnboardingError.Unknown("Unexpected error")
}
```

**IOException (no network):**
```kotlin
catch (e: IOException) {
    // Network connectivity issues
    // Mobile shows: "No internet connection. Please check your network."
}
```

### Mobile Test Scenarios (What We're Testing)

**Success Scenarios (your APIs must pass these):**
1. User with `canAccessOnboarding=true` calls GET /profile/completion-status/ → 200 OK
2. User with `canAccessOnboarding=true` calls POST /profile/mark-onboarding-complete/ → 200 OK
3. Any authenticated user calls POST /profile/me/image/ → 200 OK (no special capability)
4. Profile completion calculates correctly (e.g., 2/4 fields = 50%)
5. Missing fields list is accurate

**Error Scenarios (your APIs must handle these):**
1. User with `canAccessOnboarding=false` calls GET /profile/completion-status/ → 403 Forbidden
2. User with `canAccessOnboarding=false` calls POST /mark-onboarding-complete/ → 403 Forbidden
3. Unauthenticated user calls any endpoint → 401 Unauthorized
4. User uploads 6MB image → 400 Bad Request "Image file too large"
5. User uploads .pdf to image endpoint → 400 Bad Request "Invalid file type"
6. Network timeout/error → Mobile handles gracefully (offline-first)

**We have 13 tests in OnboardingRepositoryImplTest.kt that verify all these scenarios.**

---

## 🔍 MOBILE IMPLEMENTATION VERIFICATION

### Files You Can Reference

To see exact mobile implementation:

**Repository:**
`/app/src/main/kotlin/com/intelliwiz/mobile/data/repository/onboarding/OnboardingRepositoryImpl.kt`

**DTOs:**
`/app/src/main/kotlin/com/intelliwiz/mobile/data/remote/onboarding/dto/ProfileCompletionDto.kt`
`/app/src/main/kotlin/com/intelliwiz/mobile/data/remote/onboarding/dto/MarkOnboardingCompleteRequestDto.kt`
`/app/src/main/kotlin/com/intelliwiz/mobile/data/remote/onboarding/dto/MarkOnboardingCompleteResponseDto.kt`
`/app/src/main/kotlin/com/intelliwiz/mobile/data/remote/onboarding/dto/ProfileImageResponseDto.kt`

**API Interface:**
`/app/src/main/kotlin/com/intelliwiz/mobile/data/remote/onboarding/OnboardingApi.kt`

**Domain Models:**
`/app/src/main/kotlin/com/intelliwiz/mobile/domain/onboarding/model/ProfileCompletionStatus.kt`
`/app/src/main/kotlin/com/intelliwiz/mobile/domain/onboarding/model/OnboardingError.kt`

**Tests (Shows Expected Behavior):**
`/app/src/test/kotlin/com/intelliwiz/mobile/data/repository/onboarding/OnboardingRepositoryImplTest.kt`
`/app/src/test/kotlin/com/intelliwiz/mobile/domain/onboarding/usecase/GetProfileCompletionUseCaseTest.kt`
`/app/src/test/kotlin/com/intelliwiz/mobile/domain/onboarding/usecase/CompleteOnboardingUseCaseTest.kt`

### Integration Test Scenarios

Mobile team will test your APIs with:

**Test User 1: Admin with all capabilities**
```python
user.capabilities = {
    'canAccessOnboarding': True,
    'canUseVoiceFeatures': True,
    'canUseVoiceBiometrics': True
}
```
Expected: All endpoints accessible

**Test User 2: Regular user without onboarding**
```python
user.capabilities = {
    'canAccessOnboarding': False,
    'canUseVoiceFeatures': False
}
```
Expected: GET /profile/completion-status/ returns 403

**Test User 3: New employee (onboarding enabled)**
```python
user.capabilities = {
    'canAccessOnboarding': True,
    'canUseVoiceFeatures': False
}
user.first_login_completed = False
```
Expected: Can access onboarding APIs, profile shows incomplete

**Test User 4: Existing user (onboarding completed)**
```python
user.onboarding_completed_at = datetime.now()
user.first_login_completed = True
```
Expected: Completion status shows completed

---

## 🎯 MOBILE ONBOARDING FLOW (Implemented)

Understanding the mobile flow helps backend implementation:

```
User logs in
    ↓
Mobile checks: user.capabilities.canAccessOnboarding?
    ↓ YES (and not completed)
    ↓
Show Onboarding Flow:
    ↓
Step 1: Welcome carousel (4 slides)
    ↓
Step 2: Permission education (Location, Camera, Audio)
    ↓
Step 3: Profile Setup
    ↓
    Mobile calls: GET /api/v2/profile/completion-status/
    ← Backend returns: { completion_percentage: 60, missing_fields: [...] }
    ↓
    User uploads avatar → POST /api/v2/profile/me/image/
    ← Backend returns: { image_url: "...", profile_completion_percentage: 100 }
    ↓
    User fills DOB, Gender → PATCH /api/v2/profile/me/
    ← Backend returns: { profile: { ... } }
    ↓
Step 4: Safety briefing
    ↓
Step 5: Feature tour
    ↓
Step 6: Voice enrollment (if canUseVoiceBiometrics=true)
    ↓
Complete Onboarding:
    ↓
    Mobile calls: POST /api/v2/profile/mark-onboarding-complete/
    With: { skipped: false, completed_steps: ["welcome", "permissions", ...] }
    ← Backend updates: user.onboarding_completed_at = now()
    ← Backend returns: { success: true, onboarding_completed_at: "..." }
    ↓
    Mobile updates local state (OnboardingManager)
    ↓
Navigate to Main App
```

**Alternative Flow (Skip):**
```
User taps "Skip" button
    ↓
Mobile calls: POST /api/v2/profile/mark-onboarding-complete/
With: { skipped: true, completed_steps: [] }
    ↓
Backend updates: user.onboarding_skipped = True
    ↓
Navigate to Main App
```

This helps you understand:
- When endpoints are called
- What data mobile sends
- What mobile expects in response
- Error scenarios to handle

---

## 📊 EXACT DTO SPECIFICATIONS

### ProfileCompletionDto - Mobile Expects

```kotlin
// File: data/remote/onboarding/dto/ProfileCompletionDto.kt
// This is EXACTLY what mobile parses from your GET /profile/completion-status/ response

@Serializable
data class ProfileCompletionDto(
    @SerialName("is_complete")
    val isComplete: Boolean,

    @SerialName("completion_percentage")
    val completionPercentage: Int,

    @SerialName("missing_fields")
    val missingFields: List<MissingFieldDto>,

    @SerialName("has_completed_onboarding")
    val hasCompletedOnboarding: Boolean,

    @SerialName("onboarding_completed_at")
    val onboardingCompletedAt: String?,  // ISO 8601 format: "2025-11-12T10:30:00Z"

    @SerialName("onboarding_skipped")
    val onboardingSkipped: Boolean,

    @SerialName("first_login_completed")
    val firstLoginCompleted: Boolean,

    @SerialName("can_skip_onboarding")
    val canSkipOnboarding: Boolean,

    @SerialName("required_documents")
    val requiredDocuments: List<String> = emptyList(),

    @SerialName("onboarding_workflow_state")
    val onboardingWorkflowState: String? = null
)

@Serializable
data class MissingFieldDto(
    @SerialName("field")
    val field: String,

    @SerialName("display_name")
    val displayName: String
)
```

**Your Django Serializer Should Return This EXACT Structure:**

```python
class ProfileCompletionStatusSerializer(serializers.Serializer):
    is_complete = serializers.BooleanField()
    completion_percentage = serializers.IntegerField()
    missing_fields = serializers.ListField(
        child=serializers.DictField()  # Each dict: {"field": "...", "display_name": "..."}
    )
    has_completed_onboarding = serializers.BooleanField()
    onboarding_completed_at = serializers.DateTimeField(allow_null=True)  # ISO 8601
    onboarding_skipped = serializers.BooleanField()
    first_login_completed = serializers.BooleanField()
    can_skip_onboarding = serializers.BooleanField()
    required_documents = serializers.ListField(child=serializers.CharField())
    onboarding_workflow_state = serializers.CharField(allow_null=True)
```

### MarkOnboardingCompleteRequestDto - Mobile Sends

```kotlin
// What mobile sends to POST /profile/mark-onboarding-complete/

@Serializable
data class MarkOnboardingCompleteRequestDto(
    @SerialName("skipped")
    val skipped: Boolean,

    @SerialName("completed_steps")
    val completedSteps: List<String>
)

// Example request body:
{
    "skipped": false,
    "completed_steps": [
        "welcome",
        "permissions",
        "profile_setup",
        "safety_briefing",
        "feature_tour"
    ]
}
```

### MarkOnboardingCompleteResponseDto - Backend Should Return

```kotlin
// What mobile expects from POST /profile/mark-onboarding-complete/

@Serializable
data class MarkOnboardingCompleteResponseDto(
    @SerialName("success")
    val success: Boolean,

    @SerialName("onboarding_completed_at")
    val onboardingCompletedAt: String?,  // ISO 8601 or null if skipped

    @SerialName("onboarding_skipped")
    val onboardingSkipped: Boolean,

    @SerialName("first_login_completed")
    val firstLoginCompleted: Boolean
)

// Example response:
{
    "success": true,
    "onboarding_completed_at": "2025-11-12T10:30:00Z",
    "onboarding_skipped": false,
    "first_login_completed": true
}
```

### ProfileImageResponseDto - Image Upload Response

```kotlin
// What mobile expects from POST /profile/me/image/

@Serializable
data class ProfileImageResponseDto(
    @SerialName("image_url")
    val imageUrl: String,

    @SerialName("profile_completion_percentage")
    val profileCompletionPercentage: Int
)

// Example response:
{
    "image_url": "https://cdn.intelliwiz.com/media/profiles/123.jpg",
    "profile_completion_percentage": 100
}
```

---

## 🔗 CRITICAL INTEGRATION POINTS

### 1. Capabilities in Login Response

**IMPORTANT:** Mobile needs capabilities immediately after login.

**Current Issue:** Your login endpoint may not return capabilities.

**Two Solutions:**

**Option A (Recommended):** Add capabilities to login response
```python
# apps/api/v2/views/auth_views.py

class LoginView(APIView):
    def post(self, request):
        # ... authentication logic ...

        # ADD THIS to response:
        response_data = {
            'access': access_token,
            'refresh': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                # ADD capabilities:
                'capabilities': user.get_capabilities()  # Returns dict with all 13 flags
            }
        }
        return Response(response_data)
```

**Option B:** Mobile makes second API call
```kotlin
// After login
val userProfile = api.getProfile(userId)  // Your existing endpoint
val capabilities = userProfile.capabilities
```

**Recommendation:** Option A is cleaner (single request)

### 2. Capability Flag Structure

Mobile expects capabilities as JSONB with camelCase keys:

```python
# In People model or capability service
def get_capabilities(self) -> dict:
    """
    Returns capabilities dict for mobile app.
    Keys MUST be camelCase to match mobile expectations.
    """
    caps = self.capabilities or {}  # Get from JSONB field

    # Ensure all 13 keys exist with defaults
    return {
        'canAccessPeople': caps.get('canAccessPeople', True),
        'canAccessAttendance': caps.get('canAccessAttendance', True),
        'canAccessOperations': caps.get('canAccessOperations', True),
        'canAccessHelpdesk': caps.get('canAccessHelpdesk', True),
        'canAccessJournal': caps.get('canAccessJournal', True),
        'canAccessReports': caps.get('canAccessReports', False),
        'canAccessCalendar': caps.get('canAccessCalendar', True),
        'canAccessOnboarding': caps.get('canAccessOnboarding', False),  # NEW
        'canUseVoiceFeatures': caps.get('canUseVoiceFeatures', False),   # NEW
        'canUseVoiceBiometrics': caps.get('canUseVoiceBiometrics', False), # NEW
        'canApproveJobs': caps.get('canApproveJobs', False),
        'canManageTeam': caps.get('canManageTeam', False),
        'canViewAnalytics': caps.get('canViewAnalytics', False),
    }
```

**Mobile parses this with:**
```kotlin
UserCapabilities.parseFromMap(capabilitiesMap)
```

---

## 🧪 TESTING WITH MOBILE APP

### How to Test Your Implementation

**Step 1: Deploy backend to staging**

**Step 2: Configure mobile to point to staging**
```kotlin
// Mobile will point to your staging URL
buildConfigField("String", "API_BASE_URL", "\"https://staging.intelliwiz.com\"")
```

**Step 3: Create test user with capabilities**
```python
user = People.objects.get(loginid='mobile-test')
user.capabilities = {
    'canAccessOnboarding': True,
    'canUseVoiceFeatures': True,
    'canUseVoiceBiometrics': True
}
user.save()
```

**Step 4: Mobile team logs in and tests**
- Login with test user
- Should see onboarding flow
- Can upload avatar
- Can complete onboarding
- State persists

**Step 5: Test capability enforcement**
```python
# Disable capability
user.capabilities['canAccessOnboarding'] = False
user.save()
```
- Mobile should NOT show onboarding
- API calls should return 403

### Debugging Failed Integration

If mobile reports issues:

**1. Check Response Format:**
```bash
curl -H "Authorization: Bearer <token>" \
     https://staging.intelliwiz.com/api/v2/profile/completion-status/ | jq
```
Compare with ProfileCompletionDto structure above

**2. Check Field Names:**
- Must be snake_case in JSON
- Mobile maps to camelCase with @SerialName

**3. Check Capability Enforcement:**
```bash
# User WITHOUT capability
curl -H "Authorization: Bearer <token-without-capability>" \
     https://staging.intelliwiz.com/api/v2/profile/completion-status/
# Should return 403
```

**4. Check Error Messages:**
Mobile expects:
- 403: `{"detail": "You do not have permission..."}`
- 400: `{"error": "Specific error message"}`
- 500: Any error format (mobile shows generic message)

---

## 📦 MOBILE TEST DATA EXAMPLES

### Example 1: Incomplete Profile

**Backend State:**
```python
profile.peopleimg = None  # Missing
profile.dateofbirth = "1990-01-15"  # Present
profile.gender = None  # Missing
profile.dateofjoin = "2025-01-01"  # Present
```

**Expected API Response:**
```json
{
    "is_complete": false,
    "completion_percentage": 50,
    "missing_fields": [
        {"field": "peopleimg", "display_name": "Profile Image"},
        {"field": "gender", "display_name": "Gender"}
    ],
    "has_completed_onboarding": false,
    "onboarding_completed_at": null,
    "onboarding_skipped": false,
    "first_login_completed": false,
    "can_skip_onboarding": true,
    "required_documents": [],
    "onboarding_workflow_state": null
}
```

### Example 2: Complete Profile, Onboarding Done

**Backend State:**
```python
profile.peopleimg = "profiles/123.jpg"  # Present
profile.dateofbirth = "1990-01-15"  # Present
profile.gender = "M"  # Present
profile.dateofjoin = "2025-01-01"  # Present
user.onboarding_completed_at = "2025-11-10T14:30:00Z"
user.first_login_completed = True
```

**Expected API Response:**
```json
{
    "is_complete": true,
    "completion_percentage": 100,
    "missing_fields": [],
    "has_completed_onboarding": true,
    "onboarding_completed_at": "2025-11-10T14:30:00Z",
    "onboarding_skipped": false,
    "first_login_completed": true,
    "can_skip_onboarding": true,
    "required_documents": [],
    "onboarding_workflow_state": null
}
```

### Example 3: Onboarding Skipped

**Backend State:**
```python
user.onboarding_skipped = True
user.onboarding_completed_at = None
user.first_login_completed = True
```

**Expected API Response:**
```json
{
    "is_complete": false,
    "completion_percentage": 25,
    "missing_fields": [...],
    "has_completed_onboarding": false,
    "onboarding_completed_at": null,
    "onboarding_skipped": true,
    "first_login_completed": true,
    "can_skip_onboarding": false,
    "required_documents": [],
    "onboarding_workflow_state": null
}
```

---

## 📞 CRITICAL: Request/Response Examples

### Request Example: Mark Complete

**Mobile Sends:**
```http
POST /api/v2/profile/mark-onboarding-complete/ HTTP/1.1
Host: api.intelliwiz.com
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: application/json

{
    "skipped": false,
    "completed_steps": [
        "welcome",
        "permissions",
        "profile_setup",
        "safety_briefing",
        "feature_tour"
    ]
}
```

**Backend Should Return:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "success": true,
    "onboarding_completed_at": "2025-11-12T10:30:15.123Z",
    "onboarding_skipped": false,
    "first_login_completed": true
}
```

**Backend Should Do:**
```python
user.first_login_completed = True
user.onboarding_skipped = False
user.onboarding_completed_at = timezone.now()
user.people_extras['onboarding'] = {
    'completed_steps': request.data['completed_steps'],
    'completed_at': user.onboarding_completed_at.isoformat(),
    'skipped': False,
    'version': '1.0'
}
user.save()
```

### Request Example: Upload Image

**Mobile Sends:**
```http
POST /api/v2/profile/me/image/ HTTP/1.1
Host: api.intelliwiz.com
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...

------WebKitFormBoundary...
Content-Disposition: form-data; name="image"; filename="avatar.jpg"
Content-Type: image/jpeg

<binary image data>
------WebKitFormBoundary...--
```

**Backend Should:**
1. Validate image (size, format, dimensions)
2. Save to `profile.peopleimg`
3. Recalculate `profile.profile_completion_percentage`
4. Return image URL + new percentage

**Backend Should Return:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "image_url": "https://cdn.intelliwiz.com/media/profiles/123.jpg",
    "profile_completion_percentage": 100
}
```

---

## 🎯 MOBILE TESTING CHECKLIST

After backend implementation, we will test:

**API Functionality:**
- [ ] GET /profile/completion-status/ returns correct data
- [ ] Completion percentage calculates correctly (2/4 fields = 50%)
- [ ] Missing fields list is accurate
- [ ] POST /mark-onboarding-complete/ updates database
- [ ] Completed steps stored in people_extras
- [ ] Timestamps in ISO 8601 format
- [ ] POST /profile/me/image/ saves image
- [ ] Image URL is accessible (CORS, CDN config)

**Capability Enforcement:**
- [ ] User without canAccessOnboarding gets 403
- [ ] User with canAccessOnboarding gets 200
- [ ] 403 response has expected error message

**Error Handling:**
- [ ] 6MB image → 400 "Image file too large"
- [ ] Invalid format → 400 "Invalid file type"
- [ ] Missing required field → 400 with field errors
- [ ] Invalid completed_steps → 400 "Invalid step"

**Multi-Tenancy:**
- [ ] User A cannot access User B's profile
- [ ] Tenant isolation enforced
- [ ] No cross-tenant data leakage

---

## 🔗 REFERENCE: Mobile Files for Backend Team

If you want to see exact mobile implementation:

**Mobile Repository (shows how we call your APIs):**
```
intelliwiz-android/app/src/main/kotlin/com/intelliwiz/mobile/
    data/repository/onboarding/OnboardingRepositoryImpl.kt
```

**Mobile API Interface (shows exact endpoints we call):**
```
intelliwiz-android/app/src/main/kotlin/com/intelliwiz/mobile/
    data/remote/onboarding/OnboardingApi.kt
```

**Mobile DTOs (shows exact JSON structure we parse):**
```
intelliwiz-android/app/src/main/kotlin/com/intelliwiz/mobile/
    data/remote/onboarding/dto/ProfileCompletionDto.kt
    data/remote/onboarding/dto/MarkOnboardingCompleteRequestDto.kt
    data/remote/onboarding/dto/MarkOnboardingCompleteResponseDto.kt
    data/remote/onboarding/dto/ProfileImageResponseDto.kt
```

**Mobile Tests (shows expected behavior):**
```
intelliwiz-android/app/src/test/kotlin/com/intelliwiz/mobile/
    data/repository/onboarding/OnboardingRepositoryImplTest.kt
```

These files are committed in the IntelliWiz Android repository and can be referenced for exact specifications.

---

**Document Version:** 2.0 (Enhanced with Mobile Implementation Details)
**Created:** 2025-11-12
**Last Updated:** 2025-11-12 (Post-Implementation)
**Status:** Ready for Backend Team Implementation
**Mobile Status:** ✅ COMPLETE - Waiting for Backend APIs
