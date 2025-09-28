// swift-tools-version: 5.7
// IntelliwizTelemetry Swift SDK for iOS
// Phase 3: Cross-Platform Intelligence Hub

import PackageDescription

let package = Package(
    name: "IntelliwizTelemetry",
    platforms: [
        .iOS(.v14),
        .macOS(.v11),
        .watchOS(.v7),
        .tvOS(.v14)
    ],
    products: [
        .library(
            name: "IntelliwizTelemetry",
            targets: ["IntelliwizTelemetry"]
        ),
    ],
    dependencies: [
        // No external dependencies for maximum compatibility
    ],
    targets: [
        .target(
            name: "IntelliwizTelemetry",
            dependencies: [],
            path: "Sources/IntelliwizTelemetry",
            swiftSettings: [
                .define("INTELLIWIZ_TELEMETRY_ENABLED", .when(configuration: .debug)),
                .define("INTELLIWIZ_PERFORMANCE_MONITORING", .when(configuration: .debug))
            ]
        ),
        .testTarget(
            name: "IntelliwizTelemetryTests",
            dependencies: ["IntelliwizTelemetry"],
            path: "Tests/IntelliwizTelemetryTests"
        ),
    ],
    swiftLanguageVersions: [.v5]
)