package com.intelliwiz.mobile.telemetry.network

import com.intelliwiz.mobile.telemetry.core.StreamTelemetryClient
import com.intelliwiz.mobile.telemetry.core.TelemetryEvent
import okhttp3.Interceptor
import okhttp3.Response
import mu.KotlinLogging
import java.util.*
import kotlin.system.measureTimeMillis

private val logger = KotlinLogging.logger {}

/**
 * Network Interceptor for OkHttp
 *
 * Captures network request/response metrics for performance analysis.
 * Integrates with existing Stream Testbench for anomaly detection.
 */
class NetworkInterceptor(
    private val telemetryClient: StreamTelemetryClient
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val correlationId = UUID.randomUUID().toString()

        // Measure request timing
        var response: Response
        val responseTime = measureTimeMillis {
            response = try {
                chain.proceed(request)
            } catch (e: Exception) {
                recordNetworkEvent(
                    correlationId = correlationId,
                    url = request.url.toString(),
                    method = request.method,
                    latencyMs = -1.0,
                    statusCode = -1,
                    outcome = "error",
                    errorMessage = e.message
                )
                throw e
            }
        }

        // Record successful request
        recordNetworkEvent(
            correlationId = correlationId,
            url = request.url.toString(),
            method = request.method,
            latencyMs = responseTime.toDouble(),
            statusCode = response.code,
            requestSize = request.body?.contentLength() ?: 0,
            responseSize = response.body?.contentLength() ?: 0,
            outcome = if (response.isSuccessful) "success" else "error"
        )

        return response
    }

    /**
     * Record network telemetry event
     */
    private fun recordNetworkEvent(
        correlationId: String,
        url: String,
        method: String,
        latencyMs: Double,
        statusCode: Int,
        requestSize: Long = 0,
        responseSize: Long = 0,
        outcome: String,
        errorMessage: String? = null
    ) {
        val event = TelemetryEvent(
            id = correlationId,
            eventType = "network_request",
            timestamp = System.currentTimeMillis(),
            endpoint = sanitizeUrl(url),
            data = mapOf(
                "method" to method,
                "status_code" to statusCode,
                "request_size_bytes" to requestSize,
                "response_size_bytes" to responseSize,
                "url_pattern" to extractUrlPattern(url)
            ).let { data ->
                if (errorMessage != null) {
                    data + ("error_message" to errorMessage)
                } else data
            },
            latencyMs = latencyMs,
            outcome = outcome
        )

        telemetryClient.queueEvent(event)

        if (latencyMs > 1000 || !outcome.equals("success", ignoreCase = true)) {
            logger.debug { "Network anomaly detected: $method $url (${latencyMs}ms, status: $statusCode)" }
        }
    }

    /**
     * Sanitize URL for PII protection
     */
    private fun sanitizeUrl(url: String): String {
        return try {
            val uri = java.net.URI(url)
            "${uri.scheme}://${uri.host}${uri.path}"
        } catch (e: Exception) {
            url.substringBefore("?") // Remove query parameters as fallback
        }
    }

    /**
     * Extract URL pattern for grouping
     */
    private fun extractUrlPattern(url: String): String {
        return try {
            val uri = java.net.URI(url)
            val path = uri.path ?: "/"

            // Replace numeric IDs with placeholders
            path.replace(Regex("\\d+"), "{id}")
                .replace(Regex("\\{id\\}/\\{id\\}"), "{id}/{id}")
        } catch (e: Exception) {
            "unknown"
        }
    }
}