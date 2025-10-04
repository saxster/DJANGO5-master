# Backend Fix Checklist - Kotlin Frontend Integration

**Version**: 1.0
**Priority**: CRITICAL - Must be completed before mobile app deployment
**Estimated Effort**: 2-4 hours
**Last Updated**: 2025-09-28

---

## 🎯 Overview

This checklist addresses critical inconsistencies in the Django backend that will cause integration failures with the Kotlin Android frontend. All fixes are mandatory before mobile app deployment.

---

## 🚨 CRITICAL FIXES (P0)

### Fix 1: Audio MIME Type Standardization

**Issue**: Backend has conflicting audio format specifications
- `apps/onboarding_api/views.py:2385-2391` accepts: `audio/mp3`
- `apps/onboarding_api/serializers/site_audit_serializers.py:183-186` validates: `audio/mpeg`

**Impact**: Kotlin client audio uploads will fail with validation errors

**Fix Required**:

#### 1.1 Update Serializer Validation

**File**: `apps/onboarding_api/serializers/site_audit_serializers.py`

**Location**: Line 180-198 (ObservationCreateSerializer.validate_audio)

**Current Code**:
```python
def validate_audio(self, value):
    """Validate audio file type and size."""
    if value:
        allowed_types = [
            'audio/wav', 'audio/mpeg', 'audio/mp3',  # ← Inconsistent
            'audio/ogg', 'audio/webm', 'audio/flac'
        ]
        # ...
```

**Replace With**:
```python
# Add constant at module level
SUPPORTED_AUDIO_FORMATS = [
    'audio/webm',
    'audio/wav',
    'audio/mpeg',  # Standard MIME type
    'audio/mp3',   # Non-standard but widely used
    'audio/ogg',
    'audio/m4a',
    'audio/aac',
    'audio/flac'
]

def validate_audio(self, value):
    """Validate audio file type and size."""
    if value:
        if value.content_type not in SUPPORTED_AUDIO_FORMATS:
            raise serializers.ValidationError(
                f"Invalid audio type. Allowed: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
            )

        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Audio file too large. Maximum size: {max_size / 1024 / 1024}MB"
            )

    return value
```

#### 1.2 Update Voice Capabilities Response

**File**: `apps/onboarding_api/views.py`

**Location**: Line 2384-2392 (VoiceCapabilityView.get)

**Current Code**:
```python
"supported_formats": [
    "audio/webm",
    "audio/wav",
    "audio/mp3",
    "audio/ogg",
    "audio/m4a",
    "audio/aac",
    "audio/flac"
],
```

**Replace With**:
```python
from .serializers.site_audit_serializers import SUPPORTED_AUDIO_FORMATS

"supported_formats": SUPPORTED_AUDIO_FORMATS,
```

#### 1.3 Update Voice Input Validation

**File**: `apps/onboarding_api/views.py`

**Location**: Line 2200-2250 (ConversationVoiceInputView.post)

**Find Code**:
```python
ALLOWED_AUDIO_FORMATS = [
    'audio/webm', 'audio/wav', 'audio/mp3',
    'audio/ogg', 'audio/mpeg', 'audio/flac'
]
```

**Replace With**:
```python
from .serializers.site_audit_serializers import SUPPORTED_AUDIO_FORMATS

ALLOWED_AUDIO_FORMATS = SUPPORTED_AUDIO_FORMATS
```

**Testing**:
- [ ] Upload voice input with `audio/mp3` Content-Type → Should succeed
- [ ] Upload voice input with `audio/mpeg` Content-Type → Should succeed
- [ ] Upload site observation audio with `audio/mp3` → Should succeed
- [ ] Upload site observation audio with `audio/mpeg` → Should succeed
- [ ] Verify `/voice/capabilities/` returns consistent list

**Verification Command**:
```bash
# Test voice upload
curl -X POST "http://localhost:8000/api/v1/onboarding/conversation/{id}/voice/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "audio=@test.mp3" \
  -F "language=en-US"

# Should return 200, not 400 validation error
```

---

### Fix 2: Approval ID Type Consistency

**Issue**: URL route uses `<int:approval_id>` but documentation doesn't specify type

**Impact**: Frontend may send UUID string instead of integer, causing 404 errors

**Fix Required**:

#### 2.1 Verify URL Pattern

**File**: `apps/onboarding_api/urls.py`

**Location**: Line 78-82

