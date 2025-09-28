import Foundation
import UIKit
import os.log

/// Stream Telemetry Client for iOS
/// Mirrors the Android Kotlin SDK architecture for unified cross-platform intelligence
@objc public final class StreamTelemetryClient: NSObject {

    // MARK: - Configuration

    public struct Configuration {
        public let streamEndpoint: URL
        public let apiKey: String
        public let appVersion: String
        public let enablePIIProtection: Bool
        public let enablePerformanceTracking: Bool
        public let enableVisualRegression: Bool
        public let batchSize: Int
        public let flushInterval: TimeInterval
        public let maxRetries: Int

        public init(
            streamEndpoint: URL,
            apiKey: String,
            appVersion: String = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown",
            enablePIIProtection: Bool = true,
            enablePerformanceTracking: Bool = true,
            enableVisualRegression: Bool = false,
            batchSize: Int = 50,
            flushInterval: TimeInterval = 30.0,
            maxRetries: Int = 3
        ) {
            self.streamEndpoint = streamEndpoint
            self.apiKey = apiKey
            self.appVersion = appVersion
            self.enablePIIProtection = enablePIIProtection
            self.enablePerformanceTracking = enablePerformanceTracking
            self.enableVisualRegression = enableVisualRegression
            self.batchSize = batchSize
            self.flushInterval = flushInterval
            self.maxRetries = maxRetries
        }
    }

    // MARK: - Properties

    private let configuration: Configuration
    private let transport: TelemetryTransport
    private let deviceContext: DeviceContextCollector
    private let performanceTracker: SwiftUIPerformanceTracker
    private let logger = OSLog(subsystem: "com.intelliwiz.telemetry", category: "StreamClient")

    private var eventQueue: [TelemetryEvent] = []
    private let queueLock = NSLock()
    private var flushTimer: Timer?

    private static var shared: StreamTelemetryClient?

    // MARK: - Initialization

    public init(configuration: Configuration) {
        self.configuration = configuration
        self.transport = TelemetryTransport(
            endpoint: configuration.streamEndpoint,
            apiKey: configuration.apiKey,
            maxRetries: configuration.maxRetries
        )
        self.deviceContext = DeviceContextCollector()
        self.performanceTracker = SwiftUIPerformanceTracker()

        super.init()

        setupFlushTimer()
        setupApplicationObservers()

        os_log("StreamTelemetryClient initialized with endpoint: %@",
               log: logger, type: .info, configuration.streamEndpoint.absoluteString)
    }

    deinit {
        flushTimer?.invalidate()
        flushEvents()
    }

    // MARK: - Public API

    @objc public static func initialize(with configuration: Configuration) {
        shared = StreamTelemetryClient(configuration: configuration)
    }

    @objc public static var instance: StreamTelemetryClient? {
        return shared
    }

    /// Track a custom event
    @objc public func trackEvent(
        name: String,
        properties: [String: Any] = [:],
        correlationId: String? = nil
    ) {
        let event = TelemetryEvent(
            type: .custom,
            name: name,
            properties: sanitizeProperties(properties),
            correlationId: correlationId ?? UUID().uuidString,
            timestamp: Date(),
            deviceContext: deviceContext.collectContext()
        )

        enqueueEvent(event)
    }

    /// Track performance metrics
    @objc public func trackPerformance(
        operationName: String,
        duration: TimeInterval,
        properties: [String: Any] = [:]
    ) {
        guard configuration.enablePerformanceTracking else { return }

        var performanceProperties = properties
        performanceProperties["duration_ms"] = duration * 1000
        performanceProperties["operation_name"] = operationName

        let event = TelemetryEvent(
            type: .performance,
            name: "performance_metric",
            properties: sanitizeProperties(performanceProperties),
            correlationId: UUID().uuidString,
            timestamp: Date(),
            deviceContext: deviceContext.collectContext()
        )

        enqueueEvent(event)
    }

    /// Track SwiftUI view rendering performance
    @objc public func trackViewPerformance(
        viewName: String,
        renderTime: TimeInterval,
        layoutTime: TimeInterval? = nil
    ) {
        guard configuration.enablePerformanceTracking else { return }

        performanceTracker.recordViewPerformance(
            viewName: viewName,
            renderTime: renderTime,
            layoutTime: layoutTime
        )
    }

    /// Track visual regression baseline
    @objc public func trackVisualBaseline(
        viewName: String,
        screenshot: UIImage?,
        properties: [String: Any] = [:]
    ) {
        guard configuration.enableVisualRegression else { return }

        var visualProperties = properties
        visualProperties["view_name"] = viewName
        visualProperties["timestamp"] = Date().timeIntervalSince1970

        if let screenshot = screenshot {
            visualProperties["screenshot_hash"] = screenshot.sha256Hash
            visualProperties["screenshot_size"] = "\(screenshot.size.width)x\(screenshot.size.height)"
        }

        let event = TelemetryEvent(
            type: .visual,
            name: "visual_baseline",
            properties: sanitizeProperties(visualProperties),
            correlationId: UUID().uuidString,
            timestamp: Date(),
            deviceContext: deviceContext.collectContext()
        )

        enqueueEvent(event)
    }

