package com.intelliwiz.mobile.telemetry

import com.intelliwiz.mobile.telemetry.core.*
import com.intelliwiz.mobile.telemetry.coroutines.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/**
 * Stream Telemetry Integration Tests
 *
 * End-to-end integration tests for the entire telemetry system,
 * validating proper lifecycle management, cancellation, and cleanup.
 */
class StreamTelemetryIntegrationTest {

    private lateinit var testScope: TestScope
    private lateinit var testDispatcher: TestDispatcher

    @Before
    fun setup() {
        testDispatcher = StandardTestDispatcher()
        testScope = TestScope(testDispatcher)

        // Reset health monitor
        CoroutineHealthMonitor.getInstance().reset()
    }

    @After
    fun teardown() {
        testScope.cancel()
    }

    @Test
    fun `test telemetry client stop cancels all jobs`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()

        val config = TelemetryConfig(
            endpoint = "ws://localhost:8000/telemetry",
            batchSize = 10,
            transmissionIntervalMs = 1000,
            debugMode = true
        )

        // Note: This test doesn't actually initialize the client as it would require
        // network connection. Instead, it validates the pattern.

        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

        // Simulate telemetry jobs
        val jobs = List(5) { i ->
            scope.launch {
                monitor.trackCoroutine("telemetry-worker-$i") {
                    delay(Long.MAX_VALUE)
                }
            }
        }

        advanceTimeBy(100)

        var report = monitor.generateHealthReport()
        assertTrue(report.activeCoroutines > 0)

        // Stop (cancel all jobs)
        scope.cancel()
        advanceUntilIdle()

        // Verify all cancelled
        jobs.forEach { assertTrue(it.isCancelled) }

