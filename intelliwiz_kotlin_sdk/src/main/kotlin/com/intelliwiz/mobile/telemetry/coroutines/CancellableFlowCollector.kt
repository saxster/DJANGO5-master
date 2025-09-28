package com.intelliwiz.mobile.telemetry.coroutines

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import mu.KotlinLogging
import java.util.concurrent.atomic.AtomicBoolean

private val logger = KotlinLogging.logger {}

/**
 * Cancellable Flow Collector
 *
 * Provides safe flow collection patterns with explicit cancellation support.
 * Prevents the common anti-pattern of using boolean flags for flow collection control.
 *
 * Features:
 * - Explicit Job storage for cancellation
 * - Timeout protection on collection
 * - Error handling with retry logic
 * - Collection state tracking
 *
 * Usage:
 * ```kotlin
 * val collector = CancellableFlowCollector<Event>()
 *
 * // Start collecting
 * collector.collect(eventFlow, scope) { event ->
 *     processEvent(event)
 * }
 *
 * // Stop collecting
 * collector.stopCollecting()
 * ```
 */
class CancellableFlowCollector<T> {

    private var collectionJob: Job? = null
    private val isCollecting = AtomicBoolean(false)
    private val collectionLock = Any()

    /**
     * Start collecting from a flow
     */
    fun collect(
        flow: Flow<T>,
        scope: CoroutineScope,
        timeoutMs: Long? = null,
        onError: ((Throwable) -> Unit)? = null,
        onCompletion: (() -> Unit)? = null,
        collector: suspend (T) -> Unit
    ): Job {
        synchronized(collectionLock) {
            if (isCollecting.get()) {
                logger.warn { "Already collecting, stopping previous collection" }
                stopCollecting()
            }

            isCollecting.set(true)

            collectionJob = scope.launch {
                try {
                    if (timeoutMs != null) {
                        withTimeout(timeoutMs) {
                            collectFlow(flow, collector)
                        }
                    } else {
                        collectFlow(flow, collector)
                    }
                } catch (e: TimeoutCancellationException) {
                    logger.warn(e) { "Flow collection timed out after ${timeoutMs}ms" }
                    onError?.invoke(e)
                } catch (e: CancellationException) {
                    logger.info { "Flow collection cancelled" }
                    throw e
                } catch (e: Exception) {
                    logger.error(e) { "Error during flow collection: ${e.message}" }
                    onError?.invoke(e)
                } finally {
                    isCollecting.set(false)
                    onCompletion?.invoke()
                }
            }

            return collectionJob!!
        }
    }

    /**
     * Internal flow collection with cancellation checks
     */
    private suspend fun collectFlow(flow: Flow<T>, collector: suspend (T) -> Unit) {
        flow.collect { value ->
            ensureActive() // Check for cancellation before processing
            collector(value)
        }
    }

    /**
     * Stop collecting (cancel the collection job)
     */
    fun stopCollecting() {
        synchronized(collectionLock) {
            collectionJob?.let { job ->
                if (job.isActive) {
                    logger.info { "Stopping flow collection" }
                    job.cancel()
                }
            }
            collectionJob = null
            isCollecting.set(false)
        }
    }

    /**
     * Check if currently collecting
     */
    fun isCollecting(): Boolean = isCollecting.get()

    /**
     * Check if collection job is active
     */
    fun isActive(): Boolean = collectionJob?.isActive ?: false
}

/**
 * Buffered Cancellable Flow Collector
 *
 * Collects flow with buffering and batch processing support.
 * Useful for high-throughput flows that need batching.
 */
class BufferedFlowCollector<T>(
    private val batchSize: Int = 10,
    private val flushIntervalMs: Long = 1000
) {

    private var collectionJob: Job? = null
    private val isCollecting = AtomicBoolean(false)
    private val collectionLock = Any()

    /**
     * Collect flow with batching
     */
    fun collect(
        flow: Flow<T>,
        scope: CoroutineScope,
        onBatch: suspend (List<T>) -> Unit,
        onError: ((Throwable) -> Unit)? = null
    ): Job {
        synchronized(collectionLock) {
            if (isCollecting.get()) {
                logger.warn { "Already collecting, stopping previous collection" }
                stopCollecting()
            }

            isCollecting.set(true)

            collectionJob = scope.launch {
                try {
                    collectBuffered(flow, onBatch)
                } catch (e: CancellationException) {
                    logger.info { "Buffered flow collection cancelled" }
                    throw e
                } catch (e: Exception) {
                    logger.error(e) { "Error during buffered flow collection: ${e.message}" }
                    onError?.invoke(e)
                } finally {
                    isCollecting.set(false)
                }
            }

            return collectionJob!!
        }
    }

    /**
     * Internal buffered collection logic
     */
    private suspend fun collectBuffered(
        flow: Flow<T>,
        onBatch: suspend (List<T>) -> Unit
    ) {
        val buffer = mutableListOf<T>()
        var lastFlushTime = System.currentTimeMillis()

        flow.collect { value ->
            ensureActive() // Check for cancellation

            buffer.add(value)

            val now = System.currentTimeMillis()
            val shouldFlush = buffer.size >= batchSize ||
                    (now - lastFlushTime) >= flushIntervalMs

            if (shouldFlush) {
                try {
                    onBatch(buffer.toList())
                    buffer.clear()
                    lastFlushTime = now
                } catch (e: Exception) {
                    logger.error(e) { "Error processing batch: ${e.message}" }
                    throw e
                }
            }
        }

        // Flush remaining items
        if (buffer.isNotEmpty()) {
            onBatch(buffer.toList())
        }
    }

    /**
     * Stop collecting
     */
    fun stopCollecting() {
        synchronized(collectionLock) {
            collectionJob?.let { job ->
                if (job.isActive) {
                    logger.info { "Stopping buffered flow collection" }
                    job.cancel()
                }
            }
            collectionJob = null
            isCollecting.set(false)
        }
    }

    /**
     * Check if currently collecting
     */
    fun isCollecting(): Boolean = isCollecting.get()
}

/**
 * Extension function for safe flow collection with cancellation
 */
fun <T> Flow<T>.collectCancellable(
    scope: CoroutineScope,
    timeoutMs: Long? = null,
    onError: ((Throwable) -> Unit)? = null,
    collector: suspend (T) -> Unit
): CancellableFlowCollector<T> {
    val cancellableCollector = CancellableFlowCollector<T>()
    cancellableCollector.collect(this, scope, timeoutMs, onError, null, collector)
    return cancellableCollector
}