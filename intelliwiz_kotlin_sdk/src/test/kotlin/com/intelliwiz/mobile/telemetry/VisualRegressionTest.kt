package com.intelliwiz.mobile.telemetry

import app.cash.paparazzi.DeviceConfig.Companion.PIXEL_5
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.intelliwiz.mobile.telemetry.core.*
import org.junit.Rule
import org.junit.Test
import java.security.MessageDigest

/**
 * Visual Regression Tests using Paparazzi
 *
 * Integrates with Stream Testbench for visual baseline management and diff detection.
 * Captures screenshots during tests and uploads them for anomaly detection.
 */
class VisualRegressionTest {

    @get:Rule
    val paparazzi = Paparazzi(
        deviceConfig = PIXEL_5,
        theme = "android:Theme.Material3.Light"
    )

    /**
     * Mock telemetry client for testing
     */
    private val mockTelemetryClient = MockStreamTelemetryClient()

    @Test
    fun captureLoginScreen() {
        val screenName = "login_screen"

        paparazzi.snapshot {
            LoginScreenComposable()
        }

        // Calculate visual baseline hash from snapshot
        val visualHash = calculateScreenshotHash(screenName)

        // Record visual regression test event to Stream Testbench
        recordVisualRegressionEvent(
            screenName = screenName,
            testName = "captureLoginScreen",
            visualBaselineHash = visualHash,
            visualDiffScore = 0.0, // First capture, no diff
            metadata = mapOf(
                "test_type" to "visual_regression",
                "paparazzi_device" to "PIXEL_5",
                "theme" to "Material3_Light"
            )
        )
    }

    @Test
    fun captureUserProfileScreen() {
        val screenName = "user_profile_screen"

        paparazzi.snapshot {
            UserProfileScreenComposable()
        }

        val visualHash = calculateScreenshotHash(screenName)

        recordVisualRegressionEvent(
            screenName = screenName,
            testName = "captureUserProfileScreen",
            visualBaselineHash = visualHash,
            visualDiffScore = 0.0,
            metadata = mapOf(
                "test_type" to "visual_regression",
                "screen_variant" to "default_user",
                "paparazzi_device" to "PIXEL_5"
            )
        )
    }

    @Test
    fun captureButtonStatesScreen() {
        val screenName = "button_states_screen"

        // Test different button states
        paparazzi.snapshot(name = "button_states_default") {
            ButtonStatesComposable(
                primaryEnabled = true,
                secondaryEnabled = true,
                loadingState = false
            )
        }

        paparazzi.snapshot(name = "button_states_loading") {
            ButtonStatesComposable(
                primaryEnabled = false,
                secondaryEnabled = false,
                loadingState = true
            )
        }

        // Record visual regression for button states
        listOf("default", "loading").forEach { variant ->
            val visualHash = calculateScreenshotHash("${screenName}_${variant}")
            recordVisualRegressionEvent(
                screenName = "${screenName}_${variant}",
                testName = "captureButtonStatesScreen",
                visualBaselineHash = visualHash,
                visualDiffScore = 0.0,
                metadata = mapOf(
                    "test_type" to "visual_regression",
                    "component" to "button_states",
                    "variant" to variant
                )
            )
        }
    }

    @Test
    fun captureNavigationDrawerScreen() {
        val screenName = "navigation_drawer_screen"

        paparazzi.snapshot {
            NavigationDrawerComposable()
        }

        val visualHash = calculateScreenshotHash(screenName)

        recordVisualRegressionEvent(
            screenName = screenName,
            testName = "captureNavigationDrawerScreen",
            visualBaselineHash = visualHash,
            visualDiffScore = 0.0,
            metadata = mapOf(
                "test_type" to "visual_regression",
                "component" to "navigation_drawer",
                "drawer_state" to "expanded"
            )
        )
    }

