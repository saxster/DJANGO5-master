package com.streamtestbench

import com.github.ajalt.clikt.core.CliktCommand
import com.github.ajalt.clikt.core.subcommands
import com.github.ajalt.clikt.parameters.options.*
import com.github.ajalt.clikt.parameters.types.*
import com.streamtestbench.models.*
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import mu.KotlinLogging
import java.io.File

private val logger = KotlinLogging.logger {}

class StreamTestbench : CliktCommand(
    help = """
    🚀 Stream Testbench - Kotlin Load Generator

    Generate realistic load for WebSocket, MQTT, and HTTP streams.
    Designed for testing Django Stream Testbench infrastructure.
    """.trimIndent(),
    name = "streamtestbench"
) {
    override fun run() = Unit
}

class RunCommand : CliktCommand(
    help = "Run a test scenario",
    name = "run"
) {
    private val scenarioFile by option(
        "--scenario", "-s",
        help = "JSON file containing scenario configuration"
    ).file(mustExist = true, canBeDir = false)

    private val endpoint by option(
        "--endpoint", "-e",
        help = "Override endpoint URL"
    )

    private val duration by option(
        "--duration", "-d",
        help = "Override test duration in seconds"
    ).int()

    private val protocol by option(
        "--protocol", "-p",
        help = "Protocol to use (websocket, mqtt, http)"
    ).choice("websocket", "mqtt", "http", "mixed")

    private val connections by option(
        "--connections", "-c",
        help = "Number of concurrent connections"
    ).int()

    private val rate by option(
        "--rate", "-r",
        help = "Messages per second"
    ).double()

    private val output by option(
        "--output", "-o",
        help = "Output file for results"
    ).file()

    private val verbose by option(
        "--verbose", "-v",
        help = "Verbose logging"
    ).flag()

    override fun run() = runBlocking {
        setupLogging(verbose)

        logger.info { "🚀 Starting Stream Testbench" }

        try {
            val scenario = if (scenarioFile != null) {
                loadScenarioFromFile(scenarioFile!!)
            } else {
                createQuickScenario()
            }

            val runner = ScenarioRunner()
            val result = runner.runScenario(scenario)

            // Save results if output file specified
            output?.let { file ->
                runner.saveResultsToFile(listOf(result), file)
            }

            // Print summary
            val summary = runner.generateSummaryReport(listOf(result))
            println(summary)

            // Exit with error code if test failed
            if (result.errorRate > 0.1) { // More than 10% error rate
                logger.error { "Test failed with high error rate: ${(result.errorRate * 100).format(2)}%" }
                kotlin.system.exitProcess(1)
            }

        } catch (e: Exception) {
            logger.error(e) { "Test execution failed: ${e.message}" }
            kotlin.system.exitProcess(1)
        }
    }

    private fun loadScenarioFromFile(file: File): TestScenario {
        val json = Json { ignoreUnknownKeys = true }
        val content = file.readText()
        return json.decodeFromString(content)
    }

    private fun createQuickScenario(): TestScenario {
        val protocolEnum = when (protocol) {
            "websocket" -> Protocol.WEBSOCKET
            "mqtt" -> Protocol.MQTT
            "http" -> Protocol.HTTP
            "mixed" -> Protocol.MIXED
            else -> Protocol.WEBSOCKET
        }

        return TestScenario(
            name = "Quick Test",
            description = "Quick test scenario created from CLI parameters",
            protocol = protocolEnum,
            endpoint = endpoint ?: "localhost:8000/ws/mobile/sync/",
            duration_seconds = duration ?: 60,
            connections = connections ?: 1,
            rates = RateConfig(
                messagesPerSecond = rate ?: 1.0
            ),
            payloads = listOf(PayloadType.HEARTBEAT, PayloadType.METRICS)
        )
    }

    private fun Double.format(digits: Int): String = "%.${digits}f".format(this)
}

