package com.intelliwiz.mobile.telemetry.pii

import com.intelliwiz.mobile.telemetry.core.TelemetryEvent
import kotlinx.serialization.json.*
import mu.KotlinLogging
import java.security.MessageDigest

private val logger = KotlinLogging.logger {}

/**
 * PII Redaction System
 *
 * Mirrors Django's PII redaction rules from StreamEvent model.
 * Ensures compliance with privacy requirements while maintaining telemetry value.
 */
class PIIRedactor(
    private val redactionRules: Map<String, Any>
) {
    // Default mobile-specific PII rules (aligned with existing Django rules)
    private val defaultMobileRules = mapOf(
        "allowlisted_fields" to listOf(
            "timestamp", "event_type", "latency_ms", "status_code",
            "method", "frame_time_ms", "composition_time_ms", "jank_severity",
            "network_type", "battery_level", "memory_pressure", "device_model",
            "os_version", "app_version"
        ),
        "hash_fields" to listOf(
            "user_id", "device_id", "session_id", "correlation_id", "ip_address"
        ),
        "remove_fields" to listOf(
            "personal_data", "location", "precise_location", "contacts",
            "photos", "audio_data", "biometric_data", "password", "token"
        )
    )

    private val effectiveRules = if (redactionRules.isEmpty()) defaultMobileRules else redactionRules

    /**
     * Sanitize telemetry event (mirrors Django StreamEvent PII protection)
     */
    fun sanitize(event: TelemetryEvent): TelemetryEvent {
        return try {
            val sanitizedData = sanitizeMap(event.data)

            event.copy(
                data = sanitizedData,
                // Hash correlation ID for privacy while maintaining trackability
                id = if (shouldHashField("correlation_id")) {
                    hashValue(event.id)
                } else event.id
            )
        } catch (e: Exception) {
            logger.error(e) { "Failed to sanitize telemetry event: ${e.message}" }
            // Return minimal safe event on error
            event.copy(
                data = mapOf(
                    "event_type" to event.eventType,
                    "timestamp" to event.timestamp,
                    "sanitization_error" to "true"
                )
            )
        }
    }

    /**
     * Sanitize map data structure
     */
    private fun sanitizeMap(data: Map<String, Any>): Map<String, Any> {
        val allowlistedFields = getRule("allowlisted_fields") as? List<*> ?: emptyList<String>()
        val hashFields = getRule("hash_fields") as? List<*> ?: emptyList<String>()
        val removeFields = getRule("remove_fields") as? List<*> ?: emptyList<String>()

        return data.mapNotNull { (key, value) ->
            when {
                // Remove sensitive fields entirely
                removeFields.contains(key) -> {
                    logger.debug { "Removed sensitive field: $key" }
                    null
                }

                // Hash fields that need to maintain correlation
                hashFields.contains(key) -> {
                    key to hashValue(value.toString())
                }

                // Keep allowlisted fields as-is
                allowlistedFields.contains(key) -> {
                    key to sanitizeValue(value)
                }

                // For unknown fields, apply conservative approach
                else -> {
                    if (isPotentiallySensitive(key, value)) {
                        logger.debug { "Hashed potentially sensitive field: $key" }
                        key to hashValue(value.toString())
                    } else {
                        key to sanitizeValue(value)
                    }
                }
            }
        }.toMap()
    }

    /**
     * Sanitize individual values
     */
    private fun sanitizeValue(value: Any): Any {
        return when (value) {
            is Map<*, *> -> {
                @Suppress("UNCHECKED_CAST")
                sanitizeMap(value as Map<String, Any>)
            }
            is List<*> -> {
                value.map { if (it is Map<*, *>) sanitizeMap(it as Map<String, Any>) else it }
            }
            is String -> {
                if (value.length > 1000) {
                    // Truncate very long strings to prevent data exfiltration
                    value.take(1000) + "...[truncated]"
                } else {
                    value
                }
            }
            else -> value
        }
    }

    /**
     * Check if field is potentially sensitive based on name or content
     */
    private fun isPotentiallySensitive(fieldName: String, value: Any): Boolean {
        val sensitivePatterns = listOf(
            "password", "token", "secret", "key", "auth", "credential",
            "email", "phone", "address", "name", "personal", "private",
            "location", "gps", "coordinate", "biometric", "fingerprint"
        )

        val fieldLower = fieldName.lowercase()

        // Check field name
        val hasSensitiveName = sensitivePatterns.any { pattern ->
            fieldLower.contains(pattern)
        }

        // Check value content (if string)
        val hasSensitiveContent = if (value is String && value.length > 10) {
            // Look for patterns that might be sensitive data
            value.matches(Regex(".*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}.*")) || // Email pattern
            value.matches(Regex(".*\\+?[1-9]\\d{1,14}.*")) || // Phone number pattern
            value.contains("password", ignoreCase = true) ||
            value.contains("token", ignoreCase = true)
        } else false

        return hasSensitiveName || hasSensitiveContent
    }

    /**
     * Hash sensitive value while preserving ability to correlate
     */
    private fun hashValue(value: String): String {
        return try {
            val digest = MessageDigest.getInstance("SHA-256")
            val hashBytes = digest.digest(value.toByteArray())
            hashBytes.joinToString("") { "%02x".format(it) }.take(16) // First 16 chars of hash
        } catch (e: Exception) {
            logger.error(e) { "Failed to hash value: ${e.message}" }
            "hash_error"
        }
    }

    /**
     * Check if field should be hashed
     */
    private fun shouldHashField(fieldName: String): Boolean {
        val hashFields = getRule("hash_fields") as? List<*> ?: emptyList<String>()
        return hashFields.contains(fieldName)
    }

    /**
     * Get redaction rule
     */
    private fun getRule(ruleName: String): Any? {
        return effectiveRules[ruleName]
    }

    /**
     * Generate payload schema hash for anomaly detection (mirrors Django pattern)
     */
    fun generateSchemaHash(data: Map<String, Any>): String {
        return try {
            val schema = extractSchema(data)
            val schemaString = schema.sorted().joinToString(",")
            hashValue(schemaString).take(16)
        } catch (e: Exception) {
            logger.error(e) { "Failed to generate schema hash: ${e.message}" }
            "schema_error"
        }
    }

    /**
     * Extract schema structure from data
     */
    private fun extractSchema(data: Map<String, Any>): List<String> {
        return data.map { (key, value) ->
            val type = when (value) {
                is String -> "string"
                is Number -> "number"
                is Boolean -> "boolean"
                is Map<*, *> -> "object"
                is List<*> -> "array"
                else -> "unknown"
            }
            "$key:$type"
        }
    }
}