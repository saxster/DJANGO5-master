package com.intelliwiz.mobile.telemetry.lifecycle

import android.app.ActivityManager
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.telephony.TelephonyManager
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import mu.KotlinLogging
import java.io.File
import java.util.*

private val logger = KotlinLogging.logger {}

/**
 * Device and OS Context Collection System
 *
 * Collects device metadata and system context for correlation with performance metrics.
 * Aligns with existing AnomalyOccurrence client tracking fields:
 * - client_app_version, client_os_version, client_device_model
 */
class DeviceContextCollector(
    private val context: Context
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var lastCollectedContext: DeviceContext? = null

    // System services
    private val activityManager by lazy {
        context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    }
    private val connectivityManager by lazy {
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
    }
    private val batteryManager by lazy {
        context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
    }
    private val telephonyManager by lazy {
        context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
    }

    /**
     * Collect comprehensive device context
     * Maps to existing AnomalyOccurrence fields for trend analysis
     */
    suspend fun collectDeviceContext(): DeviceContext {
        return withContext(Dispatchers.IO) {
            try {
                val deviceContext = DeviceContext(
                    // Map to client_app_version field
                    appVersion = getAppVersion(),

                    // Map to client_os_version field
                    osVersion = getOSVersion(),

                    // Map to client_device_model field
                    deviceModel = getDeviceModel(),

                    // Additional context for performance correlation
                    deviceSpecs = getDeviceSpecs(),
                    networkInfo = getNetworkInfo(),
                    batteryInfo = getBatteryInfo(),
                    memoryInfo = getMemoryInfo(),
                    storageInfo = getStorageInfo(),

                    // Timestamp for context validity
                    collectedAt = System.currentTimeMillis()
                )

                lastCollectedContext = deviceContext
                logger.debug { "Device context collected: ${deviceContext.deviceModel}" }

                deviceContext
            } catch (e: Exception) {
                logger.error(e) { "Failed to collect device context: ${e.message}" }
                getEmptyContext()
            }
        }
    }

    /**
     * Get app version (maps to client_app_version)
     */
    private fun getAppVersion(): String {
        return try {
            val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            "${packageInfo.versionName} (${packageInfo.longVersionCode})"
        } catch (e: Exception) {
            "unknown"
        }
    }

    /**
     * Get OS version (maps to client_os_version)
     */
    private fun getOSVersion(): String {
        return "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"
    }

    /**
     * Get device model (maps to client_device_model)
     */
    private fun getDeviceModel(): String {
        val manufacturer = Build.MANUFACTURER
        val model = Build.MODEL
        return if (model.startsWith(manufacturer)) {
            model
        } else {
            "$manufacturer $model"
        }
    }

    /**
     * Get detailed device specifications
     */
    private fun getDeviceSpecs(): DeviceSpecs {
        return DeviceSpecs(
            brand = Build.BRAND,
            manufacturer = Build.MANUFACTURER,
            model = Build.MODEL,
            device = Build.DEVICE,
            hardware = Build.HARDWARE,
            cpuAbi = Build.SUPPORTED_ABIS.firstOrNull() ?: "unknown",
            screenDensity = context.resources.displayMetrics.densityDpi,
            screenWidth = context.resources.displayMetrics.widthPixels,
            screenHeight = context.resources.displayMetrics.heightPixels
        )
    }

    /**
     * Get network information for performance correlation
     */
    private fun getNetworkInfo(): NetworkInfo {
        return try {
            val networkCapabilities = connectivityManager?.activeNetwork?.let { network ->
                connectivityManager?.getNetworkCapabilities(network)
            }

            NetworkInfo(
                isConnected = networkCapabilities != null,
                connectionType = when {
                    networkCapabilities?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true -> "wifi"
                    networkCapabilities?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) == true -> "cellular"
                    networkCapabilities?.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) == true -> "ethernet"
                    else -> "unknown"
                },
                isMetered = connectivityManager?.isActiveNetworkMetered ?: false,
                networkOperator = telephonyManager?.networkOperatorName ?: "unknown"
            )
        } catch (e: Exception) {
            logger.warn(e) { "Failed to collect network info: ${e.message}" }
            NetworkInfo(false, "unknown", false, "unknown")
        }
    }

    /**
     * Get battery information for performance correlation
     */
    private fun getBatteryInfo(): BatteryInfo {
        return try {
            BatteryInfo(
                level = batteryManager?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1,
                isCharging = batteryManager?.isCharging ?: false,
                temperature = getBatteryTemperature(),
                health = getBatteryHealth()
            )
        } catch (e: Exception) {
            logger.warn(e) { "Failed to collect battery info: ${e.message}" }
            BatteryInfo(-1, false, -1, "unknown")
        }
    }

    /**
     * Get memory information for performance correlation
     */
    private fun getMemoryInfo(): MemoryInfo {
        return try {
            val memInfo = ActivityManager.MemoryInfo()
            activityManager?.getMemoryInfo(memInfo)

            MemoryInfo(
                totalMemoryMB = (memInfo.totalMem / (1024 * 1024)).toInt(),
                availableMemoryMB = (memInfo.availMem / (1024 * 1024)).toInt(),
                isLowMemory = memInfo.lowMemory,
                memoryPressure = calculateMemoryPressure(memInfo)
            )
        } catch (e: Exception) {
            logger.warn(e) { "Failed to collect memory info: ${e.message}" }
            MemoryInfo(0, 0, false, "unknown")
        }
    }

    /**
     * Get storage information
     */
    private fun getStorageInfo(): StorageInfo {
        return try {
            val internalDir = context.filesDir
            val totalSpace = internalDir.totalSpace / (1024 * 1024 * 1024) // GB
            val freeSpace = internalDir.freeSpace / (1024 * 1024 * 1024) // GB

            StorageInfo(
                totalStorageGB = totalSpace.toInt(),
                freeStorageGB = freeSpace.toInt(),
                usagePercentage = if (totalSpace > 0) {
                    ((totalSpace - freeSpace) / totalSpace * 100).toInt()
                } else 0
            )
        } catch (e: Exception) {
            logger.warn(e) { "Failed to collect storage info: ${e.message}" }
            StorageInfo(0, 0, 0)
        }
    }

    /**
     * Get battery temperature
     */
    private fun getBatteryTemperature(): Int {
        return try {
            batteryManager?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW) ?: -1
        } catch (e: Exception) {
            -1
        }
    }

    /**
     * Get battery health status
     */
    private fun getBatteryHealth(): String {
        return try {
            val healthProperty = batteryManager?.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS)
            when (healthProperty) {
                BatteryManager.BATTERY_STATUS_CHARGING -> "charging"
                BatteryManager.BATTERY_STATUS_DISCHARGING -> "discharging"
                BatteryManager.BATTERY_STATUS_FULL -> "full"
                BatteryManager.BATTERY_STATUS_NOT_CHARGING -> "not_charging"
                else -> "unknown"
            }
        } catch (e: Exception) {
            "unknown"
        }
    }

    /**
     * Calculate memory pressure indicator
     */
    private fun calculateMemoryPressure(memInfo: ActivityManager.MemoryInfo): String {
        val usagePercentage = if (memInfo.totalMem > 0) {
            ((memInfo.totalMem - memInfo.availMem) / memInfo.totalMem.toDouble()) * 100
        } else 0.0

        return when {
            usagePercentage > 90 -> "critical"
            usagePercentage > 80 -> "high"
            usagePercentage > 60 -> "medium"
            else -> "low"
        }
    }

    /**
     * Get empty context as fallback
     */
    private fun getEmptyContext(): DeviceContext {
        return DeviceContext(
            appVersion = "unknown",
            osVersion = "unknown",
            deviceModel = "unknown",
            deviceSpecs = DeviceSpecs("unknown", "unknown", "unknown", "unknown", "unknown", "unknown", 0, 0, 0),
            networkInfo = NetworkInfo(false, "unknown", false, "unknown"),
            batteryInfo = BatteryInfo(-1, false, -1, "unknown"),
            memoryInfo = MemoryInfo(0, 0, false, "unknown"),
            storageInfo = StorageInfo(0, 0, 0),
            collectedAt = System.currentTimeMillis()
        )
    }

    /**
     * Get cached context or collect new one
     */
    fun getCachedOrCollect(): DeviceContext {
        return lastCollectedContext ?: runBlocking { collectDeviceContext() }
    }

    /**
     * Shutdown collector
     */
    fun shutdown() {
        scope.cancel()
        logger.info { "DeviceContextCollector shutdown complete" }
    }
}

