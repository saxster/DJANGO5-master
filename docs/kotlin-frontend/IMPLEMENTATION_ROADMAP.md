# KOTLIN ANDROID APP - IMPLEMENTATION ROADMAP
## Detailed Phase-by-Phase Build Instructions

**Version**: 1.0
**Last Updated**: October 30, 2025
**Target**: Kotlin Android Application with Offline-First Architecture
**Estimated Timeline**: 12-14 weeks with 2-3 Android developers

---

## Table of Contents

1. [Overview](#1-overview)
2. [Phase 0: Prerequisites](#phase-0-prerequisites-week-0)
3. [Phase 1: Project Setup](#phase-1-project-setup-week-1)
4. [Phase 2: Code Generation](#phase-2-code-generation-week-2)
5. [Phase 3: Domain Layer](#phase-3-domain-layer-week-3-4)
6. [Phase 4: Data Layer](#phase-4-data-layer-week-5-6)
7. [Phase 5: Presentation Layer](#phase-5-presentation-layer-week-7-10)
8. [Phase 6: Background Sync](#phase-6-background-sync-week-11)
9. [Phase 7: Testing](#phase-7-testing-week-12)
10. [Phase 8: Security & Polish](#phase-8-security--polish-week-13-14)

---

## 1. Overview

### Implementation Strategy

**Approach**: Bottom-up implementation (infrastructure → business logic → UI)
**Testing**: Test each phase before moving to next
**Integration**: Continuous integration throughout
**Milestones**: Working app at end of each phase

### Success Criteria Per Phase

Each phase ends with:
- ✅ All planned code written and reviewed
- ✅ All tests passing (unit/integration/UI as applicable)
- ✅ Documentation updated
- ✅ Demo to stakeholders (working features)

---

## Phase 0: Prerequisites (Week 0)

### Required Knowledge

**Team Skills Needed**:
- Kotlin (intermediate to advanced)
- Jetpack Compose (intermediate)
- Android Architecture Components (ViewModel, Room, WorkManager)
- Dependency Injection (Hilt)
- Coroutines & Flow
- RESTful APIs
- Git version control

**Recommended Pre-Reading**:
1. [API_CONTRACT_FOUNDATION.md](./API_CONTRACT_FOUNDATION.md) - 45 min
2. [KOTLIN_PRD_SUMMARY.md](./KOTLIN_PRD_SUMMARY.md) sections 1-4 - 30 min
3. [MAPPING_GUIDE.md](./MAPPING_GUIDE.md) - 40 min

### Tools & Environment Setup

**Required Software**:
```bash
# Android Studio
Download: Android Studio Hedgehog | 2023.1.1 or later
Install: Android SDK 34 (API 34)

# JDK
Required: JDK 17

# Command Line Tools
- Git
- Gradle (comes with Android Studio)
```

**Backend Coordination**:
- [ ] Receive `openapi.yaml` from backend team
- [ ] Get API base URL (dev, staging, production)
- [ ] Get test credentials for API
- [ ] Confirm WebSocket endpoint availability

### Repository Setup

```bash
# Create new repository
git init MyFacilityApp
cd MyFacilityApp

# Create .gitignore
cat > .gitignore << 'EOF'
# Android
*.apk
*.ap_
*.dex
*.class
bin/
gen/
out/
build/
.gradle/
local.properties

# IDE
.idea/
*.iml
.DS_Store

# Keystore
*.jks
*.keystore

# Secrets
secrets.properties
google-services.json
EOF

# First commit
git add .gitignore
git commit -m "Initial commit with .gitignore"
```

---

## Phase 1: Project Setup (Week 1)

### 1.1 Create Multi-Module Project

**Estimated Time**: 4 hours

**Steps**:

1. **Create Project in Android Studio**
```
File → New → New Project
Choose: Empty Activity
Name: MyFacilityApp
Package: com.example.facility
Language: Kotlin
Minimum SDK: API 21 (Android 5.0)
Build configuration language: Kotlin DSL
```

2. **Create Modules**

```bash
# In Android Studio
File → New → New Module → Android Library

Create these modules:
- domain (Pure Kotlin - no Android dependencies)
- data (Android Library)
- network (Android Library)
- database (Android Library)
- common (Pure Kotlin)
```

3. **Configure Root build.gradle.kts**

```kotlin
// build.gradle.kts (Project)
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.hilt) apply false
    alias(libs.plugins.ksp) apply false
}

tasks.register("clean", Delete::class) {
    delete(rootProject.buildDir)
}
```

4. **Create Version Catalog**

Create `gradle/libs.versions.toml`:

```toml
[versions]
kotlin = "1.9.20"
compose = "1.5.4"
composeCompiler = "1.5.4"
hilt = "2.48"
room = "2.6.0"
retrofit = "2.9.0"
okhttp = "4.12.0"
coroutines = "1.7.3"
kotlinx-serialization = "1.6.2"
kotlinx-datetime = "0.5.0"
coil = "2.5.0"
work = "2.9.0"

[libraries]
# Kotlin
kotlin-stdlib = { module = "org.jetbrains.kotlin:kotlin-stdlib", version.ref = "kotlin" }
kotlinx-coroutines-core = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-core", version.ref = "coroutines" }
kotlinx-coroutines-android = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-android", version.ref = "coroutines" }
kotlinx-serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "kotlinx-serialization" }
kotlinx-datetime = { module = "org.jetbrains.kotlinx:kotlinx-datetime", version.ref = "kotlinx-datetime" }

# Compose
compose-ui = { module = "androidx.compose.ui:ui", version.ref = "compose" }
compose-material3 = { module = "androidx.compose.material3:material3", version = "1.1.2" }
compose-ui-tooling = { module = "androidx.compose.ui:ui-tooling", version.ref = "compose" }
compose-ui-tooling-preview = { module = "androidx.compose.ui:ui-tooling-preview", version.ref = "compose" }
compose-activity = { module = "androidx.activity:activity-compose", version = "1.8.1" }
compose-lifecycle = { module = "androidx.lifecycle:lifecycle-runtime-compose", version = "2.6.2" }
compose-navigation = { module = "androidx.navigation:navigation-compose", version = "2.7.5" }

# Hilt
hilt-android = { module = "com.google.dagger:hilt-android", version.ref = "hilt" }
hilt-compiler = { module = "com.google.dagger:hilt-compiler", version.ref = "hilt" }
hilt-navigation-compose = { module = "androidx.hilt:hilt-navigation-compose", version = "1.1.0" }

# Room
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-ktx = { module = "androidx.room:room-ktx", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }

# Retrofit
retrofit-core = { module = "com.squareup.retrofit2:retrofit", version.ref = "retrofit" }
retrofit-kotlinx-serialization = { module = "com.jakewharton.retrofit:retrofit2-kotlinx-serialization-converter", version = "1.0.0" }
okhttp-core = { module = "com.squareup.okhttp3:okhttp", version.ref = "okhttp" }
okhttp-logging = { module = "com.squareup.okhttp3:logging-interceptor", version.ref = "okhttp" }

# WorkManager
work-runtime = { module = "androidx.work:work-runtime-ktx", version.ref = "work" }

# Image Loading
coil = { module = "io.coil-kt:coil-compose", version.ref = "coil" }

# Security
security-crypto = { module = "androidx.security:security-crypto", version = "1.1.0-alpha06" }

# Testing
junit = { module = "junit:junit", version = "4.13.2" }
mockk = { module = "io.mockk:mockk", version = "1.13.8" }
coroutines-test = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-test", version.ref = "coroutines" }
turbine = { module = "app.cash.turbine:turbine", version = "1.0.0" }
compose-ui-test = { module = "androidx.compose.ui:ui-test-junit4", version.ref = "compose" }
hilt-testing = { module = "com.google.dagger:hilt-android-testing", version.ref = "hilt" }

[plugins]
android-application = { id = "com.android.application", version = "8.1.4" }
android-library = { id = "com.android.library", version = "8.1.4" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
hilt = { id = "com.google.dagger.hilt.android", version.ref = "hilt" }
ksp = { id = "com.google.devtools.ksp", version = "1.9.20-1.0.14" }
```

### 1.2 Configure Each Module

**app/build.gradle.kts**:
```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.example.facility"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.example.facility"
        minSdk = 21
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            isDebuggable = true
            buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000\"")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            buildConfigField("String", "API_BASE_URL", "\"https://api.example.com\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = libs.versions.composeCompiler.get()
    }
}

dependencies {
    // Modules
    implementation(project(":domain"))
    implementation(project(":data"))
    implementation(project(":common"))

    // Compose
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.activity)
    implementation(libs.compose.lifecycle)
    implementation(libs.compose.navigation)
    debugImplementation(libs.compose.ui.tooling)

    // Hilt
    implementation(libs.hilt.android)
    implementation(libs.hilt.navigation.compose)
    ksp(libs.hilt.compiler)

    // Image Loading
    implementation(libs.coil)

    // Testing
    testImplementation(libs.junit)
    androidTestImplementation(libs.compose.ui.test)
}
```

**domain/build.gradle.kts** (Pure Kotlin):
```kotlin
plugins {
    id("java-library")
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

dependencies {
    // Pure Kotlin - NO Android dependencies
    implementation(libs.kotlinx.coroutines.core)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.datetime)

    // Testing
    testImplementation(libs.junit)
    testImplementation(libs.mockk)
    testImplementation(libs.coroutines.test)
}
```

**data/build.gradle.kts**:
```kotlin
plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.example.facility.data"
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
    // Modules
    api(project(":domain"))
    implementation(project(":network"))
    implementation(project(":database"))
    implementation(project(":common"))

    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // Testing
    testImplementation(libs.junit)
    testImplementation(libs.mockk)
    androidTestImplementation(libs.hilt.testing)
}
```

**network/build.gradle.kts**:
```kotlin
plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
    id("org.openapi.generator") version "7.1.0"
}

android {
    namespace = "com.example.facility.network"
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
    // Retrofit
    implementation(libs.retrofit.core)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp.core)
    implementation(libs.okhttp.logging)

    // Serialization
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.datetime)

    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    // Testing
    testImplementation(libs.junit)
    testImplementation(libs.mockk)
}

// OpenAPI Generator Configuration (will add in Phase 2)
```

**database/build.gradle.kts**:
```kotlin
plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.example.facility.database"
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
    // Room
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)

    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // Testing
    testImplementation(libs.junit)
    androidTestImplementation(libs.hilt.testing)
}
```

**common/build.gradle.kts** (Pure Kotlin):
```kotlin
plugins {
    id("java-library")
    alias(libs.plugins.kotlin.jvm)
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

dependencies {
    implementation(libs.kotlinx.coroutines.core)

    testImplementation(libs.junit)
}
```

### 1.3 Create Initial Package Structure

```bash
# domain module
mkdir -p domain/src/main/kotlin/com/example/facility/domain/{model,usecase,repository}
mkdir -p domain/src/test/kotlin/com/example/facility/domain

# data module
mkdir -p data/src/main/kotlin/com/example/facility/data/{repository,mapper,source/{remote,local}}
mkdir -p data/src/test/kotlin/com/example/facility/data

# network module
mkdir -p network/src/main/kotlin/com/example/facility/network/{api,dto,interceptor,websocket}
mkdir -p network/src/openapi  # For openapi.yaml
mkdir -p network/src/test/kotlin/com/example/facility/network

# database module
mkdir -p database/src/main/kotlin/com/example/facility/database/{entity,dao}
mkdir -p database/src/androidTest/kotlin/com/example/facility/database

# common module
mkdir -p common/src/main/kotlin/com/example/facility/common/{result,util,constant}
mkdir -p common/src/test/kotlin/com/example/facility/common

# app module
mkdir -p app/src/main/kotlin/com/example/facility/{ui,navigation,di}
mkdir -p app/src/androidTest/kotlin/com/example/facility/ui
```

### 1.4 Create Result Sealed Class

**common/src/main/kotlin/com/example/facility/common/result/Result.kt**:
```kotlin
package com.example.facility.common.result

sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val error: Throwable) : Result<Nothing>()
    data class Loading(val progress: Float? = null) : Result<Nothing>()

    fun isSuccess(): Boolean = this is Success
    fun isError(): Boolean = this is Error
    fun isLoading(): Boolean = this is Loading

    fun getOrNull(): T? = when (this) {
        is Success -> data
        else -> null
    }

    fun getOrThrow(): T = when (this) {
        is Success -> data
        is Error -> throw error
        is Loading -> throw IllegalStateException("Result is still loading")
    }

    fun getOrElse(default: T): T = when (this) {
        is Success -> data
        else -> default
    }

    inline fun <R> map(transform: (T) -> R): Result<R> = when (this) {
        is Success -> Success(transform(data))
        is Error -> Error(error)
        is Loading -> Loading(progress)
    }

    inline fun onSuccess(action: (T) -> Unit): Result<T> {
        if (this is Success) action(data)
        return this
    }

    inline fun onError(action: (Throwable) -> Unit): Result<T> {
        if (this is Error) action(error)
        return this
    }

    inline fun onLoading(action: (Float?) -> Unit): Result<T> {
        if (this is Loading) action(progress)
        return this
    }
}

// Extension function for suspending operations
suspend fun <T> resultOf(block: suspend () -> T): Result<T> {
    return try {
        Result.Success(block())
    } catch (e: Exception) {
        Result.Error(e)
    }
}
```

### 1.5 Create Hilt Application Class

**app/src/main/kotlin/com/example/facility/FacilityApplication.kt**:
```kotlin
package com.example.facility

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class FacilityApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Initialize logging, analytics, etc.
    }
}
```

**app/src/main/AndroidManifest.xml**:
```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />

    <application
        android:name=".FacilityApplication"
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.MyFacilityApp"
        android:networkSecurityConfig="@xml/network_security_config">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.MyFacilityApp">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

### 1.6 Create Network Security Config

**app/src/main/res/xml/network_security_config.xml**:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Allow cleartext for localhost (dev only) -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">localhost</domain>
        <domain includeSubdomains="true">10.0.2.2</domain>
    </domain-config>

    <!-- Production API with certificate pinning -->
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>
        <!-- Add certificate pins in production -->
        <!--
        <pin-set expiration="2026-01-01">
            <pin digest="SHA-256">base64hash==</pin>
            <pin digest="SHA-256">backuphash==</pin>
        </pin-set>
        -->
    </domain-config>
</network-security-config>
```

### 1.7 Verify Build

```bash
# Sync Gradle
./gradlew clean build

# Expected: All modules compile successfully
```

### Phase 1 Deliverables

- [x] Multi-module project structure created
- [x] All build.gradle.kts files configured
- [x] Version catalog created (libs.versions.toml)
- [x] Package structure created for all modules
- [x] Result sealed class implemented
- [x] Hilt application class created
- [x] Network security config created
- [x] Project builds successfully

**Time Check**: Should complete in 1 day (8 hours)

---

## Phase 2: Code Generation (Week 2)

### 2.1 Receive OpenAPI Schema

**Coordinate with Backend Team**:

```bash
# Backend generates schema
cd /path/to/django/project
python manage.py spectacular --file openapi.yaml --validate

# Copy to Android project
cp openapi.yaml /path/to/android/project/network/src/openapi/
```

### 2.2 Configure OpenAPI Generator

**network/build.gradle.kts** (add to existing file):
```kotlin
// After dependencies block
openApiGenerate {
    generatorName.set("kotlin")
    inputSpec.set("$projectDir/src/openapi/openapi.yaml")
    outputDir.set("$buildDir/generated/openapi")
    apiPackage.set("com.example.facility.network.api")
    modelPackage.set("com.example.facility.network.dto")
    packageName.set("com.example.facility.network")

    configOptions.set(mapOf(
        "library" to "jvm-retrofit2",
        "serializationLibrary" to "kotlinx_serialization",
        "dateLibrary" to "kotlinx-datetime",
        "enumPropertyNaming" to "UPPERCASE",
        "useCoroutines" to "true",
        "collectionType" to "list"
    ))

    typeMappings.set(mapOf(
        "DateTime" to "kotlinx.datetime.Instant",
        "Date" to "kotlinx.datetime.LocalDate",
        "UUID" to "kotlin.String"
    ))

    importMappings.set(mapOf(
        "Instant" to "kotlinx.datetime.Instant",
        "LocalDate" to "kotlinx.datetime.LocalDate"
    ))

    skipOperationExample.set(true)
    generateApiTests.set(false)
    generateModelTests.set(false)
    generateApiDocumentation.set(false)
    generateModelDocumentation.set(false)
}

// Add generated sources
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

### 2.3 Generate DTOs

```bash
# Generate DTOs from OpenAPI
./gradlew :network:openApiGenerate

# Verify generated code
ls network/build/generated/openapi/src/main/kotlin/com/example/facility/network/

# Expected directories:
# - api/ (Retrofit services)
# - dto/ (Data transfer objects)
# - infrastructure/
```

### 2.4 Create Custom Serializers

**network/src/main/kotlin/com/example/facility/network/serializer/InstantSerializer.kt**:
```kotlin
package com.example.facility.network.serializer

import kotlinx.datetime.Instant
import kotlinx.serialization.KSerializer
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder

object InstantSerializer : KSerializer<Instant> {
    override val descriptor = PrimitiveSerialDescriptor("Instant", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: Instant) {
        encoder.encodeString(value.toString())
    }

    override fun deserialize(decoder: Decoder): Instant {
        return Instant.parse(decoder.decodeString())
    }
}
```

### 2.5 Configure JSON Instance

**network/src/main/kotlin/com/example/facility/network/JsonConfig.kt**:
```kotlin
package com.example.facility.network

import kotlinx.serialization.json.Json

object JsonConfig {
    val json = Json {
        ignoreUnknownKeys = true  // Ignore extra fields from server
        isLenient = true           // Accept non-strict JSON
        encodeDefaults = false     // Don't encode default values
        prettyPrint = false        // Compact JSON
        coerceInputValues = true   // Coerce incorrect values
    }
}
```

### 2.6 Test Generated DTOs

**network/src/test/kotlin/com/example/facility/network/dto/JournalEntryDTOTest.kt**:
```kotlin
package com.example.facility.network.dto

import com.example.facility.network.JsonConfig
import kotlinx.datetime.Instant
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull

class JournalEntryDTOTest {

    private val json = JsonConfig.json

    @Test
    fun `deserialize journal entry from JSON`() {
        val jsonString = """
            {
              "id": "abc-123-def-456",
              "title": "Morning reflection",
              "entry_type": "mood_check_in",
              "mood_rating": 8,
              "stress_level": 2,
              "privacy_scope": "private",
              "created_at": "2025-10-30T09:00:00Z",
              "updated_at": "2025-10-30T09:00:00Z"
            }
        """.trimIndent()

        val dto = json.decodeFromString<JournalEntryDTO>(jsonString)

        assertEquals("abc-123-def-456", dto.id)
        assertEquals("Morning reflection", dto.title)
        assertEquals(8, dto.moodRating)
        assertNotNull(dto.createdAt)
    }

    @Test
    fun `serialize journal entry to JSON`() {
        val dto = JournalEntryCreateDTO(
            title = "Test entry",
            entryType = EntryTypeEnum.MOOD_CHECK_IN,
            moodRating = 7,
            privacyScope = PrivacyScopeEnum.PRIVATE,
            timestamp = Instant.parse("2025-10-30T09:00:00Z")
        )

        val jsonString = json.encodeToString(dto)

        assert(jsonString.contains("\"title\":\"Test entry\""))
        assert(jsonString.contains("\"mood_rating\":7"))
    }
}
```

Run tests:
```bash
./gradlew :network:test
```

### Phase 2 Deliverables

- [x] OpenAPI schema received from backend
- [x] OpenAPI generator configured
- [x] DTOs generated successfully
- [x] Custom serializers created
- [x] JSON configuration created
- [x] DTO tests written and passing
- [x] Generated code reviewed

**Time Check**: Should complete in 2-3 days

---

## Phase 3: Domain Layer (Week 3-4)

### 3.1 Create Domain Entities

**domain/src/main/kotlin/com/example/facility/domain/model/wellness/JournalEntry.kt**:
```kotlin
package com.example.facility.domain.model.wellness

import kotlinx.datetime.Instant

data class JournalEntry(
    val id: JournalId,
    val userId: UserId,
    val title: Title,
    val entryType: EntryType,
    val timestamp: Instant,
    val wellbeingMetrics: WellbeingMetrics?,
    val positiveReflections: PositiveReflections?,
    val locationContext: LocationContext?,
    val privacyScope: PrivacyScope,
    val syncMetadata: SyncMetadata,
    val audit: AuditInfo
)

// Value Objects
@JvmInline
value class JournalId(val value: String)

@JvmInline
value class UserId(val value: Int)

@JvmInline
value class Title(val value: String) {
    init {
        require(value.length in 1..200) { "Title must be 1-200 characters" }
    }
}

// Entry Type
sealed class EntryType {
    abstract val key: String

    object MoodCheckIn : EntryType() {
        override val key = "mood_check_in"
    }

    object Gratitude : EntryType() {
        override val key = "gratitude"
    }

    object DailyReflection : EntryType() {
        override val key = "daily_reflection"
    }

    // Add other types...

    companion object {
        fun fromKey(key: String): EntryType = when (key) {
            "mood_check_in" -> MoodCheckIn
            "gratitude" -> Gratitude
            "daily_reflection" -> DailyReflection
            else -> throw IllegalArgumentException("Unknown entry type: $key")
        }
    }
}

// Wellbeing Metrics
data class WellbeingMetrics(
    val moodRating: MoodRating?,
    val stressLevel: StressLevel?,
    val energyLevel: EnergyLevel?,
    val stressTriggers: List<String>,
    val copingStrategies: List<String>
)

@JvmInline
value class MoodRating(val value: Int) {
    init {
        require(value in 1..10) { "Mood rating must be 1-10" }
    }
}

@JvmInline
value class StressLevel(val value: Int) {
    init {
        require(value in 1..5) { "Stress level must be 1-5" }
    }
}

@JvmInline
value class EnergyLevel(val value: Int) {
    init {
        require(value in 1..10) { "Energy level must be 1-10" }
    }
}

// Positive Reflections
data class PositiveReflections(
    val gratitudeItems: List<String>,
    val dailyGoals: List<String>,
    val affirmations: List<String>,
    val achievements: List<String>
)

// Location Context
data class LocationContext(
    val siteName: String?,
    val coordinates: Coordinates?
)

data class Coordinates(
    val lat: Double,
    val lng: Double
) {
    init {
        require(lat in -90.0..90.0) { "Invalid latitude: $lat" }
        require(lng in -180.0..180.0) { "Invalid longitude: $lng" }
    }
}

// Privacy Scope
sealed class PrivacyScope {
    object Private : PrivacyScope()
    object Manager : PrivacyScope()
    object Team : PrivacyScope()
    object Aggregate : PrivacyScope()
    object Shared : PrivacyScope()

    companion object {
        fun fromString(value: String): PrivacyScope = when (value.lowercase()) {
            "private" -> Private
            "manager" -> Manager
            "team" -> Team
            "aggregate" -> Aggregate
            "shared" -> Shared
            else -> throw IllegalArgumentException("Unknown privacy scope: $value")
        }
    }
}

// Sync Metadata
data class SyncMetadata(
    val mobileId: String,
    val serverId: String?,
    val version: Int,
    val syncStatus: SyncStatus,
    val lastSyncTimestamp: Instant?
)

enum class SyncStatus {
    DRAFT,
    PENDING_SYNC,
    SYNCED,
    SYNC_ERROR,
    PENDING_DELETE
}

// Audit Info
data class AuditInfo(
    val createdAt: Instant,
    val updatedAt: Instant
)
```

### 3.2 Create Repository Interfaces

**domain/src/main/kotlin/com/example/facility/domain/repository/WellnessRepository.kt**:
```kotlin
package com.example.facility.domain.repository

import com.example.facility.common.result.Result
import com.example.facility.domain.model.wellness.*
import kotlinx.coroutines.flow.Flow

interface WellnessRepository {

    /**
     * Get journal entries for current user.
     * Emits cached data immediately, then fresh data after network fetch.
     */
    fun getJournalEntries(
        entryType: EntryType? = null,
        isDraft: Boolean? = null,
        forceRefresh: Boolean = false
    ): Flow<Result<List<JournalEntry>>>

    /**
     * Get specific journal entry by ID.
     */
    fun getJournalEntry(id: JournalId): Flow<Result<JournalEntry>>

    /**
     * Create journal entry.
     * Saves locally immediately, adds to sync queue, syncs in background.
     */
    fun createJournalEntry(
        title: Title,
        entryType: EntryType,
        timestamp: Instant,
        privacyScope: PrivacyScope,
        wellbeingMetrics: WellbeingMetrics? = null,
        positiveReflections: PositiveReflections? = null,
        locationContext: LocationContext? = null
    ): Flow<Result<JournalEntry>>

    /**
     * Update journal entry.
     */
    fun updateJournalEntry(
        id: JournalId,
        title: Title? = null,
        wellbeingMetrics: WellbeingMetrics? = null,
        positiveReflections: PositiveReflections? = null
    ): Flow<Result<JournalEntry>>

    /**
     * Delete journal entry (soft delete).
     */
    fun deleteJournalEntry(id: JournalId): Flow<Result<Unit>>
}
```

### 3.3 Create Use Cases

**domain/src/main/kotlin/com/example/facility/domain/usecase/wellness/CreateJournalEntryUseCase.kt**:
```kotlin
package com.example.facility.domain.usecase.wellness

import com.example.facility.common.result.Result
import com.example.facility.domain.model.wellness.*
import com.example.facility.domain.repository.WellnessRepository
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

class CreateJournalEntryUseCase @Inject constructor(
    private val repository: WellnessRepository,
    private val validator: JournalEntryValidator
) {
    operator fun invoke(
        title: String,
        entryType: String,
        timestamp: kotlinx.datetime.Instant,
        privacyScope: String,
        moodRating: Int? = null,
        stressLevel: Int? = null,
        energyLevel: Int? = null,
        gratitudeItems: List<String>? = null,
        dailyGoals: List<String>? = null
    ): Flow<Result<JournalEntry>> {
        // Validate inputs
        val validationResult = validator.validate(
            title = title,
            moodRating = moodRating,
            stressLevel = stressLevel,
            energyLevel = energyLevel
        )

        if (validationResult is Result.Error) {
            return kotlinx.coroutines.flow.flowOf(validationResult)
        }

        // Create domain objects
        val titleObj = Title(title)
        val entryTypeObj = EntryType.fromKey(entryType)
        val privacyScopeObj = PrivacyScope.fromString(privacyScope)

        val wellbeingMetrics = if (moodRating != null || stressLevel != null || energyLevel != null) {
            WellbeingMetrics(
                moodRating = moodRating?.let { MoodRating(it) },
                stressLevel = stressLevel?.let { StressLevel(it) },
                energyLevel = energyLevel?.let { EnergyLevel(it) },
                stressTriggers = emptyList(),
                copingStrategies = emptyList()
            )
        } else null

        val positiveReflections = if (!gratitudeItems.isNullOrEmpty() || !dailyGoals.isNullOrEmpty()) {
            PositiveReflections(
                gratitudeItems = gratitudeItems ?: emptyList(),
                dailyGoals = dailyGoals ?: emptyList(),
                affirmations = emptyList(),
                achievements = emptyList()
            )
        } else null

        // Delegate to repository
        return repository.createJournalEntry(
            title = titleObj,
            entryType = entryTypeObj,
            timestamp = timestamp,
            privacyScope = privacyScopeObj,
            wellbeingMetrics = wellbeingMetrics,
            positiveReflections = positiveReflections,
            locationContext = null
        )
    }
}

class JournalEntryValidator @Inject constructor() {
    fun validate(
        title: String,
        moodRating: Int?,
        stressLevel: Int?,
        energyLevel: Int?
    ): Result<Unit> {
        if (title.isBlank() || title.length > 200) {
            return Result.Error(IllegalArgumentException("Title must be 1-200 characters"))
        }

        moodRating?.let {
            if (it !in 1..10) {
                return Result.Error(IllegalArgumentException("Mood rating must be 1-10"))
            }
        }

        stressLevel?.let {
            if (it !in 1..5) {
                return Result.Error(IllegalArgumentException("Stress level must be 1-5"))
            }
        }

        energyLevel?.let {
            if (it !in 1..10) {
                return Result.Error(IllegalArgumentException("Energy level must be 1-10"))
            }
        }

        return Result.Success(Unit)
    }
}
```

### 3.4 Write Domain Tests

**domain/src/test/kotlin/com/example/facility/domain/usecase/CreateJournalEntryUseCaseTest.kt**:
```kotlin
package com.example.facility.domain.usecase

import com.example.facility.common.result.Result
import com.example.facility.domain.model.wellness.*
import com.example.facility.domain.repository.WellnessRepository
import com.example.facility.domain.usecase.wellness.CreateJournalEntryUseCase
import com.example.facility.domain.usecase.wellness.JournalEntryValidator
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import kotlinx.datetime.Instant
import org.junit.Before
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CreateJournalEntryUseCaseTest {

    private lateinit var repository: WellnessRepository
    private lateinit var validator: JournalEntryValidator
    private lateinit var useCase: CreateJournalEntryUseCase

    @Before
    fun setup() {
        repository = mockk()
        validator = JournalEntryValidator()
        useCase = CreateJournalEntryUseCase(repository, validator)
    }

    @Test
    fun `create journal entry with valid data returns success`() = runTest {
        // Given
        val title = "Morning reflection"
        val entryType = "mood_check_in"
        val timestamp = Instant.parse("2025-10-30T09:00:00Z")
        val privacyScope = "private"
        val moodRating = 8

        val expectedEntry = mockk<JournalEntry>()

        every {
            repository.createJournalEntry(any(), any(), any(), any(), any(), any(), any())
        } returns flowOf(Result.Success(expectedEntry))

        // When
        val result = useCase(
            title = title,
            entryType = entryType,
            timestamp = timestamp,
            privacyScope = privacyScope,
            moodRating = moodRating
        ).first()

        // Then
        assertTrue(result is Result.Success)
        assertEquals(expectedEntry, (result as Result.Success).data)

        verify {
            repository.createJournalEntry(
                title = any(),
                entryType = any(),
                timestamp = timestamp,
                privacyScope = any(),
                wellbeingMetrics = any(),
                positiveReflections = null,
                locationContext = null
            )
        }
    }

    @Test
    fun `create journal entry with invalid mood rating returns error`() = runTest {
        // Given
        val title = "Test"
        val entryType = "mood_check_in"
        val timestamp = Instant.parse("2025-10-30T09:00:00Z")
        val privacyScope = "private"
        val moodRating = 15  // Invalid: must be 1-10

        // When
        val result = useCase(
            title = title,
            entryType = entryType,
            timestamp = timestamp,
            privacyScope = privacyScope,
            moodRating = moodRating
        ).first()

        // Then
        assertTrue(result is Result.Error)
    }
}
```

Run tests:
```bash
./gradlew :domain:test
```

### Phase 3 Deliverables

- [x] Domain entities created (JournalEntry, etc.)
- [x] Value objects implemented (Title, MoodRating, etc.)
- [x] Repository interfaces defined
- [x] Use cases implemented
- [x] Validators created
- [x] Domain tests written and passing (80%+ coverage)
- [x] Code reviewed

**Time Check**: Should complete in 1-2 weeks

---

## Phase 4: Data Layer (Week 5-6)

### 4.1 Create Room Database Schema

**Estimated Time**: 8-10 hours

**database/src/main/kotlin/com/example/facility/database/entity/JournalCacheEntity.kt**:
```kotlin
package com.example.facility.database.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "journal_entry_local")
data class JournalCacheEntity(
    @PrimaryKey
    val id: String,

    @ColumnInfo(name = "user_id")
    val userId: Int,

    val title: String,

    @ColumnInfo(name = "entry_type")
    val entryType: String,

    val timestamp: Long,  // Unix epoch milliseconds

    // Wellbeing metrics (separate columns for SQL queries)
    @ColumnInfo(name = "mood_rating")
    val moodRating: Int?,

    @ColumnInfo(name = "stress_level")
    val stressLevel: Int?,

    @ColumnInfo(name = "energy_level")
    val energyLevel: Int?,

    // Complex fields as JSON strings
    @ColumnInfo(name = "gratitude_items_json")
    val gratitudeItemsJson: String,

    @ColumnInfo(name = "daily_goals_json")
    val dailyGoalsJson: String,

    @ColumnInfo(name = "affirmations_json")
    val affirmationsJson: String,

    @ColumnInfo(name = "achievements_json")
    val achievementsJson: String,

    // Location (separate columns)
    @ColumnInfo(name = "location_site_name")
    val locationSiteName: String?,

    @ColumnInfo(name = "location_lat")
    val locationLat: Double?,

    @ColumnInfo(name = "location_lng")
    val locationLng: Double?,

    // Privacy
    @ColumnInfo(name = "privacy_scope")
    val privacyScope: String,

    // Sync metadata
    @ColumnInfo(name = "mobile_id")
    val mobileId: String,

    @ColumnInfo(name = "server_id")
    val serverId: String?,

    @ColumnInfo(name = "version")
    val version: Int,

    @ColumnInfo(name = "sync_status")
    val syncStatus: String,

    @ColumnInfo(name = "last_sync_timestamp")
    val lastSyncTimestamp: Long?,

    // Audit
    @ColumnInfo(name = "created_at")
    val createdAt: Long,

    @ColumnInfo(name = "updated_at")
    val updatedAt: Long,

    // Cache metadata
    @ColumnInfo(name = "is_draft")
    val isDraft: Boolean = false,

    @ColumnInfo(name = "is_deleted")
    val isDeleted: Boolean = false
)
```

**database/src/main/kotlin/com/example/facility/database/entity/PendingOperationEntity.kt**:
```kotlin
package com.example.facility.database.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pending_operations")
data class PendingOperationEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "operation_type")
    val operationType: String,  // CREATE, UPDATE, DELETE

    @ColumnInfo(name = "entity_type")
    val entityType: String,  // JOURNAL, JOB, ATTENDANCE, etc.

    @ColumnInfo(name = "entity_id")
    val entityId: String,  // mobile_id or server_id

    @ColumnInfo(name = "payload")
    val payload: String,  // JSON to send to API

    @ColumnInfo(name = "created_at")
    val createdAt: Long,

    @ColumnInfo(name = "retry_count")
    val retryCount: Int = 0,

    @ColumnInfo(name = "last_error")
    val lastError: String? = null,

    @ColumnInfo(name = "last_retry_at")
    val lastRetryAt: Long? = null
)
```

### 4.2 Create Room DAOs

**database/src/main/kotlin/com/example/facility/database/dao/JournalDao.kt**:
```kotlin
package com.example.facility.database.dao

import androidx.room.*
import com.example.facility.database.entity.JournalCacheEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface JournalDao {

    @Query("SELECT * FROM journal_entry_local WHERE is_deleted = 0 ORDER BY created_at DESC")
    fun getAllFlow(): Flow<List<JournalCacheEntity>>

    @Query("SELECT * FROM journal_entry_local WHERE is_deleted = 0 ORDER BY created_at DESC")
    suspend fun getAll(): List<JournalCacheEntity>

    @Query("SELECT * FROM journal_entry_local WHERE id = :id AND is_deleted = 0")
    suspend fun getById(id: String): JournalCacheEntity?

    @Query("SELECT * FROM journal_entry_local WHERE mobile_id = :mobileId")
    suspend fun getByMobileId(mobileId: String): JournalCacheEntity?

    @Query("SELECT * FROM journal_entry_local WHERE entry_type = :entryType AND is_deleted = 0")
    suspend fun getByType(entryType: String): List<JournalCacheEntity>

    @Query("SELECT * FROM journal_entry_local WHERE is_draft = :isDraft AND is_deleted = 0")
    suspend fun getByDraft(isDraft: Boolean): List<JournalCacheEntity>

    @Query("SELECT * FROM journal_entry_local WHERE sync_status = :status AND is_deleted = 0")
    suspend fun getBySyncStatus(status: String): List<JournalCacheEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: JournalCacheEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<JournalCacheEntity>)

    @Update
    suspend fun update(entity: JournalCacheEntity)

    @Delete
    suspend fun delete(entity: JournalCacheEntity)

    @Query("UPDATE journal_entry_local SET is_deleted = 1, updated_at = :timestamp WHERE id = :id")
    suspend fun softDelete(id: String, timestamp: Long)

    @Query("UPDATE journal_entry_local SET sync_status = :status, last_sync_timestamp = :timestamp WHERE id = :id")
    suspend fun updateSyncStatus(id: String, status: String, timestamp: Long)

    @Query("DELETE FROM journal_entry_local WHERE is_deleted = 1 AND updated_at < :timestamp")
    suspend fun purgeDeleted(timestamp: Long)
}
```

**database/src/main/kotlin/com/example/facility/database/dao/PendingOperationsDao.kt**:
```kotlin
package com.example.facility.database.dao

import androidx.room.*
import com.example.facility.database.entity.PendingOperationEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PendingOperationsDao {

    @Query("SELECT * FROM pending_operations ORDER BY created_at ASC")
    suspend fun getAll(): List<PendingOperationEntity>

    @Query("SELECT * FROM pending_operations ORDER BY created_at ASC")
    fun getAllFlow(): Flow<List<PendingOperationEntity>>

    @Query("SELECT * FROM pending_operations WHERE entity_type = :entityType")
    suspend fun getByEntityType(entityType: String): List<PendingOperationEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(operation: PendingOperationEntity)

    @Delete
    suspend fun delete(operation: PendingOperationEntity)

    @Query("DELETE FROM pending_operations WHERE entity_id = :entityId")
    suspend fun deleteByEntityId(entityId: String)

    @Query("UPDATE pending_operations SET retry_count = retry_count + 1, last_error = :error, last_retry_at = :timestamp WHERE entity_id = :entityId")
    suspend fun incrementRetryCount(entityId: String, error: String, timestamp: Long)

    @Query("DELETE FROM pending_operations WHERE retry_count >= :maxRetries")
    suspend fun purgeExceededRetries(maxRetries: Int)
}
```

### 4.3 Create Room Database

**database/src/main/kotlin/com/example/facility/database/FacilityDatabase.kt**:
```kotlin
package com.example.facility.database

import androidx.room.Database
import androidx.room.RoomDatabase
import com.example.facility.database.dao.JournalDao
import com.example.facility.database.dao.PendingOperationsDao
import com.example.facility.database.entity.JournalCacheEntity
import com.example.facility.database.entity.PendingOperationEntity

@Database(
    entities = [
        JournalCacheEntity::class,
        PendingOperationEntity::class
        // Add other entities as you build them
    ],
    version = 1,
    exportSchema = true
)
abstract class FacilityDatabase : RoomDatabase() {
    abstract fun journalDao(): JournalDao
    abstract fun pendingOperationsDao(): PendingOperationsDao
    // Add other DAOs as you build them
}
```

**database/src/main/kotlin/com/example/facility/database/di/DatabaseModule.kt**:
```kotlin
package com.example.facility.database.di

import android.content.Context
import androidx.room.Room
import com.example.facility.database.FacilityDatabase
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(
        @ApplicationContext context: Context
    ): FacilityDatabase {
        return Room.databaseBuilder(
            context,
            FacilityDatabase::class.java,
            "facility_database"
        )
            .fallbackToDestructiveMigration()  // For development - remove in production
            .build()
    }

    @Provides
    fun provideJournalDao(database: FacilityDatabase) = database.journalDao()

    @Provides
    fun providePendingOperationsDao(database: FacilityDatabase) = database.pendingOperationsDao()
}
```

### 4.4 Create Mappers

**data/src/main/kotlin/com/example/facility/data/mapper/JournalMapper.kt**:
```kotlin
package com.example.facility.data.mapper

import com.example.facility.database.entity.JournalCacheEntity
import com.example.facility.domain.model.wellness.*
import com.example.facility.network.dto.JournalEntryDTO
import kotlinx.datetime.Instant
import kotlinx.serialization.encodeToString
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import java.util.UUID
import javax.inject.Inject

class JournalMapper @Inject constructor(
    private val json: Json
) {
    /**
     * DTO → Domain Entity
     */
    fun toDomain(dto: JournalEntryDTO): JournalEntry {
        return JournalEntry(
            id = JournalId(dto.id),
            userId = UserId(dto.userId),
            title = Title(dto.title),
            entryType = EntryType.fromKey(dto.entryType.name.lowercase()),
            timestamp = dto.timestamp,
            wellbeingMetrics = if (dto.moodRating != null || dto.stressLevel != null || dto.energyLevel != null) {
                WellbeingMetrics(
                    moodRating = dto.moodRating?.let { MoodRating(it) },
                    stressLevel = dto.stressLevel?.let { StressLevel(it) },
                    energyLevel = dto.energyLevel?.let { EnergyLevel(it) },
                    stressTriggers = dto.stressTriggers ?: emptyList(),
                    copingStrategies = dto.copingStrategies ?: emptyList()
                )
            } else null,
            positiveReflections = if (!dto.gratitudeItems.isNullOrEmpty() || !dto.dailyGoals.isNullOrEmpty()) {
                PositiveReflections(
                    gratitudeItems = dto.gratitudeItems ?: emptyList(),
                    dailyGoals = dto.dailyGoals ?: emptyList(),
                    affirmations = dto.affirmations ?: emptyList(),
                    achievements = dto.achievements ?: emptyList()
                )
            } else null,
            locationContext = if (dto.locationSiteName != null || dto.locationCoordinates != null) {
                LocationContext(
                    siteName = dto.locationSiteName,
                    coordinates = dto.locationCoordinates?.let {
                        Coordinates(lat = it.lat, lng = it.lng)
                    }
                )
            } else null,
            privacyScope = PrivacyScope.fromString(dto.privacyScope.name.lowercase()),
            syncMetadata = SyncMetadata(
                mobileId = dto.mobileId ?: UUID.randomUUID().toString(),
                serverId = dto.id,
                version = dto.version ?: 1,
                syncStatus = SyncStatus.valueOf(dto.syncStatus?.name ?: "SYNCED"),
                lastSyncTimestamp = dto.lastSyncTimestamp
            ),
            audit = AuditInfo(
                createdAt = dto.createdAt,
                updatedAt = dto.updatedAt
            )
        )
    }

    /**
     * Domain Entity → DTO (for POST/PUT requests)
     */
    fun toDto(entity: JournalEntry): JournalEntryCreateDTO {
        return JournalEntryCreateDTO(
            title = entity.title.value,
            entryType = EntryTypeEnum.valueOf(entity.entryType.key.uppercase()),
            timestamp = entity.timestamp,
            privacyScope = PrivacyScopeEnum.valueOf(entity.privacyScope::class.simpleName!!.uppercase()),
            moodRating = entity.wellbeingMetrics?.moodRating?.value,
            stressLevel = entity.wellbeingMetrics?.stressLevel?.value,
            energyLevel = entity.wellbeingMetrics?.energyLevel?.value,
            gratitudeItems = entity.positiveReflections?.gratitudeItems,
            dailyGoals = entity.positiveReflections?.dailyGoals,
            affirmations = entity.positiveReflections?.affirmations,
            achievements = entity.positiveReflections?.achievements,
            locationSiteName = entity.locationContext?.siteName,
            locationCoordinates = entity.locationContext?.coordinates?.let {
                CoordinatesDTO(lat = it.lat, lng = it.lng)
            },
            mobileId = entity.syncMetadata.mobileId
        )
    }

    /**
     * Domain Entity → Cache Entity
     */
    fun toCache(entity: JournalEntry): JournalCacheEntity {
        return JournalCacheEntity(
            id = entity.id.value,
            userId = entity.userId.value,
            title = entity.title.value,
            entryType = entity.entryType.key,
            timestamp = entity.timestamp.toEpochMilliseconds(),
            moodRating = entity.wellbeingMetrics?.moodRating?.value,
            stressLevel = entity.wellbeingMetrics?.stressLevel?.value,
            energyLevel = entity.wellbeingMetrics?.energyLevel?.value,
            gratitudeItemsJson = json.encodeToString(entity.positiveReflections?.gratitudeItems ?: emptyList()),
            dailyGoalsJson = json.encodeToString(entity.positiveReflections?.dailyGoals ?: emptyList()),
            affirmationsJson = json.encodeToString(entity.positiveReflections?.affirmations ?: emptyList()),
            achievementsJson = json.encodeToString(entity.positiveReflections?.achievements ?: emptyList()),
            locationSiteName = entity.locationContext?.siteName,
            locationLat = entity.locationContext?.coordinates?.lat,
            locationLng = entity.locationContext?.coordinates?.lng,
            privacyScope = entity.privacyScope::class.simpleName!!.lowercase(),
            mobileId = entity.syncMetadata.mobileId,
            serverId = entity.syncMetadata.serverId,
            version = entity.syncMetadata.version,
            syncStatus = entity.syncMetadata.syncStatus.name,
            lastSyncTimestamp = entity.syncMetadata.lastSyncTimestamp?.toEpochMilliseconds(),
            createdAt = entity.audit.createdAt.toEpochMilliseconds(),
            updatedAt = entity.audit.updatedAt.toEpochMilliseconds(),
            isDraft = entity.syncMetadata.syncStatus == SyncStatus.DRAFT,
            isDeleted = false
        )
    }

    /**
     * Cache Entity → Domain Entity
     */
    fun fromCache(cache: JournalCacheEntity): JournalEntry {
        return JournalEntry(
            id = JournalId(cache.id),
            userId = UserId(cache.userId),
            title = Title(cache.title),
            entryType = EntryType.fromKey(cache.entryType),
            timestamp = Instant.fromEpochMilliseconds(cache.timestamp),
            wellbeingMetrics = if (cache.moodRating != null || cache.stressLevel != null || cache.energyLevel != null) {
                WellbeingMetrics(
                    moodRating = cache.moodRating?.let { MoodRating(it) },
                    stressLevel = cache.stressLevel?.let { StressLevel(it) },
                    energyLevel = cache.energyLevel?.let { EnergyLevel(it) },
                    stressTriggers = emptyList(),
                    copingStrategies = emptyList()
                )
            } else null,
            positiveReflections = PositiveReflections(
                gratitudeItems = json.decodeFromString(cache.gratitudeItemsJson),
                dailyGoals = json.decodeFromString(cache.dailyGoalsJson),
                affirmations = json.decodeFromString(cache.affirmationsJson),
                achievements = json.decodeFromString(cache.achievementsJson)
            ),
            locationContext = if (cache.locationSiteName != null || (cache.locationLat != null && cache.locationLng != null)) {
                LocationContext(
                    siteName = cache.locationSiteName,
                    coordinates = if (cache.locationLat != null && cache.locationLng != null) {
                        Coordinates(lat = cache.locationLat, lng = cache.locationLng)
                    } else null
                )
            } else null,
            privacyScope = PrivacyScope.fromString(cache.privacyScope),
            syncMetadata = SyncMetadata(
                mobileId = cache.mobileId,
                serverId = cache.serverId,
                version = cache.version,
                syncStatus = SyncStatus.valueOf(cache.syncStatus),
                lastSyncTimestamp = cache.lastSyncTimestamp?.let { Instant.fromEpochMilliseconds(it) }
            ),
            audit = AuditInfo(
                createdAt = Instant.fromEpochMilliseconds(cache.createdAt),
                updatedAt = Instant.fromEpochMilliseconds(cache.updatedAt)
            )
        )
    }
}
```

### 4.5 Create Data Sources

**data/src/main/kotlin/com/example/facility/data/source/remote/WellnessRemoteDataSource.kt**:
```kotlin
package com.example.facility.data.source.remote

import com.example.facility.network.api.WellnessApi
import com.example.facility.network.dto.JournalEntryDTO
import com.example.facility.network.dto.JournalEntryCreateDTO
import javax.inject.Inject

class WellnessRemoteDataSource @Inject constructor(
    private val wellnessApi: WellnessApi,
    private val authProvider: AuthProvider
) {
    suspend fun getJournalEntries(
        entryType: String? = null,
        isDraft: Boolean? = null
    ): List<JournalEntryDTO> {
        val response = wellnessApi.wellnessJournalList(
            entryType = entryType,
            isDraft = isDraft,
            authorization = "Bearer ${authProvider.getAccessToken()}"
        )

        if (!response.isSuccessful) {
            throw NetworkException(response.code(), response.message())
        }

        return response.body()?.results ?: emptyList()
    }

    suspend fun createJournalEntry(dto: JournalEntryCreateDTO): JournalEntryDTO {
        val response = wellnessApi.wellnessJournalCreate(
            journalEntryDTO = dto,
            authorization = "Bearer ${authProvider.getAccessToken()}"
        )

        if (!response.isSuccessful) {
            val errorBody = response.errorBody()?.string()
            throw NetworkException(response.code(), errorBody ?: response.message())
        }

        return response.body() ?: throw NetworkException(500, "Empty response body")
    }

    suspend fun updateJournalEntry(id: String, dto: JournalEntryUpdateDTO): JournalEntryDTO {
        val response = wellnessApi.wellnessJournalPartialUpdate(
            id = id,
            journalEntryDTO = dto,
            authorization = "Bearer ${authProvider.getAccessToken()}"
        )

        if (!response.isSuccessful) {
            throw NetworkException(response.code(), response.message())
        }

        return response.body() ?: throw NetworkException(500, "Empty response body")
    }

    suspend fun deleteJournalEntry(id: String) {
        val response = wellnessApi.wellnessJournalDestroy(
            id = id,
            authorization = "Bearer ${authProvider.getAccessToken()}"
        )

        if (!response.isSuccessful) {
            throw NetworkException(response.code(), response.message())
        }
    }
}

class NetworkException(val code: Int, override val message: String) : Exception(message)
```

**data/src/main/kotlin/com/example/facility/data/source/local/WellnessLocalDataSource.kt**:
```kotlin
package com.example.facility.data.source.local

import com.example.facility.database.dao.JournalDao
import com.example.facility.database.dao.PendingOperationsDao
import com.example.facility.database.entity.JournalCacheEntity
import com.example.facility.database.entity.PendingOperationEntity
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

class WellnessLocalDataSource @Inject constructor(
    private val journalDao: JournalDao,
    private val pendingOperationsDao: PendingOperationsDao
) {
    fun getJournalEntriesFlow(): Flow<List<JournalCacheEntity>> {
        return journalDao.getAllFlow()
    }

    suspend fun getJournalEntries(
        entryType: String? = null,
        isDraft: Boolean? = null
    ): List<JournalCacheEntity> {
        return when {
            entryType != null && isDraft != null -> {
                journalDao.getAll().filter { it.entryType == entryType && it.isDraft == isDraft }
            }
            entryType != null -> journalDao.getByType(entryType)
            isDraft != null -> journalDao.getByDraft(isDraft)
            else -> journalDao.getAll()
        }
    }

    suspend fun getJournalEntry(id: String): JournalCacheEntity? {
        return journalDao.getById(id)
    }

    suspend fun insertJournalEntry(entity: JournalCacheEntity) {
        journalDao.insert(entity)
    }

    suspend fun insertJournalEntries(entities: List<JournalCacheEntity>) {
        journalDao.insertAll(entities)
    }

    suspend fun updateJournalEntry(entity: JournalCacheEntity) {
        journalDao.update(entity)
    }

    suspend fun deleteJournalEntry(id: String) {
        journalDao.softDelete(id, System.currentTimeMillis())
    }

    suspend fun addPendingOperation(
        operationType: String,
        entityType: String,
        entityId: String,
        payload: String
    ) {
        pendingOperationsDao.insert(
            PendingOperationEntity(
                operationType = operationType,
                entityType = entityType,
                entityId = entityId,
                payload = payload,
                createdAt = System.currentTimeMillis()
            )
        )
    }

    suspend fun removePendingOperation(entityId: String) {
        pendingOperationsDao.deleteByEntityId(entityId)
    }

    suspend fun getPendingOperations(): List<PendingOperationEntity> {
        return pendingOperationsDao.getAll()
    }

    fun getPendingOperationsFlow(): Flow<List<PendingOperationEntity>> {
        return pendingOperationsDao.getAllFlow()
    }

    suspend fun updateSyncStatus(id: String, status: String) {
        journalDao.updateSyncStatus(id, status, System.currentTimeMillis())
    }
}
```

### 4.6 Implement Repository

**data/src/main/kotlin/com/example/facility/data/repository/WellnessRepositoryImpl.kt**:
```kotlin
package com.example.facility.data.repository

import com.example.facility.common.result.Result
import com.example.facility.data.mapper.JournalMapper
import com.example.facility.data.source.local.WellnessLocalDataSource
import com.example.facility.data.source.remote.WellnessRemoteDataSource
import com.example.facility.domain.model.wellness.*
import com.example.facility.domain.repository.WellnessRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.datetime.Clock
import kotlinx.datetime.Instant
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID
import javax.inject.Inject

class WellnessRepositoryImpl @Inject constructor(
    private val remoteDataSource: WellnessRemoteDataSource,
    private val localDataSource: WellnessLocalDataSource,
    private val mapper: JournalMapper,
    private val json: Json
) : WellnessRepository {

    override fun getJournalEntries(
        entryType: EntryType?,
        isDraft: Boolean?,
        forceRefresh: Boolean
    ): Flow<Result<List<JournalEntry>>> = flow {
        // 1. Emit loading
        emit(Result.Loading())

        // 2. Emit cached data immediately (if exists and not force refresh)
        if (!forceRefresh) {
            try {
                val cachedEntries = localDataSource.getJournalEntries(
                    entryType = entryType?.key,
                    isDraft = isDraft
                )
                if (cachedEntries.isNotEmpty()) {
                    val domainEntries = cachedEntries.map { mapper.fromCache(it) }
                    emit(Result.Success(domainEntries))
                }
            } catch (e: Exception) {
                // Cache read failed - continue to network
            }
        }

        // 3. Fetch from network
        try {
            val dtos = remoteDataSource.getJournalEntries(
                entryType = entryType?.key,
                isDraft = isDraft
            )

            // 4. Save to cache
            val cacheEntities = dtos.map { dto ->
                val domain = mapper.toDomain(dto)
                mapper.toCache(domain)
            }
            localDataSource.insertJournalEntries(cacheEntities)

            // 5. Emit fresh data
            val domainEntries = dtos.map { mapper.toDomain(it) }
            emit(Result.Success(domainEntries))

        } catch (e: Exception) {
            // Network failed - emit error only if we didn't already emit cache
            if (forceRefresh) {
                emit(Result.Error(e))
            }
        }
    }

    override fun getJournalEntry(id: JournalId): Flow<Result<JournalEntry>> = flow {
        emit(Result.Loading())

        // Check cache first
        val cached = localDataSource.getJournalEntry(id.value)
        if (cached != null) {
            emit(Result.Success(mapper.fromCache(cached)))
        }

        // Fetch from network
        try {
            val dto = remoteDataSource.getJournalEntry(id.value)
            val domain = mapper.toDomain(dto)

            // Update cache
            localDataSource.insertJournalEntry(mapper.toCache(domain))

            emit(Result.Success(domain))
        } catch (e: Exception) {
            if (cached == null) {
                emit(Result.Error(e))
            }
        }
    }

    override fun createJournalEntry(
        title: Title,
        entryType: EntryType,
        timestamp: Instant,
        privacyScope: PrivacyScope,
        wellbeingMetrics: WellbeingMetrics?,
        positiveReflections: PositiveReflections?,
        locationContext: LocationContext?
    ): Flow<Result<JournalEntry>> = flow {
        // 1. Generate mobile_id
        val mobileId = UUID.randomUUID().toString()
        val now = Clock.System.now()

        // 2. Create domain entity
        val entry = JournalEntry(
            id = JournalId("temp-${mobileId}"),  // Temporary ID
            userId = UserId(0),  // Will be set by server
            title = title,
            entryType = entryType,
            timestamp = timestamp,
            wellbeingMetrics = wellbeingMetrics,
            positiveReflections = positiveReflections,
            locationContext = locationContext,
            privacyScope = privacyScope,
            syncMetadata = SyncMetadata(
                mobileId = mobileId,
                serverId = null,
                version = 1,
                syncStatus = SyncStatus.PENDING_SYNC,
                lastSyncTimestamp = null
            ),
            audit = AuditInfo(
                createdAt = now,
                updatedAt = now
            )
        )

        // 3. Save to local cache
        localDataSource.insertJournalEntry(mapper.toCache(entry))

        // 4. Add to pending operations queue
        val dto = mapper.toDto(entry)
        localDataSource.addPendingOperation(
            operationType = "CREATE",
            entityType = "JOURNAL",
            entityId = mobileId,
            payload = json.encodeToString(dto)
        )

        // 5. Emit success immediately (offline-first)
        emit(Result.Success(entry))

        // 6. Attempt immediate sync (if online)
        try {
            val responseDto = remoteDataSource.createJournalEntry(dto)
            val syncedEntry = mapper.toDomain(responseDto)

            // Update local cache with server ID
            localDataSource.insertJournalEntry(mapper.toCache(syncedEntry))

            // Remove from pending operations
            localDataSource.removePendingOperation(mobileId)

            // Emit synced entry
            emit(Result.Success(syncedEntry))

        } catch (e: Exception) {
            // Network error - stays in pending queue for WorkManager
        }
    }

    override fun updateJournalEntry(
        id: JournalId,
        title: Title?,
        wellbeingMetrics: WellbeingMetrics?,
        positiveReflections: PositiveReflections?
    ): Flow<Result<JournalEntry>> = flow {
        // Implementation similar to create
        // 1. Update local cache
        // 2. Add to pending operations
        // 3. Emit success
        // 4. Attempt sync
    }

    override fun deleteJournalEntry(id: JournalId): Flow<Result<Unit>> = flow {
        // Soft delete
        localDataSource.deleteJournalEntry(id.value)

        // Add to pending operations
        localDataSource.addPendingOperation(
            operationType = "DELETE",
            entityType = "JOURNAL",
            entityId = id.value,
            payload = "{\"id\": \"${id.value}\"}"
        )

        emit(Result.Success(Unit))

        // Attempt sync
        try {
            remoteDataSource.deleteJournalEntry(id.value)
            localDataSource.removePendingOperation(id.value)
        } catch (e: Exception) {
            // Network error - stays in pending queue
        }
    }
}
```

### 4.7 Create Network Module (Hilt)

**network/src/main/kotlin/com/example/facility/network/di/NetworkModule.kt**:
```kotlin
package com.example.facility.network.di

import com.example.facility.network.JsonConfig
import com.example.facility.network.api.WellnessApi
import com.example.facility.network.interceptor.AuthInterceptor
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideJson() = JsonConfig.json

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            })
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(
        okHttpClient: OkHttpClient,
        json: kotlinx.serialization.json.Json
    ): Retrofit {
        return Retrofit.Builder()
            .baseUrl("https://api.example.com/")  // Use BuildConfig.API_BASE_URL in production
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    @Provides
    @Singleton
    fun provideWellnessApi(retrofit: Retrofit): WellnessApi {
        return retrofit.create(WellnessApi::class.java)
    }
}
```

### Phase 4 Deliverables

- [x] Room entities created
- [x] Room DAOs implemented
- [x] Room database configured
- [x] Mappers implemented (DTO ↔ Entity ↔ Cache)
- [x] Remote data source implemented
- [x] Local data source implemented
- [x] Repository implementation completed
- [x] Hilt modules created
- [x] Integration tests passing

**Time Check**: Should complete in 1.5-2 weeks

---

## Phase 5: Presentation Layer (Week 7-10)

### 5.1 Create ViewModel

**app/src/main/kotlin/com/example/facility/ui/wellness/journal/JournalListViewModel.kt**:
```kotlin
package com.example.facility.ui.wellness.journal

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.facility.common.result.Result
import com.example.facility.domain.model.wellness.JournalEntry
import com.example.facility.domain.usecase.wellness.GetJournalEntriesUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class JournalListViewModel @Inject constructor(
    private val getJournalEntriesUseCase: GetJournalEntriesUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow<JournalListUiState>(JournalListUiState.Loading)
    val uiState: StateFlow<JournalListUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<JournalListEvent>()
    val events: SharedFlow<JournalListEvent> = _events.asSharedFlow()

    init {
        loadJournalEntries()
    }

    fun onRefresh() {
        loadJournalEntries(forceRefresh = true)
    }

    fun onEntryTypeFilter(entryType: String?) {
        loadJournalEntries(entryType = entryType)
    }

    fun onEntryClick(entryId: String) {
        viewModelScope.launch {
            _events.emit(JournalListEvent.NavigateToDetail(entryId))
        }
    }

    fun onCreateClick() {
        viewModelScope.launch {
            _events.emit(JournalListEvent.NavigateToCreate)
        }
    }

    private fun loadJournalEntries(
        entryType: String? = null,
        forceRefresh: Boolean = false
    ) {
        viewModelScope.launch {
            getJournalEntriesUseCase(entryType = entryType, forceRefresh = forceRefresh)
                .collect { result ->
                    _uiState.value = when (result) {
                        is Result.Success -> JournalListUiState.Success(result.data)
                        is Result.Error -> JournalListUiState.Error(
                            result.error.message ?: "Unknown error"
                        )
                        is Result.Loading -> JournalListUiState.Loading
                    }
                }
        }
    }
}

sealed class JournalListUiState {
    object Loading : JournalListUiState()
    data class Success(val entries: List<JournalEntry>) : JournalListUiState()
    data class Error(val message: String) : JournalListUiState()
}

sealed class JournalListEvent {
    data class NavigateToDetail(val entryId: String) : JournalListEvent()
    object NavigateToCreate : JournalListEvent()
}
```

### 5.2 Create Compose UI

**app/src/main/kotlin/com/example/facility/ui/wellness/journal/JournalListScreen.kt**:
```kotlin
package com.example.facility.ui.wellness.journal

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.example.facility.domain.model.wellness.JournalEntry
import com.example.facility.domain.model.wellness.SyncStatus
import kotlinx.coroutines.flow.collectLatest

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JournalListScreen(
    onEntryClick: (String) -> Unit,
    onCreateClick: () -> Unit,
    viewModel: JournalListViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    // Handle events
    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                is JournalListEvent.NavigateToDetail -> onEntryClick(event.entryId)
                is JournalListEvent.NavigateToCreate -> onCreateClick()
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Journal") },
                actions = {
                    IconButton(onClick = { viewModel.onRefresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { viewModel.onCreateClick() }) {
                Icon(Icons.Default.Add, contentDescription = "Create Entry")
            }
        }
    ) { padding ->
        when (val state = uiState) {
            is JournalListUiState.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            }

            is JournalListUiState.Success -> {
                if (state.entries.isEmpty()) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                "No journal entries yet",
                                style = MaterialTheme.typography.bodyLarge
                            )
                            Spacer(Modifier.height(16.dp))
                            Button(onClick = { viewModel.onCreateClick() }) {
                                Text("Create Your First Entry")
                            }
                        }
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        contentPadding = PaddingValues(16.dp)
                    ) {
                        items(state.entries, key = { it.id.value }) { entry ->
                            JournalEntryCard(
                                entry = entry,
                                onClick = { viewModel.onEntryClick(entry.id.value) }
                            )
                        }
                    }
                }
            }

            is JournalListUiState.Error -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text(
                            state.message,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.error
                        )
                        Spacer(Modifier.height(16.dp))
                        Button(onClick = { viewModel.onRefresh() }) {
                            Text("Retry")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun JournalEntryCard(
    entry: JournalEntry,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Title
            Text(
                text = entry.title.value,
                style = MaterialTheme.typography.titleMedium
            )

            Spacer(Modifier.height(4.dp))

            // Entry type
            Text(
                text = entry.entryType.key.replace("_", " ").capitalize(),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            // Wellbeing metrics
            entry.wellbeingMetrics?.let { metrics ->
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    metrics.moodRating?.let {
                        Chip(text = "Mood: ${it.value}/10")
                    }
                    metrics.stressLevel?.let {
                        Chip(text = "Stress: ${it.value}/5")
                    }
                    metrics.energyLevel?.let {
                        Chip(text = "Energy: ${it.value}/10")
                    }
                }
            }

            // Gratitude items
            entry.positiveReflections?.gratitudeItems?.takeIf { it.isNotEmpty() }?.let { items ->
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "Grateful for: ${items.take(2).joinToString(", ")}${if (items.size > 2) "..." else ""}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.tertiary
                )
            }

            // Sync status
            if (entry.syncMetadata.syncStatus == SyncStatus.PENDING_SYNC) {
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "Syncing...",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
fun Chip(text: String) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.secondaryContainer,
        tonalElevation = 1.dp
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall
        )
    }
}
```

### 5.3 Create Navigation

**app/src/main/kotlin/com/example/facility/navigation/NavGraph.kt**:
```kotlin
package com.example.facility.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.example.facility.ui.wellness.journal.JournalListScreen

