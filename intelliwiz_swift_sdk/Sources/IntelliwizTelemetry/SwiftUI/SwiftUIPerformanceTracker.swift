import Foundation
import SwiftUI
import UIKit
import os.log

/// SwiftUI Performance Tracker
/// Tracks view rendering performance, animation smoothness, and layout metrics
public final class SwiftUIPerformanceTracker {

    // MARK: - Performance Metrics

    public struct ViewPerformanceMetrics {
        public let viewName: String
        public let renderTime: TimeInterval
        public let layoutTime: TimeInterval?
        public let frameRate: Double?
        public let memoryUsage: UInt64?
        public let timestamp: Date

        public var jankScore: Double {
            // Calculate jank score based on render time
            // Target: 16.67ms for 60fps, 8.33ms for 120fps
            let targetFrameTime: TimeInterval = 16.67 / 1000.0 // 16.67ms in seconds
            let jankMultiplier = max(1.0, renderTime / targetFrameTime)
            return min(jankMultiplier * 10.0, 100.0) // Cap at 100
        }

        public var isJanky: Bool {
            return jankScore > 20.0
        }
    }

    // MARK: - Properties

    private let logger = OSLog(subsystem: "com.intelliwiz.telemetry", category: "SwiftUIPerformance")
    private var performanceMetrics: [ViewPerformanceMetrics] = []
    private let metricsLock = NSLock()
    private let displayLink: CADisplayLink?
    private var lastFrameTime: CFTimeInterval = 0
    private var frameCount: Int = 0
    private var frameRateBuffer: [Double] = []

    // MARK: - Initialization

    public init() {
        // Setup display link for frame rate monitoring
        displayLink = CADisplayLink(target: self, selector: #selector(displayLinkTick))
        displayLink?.add(to: .main, forMode: .common)
    }

    deinit {
        displayLink?.invalidate()
    }

    // MARK: - Public API

    /// Record view performance metrics
    public func recordViewPerformance(
        viewName: String,
        renderTime: TimeInterval,
        layoutTime: TimeInterval? = nil
    ) {
        let metrics = ViewPerformanceMetrics(
            viewName: viewName,
            renderTime: renderTime,
            layoutTime: layoutTime,
            frameRate: getCurrentFrameRate(),
            memoryUsage: getCurrentMemoryUsage(),
            timestamp: Date()
        )

        metricsLock.lock()
        performanceMetrics.append(metrics)
        metricsLock.unlock()

        if metrics.isJanky {
            os_log("Jank detected in view %@: render time %.2fms, jank score: %.1f",
                   log: logger, type: .info, viewName, renderTime * 1000, metrics.jankScore)
        }

        // Report to telemetry client
        reportPerformanceMetrics(metrics)
    }

    /// Get performance metrics for a specific view
    public func getMetricsForView(_ viewName: String) -> [ViewPerformanceMetrics] {
        metricsLock.lock()
        defer { metricsLock.unlock() }

        return performanceMetrics.filter { $0.viewName == viewName }
    }

    /// Get all performance metrics
    public func getAllMetrics() -> [ViewPerformanceMetrics] {
        metricsLock.lock()
        defer { metricsLock.unlock() }

        return performanceMetrics
    }

    /// Clear performance metrics
    public func clearMetrics() {
        metricsLock.lock()
        performanceMetrics.removeAll()
        metricsLock.unlock()
    }

    /// Generate performance report
    public func generatePerformanceReport(for timeInterval: TimeInterval = 300) -> PerformanceReport {
        metricsLock.lock()
        defer { metricsLock.unlock() }

        let cutoffTime = Date().addingTimeInterval(-timeInterval)
        let recentMetrics = performanceMetrics.filter { $0.timestamp > cutoffTime }

        return PerformanceReport(metrics: recentMetrics)
    }

    // MARK: - Private Methods

    @objc private func displayLinkTick() {
        let currentTime = displayLink?.timestamp ?? 0

        if lastFrameTime > 0 {
            let frameDuration = currentTime - lastFrameTime
            let frameRate = 1.0 / frameDuration

            frameRateBuffer.append(frameRate)
            if frameRateBuffer.count > 60 { // Keep last 60 frames (1 second at 60fps)
                frameRateBuffer.removeFirst()
            }
        }

        lastFrameTime = currentTime
        frameCount += 1
    }

    private func getCurrentFrameRate() -> Double? {
        guard !frameRateBuffer.isEmpty else { return nil }
        return frameRateBuffer.reduce(0, +) / Double(frameRateBuffer.count)
    }

    private func getCurrentMemoryUsage() -> UInt64? {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size) / 4

        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }

