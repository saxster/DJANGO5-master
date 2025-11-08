# API Version Resolution Strategy

> **Critical**: Resolving v1 vs v2 endpoint mismatches between Kotlin documentation and Django backend

---

## Problem Summary

**12 Critical Mismatches Found:**

| Issue | Kotlin Docs | Django Reality | Impact |
|-------|-------------|----------------|--------|
| Base URL | `/api/v2/operations/` | `/api/v1/operations/` | **BREAKING** - All operations endpoints |
| Base URL | `/api/v2/attendance/` | `/api/v1/attendance/` | **BREAKING** - All attendance endpoints |
| Base URL | `/api/v2/people/` | `/api/v1/people/` | **BREAKING** - All people endpoints |
| Base URL | `/api/v2/helpdesk/` | `/api/v1/help-desk/tickets/` | **BREAKING** - All helpdesk endpoints |
| Field names | `title`, `assigned_to` | `jobneedname`, `people` | **BREAKING** - Job schema |
| Endpoint | `POST /checkin/` | `POST /clock-in/` | **BREAKING** - Attendance workflow |
| WebSocket param | `mobile_id` | `device_id` | **BREAKING** - WebSocket connection |
| Endpoint missing | `/jobs/{id}/approve/` | Not implemented | **BLOCKING** - Approval workflow |
| Endpoint missing | `/answers/` | Not implemented | **BLOCKING** - Cannot submit answers |
| Photo format | Base64 in JSON | Multipart form-data | **INCONSISTENT** |
| Response envelope | Not standardized | Various shapes | **INCONSISTENT** |
| Pagination | Not specified | DRF default | **INCONSISTENT** |

---

## Resolution Strategy

### Phase 1: Immediate Fixes (48-72 hours)

#### 1.1 Freeze on v2 as Canonical Source of Truth

**Decision**: All new development uses `/api/v2/` with standardized conventions.

**Backend Actions**:
- Create `/api/v2/operations/`, `/api/v2/attendance/`, `/api/v2/people/`, `/api/v2/helpdesk/` URL namespaces
- Keep `/api/v1/` endpoints as-is for backward compatibility
- Add `Deprecation` header to all v1 responses:
  ```python
  response['Deprecation'] = 'true'
  response['Sunset'] = 'Wed, 31 Jan 2026 00:00:00 GMT'
  response['Link'] = '</docs/migration-v1-to-v2>; rel="deprecation"'
  ```

**Kotlin Documentation Actions**:
- Update all API contract documents to use `/api/v2/` exclusively
- Remove all v1 references
- Add migration guide from v1 to v2

#### 1.2 Standardize JSON Conventions

**Decision**: Use `snake_case` consistently (matches Django conventions).

**Standard Response Envelope** (ALL v2 endpoints):
```json
{
  "success": true,
  "data": { /* actual payload */ },
  "errors": null,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "execution_time_ms": 25.5,
  "timestamp": "2025-11-07T12:34:56Z"
}
```

**Error Response Envelope**:
```json
{
  "success": false,
  "data": null,
  "errors": [
    {
      "error_code": "VALIDATION_ERROR",
      "message": "Invalid input data",
      "field": "title",
      "details": "Title must be between 3 and 200 characters"
    }
  ],
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-11-07T12:34:56Z"
}
```

**Standard Pagination Envelope**:
```json
{
  "success": true,
  "data": {
    "count": 47,
    "next": "https://api.intelliwiz.com/api/v2/operations/jobs/?page=2",
    "previous": null,
    "results": [ /* array of items */ ]
  },
  "correlation_id": "...",
  "timestamp": "..."
}
```

#### 1.3 Create API v2 URL Structure

**File**: `apps/api/v2/operations_urls.py` (NEW)
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.activity.api.v2 import viewsets

router = DefaultRouter()
router.register(r'jobs', viewsets.JobViewSetV2, basename='job')
router.register(r'tours', viewsets.TourViewSetV2, basename='tour')
router.register(r'tasks', viewsets.TaskViewSetV2, basename='task')
router.register(r'questions', viewsets.QuestionViewSetV2, basename='question')

app_name = 'operations_v2'

urlpatterns = [
    path('', include(router.urls)),
    path('answers/', viewsets.AnswerSubmissionView.as_view(), name='answer-submission'),
]
```

**File**: `apps/api/v2/attendance_urls.py` (NEW)
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.attendance.api.v2 import viewsets

app_name = 'attendance_v2'

urlpatterns = [
    path('checkin/', viewsets.CheckInView.as_view(), name='checkin'),
    path('checkout/', viewsets.CheckOutView.as_view(), name='checkout'),
    path('geofence/validate/', viewsets.GeofenceValidationView.as_view(), name='geofence-validate'),
    path('fraud/detect/', viewsets.FraudDetectionView.as_view(), name='fraud-detect'),
    path('conveyance/', viewsets.ConveyanceView.as_view(), name='conveyance-create'),
    path('conveyance/<int:pk>/', viewsets.ConveyanceDetailView.as_view(), name='conveyance-detail'),
    path('pay-rates/<int:user_id>/', viewsets.PayRateView.as_view(), name='pay-rates'),
    path('face/enroll/', viewsets.FaceEnrollmentView.as_view(), name='face-enroll'),
]
```