class GenerateCommand : CliktCommand(
    help = "Generate example scenario files",
    name = "generate"
) {
    private val type by option(
        "--type", "-t",
        help = "Type of scenario to generate"
    ).choice("websocket", "mqtt", "mixed", "all").default("websocket")

    private val output by option(
        "--output", "-o",
        help = "Output directory for scenario files"
    ).file().default(File("scenarios"))

    override fun run() {
        logger.info { "📝 Generating scenario files" }

        output.mkdirs()

        when (type) {
            "websocket" -> generateWebSocketScenario()
            "mqtt" -> generateMQTTScenario()
            "mixed" -> generateMixedScenario()
            "all" -> {
                generateWebSocketScenario()
                generateMQTTScenario()
                generateMixedScenario()
                generateSoakScenario()
            }
        }

        logger.info { "✅ Scenario files generated in ${output.absolutePath}" }
    }

    private fun generateWebSocketScenario() {
        val scenario = TestScenario(
            name = "WebSocket Load Test",
            description = "High-throughput WebSocket synchronization test",
            protocol = Protocol.WEBSOCKET,
            endpoint = "localhost:8000/ws/mobile/sync/",
            duration_seconds = 300,
            connections = 50,
            rates = RateConfig(
                messagesPerSecond = 10.0,
                burstMultiplier = 2.0,
                rampUpSeconds = 30,
                rampDownSeconds = 30
            ),
            payloads = listOf(
                PayloadType.VOICE_DATA,
                PayloadType.BEHAVIORAL_DATA,
                PayloadType.SESSION_DATA
            ),
            failureInjection = FailureInjectionConfig(
                enabled = true,
                networkDelays = NetworkDelayConfig(
                    enabled = true,
                    rangeMs = NetworkDelayConfig.IntRange(50, 500),
                    probability = 0.05
                ),
                duplicateMessages = DuplicateConfig(
                    probability = 0.01
                )
            )
        )

        saveScenario(scenario, "websocket_load_test.json")
    }

    private fun generateMQTTScenario() {
        val scenario = TestScenario(
            name = "MQTT Message Burst",
            description = "MQTT message publishing with GraphQL mutations",
            protocol = Protocol.MQTT,
            endpoint = "localhost:1883",
            duration_seconds = 180,
            connections = 10,
            rates = RateConfig(
                messagesPerSecond = 5.0,
                burstMultiplier = 3.0
            ),
            payloads = listOf(
                PayloadType.METRICS,
                PayloadType.HEARTBEAT
            ),
            failureInjection = FailureInjectionConfig(
                enabled = true,
                duplicateMessages = DuplicateConfig(probability = 0.02),
                connectionDrops = ConnectionDropConfig(
                    probability = 0.001,
                    reconnectDelayMs = 2000
                )
            )
        )

        saveScenario(scenario, "mqtt_burst_test.json")
    }

    private fun generateMixedScenario() {
        val scenario = TestScenario(
            name = "Mixed Protocol Stress Test",
            description = "Combined WebSocket and MQTT load testing",
            protocol = Protocol.MIXED,
            endpoint = "localhost:8000",
            duration_seconds = 600,
            connections = 100,
            rates = RateConfig(
                messagesPerSecond = 20.0,
                burstMultiplier = 1.5,
                rampUpSeconds = 60,
                rampDownSeconds = 60
            ),
            payloads = listOf(
                PayloadType.VOICE_DATA,
                PayloadType.BEHAVIORAL_DATA,
                PayloadType.SESSION_DATA,
                PayloadType.METRICS
            ),
            failureInjection = FailureInjectionConfig(
                enabled = true,
                networkDelays = NetworkDelayConfig(
                    enabled = true,
                    rangeMs = NetworkDelayConfig.IntRange(10, 1000),
                    probability = 0.03
                ),
                schemaDrift = SchemaDriftConfig(
                    probability = 0.001,
                    mutations = listOf(
                        SchemaMutation(MutationType.ADD_FIELD, "extra_field", "test_value"),
                        SchemaMutation(MutationType.REMOVE_FIELD, "optional_field")
                    )
                )
            )
        )

        saveScenario(scenario, "mixed_protocol_stress.json")
    }

    private fun generateSoakScenario() {
        val scenario = TestScenario(
            name = "24-Hour Soak Test",
            description = "Long-running stability and memory leak detection",
            protocol = Protocol.WEBSOCKET,
            endpoint = "localhost:8000/ws/mobile/sync/",
            duration_seconds = 86400, // 24 hours
            connections = 20,
            rates = RateConfig(
                messagesPerSecond = 2.0, // Lower rate for long-term testing
                burstMultiplier = 1.0
            ),
            payloads = listOf(
                PayloadType.HEARTBEAT,
                PayloadType.METRICS,
                PayloadType.SESSION_DATA
            ),
            failureInjection = FailureInjectionConfig(
                enabled = true,
                networkDelays = NetworkDelayConfig(
                    enabled = true,
                    rangeMs = NetworkDelayConfig.IntRange(100, 2000),
                    probability = 0.01
                ),
                connectionDrops = ConnectionDropConfig(
                    probability = 0.0001, // Very rare connection drops
                    reconnectDelayMs = 5000
                )
            ),
            validation = ValidationConfig(
                validateResponses = true,
                maxLatencyMs = 5000, // More lenient for soak testing
                expectedStatusCodes = listOf(200, 202)
            )
        )

        saveScenario(scenario, "soak_test_24h.json")
    }

    private fun saveScenario(scenario: TestScenario, filename: String) {
        val json = Json { prettyPrint = true }
        val file = File(output, filename)
        file.writeText(json.encodeToString(scenario))
        logger.info { "Generated: ${file.absolutePath}" }
    }
}

