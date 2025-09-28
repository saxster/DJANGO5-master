package com.intelliwiz.mobile.telemetry

import com.intelliwiz.mobile.telemetry.coroutines.SmartReconnectionManager
import com.intelliwiz.mobile.telemetry.coroutines.ReconnectionState
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/**
 * Reconnection Strategy Tests
 *
 * Validates exponential backoff, circuit breaker, and
 * reconnection logic for network resilience.
 */
class ReconnectionTest {

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
    fun `test successful reconnection on first attempt`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 1000,
            maxAttempts = 5
        )

        var connected = false
        val states = mutableListOf<ReconnectionState>()

        manager.reconnect(
            scope = this,
            onStateChange = { state -> states.add(state) },
            healthCheck = null
        ) {
            connected = true
        }

        advanceUntilIdle()

        assertTrue("Should be connected", connected)
        assertTrue(states.any { it is ReconnectionState.CONNECTED })

        val metrics = manager.getMetrics()
        assertEquals(1, metrics.currentAttempt)
        assertEquals(1, metrics.successfulReconnects)
        assertFalse(metrics.circuitBreakerOpen)
    }

    @Test
    fun `test exponential backoff delays`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 1000,
            maxAttempts = 5
        )

        val attemptTimes = mutableListOf<Long>()
        var attemptCount = 0

        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attemptTimes.add(currentTime)
            attemptCount++

            if (attemptCount < 3) {
                throw RuntimeException("Simulated failure")
            }
        }

        advanceUntilIdle()

        assertTrue("Should have multiple attempts", attemptTimes.size >= 3)

        // Check that delays increase (approximately)
        if (attemptTimes.size >= 3) {
            val delay1 = attemptTimes[1] - attemptTimes[0]
            val delay2 = attemptTimes[2] - attemptTimes[1]

            assertTrue("Delays should increase exponentially", delay2 > delay1)
        }
    }

    @Test
    fun `test max attempts reached`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 3
        )

        var attemptCount = 0
        val states = mutableListOf<ReconnectionState>()

        manager.reconnect(
            scope = this,
            onStateChange = { state -> states.add(state) },
            healthCheck = null
        ) {
            attemptCount++
            throw RuntimeException("Always fail")
        }

        advanceUntilIdle()

        assertEquals(3, attemptCount)
        assertTrue(states.any { it is ReconnectionState.MAX_ATTEMPTS_REACHED })

        val metrics = manager.getMetrics()
        assertEquals(3, metrics.currentAttempt)
        assertEquals(0, metrics.successfulReconnects)
    }

    @Test
    fun `test circuit breaker opens after threshold`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 15,
            circuitBreakerThreshold = 10
        )

        var attemptCount = 0

        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attemptCount++
            throw RuntimeException("Always fail")
        }

        advanceUntilIdle()

        val metrics = manager.getMetrics()
        assertTrue("Circuit breaker should be open", metrics.circuitBreakerOpen)
        assertTrue("Consecutive failures should exceed threshold",
            metrics.consecutiveFailures >= 10)
    }

    @Test
    fun `test circuit breaker prevents reconnection attempts`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 5,
            circuitBreakerThreshold = 3
        )

        var firstAttemptCount = 0

        // First reconnection that will open circuit breaker
        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            firstAttemptCount++
            throw RuntimeException("Fail")
        }

        advanceUntilIdle()

        assertTrue(manager.isCircuitBreakerOpen())

        // Second reconnection attempt should be refused
        var secondAttemptCount = 0
        val states = mutableListOf<ReconnectionState>()

        manager.reconnect(
            scope = this,
            onStateChange = { state -> states.add(state) },
            healthCheck = null
        ) {
            secondAttemptCount++
        }

        advanceUntilIdle()

        assertEquals(0, secondAttemptCount)
        assertTrue(states.any { it is ReconnectionState.CIRCUIT_BREAKER_OPEN })
    }

    @Test
    fun `test circuit breaker reset allows reconnection`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 5,
            circuitBreakerThreshold = 2
        )

        // Fail and open circuit breaker
        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            throw RuntimeException("Fail")
        }

        advanceUntilIdle()

        assertTrue(manager.isCircuitBreakerOpen())

        // Reset circuit breaker
        manager.resetCircuitBreaker()

        assertFalse(manager.isCircuitBreakerOpen())

        // Now reconnection should work
        var connected = false
        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            connected = true
        }

        advanceUntilIdle()

        assertTrue("Should be connected after reset", connected)
    }

    @Test
    fun `test health check prevents reconnection attempts`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 5,
            healthCheckBeforeReconnect = true
        )

        var attemptCount = 0

        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = { false } // Always fail health check
        ) {
            attemptCount++
        }

        advanceTimeBy(5000)

        // Should have attempted multiple times but never called connect action
        assertEquals(0, attemptCount)
    }

    @Test
    fun `test successful reconnection after failures`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 5
        )

        var attemptCount = 0
        var connected = false

        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attemptCount++
            if (attemptCount < 3) {
                throw RuntimeException("Fail first 2 attempts")
            }
            connected = true
        }

        advanceUntilIdle()

        assertTrue("Should eventually connect", connected)
        assertEquals(3, attemptCount)

        val metrics = manager.getMetrics()
        assertEquals(1, metrics.successfulReconnects)
    }

    @Test
    fun `test concurrent reconnection attempts are prevented`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 1000,
            maxAttempts = 3
        )

        var attempt1Count = 0
        var attempt2Count = 0

        // Start first reconnection
        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attempt1Count++
            delay(2000)
        }

        advanceTimeBy(100)

        // Try to start second reconnection (should be ignored)
        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attempt2Count++
        }

        advanceUntilIdle()

        assertTrue("First attempt should have run", attempt1Count > 0)
        assertEquals("Second attempt should be ignored", 0, attempt2Count)
    }

    @Test
    fun `test stop reconnection cancels attempts`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 1000,
            maxAttempts = 5
        )

        var attemptCount = 0

        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attemptCount++
            throw RuntimeException("Keep failing")
        }

        advanceTimeBy(500)

        assertTrue("Should have attempted at least once", attemptCount > 0)
        val countBeforeStop = attemptCount

        // Stop reconnection
        manager.stop()
        advanceTimeBy(5000)

        // No more attempts after stop
        assertEquals("No more attempts after stop", countBeforeStop, attemptCount)
        assertFalse(manager.isReconnecting())
    }

    @Test
    fun `test reconnection metrics tracking`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 5
        )

        var attemptCount = 0

        // Fail first 3, then succeed
        manager.reconnect(
            scope = this,
            onStateChange = null,
            healthCheck = null
        ) {
            attemptCount++
            if (attemptCount < 4) {
                throw RuntimeException("Fail")
            }
        }

        advanceUntilIdle()

        val metrics = manager.getMetrics()

        assertEquals("test", metrics.componentName)
        assertEquals(4, metrics.totalReconnects.toInt())
        assertEquals(1, metrics.successfulReconnects.toInt())
        assertEquals(3, metrics.failedReconnects.toInt())
        assertTrue(metrics.successRate > 0)
        assertTrue(metrics.lastReconnectTime > 0)
        assertTrue(metrics.lastSuccessTime > 0)
        assertFalse(metrics.isReconnecting)
    }

    @Test
    fun `test reconnection with timeout cancellation`() = runTest {
        val manager = SmartReconnectionManager(
            componentName = "test",
            baseDelayMs = 100,
            maxAttempts = 3
        )

        val states = mutableListOf<ReconnectionState>()

        manager.reconnect(
            scope = this,
            onStateChange = { state -> states.add(state) },
            healthCheck = null
        ) {
            // Simulate a connection attempt that takes too long
            delay(35000) // > 30 second timeout
        }

        advanceUntilIdle()

        assertTrue(states.any { it is ReconnectionState.TIMEOUT })

        val metrics = manager.getMetrics()
        assertEquals(0, metrics.successfulReconnects)
    }
}