sealed class Screen(val route: String) {
    object JournalList : Screen("journal_list")
    object JournalDetail : Screen("journal_detail/{entryId}") {
        fun createRoute(entryId: String) = "journal_detail/$entryId"
    }
    object JournalCreate : Screen("journal_create")
}

@Composable
fun NavGraph(
    navController: NavHostController = rememberNavController()
) {
    NavHost(
        navController = navController,
        startDestination = Screen.JournalList.route
    ) {
        composable(Screen.JournalList.route) {
            JournalListScreen(
                onEntryClick = { entryId ->
                    navController.navigate(Screen.JournalDetail.createRoute(entryId))
                },
                onCreateClick = {
                    navController.navigate(Screen.JournalCreate.route)
                }
            )
        }

        composable(Screen.JournalDetail.route) {
            // JournalDetailScreen (to be implemented)
        }

        composable(Screen.JournalCreate.route) {
            // JournalCreateScreen (to be implemented)
        }
    }
}
```

### Phase 5 Deliverables

- [x] ViewModels created with state management
- [x] Compose UI screens implemented
- [x] Navigation setup
- [x] UI components (cards, chips, etc.)
- [x] Theme and Material3 configuration
- [x] UI tests written
- [x] Accessibility tested

**Time Check**: Should complete in 3-4 weeks

---

## Phase 6: Background Sync (Week 11)

### 6.1 Create Sync Worker

**app/src/main/kotlin/com/example/facility/worker/SyncWorker.kt**:
```kotlin
package com.example.facility.worker

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.*
import com.example.facility.data.source.local.WellnessLocalDataSource
import com.example.facility.data.source.remote.WellnessRemoteDataSource
import com.example.facility.data.mapper.JournalMapper
import com.example.facility.network.dto.JournalEntryCreateDTO
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val localDataSource: WellnessLocalDataSource,
    private val remoteDataSource: WellnessRemoteDataSource,
    private val mapper: JournalMapper,
    private val json: Json
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            // 1. Fetch pending operations
            val pendingOps = localDataSource.getPendingOperations()

            if (pendingOps.isEmpty()) {
                return@withContext Result.success()
            }

            var successCount = 0
            var failureCount = 0

            // 2. Process each operation
            for (op in pendingOps) {
                try {
                    when (op.operationType) {
                        "CREATE" -> {
                            val dto = json.decodeFromString<JournalEntryCreateDTO>(op.payload)
                            val response = remoteDataSource.createJournalEntry(dto)

                            // Update local cache with server ID
                            val domain = mapper.toDomain(response)
                            localDataSource.insertJournalEntry(mapper.toCache(domain))

                            // Remove from queue
                            localDataSource.removePendingOperation(op.entityId)
                            successCount++
                        }

                        "UPDATE" -> {
                            // Handle update
                        }

                        "DELETE" -> {
                            remoteDataSource.deleteJournalEntry(op.entityId)
                            localDataSource.removePendingOperation(op.entityId)
                            successCount++
                        }
                    }

                } catch (e: Exception) {
                    // Increment retry count
                    if (op.retryCount >= MAX_RETRIES) {
                        // Max retries exceeded - mark as error
                        localDataSource.updateSyncStatus(op.entityId, "SYNC_ERROR")
                        localDataSource.removePendingOperation(op.entityId)
                    }
                    failureCount++
                }
            }

            // Return success if at least some operations succeeded
            if (successCount > 0 || failureCount == 0) {
                Result.success(
                    Data.Builder()
                        .putInt("success_count", successCount)
                        .putInt("failure_count", failureCount)
                        .build()
                )
            } else {
                Result.retry()
            }

        } catch (e: Exception) {
            Result.retry()
        }
    }

    companion object {
        const val MAX_RETRIES = 3
        const val WORK_NAME = "periodic_sync"

        fun enqueue(workManager: WorkManager) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .setRequiresBatteryNotLow(true)
                .build()

            val syncRequest = PeriodicWorkRequestBuilder<SyncWorker>(
                15, TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    1, TimeUnit.MINUTES
                )
                .build()

            workManager.enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                syncRequest
            )
        }
    }
}
```

### 6.2 Initialize WorkManager

**app/src/main/kotlin/com/example/facility/FacilityApplication.kt**:
```kotlin
package com.example.facility

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import androidx.work.WorkManager
import com.example.facility.worker.SyncWorker
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class FacilityApplication : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override fun onCreate() {
        super.onCreate()

        // Initialize WorkManager with Hilt
        val workManager = WorkManager.getInstance(this)

        // Enqueue periodic sync
        SyncWorker.enqueue(workManager)
    }

    override fun getWorkManagerConfiguration(): Configuration {
        return Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()
    }
}
```

### Phase 6 Deliverables

- [x] SyncWorker implemented with retry logic
- [x] WorkManager configured with Hilt
- [x] Periodic sync scheduled (15 min intervals)
- [x] Network state monitoring
- [x] Exponential backoff implemented
- [x] Sync tested with offline scenarios

**Time Check**: Should complete in 1 week

---

## Phase 7: Testing (Week 12)

### 7.1 Repository Integration Tests

**data/src/androidTest/kotlin/com/example/facility/data/WellnessRepositoryTest.kt**:
```kotlin
package com.example.facility.data

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.example.facility.common.result.Result
import com.example.facility.database.FacilityDatabase
import com.example.facility.data.repository.WellnessRepositoryImpl
import com.example.facility.domain.model.wellness.*
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import kotlinx.datetime.Clock
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import javax.inject.Inject
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