        return result == KERN_SUCCESS ? info.resident_size : nil
    }

    private func reportPerformanceMetrics(_ metrics: ViewPerformanceMetrics) {
        let properties: [String: Any] = [
            "view_name": metrics.viewName,
            "render_time_ms": metrics.renderTime * 1000,
            "layout_time_ms": metrics.layoutTime ?? 0.0 * 1000,
            "jank_score": metrics.jankScore,
            "frame_rate": metrics.frameRate ?? 0.0,
            "memory_usage_mb": Double(metrics.memoryUsage ?? 0) / (1024 * 1024),
            "is_janky": metrics.isJanky
        ]

        StreamTelemetryClient.instance?.trackPerformance(
            operationName: "swiftui_view_render",
            duration: metrics.renderTime,
            properties: properties
        )
    }
}

// MARK: - Performance Report

public struct PerformanceReport {
    public let totalMetrics: Int
    public let jankyViews: [String: Int]
    public let averageRenderTime: TimeInterval
    public let averageJankScore: Double
    public let frameRateStats: FrameRateStats?
    public let memoryStats: MemoryStats?
    public let generatedAt: Date

    public struct FrameRateStats {
        public let average: Double
        public let minimum: Double
        public let maximum: Double
        public let standardDeviation: Double
    }

    public struct MemoryStats {
        public let averageMB: Double
        public let peakMB: Double
        public let minimumMB: Double
    }

    internal init(metrics: [SwiftUIPerformanceTracker.ViewPerformanceMetrics]) {
        self.totalMetrics = metrics.count
        self.generatedAt = Date()

        // Calculate janky views
        var jankyViewCounts: [String: Int] = [:]
        for metric in metrics where metric.isJanky {
            jankyViewCounts[metric.viewName, default: 0] += 1
        }
        self.jankyViews = jankyViewCounts

        // Calculate average render time
        self.averageRenderTime = metrics.isEmpty ? 0 : metrics.map(\.renderTime).reduce(0, +) / Double(metrics.count)

        // Calculate average jank score
        self.averageJankScore = metrics.isEmpty ? 0 : metrics.map(\.jankScore).reduce(0, +) / Double(metrics.count)

        // Calculate frame rate stats
        let frameRates = metrics.compactMap(\.frameRate)
        if !frameRates.isEmpty {
            let average = frameRates.reduce(0, +) / Double(frameRates.count)
            let minimum = frameRates.min() ?? 0
            let maximum = frameRates.max() ?? 0
            let variance = frameRates.map { pow($0 - average, 2) }.reduce(0, +) / Double(frameRates.count)
            let standardDeviation = sqrt(variance)

            self.frameRateStats = FrameRateStats(
                average: average,
                minimum: minimum,
                maximum: maximum,
                standardDeviation: standardDeviation
            )
        } else {
            self.frameRateStats = nil
        }

        // Calculate memory stats
        let memoryUsages = metrics.compactMap(\.memoryUsage).map { Double($0) / (1024 * 1024) }
        if !memoryUsages.isEmpty {
            let averageMB = memoryUsages.reduce(0, +) / Double(memoryUsages.count)
            let peakMB = memoryUsages.max() ?? 0
            let minimumMB = memoryUsages.min() ?? 0

            self.memoryStats = MemoryStats(
                averageMB: averageMB,
                peakMB: peakMB,
                minimumMB: minimumMB
            )
        } else {
            self.memoryStats = nil
        }
    }
}