class ValidateCommand : CliktCommand(
    help = "Validate scenario configuration files",
    name = "validate"
) {
    private val scenarioFile by argument(
        help = "Scenario file to validate"
    ).file(mustExist = true)

    override fun run() {
        logger.info { "🔍 Validating scenario: ${scenarioFile.absolutePath}" }

        try {
            val json = Json { ignoreUnknownKeys = true }
            val scenario: TestScenario = json.decodeFromString(scenarioFile.readText())

            logger.info { "✅ Scenario validation passed" }
            logger.info { "   Name: ${scenario.name}" }
            logger.info { "   Protocol: ${scenario.protocol}" }
            logger.info { "   Duration: ${scenario.duration_seconds}s" }
            logger.info { "   Connections: ${scenario.connections}" }
            logger.info { "   Rate: ${scenario.rates.messagesPerSecond} msgs/sec" }

            // Additional validation logic
            validateScenarioContent(scenario)

        } catch (e: Exception) {
            logger.error(e) { "❌ Scenario validation failed: ${e.message}" }
            kotlin.system.exitProcess(1)
        }
    }

    private fun validateScenarioContent(scenario: TestScenario) {
        val warnings = mutableListOf<String>()

        if (scenario.duration_seconds > 3600) {
            warnings.add("⚠️  Long duration (>1h) - consider using soak test configuration")
        }

        if (scenario.connections > 1000) {
            warnings.add("⚠️  High connection count (>1000) - ensure system resources are adequate")
        }

        if (scenario.rates.messagesPerSecond > 1000) {
            warnings.add("⚠️  High message rate (>1000/sec) - monitor target system performance")
        }

        if (scenario.failureInjection.enabled) {
            logger.info { "🧪 Failure injection is enabled" }
        }

        warnings.forEach { logger.warn { it } }
    }
}

private fun setupLogging(verbose: Boolean) {
    // Configure logging based on verbose flag
    val logLevel = if (verbose) "DEBUG" else "INFO"
    System.setProperty("org.slf4j.simpleLogger.defaultLogLevel", logLevel)
}

fun main(args: Array<String>) = StreamTestbench()
    .subcommands(RunCommand(), GenerateCommand(), ValidateCommand())
    .main(args)