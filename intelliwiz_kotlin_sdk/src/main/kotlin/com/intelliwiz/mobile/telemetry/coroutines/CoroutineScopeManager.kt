package com.intelliwiz.mobile.telemetry.coroutines

import kotlinx.coroutines.*
import mu.KotlinLogging
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

private val logger = KotlinLogging.logger {}

/**
 * Centralized Coroutine Scope Manager
 *
 * Provides lifecycle management for named coroutine scopes across the SDK.
 * Prevents orphaned coroutines by tracking and managing scope lifecycles.
 *
 * Features:
 * - Named scope registry with unique identifiers
 * - Automatic cleanup and cancellation
 * - Scope health monitoring
 * - Thread-safe operations
 *
 * Usage:
 * ```kotlin
 * val manager = CoroutineScopeManager.getInstance()
 * val scope = manager.getOrCreate("telemetry", Dispatchers.IO)
 * scope.launch { ... }
 * manager.cancel("telemetry") // Clean cancellation
 * ```
 */
class CoroutineScopeManager private constructor() {

    companion object {
        @Volatile
        private var INSTANCE: CoroutineScopeManager? = null

        fun getInstance(): CoroutineScopeManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: CoroutineScopeManager().also { INSTANCE = it }
            }
        }
    }

    private val scopes = ConcurrentHashMap<String, ManagedScope>()
    private val scopeIdCounter = AtomicInteger(0)

    /**
     * Get existing scope or create a new one
     */
    fun getOrCreate(
        key: String,
        dispatcher: CoroutineDispatcher = Dispatchers.Default,
        exceptionHandler: CoroutineExceptionHandler? = null
    ): CoroutineScope {
        return scopes.getOrPut(key) {
            val handler = exceptionHandler ?: CoroutineExceptionHandler { context, exception ->
                logger.error(exception) { "Unhandled exception in scope '$key': ${exception.message}" }
            }

            val scope = CoroutineScope(SupervisorJob() + dispatcher + handler)
            logger.debug { "Created new scope: $key" }

            ManagedScope(
                id = scopeIdCounter.incrementAndGet(),
                key = key,
                scope = scope,
                createdAt = System.currentTimeMillis()
            )
        }.scope
    }

    /**
     * Cancel a specific scope by key
     */
    fun cancel(key: String) {
        scopes.remove(key)?.let { managed ->
            try {
                managed.scope.cancel()
                logger.info { "Cancelled scope: $key (id: ${managed.id})" }
            } catch (e: Exception) {
                logger.warn(e) { "Error cancelling scope '$key': ${e.message}" }
            }
        } ?: logger.warn { "Attempted to cancel non-existent scope: $key" }
    }

    /**
     * Cancel all managed scopes
     */
    fun cancelAll() {
        logger.info { "Cancelling all ${scopes.size} managed scopes" }

        scopes.keys.toList().forEach { key ->
            cancel(key)
        }

        scopes.clear()
        logger.info { "All scopes cancelled" }
    }

    /**
     * Get list of active scope keys
     */
    fun getActiveScopes(): List<String> {
        return scopes.keys.toList()
    }

    /**
     * Get scope metadata by key
     */
    fun getScopeMetadata(key: String): ScopeMetadata? {
        return scopes[key]?.let { managed ->
            ScopeMetadata(
                id = managed.id,
                key = managed.key,
                isActive = managed.scope.isActive,
                createdAt = managed.createdAt,
                ageMs = System.currentTimeMillis() - managed.createdAt
            )
        }
    }

    /**
     * Get all scope metadata
     */
    fun getAllScopeMetadata(): List<ScopeMetadata> {
        return scopes.values.map { managed ->
            ScopeMetadata(
                id = managed.id,
                key = managed.key,
                isActive = managed.scope.isActive,
                createdAt = managed.createdAt,
                ageMs = System.currentTimeMillis() - managed.createdAt
            )
        }
    }

    /**
     * Check if a scope exists and is active
     */
    fun isScopeActive(key: String): Boolean {
        return scopes[key]?.scope?.isActive ?: false
    }

    /**
     * Get scope health status
     */
    fun getHealthStatus(): HealthStatus {
        val activeCount = scopes.count { it.value.scope.isActive }
        val totalCount = scopes.size
        val oldScopes = scopes.values.count {
            (System.currentTimeMillis() - it.createdAt) > 3600000 // > 1 hour
        }

        return HealthStatus(
            totalScopes = totalCount,
            activeScopes = activeCount,
            inactiveScopes = totalCount - activeCount,
            longRunningScopes = oldScopes,
            isHealthy = activeCount == totalCount && oldScopes == 0
        )
    }

    /**
     * Launch a job in a managed scope
     */
    fun launch(
        key: String,
        dispatcher: CoroutineDispatcher = Dispatchers.Default,
        block: suspend CoroutineScope.() -> Unit
    ): Job {
        val scope = getOrCreate(key, dispatcher)
        return scope.launch(block = block)
    }

    /**
     * Async operation in a managed scope
     */
    fun <T> async(
        key: String,
        dispatcher: CoroutineDispatcher = Dispatchers.Default,
        block: suspend CoroutineScope.() -> T
    ): Deferred<T> {
        val scope = getOrCreate(key, dispatcher)
        return scope.async(block = block)
    }
}

/**
 * Internal managed scope wrapper
 */
private data class ManagedScope(
    val id: Int,
    val key: String,
    val scope: CoroutineScope,
    val createdAt: Long
)

/**
 * Scope metadata for monitoring
 */
data class ScopeMetadata(
    val id: Int,
    val key: String,
    val isActive: Boolean,
    val createdAt: Long,
    val ageMs: Long
)

/**
 * Health status of scope manager
 */
data class HealthStatus(
    val totalScopes: Int,
    val activeScopes: Int,
    val inactiveScopes: Int,
    val longRunningScopes: Int,
    val isHealthy: Boolean
)