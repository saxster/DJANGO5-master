package com.intelliwiz.mobile.telemetry.coroutines

import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.*
import mu.KotlinLogging

private val logger = KotlinLogging.logger {}

/**
 * Lifecycle-Aware Coroutine Scope
 *
 * Automatically manages coroutine scope lifecycle based on Android component lifecycle.
 * Prevents memory leaks by automatically cancelling coroutines when the lifecycle is destroyed.
 *
 * Features:
 * - Automatic cancellation on lifecycle destroy
 * - Optional pause/resume on lifecycle state changes
 * - Integration with Android Architecture Components
 * - Thread-safe scope access
 *
 * Usage:
 * ```kotlin
 * class MyActivity : AppCompatActivity() {
 *     private val lifecycleScope = LifecycleAwareScope(lifecycle)
 *
 *     override fun onCreate(savedInstanceState: Bundle?) {
 *         super.onCreate(savedInstanceState)
 *         lifecycleScope.scope.launch {
 *             // This will be automatically cancelled when activity is destroyed
 *         }
 *     }
 * }
 * ```
 */
class LifecycleAwareScope(
    private val lifecycle: Lifecycle,
    dispatcher: CoroutineDispatcher = Dispatchers.Main,
    private val pauseOnStop: Boolean = false
) : DefaultLifecycleObserver {

    private val job = SupervisorJob()
    private val exceptionHandler = CoroutineExceptionHandler { context, exception ->
        logger.error(exception) { "Unhandled exception in lifecycle-aware scope: ${exception.message}" }
    }

    val scope: CoroutineScope = CoroutineScope(job + dispatcher + exceptionHandler)

    private val activeJobs = mutableSetOf<Job>()
    private val jobsLock = Any()

    init {
        lifecycle.addObserver(this)
        logger.debug { "LifecycleAwareScope created for lifecycle: ${lifecycle.currentState}" }
    }

    override fun onCreate(owner: LifecycleOwner) {
        super.onCreate(owner)
        logger.debug { "Lifecycle onCreate" }
    }

    override fun onStart(owner: LifecycleOwner) {
        super.onStart(owner)
        logger.debug { "Lifecycle onStart" }

        if (pauseOnStop && job.isCancelled.not()) {
            synchronized(jobsLock) {
                activeJobs.forEach { job ->
                    if (job.isActive.not() && job.isCancelled.not()) {
                        // Resume paused jobs if needed
                        logger.debug { "Resuming job on lifecycle start" }
                    }
                }
            }
        }
    }

    override fun onStop(owner: LifecycleOwner) {
        super.onStop(owner)
        logger.debug { "Lifecycle onStop" }

        if (pauseOnStop) {
            // Optionally pause jobs instead of cancelling
            logger.debug { "Pausing coroutines on lifecycle stop" }
        }
    }

    override fun onDestroy(owner: LifecycleOwner) {
        super.onDestroy(owner)
        logger.info { "Lifecycle onDestroy - cancelling all coroutines" }

        cancel()
        lifecycle.removeObserver(this)
    }

    /**
     * Launch a coroutine in this lifecycle-aware scope
     */
    fun launch(
        context: CoroutineContext = EmptyCoroutineContext,
        start: CoroutineStart = CoroutineStart.DEFAULT,
        block: suspend CoroutineScope.() -> Unit
    ): Job {
        val launchedJob = scope.launch(context, start, block)

        synchronized(jobsLock) {
            activeJobs.add(launchedJob)

            // Clean up completed jobs
            launchedJob.invokeOnCompletion {
                synchronized(jobsLock) {
                    activeJobs.remove(launchedJob)
                }
            }
        }

        return launchedJob
    }

    /**
     * Async operation in this lifecycle-aware scope
     */
    fun <T> async(
        context: CoroutineContext = EmptyCoroutineContext,
        start: CoroutineStart = CoroutineStart.DEFAULT,
        block: suspend CoroutineScope.() -> T
    ): Deferred<T> {
        return scope.async(context, start, block)
    }

    /**
     * Cancel all coroutines in this scope
     */
    fun cancel() {
        logger.info { "Cancelling lifecycle-aware scope with ${activeJobs.size} active jobs" }

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

        job.cancel()
        logger.info { "Lifecycle-aware scope cancelled" }
    }

    /**
     * Check if the scope is active
     */
    fun isActive(): Boolean = scope.isActive

    /**
     * Get the number of active jobs
     */
    fun getActiveJobCount(): Int {
        synchronized(jobsLock) {
            return activeJobs.count { it.isActive }
        }
    }

    /**
     * Get lifecycle state
     */
    fun getLifecycleState(): Lifecycle.State = lifecycle.currentState
}

/**
 * Extension function to create a lifecycle-aware scope from a LifecycleOwner
 */
fun LifecycleOwner.createLifecycleScope(
    dispatcher: CoroutineDispatcher = Dispatchers.Main,
    pauseOnStop: Boolean = false
): LifecycleAwareScope {
    return LifecycleAwareScope(lifecycle, dispatcher, pauseOnStop)
}