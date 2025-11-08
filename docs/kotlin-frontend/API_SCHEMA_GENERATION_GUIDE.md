# API Schema Generation & Distribution Guide

> **Purpose:** How to generate, publish, and consume OpenAPI schemas for type-safe Kotlin development
> **Version:** 1.0.0
> **Last Updated:** November 7, 2025

---

## 📋 Table of Contents

- [Overview](#overview)
- [Backend: Generate OpenAPI Schema](#backend-generate-openapi-schema)
- [Backend: Publish Schema (CI/CD)](#backend-publish-schema-cicd)
- [Mobile: Download & Generate DTOs](#mobile-download--generate-dtos)
- [Mobile: CI/CD Integration](#mobile-cicd-integration)
- [Schema Validation](#schema-validation)
- [Versioning Strategy](#versioning-strategy)
- [Troubleshooting](#troubleshooting)

---

## Overview

### The Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Django    │────▶│   OpenAPI    │────▶│   Kotlin    │
│   Models    │     │    Schema    │     │    DTOs     │
│ Serializers │     │ (YAML/JSON)  │     │  (Auto-gen) │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                     │
       │                    │                     │
   Manual dev        Auto-generated        Auto-generated
```

**Key Benefits:**
- **Type Safety:** Compile-time errors if API changes
- **No Manual Work:** 100+ DTOs generated automatically
- **Always in Sync:** Schema reflects actual API
- **Breaking Change Detection:** CI/CD catches incompatibilities

**Tools Used:**
- **Django:** drf-spectacular (OpenAPI 3.0 generator)
- **Kotlin:** openapi-generator-gradle-plugin
- **Validation:** Spectral (OpenAPI linter)
- **CI/CD:** GitHub Actions

---

## Backend: Generate OpenAPI Schema

### Prerequisites

**1. Install drf-spectacular** (already done):
```python
# intelliwiz_config/settings/base.py
INSTALLED_APPS = [
    ...
    'drf_spectacular',
]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Intelliwiz API',
    'DESCRIPTION': 'Enterprise Facility Management Platform API',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': True,
    'SCHEMA_PATH_PREFIX': '/api/v[0-9]',
    'COMPONENT_SPLIT_REQUEST': True,
}
```

**2. Expose schema endpoints** (already done):
```python
# intelliwiz_config/urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

---

### Generate Schema (Manual)

**Command:**
```bash
# Generate OpenAPI schema as YAML
python manage.py spectacular --file openapi.yaml --format openapi

# Or as JSON
python manage.py spectacular --file openapi.json --format openapi-json

# Validate schema (exits with error if invalid)
python manage.py spectacular --file openapi.yaml --validate
```

**Output Location:**
```
/Users/amar/Desktop/MyCode/DJANGO5-master/openapi.yaml
```

**Schema Contents:**
```yaml
openapi: 3.0.3
info:
  title: Intelliwiz API
  version: 2.0.0
  description: Enterprise Facility Management Platform API

servers:
  - url: https://api.intelliwiz.com/api/v2
    description: Production server
  - url: http://localhost:8000/api/v2
    description: Development server

paths:
  /operations/jobs/:
    post:
      operationId: operations_jobs_create
      summary: Create Job
      tags:
        - operations
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JobCreate'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobDetail'
        '400':
          description: Validation Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValidationError'

components:
  schemas:
    JobCreate:
      type: object
      required:
        - title
        - job_type
        - priority
        - scheduled_start
      properties:
        title:
          type: string
          minLength: 3
          maxLength: 200
        job_type:
          type: string
          enum: [corrective, preventive_maintenance, inspection, installation, emergency]
        priority:
          type: string
          enum: [low, medium, high, urgent]
        scheduled_start:
          type: string
          format: date-time
        # ... (100+ more fields)
```

---

### Enhancing Schema with Annotations

**Add detailed descriptions and examples to serializers:**

```python
# apps/activity/serializers.py

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer, OpenApiExample

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Create HVAC Job',
            summary='Create preventive maintenance job',
            description='Example of creating a scheduled HVAC inspection',
            value={
                'title': 'Monthly HVAC Inspection',
                'job_type': 'preventive_maintenance',
                'priority': 'medium',
                'scheduled_start': '2025-11-15T09:00:00Z',
                'assigned_to': [123],
                'location': {'site_id': 789}
            }
        )
    ]
)
class JobCreateSerializer(serializers.ModelSerializer):
    title = serializers.CharField(
        max_length=200,
        help_text="Job title (3-200 characters)"
    )
    job_type = serializers.ChoiceField(
        choices=JOB_TYPE_CHOICES,
        help_text="Type of job: corrective, preventive_maintenance, inspection, installation, emergency"
    )

    class Meta:
        model = Job
        fields = ['title', 'job_type', 'priority', ...]
```

**Result:** Schema includes examples and help text for Kotlin developers.

---

## Backend: Publish Schema (CI/CD)

### GitHub Actions Workflow

**Create:** `.github/workflows/publish-openapi-schema.yml`

```yaml
name: Publish OpenAPI Schema

on:
  push:
    branches: [main, develop]
    paths:
      - 'apps/**/serializers.py'
      - 'apps/**/api/**/*.py'
      - 'apps/**/models/**/*.py'
  workflow_dispatch:

jobs:
  generate-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements/base-linux.txt
          pip install drf-spectacular

      - name: Generate OpenAPI schema
        run: |
          python manage.py spectacular --file openapi.yaml --format openapi
          python manage.py spectacular --file openapi.json --format openapi-json

      - name: Validate schema with Spectral
        uses: stoplightio/spectral-action@latest
        with:
          file_glob: 'openapi.yaml'
          spectral_ruleset: '.spectral.yaml'

      - name: Detect breaking changes
        run: |
          # Download previous schema
          wget https://api.intelliwiz.com/api/schema/ -O openapi_previous.yaml

          # Compare schemas
          npx openapi-diff openapi_previous.yaml openapi.yaml --json > schema-diff.json

          # Check for breaking changes
          python scripts/check_breaking_changes.py schema-diff.json

      - name: Publish to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./
          destination_dir: api-schemas/${{ github.ref_name }}
          keep_files: true

      - name: Upload to cloud storage
        run: |
          # Upload to S3/GCS for mobile team
          aws s3 cp openapi.yaml s3://intelliwiz-schemas/openapi-latest.yaml
          aws s3 cp openapi.json s3://intelliwiz-schemas/openapi-latest.json

          # Version-specific copy
          aws s3 cp openapi.yaml s3://intelliwiz-schemas/openapi-v2.0.0.yaml

      - name: Notify mobile team
        run: |
          curl -X POST https://slack.com/api/chat.postMessage \
            -H "Authorization: Bearer ${{ secrets.SLACK_TOKEN }}" \
            -d channel=mobile-dev \
            -d text="📱 New OpenAPI schema published: https://intelliwiz-schemas.s3.amazonaws.com/openapi-latest.yaml"
```

---

## Mobile: Download & Generate DTOs

### Prerequisites

**1. Add Gradle plugin** (already in CODE_GENERATION_PLAN.md):

```kotlin
// build.gradle.kts (project level)
plugins {
    id("org.openapi.generator") version "7.0.1" apply false
}

// build.gradle.kts (network module)
plugins {
    id("org.openapi.generator")
}

openApiGenerate {
    generatorName.set("kotlin")
    inputSpec.set("$rootDir/openapi.yaml") // Downloaded schema
    outputDir.set("$buildDir/generated/openapi")
    apiPackage.set("com.intelliwiz.network.api")
    modelPackage.set("com.intelliwiz.network.dto")
    configOptions.set(mapOf(
        "dateLibrary" to "kotlinx-datetime",
        "serializationLibrary" to "kotlinx_serialization",
        "enumPropertyNaming" to "UPPERCASE"
    ))
}
```

---

### Download Schema (Manual)

**Option 1: From Django server (development):**
```bash
# Download from local server
curl http://localhost:8000/api/schema/ > openapi.yaml

# Or from production
curl https://api.intelliwiz.com/api/schema/ > openapi.yaml
```

**Option 2: From cloud storage (recommended):**
```bash
# Download latest from S3
wget https://intelliwiz-schemas.s3.amazonaws.com/openapi-latest.yaml -O openapi.yaml

# Or specific version
wget https://intelliwiz-schemas.s3.amazonaws.com/openapi-v2.0.0.yaml -O openapi.yaml
```

**Option 3: From GitHub Pages:**
```bash
wget https://intelliwiz.github.io/api-schemas/main/openapi.yaml
```

**Place in project:**
```
android-app/
├── openapi.yaml  ← Downloaded schema (in .gitignore)
├── build.gradle.kts
└── network/
    └── build.gradle.kts  ← Has openApiGenerate config
```

---

### Generate DTOs (Manual)

**Command:**
```bash
# From project root
./gradlew :network:openApiGenerate

# Output:
# ✓ Generating Kotlin DTOs...
# ✓ Generated 120 data classes
# ✓ Generated 15 Retrofit services
# ✓ Generated 25 enums
# ✓ Output: build/generated/openapi/
```

**Generated Files:**
```
build/generated/openapi/
├── src/main/kotlin/com/intelliwiz/network/
    ├── api/
    │   ├── OperationsApi.kt  ← Retrofit interface for /operations/*
    │   ├── AttendanceApi.kt  ← Retrofit interface for /attendance/*
    │   ├── PeopleApi.kt      ← Retrofit interface for /people/*
    │   └── HelpdeskApi.kt    ← Retrofit interface for /helpdesk/*
    └── dto/
        ├── JobCreateDto.kt
        ├── JobDetailDto.kt
        ├── AttendanceCheckinDto.kt
        ├── UserProfileDto.kt
        ├── TicketCreateDto.kt
        └── ... (115 more DTOs)
```

**Example Generated DTO:**
```kotlin
// Generated: JobCreateDto.kt
@Serializable
data class JobCreateDto(
    @SerialName("title")
    val title: String,

    @SerialName("job_type")
    val jobType: JobType,

    @SerialName("priority")
    val priority: Priority,

    @SerialName("scheduled_start")
    val scheduledStart: Instant,

    @SerialName("scheduled_end")
    val scheduledEnd: Instant? = null,

    @SerialName("assigned_to")
    val assignedTo: List<Long>,

    @SerialName("location")
    val location: LocationDto,

    @SerialName("assets")
    val assets: List<AssetRefDto>? = null
)

@Serializable
enum class JobType {
    @SerialName("corrective")
    CORRECTIVE,

    @SerialName("preventive_maintenance")
    PREVENTIVE_MAINTENANCE,

    @SerialName("inspection")
    INSPECTION,

    @SerialName("installation")
    INSTALLATION,

    @SerialName("emergency")
    EMERGENCY
}
```

**Example Generated Retrofit Service:**
```kotlin
// Generated: OperationsApi.kt
interface OperationsApi {
    @POST("operations/jobs/")
    suspend fun createJob(
        @Body request: JobCreateDto
    ): JobDetailDto

    @GET("operations/jobs/")
    suspend fun listJobs(
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null,
        @Query("status") status: String? = null,
        @Query("priority") priority: String? = null
    ): PaginatedJobList

    @GET("operations/jobs/{id}/")
    suspend fun getJob(
        @Path("id") id: Long
    ): JobDetailDto

    @PATCH("operations/jobs/{id}/")
    suspend fun updateJob(
        @Path("id") id: Long,
        @Body request: JobUpdateDto
    ): JobDetailDto
}
```

---

## Backend: Publish Schema (CI/CD)

### Automatic Schema Publication

**When to publish:**
- On every merge to `main` or `develop`
- When API-related files change (serializers, models, viewsets)
- Manual trigger via workflow_dispatch

**Where to publish:**
- GitHub Pages: `https://intelliwiz.github.io/api-schemas/{branch}/openapi.yaml`
- Cloud Storage: `https://intelliwiz-schemas.s3.amazonaws.com/openapi-latest.yaml`
- Versioned: `https://intelliwiz-schemas.s3.amazonaws.com/openapi-v{major}.{minor}.{patch}.yaml`

**CI/CD workflow:** (see `.github/workflows/publish-openapi-schema.yml` in previous section)

---

### Breaking Change Detection

**Script:** `scripts/check_breaking_changes.py`

```python
#!/usr/bin/env python3
"""
Detect breaking changes in OpenAPI schema
"""
import json
import sys

def check_breaking_changes(diff_json_path):
    with open(diff_json_path) as f:
        diff = json.load(f)

    breaking_changes = []

    # Check for removed endpoints
    if 'paths' in diff.get('removed', {}):
        breaking_changes.append(f"REMOVED ENDPOINTS: {diff['removed']['paths']}")

    # Check for removed required fields
    if 'schemas' in diff.get('changed', {}):
        for schema, changes in diff['changed']['schemas'].items():
            if 'required' in changes.get('removed', {}):
                breaking_changes.append(f"REMOVED REQUIRED FIELD: {schema}.{changes['removed']['required']}")

    # Check for changed types
    if 'schemas' in diff.get('changed', {}):
        for schema, changes in diff['changed']['schemas'].items():
            if 'properties' in changes.get('changed', {}):
                for prop, prop_changes in changes['changed']['properties'].items():
                    if 'type' in prop_changes.get('changed', {}):
                        breaking_changes.append(f"TYPE CHANGED: {schema}.{prop}")

    if breaking_changes:
        print("❌ BREAKING CHANGES DETECTED:")
        for change in breaking_changes:
            print(f"  - {change}")
        print("\n⚠️ Increment MAJOR version and notify mobile team!")
        sys.exit(1)
    else:
        print("✅ No breaking changes detected")
        sys.exit(0)

if __name__ == '__main__':
    check_breaking_changes('schema-diff.json')
```

**Usage in CI:**
```bash
# Compare schemas
npx openapi-diff openapi_previous.yaml openapi.yaml --json > schema-diff.json

# Check for breaking changes (exits 1 if found)
python scripts/check_breaking_changes.py schema-diff.json
```

**If breaking change detected:**
1. CI fails
2. Slack notification sent to mobile team
3. PR requires explicit "BREAKING CHANGE" label to merge
4. Major version increment required

---

## Mobile: Download & Generate DTOs

### Download Schema (Mobile Team)

**Option 1: Automated download in Gradle:**

```kotlin
// build.gradle.kts (network module)
tasks.register("downloadOpenApiSchema") {
    doLast {
        val schemaUrl = "https://intelliwiz-schemas.s3.amazonaws.com/openapi-latest.yaml"
        val outputFile = file("$rootDir/openapi.yaml")

        java.net.URL(schemaUrl).openStream().use { input ->
            outputFile.outputStream().use { output ->
                input.copyTo(output)
            }
        }

        println("✓ Downloaded OpenAPI schema to $outputFile")
    }
}

// Run before code generation
tasks.named("openApiGenerate") {
    dependsOn("downloadOpenApiSchema")
}
```

**Option 2: Manual download (for verification):**
```bash
cd android-app/
wget https://intelliwiz-schemas.s3.amazonaws.com/openapi-latest.yaml -O openapi.yaml
```

---

### Generate DTOs (Mobile Team)

**Command:**
```bash
# Generate Kotlin DTOs from schema
./gradlew :network:openApiGenerate

# Clean previous generation and regenerate
./gradlew :network:clean :network:openApiGenerate
```

**Build Configuration:**

```kotlin
// build.gradle.kts (network module)
sourceSets {
    main {
        kotlin {
            srcDirs("build/generated/openapi/src/main/kotlin")
        }
    }
}

// Run generation before compilation
tasks.named("compileKotlin") {
    dependsOn("openApiGenerate")
}
```

**Commit Generated Code?**

**Option A: Commit generated DTOs** (recommended for stability)
- Pros: Build works offline, no dependency on schema server
- Cons: Large diffs when schema changes
- Use when: Production app, want deterministic builds

**Option B: Generate on build** (recommended for development)
- Pros: Always fresh, smaller git diffs
- Cons: Build requires network, slower builds
- Use when: Active development, frequent schema changes

**Recommendation:** **Commit generated code** but regenerate frequently (daily or on schema update).

---

## Mobile: CI/CD Integration

### Mobile CI/CD Workflow

**.github/workflows/android-build.yml:**

```yaml
name: Android Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up JDK 17
        uses: actions/setup-java@v3
        with:
          java-version: '17'

      - name: Download OpenAPI schema
        run: |
          wget https://intelliwiz-schemas.s3.amazonaws.com/openapi-latest.yaml -O openapi.yaml

      - name: Generate DTOs
        run: |
          ./gradlew :network:openApiGenerate

      - name: Validate generated code compiles
        run: |
          ./gradlew :network:build

      - name: Run DTO serialization tests
        run: |
          ./gradlew :network:test

      - name: Build app
        run: |
          ./gradlew assembleDebug
```

---

## Schema Validation

### Spectral Configuration

**Create:** `.spectral.yaml`

```yaml
extends: spectral:oas

rules:
  # Require operation IDs for all endpoints
  operation-operationId: error

  # Require descriptions for all schemas
  info-description: error
  oas3-schema-description: warn

  # Require examples for request bodies
  operation-request-body-example: warn

  # Require 200/400/401/403/500 responses
  operation-success-response: error

  # Ensure consistent error response format
  custom-error-response:
    message: "Error responses must use standard ValidationError schema"
    given: "$.paths[*][*].responses[4*, 5*].content.application/json.schema"
    then:
      field: "$ref"
      function: pattern
      functionOptions:
        match: "#/components/schemas/(ValidationError|ErrorResponse)"

  # Enforce semantic versioning
  oas3-api-servers: error

  # Require security schemes
  oas3-operation-security-defined: error
```

**Run validation:**
```bash
# Install Spectral
npm install -g @stoplight/spectral-cli

# Validate schema
spectral lint openapi.yaml

# Output:
# ✓ 0 errors
# ⚠ 3 warnings
#   - operation-request-body-example: POST /operations/jobs/ missing example
```

---

## Versioning Strategy

### Semantic Versioning for API

**Version Format:** `MAJOR.MINOR.PATCH`

**MAJOR** - Increment when:
- Removing endpoints
- Removing required fields
- Changing field types
- Changing authentication scheme

**MINOR** - Increment when:
- Adding new endpoints
- Adding optional fields
- Adding new enum values

**PATCH** - Increment when:
- Documentation updates
- Bug fixes in descriptions
- Example improvements

**Example:**
- **v1.0.0** - Initial release
- **v1.1.0** - Added tours endpoints (backward compatible)
- **v1.1.1** - Fixed typo in descriptions
- **v2.0.0** - Changed `datetime` format from epoch to ISO 8601 (breaking)

### Schema Versioning in Git

**Tag schema releases:**
```bash
# After schema generation
git add openapi.yaml
git commit -m "chore(api): Update OpenAPI schema to v2.1.0"
git tag api-v2.1.0
git push origin api-v2.1.0
```

**Mobile team pins to specific version:**
```kotlin
// build.gradle.kts
openApiGenerate {
    inputSpec.set("https://intelliwiz-schemas.s3.amazonaws.com/openapi-v2.1.0.yaml")
}
```

---

## Workflow Summary

### Complete Flow (Weekly Schema Update)

```
1. Backend Dev: Update API
   - Add new endpoint or field
   - Update serializer with @extend_schema annotations
   - Commit changes

2. CI/CD (automatic)
   - Generate new schema
   - Validate with Spectral
   - Detect breaking changes
   - If breaking: FAIL build, notify team
   - If compatible: Publish to S3 + GitHub Pages
   - Tag: api-v2.1.0

3. Mobile Dev (notified via Slack)
   - Download new schema: wget https://...
   - Regenerate DTOs: ./gradlew :network:openApiGenerate
   - Review diff: git diff network/src/generated/
   - Update mappers if new fields added
   - Run tests: ./gradlew :network:test
   - Commit: git add + commit + push

4. Verification
   - CI builds app with new DTOs
   - Integration tests pass
   - App ready for feature implementation
```

---

## Troubleshooting

### Schema Generation Fails

**Error:** `ImportError: cannot import spectacular`
**Solution:**
```bash
pip install drf-spectacular
```

**Error:** `No schema for viewset XYZ`
**Solution:**
Add to `SPECTACULAR_SETTINGS`:
```python
'COMPONENT_SPLIT_REQUEST': True,
'COMPONENT_NO_READ_ONLY_REQUIRED': True,
```

---

### DTO Generation Fails

**Error:** `Unknown type: date-time`
**Solution:** Add type mapping:
```kotlin
configOptions.set(mapOf(
    "dateLibrary" to "kotlinx-datetime"
))
```

**Error:** `Duplicate class JobDto`
**Solution:** Clean and regenerate:
```bash
./gradlew :network:clean :network:openApiGenerate
```

---

### Generated Code Doesn't Compile

**Error:** `Unresolved reference: Instant`
**Solution:** Add kotlinx-datetime dependency:
```kotlin
dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.5.0")
}
```

**Error:** `Serializer not found for Instant`
**Solution:** Already handled by `kotlinx-serialization` - verify plugin applied:
```kotlin
plugins {
    kotlin("plugin.serialization") version "1.9.0"
}
```

---

## Best Practices

### Backend Best Practices

1. **Annotate everything:**
   ```python
   @extend_schema(
       summary="Create job",
       description="Create new job with location and assets",
       examples=[...]
   )
   def create(self, request):
       ...
   ```

2. **Use explicit serializers** (don't rely on auto-generation):
   - `JobCreateSerializer` (for POST)
   - `JobDetailSerializer` (for GET detail)
   - `JobListSerializer` (for GET list)
   - `JobUpdateSerializer` (for PATCH)

3. **Validate schema before commit:**
   ```bash
   python manage.py spectacular --file openapi.yaml --validate
   spectral lint openapi.yaml
   ```

4. **Version API endpoints:**
   - Use `/api/v2/` not `/api/`
   - Never break v2 contracts
   - Create v3 for breaking changes

### Mobile Best Practices

1. **Regenerate frequently:**
   ```bash
   # Daily or on schema update
   ./gradlew :network:clean :network:openApiGenerate
   ```

2. **Test generated code:**
   ```kotlin
   @Test
   fun `DTO serialization works`() {
       val dto = JobCreateDto(...)
       val json = Json.encodeToString(dto)
       val decoded = Json.decodeFromString<JobCreateDto>(json)
       assertEquals(dto, decoded)
   }
   ```

3. **Don't edit generated code** - wrap instead:
   ```kotlin
   // ✅ CORRECT: Wrap generated DTO
   data class Job(
       val id: Long,
       val title: String
   ) {
       fun toDto(): JobDetailDto = ...
       companion object {
           fun fromDto(dto: JobDetailDto): Job = ...
       }
   }

   // ❌ WRONG: Edit generated file
   // build/generated/.../JobDetailDto.kt
   // Don't touch this!
   ```

4. **Commit generated code** (if using Option A):
   ```bash
   git add network/src/generated/
   git commit -m "chore: Regenerate DTOs from schema v2.1.0"
   ```

---

## Schema Diff Workflow

### Comparing Schema Versions

**Install openapi-diff:**
```bash
npm install -g openapi-diff
```

**Compare schemas:**
```bash
# Download old and new
wget https://.../openapi-v2.0.0.yaml -O old.yaml
wget https://.../openapi-v2.1.0.yaml -O new.yaml

# Compare
openapi-diff old.yaml new.yaml

# Output:
# ✅ 5 new endpoints added
# ✅ 12 new optional fields added
# ❌ 0 breaking changes
```

**Review before mobile team regenerates:**
- Check for new endpoints → implement features
- Check for new fields → update mappers
- Check for deprecations → plan migration

---

## Quick Reference Commands

### Backend (Django)

```bash
# Generate schema
python manage.py spectacular --file openapi.yaml

# Validate schema
python manage.py spectacular --file openapi.yaml --validate
spectral lint openapi.yaml

# Test schema endpoint
curl http://localhost:8000/api/schema/ > schema.yaml

# View interactive docs
open http://localhost:8000/api/schema/swagger/
```

### Mobile (Kotlin)

```bash
# Download latest schema
wget https://intelliwiz-schemas.s3.amazonaws.com/openapi-latest.yaml -O openapi.yaml

# Generate DTOs
./gradlew :network:openApiGenerate

# Verify compilation
./gradlew :network:build

# Run DTO tests
./gradlew :network:test

# Clean and regenerate
./gradlew :network:clean :network:openApiGenerate
```

---

## FAQ

**Q: Do I commit openapi.yaml to mobile repo?**
A: Optional. If you download before builds, yes (for offline builds). If you generate on CI, no.

**Q: How often should I regenerate DTOs?**
A: Weekly during active development, or when notified of schema changes.

**Q: What if schema changes but I'm mid-feature?**
A: Pin to specific version: `openapi-v2.0.0.yaml` until feature done, then update.

**Q: Can I customize generated DTOs?**
A: No. Use mapper pattern to wrap DTOs in domain entities.

**Q: How do I handle deprecated endpoints?**
A: Schema marks them `deprecated: true`. Linter warns. Plan migration before removal.

---

**Document Version:** 1.0.0
**Last Updated:** November 7, 2025
**Next Review:** December 7, 2025