**File**: `intelliwiz_config/urls_optimized.py` (UPDATE)
```python
# Add these to existing v2 paths:
path('api/v2/operations/', include('apps.api.v2.operations_urls')),
path('api/v2/attendance/', include('apps.api.v2.attendance_urls')),
path('api/v2/people/', include('apps.api.v2.people_urls')),
path('api/v2/helpdesk/', include('apps.api.v2.helpdesk_urls')),
```

---

### Phase 2: Complete Missing Endpoints (1-2 weeks)

#### 2.1 Operations Domain - Missing Endpoints

**Priority 1 - BLOCKING**:
1. `POST /api/v2/operations/answers/` - Submit answers to questions
2. `POST /api/v2/operations/jobs/{id}/approve/` - Approve job completion
3. `POST /api/v2/operations/jobs/{id}/reject/` - Reject job with comments

**Priority 2 - HIGH**:
4. `GET /api/v2/operations/tours/` - List tours
5. `POST /api/v2/operations/tours/` - Create tour
6. `GET /api/v2/operations/tasks/` - List PPM tasks
7. `GET /api/v2/operations/questions/{id}/` - Get question details

**Implementation Template**:
```python
# apps/activity/api/v2/viewsets.py
from apps.core.api_responses import create_success_response, create_error_response
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

class JobViewSetV2(viewsets.ModelViewSet):
    """V2 Job endpoints with standardized responses"""
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve job completion"""
        job = self.get_object()
        serializer = JobApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                create_error_response(serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = JobService.approve_job(
            job=job,
            approved_by=request.user,
            comments=serializer.validated_data.get('comments')
        )
        
        return Response(
            create_success_response(
                JobSerializer(result).data,
                execution_time_ms=request.execution_time
            ),
            status=status.HTTP_200_OK
        )
```

#### 2.2 Attendance Domain - Missing Endpoints

**Priority 1 - BLOCKING**:
1. `GET /api/v2/attendance/pay-rates/{user_id}/` - Get pay calculation parameters
2. `POST /api/v2/attendance/face/enroll/` - Enroll facial biometrics

**Implementation**:
```python
# apps/attendance/api/v2/viewsets.py
class PayRateView(APIView):
    """Get pay calculation parameters for user"""
    
    def get(self, request, user_id):
        pay_rate = PayRateService.get_user_pay_rate(user_id)
        
        return Response(create_success_response({
            'base_hourly_rate': str(pay_rate.base_rate),
            'currency': pay_rate.currency,
            'overtime_multiplier': pay_rate.overtime_multiplier,
            'break_minutes': pay_rate.break_minutes,
            'premiums': {
                'night_shift': pay_rate.night_shift_premium,
                'weekend': pay_rate.weekend_premium,
                'holiday': pay_rate.holiday_premium
            },
            'calculation_rules': {
                'grace_period_minutes': 5,
                'rounding_method': 'nearest_15_minutes',
                'overtime_threshold_hours': 8
            }
        }))

class FaceEnrollmentView(APIView):
    """Enroll facial biometrics"""
    parser_classes = [MultiPartParser]
    
    def post(self, request):
        serializer = FaceEnrollmentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                create_error_response(serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process 3 photos for enrollment
        result = FacialRecognitionService.enroll_user(
            user=request.user,
            photos=request.FILES.getlist('photos'),
            quality_threshold=0.85
        )
        
        return Response(
            create_success_response(result),
            status=status.HTTP_201_CREATED
        )
```

---

### Phase 3: Field Name Standardization (Week 2)

#### 3.1 Operations Field Mapping

**Create V2 Serializers** with clean field names:

```python
# apps/activity/api/v2/serializers.py
class JobSerializerV2(serializers.ModelSerializer):
    """V2 serializer with clean field names"""
    
    # Map old fields to new names
    title = serializers.CharField(source='jobneedname', max_length=200)
    description = serializers.CharField(source='jobneedneed', allow_blank=True)
    assigned_to = serializers.PrimaryKeyRelatedField(
        source='people',
        many=True,
        queryset=People.objects.all()
    )
    job_type = serializers.CharField(source='jobtype')
    
    class Meta:
        model = Jobneed
        fields = [
            'id', 'title', 'description', 'job_type', 'status',
            'assigned_to', 'scheduled_start', 'scheduled_end',
            'location', 'priority', 'version', 'created_at', 'updated_at'
        ]
```

