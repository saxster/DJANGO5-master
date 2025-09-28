package com.streamtestbench.generators

import com.streamtestbench.models.*
import kotlinx.coroutines.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import mu.KotlinLogging
import org.eclipse.paho.client.mqttv3.*
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence
import java.util.concurrent.atomic.AtomicLong
import kotlin.random.Random
import kotlin.system.measureTimeMillis

private val logger = KotlinLogging.logger {}

class MQTTGenerator(
    private val scenario: TestScenario
) : MqttCallback {
    private val messageCounter = AtomicLong(0)
    private val successCounter = AtomicLong(0)
    private val errorCounter = AtomicLong(0)
    private val latencies = mutableListOf<Double>()
    private val errors = mutableMapOf<String, ErrorSummary>()

    private val json = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
    }

    private var mqttClient: MqttClient? = null
    private val connectionMetrics = ConnectionMetrics(0, 0, 0, 0, 0.0)

    // Job tracking for proper lifecycle management
    private var publishingJob: Job? = null

    suspend fun runScenario(): TestResult {
        logger.info { "Starting MQTT scenario: ${scenario.name}" }
        logger.info { "Endpoint: ${scenario.endpoint}" }
        logger.info { "Duration: ${scenario.duration_seconds}s" }

        val startTime = System.currentTimeMillis()

        try {
            // Create MQTT client
            val brokerUrl = normalizeBrokerUrl(scenario.endpoint)
            val clientId = "streamtestbench_${System.currentTimeMillis()}"

            mqttClient = MqttClient(brokerUrl, clientId, MemoryPersistence())
            mqttClient!!.setCallback(this)

            // Connect to MQTT broker
            connectToBroker()

            // Run message publishing
            runMessagePublishing()

            // Wait for scenario duration
            delay(scenario.duration_seconds * 1000L)

        } finally {
            mqttClient?.let { client ->
                try {
                    if (client.isConnected) {
                        client.disconnect()
                        logger.info { "Disconnected from MQTT broker" }
                    }
                    client.close()
                } catch (e: Exception) {
                    logger.error(e) { "Error closing MQTT client: ${e.message}" }
                }
            }
        }

        val endTime = System.currentTimeMillis()
        return generateTestResult(startTime, endTime, connectionMetrics)
    }

    private suspend fun connectToBroker() {
        val connectOptions = MqttConnectOptions().apply {
            isCleanSession = true
            connectionTimeout = 30
            keepAliveInterval = 60

            // Apply authentication if configured
            scenario.authentication?.let { auth ->
                when (auth.type) {
                    AuthType.BASIC_AUTH -> {
                        userName = auth.credentials["username"]
                        password = auth.credentials["password"]?.toCharArray()
                    }
                    AuthType.API_KEY -> {
                        userName = auth.credentials["api_key"]
                        password = auth.credentials["api_secret"]?.toCharArray()
                    }
                    else -> {
                        // No authentication
                    }
                }
            }
        }

        try {
            val connectionStartTime = System.currentTimeMillis()
            mqttClient!!.connect(connectOptions)
            val connectionTime = System.currentTimeMillis() - connectionStartTime

            logger.info { "Connected to MQTT broker in ${connectionTime}ms" }

            // Subscribe to response topic if needed
            subscribeToTopics()

        } catch (e: MqttException) {
            logger.error(e) { "Failed to connect to MQTT broker: ${e.message}" }
            recordError("CONNECTION_FAILED", e.message ?: "Connection failed", e.stackTraceToString())
            throw e
        }
    }

    private fun subscribeToTopics() {
        try {
            // Subscribe to standard response topics
            val responseTopics = arrayOf(
                "response/acknowledgement",
                "response/status",
                "graphql/mutation/status"
            )

            responseTopics.forEach { topic ->
                mqttClient!!.subscribe(topic, 1) // QoS 1
                logger.debug { "Subscribed to topic: $topic" }
            }
        } catch (e: MqttException) {
            logger.error(e) { "Failed to subscribe to topics: ${e.message}" }
            recordError("SUBSCRIPTION_FAILED", e.message ?: "Subscription failed", e.stackTraceToString())
        }
    }

    private suspend fun runMessagePublishing() {
        val messageInterval = (1000.0 / scenario.rates.messagesPerSecond).toLong()
        val topic = extractTopic()

        logger.info { "Publishing to topic: $topic at ${scenario.rates.messagesPerSecond} msgs/sec" }

        try {
            coroutineScope {
                publishingJob = launch {
                    try {
                        while (isActive) {
                            ensureActive() // Explicit cancellation check

                            try {
                                delay(messageInterval)

                                val payload = generatePayload()
                                val message = createMQTTMessage(payload)

                                publishMessage(topic, message)

                                // Apply failure injection
                                applyFailureInjection()

                            } catch (e: CancellationException) {
                                logger.info { "Message publishing cancelled" }
                                throw e // Re-throw to propagate cancellation
                            } catch (e: MqttException) {
                                logger.error(e) { "MQTT error during publishing: ${e.message}" }
                                recordError("MQTT_ERROR", e.message ?: "MQTT error", e.stackTraceToString())
                                delay(1000) // Back-off on MQTT errors
                            } catch (e: java.net.SocketException) {
                                logger.error(e) { "Network error during publishing: ${e.message}" }
                                recordError("NETWORK_ERROR", e.message ?: "Network error", e.stackTraceToString())
                                delay(2000) // Back-off on network errors
                            }
                        }
                    } catch (e: CancellationException) {
                        logger.info { "Publishing job cancelled gracefully" }
                        throw e
                    }
                }
            }
        } catch (e: CancellationException) {
            logger.info { "Message publishing coroutine scope cancelled" }
            throw e
        } catch (e: Exception) {
            logger.error(e) { "Message publishing loop failed: ${e.message}" }
            recordError("PUBLISHING_FAILED", e.message ?: "Publishing failed", e.stackTraceToString())
        }
    }

    /**
     * Stop message publishing (graceful cancellation)
     */
    fun stopPublishing() {
        logger.info { "Stopping message publishing" }
        publishingJob?.cancel()
        publishingJob = null
        logger.info { "Message publishing stopped" }
    }

    private fun publishMessage(topic: String, messagePayload: Map<String, Any>) {
        try {
            val jsonPayload = json.encodeToString(messagePayload)
            val message = MqttMessage(jsonPayload.toByteArray()).apply {
                qos = 1 // QoS 1 for at-least-once delivery
                isRetained = false
            }

            val publishStartTime = System.currentTimeMillis()

            mqttClient!!.publish(topic, message)

            val latency = System.currentTimeMillis() - publishStartTime

            synchronized(latencies) {
                latencies.add(latency.toDouble())
            }

            messageCounter.incrementAndGet()
            successCounter.incrementAndGet()

            logger.trace { "Published message to $topic: ${jsonPayload.take(100)}..." }

        } catch (e: MqttException) {
            logger.error(e) { "Failed to publish message: ${e.message}" }
            recordError("PUBLISH_FAILED", e.message ?: "Publish failed", e.stackTraceToString())
            errorCounter.incrementAndGet()
        }
    }

    private fun generatePayload(): Map<String, Any> {
        val basePayload = mutableMapOf<String, Any>(
            "timestamp" to System.currentTimeMillis(),
            "messageId" to generateCorrelationId(),
            "clientId" to (mqttClient?.clientId ?: "unknown")
        )

        scenario.payloads.forEach { payloadType ->
            when (payloadType) {
                PayloadType.VOICE_DATA -> {
                    basePayload["voiceData"] = mapOf(
                        "qualityScore" to Random.nextDouble(0.5, 1.0),
                        "durationMs" to Random.nextInt(100, 5000),
                        "confidenceScore" to Random.nextDouble(0.6, 1.0)
                    )
                }
                PayloadType.BEHAVIORAL_DATA -> {
                    basePayload["behavioralData"] = mapOf(
                        "eventType" to listOf("interaction", "navigation", "task_completion").random(),
                        "interactionCount" to Random.nextInt(1, 50),
                        "sessionDurationMs" to Random.nextInt(1000, 60000)
                    )
                }
                PayloadType.SESSION_DATA -> {
                    basePayload["sessionData"] = mapOf(
                        "sessionId" to generateCorrelationId(),
                        "status" to listOf("active", "idle", "terminated").random(),
                        "eventCount" to Random.nextInt(1, 100)
                    )
                }
                PayloadType.METRICS -> {
                    basePayload["metrics"] = mapOf(
                        "cpuUsage" to Random.nextDouble(0.0, 100.0),
                        "memoryUsage" to Random.nextDouble(0.0, 100.0),
                        "networkLatency" to Random.nextInt(10, 500)
                    )
                }
                PayloadType.HEARTBEAT -> {
                    basePayload["heartbeat"] = mapOf(
                        "status" to "alive",
                        "uptimeMs" to System.currentTimeMillis()
                    )
                }
                PayloadType.CUSTOM -> {
                    basePayload["customData"] = mapOf(
                        "testField" to "testValue",
                        "randomNumber" to Random.nextInt()
                    )
                }
            }
        }

        return basePayload
    }

    private fun createMQTTMessage(payload: Map<String, Any>): Map<String, Any> {
        return mapOf(
            "serviceName" to "streamtestbench",
            "uuids" to listOf(generateCorrelationId()),
            "query" to "mutation { processStreamData(input: \$input) { success message } }",
            "variables" to mapOf("input" to payload),
            "timestamp" to System.currentTimeMillis()
        )
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

        // Duplicate message injection
        injection.duplicateMessages?.let { dupConfig ->
            if (Random.nextDouble() < dupConfig.probability) {
                val duplicates = Random.nextInt(1, dupConfig.maxDuplicates + 1)
                logger.debug { "Injecting $duplicates duplicate messages" }

                repeat(duplicates) {
                    delay(Random.nextLong(10, 100)) // Small delay between duplicates
                    val payload = generatePayload()
                    val message = createMQTTMessage(payload)
                    publishMessage(extractTopic(), message)
                }
            }
        }
    }

    private fun extractTopic(): String {
        // Default to GraphQL mutation topic if not specified
        return "graphql/mutation"
    }

    private fun normalizeBrokerUrl(endpoint: String): String {
        return if (endpoint.startsWith("tcp://") || endpoint.startsWith("ssl://")) {
            endpoint
        } else {
            "tcp://$endpoint"
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
                    sampleStackTrace = stackTrace?.take(1000)
                )
            }
        }
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

    // MqttCallback interface implementations
    override fun connectionLost(cause: Throwable?) {
        logger.warn(cause) { "MQTT connection lost: ${cause?.message}" }
        recordError("CONNECTION_LOST", cause?.message ?: "Connection lost", cause?.stackTraceToString())
    }

    override fun messageArrived(topic: String?, message: MqttMessage?) {
        if (topic != null && message != null) {
            val payload = String(message.payload)
            logger.trace { "Received message on topic $topic: ${payload.take(100)}..." }

            // Process response message for validation
            processReceivedMessage(topic, payload)
        }
    }

    override fun deliveryComplete(token: IMqttDeliveryToken?) {
        logger.trace { "Message delivery completed: ${token?.messageId}" }
    }

    private fun processReceivedMessage(topic: String, message: String) {
        try {
            // Basic validation of received messages
            val parsed = json.parseToJsonElement(message)
            logger.trace { "Successfully processed message from topic: $topic" }
        } catch (e: Exception) {
            logger.warn(e) { "Failed to process received message from topic $topic: ${e.message}" }
            recordError("MESSAGE_PROCESSING_FAILED", e.message ?: "Processing error", e.stackTraceToString())
        }
    }
}