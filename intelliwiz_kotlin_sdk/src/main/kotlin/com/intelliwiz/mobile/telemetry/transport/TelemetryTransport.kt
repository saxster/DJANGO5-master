package com.intelliwiz.mobile.telemetry.transport

import com.intelliwiz.mobile.telemetry.core.*
import io.ktor.client.*
import io.ktor.client.engine.android.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.plugins.logging.*
import io.ktor.client.plugins.websocket.*
import io.ktor.client.request.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import mu.KotlinLogging
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import kotlin.random.Random

private val logger = KotlinLogging.logger {}

/**
 * Dual Transport Implementation (WebSocket + HTTPS Fallback)
 *
 * Based on existing WebSocketGenerator patterns but enhanced for mobile reliability.
 * Primary: WebSocket (real-time streaming to Stream Testbench)
 * Fallback: HTTPS batched upload (when WebSocket unavailable)
 */
class TelemetryTransport(
    private val config: TelemetryConfig,
    private val json: Json
) {
    // HTTP client (reuse existing Ktor patterns)
    private val httpClient = HttpClient(Android) {
        install(WebSockets) {
            pingInterval = 20_000 // 20 seconds heartbeat
            maxFrameSize = Long.MAX_VALUE
        }

        install(ContentNegotiation) {
            json(this@TelemetryTransport.json)
        }

        install(Logging) {
            logger = Logger.SIMPLE
            level = if (config.debugMode) LogLevel.ALL else LogLevel.INFO
        }
    }

    // Connection management
    private val isConnected = AtomicBoolean(false)
    private val connectionAttempts = AtomicLong(0)
    private val lastSuccessfulConnection = AtomicLong(0)

    // Transport channels
    private val websocketChannel = Channel<StreamEventBatch>(Channel.UNLIMITED)
    private val httpFallbackChannel = Channel<StreamEventBatch>(Channel.UNLIMITED)

    // Connection state
    private var websocketSession: DefaultClientWebSocketSession? = null
    private val transportScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // Job tracking for proper lifecycle management
    private val activeJobs = mutableSetOf<Job>()
    private val jobsLock = Any()
    private var webSocketSendJob: Job? = null
    private var webSocketReceiveJob: Job? = null
    private var wsTransportJob: Job? = null
    private var httpTransportJob: Job? = null

    /**
     * Connect to Stream Testbench endpoint
     * Mirrors existing WebSocket connection patterns with authentication
     */
    suspend fun connect() {
        logger.info { "Connecting to Stream Testbench: ${config.endpoint}" }

        connectionAttempts.incrementAndGet()

        try {
            // Attempt WebSocket connection first (primary transport)
            connectWebSocket()

            // Start transport processing
            startTransportProcessing()

        } catch (e: Exception) {
            logger.warn(e) { "WebSocket connection failed, using HTTPS fallback: ${e.message}" }
            startHttpFallbackOnly()
        }
    }

    /**
     * Connect WebSocket (reuse existing connection patterns)
     */
    private suspend fun connectWebSocket() {
        try {
            val (host, port, path) = parseEndpoint(config.endpoint)

            httpClient.webSocket(
                method = HttpMethod.Get,
                host = host,
                port = port,
                path = path
            ) {
                websocketSession = this
                isConnected.set(true)
                lastSuccessfulConnection.set(System.currentTimeMillis())

                logger.info { "WebSocket connected to Stream Testbench" }

                // Send authentication (reuse existing auth patterns)
                config.authConfig?.let { auth ->
                    sendAuthentication(auth)
                }

                // Handle WebSocket lifecycle
                handleWebSocketSession()
            }
        } catch (e: Exception) {
            logger.error(e) { "WebSocket connection failed: ${e.message}" }
            isConnected.set(false)
            websocketSession = null
            throw e
        }
    }

    /**
     * Handle WebSocket session (inspired by existing WebSocketGenerator)
     * Now with proper job tracking and cancellation
     */
    private suspend fun DefaultClientWebSocketSession.handleWebSocketSession() {
        try {
            // Start message sending coroutine
            webSocketSendJob = launch {
                try {
                    for (batch in websocketChannel) {
                        ensureActive() // Check for cancellation
                        try {
                            withTimeout(5000) { // 5 second timeout per message
                                val message = json.encodeToString(batch)
                                send(message)
                                logger.debug { "Sent batch via WebSocket: ${batch.correlationId}" }
                            }
                        } catch (e: TimeoutCancellationException) {
                            logger.warn(e) { "WebSocket send timed out for batch: ${batch.correlationId}" }
                            httpFallbackChannel.trySend(batch)
                        } catch (e: CancellationException) {
                            throw e // Re-throw cancellation
                        } catch (e: Exception) {
                            logger.error(e) { "Failed to send batch via WebSocket: ${e.message}" }
                            httpFallbackChannel.trySend(batch)
                        }
                    }
                } catch (e: CancellationException) {
                    logger.info { "WebSocket send job cancelled" }
                    throw e
                }
            }

            // Start message receiving coroutine
            webSocketReceiveJob = launch {
                try {
                    for (frame in incoming) {
                        ensureActive() // Check for cancellation
                        when (frame) {
                            is Frame.Text -> {
                                val response = frame.readText()
                                logger.debug { "Received WebSocket response: $response" }
                                processServerResponse(response)
                            }
                            is Frame.Close -> {
                                logger.info { "WebSocket closed by server" }
                                break
                            }
                            else -> {
                                logger.debug { "Received unknown WebSocket frame type" }
                            }
                        }
                    }
                } catch (e: CancellationException) {
                    logger.info { "WebSocket receive job cancelled" }
                    throw e
                }
            }

            // Track jobs
            synchronized(jobsLock) {
                webSocketSendJob?.let { activeJobs.add(it) }
                webSocketReceiveJob?.let { activeJobs.add(it) }
            }

            // Wait for jobs to complete
            joinAll(webSocketSendJob!!, webSocketReceiveJob!!)

        } catch (e: CancellationException) {
            logger.info { "WebSocket session cancelled" }
            throw e
        } catch (e: Exception) {
            logger.error(e) { "WebSocket session error: ${e.message}" }
        } finally {
            // Cleanup
            synchronized(jobsLock) {
                webSocketSendJob?.let { activeJobs.remove(it) }
                webSocketReceiveJob?.let { activeJobs.remove(it) }
            }
            webSocketSendJob = null
            webSocketReceiveJob = null
            isConnected.set(false)
            websocketSession = null
            logger.info { "WebSocket session ended" }
        }
    }

    /**
     * Send authentication message (reuse existing pattern)
     */
    private suspend fun DefaultClientWebSocketSession.sendAuthentication(auth: AuthConfig) {
        val authMessage = when (auth.type) {
            AuthType.BEARER_TOKEN -> mapOf(
                "type" to "authenticate",
                "token" to auth.credentials["token"]
            )
            AuthType.API_KEY -> mapOf(
                "type" to "authenticate",
                "api_key" to auth.credentials["api_key"]
            )
            else -> mapOf(
                "type" to "authenticate",
                "credentials" to auth.credentials
            )
        }

        send(json.encodeToString(authMessage))
        logger.debug { "Sent authentication via WebSocket" }
    }

    /**
     * Start transport processing (dual-channel approach)
     * Now with proper job tracking
     */
    private fun startTransportProcessing() {
        wsTransportJob = transportScope.launch {
            try {
                processWebSocketTransport()
            } catch (e: CancellationException) {
                logger.info { "WebSocket transport job cancelled" }
                throw e
            }
        }

        httpTransportJob = transportScope.launch {
            try {
                processHttpFallbackTransport()
            } catch (e: CancellationException) {
                logger.info { "HTTP fallback transport job cancelled" }
                throw e
            }
        }

        synchronized(jobsLock) {
            wsTransportJob?.let { activeJobs.add(it) }
            httpTransportJob?.let { activeJobs.add(it) }
        }
    }

    /**
     * Process WebSocket transport channel
     * Now with explicit cancellation checks and proper error handling
     */
    private suspend fun processWebSocketTransport() {
        try {
            for (batch in websocketChannel) {
                ensureActive() // Check for cancellation

                if (isConnected.get() && websocketSession != null) {
                    try {
                        withTimeout(5000) {
                            val message = json.encodeToString(batch)
                            websocketSession?.send(message)
                            logger.debug { "Processed batch via WebSocket: ${batch.correlationId}" }
                        }
                    } catch (e: TimeoutCancellationException) {
                        logger.warn(e) { "WebSocket send timed out, falling back to HTTP: ${batch.correlationId}" }
                        httpFallbackChannel.trySend(batch)
                    } catch (e: CancellationException) {
                        throw e // Re-throw cancellation
                    } catch (e: java.net.SocketException) {
                        logger.error(e) { "WebSocket socket error, falling back to HTTP: ${e.message}" }
                        httpFallbackChannel.trySend(batch)
                    } catch (e: java.io.IOException) {
                        logger.error(e) { "WebSocket IO error, falling back to HTTP: ${e.message}" }
                        httpFallbackChannel.trySend(batch)
                    }
                } else {
                    // WebSocket not available, use HTTP fallback
                    httpFallbackChannel.trySend(batch)
                }
            }
        } catch (e: CancellationException) {
            logger.info { "WebSocket transport processing cancelled" }
            throw e
        }
    }

    /**
     * Process HTTP fallback transport
     * Now with explicit cancellation checks and specific error handling
     */
    private suspend fun processHttpFallbackTransport() {
        try {
            for (batch in httpFallbackChannel) {
                ensureActive() // Check for cancellation

                try {
                    withTimeout(10000) { // 10 second timeout for HTTP
                        sendViaHttp(batch)
                        logger.debug { "Processed batch via HTTP fallback: ${batch.correlationId}" }
                    }
                } catch (e: TimeoutCancellationException) {
                    logger.error(e) { "HTTP fallback timed out for batch: ${batch.correlationId}" }
                } catch (e: CancellationException) {
                    throw e // Re-throw cancellation
                } catch (e: java.net.UnknownHostException) {
                    logger.error(e) { "HTTP fallback failed (unknown host) for batch: ${batch.correlationId}" }
                } catch (e: java.net.SocketTimeoutException) {
                    logger.error(e) { "HTTP fallback failed (timeout) for batch: ${batch.correlationId}" }
                } catch (e: java.io.IOException) {
                    logger.error(e) { "HTTP fallback IO error for batch: ${batch.correlationId}" }
                }
            }
        } catch (e: CancellationException) {
            logger.info { "HTTP fallback transport processing cancelled" }
            throw e
        }
    }

    /**
     * Send batch via HTTP (fallback transport)
     */
    private suspend fun sendViaHttp(batch: StreamEventBatch) {
        try {
            val httpEndpoint = config.endpoint.replace("ws://", "http://").replace("wss://", "https://")
            val url = "$httpEndpoint/api/v2/telemetry/stream-events/batch"

            val response = httpClient.post(url) {
                contentType(ContentType.Application.Json)

                // Add authentication headers
                config.authConfig?.let { auth ->
                    when (auth.type) {
                        AuthType.BEARER_TOKEN -> {
                            headers["Authorization"] = "Bearer ${auth.credentials["token"]}"
                        }
                        AuthType.API_KEY -> {
                            headers["X-API-Key"] = auth.credentials["api_key"] ?: ""
                        }
                        else -> {
                            // Custom auth handling
                        }
                    }
                }

                setBody(batch)
            }

            if (response.status.isSuccess()) {
                logger.debug { "HTTP batch upload successful: ${batch.correlationId}" }
            } else {
                logger.error { "HTTP batch upload failed with status: ${response.status}" }
            }

        } catch (e: Exception) {
            logger.error(e) { "HTTP batch upload exception: ${e.message}" }
            throw e
        }
    }

    /**
     * Start HTTP-only fallback mode
     */
    private fun startHttpFallbackOnly() {
        logger.info { "Starting HTTP-only transport mode" }
        transportScope.launch {
            processHttpFallbackTransport()
        }
    }

    /**
     * Send telemetry batch (primary interface)
     */
    suspend fun send(batch: StreamEventBatch) {
        try {
            if (isConnected.get()) {
                // Try WebSocket first
                websocketChannel.trySend(batch).getOrThrow()
            } else {
                // Use HTTP fallback
                httpFallbackChannel.trySend(batch).getOrThrow()
            }
        } catch (e: Exception) {
            logger.error(e) { "Failed to queue batch for transmission: ${e.message}" }
            // Last resort: try HTTP immediately
            try {
                sendViaHttp(batch)
            } catch (httpException: Exception) {
                logger.error(httpException) { "All transport methods failed for batch: ${batch.correlationId}" }
                throw httpException
            }
        }
    }

    /**
     * Process server response
     */
    private fun processServerResponse(response: String) {
        try {
            // Parse and handle server responses
            // Could include acknowledgments, configuration updates, etc.
            logger.debug { "Processed server response: ${response.take(100)}" }
        } catch (e: Exception) {
            logger.warn(e) { "Failed to process server response: ${e.message}" }
        }
    }

    /**
     * Parse endpoint URL (reuse existing parsing logic)
     */
    private fun parseEndpoint(endpoint: String): Triple<String, Int, String> {
        return try {
            val url = if (!endpoint.startsWith("ws://") && !endpoint.startsWith("wss://")) {
                "ws://$endpoint"
            } else endpoint

            val uri = java.net.URI(url)
            val host = uri.host ?: "localhost"
            val port = if (uri.port > 0) uri.port else 8000
            val path = uri.path.ifEmpty { "/" }

            Triple(host, port, path)
        } catch (e: Exception) {
            logger.warn(e) { "Failed to parse endpoint, using defaults: ${e.message}" }
            Triple("localhost", 8000, "/")
        }
    }

    /**
     * Check if transport is connected
     */
    fun isConnected(): Boolean {
        return isConnected.get()
    }

    /**
     * Get connection metrics
     */
    fun getConnectionMetrics(): ConnectionMetrics {
        return ConnectionMetrics(
            isConnected = isConnected.get(),
            connectionAttempts = connectionAttempts.get(),
            lastSuccessfulConnection = lastSuccessfulConnection.get(),
            websocketQueueSize = websocketChannel.tryReceive().getOrNull()?.let {
                websocketChannel.isEmpty.not()
            } ?: false,
            httpFallbackQueueSize = httpFallbackChannel.tryReceive().getOrNull()?.let {
                httpFallbackChannel.isEmpty.not()
            } ?: false
        )
    }

    /**
     * Stop transport (graceful stop without full disconnect)
     */
    fun stopTransport() {
        logger.info { "Stopping TelemetryTransport" }

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

        // Cancel specific job references
        webSocketSendJob?.cancel()
        webSocketReceiveJob?.cancel()
        wsTransportJob?.cancel()
        httpTransportJob?.cancel()

        // Clear job references
        webSocketSendJob = null
        webSocketReceiveJob = null
        wsTransportJob = null
        httpTransportJob = null

        logger.info { "TelemetryTransport stopped" }
    }

    /**
     * Disconnect transport (full cleanup)
     */
    fun disconnect() {
        logger.info { "Disconnecting TelemetryTransport" }

        // Stop all jobs first
        stopTransport()

        // Set disconnected state
        isConnected.set(false)

        // Cancel transport scope
        transportScope.cancel()

        // Close WebSocket session
        websocketSession?.cancel()
        websocketSession = null

        // Close HTTP client
        httpClient.close()

        logger.info { "TelemetryTransport disconnected" }
    }
}

/**
 * Connection metrics for monitoring
 */
data class ConnectionMetrics(
    val isConnected: Boolean,
    val connectionAttempts: Long,
    val lastSuccessfulConnection: Long,
    val websocketQueueSize: Boolean,
    val httpFallbackQueueSize: Boolean
)