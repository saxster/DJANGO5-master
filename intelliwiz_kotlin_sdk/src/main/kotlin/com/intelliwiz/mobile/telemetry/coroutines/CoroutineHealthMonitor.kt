package com.intelliwiz.mobile.telemetry.coroutines

import kotlinx.coroutines.*
import mu.KotlinLogging
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong
import kotlin.system.measureTimeMillis

private val logger = KotlinLogging.logger {}

/**
 * Coroutine Health Monitor
 *
 * Real-time monitoring and alerting system for coroutine lifecycle health.
 * Detects memory leaks, orphaned coroutines, and performance issues.
 *
 * Features:
 * - Track active coroutines per component
 * - Detect coroutine leaks (coroutines that should have been cancelled)
 * - Monitor cancellation success rates
 * - Alert on suspicious patterns
 * - Performance metrics (launch time, completion time)
 *
 * Usage:
 * ```kotlin
 * val monitor = CoroutineHealthMonitor.getInstance()
 *
 * val job = scope.launch {
 *     monitor.trackCoroutine("telemetry-worker") {
 *         // Work here
 *     }
 * }
 *
 * // Later: check for leaks
 * val report = monitor.generateHealthReport()
 * ```
 */
class CoroutineHealthMonitor private constructor() {

    companion object {
        @Volatile
        private var INSTANCE: CoroutineHealthMonitor? = null

        fun getInstance(): CoroutineHealthMonitor {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: CoroutineHealthMonitor().also { INSTANCE = it }
            }
        }

