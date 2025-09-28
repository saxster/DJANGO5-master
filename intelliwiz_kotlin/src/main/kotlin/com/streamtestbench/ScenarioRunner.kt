package com.streamtestbench

import com.streamtestbench.generators.MQTTGenerator
import com.streamtestbench.generators.WebSocketGenerator
import com.streamtestbench.models.Protocol
import com.streamtestbench.models.TestResult
import com.streamtestbench.models.TestScenario
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import mu.KotlinLogging
import java.io.File

private val logger = KotlinLogging.logger {}

class ScenarioRunner {
    private val json = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
    }

    suspend fun runScenario(scenario: TestScenario): TestResult {
        logger.info { "🚀 Starting scenario: ${scenario.name}" }
        logger.info { "📊 Protocol: ${scenario.protocol}" }
        logger.info { "🎯 Endpoint: ${scenario.endpoint}" }
        logger.info { "⏱️  Duration: ${scenario.duration_seconds}s" }

        return when (scenario.protocol) {
            Protocol.WEBSOCKET -> runWebSocketScenario(scenario)
            Protocol.MQTT -> runMQTTScenario(scenario)
            Protocol.HTTP -> runHTTPScenario(scenario)
            Protocol.MIXED -> runMixedProtocolScenario(scenario)
        }
    }

    suspend fun runScenariosFromFile(file: File): List<TestResult> {
        logger.info { "📂 Loading scenarios from: ${file.absolutePath}" }

        val scenariosJson = file.readText()
        val scenarios: List<TestScenario> = json.decodeFromString(scenariosJson)

        logger.info { "📋 Found ${scenarios.size} scenarios to run" }

        return coroutineScope {
            scenarios.map { scenario ->
                async { runScenario(scenario) }
            }.awaitAll()
        }
    }

    suspend fun runMultipleScenarios(scenarios: List<TestScenario>, parallel: Boolean = false): List<TestResult> {
        logger.info { "🎭 Running ${scenarios.size} scenarios (parallel: $parallel)" }

        return if (parallel) {
            coroutineScope {
                scenarios.map { scenario ->
                    async { runScenario(scenario) }
                }.awaitAll()
            }
        } else {
            scenarios.map { scenario ->
                runScenario(scenario)
            }
        }
    }

    private suspend fun runWebSocketScenario(scenario: TestScenario): TestResult {
        logger.info { "🔌 Running WebSocket scenario" }
        val generator = WebSocketGenerator(scenario)
        return generator.runScenario()
    }

    private suspend fun runMQTTScenario(scenario: TestScenario): TestResult {
        logger.info { "📡 Running MQTT scenario" }
        val generator = MQTTGenerator(scenario)
        return generator.runScenario()
    }

    private suspend fun runHTTPScenario(scenario: TestScenario): TestResult {
        // HTTP scenario implementation would go here
        logger.warn { "🚧 HTTP scenario not implemented yet" }
        return TestResult(
            scenarioName = scenario.name,
            startTime = System.currentTimeMillis(),
            endTime = System.currentTimeMillis(),
            totalMessages = 0,
            successfulMessages = 0,
            failedMessages = 0,
            averageLatencyMs = 0.0,
            p95LatencyMs = 0.0,
            p99LatencyMs = 0.0,
            throughputQps = 0.0,
            errorRate = 0.0,
            anomaliesDetected = 0,
            connectionMetrics = com.streamtestbench.models.ConnectionMetrics(0, 0, 0, 0, 0.0),
            errors = emptyList()
        )
    }

    private suspend fun runMixedProtocolScenario(scenario: TestScenario): TestResult {
        logger.info { "🌐 Running mixed protocol scenario" }

        // For mixed scenarios, we'll run both WebSocket and MQTT concurrently
        val results = coroutineScope {
            val wsResult = async { runWebSocketScenario(scenario.copy(protocol = Protocol.WEBSOCKET)) }
            val mqttResult = async { runMQTTScenario(scenario.copy(protocol = Protocol.MQTT)) }

            listOf(wsResult.await(), mqttResult.await())
        }

        // Combine results
        return combineResults(scenario.name, results)
    }

    private fun combineResults(scenarioName: String, results: List<TestResult>): TestResult {
        val totalMessages = results.sumOf { it.totalMessages }
        val successfulMessages = results.sumOf { it.successfulMessages }
        val failedMessages = results.sumOf { it.failedMessages }
        val allLatencies = results.flatMap { listOf(it.averageLatencyMs) }
        val allErrors = results.flatMap { it.errors }

        return TestResult(
            scenarioName = scenarioName,
            startTime = results.minOfOrNull { it.startTime } ?: System.currentTimeMillis(),
            endTime = results.maxOfOrNull { it.endTime } ?: System.currentTimeMillis(),
            totalMessages = totalMessages,
            successfulMessages = successfulMessages,
            failedMessages = failedMessages,
            averageLatencyMs = if (allLatencies.isNotEmpty()) allLatencies.average() else 0.0,
            p95LatencyMs = results.map { it.p95LatencyMs }.average(),
            p99LatencyMs = results.map { it.p99LatencyMs }.average(),
            throughputQps = results.sumOf { it.throughputQps },
            errorRate = if (totalMessages > 0) failedMessages.toDouble() / totalMessages else 0.0,
            anomaliesDetected = results.sumOf { it.anomaliesDetected },
            connectionMetrics = com.streamtestbench.models.ConnectionMetrics(
                totalConnections = results.sumOf { it.connectionMetrics.totalConnections },
                successfulConnections = results.sumOf { it.connectionMetrics.successfulConnections },
                failedConnections = results.sumOf { it.connectionMetrics.failedConnections },
                reconnectionCount = results.sumOf { it.connectionMetrics.reconnectionCount },
                averageConnectionTime = results.map { it.connectionMetrics.averageConnectionTime }.average()
            ),
            errors = allErrors
        )
    }

    fun saveResultsToFile(results: List<TestResult>, outputFile: File) {
        logger.info { "💾 Saving results to: ${outputFile.absolutePath}" }

        val resultsJson = json.encodeToString(results)
        outputFile.writeText(resultsJson)

        logger.info { "✅ Results saved successfully" }
    }

    fun generateSummaryReport(results: List<TestResult>): String {
        val report = StringBuilder()

        report.appendLine("📊 Stream Testbench Results Summary")
        report.appendLine("=" * 50)
        report.appendLine()

        results.forEach { result ->
            report.appendLine("🎯 Scenario: ${result.scenarioName}")
            report.appendLine("   Duration: ${(result.endTime - result.startTime) / 1000.0}s")
            report.appendLine("   Total Messages: ${result.totalMessages}")
            report.appendLine("   Successful: ${result.successfulMessages}")
            report.appendLine("   Failed: ${result.failedMessages}")
            report.appendLine("   Success Rate: ${((result.successfulMessages.toDouble() / result.totalMessages.coerceAtLeast(1)) * 100).format(2)}%")
            report.appendLine("   Throughput: ${result.throughputQps.format(2)} QPS")
            report.appendLine("   Avg Latency: ${result.averageLatencyMs.format(2)}ms")
            report.appendLine("   P95 Latency: ${result.p95LatencyMs.format(2)}ms")
            report.appendLine("   P99 Latency: ${result.p99LatencyMs.format(2)}ms")

            if (result.errors.isNotEmpty()) {
                report.appendLine("   ⚠️  Errors:")
                result.errors.take(5).forEach { error ->
                    report.appendLine("     • ${error.errorType}: ${error.count} occurrences")
                }
            }

            report.appendLine()
        }

        // Overall summary
        val totalMessages = results.sumOf { it.totalMessages }
        val totalSuccessful = results.sumOf { it.successfulMessages }
        val totalErrors = results.sumOf { it.failedMessages }
        val avgThroughput = results.map { it.throughputQps }.average()
        val avgLatency = results.map { it.averageLatencyMs }.average()

        report.appendLine("🏆 Overall Summary:")
        report.appendLine("   Total Messages: $totalMessages")
        report.appendLine("   Success Rate: ${((totalSuccessful.toDouble() / totalMessages.coerceAtLeast(1)) * 100).format(2)}%")
        report.appendLine("   Average Throughput: ${avgThroughput.format(2)} QPS")
        report.appendLine("   Average Latency: ${avgLatency.format(2)}ms")
        report.appendLine("   Total Anomalies: ${results.sumOf { it.anomaliesDetected }}")

        return report.toString()
    }

    private fun Double.format(digits: Int): String = "%.${digits}f".format(this)

    companion object {
        private operator fun String.times(n: Int): String = this.repeat(n)
    }
}