package com.intelliwiz.mobile.telemetry

import com.intelliwiz.mobile.telemetry.coroutines.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import kotlin.system.measureTimeMillis

/**
 * Comprehensive Coroutine Lifecycle Tests
 *
 * Tests proper lifecycle management, cancellation propagation,
 * and leak detection for all coroutine patterns in the SDK.
 */
class CoroutineLifecycleTest {

    private lateinit var testScope: TestScope
    private lateinit var testDispatcher: TestDispatcher

    @Before
    fun setup() {
        testDispatcher = StandardTestDispatcher()
        testScope = TestScope(testDispatcher)
    }

    @After
    fun teardown() {
        testScope.cancel()
    }

    @Test
    fun `test coroutine scope manager creates and cancels scopes`() = runTest {
        val manager = CoroutineScopeManager.getInstance()

        // Create scope
        val scope = manager.getOrCreate("test-scope", Dispatchers.Unconfined)
        assertNotNull(scope)
        assertTrue(manager.isScopeActive("test-scope"))

        // Launch job in scope
        val job = scope.launch {
            delay(1000)
        }

        assertTrue(job.isActive)

        // Cancel scope
        manager.cancel("test-scope")

        // Wait for cancellation
        advanceUntilIdle()

        assertFalse(manager.isScopeActive("test-scope"))
        assertTrue(job.isCancelled)
    }

    @Test
    fun `test coroutine scope manager prevents multiple scopes with same key`() = runTest {
        val manager = CoroutineScopeManager.getInstance()

        val scope1 = manager.getOrCreate("duplicate-scope", Dispatchers.Unconfined)
        val scope2 = manager.getOrCreate("duplicate-scope", Dispatchers.Unconfined)

        // Should return the same scope instance
        assertSame(scope1, scope2)

        manager.cancel("duplicate-scope")
    }

    @Test
    fun `test cancellable flow collector stops collection on cancellation`() = runTest {
        val flow = kotlinx.coroutines.flow.flow {
            repeat(100) {
                emit(it)
                delay(10)
            }
        }

        val collector = CancellableFlowCollector<Int>()
        val collected = mutableListOf<Int>()

        // Start collecting
        collector.collect(flow, this, null, null, null) { value ->
            collected.add(value)
        }

        // Let it collect some items
        advanceTimeBy(50)
        assertTrue(collected.isNotEmpty())

        // Stop collection
        collector.stopCollecting()
        val sizeAfterStop = collected.size

        // Advance time and verify no more items collected
        advanceTimeBy(100)
        assertEquals(sizeAfterStop, collected.size)

        assertFalse(collector.isCollecting())
    }

    @Test
    fun `test buffered flow collector batches items correctly`() = runTest {
        val flow = kotlinx.coroutines.flow.flow {
            repeat(25) {
                emit(it)
                delay(10)
            }
        }

        val batchCollector = BufferedFlowCollector<Int>(batchSize = 10, flushIntervalMs = 1000)
        val batches = mutableListOf<List<Int>>()

        batchCollector.collect(flow, this, { batch ->
            batches.add(batch)
        }, null)

        // Let it collect all items
        advanceUntilIdle()

        // Should have collected in batches
        assertTrue(batches.isNotEmpty())
        assertTrue(batches.any { it.size == 10 }) // At least one full batch

        batchCollector.stopCollecting()
    }

    @Test
    fun `test coroutine health monitor tracks coroutine lifecycle`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()
        monitor.reset()

        // Track a coroutine
        val result = monitor.trackCoroutine("test-component") {
            delay(50)
            "completed"
        }

        advanceUntilIdle()

        assertEquals("completed", result)

        // Generate health report
        val report = monitor.generateHealthReport()

