package com.intelliwiz.mobile.telemetry.core

import android.app.Application
import android.content.Context
import androidx.lifecycle.ProcessLifecycleOwner
import com.intelliwiz.mobile.telemetry.transport.TelemetryTransport
import com.intelliwiz.mobile.telemetry.compose.ComposePerformanceTracker
import com.intelliwiz.mobile.telemetry.lifecycle.LifecycleTracker
import com.intelliwiz.mobile.telemetry.network.NetworkInterceptor
import com.intelliwiz.mobile.telemetry.pii.PIIRedactor
import kotlinx.coroutines.*
import kotlinx.serialization.json.Json
import mu.KotlinLogging
import java.util.*
import java.util.concurrent.ConcurrentLinkedQueue

private val logger = KotlinLogging.logger {}

/**
 * Main entry point for Stream Testbench Mobile Telemetry SDK
 *
 * Based on existing WebSocketGenerator patterns but optimized for real mobile app instrumentation.
 * Provides comprehensive telemetry collection with PII protection and real-time streaming.
 */
class StreamTelemetryClient private constructor(
    private val config: TelemetryConfig
) {
    companion object {
        @Volatile
        private var INSTANCE: StreamTelemetryClient? = null

        /**
         * Initialize the telemetry client (call once in Application.onCreate)
         */
        fun initialize(context: Context, config: TelemetryConfig): StreamTelemetryClient {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: StreamTelemetryClient(config).also { client ->
                    INSTANCE = client
                    client.setup(context.applicationContext)
                }
            }
        }

        /**
         * Get the initialized client instance
         */
        fun getInstance(): StreamTelemetryClient {
            return INSTANCE ?: throw IllegalStateException(
                "StreamTelemetryClient not initialized. Call initialize() first."
            )
        }
    }

    // Core components (reusing existing patterns)
    private lateinit var transport: TelemetryTransport
    private lateinit var piiRedactor: PIIRedactor
    private lateinit var composeTracker: ComposePerformanceTracker
    private lateinit var lifecycleTracker: LifecycleTracker
    private lateinit var networkInterceptor: NetworkInterceptor

    // Coroutine management (similar to WebSocketGenerator)
    private val clientScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val eventQueue = ConcurrentLinkedQueue<TelemetryEvent>()

    // Job tracking for proper lifecycle management
    private var processingJob: Job? = null
    private val activeJobs = mutableSetOf<Job>()
    private val jobsLock = Any()

    // JSON serialization (align with existing)
    private val json = Json {
        prettyPrint = config.debugMode
        ignoreUnknownKeys = true
        encodeDefaults = false
    }

    // Metrics tracking (inspired by WebSocketGenerator)
    private var eventsSent = 0L
    private var eventsQueued = 0L
    private var transmissionErrors = 0L
    private var lastConnectionTime = 0L

    private fun setup(context: Context) {
        logger.info { "Initializing StreamTelemetryClient with endpoint: ${config.endpoint}" }

        // Initialize core components
        transport = TelemetryTransport(config, json)
        piiRedactor = PIIRedactor(config.piiRedactionRules)
        composeTracker = ComposePerformanceTracker(this)
        lifecycleTracker = LifecycleTracker(this)
        networkInterceptor = NetworkInterceptor(this)

        // Setup lifecycle observation
        if (context is Application) {
            ProcessLifecycleOwner.get().lifecycle.addObserver(lifecycleTracker)
        }

        // Start telemetry collection
        startTelemetryCollection()

        logger.info { "StreamTelemetryClient initialized successfully" }
    }

    /**
     * Start telemetry collection and transmission
     */
    private fun startTelemetryCollection() {
        processingJob = clientScope.launch {
            try {
                withTimeout(config.transmissionIntervalMs * 100) {
                    // Connect to stream testbench (reuse WebSocket patterns)
                    transport.connect()

                    // Start event processing loop
                    processEventQueue()
                }
            } catch (e: TimeoutCancellationException) {
                logger.error(e) { "Telemetry collection timed out: ${e.message}" }
            } catch (e: CancellationException) {
                logger.info { "Telemetry collection cancelled" }
                throw e // Re-throw to propagate cancellation
            } catch (e: Exception) {
                logger.error(e) { "Telemetry collection error: ${e.message}" }
            }
        }

        synchronized(jobsLock) {
            processingJob?.let { activeJobs.add(it) }
        }
    }

    /**
     * Process queued events and transmit to Stream Testbench
     * Based on WebSocketGenerator message sending patterns
     * Uses explicit cancellation checks instead of passive while loop
     */
    private suspend fun processEventQueue() {
        try {
            while (isActive) {
                // Check for cancellation before processing
                ensureActive()

                try {
                    val events = mutableListOf<TelemetryEvent>()

                    // Batch events for efficient transmission
                    repeat(config.batchSize.coerceAtMost(eventQueue.size)) {
                        eventQueue.poll()?.let { events.add(it) }
                    }

                    if (events.isNotEmpty()) {
                        withTimeout(config.transmissionIntervalMs * 2) {
                            transmitEvents(events)
                        }
                        eventsSent += events.size
                    }

                    // Wait before next batch (configurable interval)
                    delay(config.transmissionIntervalMs)

                } catch (e: TimeoutCancellationException) {
                    logger.warn(e) { "Event transmission timed out, retrying: ${e.message}" }
                    transmissionErrors++
                } catch (e: CancellationException) {
                    logger.info { "Event queue processing cancelled" }
                    throw e // Re-throw to propagate cancellation
                } catch (e: java.net.SocketException) {
                    logger.error(e) { "Network error processing event queue: ${e.message}" }
                    transmissionErrors++
                    delay(5000) // Back-off on network errors
                } catch (e: java.io.IOException) {
                    logger.error(e) { "IO error processing event queue: ${e.message}" }
                    transmissionErrors++
                    delay(5000) // Back-off on IO errors
                }
            }
        } catch (e: CancellationException) {
            logger.info { "Event queue processing cancelled gracefully" }
            throw e
        }
    }

    /**
     * Transmit events to Stream Testbench
     * Mirrors existing WebSocket message sending with correlation IDs
     */
    private suspend fun transmitEvents(events: List<TelemetryEvent>) {
        try {
            val correlationId = generateCorrelationId()

            val message = StreamEventBatch(
                type = "mobile_telemetry_batch",
                correlationId = correlationId,
                timestamp = System.currentTimeMillis(),
                events = events.map { event ->
                    piiRedactor.sanitize(event) // Apply PII redaction like existing
                },
                metadata = TelemetryMetadata(
                    sdkVersion = BuildConfig.SDK_VERSION,
                    clientType = "mobile_android",
                    batchSize = events.size
                )
            )

            transport.send(message)
            logger.debug { "Transmitted batch with correlation ID: $correlationId" }

        } catch (e: Exception) {
            logger.error(e) { "Failed to transmit events: ${e.message}" }
            transmissionErrors++
            throw e
        }
    }

    /**
     * Queue telemetry event for transmission
     */
    internal fun queueEvent(event: TelemetryEvent) {
        if (eventQueue.size < config.maxQueueSize) {
            eventQueue.offer(event)
            eventsQueued++
        } else {
            logger.warn { "Event queue full, dropping event: ${event.eventType}" }
        }
    }

    /**
     * Get network interceptor for OkHttp integration
     */
    fun getNetworkInterceptor(): okhttp3.Interceptor {
        return networkInterceptor
    }

    /**
     * Get Compose performance tracker
     */
    fun getComposeTracker(): ComposePerformanceTracker {
        return composeTracker
    }

    /**
     * Record custom telemetry event
     */
    fun recordEvent(
        eventType: String,
        data: Map<String, Any>,
        endpoint: String? = null,
        latencyMs: Double? = null
    ) {
        val event = TelemetryEvent(
            id = UUID.randomUUID().toString(),
            eventType = eventType,
            timestamp = System.currentTimeMillis(),
            endpoint = endpoint ?: "custom",
            data = data,
            latencyMs = latencyMs,
            outcome = if (latencyMs != null && latencyMs > 1000) "anomaly" else "success"
        )

        queueEvent(event)
    }

    /**
     * Get current telemetry metrics
     */
    fun getMetrics(): TelemetryMetrics {
        return TelemetryMetrics(
            eventsSent = eventsSent,
            eventsQueued = eventsQueued,
            queueSize = eventQueue.size,
            transmissionErrors = transmissionErrors,
            isConnected = transport.isConnected(),
            lastConnectionTime = lastConnectionTime
        )
    }

    /**
     * Stop telemetry collection (graceful stop without full shutdown)
     */
    fun stop() {
        logger.info { "Stopping StreamTelemetryClient" }

        // Cancel processing job
        processingJob?.cancel()
        processingJob = null

        // Cancel all active jobs
        synchronized(jobsLock) {
            activeJobs.forEach { job ->
                try {
                    job.cancel()
                } catch (e: Exception) {
                    logger.warn(e) { "Error cancelling job: ${e.message}" }
                }
            }
            activeJobs.clear()
        }

        logger.info { "StreamTelemetryClient stopped" }
    }

    /**
     * Shutdown telemetry client (full cleanup with transport disconnect)
     */
    fun shutdown() {
        logger.info { "Shutting down StreamTelemetryClient" }

        // Stop all coroutines first
        stop()

        // Cancel the scope
        clientScope.cancel()

        // Disconnect transport
        transport.disconnect()

        logger.info { "StreamTelemetryClient shutdown complete" }
    }

    /**
     * Generate correlation ID (reuse existing pattern)
     */
    private fun generateCorrelationId(): String {
        return UUID.randomUUID().toString()
    }
}

