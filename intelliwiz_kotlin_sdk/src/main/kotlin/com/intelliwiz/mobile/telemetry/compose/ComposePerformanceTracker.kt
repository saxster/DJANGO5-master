package com.intelliwiz.mobile.telemetry.compose

import android.view.Choreographer
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.LifecycleOwner
import com.intelliwiz.mobile.telemetry.core.StreamTelemetryClient
import com.intelliwiz.mobile.telemetry.core.TelemetryEvent
import kotlinx.coroutines.*
import mu.KotlinLogging
import java.util.concurrent.atomic.AtomicLong
import kotlin.system.measureTimeMillis

private val logger = KotlinLogging.logger {}

/**
 * Compose Performance Tracker for UI jank detection and composition monitoring
 *
 * Leverages existing correlation ID patterns from WebSocketGenerator for event tracking.
 * Provides real-time performance metrics feeding into Stream Testbench anomaly detection.
 */
class ComposePerformanceTracker(
    private val telemetryClient: StreamTelemetryClient
) {
    // Frame metrics (inspired by WebSocketGenerator latency tracking)
    private val frameTimeTracker = FrameTimeTracker()
    private val compositionTracker = CompositionTracker()
    private val jankDetector = JankDetector()

    // Performance counters (similar to WebSocketGenerator counters)
    private val totalCompositions = AtomicLong(0)
    private val jankFrames = AtomicLong(0)
    private val slowCompositions = AtomicLong(0)
    private val anrDetections = AtomicLong(0)

    // Coroutine scope for async tracking
    private val trackerScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    init {
        startFrameTimeMonitoring()
        logger.info { "ComposePerformanceTracker initialized" }
    }

    /**
     * Start frame time monitoring using Choreographer
     * Mirrors WebSocketGenerator's performance measurement patterns
     */
    private fun startFrameTimeMonitoring() {
        frameTimeTracker.startMonitoring { frameTimeMs ->
            // Detect jank (similar to anomaly detection in WebSocketGenerator)
            if (frameTimeMs > JANK_THRESHOLD_MS) {
                jankFrames.incrementAndGet()
                recordJankEvent(frameTimeMs)
            }

            // Record frame timing metrics
            recordFrameMetrics(frameTimeMs)
        }
    }

    /**
     * Composable function to track composition performance
     * Use in Compose UI to monitor component performance
     */
    @Composable
    fun TrackComposition(
        screenName: String,
        content: @Composable () -> Unit
    ) {
        val lifecycleOwner = LocalLifecycleOwner.current

        // Track composition lifecycle (similar to WebSocket connection lifecycle)
        DisposableEffect(lifecycleOwner) {
            val observer = LifecycleEventObserver { _, event ->
                when (event) {
                    Lifecycle.Event.ON_CREATE -> {
                        recordCompositionEvent(screenName, "composition_created")
                    }
                    Lifecycle.Event.ON_START -> {
                        compositionTracker.startTracking(screenName)
                    }
                    Lifecycle.Event.ON_STOP -> {
                        compositionTracker.stopTracking(screenName)
                    }
                    Lifecycle.Event.ON_DESTROY -> {
                        recordCompositionEvent(screenName, "composition_destroyed")
                    }
                    else -> { /* No action needed */ }
                }
            }

            lifecycleOwner.lifecycle.addObserver(observer)

            onDispose {
                lifecycleOwner.lifecycle.removeObserver(observer)
            }
        }

        // Track composition timing (similar to WebSocket message timing)
        val compositionTime = remember { measureTimeMillis { content() } }

        LaunchedEffect(screenName, compositionTime) {
            totalCompositions.incrementAndGet()

            // Detect slow compositions (anomaly detection pattern)
            if (compositionTime > SLOW_COMPOSITION_THRESHOLD_MS) {
                slowCompositions.incrementAndGet()
                recordSlowCompositionEvent(screenName, compositionTime)
            }

            recordCompositionMetrics(screenName, compositionTime)
        }

        content()
    }

    /**
     * Record jank event (mirrors WebSocketGenerator error recording)
     */
    private fun recordJankEvent(frameTimeMs: Double) {
        val event = TelemetryEvent(
            id = generateCorrelationId(),
            eventType = "ui_jank_detected",
            timestamp = System.currentTimeMillis(),
            endpoint = "compose_ui",
            data = mapOf(
                "frame_time_ms" to frameTimeMs,
                "jank_severity" to when {
                    frameTimeMs > 100 -> "severe"
                    frameTimeMs > 50 -> "moderate"
                    else -> "mild"
                },
                "threshold_exceeded_by_ms" to (frameTimeMs - JANK_THRESHOLD_MS)
            ),
            latencyMs = frameTimeMs,
            outcome = "anomaly" // Mark as anomaly for Stream Testbench detection
        )

        telemetryClient.queueEvent(event)
        logger.debug { "Jank detected: ${frameTimeMs}ms frame time" }
    }

    /**
     * Record slow composition event
     */
    private fun recordSlowCompositionEvent(screenName: String, compositionTimeMs: Long) {
        val event = TelemetryEvent(
            id = generateCorrelationId(),
            eventType = "slow_composition_detected",
            timestamp = System.currentTimeMillis(),
            endpoint = "compose_screen/$screenName",
            data = mapOf(
                "screen_name" to screenName,
                "composition_time_ms" to compositionTimeMs,
                "threshold_ms" to SLOW_COMPOSITION_THRESHOLD_MS,
                "performance_impact" to when {
                    compositionTimeMs > 500 -> "high"
                    compositionTimeMs > 200 -> "medium"
                    else -> "low"
                }
            ),
            latencyMs = compositionTimeMs.toDouble(),
            outcome = "anomaly"
        )

        telemetryClient.queueEvent(event)
        logger.debug { "Slow composition detected on $screenName: ${compositionTimeMs}ms" }
    }

    /**
     * Record regular frame metrics
     */
    private fun recordFrameMetrics(frameTimeMs: Double) {
        // Aggregate metrics and send periodically (like WebSocketGenerator batching)
        trackerScope.launch {
            val event = TelemetryEvent(
                id = generateCorrelationId(),
                eventType = "frame_metrics",
                timestamp = System.currentTimeMillis(),
                endpoint = "compose_frame",
                data = mapOf(
                    "frame_time_ms" to frameTimeMs,
                    "is_smooth" to (frameTimeMs <= 16.67), // 60 FPS threshold
                    "fps_equivalent" to (1000.0 / frameTimeMs).coerceAtMost(60.0)
                ),
                latencyMs = frameTimeMs,
                outcome = if (frameTimeMs > JANK_THRESHOLD_MS) "anomaly" else "success"
            )

            telemetryClient.queueEvent(event)
        }
    }

    /**
     * Record composition metrics
     */
    private fun recordCompositionMetrics(screenName: String, compositionTimeMs: Long) {
        val event = TelemetryEvent(
            id = generateCorrelationId(),
            eventType = "composition_metrics",
            timestamp = System.currentTimeMillis(),
            endpoint = "compose_screen/$screenName",
            data = mapOf(
                "screen_name" to screenName,
                "composition_time_ms" to compositionTimeMs,
                "total_compositions" to totalCompositions.get(),
                "performance_grade" to when {
                    compositionTimeMs <= 50 -> "A"
                    compositionTimeMs <= 100 -> "B"
                    compositionTimeMs <= 200 -> "C"
                    else -> "D"
                }
            ),
            latencyMs = compositionTimeMs.toDouble(),
            outcome = "success"
        )

        telemetryClient.queueEvent(event)
    }

    /**
     * Record general composition events
     */
    private fun recordCompositionEvent(screenName: String, eventType: String) {
        val event = TelemetryEvent(
            id = generateCorrelationId(),
            eventType = eventType,
            timestamp = System.currentTimeMillis(),
            endpoint = "compose_lifecycle/$screenName",
            data = mapOf(
                "screen_name" to screenName,
                "lifecycle_event" to eventType
            ),
            outcome = "success"
        )

        telemetryClient.queueEvent(event)
    }

    /**
     * Get current performance metrics
     */
    fun getPerformanceMetrics(): ComposePerformanceMetrics {
        return ComposePerformanceMetrics(
            totalCompositions = totalCompositions.get(),
            jankFrames = jankFrames.get(),
            slowCompositions = slowCompositions.get(),
            anrDetections = anrDetections.get(),
            averageFrameTime = frameTimeTracker.getAverageFrameTime(),
            jankPercentage = if (totalCompositions.get() > 0) {
                (jankFrames.get().toDouble() / totalCompositions.get()) * 100
            } else 0.0
        )
    }

    /**
     * Generate correlation ID (reuse WebSocketGenerator pattern)
     */
    private fun generateCorrelationId(): String {
        return java.util.UUID.randomUUID().toString()
    }

    /**
     * Shutdown performance tracking
     */
    fun shutdown() {
        frameTimeTracker.stopMonitoring()
        trackerScope.cancel()
        logger.info { "ComposePerformanceTracker shutdown complete" }
    }

    companion object {
        private const val JANK_THRESHOLD_MS = 16.67 // ~60 FPS threshold
        private const val SLOW_COMPOSITION_THRESHOLD_MS = 100L
    }
}

