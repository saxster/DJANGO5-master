# OpenAPI & Contract Testing Implementation Guide

**Version**: 1.0
**For**: Backend & Mobile Teams
**Purpose**: Automate contract validation between Django backend and Kotlin frontend
**Last Updated**: 2025-09-28

---

## 🎯 Overview

This guide provides a comprehensive strategy for:
1. Generating OpenAPI specifications from Django REST Framework
2. Implementing contract testing with Pact
3. Automating schema validation
4. Continuous integration for API contracts

**Benefits**:
- ✅ Single source of truth for API contracts
- ✅ Automated detection of breaking changes
- ✅ Reduced integration bugs
- ✅ Living documentation that never goes stale
- ✅ Confidence in API compatibility before deployment

---

## 📚 Table of Contents

1. [OpenAPI Specification](#openapi-specification)
2. [Contract Testing with Pact](#contract-testing-with-pact)
3. [Schema Validation](#schema-validation)
4. [CI/CD Integration](#cicd-integration)
5. [Best Practices](#best-practices)

---

## OpenAPI Specification

### Why OpenAPI?

OpenAPI (formerly Swagger) provides a machine-readable API specification that can be used to:
- Generate client SDKs automatically
- Validate requests/responses at runtime
- Generate interactive API documentation
- Power contract testing frameworks

### Implementation: drf-spectacular

**Already installed** in your Django project: `intelliwiz_config/settings/rest_api.py:138-182`

#### 1. Configuration Review

**File**: `intelliwiz_config/settings/rest_api.py`

**Current Configuration** (Verify):
```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'YOUTILITY5 Enterprise API',
    'DESCRIPTION': 'Enterprise facility management platform with versioned REST and GraphQL APIs',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticatedOrReadOnly'],

    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SCHEMA_MOUNT_PATH': '/api/schema/',

    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',

    'COMPONENT_SPLIT_REQUEST': True,
    'PREPROCESSING_HOOKS': [],
    'POSTPROCESSING_HOOKS': [],

    'SERVERS': [
        {'url': 'https://api.youtility.in', 'description': 'Production'},
        {'url': 'https://staging-api.youtility.in', 'description': 'Staging'},
        {'url': 'http://localhost:8000', 'description': 'Development'},
    ],
}
```

#### 2. Generate OpenAPI Schema

**Command**:
```bash
# Generate OpenAPI 3.0 schema
python manage.py spectacular --file openapi-schema.yaml --format openapi

# Generate in JSON format
python manage.py spectacular --file openapi-schema.json --format openapi-json

# Validate generated schema
python manage.py spectacular --validate
```

**Add to Scripts**:

**File**: `scripts/generate_openapi_schema.sh` (create new)

```bash
#!/bin/bash
# Generate OpenAPI schema for API contract testing

echo "Generating OpenAPI schema..."
python manage.py spectacular \
    --file docs/openapi/youtility-api-v1.yaml \
    --format openapi \
    --api-version v1

python manage.py spectacular \
    --file docs/openapi/youtility-api-v1.json \
    --format openapi-json \
    --api-version v1

echo "Validating schema..."
python manage.py spectacular --validate

echo "Schema generation complete!"
echo "YAML: docs/openapi/youtility-api-v1.yaml"
echo "JSON: docs/openapi/youtility-api-v1.json"
```

**Make executable**:
```bash
chmod +x scripts/generate_openapi_schema.sh
```

#### 3. Expose Schema Endpoints

**File**: `apps/onboarding_api/urls.py`

**Current Configuration** (Verify exists at line 528-537):
```python
from .openapi_schemas import schema_view

# API DOCUMENTATION
re_path(r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=0),
        name='schema-json'),
re_path(r'^swagger/$',
        schema_view.with_ui('swagger', cache_timeout=0),
        name='schema-swagger-ui'),
re_path(r'^redoc/$',
        schema_view.with_ui('redoc', cache_timeout=0),
        name='schema-redoc'),
```

**Access Points**:
- Swagger UI: `http://localhost:8000/api/v1/onboarding/swagger/`
- ReDoc: `http://localhost:8000/api/v1/onboarding/redoc/`
- OpenAPI JSON: `http://localhost:8000/api/v1/onboarding/swagger.json`
- OpenAPI YAML: `http://localhost:8000/api/v1/onboarding/swagger.yaml`

#### 4. Enhance Serializers with OpenAPI Metadata

**Best Practice**: Add explicit OpenAPI documentation to serializers

**File**: `apps/onboarding_api/serializers/site_audit_serializers.py`

**Example Enhancement**:
```python
from drf_spectacular.utils import extend_schema_field, OpenApiExample
from drf_spectacular.types import OpenApiTypes

class SiteAuditStartSerializer(serializers.Serializer):
    """
    Serializer for starting a new site audit session.

    Validates business unit, site type, and optional configuration.
    """

    business_unit_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the business unit to audit"
    )

    @extend_schema_field(OpenApiTypes.STR)
    site_type = serializers.ChoiceField(
        choices=OnboardingSite.SiteTypeChoices.choices,
        required=True,
        help_text="Type of site being audited"
    )

    # Add OpenAPI examples
    class Meta:
        examples = [
            OpenApiExample(
                'Bank Branch Audit',
                value={
                    'business_unit_id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'site_type': 'bank_branch',
                    'language': 'en',
                    'operating_hours': {
                        'start': '09:00',
                        'end': '18:00'
                    },
                    'gps_location': {
                        'latitude': 19.076,
                        'longitude': 72.877
                    }
                },
                request_only=True,
            ),
        ]
```

#### 5. Enhance Views with OpenAPI Metadata

**File**: `apps/onboarding_api/views/site_audit_views.py`

**Example Enhancement**:
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

class SiteAuditStartView(APIView):
    """
    POST /api/v1/onboarding/site-audit/start/

    Initialize a new site audit session with zones and checklist.
    """

    @extend_schema(
        request=SiteAuditStartSerializer,
        responses={
            201: OpenApiResponse(
                response=SiteAuditStartSerializer,
                description='Audit session created successfully'
            ),
            400: OpenApiResponse(
                description='Validation error'
            ),
            404: OpenApiResponse(
                description='Business unit not found'
            ),
        },
        tags=['Site Audit'],
        operation_id='start_site_audit',
        summary='Start a new site audit session',
        description='''
        Initialize a new multimodal site security audit session.

        **Features**:
        - Automatic zone generation based on site type
        - Pre-configured audit checklist
        - Optimized route suggestion
        - Estimated audit duration
        ''',
    )
    def post(self, request):
        # Implementation...
```

---

## Contract Testing with Pact

### What is Pact?

**Pact** is a contract testing framework that enables consumer-driven contract testing:
- Consumer (Kotlin app) defines expectations
- Provider (Django backend) verifies it meets those expectations
- Automated verification on both sides

### Implementation Steps

#### 1. Backend Setup (Provider)

**Install Pact**:
```bash
pip install pact-python
```

**Add to requirements**:

**File**: `requirements/test.txt`

```
pact-python==2.2.0
```

**Create Pact Provider Tests**:

**File**: `apps/onboarding_api/tests/test_pact_provider.py` (create new)

```python
"""
Pact provider verification tests.

Verifies that Django backend fulfills contracts defined by Kotlin consumer.
"""
import os
from django.test import LiveServerTestCase
from pact import Verifier


class PactProviderTestCase(LiveServerTestCase):
    """Verify backend provider against Kotlin consumer contracts."""

    def setUp(self):
        self.verifier = Verifier(
            provider='django-backend',
            provider_base_url=self.live_server_url
        )

    def test_verify_pacts_from_kotlin_consumer(self):
        """
        Verify all pacts from Kotlin mobile app.

        Pact files should be published to Pact Broker or stored locally.
        """
        success, logs = self.verifier.verify_pacts(
            # Option 1: Pact Broker
            # './pacts/kotlin-mobile-app-django-backend.json',

            # Option 2: Local file
            './pacts/kotlin_consumer_pacts/',

            # Enable provider states
            provider_states_setup_url=f'{self.live_server_url}/api/v1/onboarding/pact-states/',

            # Authentication
            headers=['Authorization: Bearer test-token'],

            # Verbose output
            verbose=True,
        )

        self.assertTrue(success, f'Pact verification failed:\n{logs}')

    def test_verify_conversation_start_contract(self):
        """Verify conversation start endpoint contract."""
        success, logs = self.verifier.verify_pacts(
            './pacts/conversation_start_pact.json',
            provider_states_setup_url=f'{self.live_server_url}/api/v1/onboarding/pact-states/',
            verbose=True,
        )

        self.assertTrue(success)

    def test_verify_site_audit_start_contract(self):
        """Verify site audit start endpoint contract."""
        success, logs = self.verifier.verify_pacts(
            './pacts/site_audit_start_pact.json',
            provider_states_setup_url=f'{self.live_server_url}/api/v1/onboarding/pact-states/',
            verbose=True,
        )

        self.assertTrue(success)
```

**Create Provider States Endpoint**:

**File**: `apps/onboarding_api/views/pact_provider_states.py` (create new)

```python
"""
Pact provider state setup endpoint.

Sets up backend state for Pact contract verification.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model

User = get_user_model()


@api_view(['POST'])
def pact_provider_states(request):
    """
    Set up provider state for Pact verification.

    Pact sends state setup requests before each interaction verification.
    """
    state = request.data.get('state')
    params = request.data.get('params', {})

    if state == 'user has valid business unit association':
        # Create test user with business unit
        user = User.objects.create_user(
            loginid='test@example.com',
            password='test-password',
            peoplename='Test User'
        )
        # Associate with business unit...
        return Response({'user_id': str(user.id)})

    elif state == 'conversation session exists':
        # Create test conversation session
        session_id = params.get('session_id')
        # Create session...
        return Response({'session_id': session_id})

    elif state == 'site audit session exists':
        # Create test site audit session
        session_id = params.get('session_id')
        # Create session...
        return Response({'session_id': session_id})

    # Unknown state
    return Response({'error': f'Unknown provider state: {state}'}, status=400)
```

**Register Provider States URL**:

**File**: `apps/onboarding_api/urls.py`

```python
# Add to urlpatterns
path('pact-states/', views.pact_provider_states, name='pact-provider-states'),
```

#### 2. Kotlin Consumer Setup

**File**: (Kotlin project) `app/src/test/kotlin/ContractTests.kt`

```kotlin
import au.com.dius.pact.consumer.MockServer
import au.com.dius.pact.consumer.dsl.PactDslWithProvider
import au.com.dius.pact.consumer.junit5.PactConsumerTestExt
import au.com.dius.pact.consumer.junit5.PactTestFor
import au.com.dius.pact.core.model.RequestResponsePact
import au.com.dius.pact.core.model.annotations.Pact
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.extension.ExtendWith

@ExtendWith(PactConsumerTestExt::class)
@PactTestFor(providerName = "django-backend", hostInterface = "localhost")
class ConversationStartContractTest {

    @Pact(consumer = "kotlin-mobile-app", provider = "django-backend")
    fun conversationStartPact(builder: PactDslWithProvider): RequestResponsePact {
        return builder
            .given("user has valid business unit association")
            .uponReceiving("start conversation request")
            .path("/api/v1/onboarding/conversation/start/")
            .method("POST")
            .headers(mapOf(
                "Authorization" to "Bearer valid_token",
                "Content-Type" to "application/json"
            ))
            .body("""{
                "language": "en",
                "client_context": {},
                "initial_input": "Start setup",
                "resume_existing": false
            }""")
            .willRespondWith()
            .status(200)
            .headers(mapOf("Content-Type" to "application/json"))
            .body(PactDslJsonBody()
                .stringType("conversation_id")
                .object("enhanced_understanding")
                .closeObject()
                .array("questions")
                .closeArray()
                .object("context")
                .closeObject()
            )
            .toPact()
    }

    @Test
    @PactTestFor(pactMethod = "conversationStartPact")
    fun testConversationStart(mockServer: MockServer) {
        val apiService = ApiClient.create(mockServer.getUrl())

        val request = ConversationStartRequest(
            language = "en",
            clientContext = JsonObject(emptyMap()),
            initialInput = "Start setup",
            resumeExisting = false
        )

        val response = apiService.startConversation(request).execute()

        assert(response.isSuccessful)
        assert(response.body()?.conversationId != null)
    }
}
```

**Publish Pacts**:

```bash
# After running Kotlin consumer tests, publish pacts
./gradlew pactPublish
```

---

## Schema Validation

### Runtime Request/Response Validation

#### 1. Install OpenAPI Validator

```bash
pip install openapi-core openapi-spec-validator
```

**Add to requirements**:

**File**: `requirements/base.txt`

```
openapi-core==0.18.2
openapi-spec-validator==0.7.1
```

#### 2. Create Validation Middleware

**File**: `apps/core/middleware/openapi_validation.py` (create new)

```python
"""
OpenAPI request/response validation middleware.

Validates all API requests and responses against OpenAPI schema.
"""
import json
import logging
from django.conf import settings
from django.http import JsonResponse
from openapi_core import OpenAPI
from openapi_core.validation.request import openapi_request_validator
from openapi_core.validation.response import openapi_response_validator

logger = logging.getLogger(__name__)


class OpenAPIValidationMiddleware:
    """
    Middleware to validate requests/responses against OpenAPI schema.

    Only active in development/testing environments.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Load OpenAPI schema
        if settings.OPENAPI_SCHEMA_VALIDATION_ENABLED:
            with open(settings.OPENAPI_SCHEMA_PATH) as f:
                spec_dict = json.load(f)
                self.openapi = OpenAPI.from_dict(spec_dict)
        else:
            self.openapi = None

    def __call__(self, request):
        # Skip if not enabled or not API request
        if not self.openapi or not request.path.startswith('/api/'):
            return self.get_response(request)

        # Validate request
        try:
            validator = openapi_request_validator.RequestValidator(self.openapi)
            result = validator.validate(request)
            if result.errors:
                logger.error(f'OpenAPI request validation failed: {result.errors}')
                return JsonResponse(
                    {
                        'error': 'Request validation failed',
                        'details': [str(e) for e in result.errors]
                    },
                    status=400
                )
        except Exception as e:
            logger.warning(f'OpenAPI request validation error: {e}')

        # Get response
        response = self.get_response(request)

        # Validate response
        try:
            validator = openapi_response_validator.ResponseValidator(self.openapi)
            result = validator.validate(request, response)
            if result.errors:
                logger.error(f'OpenAPI response validation failed: {result.errors}')
        except Exception as e:
            logger.warning(f'OpenAPI response validation error: {e}')

        return response
```

**Add to Settings**:

**File**: `intelliwiz_config/settings/development.py`

```python
# OpenAPI validation (development only)
OPENAPI_SCHEMA_VALIDATION_ENABLED = True
OPENAPI_SCHEMA_PATH = BASE_DIR / 'docs/openapi/youtility-api-v1.json'

# Add to middleware (only in development)
MIDDLEWARE += [
    'apps.core.middleware.openapi_validation.OpenAPIValidationMiddleware',
]
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/contract-testing.yml` (create new)

```yaml
name: API Contract Testing

on:
  pull_request:
    paths:
      - 'apps/onboarding_api/**'
      - 'intelliwiz_config/settings/**'
  push:
    branches:
      - main
      - develop

jobs:
  generate-openapi-schema:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements/test.txt

      - name: Generate OpenAPI schema
        run: |
          python manage.py spectacular \
            --file openapi-schema-generated.yaml \
            --format openapi

      - name: Validate OpenAPI schema
        run: |
          python manage.py spectacular --validate

      - name: Upload schema artifact
        uses: actions/upload-artifact@v3
        with:
          name: openapi-schema
          path: openapi-schema-generated.yaml

      - name: Check for breaking changes
        run: |
          # Compare with committed schema
          pip install openapi-diff
          openapi-diff \
            docs/openapi/youtility-api-v1.yaml \
            openapi-schema-generated.yaml \
            --fail-on-incompatible

  verify-pact-contracts:
    runs-on: ubuntu-latest
    needs: generate-openapi-schema
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements/test.txt

      - name: Download Kotlin consumer pacts
        run: |
          # Download from Pact Broker or artifact storage
          # curl -o pacts/ https://pact-broker.youtility.in/pacts/...

      - name: Run Pact provider verification
        run: |
          python -m pytest apps/onboarding_api/tests/test_pact_provider.py -v

      - name: Publish verification results
        if: always()
        run: |
          # Publish to Pact Broker
          # curl -X PUT https://pact-broker.youtility.in/...

  lint-api-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Lint OpenAPI schema
        uses: stoplightio/spectral-action@latest
        with:
          file_glob: 'docs/openapi/*.yaml'
```

### Pre-Commit Hook

**File**: `.githooks/pre-commit` (add to existing)

```bash
#!/bin/bash
# Validate OpenAPI schema before commit

echo "Validating OpenAPI schema..."
python manage.py spectacular --validate

if [ $? -ne 0 ]; then
    echo "❌ OpenAPI schema validation failed"
    echo "Run: python manage.py spectacular --validate"
    exit 1
fi

echo "✅ OpenAPI schema validation passed"
```

---

## Best Practices

### 1. Schema as Single Source of Truth

**Workflow**:
1. Update Django serializers/views
2. Generate OpenAPI schema: `./scripts/generate_openapi_schema.sh`
3. Commit schema to version control
4. CI validates schema hasn't broken backwards compatibility
5. Mobile team uses schema to generate client code

### 2. Versioning Strategy

**Directory Structure**:
```
docs/
  openapi/
    youtility-api-v1.yaml       # Current v1 schema
    youtility-api-v1.json       # JSON format
    youtility-api-v2.yaml       # Future v2 schema (when ready)
    CHANGELOG.md                # Schema changes log
```

**CHANGELOG.md Format**:
```markdown
# OpenAPI Schema Changelog

## v1.1.0 (2025-10-01)

### Added
- New endpoint: `POST /api/v1/onboarding/site-audit/{id}/annotations/`
- New field: `ObservationResponse.ai_confidence`

### Changed
- `approval_id` explicitly documented as INTEGER type

### Deprecated
- `conversation/start/ui/` endpoint (use standard endpoint)

### Breaking Changes
- None
```

### 3. Documentation Generation

**Auto-generate client SDK**:

```bash
# Generate Kotlin client from OpenAPI schema
npx @openapitools/openapi-generator-cli generate \
  -i docs/openapi/youtility-api-v1.yaml \
  -g kotlin \
  -o generated/kotlin-client/ \
  --additional-properties=packageName=com.youtility.api

# Review generated code before using
```

### 4. Contract Testing Best Practices

**Do**:
- ✅ Write consumer tests first (consumer-driven)
- ✅ Test critical user flows
- ✅ Keep contracts focused and minimal
- ✅ Run provider verification on every backend PR
- ✅ Publish verification results

**Don't**:
- ❌ Test every possible edge case (use unit tests for that)
- ❌ Couple tests to implementation details
- ❌ Skip provider verification
- ❌ Modify contracts without coordination

### 5. Breaking Change Detection

**Use OpenAPI Diff**:

```bash
# Install openapi-diff
npm install -g openapi-diff

# Check for breaking changes
openapi-diff \
  docs/openapi/youtility-api-v1-old.yaml \
  docs/openapi/youtility-api-v1-new.yaml \
  --fail-on-incompatible

# Output shows:
# - Breaking changes (incompatible)
# - Non-breaking changes (compatible)
# - Additions (new endpoints/fields)
```

### 6. Monitoring & Alerts

**Track Contract Violations**:

```python
# In production, log contract violations for monitoring
if settings.OPENAPI_MONITORING_ENABLED:
    import sentry_sdk

    @api_view(['POST'])
    def api_endpoint(request):
        # Validate against schema
        validator = RequestValidator(openapi_spec)
        result = validator.validate(request)

        if result.errors:
            # Log to monitoring service
            sentry_sdk.capture_message(
                f'Contract violation: {result.errors}',
                level='warning',
                extra={
                    'endpoint': request.path,
                    'method': request.method,
                    'errors': [str(e) for e in result.errors]
                }
            )
```

---

## 📊 Success Metrics

Track these metrics to measure contract testing effectiveness:

- **Contract Coverage**: % of critical API endpoints covered by Pact tests
- **Breaking Change Detection**: Time to detect breaking changes (target: < 1 hour)
- **Integration Bugs**: Reduction in API-related integration bugs
- **Documentation Accuracy**: % of API docs auto-generated vs manual

**Target KPIs**:
- Contract coverage: > 80% of critical endpoints
- Breaking change detection: 100% automated
- Integration bugs: 50% reduction in first 3 months
- Schema validation pass rate: 100%

---

## 📞 Support & Resources

**Documentation**:
- [OpenAPI Specification](https://spec.openapis.org/oas/v3.1.0)
- [drf-spectacular Docs](https://drf-spectacular.readthedocs.io/)
- [Pact Documentation](https://docs.pact.io/)

**Tools**:
- [Swagger Editor](https://editor.swagger.io/)
- [Postman](https://www.postman.com/) - Import OpenAPI schema
- [Spectral](https://stoplight.io/open-source/spectral) - OpenAPI linter

**Team Contacts**:
- Backend Lead: backend-lead@youtility.in
- Frontend Lead: mobile-team@youtility.in
- DevOps: devops@youtility.in

---

**Document Version**: 1.0
**Last Updated**: 2025-09-28
**Next Review**: Quarterly