// MARK: - SwiftUI View Modifier

/// SwiftUI View Modifier for automatic performance tracking
public struct PerformanceTrackingModifier: ViewModifier {
    let viewName: String
    let tracker: SwiftUIPerformanceTracker

    public init(viewName: String, tracker: SwiftUIPerformanceTracker = SwiftUIPerformanceTracker()) {
        self.viewName = viewName
        self.tracker = tracker
    }

    public func body(content: Content) -> some View {
        content
            .onAppear {
                trackViewPerformance()
            }
            .onChange(of: viewName) { _ in
                trackViewPerformance()
            }
    }

    private func trackViewPerformance() {
        let startTime = CACurrentMediaTime()

        DispatchQueue.main.async {
            let endTime = CACurrentMediaTime()
            let renderTime = endTime - startTime

            self.tracker.recordViewPerformance(
                viewName: self.viewName,
                renderTime: renderTime
            )
        }
    }
}

// MARK: - SwiftUI Extensions

public extension View {
    /// Add performance tracking to any SwiftUI view
    func trackPerformance(
        name: String,
        tracker: SwiftUIPerformanceTracker = SwiftUIPerformanceTracker()
    ) -> some View {
        self.modifier(PerformanceTrackingModifier(viewName: name, tracker: tracker))
    }
}

// MARK: - Performance Benchmarking

/// Utility for benchmarking view operations
public struct ViewBenchmark {
    public static func measureViewRender<T: View>(
        viewName: String,
        iterations: Int = 1,
        @ViewBuilder view: () -> T
    ) -> TimeInterval {
        var totalTime: TimeInterval = 0

        for _ in 0..<iterations {
            let startTime = CACurrentMediaTime()

            // Create and render the view
            let testView = view()
            let hostingController = UIHostingController(rootView: testView)
            hostingController.view.layoutIfNeeded()

            let endTime = CACurrentMediaTime()
            totalTime += (endTime - startTime)
        }

        let averageTime = totalTime / Double(iterations)

        // Report to performance tracker
        StreamTelemetryClient.instance?.trackPerformance(
            operationName: "view_benchmark",
            duration: averageTime,
            properties: [
                "view_name": viewName,
                "iterations": iterations,
                "total_time_ms": totalTime * 1000,
                "average_time_ms": averageTime * 1000
            ]
        )

        return averageTime
    }
}

#if DEBUG
// MARK: - Debug Extensions

public extension SwiftUIPerformanceTracker {
    /// Print performance summary to console (debug only)
    func printPerformanceSummary() {
        let report = generatePerformanceReport()

        print("\n=== SwiftUI Performance Summary ===")
        print("Total metrics: \(report.totalMetrics)")
        print("Average render time: \(String(format: "%.2f", report.averageRenderTime * 1000))ms")
        print("Average jank score: \(String(format: "%.1f", report.averageJankScore))")

        if let frameRateStats = report.frameRateStats {
            print("Frame rate - Avg: \(String(format: "%.1f", frameRateStats.average))fps, Min: \(String(format: "%.1f", frameRateStats.minimum))fps, Max: \(String(format: "%.1f", frameRateStats.maximum))fps")
        }

        if let memoryStats = report.memoryStats {
            print("Memory - Avg: \(String(format: "%.1f", memoryStats.averageMB))MB, Peak: \(String(format: "%.1f", memoryStats.peakMB))MB")
        }

        if !report.jankyViews.isEmpty {
            print("Janky views:")
            for (viewName, count) in report.jankyViews.sorted(by: { $0.value > $1.value }) {
                print("  \(viewName): \(count) occurrences")
            }
        }
        print("================================\n")
    }
}
#endif