/**
 * Complete device context information
 */
data class DeviceContext(
    // Maps to existing AnomalyOccurrence fields
    val appVersion: String,        // -> client_app_version
    val osVersion: String,         // -> client_os_version
    val deviceModel: String,       // -> client_device_model

    // Extended context for performance correlation
    val deviceSpecs: DeviceSpecs,
    val networkInfo: NetworkInfo,
    val batteryInfo: BatteryInfo,
    val memoryInfo: MemoryInfo,
    val storageInfo: StorageInfo,
    val collectedAt: Long
)

/**
 * Device specifications
 */
data class DeviceSpecs(
    val brand: String,
    val manufacturer: String,
    val model: String,
    val device: String,
    val hardware: String,
    val cpuAbi: String,
    val screenDensity: Int,
    val screenWidth: Int,
    val screenHeight: Int
)

/**
 * Network connectivity information
 */
data class NetworkInfo(
    val isConnected: Boolean,
    val connectionType: String, // wifi, cellular, ethernet, unknown
    val isMetered: Boolean,
    val networkOperator: String
)

/**
 * Battery status information
 */
data class BatteryInfo(
    val level: Int, // 0-100 percentage
    val isCharging: Boolean,
    val temperature: Int,
    val health: String
)

/**
 * Memory information
 */
data class MemoryInfo(
    val totalMemoryMB: Int,
    val availableMemoryMB: Int,
    val isLowMemory: Boolean,
    val memoryPressure: String // low, medium, high, critical
)

/**
 * Storage information
 */
data class StorageInfo(
    val totalStorageGB: Int,
    val freeStorageGB: Int,
    val usagePercentage: Int // 0-100
)