@HiltAndroidTest
class WellnessRepositoryTest {

    @get:Rule
    var hiltRule = HiltAndroidRule(this)

    @Inject
    lateinit var repository: WellnessRepositoryImpl

    private lateinit var database: FacilityDatabase

    @Before
    fun setup() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            FacilityDatabase::class.java
        ).build()

        hiltRule.inject()
    }

    @After
    fun teardown() {
        database.close()
    }

    @Test
    fun createJournalEntry_savesToLocalDb() = runTest {
        // Given
        val title = Title("Test Entry")
        val entryType = EntryType.MoodCheckIn
        val timestamp = Clock.System.now()
        val privacyScope = PrivacyScope.Private

        // When
        val result = repository.createJournalEntry(
            title = title,
            entryType = entryType,
            timestamp = timestamp,
            privacyScope = privacyScope
        ).first()

        // Then
        assertTrue(result is Result.Success)
        val entry = (result as Result.Success).data

        assertNotNull(entry.syncMetadata.mobileId)
        assertEquals(SyncStatus.PENDING_SYNC, entry.syncMetadata.syncStatus)

        // Verify local DB
        val cached = database.journalDao().getByMobileId(entry.syncMetadata.mobileId)
        assertNotNull(cached)
        assertEquals(title.value, cached.title)
    }

    @Test
    fun createJournalEntry_addsToSyncQueue() = runTest {
        // Given
        val title = Title("Test Entry")
        val entryType = EntryType.MoodCheckIn
        val timestamp = Clock.System.now()
        val privacyScope = PrivacyScope.Private

        // When
        repository.createJournalEntry(
            title = title,
            entryType = entryType,
            timestamp = timestamp,
            privacyScope = privacyScope
        ).first()

        // Then
        val pendingOps = database.pendingOperationsDao().getAll()
        assertEquals(1, pendingOps.size)
        assertEquals("CREATE", pendingOps[0].operationType)
        assertEquals("JOURNAL", pendingOps[0].entityType)
    }
}
```

### 7.2 UI Tests

**app/src/androidTest/kotlin/com/example/facility/ui/JournalListScreenTest.kt**:
```kotlin
package com.example.facility.ui

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import com.example.facility.MainActivity
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Before
import org.junit.Rule
import org.junit.Test