**Verify This Exists**:
```python
path(
    'approvals/<int:approval_id>/decide/',  # ← Confirms INT type
    views.SecondaryApprovalView.as_view(),
    name='secondary-approval-decide'
),
```

✅ **No code change needed** - URL pattern is correct

#### 2.2 Add Type Validation in View

**File**: `apps/onboarding_api/views.py`

**Location**: SecondaryApprovalView class

**Add Validation**:
```python
class SecondaryApprovalView(APIView):
    """
    POST /api/v1/onboarding/approvals/{approval_id}/decide/

    Note: approval_id is INTEGER, not UUID
    """
    permission_classes = [IsAuthenticated, CanApproveAIRecommendations]

    def post(self, request, approval_id):
        # Validate approval_id is integer
        if not isinstance(approval_id, int):
            return Response(
                {'error': 'approval_id must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Rest of implementation...
```

**Testing**:
- [ ] POST to `/approvals/12345/decide/` with integer → Should succeed
- [ ] POST to `/approvals/uuid-string/decide/` → Should return 404
- [ ] Verify response from `/recommendations/approve/` includes integer `approval_id`

**Verification Command**:
```bash
# Test with integer (should work)
curl -X POST "http://localhost:8000/api/v1/onboarding/approvals/123/decide/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "comments": "Test"}'

# Test with UUID (should fail with 404)
curl -X POST "http://localhost:8000/api/v1/onboarding/approvals/3fa85f64-5717-4562-b3fc-2c963f66afa6/decide/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved"}'
```

---

## ⚠️ HIGH PRIORITY FIXES (P1)

### Fix 3: Error Response Format Consistency

**Issue**: Error responses use inconsistent formats across endpoints

**Impact**: Frontend cannot reliably parse error messages

**Fix Required**:

#### 3.1 Create Standardized Error Response Utility

**File**: `apps/onboarding_api/utils/responses.py` (create new file)

```python
"""
Standardized error response utilities for consistent API error handling.
"""
from rest_framework.response import Response
from rest_framework import status as http_status


def error_response(message: str, status_code: int = http_status.HTTP_400_BAD_REQUEST, **kwargs):
    """
    Return standardized generic error response.

    Format: {"error": "message", **additional_fields}
    """
    data = {"error": message}
    data.update(kwargs)
    return Response(data, status=status_code)


def validation_error_response(field_errors: dict, status_code: int = http_status.HTTP_400_BAD_REQUEST):
    """
    Return standardized field-level validation error.

    Format: {
        "field_name": ["error message 1", "error message 2"],
        "another_field": ["error message"]
    }
    """
    return Response(field_errors, status=status_code)


def non_field_error_response(errors: list, status_code: int = http_status.HTTP_400_BAD_REQUEST):
    """
    Return standardized non-field errors.

    Format: {"errors": ["error message 1", "error message 2"]}
    """
    return Response({"errors": errors}, status=status_code)
```

#### 3.2 Update Views to Use Standardized Responses

**Example Updates** (apply pattern to all views):

**File**: `apps/onboarding_api/views/site_audit_views.py`

**Before**:
```python
return Response(
    {'error': str(e)},
    status=status.HTTP_400_BAD_REQUEST
)
```

**After**:
```python
from ..utils.responses import error_response

return error_response(str(e), status.HTTP_400_BAD_REQUEST)
```

**Testing**:
- [ ] Invalid request → Returns `{"error": "message"}`
- [ ] Validation error → Returns `{"field_name": ["error"]}`
- [ ] Multiple validation errors → Returns `{"errors": [...]}`
- [ ] 500 error → Returns `{"error": "message", "support_reference": "..."}`

---

### Fix 4: CSRF Protection Documentation

**Issue**: GraphQL CSRF requirements not documented for API consumers

**Impact**: Frontend GraphQL mutations may fail with CSRF errors

**Fix Required**:

#### 4.1 Update GraphQL View with Documentation

**File**: `intelliwiz_config/urls_optimized.py`

**Location**: Line 84-88

**Add Comment**:
```python
# GraphQL endpoints with CSRF protection (vulnerability fix: CVSS 8.1)
# CSRF protection handled by GraphQLCSRFProtectionMiddleware
# Queries (read-only): No CSRF required
# Mutations: Require CSRF token OR JWT authentication
# Mobile apps: Use JWT-only mode (no CSRF token needed)
path('api/graphql/', FileUploadGraphQLView.as_view(graphiql=True)),
```