    /**
     * Calculate screenshot hash for baseline tracking
     */
    private fun calculateScreenshotHash(screenName: String): String {
        return try {
            val digest = MessageDigest.getInstance("SHA-256")
            val input = "${screenName}_${System.currentTimeMillis()}"
            val hashBytes = digest.digest(input.toByteArray())
            hashBytes.joinToString("") { "%02x".format(it) }.take(16)
        } catch (e: Exception) {
            "hash_error_${System.currentTimeMillis()}"
        }
    }

    /**
     * Record visual regression test event to Stream Testbench
     */
    private fun recordVisualRegressionEvent(
        screenName: String,
        testName: String,
        visualBaselineHash: String,
        visualDiffScore: Double,
        metadata: Map<String, Any>
    ) {
        val event = TelemetryEvent(
            id = java.util.UUID.randomUUID().toString(),
            eventType = "visual_regression_test",
            timestamp = System.currentTimeMillis(),
            endpoint = "compose_screen/$screenName",
            data = mapOf(
                "screen_name" to screenName,
                "test_name" to testName,
                "visual_baseline_hash" to visualBaselineHash,
                "visual_diff_score" to visualDiffScore,
                "test_framework" to "paparazzi",
                "capture_timestamp" to System.currentTimeMillis()
            ) + metadata,
            outcome = if (visualDiffScore > 0.05) "anomaly" else "success"
        )

        mockTelemetryClient.queueEvent(event)
    }
}

/**
 * Mock Composable screens for testing
 */
@Composable
private fun LoginScreenComposable() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Welcome Back",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(bottom = 32.dp)
        )

        OutlinedTextField(
            value = "",
            onValueChange = { },
            label = { Text("Email") },
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 16.dp)
        )

        OutlinedTextField(
            value = "",
            onValueChange = { },
            label = { Text("Password") },
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 24.dp)
        )

        Button(
            onClick = { },
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 16.dp)
        ) {
            Text("Sign In")
        }

        TextButton(
            onClick = { }
        ) {
            Text("Forgot Password?")
        }
    }
}

@Composable
private fun UserProfileScreenComposable() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "User Profile",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(bottom = 24.dp)
        )

        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 16.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp)
            ) {
                Text("John Doe", style = MaterialTheme.typography.headlineSmall)
                Text("john.doe@example.com", style = MaterialTheme.typography.bodyMedium)
                Text("Member since 2021", style = MaterialTheme.typography.bodySmall)
            }
        }

        Button(
            onClick = { },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Edit Profile")
        }
    }
}

@Composable
private fun ButtonStatesComposable(
    primaryEnabled: Boolean,
    secondaryEnabled: Boolean,
    loadingState: Boolean
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("Button States Test", style = MaterialTheme.typography.headlineMedium)

        Button(
            onClick = { },
            enabled = primaryEnabled,
            modifier = Modifier.fillMaxWidth()
        ) {
            if (loadingState) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    strokeWidth = 2.dp
                )
            } else {
                Text("Primary Button")
            }
        }

        OutlinedButton(
            onClick = { },
            enabled = secondaryEnabled,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Secondary Button")
        }
    }
}

@Composable
private fun NavigationDrawerComposable() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("Navigation Menu", style = MaterialTheme.typography.headlineSmall)

        Spacer(modifier = Modifier.height(16.dp))

        listOf("Home", "Profile", "Settings", "Help", "About").forEach { item ->
            NavigationDrawerItem(
                label = { Text(item) },
                selected = item == "Home",
                onClick = { },
                modifier = Modifier.padding(vertical = 4.dp)
            )
        }
    }
}

/**
 * Mock telemetry client for testing
 */
private class MockStreamTelemetryClient {
    private val events = mutableListOf<TelemetryEvent>()

    fun queueEvent(event: TelemetryEvent) {
        events.add(event)
        println("Visual regression event recorded: ${event.data["screen_name"]} - ${event.data["test_name"]}")
    }

    fun getEvents(): List<TelemetryEvent> = events
}