# Kotlin Coroutine Lifecycle Best Practices

**For: IntelliWiz Kotlin SDK**
**Date: 2025-09-27**
**Status: Implemented**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Critical Anti-Patterns (Forbidden)](#critical-anti-patterns-forbidden)
3. [Required Patterns](#required-patterns)
4. [Utility Classes](#utility-classes)
5. [Testing Strategy](#testing-strategy)
6. [Examples](#examples)
7. [Troubleshooting](#troubleshooting)

---

## Overview

This document outlines mandatory best practices for coroutine lifecycle management in the IntelliWiz Kotlin SDK. Following these patterns prevents memory leaks, orphaned coroutines, and ensures proper resource cleanup.

### Why This Matters

**Memory Leaks:** Uncancelled coroutines can hold references to objects indefinitely
**Resource Exhaustion:** Orphaned background tasks consume CPU and battery
**App Crashes:** Accumulated coroutines can lead to OutOfMemoryError
**Poor UX:** Battery drain and performance degradation

---

## Critical Anti-Patterns (Forbidden)

### ❌ **Anti-Pattern 1: Long-Running Collection Without Cancellation**

```kotlin
// WRONG - Boolean flag pattern
class AttachmentSyncObserver {
    private var isObserving = false

    fun startObserving() {
        isObserving = true
        scope.launch {
            myFlow.collect {
                if (!isObserving) return@collect // Passive check
                process(it)
            }
        }
    }

    fun stopObserving() {
        isObserving = false // Doesn't actually cancel!
    }
}
```

**Problems:**
- Collection continues even after `stopObserving()` is called
- Flow collection holds resources
- No explicit cancellation mechanism

✅ **Correct Pattern:**

```kotlin
class AttachmentSyncObserver {
    private var collectionJob: Job? = null

    fun startObserving() {
        collectionJob = scope.launch {
            myFlow.collect {
                ensureActive() // Explicit cancellation check
                process(it)
            }
        }
    }

    fun stopObserving() {
        collectionJob?.cancel() // Explicit cancellation
        collectionJob = null
    }
}
```

---

### ❌ **Anti-Pattern 2: Orphaned Background Coroutines in Singletons**

```kotlin
// WRONG - Ad-hoc coroutine launches
class DjangoChannelsMobileSyncService {
    fun connect() {
        // Orphaned heartbeat
        CoroutineScope(Dispatchers.IO).launch {
            while (true) {
                sendHeartbeat()
                delay(30000)
            }
        }

        // Orphaned retry logic
        CoroutineScope(Dispatchers.IO).launch {
            retryFailedRequests()
        }
    }
}
```

**Problems:**
- No way to cancel these coroutines
- Singleton lifecycle means they run forever
- No parent scope relationship

✅ **Correct Pattern:**

```kotlin
class DjangoChannelsMobileSyncService {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val activeJobs = mutableSetOf<Job>()

    fun connect() {
        val heartbeatJob = serviceScope.launch {
            while (isActive) {
                ensureActive()
                sendHeartbeat()
                delay(30000)
            }
        }

        val retryJob = serviceScope.launch {
            retryFailedRequests()
        }

        synchronized(activeJobs) {
            activeJobs.add(heartbeatJob)
            activeJobs.add(retryJob)
        }
    }

    fun disconnect() {
        synchronized(activeJobs) {
            activeJobs.forEach { it.cancel() }
            activeJobs.clear()
        }
        serviceScope.cancel()
    }
}
```

---

### ❌ **Anti-Pattern 3: Blocking Primitives Inside Coroutines**

```kotlin
// WRONG - CountDownLatch in coroutine
class MqttConnectionManager {
    suspend fun connect() = withContext(Dispatchers.IO) {
        val latch = CountDownLatch(1)

        mqttClient.connect(object : IMqttActionListener {
            override fun onSuccess(asyncActionToken: IMqttToken?) {
                latch.countDown()
            }
            override fun onFailure(asyncActionToken: IMqttToken?, exception: Throwable?) {
                latch.countDown()
            }
        })

        latch.await() // Blocks thread!
    }
}
```

**Problems:**
- Blocks thread pool thread
- Cannot be cancelled
- Not idiomatic Kotlin

✅ **Correct Pattern:**

```kotlin
class MqttConnectionManager {
    suspend fun connect() = suspendCancellableCoroutine<Unit> { continuation ->
        mqttClient.connect(object : IMqttActionListener {
            override fun onSuccess(asyncActionToken: IMqttToken?) {
                continuation.resume(Unit)
            }
            override fun onFailure(asyncActionToken: IMqttToken?, exception: Throwable?) {
                continuation.resumeWithException(exception ?: Exception("Connection failed"))
            }
        })

        // Handle cancellation
        continuation.invokeOnCancellation {
            mqttClient.disconnect()
        }
    }
}
```

---

### ❌ **Anti-Pattern 4: Broadcast Receiver Network Callback Lifecycle**

```kotlin
// WRONG - No unregister mechanism
class ConnectivityReceiver {
    fun registerNetworkCallback(context: Context) {
        val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

        connectivityManager.registerNetworkCallback(
            NetworkRequest.Builder().build(),
            object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    handleNetworkAvailable()
                }
            }
        )
        // No way to unregister!
    }
}
```

**Problems:**
- Callback leaks
- No lifecycle management
- Context leak potential

✅ **Correct Pattern:**

```kotlin
class ConnectivityReceiver {
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var connectivityManager: ConnectivityManager? = null

    fun registerNetworkCallback(context: Context) {
        connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                handleNetworkAvailable()
            }
        }.also { callback ->
            connectivityManager?.registerNetworkCallback(
                NetworkRequest.Builder().build(),
                callback
            )
        }
    }

    fun unregisterNetworkCallback() {
        networkCallback?.let { callback ->
            connectivityManager?.unregisterNetworkCallback(callback)
        }
        networkCallback = null
        connectivityManager = null
    }
}
```

---

## Required Patterns

### ✅ **Pattern 1: Explicit Job Tracking**

```kotlin
class TelemetryWorker {
    private val activeJobs = mutableSetOf<Job>()
    private val jobsLock = Any()

    fun startWork(scope: CoroutineScope) {
        val job = scope.launch {
            performWork()
        }

        synchronized(jobsLock) {
            activeJobs.add(job)
            job.invokeOnCompletion {
                synchronized(jobsLock) {
                    activeJobs.remove(job)
                }
            }
        }
    }

    fun stopAllWork() {
        synchronized(jobsLock) {
            activeJobs.forEach { it.cancel() }
            activeJobs.clear()
        }
    }
}
```

### ✅ **Pattern 2: Cancellable Flow Collection**

```kotlin
val collector = CancellableFlowCollector<Event>()

// Start
collector.collect(eventFlow, scope, timeoutMs = 30000) { event ->
    processEvent(event)
}

// Stop
collector.stopCollecting()
```

### ✅ **Pattern 3: Lifecycle-Aware Scopes**

```kotlin
class MyActivity : AppCompatActivity() {
    private val lifecycleScope = LifecycleAwareScope(lifecycle)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        lifecycleScope.launch {
            // Automatically cancelled when activity is destroyed
            collectData()
        }
    }
}
```

### ✅ **Pattern 4: Timeout Protection**

```kotlin
suspend fun sendTelemetry(event: Event) {
    try {
        withTimeout(5000) { // 5 second timeout
            transport.send(event)
        }
    } catch (e: TimeoutCancellationException) {
        logger.warn("Send timed out, using fallback")
        fallbackTransport.send(event)
    }
}
```

### ✅ **Pattern 5: Specific Exception Handling**

```kotlin
// WRONG - Generic catch
try {
    performOperation()
} catch (e: Exception) {
    logger.error(e)
}

// CORRECT - Specific exceptions
try {
    performOperation()
} catch (e: TimeoutCancellationException) {
    handleTimeout()
} catch (e: CancellationException) {
    throw e // Re-throw cancellation
} catch (e: SocketException) {
    handleNetworkError(e)
} catch (e: IOException) {
    handleIOError(e)
}
```

---

## Utility Classes

### CoroutineScopeManager

Centralized scope management across the SDK.

```kotlin
val manager = CoroutineScopeManager.getInstance()

// Create or get scope
val scope = manager.getOrCreate("telemetry", Dispatchers.IO)

// Launch work
scope.launch {
    doWork()
}

// Cancel specific scope
manager.cancel("telemetry")

// Cancel all scopes
manager.cancelAll()

// Health monitoring
val health = manager.getHealthStatus()
```

### CoroutineHealthMonitor

Track and detect coroutine leaks.

```kotlin
val monitor = CoroutineHealthMonitor.getInstance()

// Track coroutine
monitor.trackCoroutine("worker") {
    performWork()
}

// Register existing job
val job = scope.launch { ... }
monitor.registerJob("background-task", job)

// Check for leaks
val leaks = monitor.detectLeaks()
leaks.forEach { leak ->
    logger.warn("Leak detected: ${leak.componentName}, age: ${leak.ageMs}ms")
}

// Generate report
val report = monitor.generateHealthReport()
println("Active: ${report.activeCoroutines}, Success rate: ${report.successRate}%")
```

### SmartReconnectionManager

Intelligent reconnection with exponential backoff.

```kotlin
val reconnectionManager = SmartReconnectionManager(
    componentName = "WebSocket",
    baseDelayMs = 1000,
    maxAttempts = 5,
    circuitBreakerThreshold = 10
)

reconnectionManager.reconnect(scope,
    onStateChange = { state ->
        when (state) {
            is ReconnectionState.CONNECTED -> logger.info("Connected")
            is ReconnectionState.FAILED -> logger.error("Failed: ${state.error}")
            is ReconnectionState.CIRCUIT_BREAKER_OPEN -> logger.warn("Circuit breaker open")
            else -> {}
        }
    },
    healthCheck = { checkNetworkConnectivity() }
) {
    connectToServer()
}

// Stop reconnection
reconnectionManager.stop()

// Reset circuit breaker
reconnectionManager.resetCircuitBreaker()
```

---

## Testing Strategy

### Unit Tests

Test individual coroutine lifecycle operations.

```kotlin
@Test
fun `test job cancellation propagates correctly`() = runTest {
    val job = launch { delay(Long.MAX_VALUE) }
    assertTrue(job.isActive)

    job.cancel()
    advanceUntilIdle()

    assertTrue(job.isCancelled)
}
```

### Leak Detection Tests

Validate no coroutines leak after cancellation.

```kotlin
@Test
fun `test no leaked coroutines after stop`() = runTest {
    val monitor = CoroutineHealthMonitor.getInstance()
    monitor.reset()

    val scope = CoroutineScope(SupervisorJob())
    repeat(10) { i ->
        monitor.registerJob("test-$i", scope.launch { delay(1000) })
    }

    scope.cancel()
    advanceUntilIdle()

    val report = monitor.generateHealthReport()
    assertEquals(0, report.activeCoroutines)
}
```

### Integration Tests

End-to-end lifecycle validation.

```kotlin
@Test
fun `test telemetry client full lifecycle`() = runTest {
    val client = StreamTelemetryClient.initialize(context, config)

    // Use client
    client.recordEvent("test", mapOf("key" to "value"))
    advanceTimeBy(1000)

    // Stop
    client.stop()
    advanceUntilIdle()

    // Verify cleanup
    val metrics = client.getMetrics()
    assertEquals(0, metrics.queueSize)
}
```

---

## Examples

### Complete Service Implementation

```kotlin
class TelemetryService(
    private val context: Context
) {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val healthMonitor = CoroutineHealthMonitor.getInstance()
    private val scopeManager = CoroutineScopeManager.getInstance()

    private var eventProcessingJob: Job? = null
    private var transportJob: Job? = null

    fun start() {
        eventProcessingJob = serviceScope.launch {
            healthMonitor.trackCoroutine("event-processing") {
                processEvents()
            }
        }

        transportJob = serviceScope.launch {
            healthMonitor.trackCoroutine("transport") {
                manageTransport()
            }
        }
    }

    fun stop() {
        eventProcessingJob?.cancel()
        transportJob?.cancel()
        eventProcessingJob = null
        transportJob = null
    }

    fun shutdown() {
        stop()
        serviceScope.cancel()
    }

    private suspend fun processEvents() {
        while (isActive) {
            ensureActive()
            try {
                withTimeout(5000) {
                    val event = eventQueue.take()
                    processEvent(event)
                }
            } catch (e: TimeoutCancellationException) {
                logger.warn("Event processing timed out")
            } catch (e: CancellationException) {
                throw e
            }
        }
    }
}
```

---

## Troubleshooting

### Issue: Coroutines Not Cancelling

**Symptom:** Jobs remain active after calling cancel()

**Solution:**
1. Check for `ensureActive()` calls in loops
2. Verify parent scope is not cancelled
3. Look for blocking operations
4. Check if CancellationException is being swallowed

### Issue: Memory Leaks Detected

**Symptom:** CoroutineHealthMonitor reports leaks

**Solution:**
1. Review Job storage and cancellation
2. Check for circular references
3. Verify cleanup in finally blocks
4. Use WeakReference for long-lived objects

### Issue: Circuit Breaker Always Open

**Symptom:** SmartReconnectionManager refuses connections

**Solution:**
1. Check consecutive failure count
2. Review failure threshold settings
3. Manually reset circuit breaker if needed
4. Implement proper health checks

---

## Compliance Checklist

Before submitting code, verify:

- [ ] All launched coroutines have Job references stored
- [ ] All stored Jobs can be cancelled
- [ ] No passive boolean flags for cancellation control
- [ ] All flows use CancellableFlowCollector or similar
- [ ] No blocking primitives (CountDownLatch, wait()) in coroutines
- [ ] All callbacks have unregister mechanisms
- [ ] Timeout protection on all network operations
- [ ] Specific exception handling (no generic `catch (e: Exception)`)
- [ ] Comprehensive tests for lifecycle management
- [ ] CoroutineHealthMonitor integration

---

## References

- [Kotlin Coroutines Guide](https://kotlinlang.org/docs/coroutines-guide.html)
- [Structured Concurrency](https://kotlinlang.org/docs/composing-suspending-functions.html#structured-concurrency-with-async)
- [Cancellation and Timeouts](https://kotlinlang.org/docs/cancellation-and-timeouts.html)

---

**Document Version:** 1.0
**Last Updated:** 2025-09-27
**Maintained By:** IntelliWiz SDK Team