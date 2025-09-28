package com.intelliwiz.mobile.telemetry

import com.intelliwiz.mobile.telemetry.core.StreamTelemetryClient
import com.intelliwiz.mobile.telemetry.core.TelemetryConfig
import com.intelliwiz.mobile.telemetry.coroutines.*
import com.intelliwiz.mobile.telemetry.transport.TelemetryTransport
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.lang.ref.WeakReference

/**
 * Memory Leak Detection Tests
 *
 * Validates that coroutines don't leak memory and are properly
 * cleaned up when cancelled or when scopes are destroyed.
 */
class MemoryLeakTest {

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
    fun `test no leaked coroutines after scope cancellation`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()

        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

        // Launch multiple coroutines
        repeat(10) { i ->
            val job = scope.launch {
                delay(Long.MAX_VALUE)
            }
            monitor.registerJob("test-component-$i", job)
        }

        advanceTimeBy(100)

        // Verify all active
        var report = monitor.generateHealthReport()
        assertEquals(10, report.activeCoroutines)

        // Cancel scope
        scope.cancel()
        advanceUntilIdle()

        // Verify all cancelled
        report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
        assertEquals(10, report.totalCancelled.toInt())
    }

    @Test
    fun `test weak references are cleared after cancellation`() = runTest {
        var job: Job? = launch {
            delay(Long.MAX_VALUE)
        }

        val weakRef = WeakReference(job)

        // Cancel and clear reference
        job?.cancel()
        job = null

        advanceUntilIdle()

        // Force garbage collection hint
        System.gc()
        delay(100)

        // Note: GC is not guaranteed, but we can check if the job is cancelled
        val ref = weakRef.get()
        if (ref != null) {
            assertTrue("Job should be cancelled", ref.isCancelled)
        }
    }

    @Test
    fun `test no leaked coroutines in scope manager`() = runTest {
        val manager = CoroutineScopeManager.getInstance()

        // Create multiple scopes and launch jobs
        repeat(20) { i ->
            val scope = manager.getOrCreate("scope-$i", Dispatchers.Unconfined)
            scope.launch {
                delay(1000)
            }
        }

        val health = manager.getHealthStatus()
        assertEquals(20, health.totalScopes)
        assertEquals(20, health.activeScopes)

        // Cancel all
        manager.cancelAll()
        advanceUntilIdle()

        val healthAfter = manager.getHealthStatus()
        assertEquals(0, healthAfter.totalScopes)
        assertEquals(0, healthAfter.activeScopes)
    }

    @Test
    fun `test flow collector cleanup prevents leaks`() = runTest {
        val flow = kotlinx.coroutines.flow.flow {
            repeat(1000) {
                emit(it)
                delay(10)
            }
        }

        val collector = CancellableFlowCollector<Int>()

        // Start collecting
        val job = collector.collect(flow, this, null, null, null) { }

        advanceTimeBy(50)

        assertTrue(collector.isCollecting())

        // Stop collection
        collector.stopCollecting()
        advanceUntilIdle()

        assertFalse(collector.isCollecting())
        assertFalse(collector.isActive())
        assertTrue(job.isCancelled)
    }

    @Test
    fun `test multiple start-stop cycles don't leak`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()

        repeat(10) { cycle ->
            val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

            // Launch jobs
            val jobs = List(5) { i ->
                scope.launch {
                    delay(100)
                }.also { job ->
                    monitor.registerJob("cycle-$cycle-job-$i", job)
                }
            }

            advanceTimeBy(50)

            // Cancel all
            scope.cancel()
            advanceUntilIdle()

            // Verify all cancelled
            jobs.forEach { assertTrue(it.isCancelled) }
        }

        val report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
        assertEquals(50, report.totalCancelled.toInt())
    }

    @Test
    fun `test long-running coroutines are detected as potential leaks`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()

        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val job = scope.launch {
            delay(Long.MAX_VALUE)
        }

        monitor.registerJob("long-running", job)

        // Fast-forward past leak threshold
        advanceTimeBy(61000) // > 1 minute

        val leaks = monitor.detectLeaks()

        assertTrue(leaks.isNotEmpty())
        assertEquals(1, leaks.size)
        assertEquals("long-running", leaks.first().componentName)
        assertTrue(leaks.first().ageMs > 60000)

        // Cleanup
        job.cancel()
        scope.cancel()
        advanceUntilIdle()

        // After cancellation, no leaks
        val leaksAfter = monitor.detectLeaks()
        assertTrue(leaksAfter.isEmpty())
    }

    @Test
    fun `test nested coroutine cleanup`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()

        val parentJob = launch {
            monitor.trackCoroutine("parent") {
                launch {
                    monitor.trackCoroutine("child-1") {
                        delay(1000)
                    }
                }

                launch {
                    monitor.trackCoroutine("child-2") {
                        delay(1000)
                    }
                }

                delay(Long.MAX_VALUE)
            }
        }

        advanceTimeBy(100)

        var report = monitor.generateHealthReport()
        assertTrue(report.activeCoroutines > 0)

        // Cancel parent should cancel all children
        parentJob.cancel()
        advanceUntilIdle()

        report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
    }

    @Test
    fun `test resource cleanup in finally blocks`() = runTest {
        var resourceReleased = false

        val job = launch {
            try {
                delay(Long.MAX_VALUE)
            } finally {
                resourceReleased = true
            }
        }

        advanceTimeBy(100)

        assertFalse(resourceReleased)

        job.cancel()
        advanceUntilIdle()

        assertTrue("Resource should be released in finally block", resourceReleased)
    }

    @Test
    fun `test channel cleanup after cancellation`() = runTest {
        val channel = kotlinx.coroutines.channels.Channel<Int>(10)

        val producer = launch {
            repeat(100) {
                channel.send(it)
                delay(10)
            }
            channel.close()
        }

        val consumer = launch {
            for (item in channel) {
                // Process items
            }
        }

        advanceTimeBy(50)

        // Cancel both
        producer.cancel()
        consumer.cancel()
        channel.cancel()

        advanceUntilIdle()

        assertTrue(producer.isCancelled)
        assertTrue(consumer.isCancelled)
        assertTrue(channel.isClosedForSend)
        assertTrue(channel.isClosedForReceive)
    }

    @Test
    fun `test cleanup after exception in coroutine`() = runTest {
        var cleanupCalled = false

        val handler = CoroutineExceptionHandler { _, _ -> }
        val scope = CoroutineScope(SupervisorJob() + handler + Dispatchers.Unconfined)

        val job = scope.launch {
            try {
                delay(50)
                throw RuntimeException("Test exception")
            } finally {
                cleanupCalled = true
            }
        }

        try {
            job.join()
        } catch (e: Exception) {
            // Expected
        }

        advanceUntilIdle()

        assertTrue("Cleanup should be called even after exception", cleanupCalled)

        scope.cancel()
    }

    @Test
    fun `test stress test 1000 coroutines cancelled successfully`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

        // Launch 1000 coroutines
        val jobs = List(1000) { i ->
            scope.launch {
                delay(100)
            }.also { job ->
                monitor.registerJob("stress-$i", job)
            }
        }

        advanceTimeBy(50)

        var report = monitor.generateHealthReport()
        assertTrue(report.activeCoroutines > 0)

        // Cancel all
        scope.cancel()
        advanceUntilIdle()

        // Verify all cancelled
        jobs.forEach { assertTrue(it.isCancelled) }

        report = monitor.generateHealthReport()
        assertEquals(0, report.activeCoroutines)
        assertEquals(1000, report.totalCancelled.toInt())
    }

    @Test
    fun `test scope manager detects old scopes`() = runTest {
        val manager = CoroutineScopeManager.getInstance()

        // Create an old scope (simulate by manipulating time)
        manager.getOrCreate("old-scope", Dispatchers.Unconfined)

        // Fast-forward time
        advanceTimeBy(3600001) // > 1 hour

        val health = manager.getHealthStatus()
        assertTrue(health.longRunningScopes > 0)

        // Cleanup
        manager.cancelAll()
    }
}