/**
 * Telemetry configuration
 */
data class TelemetryConfig(
    val endpoint: String,
    val authConfig: AuthConfig? = null,
    val piiRedactionRules: Map<String, Any> = emptyMap(),
    val batchSize: Int = 10,
    val maxQueueSize: Int = 1000,
    val transmissionIntervalMs: Long = 5000,
    val debugMode: Boolean = false,
    val enableCompose: Boolean = true,
    val enableNetworkTracking: Boolean = true,
    val enableLifecycleTracking: Boolean = true
)

/**
 * Authentication configuration (reuse existing pattern)
 */
data class AuthConfig(
    val type: AuthType,
    val credentials: Map<String, String>
)

enum class AuthType {
    BEARER_TOKEN,
    API_KEY,
    CUSTOM
}

/**
 * Individual telemetry event
 */
data class TelemetryEvent(
    val id: String,
    val eventType: String,
    val timestamp: Long,
    val endpoint: String,
    val data: Map<String, Any>,
    val latencyMs: Double? = null,
    val outcome: String = "success",
    val direction: String = "outbound"
)

/**
 * Batch of events for transmission
 */
data class StreamEventBatch(
    val type: String,
    val correlationId: String,
    val timestamp: Long,
    val events: List<TelemetryEvent>,
    val metadata: TelemetryMetadata
)

/**
 * Telemetry metadata
 */
data class TelemetryMetadata(
    val sdkVersion: String,
    val clientType: String,
    val batchSize: Int
)

/**
 * Current telemetry metrics
 */
data class TelemetryMetrics(
    val eventsSent: Long,
    val eventsQueued: Long,
    val queueSize: Int,
    val transmissionErrors: Long,
    val isConnected: Boolean,
    val lastConnectionTime: Long
)