@HiltAndroidTest
class JournalListScreenTest {

    @get:Rule(order = 0)
    var hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Before
    fun setup() {
        hiltRule.inject()
    }

    @Test
    fun journalListScreen_displaysEntries() {
        composeTestRule.apply {
            onNodeWithText("My Journal").assertExists()
            onNodeWithContentDescription("Create Entry").assertExists()
        }
    }

    @Test
    fun clickingFab_navigatesToCreateScreen() {
        composeTestRule.apply {
            onNodeWithContentDescription("Create Entry").performClick()
            // Verify navigation
        }
    }

    @Test
    fun clickingRefresh_reloadsData() {
        composeTestRule.apply {
            onNodeWithContentDescription("Refresh").performClick()
            onNodeWithTag("loading").assertExists()
        }
    }
}
```

### Phase 7 Deliverables

- [x] Repository integration tests (80%+ coverage)
- [x] DAO tests
- [x] Mapper tests
- [x] ViewModel tests
- [x] UI tests (Compose)
- [x] End-to-end tests
- [x] All tests passing

**Time Check**: Should complete in 1 week

---

## Phase 8: Security & Polish (Week 13-14)

### 8.1 Implement Secure Token Storage

**app/src/main/kotlin/com/example/facility/security/SecureTokenStorage.kt**:
```kotlin
package com.example.facility.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecureTokenStorage @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val encryptedPrefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveAccessToken(token: String) {
        encryptedPrefs.edit().putString(KEY_ACCESS_TOKEN, token).apply()
    }

    fun getAccessToken(): String? {
        return encryptedPrefs.getString(KEY_ACCESS_TOKEN, null)
    }

    fun saveRefreshToken(token: String) {
        encryptedPrefs.edit().putString(KEY_REFRESH_TOKEN, token).apply()
    }

    fun getRefreshToken(): String? {
        return encryptedPrefs.getString(KEY_REFRESH_TOKEN, null)
    }

    fun saveDeviceId(deviceId: String) {
        encryptedPrefs.edit().putString(KEY_DEVICE_ID, deviceId).apply()
    }

    fun getDeviceId(): String? {
        return encryptedPrefs.getString(KEY_DEVICE_ID, null)
    }

    fun clearTokens() {
        encryptedPrefs.edit()
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .apply()
    }

    companion object {
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_DEVICE_ID = "device_id"
    }
}
```

### 8.2 Configure ProGuard

**app/proguard-rules.pro**:
```proguard
# Keep all models/DTOs for kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt

