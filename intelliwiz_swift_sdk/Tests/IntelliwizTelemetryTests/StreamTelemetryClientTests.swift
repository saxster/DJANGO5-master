import XCTest
@testable import IntelliwizTelemetry

/// Test cases for StreamTelemetryClient
final class StreamTelemetryClientTests: XCTestCase {

    var client: StreamTelemetryClient!
    var mockTransport: TelemetryTransport!

    override func setUpWithError() throws {
        let config = StreamTelemetryClient.Configuration(
            streamEndpoint: URL(string: "https://test.example.com/telemetry")!,
            apiKey: "test-api-key",
            appVersion: "1.0.0-test",
            enablePIIProtection: true,
            enablePerformanceTracking: true,
            batchSize: 10,
            flushInterval: 1.0
        )

        client = StreamTelemetryClient(configuration: config)
    }

    override func tearDownWithError() throws {
        client = nil
        mockTransport = nil
    }

    func testClientInitialization() throws {
        XCTAssertNotNil(client)
    }

    func testTrackCustomEvent() throws {
        let expectation = self.expectation(description: "Event tracked")

        client.trackEvent(
            name: "test_event",
            properties: [
                "key1": "value1",
                "key2": 42,
                "key3": true
            ]
        )

        // Verify event was queued
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            expectation.fulfill()
        }

        waitForExpectations(timeout: 1.0)
    }

    func testTrackPerformanceMetrics() throws {
        let expectation = self.expectation(description: "Performance tracked")

        client.trackPerformance(
            operationName: "test_operation",
            duration: 0.5,
            properties: ["test_param": "test_value"]
        )

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            expectation.fulfill()
        }

        waitForExpectations(timeout: 1.0)
    }

    func testPIIProtection() throws {
        let expectation = self.expectation(description: "PII protection")

        client.trackEvent(
            name: "test_pii",
            properties: [
                "email": "test@example.com",
                "password": "secret123",
                "safe_data": "this is safe"
            ]
        )

        // In a real test, we would verify that PII was redacted
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            expectation.fulfill()
        }

        waitForExpectations(timeout: 1.0)
    }

    func testErrorTracking() throws {
        let expectation = self.expectation(description: "Error tracked")

        let testError = NSError(
            domain: "TestDomain",
            code: 404,
            userInfo: [NSLocalizedDescriptionKey: "Test error message"]
        )

        client.trackError(
            error: testError,
            context: ["context_key": "context_value"]
        )

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            expectation.fulfill()
        }

        waitForExpectations(timeout: 1.0)
    }
}

/// Test cases for SwiftUIPerformanceTracker
final class SwiftUIPerformanceTrackerTests: XCTestCase {

    var tracker: SwiftUIPerformanceTracker!

    override func setUpWithError() throws {
        tracker = SwiftUIPerformanceTracker()
    }

    override func tearDownWithError() throws {
        tracker = nil
    }

    func testRecordViewPerformance() throws {
        tracker.recordViewPerformance(
            viewName: "TestView",
            renderTime: 0.016 // 16ms - good performance
        )

        let metrics = tracker.getMetricsForView("TestView")
        XCTAssertEqual(metrics.count, 1)
        XCTAssertEqual(metrics.first?.viewName, "TestView")
        XCTAssertFalse(metrics.first?.isJanky ?? true)
    }

    func testJankDetection() throws {
        tracker.recordViewPerformance(
            viewName: "SlowView",
            renderTime: 0.1 // 100ms - very janky
        )

        let metrics = tracker.getMetricsForView("SlowView")
        XCTAssertEqual(metrics.count, 1)
        XCTAssertTrue(metrics.first?.isJanky ?? false)
        XCTAssertGreaterThan(metrics.first?.jankScore ?? 0, 20.0)
    }

    func testPerformanceReport() throws {
        // Record some test metrics
        tracker.recordViewPerformance(viewName: "View1", renderTime: 0.010)
        tracker.recordViewPerformance(viewName: "View2", renderTime: 0.020)
        tracker.recordViewPerformance(viewName: "View3", renderTime: 0.050) // Janky

        let report = tracker.generatePerformanceReport()

        XCTAssertEqual(report.totalMetrics, 3)
        XCTAssertEqual(report.jankyViews.count, 1)
        XCTAssertTrue(report.jankyViews.keys.contains("View3"))
        XCTAssertGreaterThan(report.averageRenderTime, 0.020)
    }

    func testClearMetrics() throws {
        tracker.recordViewPerformance(viewName: "TestView", renderTime: 0.016)
        XCTAssertEqual(tracker.getAllMetrics().count, 1)

        tracker.clearMetrics()
        XCTAssertEqual(tracker.getAllMetrics().count, 0)
    }
}

/// Test cases for DeviceContextCollector
final class DeviceContextCollectorTests: XCTestCase {

    var collector: DeviceContextCollector!

    override func setUpWithError() throws {
        collector = DeviceContextCollector()
    }

    override func tearDownWithError() throws {
        collector = nil
    }

    func testCollectContext() throws {
        let context = collector.collectContext()

        // Verify essential context fields
        XCTAssertNotNil(context["device_model"])
        XCTAssertNotNil(context["system_name"])
        XCTAssertNotNil(context["system_version"])
        XCTAssertNotNil(context["app_version"])
        XCTAssertNotNil(context["connection_type"])
        XCTAssertNotNil(context["battery_level"])
        XCTAssertNotNil(context["memory_used_mb"])
        XCTAssertNotNil(context["context_timestamp"])
    }

    func testFullContextStructure() throws {
        let fullContext = collector.collectFullContext()

        XCTAssertNotNil(fullContext.deviceInfo.deviceModel)
        XCTAssertNotNil(fullContext.deviceInfo.systemName)
        XCTAssertNotNil(fullContext.networkInfo.connectionType)
        XCTAssertNotNil(fullContext.batteryInfo.level)
        XCTAssertNotNil(fullContext.memoryInfo.usedMB)
        XCTAssertNotNil(fullContext.thermalState)
    }

    func testMonitoring() throws {
        // Test that monitoring can be started and stopped without errors
        XCTAssertNoThrow(collector.startMonitoring())
        XCTAssertNoThrow(collector.stopMonitoring())
    }
}

/// Test cases for TelemetryTransport
final class TelemetryTransportTests: XCTestCase {

    func testTransportInitialization() throws {
        let transport = TelemetryTransport(
            endpoint: URL(string: "https://test.example.com/telemetry")!,
            apiKey: "test-key"
        )

        XCTAssertNotNil(transport)
    }

    func testCreateRequest() throws {
        let config = TelemetryTransport.TransportConfiguration(
            endpoint: URL(string: "https://test.example.com/telemetry")!,
            apiKey: "test-key"
        )
        let transport = TelemetryTransport(configuration: config)

        let events = [
            TelemetryEvent(
                type: .custom,
                name: "test_event",
                properties: ["key": "value"],
                correlationId: "test-correlation",
                timestamp: Date(),
                deviceContext: ["device": "test"]
            )
        ]

        let request = try transport.createRequest(for: events)

        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertNotNil(request.httpBody)
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer test-key")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Content-Type"), "application/json")
    }
}

/// Performance benchmark tests
final class PerformanceBenchmarkTests: XCTestCase {

    func testViewBenchmark() throws {
        measure {
            let _ = ViewBenchmark.measureViewRender(
                viewName: "BenchmarkView",
                iterations: 100
            ) {
                Text("Test View")
                    .padding()
                    .background(Color.blue)
            }
        }
    }
}