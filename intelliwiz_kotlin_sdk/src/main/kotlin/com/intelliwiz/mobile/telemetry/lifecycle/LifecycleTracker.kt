package com.intelliwiz.mobile.telemetry.lifecycle

import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import com.intelliwiz.mobile.telemetry.core.StreamTelemetryClient
import com.intelliwiz.mobile.telemetry.core.TelemetryEvent
import mu.KotlinLogging
import java.util.*

private val logger = KotlinLogging.logger {}

/**
 * Application Lifecycle Tracker
 *
 * Tracks app lifecycle events and ANR detection for performance correlation.
 * Feeds lifecycle events to Stream Testbench for anomaly detection.
 */
class LifecycleTracker(
    private val telemetryClient: StreamTelemetryClient
) : DefaultLifecycleObserver {

    private var appStartTime = System.currentTimeMillis()
    private var lastForegroundTime = 0L
    private var lastBackgroundTime = 0L

    override fun onCreate(owner: LifecycleOwner) {
        super.onCreate(owner)
        recordLifecycleEvent("app_created")
        logger.info { "Application created" }
    }

    override fun onStart(owner: LifecycleOwner) {
        super.onStart(owner)
        lastForegroundTime = System.currentTimeMillis()
        val backgroundDuration = if (lastBackgroundTime > 0) {
            lastForegroundTime - lastBackgroundTime
        } else 0L

        recordLifecycleEvent("app_foreground", mapOf(
            "background_duration_ms" to backgroundDuration
        ))

        logger.debug { "Application came to foreground (background duration: ${backgroundDuration}ms)" }
    }

    override fun onStop(owner: LifecycleOwner) {
        super.onStop(owner)
        lastBackgroundTime = System.currentTimeMillis()
        val foregroundDuration = if (lastForegroundTime > 0) {
            lastBackgroundTime - lastForegroundTime
        } else 0L

        recordLifecycleEvent("app_background", mapOf(
            "foreground_duration_ms" to foregroundDuration
        ))

        logger.debug { "Application went to background (foreground duration: ${foregroundDuration}ms)" }
    }

    override fun onDestroy(owner: LifecycleOwner) {
        super.onDestroy(owner)
        val totalAppDuration = System.currentTimeMillis() - appStartTime

        recordLifecycleEvent("app_destroyed", mapOf(
            "total_app_duration_ms" to totalAppDuration
        ))

        logger.info { "Application destroyed (total duration: ${totalAppDuration}ms)" }
    }

    /**
     * Record lifecycle event
     */
    private fun recordLifecycleEvent(eventType: String, additionalData: Map<String, Any> = emptyMap()) {
        val event = TelemetryEvent(
            id = UUID.randomUUID().toString(),
            eventType = eventType,
            timestamp = System.currentTimeMillis(),
            endpoint = "app_lifecycle",
            data = mapOf(
                "lifecycle_event" to eventType,
                "app_start_time" to appStartTime
            ) + additionalData,
            outcome = "success"
        )

        telemetryClient.queueEvent(event)
    }
}