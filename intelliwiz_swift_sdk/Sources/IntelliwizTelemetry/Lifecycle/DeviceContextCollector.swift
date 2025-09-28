import Foundation
import UIKit
import SystemConfiguration.CaptiveNetwork
import CoreTelephony
import os.log

/// Device Context Collector for iOS
/// Gathers device information, network state, and performance context
public final class DeviceContextCollector {

    // MARK: - Device Context

    public struct DeviceContext {
        public let deviceInfo: DeviceInfo
        public let networkInfo: NetworkInfo
        public let batteryInfo: BatteryInfo
        public let memoryInfo: MemoryInfo
        public let thermalState: ThermalState
        public let lowPowerMode: Bool
        public let timestamp: Date

        public struct DeviceInfo {
            public let deviceModel: String
            public let systemName: String
            public let systemVersion: String
            public let appVersion: String
            public let appBuild: String
            public let deviceId: String
            public let locale: String
            public let timezone: String
            public let screenSize: CGSize
            public let screenScale: CGFloat
        }

        public struct NetworkInfo {
            public let connectionType: ConnectionType
            public let carrierName: String?
            public let wifiSSID: String?
            public let isExpensive: Bool
            public let isConstrained: Bool

            public enum ConnectionType: String, CaseIterable {
                case wifi = "wifi"
                case cellular = "cellular"
                case ethernet = "ethernet"
                case offline = "offline"
                case unknown = "unknown"
            }
        }

        public struct BatteryInfo {
            public let level: Float
            public let state: BatteryState
            public let isCharging: Bool

            public enum BatteryState: String, CaseIterable {
                case charging = "charging"
                case unplugged = "unplugged"
                case full = "full"
                case unknown = "unknown"
            }
        }

        public struct MemoryInfo {
            public let usedMB: Double
            public let availableMB: Double
            public let totalMB: Double
            public let pressureLevel: MemoryPressureLevel

            public enum MemoryPressureLevel: String, CaseIterable {
                case normal = "normal"
                case warning = "warning"
                case critical = "critical"
                case unknown = "unknown"
            }
        }

        public enum ThermalState: String, CaseIterable {
            case nominal = "nominal"
            case fair = "fair"
            case serious = "serious"
            case critical = "critical"
        }
    }

    // MARK: - Properties

    private let logger = OSLog(subsystem: "com.intelliwiz.telemetry", category: "DeviceContext")
    private let deviceInfoQueue = DispatchQueue(label: "deviceContext.queue", qos: .utility)

    // Cached device info (static information)
    private lazy var staticDeviceInfo: DeviceContext.DeviceInfo = {
        return DeviceContext.DeviceInfo(
            deviceModel: deviceModel,
            systemName: UIDevice.current.systemName,
            systemVersion: UIDevice.current.systemVersion,
            appVersion: appVersion,
            appBuild: appBuild,
            deviceId: deviceIdentifier,
            locale: Locale.current.identifier,
            timezone: TimeZone.current.identifier,
            screenSize: UIScreen.main.bounds.size,
            screenScale: UIScreen.main.scale
        )
    }()

    // MARK: - Public API

    /// Collect current device context
    public func collectContext() -> [String: Any] {
        let context = collectFullContext()
        return context.toDictionary()
    }

    /// Collect full structured device context
    public func collectFullContext() -> DeviceContext {
        return DeviceContext(
            deviceInfo: staticDeviceInfo,
            networkInfo: collectNetworkInfo(),
            batteryInfo: collectBatteryInfo(),
            memoryInfo: collectMemoryInfo(),
            thermalState: collectThermalState(),
            lowPowerMode: ProcessInfo.processInfo.isLowPowerModeEnabled,
            timestamp: Date()
        )
    }