/**
 * Frame time tracking using Choreographer
 */
private class FrameTimeTracker {
    private var isMonitoring = false
    private var lastFrameTime = 0L
    private val frameTimes = mutableListOf<Double>()
    private var frameCallback: ((Double) -> Unit)? = null

    private val choreographerCallback = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            if (isMonitoring) {
                if (lastFrameTime != 0L) {
                    val frameTimeMs = (frameTimeNanos - lastFrameTime) / 1_000_000.0
                    frameTimes.add(frameTimeMs)
                    frameCallback?.invoke(frameTimeMs)

                    // Keep only recent frame times for average calculation
                    if (frameTimes.size > 100) {
                        frameTimes.removeAt(0)
                    }
                }
                lastFrameTime = frameTimeNanos
                Choreographer.getInstance().postFrameCallback(this)
            }
        }
    }

    fun startMonitoring(callback: (Double) -> Unit) {
        frameCallback = callback
        isMonitoring = true
        Choreographer.getInstance().postFrameCallback(choreographerCallback)
    }

    fun stopMonitoring() {
        isMonitoring = false
        Choreographer.getInstance().removeFrameCallback(choreographerCallback)
    }

    fun getAverageFrameTime(): Double {
        return if (frameTimes.isNotEmpty()) {
            frameTimes.average()
        } else 0.0
    }
}

