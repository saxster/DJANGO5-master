package com.intelliwiz.mobile.telemetry.coroutines

import kotlinx.coroutines.*
import mu.KotlinLogging
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.min
import kotlin.math.pow
import kotlin.random.Random

private val logger = KotlinLogging.logger {}

/**
 * Smart Reconnection Manager
 *
 * Intelligent reconnection strategy with exponential backoff, jitter, and circuit breaker pattern.
 * Prevents network flooding during outages and adapts to changing network conditions.
 *
 * Features:
 * - Exponential backoff with configurable base delay
 * - Jitter to prevent thundering herd
 * - Circuit breaker to stop reconnection attempts during sustained failures
 * - Health check before reconnection attempts
 * - Connection state tracking and metrics
 *
 * Usage:
 * ```kotlin
 * val manager = SmartReconnectionManager(
 *     componentName = "WebSocket",
 *     baseDelayMs = 1000,
 *     maxAttempts = 5
 * )
 *
 * manager.reconnect(scope) {
 *     // Connection logic here
 *     connectToServer()
 * }
 * ```
 */
class SmartReconnectionManager(
    private val componentName: String,
    private val baseDelayMs: Long = 1000,
    private val maxDelayMs: Long = 32000,
    private val maxAttempts: Int = 5,
    private val jitterFactor: Double = 0.3,
    private val circuitBreakerThreshold: Int = 10,
    private val healthCheckBeforeReconnect: Boolean = true
) {

    private val attemptCount = AtomicInteger(0)
    private val consecutiveFailures = AtomicInteger(0)
    private val totalReconnects = AtomicLong(0)
    private val successfulReconnects = AtomicLong(0)
    private val lastReconnectTime = AtomicLong(0)
    private val lastSuccessTime = AtomicLong(0)

    private val isReconnecting = AtomicBoolean(false)
    private val circuitBreakerOpen = AtomicBoolean(false)

    private var reconnectionJob: Job? = null
    private val jobLock = Any()

    /**
     * Attempt reconnection with exponential backoff
     */
    suspend fun reconnect(
        scope: CoroutineScope,
        onStateChange: ((ReconnectionState) -> Unit)? = null,
        healthCheck: (suspend () -> Boolean)? = null,
        connectAction: suspend () -> Unit
    ) {
        synchronized(jobLock) {
            if (isReconnecting.get()) {
                logger.warn { "$componentName: Already reconnecting, ignoring new reconnect request" }
                return
            }

            if (circuitBreakerOpen.get()) {
                logger.warn { "$componentName: Circuit breaker is open, refusing reconnection attempt" }
                onStateChange?.invoke(ReconnectionState.CIRCUIT_BREAKER_OPEN)
                return
            }

            isReconnecting.set(true)
            attemptCount.set(0)

            reconnectionJob = scope.launch {
                try {
                    performReconnectionAttempts(onStateChange, healthCheck, connectAction)
                } finally {
                    isReconnecting.set(false)
                }
            }
        }
    }

    /**
     * Perform reconnection attempts with backoff
     */
    private suspend fun performReconnectionAttempts(
        onStateChange: ((ReconnectionState) -> Unit)?,
        healthCheck: (suspend () -> Boolean)?,
        connectAction: suspend () -> Unit
    ) {
        while (attemptCount.get() < maxAttempts && isActive) {
            val currentAttempt = attemptCount.incrementAndGet()
            logger.info { "$componentName: Reconnection attempt $currentAttempt of $maxAttempts" }

            onStateChange?.invoke(ReconnectionState.ATTEMPTING(currentAttempt, maxAttempts))

            try {
                // Optional health check before attempting
                if (healthCheckBeforeReconnect && healthCheck != null) {
                    if (!healthCheck()) {
                        logger.warn { "$componentName: Health check failed, skipping reconnection" }
                        delay(baseDelayMs)
                        continue
                    }
                }

                // Attempt connection
                withTimeout(30000) { // 30 second timeout
                    connectAction()
                }

                // Success!
                onReconnectSuccess()
                onStateChange?.invoke(ReconnectionState.CONNECTED)
                logger.info { "$componentName: Reconnection successful on attempt $currentAttempt" }
                return

            } catch (e: TimeoutCancellationException) {
                logger.warn(e) { "$componentName: Reconnection attempt timed out" }
                onReconnectFailure()
                onStateChange?.invoke(ReconnectionState.TIMEOUT)
            } catch (e: CancellationException) {
                logger.info { "$componentName: Reconnection cancelled" }
                onStateChange?.invoke(ReconnectionState.CANCELLED)
                throw e
            } catch (e: Exception) {
                logger.error(e) { "$componentName: Reconnection attempt failed: ${e.message}" }
                onReconnectFailure()
                onStateChange?.invoke(ReconnectionState.FAILED(e))
            }

            // Check if we should stop trying
            if (currentAttempt >= maxAttempts) {
                logger.error { "$componentName: Max reconnection attempts ($maxAttempts) reached" }
                onStateChange?.invoke(ReconnectionState.MAX_ATTEMPTS_REACHED)
                break
            }

            // Check circuit breaker
            if (circuitBreakerOpen.get()) {
                logger.warn { "$componentName: Circuit breaker opened, stopping reconnection attempts" }
                onStateChange?.invoke(ReconnectionState.CIRCUIT_BREAKER_OPEN)
                break
            }

            // Calculate delay with exponential backoff and jitter
            val backoffDelay = calculateBackoffDelay(currentAttempt)
            logger.debug { "$componentName: Waiting ${backoffDelay}ms before next attempt" }
            onStateChange?.invoke(ReconnectionState.BACKOFF(backoffDelay))

            delay(backoffDelay)
        }
    }

    /**
     * Calculate backoff delay with exponential backoff and jitter
     */
    private fun calculateBackoffDelay(attempt: Int): Long {
        // Exponential backoff: baseDelay * 2^(attempt-1)
        val exponentialDelay = baseDelayMs * 2.0.pow(attempt - 1).toLong()

        // Cap at max delay
        val cappedDelay = min(exponentialDelay, maxDelayMs)

        // Add jitter (±30% by default)
        val jitter = (cappedDelay * jitterFactor * (Random.nextDouble() * 2 - 1)).toLong()
        val finalDelay = cappedDelay + jitter

        return finalDelay.coerceAtLeast(baseDelayMs)
    }

    /**
     * Handle successful reconnection
     */
    private fun onReconnectSuccess() {
        lastReconnectTime.set(System.currentTimeMillis())
        lastSuccessTime.set(System.currentTimeMillis())
        totalReconnects.incrementAndGet()
        successfulReconnects.incrementAndGet()

        // Reset failure counters
        consecutiveFailures.set(0)
        attemptCount.set(0)

        // Close circuit breaker if it was open
        if (circuitBreakerOpen.get()) {
            logger.info { "$componentName: Circuit breaker closed after successful reconnection" }
            circuitBreakerOpen.set(false)
        }
    }

    /**
     * Handle reconnection failure
     */
    private fun onReconnectFailure() {
        lastReconnectTime.set(System.currentTimeMillis())
        totalReconnects.incrementAndGet()

        val failures = consecutiveFailures.incrementAndGet()

        // Open circuit breaker if threshold reached
        if (failures >= circuitBreakerThreshold && !circuitBreakerOpen.get()) {
            logger.error { "$componentName: Opening circuit breaker after $failures consecutive failures" }
            circuitBreakerOpen.set(true)
        }
    }

    /**
     * Stop reconnection attempts
     */
    fun stop() {
        synchronized(jobLock) {
            logger.info { "$componentName: Stopping reconnection manager" }
            reconnectionJob?.cancel()
            reconnectionJob = null
            isReconnecting.set(false)
        }
    }

    /**
     * Reset circuit breaker (manual intervention)
     */
    fun resetCircuitBreaker() {
        logger.info { "$componentName: Manually resetting circuit breaker" }
        circuitBreakerOpen.set(false)
        consecutiveFailures.set(0)
    }

    /**
     * Reset all metrics
     */
    fun reset() {
        attemptCount.set(0)
        consecutiveFailures.set(0)
        circuitBreakerOpen.set(false)
        logger.info { "$componentName: Reconnection manager reset" }
    }

    /**
     * Get current reconnection metrics
     */
    fun getMetrics(): ReconnectionMetrics {
        return ReconnectionMetrics(
            componentName = componentName,
            isReconnecting = isReconnecting.get(),
            currentAttempt = attemptCount.get(),
            maxAttempts = maxAttempts,
            totalReconnects = totalReconnects.get(),
            successfulReconnects = successfulReconnects.get(),
            failedReconnects = totalReconnects.get() - successfulReconnects.get(),
            consecutiveFailures = consecutiveFailures.get(),
            circuitBreakerOpen = circuitBreakerOpen.get(),
            lastReconnectTime = lastReconnectTime.get(),
            lastSuccessTime = lastSuccessTime.get(),
            successRate = if (totalReconnects.get() > 0) {
                (successfulReconnects.get().toDouble() / totalReconnects.get().toDouble()) * 100
            } else 0.0
        )
    }

    /**
     * Check if reconnection is in progress
     */
    fun isReconnecting(): Boolean = isReconnecting.get()

    /**
     * Check if circuit breaker is open
     */
    fun isCircuitBreakerOpen(): Boolean = circuitBreakerOpen.get()
}

/**
 * Reconnection state
 */
sealed class ReconnectionState {
    object CONNECTED : ReconnectionState()
    data class ATTEMPTING(val attempt: Int, val maxAttempts: Int) : ReconnectionState()
    data class BACKOFF(val delayMs: Long) : ReconnectionState()
    data class FAILED(val error: Exception) : ReconnectionState()
    object TIMEOUT : ReconnectionState()
    object CANCELLED : ReconnectionState()
    object MAX_ATTEMPTS_REACHED : ReconnectionState()
    object CIRCUIT_BREAKER_OPEN : ReconnectionState()
}

/**
 * Reconnection metrics for monitoring
 */
data class ReconnectionMetrics(
    val componentName: String,
    val isReconnecting: Boolean,
    val currentAttempt: Int,
    val maxAttempts: Int,
    val totalReconnects: Long,
    val successfulReconnects: Long,
    val failedReconnects: Long,
    val consecutiveFailures: Int,
    val circuitBreakerOpen: Boolean,
    val lastReconnectTime: Long,
    val lastSuccessTime: Long,
    val successRate: Double
)