        assertEquals(1L, report.totalLaunched)
        assertEquals(1L, report.totalCompleted)
        assertEquals(0, report.activeCoroutines)
    }

    @Test
    fun `test coroutine health monitor detects leaks`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()
        monitor.reset()

        // Register a job that will not complete
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val job = scope.launch {
            delay(Long.MAX_VALUE)
        }

        monitor.registerJob("leaky-component", job)

        // Fast-forward time to exceed leak threshold
        advanceTimeBy(61000) // > 1 minute

        // Check for leaks
        val leaks = monitor.detectLeaks()

        assertTrue(leaks.isNotEmpty())
        assertEquals("leaky-component", leaks.first().componentName)

        // Cleanup
        job.cancel()
        scope.cancel()
    }

    @Test
    fun `test coroutine health monitor tracks failures`() = runTest {
        val monitor = CoroutineHealthMonitor.getInstance()
        monitor.reset()

        try {
            monitor.trackCoroutine("failing-component") {
                throw RuntimeException("Test failure")
            }
            fail("Should have thrown exception")
        } catch (e: RuntimeException) {
            // Expected
        }

        advanceUntilIdle()

        val report = monitor.generateHealthReport()

        assertEquals(1L, report.totalLaunched)
        assertEquals(1L, report.totalFailed)
        assertEquals(0L, report.totalCompleted)
    }

    @Test
    fun `test coroutine cancellation propagates correctly`() = runTest {
        val parentJob = SupervisorJob()
        val scope = CoroutineScope(parentJob + Dispatchers.Unconfined)

        val childJob1 = scope.launch {
            delay(1000)
        }

        val childJob2 = scope.launch {
            delay(1000)
        }

        assertTrue(childJob1.isActive)
        assertTrue(childJob2.isActive)

        // Cancel parent
        parentJob.cancel()

        advanceUntilIdle()

        // Children should be cancelled
        assertTrue(childJob1.isCancelled)
        assertTrue(childJob2.isCancelled)
    }

    @Test
    fun `test timeout protection on coroutines`() = runTest {
        var timedOut = false

        try {
            withTimeout(100) {
                delay(200)
            }
        } catch (e: TimeoutCancellationException) {
            timedOut = true
        }

        advanceUntilIdle()

        assertTrue("Timeout should have occurred", timedOut)
    }

    @Test
    fun `test structured concurrency with coroutineScope`() = runTest {
        val results = mutableListOf<String>()

        coroutineScope {
            launch {
                delay(50)
                results.add("job1")
            }

            launch {
                delay(30)
                results.add("job2")
            }
        }

        // coroutineScope waits for all children
        assertEquals(2, results.size)
        assertTrue(results.contains("job1"))
        assertTrue(results.contains("job2"))
    }

    @Test
    fun `test cancellation cleanup handlers`() = runTest {
        var cleanupCalled = false

        val job = launch {
            try {
                delay(Long.MAX_VALUE)
            } finally {
                cleanupCalled = true
            }
        }

        job.cancel()
        advanceUntilIdle()

        assertTrue("Cleanup handler should have been called", cleanupCalled)
    }

    @Test
    fun `test job completion callbacks`() = runTest {
        var completed = false

        val job = launch {
            delay(50)
        }

        job.invokeOnCompletion {
            completed = true
        }

        advanceUntilIdle()

        assertTrue("Job completion callback should have been called", completed)
    }

    @Test
    fun `test multiple coroutine cancellations are idempotent`() = runTest {
        val job = launch {
            delay(Long.MAX_VALUE)
        }

        // Cancel multiple times
        job.cancel()
        job.cancel()
        job.cancel()

        advanceUntilIdle()

        assertTrue(job.isCancelled)
        assertFalse(job.isActive)
    }

    @Test
    fun `test scope manager cleanup on cancel all`() = runTest {
        val manager = CoroutineScopeManager.getInstance()

        // Create multiple scopes
        repeat(5) { i ->
            val scope = manager.getOrCreate("scope-$i", Dispatchers.Unconfined)
            scope.launch {
                delay(1000)
            }
        }

        assertEquals(5, manager.getActiveScopes().size)

        // Cancel all
        manager.cancelAll()

        advanceUntilIdle()

        assertEquals(0, manager.getActiveScopes().size)
    }

    @Test
    fun `test coroutine exception handling`() = runTest {
        val handler = CoroutineExceptionHandler { _, exception ->
            assertEquals("Test exception", exception.message)
        }

        val scope = CoroutineScope(SupervisorJob() + handler + Dispatchers.Unconfined)

        scope.launch {
            throw RuntimeException("Test exception")
        }

        advanceUntilIdle()

        // Cleanup
        scope.cancel()
    }

    @Test
    fun `test supervisor job isolates failures`() = runTest {
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(supervisor + Dispatchers.Unconfined)

        val job1 = scope.launch {
            delay(100)
            throw RuntimeException("Job 1 failed")
        }

        val job2 = scope.launch {
            delay(200)
        }

        try {
            job1.join()
        } catch (e: RuntimeException) {
            // Expected
        }

        advanceUntilIdle()

        // Job 2 should still be active (SupervisorJob isolates failures)
        assertTrue(job2.isCompleted)
        assertFalse(supervisor.isCancelled)

        supervisor.cancel()
    }
}