/**
 * Composition lifecycle tracking
 */
private class CompositionTracker {
    private val activeCompositions = mutableMapOf<String, Long>()

    fun startTracking(screenName: String) {
        activeCompositions[screenName] = System.currentTimeMillis()
    }

    fun stopTracking(screenName: String): Long? {
        val startTime = activeCompositions.remove(screenName)
        return if (startTime != null) {
            System.currentTimeMillis() - startTime
        } else null
    }
}

/**
 * Jank detection and classification
 */
private class JankDetector {
    private var consecutiveJankFrames = 0
    private var lastJankTime = 0L

    fun detectJank(frameTimeMs: Double): JankLevel {
        val now = System.currentTimeMillis()
        val isJank = frameTimeMs > 16.67

        if (isJank) {
            if (now - lastJankTime < 1000) { // Within 1 second
                consecutiveJankFrames++
            } else {
                consecutiveJankFrames = 1
            }
            lastJankTime = now

            return when {
                consecutiveJankFrames > 10 -> JankLevel.SEVERE
                consecutiveJankFrames > 5 -> JankLevel.MODERATE
                frameTimeMs > 50 -> JankLevel.MODERATE
                else -> JankLevel.MILD
            }
        } else {
            consecutiveJankFrames = 0
            return JankLevel.NONE
        }
    }
}

enum class JankLevel {
    NONE, MILD, MODERATE, SEVERE
}

/**
 * Performance metrics summary
 */
data class ComposePerformanceMetrics(
    val totalCompositions: Long,
    val jankFrames: Long,
    val slowCompositions: Long,
    val anrDetections: Long,
    val averageFrameTime: Double,
    val jankPercentage: Double
)