    /// Start monitoring device context changes
    public func startMonitoring() {
        // Enable battery monitoring
        UIDevice.current.isBatteryMonitoringEnabled = true

        // Register for notifications
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(batteryStateChanged),
            name: UIDevice.batteryStateDidChangeNotification,
            object: nil
        )

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(batteryLevelChanged),
            name: UIDevice.batteryLevelDidChangeNotification,
            object: nil
        )

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(thermalStateChanged),
            name: ProcessInfo.thermalStateDidChangeNotification,
            object: nil
        )

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(lowPowerModeChanged),
            name: .NSProcessInfoPowerStateDidChange,
            object: nil
        )

        os_log("Device context monitoring started", log: logger, type: .info)
    }

    /// Stop monitoring device context changes
    public func stopMonitoring() {
        NotificationCenter.default.removeObserver(self)
        UIDevice.current.isBatteryMonitoringEnabled = false

        os_log("Device context monitoring stopped", log: logger, type: .info)
    }

    // MARK: - Private Methods - Device Info

    private var deviceModel: String {
        var systemInfo = utsname()
        uname(&systemInfo)
        let machineMirror = Mirror(reflecting: systemInfo.machine)
        let identifier = machineMirror.children.reduce("") { identifier, element in
            guard let value = element.value as? Int8, value != 0 else { return identifier }
            return identifier + String(UnicodeScalar(UInt8(value))!)
        }
        return identifier
    }

    private var appVersion: String {
        return Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown"
    }

    private var appBuild: String {
        return Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "unknown"
    }

    private var deviceIdentifier: String {
        return UIDevice.current.identifierForVendor?.uuidString ?? "unknown"
    }

    // MARK: - Private Methods - Network Info

    private func collectNetworkInfo() -> DeviceContext.NetworkInfo {
        let connectionType = detectConnectionType()
        let carrierName = getCarrierName()
        let wifiSSID = getWifiSSID()

        return DeviceContext.NetworkInfo(
            connectionType: connectionType,
            carrierName: carrierName,
            wifiSSID: wifiSSID,
            isExpensive: isConnectionExpensive(),
            isConstrained: isConnectionConstrained()
        )
    }

    private func detectConnectionType() -> DeviceContext.NetworkInfo.ConnectionType {
        var zeroAddress = sockaddr_in()
        zeroAddress.sin_len = UInt8(MemoryLayout.size(ofValue: zeroAddress))
        zeroAddress.sin_family = sa_family_t(AF_INET)

        guard let defaultRouteReachability = withUnsafePointer(to: &zeroAddress, {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                SCNetworkReachabilityCreateWithAddress(kCFAllocatorDefault, $0)
            }
        }) else {
            return .unknown
        }

        var flags: SCNetworkReachabilityFlags = []
        guard SCNetworkReachabilityGetFlags(defaultRouteReachability, &flags) else {
            return .unknown
        }

        if !flags.contains(.reachable) {
            return .offline
        }

        if flags.contains(.isWWAN) {
            return .cellular
        }

        if !flags.contains(.connectionRequired) {
            return .wifi
        }

        if flags.contains(.connectionOnDemand) || flags.contains(.connectionOnTraffic) {
            if !flags.contains(.interventionRequired) {
                return .wifi
            }
        }

        return .unknown
    }

    private func getCarrierName() -> String? {
        let telephonyInfo = CTTelephonyNetworkInfo()
        return telephonyInfo.subscriberCellularProvider?.carrierName
    }

    private func getWifiSSID() -> String? {
        guard let interfaces = CNCopySupportedInterfaces() as? [String] else {
            return nil
        }

        for interface in interfaces {
            guard let interfaceInfo = CNCopyCurrentNetworkInfo(interface as CFString) as NSDictionary? else {
                continue
            }

            return interfaceInfo[kCNNetworkInfoKeySSID as String] as? String
        }

        return nil
    }

    private func isConnectionExpensive() -> Bool {
        // iOS doesn't have a direct API for this, but cellular is typically expensive
        return detectConnectionType() == .cellular
    }

    private func isConnectionConstrained() -> Bool {
        // Check low power mode as a proxy for constrained connections
        return ProcessInfo.processInfo.isLowPowerModeEnabled
    }

    // MARK: - Private Methods - Battery Info

    private func collectBatteryInfo() -> DeviceContext.BatteryInfo {
        let device = UIDevice.current

        let batteryState: DeviceContext.BatteryInfo.BatteryState
        switch device.batteryState {
        case .charging:
            batteryState = .charging
        case .unplugged:
            batteryState = .unplugged
        case .full:
            batteryState = .full
        case .unknown:
            batteryState = .unknown
        @unknown default:
            batteryState = .unknown
        }

        return DeviceContext.BatteryInfo(
            level: device.batteryLevel,
            state: batteryState,
            isCharging: device.batteryState == .charging
        )
    }

    // MARK: - Private Methods - Memory Info

    private func collectMemoryInfo() -> DeviceContext.MemoryInfo {
        let memoryInfo = mach_memory_info()

        return DeviceContext.MemoryInfo(
            usedMB: Double(memoryInfo.used) / (1024 * 1024),
            availableMB: Double(memoryInfo.free) / (1024 * 1024),
            totalMB: Double(memoryInfo.total) / (1024 * 1024),
            pressureLevel: memoryInfo.pressureLevel
        )
    }

    private func mach_memory_info() -> (used: UInt64, free: UInt64, total: UInt64, pressureLevel: DeviceContext.MemoryInfo.MemoryPressureLevel) {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size) / 4

        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }

        guard result == KERN_SUCCESS else {
            return (0, 0, 0, .unknown)
        }

        // Get physical memory
        let physicalMemory = ProcessInfo.processInfo.physicalMemory
        let usedMemory = info.resident_size
        let freeMemory = physicalMemory - usedMemory

        // Estimate memory pressure based on usage
        let usageRatio = Double(usedMemory) / Double(physicalMemory)
        let pressureLevel: DeviceContext.MemoryInfo.MemoryPressureLevel
        if usageRatio > 0.9 {
            pressureLevel = .critical
        } else if usageRatio > 0.8 {
            pressureLevel = .warning
        } else {
            pressureLevel = .normal
        }

        return (usedMemory, freeMemory, physicalMemory, pressureLevel)
    }

    // MARK: - Private Methods - Thermal State

    private func collectThermalState() -> DeviceContext.ThermalState {
        let thermalState = ProcessInfo.processInfo.thermalState

        switch thermalState {
        case .nominal:
            return .nominal
        case .fair:
            return .fair
        case .serious:
            return .serious
        case .critical:
            return .critical
        @unknown default:
            return .nominal
        }
    }

    // MARK: - Notification Handlers

    @objc private func batteryStateChanged() {
        os_log("Battery state changed", log: logger, type: .debug)
        reportContextChange("battery_state_changed")
    }

    @objc private func batteryLevelChanged() {
        os_log("Battery level changed", log: logger, type: .debug)
        reportContextChange("battery_level_changed")
    }

    @objc private func thermalStateChanged() {
        os_log("Thermal state changed", log: logger, type: .debug)
        reportContextChange("thermal_state_changed")
    }

    @objc private func lowPowerModeChanged() {
        os_log("Low power mode changed", log: logger, type: .debug)
        reportContextChange("low_power_mode_changed")
    }

    private func reportContextChange(_ changeType: String) {
        deviceInfoQueue.async {
            let context = self.collectContext()

            StreamTelemetryClient.instance?.trackEvent(
                name: "device_context_changed",
                properties: [
                    "change_type": changeType,
                    "device_context": context
                ]
            )
        }
    }
}