#### 4.2 Add CSRF Bypass for JWT-Authenticated Requests

**File**: `apps/core/middleware/graphql_csrf.py` (verify exists)

**Ensure This Logic Exists**:
```python
class GraphQLCSRFProtectionMiddleware:
    def __call__(self, request):
        # Check if request has valid JWT token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer ') and self.validate_jwt(auth_header):
            # JWT authentication - bypass CSRF check
            return self.get_response(request)

        # No JWT - enforce CSRF for mutations
        if self.is_graphql_mutation(request):
            csrf_token = request.headers.get('X-CSRFToken')
            if not csrf_token or not self.validate_csrf(csrf_token):
                return JsonResponse(
                    {'error': 'CSRF token missing or invalid for GraphQL mutation'},
                    status=403
                )

        return self.get_response(request)
```

**Testing**:
- [ ] GraphQL query without CSRF → Should succeed
- [ ] GraphQL mutation with JWT, no CSRF → Should succeed
- [ ] GraphQL mutation without JWT or CSRF → Should fail with 403

---

## 📋 MEDIUM PRIORITY FIXES (P2)

### Fix 5: Datetime Format Documentation

**Issue**: Datetime format documented but not explicitly validated

**Fix Required**:

#### 5.1 Add Datetime Format Validation Test

**File**: `apps/onboarding_api/tests/test_serializers.py` (create if needed)

```python
from datetime import datetime
from django.test import TestCase
from rest_framework import serializers


class DatetimeFormatTestCase(TestCase):
    """Verify datetime serialization format matches contract."""

    def test_datetime_format_with_microseconds(self):
        """Datetime should serialize as %Y-%m-%dT%H:%M:%S.%fZ"""
        from django.conf import settings

        # Verify DRF datetime format setting
        expected_format = '%Y-%m-%dT%H:%M:%S.%fZ'
        actual_format = settings.REST_FRAMEWORK['DATETIME_FORMAT']

        self.assertEqual(expected_format, actual_format,
            "DRF DATETIME_FORMAT must match contract specification")

    def test_datetime_serialization_output(self):
        """Verify actual serialization output format."""
        from rest_framework.fields import DateTimeField

        dt = datetime(2025, 9, 28, 12, 34, 56, 789123)
        field = DateTimeField()
        serialized = field.to_representation(dt)

        # Should match: 2025-09-28T12:34:56.789123Z
        self.assertRegex(serialized, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$')
```

**Testing**:
- [ ] Run test suite → All datetime format tests pass

---

### Fix 6: Rate Limit Response Headers

**Issue**: Rate limit responses should include `Retry-After` header

**Fix Required**:

#### 6.1 Update Rate Limit Handler

**File**: `apps/core/middleware/rate_limiting.py` (or wherever throttling is handled)

**Ensure This Logic Exists**:
```python
from rest_framework.throttling import UserRateThrottle


class EnhancedUserRateThrottle(UserRateThrottle):
    """User rate throttle with Retry-After header."""

    def throttle_failure(self, request, wait):
        """Add Retry-After header on throttle failure."""
        # DRF will raise Throttled exception with wait time
        # This gets caught by exception handler
        return super().throttle_failure(request, wait)


# In exception handler (apps/core/api_versioning/exception_handler.py)
def versioned_exception_handler(exc, context):
    """Enhanced exception handler with Retry-After for throttling."""
    if isinstance(exc, Throttled):
        response = Response(
            {
                'error': 'Rate limit exceeded',
                'detail': str(exc.detail),
                'retry_after': int(exc.wait)
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
        response['Retry-After'] = str(int(exc.wait))
        return response

    # Handle other exceptions...
```

**Testing**:
- [ ] Trigger rate limit → Response includes `Retry-After` header
- [ ] Response body includes `retry_after` field

---

## ✅ Verification & Testing

### Pre-Deployment Checklist

- [ ] All P0 (Critical) fixes completed
- [ ] All P1 (High Priority) fixes completed
- [ ] Unit tests pass for all modified code
- [ ] Integration tests pass with Kotlin client
- [ ] API documentation updated
- [ ] Migration guide prepared (if needed)

### Manual Testing Script

**File**: `scripts/test_kotlin_contract_compliance.sh` (create new file)