-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Keep DTOs
-keep class com.example.facility.network.dto.** { *; }

# Retrofit
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keepattributes AnnotationDefault
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Room
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-dontwarn androidx.room.paging.**
```

### 8.3 Add Certificate Pinning (Production)

**Update network_security_config.xml**:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Production with certificate pinning -->
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2026-10-30">
            <!-- Get actual hashes from your SSL certificate -->
            <pin digest="SHA-256">AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</pin>
            <pin digest="SHA-256">BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

**Get certificate hashes**:
```bash
# Extract certificate from server
openssl s_client -servername api.example.com -connect api.example.com:443 < /dev/null | openssl x509 -pubkey -noout | openssl rsa -pubin -outform der | openssl dgst -sha256 -binary | openssl enc -base64
```

### Phase 8 Deliverables

- [x] Secure token storage (EncryptedSharedPreferences)
- [x] Certificate pinning configured
- [x] ProGuard rules added
- [x] App icons and branding
- [x] Splash screen
- [x] Error tracking (Firebase Crashlytics - optional)
- [x] Analytics (Firebase Analytics - optional)
- [x] Performance profiling
- [x] Memory leak testing
- [x] Final QA testing

**Time Check**: Should complete in 1-2 weeks

---

## Summary: Complete Implementation Timeline

| Phase | Duration | Key Deliverables | Dependencies |
|-------|----------|------------------|--------------|
| **Phase 0** | 1-2 days | Prerequisites, environment setup | None |
| **Phase 1** | 1 week | Project structure, modules, build configs | Phase 0 |
| **Phase 2** | 2-3 days | DTO generation, JSON config | Phase 1, openapi.yaml from backend |
| **Phase 3** | 1-2 weeks | Domain entities, use cases, tests | Phase 2 |
| **Phase 4** | 1.5-2 weeks | Room DB, mappers, repositories | Phase 3 |
| **Phase 5** | 3-4 weeks | ViewModels, Compose UI, navigation | Phase 4 |
| **Phase 6** | 1 week | Background sync, WorkManager | Phase 5 |
| **Phase 7** | 1 week | Integration tests, UI tests | Phase 6 |
| **Phase 8** | 1-2 weeks | Security, polish, final QA | Phase 7 |
| **TOTAL** | **12-14 weeks** | Production-ready Android app | - |

---

## Critical Success Factors

### Must-Haves Each Phase

1. **Code Review**: All code reviewed before merging
2. **Tests Passing**: 80%+ coverage (unit), key workflows (integration)
3. **Documentation**: Update docs if API changes
4. **Demo**: Show working features to stakeholders
5. **No Blockers**: Resolve issues before moving to next phase

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API changes during development | Weekly sync with backend team |
| Performance issues | Profile each phase, optimize early |
| Security vulnerabilities | Security review after Phase 8 |
| Test failures | Fix immediately, don't accumulate |
| Scope creep | Stick to defined phases, defer extras |

---

## Verification Checklist (End of Project)

### Functional Requirements
- [ ] User can create journal entries offline
- [ ] Entries sync when online
- [ ] Conflicts resolve correctly
- [ ] Pagination works smoothly
- [ ] Search and filters work
- [ ] File uploads work
- [ ] WebSocket real-time sync works
- [ ] All error scenarios handled gracefully

### Non-Functional Requirements
- [ ] App starts in < 3 seconds
- [ ] UI responds in < 100ms
- [ ] No memory leaks
- [ ] Battery usage acceptable
- [ ] Works on Android 5.0+ (API 21+)
- [ ] Accessibility (TalkBack) works
- [ ] Offline mode fully functional
- [ ] Network failures handled

### Security Requirements
- [ ] Tokens stored in KeyStore
- [ ] Certificate pinning enabled (production)
- [ ] No sensitive data in logs
- [ ] ProGuard enabled (release)
- [ ] No hardcoded secrets
- [ ] SSL/TLS only (no cleartext)

### Code Quality
- [ ] All tests passing (unit, integration, UI)
- [ ] Test coverage > 80% (domain, data layers)
- [ ] No lint warnings
- [ ] No memory leaks (LeakCanary)
- [ ] Code reviewed by 2+ developers
- [ ] Documentation updated

---

## Post-Launch (Ongoing)

### Maintenance

**Weekly**:
- Sync with backend for API changes
- Regenerate DTOs if needed
- Update domain contracts

**Monthly**:
- Dependency updates
- Security patching
- Performance monitoring review

**Quarterly**:
- Major refactoring (if needed)
- Architecture review
- Documentation review

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Target**: Android developers implementing Kotlin app
**Estimated Total Effort**: 12-14 weeks with 2-3 developers