// MARK: - DeviceContext Dictionary Conversion

private extension DeviceContextCollector.DeviceContext {
    func toDictionary() -> [String: Any] {
        var dict: [String: Any] = [:]

        // Device info
        dict["device_model"] = deviceInfo.deviceModel
        dict["system_name"] = deviceInfo.systemName
        dict["system_version"] = deviceInfo.systemVersion
        dict["app_version"] = deviceInfo.appVersion
        dict["app_build"] = deviceInfo.appBuild
        dict["device_id"] = deviceInfo.deviceId
        dict["locale"] = deviceInfo.locale
        dict["timezone"] = deviceInfo.timezone
        dict["screen_width"] = deviceInfo.screenSize.width
        dict["screen_height"] = deviceInfo.screenSize.height
        dict["screen_scale"] = deviceInfo.screenScale

        // Network info
        dict["connection_type"] = networkInfo.connectionType.rawValue
        dict["carrier_name"] = networkInfo.carrierName
        dict["wifi_ssid"] = networkInfo.wifiSSID
        dict["is_expensive_connection"] = networkInfo.isExpensive
        dict["is_constrained_connection"] = networkInfo.isConstrained

        // Battery info
        dict["battery_level"] = batteryInfo.level
        dict["battery_state"] = batteryInfo.state.rawValue
        dict["is_charging"] = batteryInfo.isCharging

        // Memory info
        dict["memory_used_mb"] = memoryInfo.usedMB
        dict["memory_available_mb"] = memoryInfo.availableMB
        dict["memory_total_mb"] = memoryInfo.totalMB
        dict["memory_pressure"] = memoryInfo.pressureLevel.rawValue

        // Thermal and power
        dict["thermal_state"] = thermalState.rawValue
        dict["low_power_mode"] = lowPowerMode

        dict["context_timestamp"] = timestamp.timeIntervalSince1970

        return dict
    }
}