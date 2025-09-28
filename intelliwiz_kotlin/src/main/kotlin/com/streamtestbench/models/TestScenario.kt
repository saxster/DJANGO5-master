package com.streamtestbench.models

import kotlinx.serialization.Serializable

@Serializable
data class TestScenario(
    val name: String,
    val description: String = "",
    val protocol: Protocol,
    val endpoint: String,
    val duration_seconds: Int,
    val connections: Int = 1,
    val rates: RateConfig,
    val payloads: List<PayloadType>,
    val failureInjection: FailureInjectionConfig = FailureInjectionConfig(),
    val authentication: AuthConfig? = null,
    val validation: ValidationConfig = ValidationConfig()
)

@Serializable
enum class Protocol {
    WEBSOCKET, MQTT, HTTP, MIXED
}

@Serializable
data class RateConfig(
    val messagesPerSecond: Double,
    val burstMultiplier: Double = 1.0,
    val rampUpSeconds: Int = 10,
    val rampDownSeconds: Int = 10
)

@Serializable
enum class PayloadType {
    VOICE_DATA, BEHAVIORAL_DATA, SESSION_DATA, METRICS, HEARTBEAT, CUSTOM
}

@Serializable
data class FailureInjectionConfig(
    val enabled: Boolean = false,
    val networkDelays: NetworkDelayConfig? = null,
    val duplicateMessages: DuplicateConfig? = null,
    val schemaDrift: SchemaDriftConfig? = null,
    val connectionDrops: ConnectionDropConfig? = null
)

@Serializable
data class NetworkDelayConfig(
    val enabled: Boolean,
    val rangeMs: IntRange,
    val probability: Double = 0.05
) {
    @Serializable
    data class IntRange(val start: Int, val endInclusive: Int)
}

@Serializable
data class DuplicateConfig(
    val probability: Double = 0.01,
    val maxDuplicates: Int = 3
)

@Serializable
data class SchemaDriftConfig(
    val probability: Double = 0.001,
    val mutations: List<SchemaMutation> = emptyList()
)

@Serializable
data class SchemaMutation(
    val type: MutationType,
    val fieldPath: String,
    val newValue: String? = null
)

@Serializable
enum class MutationType {
    ADD_FIELD, REMOVE_FIELD, CHANGE_TYPE, RENAME_FIELD
}

@Serializable
data class ConnectionDropConfig(
    val probability: Double = 0.001,
    val reconnectDelayMs: Int = 1000
)

@Serializable
data class AuthConfig(
    val type: AuthType,
    val credentials: Map<String, String>
)

@Serializable
enum class AuthType {
    BEARER_TOKEN, BASIC_AUTH, API_KEY, NONE
}

@Serializable
data class ValidationConfig(
    val validateResponses: Boolean = true,
    val expectedStatusCodes: List<Int> = listOf(200, 201, 202),
    val maxLatencyMs: Int = 1000,
    val requiredFields: List<String> = emptyList()
)

@Serializable
data class TestResult(
    val scenarioName: String,
    val startTime: Long,
    val endTime: Long,
    val totalMessages: Long,
    val successfulMessages: Long,
    val failedMessages: Long,
    val averageLatencyMs: Double,
    val p95LatencyMs: Double,
    val p99LatencyMs: Double,
    val throughputQps: Double,
    val errorRate: Double,
    val anomaliesDetected: Int,
    val connectionMetrics: ConnectionMetrics,
    val errors: List<ErrorSummary>
)

@Serializable
data class ConnectionMetrics(
    val totalConnections: Int,
    val successfulConnections: Int,
    val failedConnections: Int,
    val reconnectionCount: Int,
    val averageConnectionTime: Double
)

@Serializable
data class ErrorSummary(
    val errorType: String,
    val errorMessage: String,
    val count: Int,
    val firstOccurrence: Long,
    val lastOccurrence: Long,
    val sampleStackTrace: String? = null
)