        private const val LEAK_THRESHOLD_MS = 60000L // 1 minute
        private const val WARNING_THRESHOLD_ACTIVE = 100 // 100 active coroutines
    }

    private val activeCoroutines = ConcurrentHashMap<String, CoroutineInfo>()
    private val completedCoroutines = ConcurrentHashMap<String, CompletedCoroutineInfo>()

    private val totalLaunched = AtomicLong(0)
    private val totalCompleted = AtomicLong(0)
    private val totalCancelled = AtomicLong(0)
    private val totalFailed = AtomicLong(0)

    private val scopeManager = CoroutineScopeManager.getInstance()
    private val monitorScope = scopeManager.getOrCreate("health-monitor", Dispatchers.Default)

    /**
     * Track a coroutine for health monitoring
     */
    suspend fun <T> trackCoroutine(
        componentName: String,
        block: suspend CoroutineScope.() -> T
    ): T {
        val coroutineId = generateCoroutineId()
        val startTime = System.currentTimeMillis()

        val info = CoroutineInfo(
            id = coroutineId,
            componentName = componentName,
            launchedAt = startTime,
            threadName = Thread.currentThread().name
        )

        activeCoroutines[coroutineId] = info
        totalLaunched.incrementAndGet()

        logger.debug { "Tracking coroutine: $componentName ($coroutineId)" }

        return try {
            coroutineScope {
                val result: T
                val executionTime = measureTimeMillis {
                    result = block()
                }

                onCoroutineCompleted(coroutineId, executionTime, null)
                result
            }
        } catch (e: CancellationException) {
            onCoroutineCancelled(coroutineId, System.currentTimeMillis() - startTime)
            throw e
        } catch (e: Exception) {
            onCoroutineFailed(coroutineId, System.currentTimeMillis() - startTime, e)
            throw e
        }
    }

    /**
     * Register a Job for tracking
     */
    fun registerJob(componentName: String, job: Job): String {
        val coroutineId = generateCoroutineId()
        val startTime = System.currentTimeMillis()

        val info = CoroutineInfo(
            id = coroutineId,
            componentName = componentName,
            launchedAt = startTime,
            threadName = Thread.currentThread().name
        )

        activeCoroutines[coroutineId] = info
        totalLaunched.incrementAndGet()

        job.invokeOnCompletion { throwable ->
            val executionTime = System.currentTimeMillis() - startTime

            when {
                throwable is CancellationException -> {
                    onCoroutineCancelled(coroutineId, executionTime)
                }
                throwable != null -> {
                    onCoroutineFailed(coroutineId, executionTime, throwable)
                }
                else -> {
                    onCoroutineCompleted(coroutineId, executionTime, null)
                }
            }
        }

        logger.debug { "Registered job: $componentName ($coroutineId)" }
        return coroutineId
    }

    /**
     * Unregister a coroutine (manual completion tracking)
     */
    fun unregisterCoroutine(coroutineId: String) {
        activeCoroutines.remove(coroutineId)?.let { info ->
            val executionTime = System.currentTimeMillis() - info.launchedAt
            onCoroutineCompleted(coroutineId, executionTime, null)
        }
    }

    /**
     * Handle coroutine completion
     */
    private fun onCoroutineCompleted(coroutineId: String, executionTimeMs: Long, result: Any?) {
        activeCoroutines.remove(coroutineId)?.let { info ->
            val completed = CompletedCoroutineInfo(
                info = info,
                completedAt = System.currentTimeMillis(),
                executionTimeMs = executionTimeMs,
                outcome = CoroutineOutcome.COMPLETED,
                error = null
            )

            completedCoroutines[coroutineId] = completed
            totalCompleted.incrementAndGet()

            logger.debug { "Coroutine completed: ${info.componentName} (${executionTimeMs}ms)" }

            // Cleanup old completed entries
            cleanupCompletedCoroutines()
        }
    }

    /**
     * Handle coroutine cancellation
     */
    private fun onCoroutineCancelled(coroutineId: String, executionTimeMs: Long) {
        activeCoroutines.remove(coroutineId)?.let { info ->
            val completed = CompletedCoroutineInfo(
                info = info,
                completedAt = System.currentTimeMillis(),
                executionTimeMs = executionTimeMs,
                outcome = CoroutineOutcome.CANCELLED,
                error = null
            )

            completedCoroutines[coroutineId] = completed
            totalCancelled.incrementAndGet()

            logger.debug { "Coroutine cancelled: ${info.componentName} (${executionTimeMs}ms)" }
        }
    }

    /**
     * Handle coroutine failure
     */
    private fun onCoroutineFailed(coroutineId: String, executionTimeMs: Long, error: Throwable) {
        activeCoroutines.remove(coroutineId)?.let { info ->
            val completed = CompletedCoroutineInfo(
                info = info,
                completedAt = System.currentTimeMillis(),
                executionTimeMs = executionTimeMs,
                outcome = CoroutineOutcome.FAILED,
                error = error.message
            )

            completedCoroutines[coroutineId] = completed
            totalFailed.incrementAndGet()

            logger.error { "Coroutine failed: ${info.componentName} - ${error.message}" }
        }
    }

    /**
     * Detect potential coroutine leaks
     */
    fun detectLeaks(): List<LeakInfo> {
        val now = System.currentTimeMillis()
        val leaks = mutableListOf<LeakInfo>()

        activeCoroutines.values.forEach { info ->
            val age = now - info.launchedAt

            if (age > LEAK_THRESHOLD_MS) {
                leaks.add(
                    LeakInfo(
                        coroutineId = info.id,
                        componentName = info.componentName,
                        ageMs = age,
                        launchedAt = info.launchedAt,
                        threadName = info.threadName
                    )
                )
            }
        }

        if (leaks.isNotEmpty()) {
            logger.warn { "Detected ${leaks.size} potential coroutine leaks" }
        }

        return leaks
    }

    /**
     * Generate comprehensive health report
     */
    fun generateHealthReport(): HealthReport {
        val activeCount = activeCoroutines.size
        val leaks = detectLeaks()

        val componentBreakdown = activeCoroutines.values
            .groupBy { it.componentName }
            .mapValues { it.value.size }

        val avgExecutionTime = if (completedCoroutines.isNotEmpty()) {
            completedCoroutines.values.map { it.executionTimeMs }.average()
        } else 0.0

        val successRate = if (totalLaunched.get() > 0) {
            (totalCompleted.get().toDouble() / totalLaunched.get().toDouble()) * 100
        } else 0.0

        val cancellationRate = if (totalLaunched.get() > 0) {
            (totalCancelled.get().toDouble() / totalLaunched.get().toDouble()) * 100
        } else 0.0

        val isHealthy = activeCount < WARNING_THRESHOLD_ACTIVE &&
                leaks.isEmpty() &&
                totalFailed.get() < (totalLaunched.get() * 0.05) // < 5% failure rate

        return HealthReport(
            timestamp = System.currentTimeMillis(),
            activeCoroutines = activeCount,
            totalLaunched = totalLaunched.get(),
            totalCompleted = totalCompleted.get(),
            totalCancelled = totalCancelled.get(),
            totalFailed = totalFailed.get(),
            leaksDetected = leaks.size,
            leakDetails = leaks,
            componentBreakdown = componentBreakdown,
            averageExecutionTimeMs = avgExecutionTime,
            successRate = successRate,
            cancellationRate = cancellationRate,
            isHealthy = isHealthy
        )
    }

    /**
     * Get active coroutines for a specific component
     */
    fun getActiveCoroutinesForComponent(componentName: String): List<CoroutineInfo> {
        return activeCoroutines.values.filter { it.componentName == componentName }
    }

    /**
     * Clean up old completed coroutine records (keep last 1000)
     */
    private fun cleanupCompletedCoroutines() {
        if (completedCoroutines.size > 1000) {
            val sorted = completedCoroutines.values.sortedBy { it.completedAt }
            val toRemove = sorted.take(sorted.size - 1000)

            toRemove.forEach { completedCoroutines.remove(it.info.id) }

            logger.debug { "Cleaned up ${toRemove.size} old completed coroutine records" }
        }
    }

    /**
     * Reset all metrics
     */
    fun reset() {
        activeCoroutines.clear()
        completedCoroutines.clear()
        totalLaunched.set(0)
        totalCompleted.set(0)
        totalCancelled.set(0)
        totalFailed.set(0)
        logger.info { "Health monitor metrics reset" }
    }

    private fun generateCoroutineId(): String {
        return "coroutine-${System.currentTimeMillis()}-${(Math.random() * 10000).toInt()}"
    }
}

/**
 * Information about an active coroutine
 */
data class CoroutineInfo(
    val id: String,
    val componentName: String,
    val launchedAt: Long,
    val threadName: String
)

/**
 * Information about a completed coroutine
 */
data class CompletedCoroutineInfo(
    val info: CoroutineInfo,
    val completedAt: Long,
    val executionTimeMs: Long,
    val outcome: CoroutineOutcome,
    val error: String?
)

/**
 * Coroutine completion outcome
 */
enum class CoroutineOutcome {
    COMPLETED,
    CANCELLED,
    FAILED
}

/**
 * Information about a potential coroutine leak
 */
data class LeakInfo(
    val coroutineId: String,
    val componentName: String,
    val ageMs: Long,
    val launchedAt: Long,
    val threadName: String
)

/**
 * Comprehensive health report
 */
data class HealthReport(
    val timestamp: Long,
    val activeCoroutines: Int,
    val totalLaunched: Long,
    val totalCompleted: Long,
    val totalCancelled: Long,
    val totalFailed: Long,
    val leaksDetected: Int,
    val leakDetails: List<LeakInfo>,
    val componentBreakdown: Map<String, Int>,
    val averageExecutionTimeMs: Double,
    val successRate: Double,
    val cancellationRate: Double,
    val isHealthy: Boolean
)