#### 3.2 Attendance Field Mapping

```python
# apps/attendance/api/v2/serializers.py
class CheckInSerializerV2(serializers.Serializer):
    """Clean V2 check-in schema"""
    
    post_id = serializers.IntegerField()
    location = serializers.DictField()  # {latitude, longitude, accuracy}
    timestamp = serializers.DateTimeField()
    face_photo = serializers.ImageField(required=False)
    consent_given = serializers.BooleanField(default=True)
    device_info = serializers.DictField()
    
    def validate(self, data):
        # GPS accuracy validation
        if data['location']['accuracy'] > 50:
            raise serializers.ValidationError({
                'location': 'GPS accuracy must be < 50 meters'
            })
        
        # Photo requirement
        post = Post.objects.get(id=data['post_id'])
        if post.requires_facial_recognition and 'face_photo' not in data:
            raise serializers.ValidationError({
                'face_photo': 'Facial recognition photo required for this post'
            })
        
        return data
```

---

### Phase 4: OpenAPI Schema Generation (Week 2)

#### 4.1 Configure drf-spectacular

**File**: `intelliwiz_config/settings/rest_api_core.py` (UPDATE)
```python
INSTALLED_APPS += ['drf_spectacular']

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # ... existing config
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'IntelliWiz Mobile API',
    'DESCRIPTION': 'Type-safe API for Kotlin/Android and Swift/iOS mobile apps',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/v2/',
    'SERVERS': [
        {'url': 'https://api.intelliwiz.com', 'description': 'Production'},
        {'url': 'http://localhost:8000', 'description': 'Development'},
    ],
    'SECURITY': [{'bearerAuth': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'bearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
    'ENUM_NAME_OVERRIDES': {
        'JobStatus': 'apps.activity.models.JobStatus',
        'AttendanceStatus': 'apps.attendance.models.AttendanceStatus',
    },
    'POSTPROCESSING_HOOKS': [
        'apps.core.openapi.postprocess_schema_enums',
    ],
}
```

#### 4.2 Generate and Validate Schema

```bash
# Generate OpenAPI schema
python manage.py spectacular --file docs/kotlin-frontend/openapi/openapi-v2.yaml --validate

# Install validation tools
pip install openapi-spec-validator spectral-cli

# Validate schema
openapi-spec-validator docs/kotlin-frontend/openapi/openapi-v2.yaml

# Lint with Spectral
spectral lint docs/kotlin-frontend/openapi/openapi-v2.yaml \
  --ruleset docs/kotlin-frontend/openapi/.spectral.yaml
```

#### 4.3 Spectral Lint Rules

**File**: `docs/kotlin-frontend/openapi/.spectral.yaml` (NEW)
```yaml
extends: spectral:oas
rules:
  # Enforce snake_case for all properties
  property-casing:
    message: "{{property}} must use snake_case"
    severity: error
    given: "$.paths..properties.*~"
    then:
      function: pattern
      functionOptions:
        match: "^[a-z][a-z0-9_]*$"
  
  # Require error responses to have error_code
  error-response-structure:
    message: "Error responses must include error_code field"
    severity: error
    given: "$.paths..responses[?(@property.match(/^[45]/))]..properties"
    then:
      field: error_code
      function: truthy
  
  # Require correlation_id in all responses
  correlation-id-required:
    message: "All responses must include correlation_id"
    severity: warn
    given: "$.paths..responses..properties"
    then:
      field: correlation_id
      function: truthy
  
  # Consistent pagination
  pagination-consistency:
    message: "List endpoints must use consistent pagination parameters"
    severity: error
    given: "$.paths[?(@property.match(/.*\/$/))].get.parameters"
    then:
      field: "@"
      function: schema
      functionOptions:
        schema:
          type: array
          contains:
            oneOf:
              - { name: "page" }
              - { name: "limit" }
```

---

### Phase 5: CI/CD Contract Testing (Week 3)

#### 5.1 GitHub Actions Workflow

