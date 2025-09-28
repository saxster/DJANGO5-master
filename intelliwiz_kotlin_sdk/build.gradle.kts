plugins {
    id("com.android.library")
    kotlin("android") version "1.9.22"
    kotlin("plugin.serialization") version "1.9.22"
    id("maven-publish")
}

android {
    namespace = "com.intelliwiz.mobile.telemetry"
    compileSdk = 34

    defaultConfig {
        minSdk = 24
        targetSdk = 34

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        consumerProguardFiles("consumer-rules.pro")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        jvmTarget = "1.8"
    }

    buildFeatures {
        compose = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    // Kotlin Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Ktor for WebSocket and HTTP client (reuse existing patterns)
    implementation("io.ktor:ktor-client-core:2.3.8")
    implementation("io.ktor:ktor-client-android:2.3.8")
    implementation("io.ktor:ktor-client-websockets:2.3.8")
    implementation("io.ktor:ktor-client-logging:2.3.8")
    implementation("io.ktor:ktor-client-content-negotiation:2.3.8")
    implementation("io.ktor:ktor-serialization-kotlinx-json:2.3.8")

    // JSON serialization (align with existing)
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")

    // Android dependencies
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-process:2.7.0")
    implementation("androidx.work:work-runtime-ktx:2.9.0")

    // Jetpack Compose (for performance tracking)
    implementation("androidx.compose.ui:ui:1.5.8")
    implementation("androidx.compose.runtime:runtime:1.5.8")
    implementation("androidx.compose.foundation:foundation:1.5.8")

    // OkHttp for network interception
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Room for local storage (optional caching)
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")

    // Logging (align with existing)
    implementation("ch.qos.logback:logback-android:3.0.0")
    implementation("io.github.microutils:kotlin-logging:3.0.5")

    // Testing
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
    testImplementation("io.mockk:mockk:1.13.8")

    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4:1.5.8")

    // Paparazzi for visual regression testing
    testImplementation("app.cash.paparazzi:paparazzi:1.3.2")

    // Macrobenchmark support
    androidTestImplementation("androidx.benchmark:benchmark-macro-junit4:1.2.2")
}

// Publishing configuration for distributing SDK
publishing {
    publications {
        create<MavenPublication>("release") {
            from(components["release"])

            groupId = "com.intelliwiz.mobile"
            artifactId = "telemetry-sdk"
            version = "1.0.0-alpha01"
        }
    }
}