    /// Track error or exception
    @objc public func trackError(
        error: Error,
        context: [String: Any] = [:],
        correlationId: String? = nil
    ) {
        var errorProperties = context
        errorProperties["error_domain"] = (error as NSError).domain
        errorProperties["error_code"] = (error as NSError).code
        errorProperties["error_description"] = error.localizedDescription

        if let nsError = error as NSError? {
            errorProperties["error_user_info"] = sanitizeUserInfo(nsError.userInfo)
        }

        let event = TelemetryEvent(
            type: .error,
            name: "error_occurred",
            properties: sanitizeProperties(errorProperties),
            correlationId: correlationId ?? UUID().uuidString,
            timestamp: Date(),
            deviceContext: deviceContext.collectContext()
        )

        enqueueEvent(event)

        // Immediate flush for errors
        flushEvents()
    }

    /// Manually flush queued events
    @objc public func flush() {
        flushEvents()
    }

    // MARK: - Private Methods

    private func setupFlushTimer() {
        flushTimer = Timer.scheduledTimer(withTimeInterval: configuration.flushInterval, repeats: true) { _ in
            self.flushEvents()
        }
    }

    private func setupApplicationObservers() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(applicationWillTerminate),
            name: UIApplication.willTerminateNotification,
            object: nil
        )

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(applicationDidEnterBackground),
            name: UIApplication.didEnterBackgroundNotification,
            object: nil
        )
    }

    @objc private func applicationWillTerminate() {
        flushEvents()
    }

    @objc private func applicationDidEnterBackground() {
        flushEvents()
    }

    private func enqueueEvent(_ event: TelemetryEvent) {
        queueLock.lock()
        defer { queueLock.unlock() }

        eventQueue.append(event)

        if eventQueue.count >= configuration.batchSize {
            flushEvents()
        }
    }

    private func flushEvents() {
        queueLock.lock()
        let eventsToFlush = eventQueue
        eventQueue.removeAll()
        queueLock.unlock()

        guard !eventsToFlush.isEmpty else { return }

        transport.sendEvents(eventsToFlush) { [weak self] result in
            switch result {
            case .success:
                os_log("Successfully sent %d events", log: self?.logger ?? OSLog.disabled, type: .info, eventsToFlush.count)

            case .failure(let error):
                os_log("Failed to send events: %@", log: self?.logger ?? OSLog.disabled, type: .error, error.localizedDescription)

                // Re-queue events for retry (up to max retries)
                self?.requeueFailedEvents(eventsToFlush)
            }
        }
    }

    private func requeueFailedEvents(_ events: [TelemetryEvent]) {
        // Simple retry logic - in production, would implement exponential backoff
        DispatchQueue.global().asyncAfter(deadline: .now() + 5.0) {
            self.queueLock.lock()
            self.eventQueue.append(contentsOf: events)
            self.queueLock.unlock()
        }
    }

    private func sanitizeProperties(_ properties: [String: Any]) -> [String: Any] {
        guard configuration.enablePIIProtection else { return properties }

        var sanitized: [String: Any] = [:]
        let piiKeys = ["email", "phone", "ssn", "credit_card", "password", "token", "api_key"]

        for (key, value) in properties {
            let lowerKey = key.lowercased()

            if piiKeys.contains(where: lowerKey.contains) {
                sanitized[key] = "[REDACTED]"
            } else if let stringValue = value as? String, stringValue.isEmail {
                sanitized[key] = "[EMAIL_REDACTED]"
            } else {
                sanitized[key] = value
            }
        }

        return sanitized
    }

    private func sanitizeUserInfo(_ userInfo: [AnyHashable: Any]) -> [String: Any] {
        var sanitized: [String: Any] = [:]

        for (key, value) in userInfo {
            if let stringKey = key as? String {
                sanitized[stringKey] = "\(value)"
            }
        }

        return sanitizeProperties(sanitized)
    }
}

// MARK: - TelemetryEvent

public struct TelemetryEvent {
    public enum EventType: String, CaseIterable {
        case custom
        case performance
        case visual
        case error
        case lifecycle
    }

    public let id: String
    public let type: EventType
    public let name: String
    public let properties: [String: Any]
    public let correlationId: String
    public let timestamp: Date
    public let deviceContext: [String: Any]

    public init(
        type: EventType,
        name: String,
        properties: [String: Any],
        correlationId: String,
        timestamp: Date,
        deviceContext: [String: Any]
    ) {
        self.id = UUID().uuidString
        self.type = type
        self.name = name
        self.properties = properties
        self.correlationId = correlationId
        self.timestamp = timestamp
        self.deviceContext = deviceContext
    }
}

// MARK: - Extensions

private extension String {
    var isEmail: Bool {
        let emailRegex = try! NSRegularExpression(pattern: "^[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", options: .caseInsensitive)
        return emailRegex.firstMatch(in: self, options: [], range: NSRange(location: 0, length: count)) != nil
    }
}

private extension UIImage {
    var sha256Hash: String {
        guard let data = self.pngData() else { return "" }

        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
        }

        return hash.map { String(format: "%02x", $0) }.joined()
    }
}

#if canImport(CommonCrypto)
import CommonCrypto
#endif