package com.streamtestbench.generators

import com.streamtestbench.models.*
import io.ktor.client.*
import io.ktor.client.engine.cio.*
import io.ktor.client.plugins.logging.*
import io.ktor.client.plugins.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import mu.KotlinLogging
import java.util.concurrent.atomic.AtomicLong
import kotlin.random.Random
import kotlin.system.measureTimeMillis

private val logger = KotlinLogging.logger {}

class WebSocketGenerator(
    private val scenario: TestScenario
) {
    private val client = HttpClient(CIO) {
        install(WebSockets)
        install(Logging) {
            logger = Logger.SIMPLE
            level = LogLevel.INFO
        }
    }

    private val messageCounter = AtomicLong(0)
    private val successCounter = AtomicLong(0)
    private val errorCounter = AtomicLong(0)
    private val latencies = mutableListOf<Double>()
    private val errors = mutableMapOf<String, ErrorSummary>()

    private val json = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
    }

    suspend fun runScenario(): TestResult {
        logger.info { "Starting WebSocket scenario: ${scenario.name}" }
        logger.info { "Endpoint: ${scenario.endpoint}" }
        logger.info { "Connections: ${scenario.connections}" }
        logger.info { "Duration: ${scenario.duration_seconds}s" }

        val startTime = System.currentTimeMillis()
        val connectionMetrics = ConnectionMetrics(0, 0, 0, 0, 0.0)

        try {
            // Run multiple connections concurrently
            coroutineScope {
                val jobs = (1..scenario.connections).map { connectionId ->
                    async {
                        runConnection(connectionId, connectionMetrics)
                    }
                }

                // Wait for all connections to complete or timeout
                try {
                    withTimeout((scenario.duration_seconds * 1000L) + 10000) {
                        jobs.awaitAll()
                    }
                } catch (e: TimeoutCancellationException) {
                    logger.warn { "Some connections timed out" }
                    jobs.forEach { it.cancel() }
                }
            }
        } finally {
            client.close()
        }

        val endTime = System.currentTimeMillis()
        return generateTestResult(startTime, endTime, connectionMetrics)
    }

    private suspend fun runConnection(
        connectionId: Int,
        connectionMetrics: ConnectionMetrics
    ) {
        logger.debug { "Starting connection $connectionId" }

        try {
            val connectionStartTime = System.currentTimeMillis()

            client.webSocket(
                method = io.ktor.http.HttpMethod.Get,
                host = extractHost(scenario.endpoint),
                port = extractPort(scenario.endpoint),
                path = extractPath(scenario.endpoint)
            ) {
                val connectionTime = System.currentTimeMillis() - connectionStartTime
                logger.info { "Connection $connectionId established in ${connectionTime}ms" }

                // Send authentication if configured
                scenario.authentication?.let { auth ->
                    sendAuthMessage(auth)
                }

                // Start message sending coroutine
                val sendJob = launch {
                    sendMessages(connectionId)
                }

                // Start message receiving coroutine
                val receiveJob = launch {
                    receiveMessages(connectionId)
                }

                // Wait for scenario duration
                delay(scenario.duration_seconds * 1000L)

                // Cancel jobs and close connection
                sendJob.cancel()
                receiveJob.cancel()

                logger.debug { "Connection $connectionId completed" }
            }
        } catch (e: Exception) {
            logger.error(e) { "Connection $connectionId failed: ${e.message}" }
            recordError("CONNECTION_FAILED", e.message ?: "Unknown error", e.stackTraceToString())
        }
    }

    private suspend fun DefaultClientWebSocketSession.sendMessages(connectionId: Int) {
        val messageInterval = (1000.0 / scenario.rates.messagesPerSecond).toLong()

        try {
            while (!kotlinx.coroutines.isActive) {
                delay(messageInterval)

                val payload = generatePayload()
                val correlationId = generateCorrelationId()

                val message = createWebSocketMessage(payload, correlationId)

                val latency = measureTimeMillis {
                    send(json.encodeToString(message))
                }

                synchronized(latencies) {
                    latencies.add(latency.toDouble())
                }

                messageCounter.incrementAndGet()
                successCounter.incrementAndGet()

                // Apply failure injection
                applyFailureInjection()

                logger.trace { "Connection $connectionId sent message: $correlationId" }
            }
        } catch (e: Exception) {
            logger.error(e) { "Send loop failed for connection $connectionId: ${e.message}" }
            recordError("SEND_FAILED", e.message ?: "Send error", e.stackTraceToString())
        }
    }

    private suspend fun DefaultClientWebSocketSession.receiveMessages(connectionId: Int) {
        try {
            for (frame in incoming) {
                when (frame) {
                    is Frame.Text -> {
                        val text = frame.readText()
                        logger.trace { "Connection $connectionId received: $text" }
                        // Process received message for validation
                        processReceivedMessage(text)
                    }
                    is Frame.Binary -> {
                        logger.debug { "Connection $connectionId received binary frame" }
                    }
                    is Frame.Close -> {
                        logger.info { "Connection $connectionId closed by server" }
                        break
                    }
                    else -> {
                        logger.debug { "Connection $connectionId received unknown frame type" }
                    }
                }
            }
        } catch (e: Exception) {
            logger.error(e) { "Receive loop failed for connection $connectionId: ${e.message}" }
            recordError("RECEIVE_FAILED", e.message ?: "Receive error", e.stackTraceToString())
        }
    }

    private suspend fun DefaultClientWebSocketSession.sendAuthMessage(auth: AuthConfig) {
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
        logger.debug { "Sent authentication message" }
    }

    private fun generatePayload(): Map<String, Any> {
        val basePayload = mutableMapOf<String, Any>(
            "timestamp" to System.currentTimeMillis(),
            "message_id" to generateCorrelationId(),
            "connection_type" to "websocket"
        )

        scenario.payloads.forEach { payloadType ->
            when (payloadType) {
                PayloadType.VOICE_DATA -> {
                    basePayload["voice_data"] = mapOf(
                        "quality_score" to Random.nextDouble(0.5, 1.0),
                        "duration_ms" to Random.nextInt(100, 5000),
                        "confidence_score" to Random.nextDouble(0.6, 1.0),
                        "verified" to Random.nextBoolean()
                    )
                }
                PayloadType.BEHAVIORAL_DATA -> {
                    basePayload["behavioral_data"] = mapOf(
                        "event_type" to listOf("click", "swipe", "tap", "scroll").random(),
                        "interaction_count" to Random.nextInt(1, 50),
                        "session_duration_ms" to Random.nextInt(1000, 60000)
                    )
                }
                PayloadType.SESSION_DATA -> {
                    basePayload["session_data"] = mapOf(
                        "session_id" to generateCorrelationId(),
                        "status" to listOf("active", "idle", "terminated").random(),
                        "event_count" to Random.nextInt(1, 100)
                    )
                }
                PayloadType.METRICS -> {
                    basePayload["metrics"] = mapOf(
                        "cpu_usage" to Random.nextDouble(0.0, 100.0),
                        "memory_usage" to Random.nextDouble(0.0, 100.0),
                        "network_latency" to Random.nextInt(10, 500)
                    )
                }
                PayloadType.HEARTBEAT -> {
                    basePayload["heartbeat"] = mapOf(
                        "status" to "alive",
                        "uptime_ms" to System.currentTimeMillis()
                    )
                }
                PayloadType.CUSTOM -> {
                    basePayload["custom_data"] = mapOf(
                        "test_field" to "test_value",
                        "random_number" to Random.nextInt()
                    )
                }
            }
        }

        return basePayload
    }

    private fun createWebSocketMessage(
        payload: Map<String, Any>,
        correlationId: String
    ): Map<String, Any> {
        return mapOf(
            "type" to "sync_data",
            "correlation_id" to correlationId,
            "timestamp" to System.currentTimeMillis(),
            "data" to payload
        )
    }

    private fun processReceivedMessage(message: String) {
        try {
            // Basic validation of received messages
            val parsed = json.parseToJsonElement(message)
            // Add validation logic based on scenario.validation config
            logger.trace { "Successfully processed received message" }
        } catch (e: Exception) {
            logger.warn(e) { "Failed to process received message: ${e.message}" }
            recordError("MESSAGE_PROCESSING_FAILED", e.message ?: "Processing error", e.stackTraceToString())
        }
    }

    private suspend fun applyFailureInjection() {
        val injection = scenario.failureInjection

        if (!injection.enabled) return

        // Network delay injection
        injection.networkDelays?.let { delayConfig ->
            if (delayConfig.enabled && Random.nextDouble() < delayConfig.probability) {
                val delayMs = Random.nextInt(
                    delayConfig.rangeMs.start,
                    delayConfig.rangeMs.endInclusive
                )
                logger.debug { "Injecting network delay: ${delayMs}ms" }
                delay(delayMs.toLong())
            }
        }

        // Connection drop injection
        injection.connectionDrops?.let { dropConfig ->
            if (Random.nextDouble() < dropConfig.probability) {
                logger.debug { "Injecting connection drop" }
                throw RuntimeException("Simulated connection drop")
            }
        }
    }

    private fun recordError(type: String, message: String, stackTrace: String?) {
        synchronized(errors) {
            val existing = errors[type]
            if (existing != null) {
                errors[type] = existing.copy(
                    count = existing.count + 1,
                    lastOccurrence = System.currentTimeMillis()
                )
            } else {
                errors[type] = ErrorSummary(
                    errorType = type,
                    errorMessage = message,
                    count = 1,
                    firstOccurrence = System.currentTimeMillis(),
                    lastOccurrence = System.currentTimeMillis(),
                    sampleStackTrace = stackTrace?.take(1000) // Limit stack trace size
                )
            }
        }
        errorCounter.incrementAndGet()
    }

    private fun generateTestResult(
        startTime: Long,
        endTime: Long,
        connectionMetrics: ConnectionMetrics
    ): TestResult {
        val duration = (endTime - startTime) / 1000.0
        val sortedLatencies = latencies.sorted()

        return TestResult(
            scenarioName = scenario.name,
            startTime = startTime,
            endTime = endTime,
            totalMessages = messageCounter.get(),
            successfulMessages = successCounter.get(),
            failedMessages = errorCounter.get(),
            averageLatencyMs = if (latencies.isNotEmpty()) latencies.average() else 0.0,
            p95LatencyMs = if (latencies.isNotEmpty()) {
                sortedLatencies[(sortedLatencies.size * 0.95).toInt()]
            } else 0.0,
            p99LatencyMs = if (latencies.isNotEmpty()) {
                sortedLatencies[(sortedLatencies.size * 0.99).toInt()]
            } else 0.0,
            throughputQps = if (duration > 0) successCounter.get() / duration else 0.0,
            errorRate = if (messageCounter.get() > 0) {
                errorCounter.get().toDouble() / messageCounter.get()
            } else 0.0,
            anomaliesDetected = errors.size,
            connectionMetrics = connectionMetrics,
            errors = errors.values.toList()
        )
    }

    private fun generateCorrelationId(): String {
        return java.util.UUID.randomUUID().toString()
    }

    private fun extractHost(endpoint: String): String {
        return try {
            val url = if (!endpoint.startsWith("ws://") && !endpoint.startsWith("wss://")) {
                "ws://$endpoint"
            } else endpoint
            java.net.URI(url).host ?: "localhost"
        } catch (e: Exception) {
            "localhost"
        }
    }

    private fun extractPort(endpoint: String): Int {
        return try {
            val url = if (!endpoint.startsWith("ws://") && !endpoint.startsWith("wss://")) {
                "ws://$endpoint"
            } else endpoint
            val port = java.net.URI(url).port
            if (port > 0) port else 8000
        } catch (e: Exception) {
            8000
        }
    }

    private fun extractPath(endpoint: String): String {
        return try {
            val url = if (!endpoint.startsWith("ws://") && !endpoint.startsWith("wss://")) {
                "ws://$endpoint"
            } else endpoint
            java.net.URI(url).path ?: "/"
        } catch (e: Exception) {
            "/"
        }
    }
}