        report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
    }

    @Test
    fun `test telemetry event queueing and cancellation`() = runTest {
        val eventQueue = kotlinx.coroutines.channels.Channel<TelemetryEvent>(100)
        val processedEvents = mutableListOf<TelemetryEvent>()

        val processingJob = launch {
            for (event in eventQueue) {
                ensureActive()
                processedEvents.add(event)
                delay(10)
            }
        }

        // Queue events
        repeat(10) { i ->
            eventQueue.send(
                TelemetryEvent(
                    id = "event-$i",
                    eventType = "test",
                    timestamp = System.currentTimeMillis(),
                    endpoint = "test",
                    data = mapOf("value" to i)
                )
            )
        }

        advanceTimeBy(50)

        assertTrue(processedEvents.isNotEmpty())

        // Cancel processing
        processingJob.cancel()
        eventQueue.close()
        advanceUntilIdle()

        assertTrue(processingJob.isCancelled)
        assertTrue(eventQueue.isClosedForSend)
    }

    @Test
    fun `test concurrent telemetry operations cleanup`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

        // Simulate multiple concurrent operations
        val jobs = listOf(
            scope.launch {
                monitor.trackCoroutine("event-processor") {
                    delay(Long.MAX_VALUE)
                }
            },
            scope.launch {
                monitor.trackCoroutine("transport-websocket") {
                    delay(Long.MAX_VALUE)
                }
            },
            scope.launch {
                monitor.trackCoroutine("transport-http") {
                    delay(Long.MAX_VALUE)
                }
            },
            scope.launch {
                monitor.trackCoroutine("health-monitor") {
                    delay(Long.MAX_VALUE)
                }
            }
        )

        advanceTimeBy(100)

        var report = monitor.generateHealthReport()
        assertEquals(4, report.activeCoroutines)

        // Graceful shutdown
        scope.cancel()
        advanceUntilIdle()

        // Verify all cleaned up
        jobs.forEach { assertTrue(it.isCancelled) }

        report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
    }

    @Test
    fun `test telemetry under load with proper cleanup`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

        // Simulate high load
        val jobs = List(100) { i ->
            scope.launch {
                monitor.trackCoroutine("load-test-$i") {
                    repeat(10) {
                        delay(10)
                    }
                }
            }
        }

        advanceTimeBy(50)

        var report = monitor.generateHealthReport()
        assertTrue(report.activeCoroutines > 0)

        // Let some complete naturally
        advanceTimeBy(150)

        // Cancel remaining
        scope.cancel()
        advanceUntilIdle()

        report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
        assertEquals(100, report.totalLaunched.toInt())
    }

    @Test
    fun `test error handling doesn't leak coroutines`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()

        val handler = CoroutineExceptionHandler { _, _ -> }
        val scope = CoroutineScope(SupervisorJob() + handler + Dispatchers.Unconfined)

        // Launch jobs that will fail
        val jobs = List(10) { i ->
            scope.launch {
                try {
                    monitor.trackCoroutine("failing-job-$i") {
                        delay(50)
                        throw RuntimeException("Simulated error")
                    }
                } catch (e: RuntimeException) {
                    // Handle error
                }
            }
        }

        advanceUntilIdle()

        val report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
        assertEquals(10, report.totalLaunched.toInt())

        // Cleanup
        scope.cancel()
    }

    @Test
    fun `test transport reconnection with proper job management`() = runTest {
        val reconnectionManager = SmartReconnectionManager(
            componentName = "telemetry-transport",
            baseDelayMs = 100,
            maxAttempts = 3
        )

        var attemptCount = 0
        var connected = false

        reconnectionManager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attemptCount++
            if (attemptCount < 2) {
                throw RuntimeException("Connection failed")
            }
            connected = true
        }

        advanceUntilIdle()

        assertTrue("Should eventually connect", connected)

        // Verify no orphaned jobs
        reconnectionManager.stop()
        advanceUntilIdle()

        assertFalse(reconnectionManager.isReconnecting())
    }

    @Test
    fun `test scope manager integration with telemetry operations`() = runTest {
        val scopeManager = CoroutineScopeManager.getInstance()
        val monitor = CoroutineHealthMonitor.getInstance()

        // Create telemetry scopes
        val transportScope = scopeManager.getOrCreate("transport", Dispatchers.Unconfined)
        val processingScope = scopeManager.getOrCreate("processing", Dispatchers.Unconfined)

        // Launch jobs in managed scopes
        val transportJob = transportScope.launch {
            monitor.trackCoroutine("transport-worker") {
                delay(1000)
            }
        }

        val processingJob = processingScope.launch {
            monitor.trackCoroutine("processing-worker") {
                delay(1000)
            }
        }

        advanceTimeBy(100)

        assertTrue(scopeManager.isScopeActive("transport"))
        assertTrue(scopeManager.isScopeActive("processing"))

        // Cancel all scopes
        scopeManager.cancelAll()
        advanceUntilIdle()

        assertTrue(transportJob.isCancelled)
        assertTrue(processingJob.isCancelled)

        val report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
    }

    @Test
    fun `test flow-based telemetry collection cleanup`() = runTest {
        val flow = kotlinx.coroutines.flow.flow {
            repeat(100) { i ->
                emit(TelemetryEvent(
                    id = "event-$i",
                    eventType = "flow-test",
                    timestamp = System.currentTimeMillis(),
                    endpoint = "test",
                    data = mapOf("value" to i)
                ))
                delay(10)
            }
        }

        val collector = BufferedFlowCollector<TelemetryEvent>(batchSize = 10)
        val batches = mutableListOf<List<TelemetryEvent>>()

        collector.collect(flow, this, { batch ->
            batches.add(batch)
        }, null)

        advanceTimeBy(500)

        assertTrue(batches.isNotEmpty())

        // Stop collection
        collector.stopCollecting()
        advanceUntilIdle()

        assertFalse(collector.isCollecting())
    }

    @Test
    fun `test health monitoring throughout telemetry lifecycle`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

        // Phase 1: Launch jobs
        val jobs = List(20) { i ->
            scope.launch {
                monitor.trackCoroutine("lifecycle-test-$i") {
                    delay(if (i % 2 == 0) 100L else 200L)
                }
            }
        }

        advanceTimeBy(50)

        var report = monitor.generateHealthReport()
        assertTrue(report.activeCoroutines > 0)
        assertEquals(20, report.totalLaunched.toInt())

        // Phase 2: Let some complete
        advanceTimeBy(100)

        report = monitor.generateHealthReport()
        assertTrue(report.totalCompleted > 0)

        // Phase 3: Cancel remaining
        scope.cancel()
        advanceUntilIdle()

        report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
        assertEquals(20, report.totalLaunched.toInt())
        assertTrue(report.totalCompleted + report.totalCancelled == 20L)
    }

    @Test
    fun `test graceful shutdown with pending events`() = runTest {
        val eventQueue = mutableListOf<TelemetryEvent>()
        val processedEvents = mutableListOf<TelemetryEvent>()

        // Queue events
        repeat(50) { i ->
            eventQueue.add(
                TelemetryEvent(
                    id = "event-$i",
                    eventType = "shutdown-test",
                    timestamp = System.currentTimeMillis(),
                    endpoint = "test",
                    data = mapOf("value" to i)
                )
            )
        }

        val processingJob = launch {
            try {
                eventQueue.forEach { event ->
                    ensureActive()
                    processedEvents.add(event)
                    delay(10)
                }
            } finally {
                // Ensure cleanup happens
            }
        }

        advanceTimeBy(250)

        // Gracefully stop
        processingJob.cancel()
        advanceUntilIdle()

        assertTrue(processingJob.isCancelled)
        assertTrue("Some events should have been processed", processedEvents.isNotEmpty())
        assertTrue("Not all events processed during shutdown", processedEvents.size < eventQueue.size)
    }
}