**File**: `.github/workflows/api-contract-tests.yml` (NEW)
```yaml
name: API Contract Tests

on:
  pull_request:
    paths:
      - 'apps/*/api/**'
      - 'apps/api/v2/**'
      - 'docs/kotlin-frontend/openapi/**'
  push:
    branches: [main]

jobs:
  contract-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Generate OpenAPI Schema
        run: |
          python manage.py spectacular --file openapi-generated.yaml
      
      - name: Validate Schema
        run: |
          openapi-spec-validator openapi-generated.yaml
      
      - name: Lint with Spectral
        run: |
          spectral lint openapi-generated.yaml \
            --ruleset docs/kotlin-frontend/openapi/.spectral.yaml
      
      - name: Detect Breaking Changes
        run: |
          pip install openapi-diff
          openapi-diff docs/kotlin-frontend/openapi/openapi-v2.yaml \
            openapi-generated.yaml \
            --fail-on-incompatible
  
  schemathesis-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:14-3.2
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Django
        run: |
          python manage.py migrate
          python manage.py runserver &
          sleep 10
      
      - name: Run Schemathesis
        run: |
          pip install schemathesis
          schemathesis run http://localhost:8000/api/schema/ \
            --checks all \
            --hypothesis-max-examples=50 \
            --base-url=http://localhost:8000 \
            --auth-type=bearer \
            --auth=${{ secrets.TEST_JWT_TOKEN }}
```

---

## Migration Timeline

### Week 0: Freeze & Decide
- ✅ Freeze on v2 as canonical
- ✅ Document 12 mismatches
- ✅ Create resolution strategy
- ✅ Stakeholder alignment

### Week 1: Backend Implementation
- Create `/api/v2/` URL structure
- Implement missing endpoints (approve, reject, answers)
- Create V2 serializers with clean field names
- Add deprecation headers to v1
- Generate initial OpenAPI v2 schema

### Week 2: Documentation Update
- Update all Kotlin API contracts to v2
- Add complete field validation tables
- Document all error codes
- Create migration guide from v1 to v2
- Set up Spectral linting

### Week 3: Testing & Validation
- Set up CI/CD contract tests
- Run Schemathesis against v2 endpoints
- Validate all examples in documentation
- Fix any contract violations
- Tag v2.0.0 release

### Week 4+: Kotlin Implementation
- Generate Kotlin DTOs from OpenAPI
- Implement Retrofit services
- Build Room database models
- Create ViewModels and UI
- End-to-end integration testing

---

## Deprecation Policy

### V1 Endpoints
- **Status**: Deprecated immediately
- **Sunset Date**: January 31, 2026 (90 days after v2 GA)
- **Support**: Bug fixes only, no new features
- **Migration Path**: See `/docs/kotlin-frontend/V1_TO_V2_MIGRATION.md`

### Breaking Change Policy
- **Minor version bump**: Additive changes only (new fields, endpoints)
- **Major version bump**: Breaking changes (field renames, removals)
- **Deprecation notice**: 60 days before removal
- **Changelog**: Required for every version bump

---

## Success Criteria

### Phase 1 Complete When:
- ✅ All v2 URLs registered in Django
- ✅ All documented endpoints return 200/201 (not 404)
- ✅ Response envelope matches specification
- ✅ OpenAPI schema validates
- ✅ Zero Spectral lint errors

### Phase 2 Complete When:
- ✅ Missing endpoints implemented
- ✅ Field names match documentation
- ✅ All examples work end-to-end
- ✅ Schemathesis passes 100%
- ✅ Breaking change detection in CI

### Ready for Kotlin Implementation When:
- ✅ OpenAPI v2.0.0 tagged and published
- ✅ Contract tests green in CI
- ✅ All priority 1 endpoints complete
- ✅ Documentation 95%+ complete
- ✅ Mobile team sign-off

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Hidden backend dependencies on v1 | Medium | High | Comprehensive test coverage before deprecation |
| Field name changes break internal code | High | Medium | Use source= in serializers, minimal DB changes |
| Timeline slips due to complexity | Medium | Medium | Prioritize blocking endpoints first |
| Kotlin team blocked waiting | Low | High | Deliver incomplete but working endpoints incrementally |
| Breaking changes introduced accidentally | Medium | High | CI contract tests with fail-fast |

---

## Next Steps

1. **Immediate** (Today):
   - Create `apps/api/v2/operations_urls.py`
   - Create `apps/api/v2/attendance_urls.py`
   - Register in `urls_optimized.py`
   - Smoke test endpoints return 404 → implement stubs

2. **This Week**:
   - Implement JobViewSetV2 with approve/reject actions
   - Implement AnswerSubmissionView
   - Implement CheckInView/CheckOutView with clean field names
   - Generate OpenAPI schema
   - Set up Spectral linting

3. **Next Week**:
   - Update all Kotlin documentation to v2
   - Add field validation tables
   - Complete error code documentation
   - Set up CI contract tests
   - Begin Kotlin DTO generation

---

**Document Status**: ✅ Complete  
**Last Updated**: Nov 7, 2025  
**Stakeholders**: Backend Team, Mobile Team, API Editor  
**Review Cycle**: Weekly until v2.0.0 GA