```bash
#!/bin/bash
# Test script to verify Kotlin frontend contract compliance

BASE_URL="http://localhost:8000/api/v1/onboarding"
TOKEN="your-jwt-token-here"

echo "Testing Audio MIME Type Support..."
curl -X POST "$BASE_URL/conversation/test-id/voice/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "audio=@test_files/audio.mp3" \
  -F "language=en-US" \
  | jq '.transcription.text'

curl -X POST "$BASE_URL/conversation/test-id/voice/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "audio=@test_files/audio_mpeg.mp3;type=audio/mpeg" \
  -F "language=en-US" \
  | jq '.transcription.text'

echo "Testing Coordinate Serialization..."
curl -X POST "$BASE_URL/site-audit/start/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_unit_id": "test-uuid",
    "site_type": "bank_branch",
    "gps_location": {"latitude": 19.076, "longitude": 72.877}
  }' | jq '.zones[0].gps_coordinates'

echo "Testing Approval ID Type..."
curl -X POST "$BASE_URL/recommendations/approve/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "approved_items": [],
    "rejected_items": [],
    "dry_run": true
  }' | jq '.approval_id | type'

echo "Testing Error Response Format..."
curl -X POST "$BASE_URL/site-audit/start/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}' \
  | jq 'keys'

echo "All tests complete!"
```

**Make executable**:
```bash
chmod +x scripts/test_kotlin_contract_compliance.sh
```

### Automated Testing

**File**: `apps/onboarding_api/tests/test_kotlin_contract_compliance.py` (create new)

```python
"""
Test suite to verify API contract compliance for Kotlin frontend.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
import json


class KotlinContractComplianceTest(TestCase):
    """Verify backend adheres to Kotlin frontend contract."""

    def setUp(self):
        self.client = APIClient()
        # Create test user and authenticate
        # self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)

    def test_audio_mime_types_audio_mp3(self):
        """Verify audio/mp3 is accepted."""
        # Test implementation...

    def test_audio_mime_types_audio_mpeg(self):
        """Verify audio/mpeg is accepted."""
        # Test implementation...

    def test_approval_id_is_integer(self):
        """Verify approval_id in response is integer type."""
        # Test implementation...

    def test_error_response_format_generic(self):
        """Verify generic errors use {"error": "message"} format."""
        # Test implementation...

    def test_error_response_format_validation(self):
        """Verify field errors use {field: [errors]} format."""
        # Test implementation...

    def test_datetime_format_with_microseconds(self):
        """Verify datetime serialization includes microseconds."""
        # Test implementation...

    def test_rate_limit_includes_retry_after(self):
        """Verify 429 responses include Retry-After header."""
        # Test implementation...
```

---

## 📊 Progress Tracking

### Fix Status

| Fix # | Priority | Description | Status | Assignee | ETA |
|-------|----------|-------------|--------|----------|-----|
| 1 | P0 | Audio MIME types | ⏳ Pending | | |
| 2 | P0 | Approval ID type | ⏳ Pending | | |
| 3 | P1 | Error response format | ⏳ Pending | | |
| 4 | P1 | CSRF documentation | ⏳ Pending | | |
| 5 | P2 | Datetime validation | ⏳ Pending | | |
| 6 | P2 | Rate limit headers | ⏳ Pending | | |

**Legend**: ⏳ Pending | 🚧 In Progress | ✅ Complete | ❌ Blocked

---

## 🚀 Deployment Plan

### Phase 1: Critical Fixes (Week 1)
1. Fix 1: Audio MIME types (Day 1-2)
2. Fix 2: Approval ID validation (Day 2)
3. Integration testing with Kotlin team (Day 3-5)

### Phase 2: High Priority (Week 2)
4. Fix 3: Error response standardization (Day 1-3)
5. Fix 4: CSRF documentation (Day 3-4)
6. Contract testing setup (Day 4-5)

### Phase 3: Medium Priority (Week 3)
7. Fix 5: Datetime validation tests (Day 1-2)
8. Fix 6: Rate limit headers (Day 2-3)
9. Final verification (Day 4-5)

---

## 📞 Support

**Questions or Issues**:
- Backend Team Lead: backend-lead@youtility.in
- Frontend Team: mobile-team@youtility.in
- Contract Issues: https://github.com/youtility/api-contracts/issues

**Review Schedule**:
- Daily standup: 10:00 AM IST
- Weekly sync: Every Monday 3:00 PM IST
- Final review: Before mobile app release

---

**Checklist Version**: 1.0
**Last Updated**: 2025-09-28
**Next Review**: Weekly until all fixes complete