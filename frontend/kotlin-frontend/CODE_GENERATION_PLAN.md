# CODE GENERATION PLAN
## Automated DTO Generation from Django OpenAPI Schema

**Version**: 1.0
**Last Updated**: October 30, 2025
**Backend**: Django 5.2.1 + Django REST Framework + drf-spectacular
**Target**: Kotlin Android with Retrofit + kotlinx.serialization

---

## Table of Contents

1. [Overview](#1-overview)
2. [Django: OpenAPI Schema Generation](#2-django-openapi-schema-generation)
3. [Kotlin: Gradle Configuration](#3-kotlin-gradle-configuration)
4. [Generated Code Structure](#4-generated-code-structure)
5. [Code Generation Workflow](#5-code-generation-workflow)
6. [Customization & Type Mappings](#6-customization--type-mappings)
7. [Validation & Testing](#7-validation--testing)
8. [Maintenance Strategy](#8-maintenance-strategy)

---

## 1. Overview

### Goal

**Automatically generate type-safe Kotlin data classes (DTOs) from the Django REST API**, ensuring:
- **Single source of truth**: Backend defines API contract
- **Type safety**: Compile-time verification of all API interactions
- **Synchronization**: Frontend DTOs always match backend serializers
- **Reduced manual work**: No hand-writing DTOs for 100+ endpoints

### Architecture

```
┌─────────────────────────────────────┐
│   Django Backend                    │
│                                     │
│  DRF Serializers ────┐             │
│  ViewSets            │             │
│  URL Routing         │             │
└──────────────────────┼──────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │  drf-spectacular         │
        │  (OpenAPI Generator)     │
        └──────────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │   openapi.yaml           │
        │   (API Specification)    │
        └──────────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │  openapi-generator       │
        │  (Gradle Plugin)         │
        └──────────┬───────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│   Kotlin Android                     │
│                                      │
│  DTOs (data classes)                │
│  Retrofit Services                   │
│  Type-safe API calls                 │
└──────────────────────────────────────┘
```

---

## 2. Django: OpenAPI Schema Generation

### 2.1 Install drf-spectacular

Add to Django requirements:

```bash
pip install drf-spectacular
```

**Version**: `drf-spectacular>=0.27.0`

### 2.2 Configure Django Settings

**File**: `intelliwiz_config/settings/rest_api_core.py`

```python
INSTALLED_APPS = [
    ...
    'drf_spectacular',
    ...
]

REST_FRAMEWORK = {
    ...
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    ...
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Intelliwiz Security Services API',
    'DESCRIPTION': 'Enterprise facility management platform API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,

    # API versioning
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SCHEMA_PATH_PREFIX_TRIM': True,

    # Component naming
    'COMPONENT_SPLIT_REQUEST': True,  # Separate Request/Response schemas
    'COMPONENT_NO_READ_ONLY_REQUIRED': True,

    # Authentication
    'SECURITY': [{'bearerAuth': []}],
    'SECURITY_DEFINITIONS': {
        'bearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
    },

    # Enums
    'ENUM_NAME_OVERRIDES': {
        'SyncStatusEnum': 'apps.core.models.SyncStatus',
        'JobStatusEnum': 'apps.activity.models.JobStatus',
        'PriorityEnum': 'apps.y_helpdesk.models.Priority',
    },

    # Postprocessing hooks
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
    ],
}
```

### 2.3 Add URL Endpoint (Optional - for development)

**File**: `intelliwiz_config/urls_optimized.py`

```python
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    ...
    # OpenAPI schema endpoint (development only)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Swagger UI (development only)
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ...
]
```

**Security**: Disable in production or restrict to admin users only.

### 2.4 Enhance Serializers with Schema Metadata

**Add docstrings and field descriptions**:

```python
from drf_spectacular.utils import extend_schema, extend_schema_field
from rest_framework import serializers

class JournalEntrySerializer(serializers.ModelSerializer):
    """
    Journal entry with wellbeing metrics and reflections.

    Captures mood, stress, energy levels, gratitude items, and contextual information
    for evidence-based wellness interventions.
    """

    mood_rating = serializers.IntegerField(
        min_value=1,
        max_value=10,
        required=False,
        help_text="Mood rating from 1 (very low) to 10 (very high)"
    )

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_location_coordinates(self, obj):
        """GPS coordinates as {lat, lng}"""
        if obj.location_coordinates:
            return obj.location_coordinates
        return None

    class Meta:
        model = JournalEntry
        fields = '__all__'
```

### 2.5 Enhance ViewSets with Operation Metadata

```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

class JournalViewSet(viewsets.ModelViewSet):
    """
    Journal entries for wellbeing tracking.

    Supports CRUD operations with privacy controls and real-time analytics.
    """

    @extend_schema(
        summary="List journal entries",
        description="Retrieve user's journal entries with filtering and pagination",
        parameters=[
            OpenApiParameter(
                name='entry_type',
                type=str,
                description="Filter by entry type",
                enum=['mood_check_in', 'gratitude', 'daily_reflection', ...]
            ),
            OpenApiParameter(
                name='is_draft',
                type=bool,
                description="Filter by draft status"
            ),
        ],
        examples=[
            OpenApiExample(
                'Mood Check-In',
                value={
                    "title": "Morning reflection",
                    "entry_type": "mood_check_in",
                    "mood_rating": 8,
                    "stress_level": 2,
                },
                request_only=True,
            ),
        ]
    )
    def list(self, request):
        return super().list(request)

    @extend_schema(
        summary="Create journal entry",
        description="Create a new journal entry with wellbeing metrics",
    )
    def create(self, request):
        return super().create(request)
```

### 2.6 Generate OpenAPI Schema

**Management Command**:

```bash
python manage.py spectacular --file openapi.yaml --format openapi --validate
```

**Options**:
- `--file openapi.yaml` - Output file
- `--format openapi` - OpenAPI 3.0 format (can also use `openapi-json`)
- `--validate` - Validate schema before writing
- `--api-version v1` - Generate for specific version

**Output**: `openapi.yaml` file in project root

**Example Output Structure**:
```yaml
openapi: 3.0.3
info:
  title: Intelliwiz Security Services API
  version: 1.0.0
servers:
  - url: https://api.example.com
    description: Production
  - url: http://localhost:8000
    description: Development
paths:
  /api/v1/wellness/journal/:
    get:
      summary: List journal entries
      operationId: wellnessJournalList
      parameters:
        - name: entry_type
          in: query
          schema:
            type: string
            enum: [mood_check_in, gratitude, ...]
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PaginatedJournalEntryList'
components:
  schemas:
    JournalEntry:
      type: object
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
          maxLength: 200
        mood_rating:
          type: integer
          minimum: 1
          maximum: 10
```

### 2.7 Automate Schema Generation (CI/CD)

**Add to pre-commit or CI pipeline**:

```bash
#!/bin/bash
# scripts/generate_openapi_schema.sh

python manage.py spectacular --file openapi.yaml --validate

if [ $? -ne 0 ]; then
    echo "OpenAPI schema generation failed!"
    exit 1
fi

echo "OpenAPI schema generated successfully"
```

**Pre-commit hook** (`.pre-commit-config.yaml`):
```yaml
- repo: local
  hooks:
    - id: generate-openapi
      name: Generate OpenAPI Schema
      entry: python manage.py spectacular --file openapi.yaml --validate
      language: system
      pass_filenames: false
```

---

## 3. Kotlin: Gradle Configuration

### 3.1 Project Structure

```
MyAndroidProject/
├── app/                    (Presentation layer)
├── domain/                 (Business logic)
├── data/                   (Repositories)
├── network/                (Retrofit, DTOs)
│   ├── src/
│   │   ├── main/
│   │   │   └── kotlin/
│   │   │       └── com/example/
│   │   │           └── network/
│   │   │               ├── dto/       (Generated DTOs)
│   │   │               ├── api/       (Generated Retrofit services)
│   │   │               └── infrastructure/
│   │   └── openapi/
│   │       └── openapi.yaml  (Copied from Django)
│   └── build.gradle.kts
├── database/               (Room)
└── build.gradle.kts        (Root)
```

### 3.2 Root build.gradle.kts

```kotlin
// Root build.gradle.kts
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.hilt) apply false
}
```

### 3.3 Network Module build.gradle.kts

```kotlin
// network/build.gradle.kts
plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("org.openapi.generator") version "7.1.0"
}

android {
    namespace = "com.example.network"
    compileSdk = 34

    defaultConfig {
        minSdk = 21
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.jakewharton.retrofit:retrofit2-kotlinx-serialization-converter:1.0.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Serialization
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")

    // DateTime
    implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.5.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
}

// OpenAPI Generator Configuration
openApiGenerate {
    generatorName.set("kotlin")
    inputSpec.set("$projectDir/src/openapi/openapi.yaml")
    outputDir.set("$buildDir/generated/openapi")
    apiPackage.set("com.example.network.api")
    modelPackage.set("com.example.network.dto")
    packageName.set("com.example.network")

    // Generator options
    configOptions.set(mapOf(
        "library" to "jvm-retrofit2",
        "serializationLibrary" to "kotlinx_serialization",
        "dateLibrary" to "kotlinx-datetime",
        "enumPropertyNaming" to "UPPERCASE",
        "useCoroutines" to "true",
        "collectionType" to "list"
    ))

    // Additional properties
    additionalProperties.set(mapOf(
        "removeEnumValuePrefix" to "false"
    ))

    // Global properties
    globalProperties.set(mapOf(
        "models" to "",
        "apis" to "",
        "supportingFiles" to ""
    ))

    // Skip files we'll implement manually
    skipOperationExample.set(true)
    generateApiTests.set(false)
    generateModelTests.set(false)
    generateApiDocumentation.set(false)
    generateModelDocumentation.set(false)
}

// Add generated sources to compile
kotlin.sourceSets {
    getByName("main") {
        kotlin.srcDir("$buildDir/generated/openapi/src/main/kotlin")
    }
}

// Generate before compiling
tasks.named("preBuild") {
    dependsOn("openApiGenerate")
}
```

### 3.4 Version Catalog (libs.versions.toml)

```toml
[versions]
retrofit = "2.9.0"
okhttp = "4.12.0"
kotlinx-serialization = "1.6.2"
kotlinx-datetime = "0.5.0"

[libraries]
retrofit-core = { module = "com.squareup.retrofit2:retrofit", version.ref = "retrofit" }
retrofit-kotlinx-serialization = { module = "com.jakewharton.retrofit:retrofit2-kotlinx-serialization-converter", version = "1.0.0" }
okhttp-core = { module = "com.squareup.okhttp3:okhttp", version.ref = "okhttp" }
okhttp-logging = { module = "com.squareup.okhttp3:logging-interceptor", version.ref = "okhttp" }
kotlinx-serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "kotlinx-serialization" }
kotlinx-datetime = { module = "org.jetbrains.kotlinx:kotlinx-datetime", version.ref = "kotlinx-datetime" }
```

---

## 4. Generated Code Structure

### 4.1 DTOs (Data Transfer Objects)

**Generated from OpenAPI components/schemas**:

```kotlin
// Generated: com/example/network/dto/JournalEntryDTO.kt
package com.example.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.datetime.Instant

@Serializable
data class JournalEntryDTO(
    @SerialName("id")
    val id: String,

    @SerialName("title")
    val title: String,

    @SerialName("entry_type")
    val entryType: EntryTypeEnum,

    @SerialName("mood_rating")
    val moodRating: Int? = null,

    @SerialName("stress_level")
    val stressLevel: Int? = null,

    @SerialName("energy_level")
    val energyLevel: Int? = null,

    @SerialName("gratitude_items")
    val gratitudeItems: List<String>? = null,

    @SerialName("privacy_scope")
    val privacyScope: PrivacyScopeEnum,

    @SerialName("created_at")
    val createdAt: Instant,

    @SerialName("updated_at")
    val updatedAt: Instant
)

@Serializable
enum class EntryTypeEnum {
    @SerialName("mood_check_in") MOOD_CHECK_IN,
    @SerialName("gratitude") GRATITUDE,
    @SerialName("daily_reflection") DAILY_REFLECTION,
    // ... more values
}

@Serializable
enum class PrivacyScopeEnum {
    @SerialName("private") PRIVATE,
    @SerialName("manager") MANAGER,
    @SerialName("team") TEAM,
    @SerialName("aggregate") AGGREGATE,
    @SerialName("shared") SHARED
}
```

### 4.2 Retrofit Service Interfaces

**Generated from OpenAPI paths**:

```kotlin
// Generated: com/example/network/api/WellnessApi.kt
package com.example.network.api

import com.example.network.dto.*
import retrofit2.Response
import retrofit2.http.*

interface WellnessApi {

    /**
     * List journal entries
     * Retrieve user&#39;s journal entries with filtering and pagination
     *
     * @param entryType Filter by entry type (optional)
     * @param isDraft Filter by draft status (optional)
     * @param page Page number (optional)
     * @param pageSize Page size (optional, default to 25)
     */
    @GET("api/v1/wellness/journal/")
    suspend fun wellnessJournalList(
        @Query("entry_type") entryType: String? = null,
        @Query("is_draft") isDraft: Boolean? = null,
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null,
        @Header("Authorization") authorization: String
    ): Response<PaginatedJournalEntryDTOList>

    /**
     * Create journal entry
     * Create a new journal entry with wellbeing metrics
     *
     * @param journalEntryDTO Journal entry data
     */
    @POST("api/v1/wellness/journal/")
    suspend fun wellnessJournalCreate(
        @Body journalEntryDTO: JournalEntryCreateDTO,
        @Header("Authorization") authorization: String
    ): Response<JournalEntryDTO>

    /**
     * Get journal entry
     *
     * @param id Entry UUID
     */
    @GET("api/v1/wellness/journal/{id}/")
    suspend fun wellnessJournalRetrieve(
        @Path("id") id: String,
        @Header("Authorization") authorization: String
    ): Response<JournalEntryDTO>

    /**
     * Update journal entry
     *
     * @param id Entry UUID
     * @param journalEntryDTO Updated data
     */
    @PATCH("api/v1/wellness/journal/{id}/")
    suspend fun wellnessJournalPartialUpdate(
        @Path("id") id: String,
        @Body journalEntryDTO: JournalEntryUpdateDTO,
        @Header("Authorization") authorization: String
    ): Response<JournalEntryDTO>

    /**
     * Delete journal entry
     *
     * @param id Entry UUID
     */
    @DELETE("api/v1/wellness/journal/{id}/")
    suspend fun wellnessJournalDestroy(
        @Path("id") id: String,
        @Header("Authorization") authorization: String
    ): Response<Unit>
}
```

### 4.3 Infrastructure (Optionally Generated)

```kotlin
// Generated: com/example/network/infrastructure/Serializer.kt
package com.example.network.infrastructure

import kotlinx.serialization.json.Json

object Serializer {
    val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = false
        prettyPrint = false
        coerceInputValues = true
    }
}
```

---

## 5. Code Generation Workflow

### 5.1 Development Workflow

**Step 1: Update Django API**
```bash
# Make changes to Django models, serializers, or viewsets
# Example: Add new field to JournalEntry model
```

**Step 2: Generate OpenAPI Schema**
```bash
cd /path/to/django/project
python manage.py spectacular --file openapi.yaml --validate
```

**Step 3: Copy Schema to Android Project**
```bash
cp openapi.yaml /path/to/android/project/network/src/openapi/
```

**Step 4: Generate Kotlin DTOs**
```bash
cd /path/to/android/project
./gradlew :network:openApiGenerate
```

**Step 5: Review Generated Code**
```bash
# Check generated files
ls network/build/generated/openapi/src/main/kotlin/com/example/network/

# Review changes
git diff network/src/
```

**Step 6: Update Mappers (if schema changed)**
```kotlin
// Update mapper to handle new fields
class JournalMapper {
    fun toEntity(dto: JournalEntryDTO): JournalEntity {
        return JournalEntity(
            id = dto.id,
            title = dto.title,
            moodRating = dto.moodRating, // New field
            // ... rest of mapping
        )
    }
}
```

**Step 7: Compile & Test**
```bash
./gradlew :app:assemble
./gradlew :app:testDebugUnitTest
```

### 5.2 CI/CD Integration

**GitHub Actions Example** (`.github/workflows/android-build.yml`):

```yaml
name: Android CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up JDK 17
        uses: actions/setup-java@v3
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Fetch latest OpenAPI schema
        run: |
          # Option A: Download from Django API
          curl https://api.example.com/schema/ -o network/src/openapi/openapi.yaml

          # Option B: Copy from Django repo (if monorepo)
          cp ../django-backend/openapi.yaml network/src/openapi/

      - name: Generate Kotlin DTOs
        run: ./gradlew :network:openApiGenerate

      - name: Build with Gradle
        run: ./gradlew build

      - name: Run tests
        run: ./gradlew test
```

---

## 6. Customization & Type Mappings

### 6.1 Custom Type Mappings

**Problem**: OpenAPI uses `string` for dates, but we want Kotlin `Instant`.

**Solution**: Configure type mappings in `openApiGenerate`:

```kotlin
openApiGenerate {
    // ... other config ...

    typeMappings.set(mapOf(
        "DateTime" to "kotlinx.datetime.Instant",
        "Date" to "kotlinx.datetime.LocalDate",
        "UUID" to "kotlin.String"  // Or java.util.UUID if preferred
    ))

    importMappings.set(mapOf(
        "Instant" to "kotlinx.datetime.Instant",
        "LocalDate" to "kotlinx.datetime.LocalDate"
    ))
}
```

### 6.2 Custom Templates (Advanced)

**Use Case**: Need more control over generated code structure.

**Steps**:

1. **Extract default templates**:
```bash
java -jar openapi-generator-cli.jar author template -g kotlin --output templates/
```

2. **Customize templates**:
```kotlin
// templates/model.mustache
package {{packageName}}

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * {{description}}
 * @property {{name}} {{description}}
 */
@Serializable
data class {{classname}}(
    {{#vars}}
    @SerialName("{{baseName}}")
    val {{name}}: {{dataType}}{{^required}}? = null{{/required}}{{^-last}},{{/-last}}
    {{/vars}}
)
```

3. **Configure Gradle to use custom templates**:
```kotlin
openApiGenerate {
    templateDir.set("$projectDir/templates")
}
```

### 6.3 Handling Polymorphism

**OpenAPI Schema** (Django `oneOf`):
```yaml
components:
  schemas:
    Notification:
      oneOf:
        - $ref: '#/components/schemas/TicketNotification'
        - $ref: '#/components/schemas/JournalNotification'
      discriminator:
        propertyName: notification_type
```

**Generated Kotlin** (sealed class):
```kotlin
@Serializable
sealed class NotificationDTO {
    abstract val notificationType: String

    @Serializable
    @SerialName("ticket")
    data class TicketNotification(
        override val notificationType: String = "ticket",
        val ticketId: Int,
        val message: String
    ) : NotificationDTO()

    @Serializable
    @SerialName("journal")
    data class JournalNotification(
        override val notificationType: String = "journal",
        val entryId: String,
        val intervention: String
    ) : NotificationDTO()
}
```

---

## 7. Validation & Testing

### 7.1 Validate OpenAPI Schema

**Use OpenAPI validator**:

```bash
npm install -g @stoplight/spectral-cli

spectral lint openapi.yaml
```

**Custom rules** (`.spectral.yaml`):
```yaml
extends: [[spectral:oas, all]]

rules:
  oas3-api-servers: error
  operation-description: warn
  operation-operationId: error
```

### 7.2 Test Generated DTOs

**Serialization tests**:

```kotlin
class JournalEntryDTOTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `deserialize journal entry from JSON`() {
        val jsonString = """
            {
              "id": "uuid-abc-123",
              "title": "Morning reflection",
              "entry_type": "mood_check_in",
              "mood_rating": 8,
              "privacy_scope": "private",
              "created_at": "2025-10-30T09:00:00Z",
              "updated_at": "2025-10-30T09:00:00Z"
            }
        """.trimIndent()

        val dto = json.decodeFromString<JournalEntryDTO>(jsonString)

        assertEquals("uuid-abc-123", dto.id)
        assertEquals("Morning reflection", dto.title)
        assertEquals(EntryTypeEnum.MOOD_CHECK_IN, dto.entryType)
        assertEquals(8, dto.moodRating)
    }

    @Test
    fun `serialize journal entry to JSON`() {
        val dto = JournalEntryDTO(
            id = "uuid-abc-123",
            title = "Morning reflection",
            entryType = EntryTypeEnum.MOOD_CHECK_IN,
            moodRating = 8,
            privacyScope = PrivacyScopeEnum.PRIVATE,
            createdAt = Instant.parse("2025-10-30T09:00:00Z"),
            updatedAt = Instant.parse("2025-10-30T09:00:00Z")
        )

        val jsonString = json.encodeToString(JournalEntryDTO.serializer(), dto)

        assertTrue(jsonString.contains("\"mood_rating\":8"))
        assertTrue(jsonString.contains("\"entry_type\":\"mood_check_in\""))
    }
}
```

### 7.3 Test Retrofit Services

**Mock server tests**:

```kotlin
class WellnessApiTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var wellnessApi: WellnessApi

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        val retrofit = Retrofit.Builder()
            .baseUrl(mockWebServer.url("/"))
            .addConverterFactory(Json.asConverterFactory("application/json".toMediaType()))
            .build()

        wellnessApi = retrofit.create(WellnessApi::class.java)
    }

    @Test
    fun `fetch journal entries returns paginated list`() = runTest {
        val responseJson = """
            {
              "count": 50,
              "next": null,
              "previous": null,
              "results": [
                {
                  "id": "uuid-abc-123",
                  "title": "Morning reflection",
                  "entry_type": "mood_check_in",
                  "mood_rating": 8,
                  "privacy_scope": "private",
                  "created_at": "2025-10-30T09:00:00Z",
                  "updated_at": "2025-10-30T09:00:00Z"
                }
              ]
            }
        """.trimIndent()

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(responseJson)
        )

        val response = wellnessApi.wellnessJournalList(
            authorization = "Bearer test-token"
        )

        assertTrue(response.isSuccessful)
        assertEquals(50, response.body()?.count)
        assertEquals(1, response.body()?.results?.size)
    }
}
```

---

## 8. Maintenance Strategy

### 8.1 Version Control

**Commit generated code?**

**Option A: Commit Generated Code** (Recommended)
- ✅ Easier code review (see what changed)
- ✅ No build-time dependency on Django
- ✅ Faster CI builds
- ❌ Larger repo size

**Option B: Generate at Build Time**
- ✅ Smaller repo
- ❌ Requires Django running or schema file synced
- ❌ Slower builds
- ❌ Hard to review API changes

**Recommendation**: Commit generated code, but use `.gitattributes` to exclude from diffs:

```gitattributes
# .gitattributes
network/build/generated/** linguist-generated=true
```

### 8.2 Schema Versioning

**Track OpenAPI schema versions**:

```
network/src/openapi/
├── openapi-v1.yaml         (Stable)
├── openapi-v2.yaml         (Preview)
└── openapi-current.yaml    (Symlink to v1)
```

**Generate from specific version**:
```kotlin
openApiGenerate {
    inputSpec.set("$projectDir/src/openapi/openapi-v1.yaml")
}
```

### 8.3 Breaking Change Detection

**Use openapi-diff**:

```bash
npm install -g @openapitools/openapi-diff

openapi-diff openapi-old.yaml openapi-new.yaml --fail-on-incompatible
```

**CI Integration**:
```yaml
- name: Check for breaking changes
  run: |
    openapi-diff network/src/openapi/openapi-old.yaml network/src/openapi/openapi-new.yaml --fail-on-incompatible
```

### 8.4 Regular Sync Schedule

**Weekly sync** (or on every backend release):
1. Django team generates new `openapi.yaml`
2. Copy to Android repo
3. Regenerate Kotlin DTOs
4. Run tests
5. Fix any breaking changes
6. Create PR for review

---

## Summary

This plan automates DTO generation from Django OpenAPI schemas, ensuring:

✅ **Type Safety**: Compile-time verification of all API calls
✅ **Synchronization**: Frontend always matches backend
✅ **Reduced Manual Work**: No hand-writing 100+ DTOs
✅ **Validation**: Automated schema validation
✅ **Testability**: Generated code is testable

**Tools**:
- **Backend**: drf-spectacular (OpenAPI generation)
- **Frontend**: openapi-generator-gradle-plugin (Kotlin generation)
- **Serialization**: kotlinx.serialization
- **Validation**: Spectral (OpenAPI linter)

**Next Steps**:
1. Install drf-spectacular in Django
2. Generate initial OpenAPI schema
3. Configure Gradle plugin in Android
4. Generate initial DTOs
5. Create integration tests
6. Setup CI/CD automation

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Maintainer**: Backend & Mobile Teams
