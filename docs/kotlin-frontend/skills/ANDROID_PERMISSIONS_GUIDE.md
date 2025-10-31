# ANDROID PERMISSIONS & GPS LOCATION GUIDE
## Runtime Permissions & FusedLocationProvider Best Practices

**Version**: 1.0
**Last Updated**: October 30, 2025
**Based on**: Android 14 (API 34), developer.android.com October 2025

---

## Table of Contents

1. [Runtime Permissions Flow](#1-runtime-permissions-flow)
2. [Location Permissions (Special Rules)](#2-location-permissions-special-rules)
3. [FusedLocationProvider](#3-fusedlocationprovider)
4. [Geofencing](#4-geofencing)
5. [Common Issues](#5-common-issues)

---

## 1. Runtime Permissions Flow

### 1.1 The Standard Flow

```
Check Permission → Granted?
                      ↓ No
Show Rationale? → Show Dialog → Request Permission → Granted?
                                                        ↓ No
                                              Permanently Denied? → Redirect to Settings
```

### 1.2 Complete Implementation

```kotlin
class PermissionManager @Inject constructor(
    private val activity: ComponentActivity
) {
    private val requestPermissionLauncher =
        activity.registerForActivityResult(
            ActivityResultContracts.RequestPermission()
        ) { isGranted ->
            if (isGranted) {
                // Permission granted
                onPermissionGranted()
            } else {
                // Permission denied
                handlePermissionDenied()
            }
        }

    fun requestLocationPermission() {
        when {
            // Already granted
            hasLocationPermission() -> {
                onPermissionGranted()
            }

            // Should show rationale
            activity.shouldShowRequestPermissionRationale(
                Manifest.permission.ACCESS_FINE_LOCATION
            ) -> {
                showRationaleDialog()
            }

            // First time requesting
            else -> {
                requestPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            }
        }
    }

    private fun hasLocationPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            activity,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun showRationaleDialog() {
        AlertDialog.Builder(activity)
            .setTitle("Location Permission Required")
            .setMessage("We need location access to track your attendance at work sites.")
            .setPositiveButton("OK") { _, _ ->
                requestPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun handlePermissionDenied() {
        // Check if permanently denied
        if (!activity.shouldShowRequestPermissionRationale(Manifest.permission.ACCESS_FINE_LOCATION)) {
            // Permanently denied - show settings dialog
            showSettingsDialog()
        } else {
            // Denied this time, can ask again
            Toast.makeText(activity, "Location permission required", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showSettingsDialog() {
        AlertDialog.Builder(activity)
            .setTitle("Permission Required")
            .setMessage("Location permission is required. Please enable it in app settings.")
            .setPositiveButton("Open Settings") { _, _ ->
                val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.fromParts("package", activity.packageName, null)
                }
                activity.startActivity(intent)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }
}
```

---

## 2. Location Permissions (Special Rules)

### 2.1 Android 12+ Requirement: Request Both FINE and COARSE

**CRITICAL**: On Android 12, requesting only FINE_LOCATION causes system to ignore the request!

```kotlin
// ❌ WRONG: Only FINE_LOCATION (ignored on Android 12!)
requestPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)

// ✅ CORRECT: Request both in single request
val requestMultiplePermissions = activity.registerForActivityResult(
    ActivityResultContracts.RequestMultiplePermissions()
) { permissions ->
    when {
        permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true -> {
            // Precise location granted
            onPreciseLocationGranted()
        }
        permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true -> {
            // Approximate location granted
            onApproximateLocationGranted()
        }
        else -> {
            // No location access
            onLocationDenied()
        }
    }
}

// Request both
requestMultiplePermissions.launch(arrayOf(
    Manifest.permission.ACCESS_FINE_LOCATION,
    Manifest.permission.ACCESS_COARSE_LOCATION
))
```

**Source**: developer.android.com October 2025

---

### 2.2 Incremental Requests (Android 11+ Requirement)

**CRITICAL**: Android 11+ ignores simultaneous foreground + background request!

```kotlin
// ❌ WRONG: Request foreground + background together (ignored on Android 11+!)
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
    requestMultiplePermissions.launch(arrayOf(
        Manifest.permission.ACCESS_FINE_LOCATION,
        Manifest.permission.ACCESS_BACKGROUND_LOCATION  // Ignored!
    ))
}

// ✅ CORRECT: Incremental requests
// Step 1: Request foreground location first
requestMultiplePermissions.launch(arrayOf(
    Manifest.permission.ACCESS_FINE_LOCATION,
    Manifest.permission.ACCESS_COARSE_LOCATION
))

// Step 2: After foreground granted, request background (user initiates)
fun requestBackgroundLocation() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        // Show explanation first (required for good UX)
        showBackgroundLocationRationale {
            requestPermissionLauncher.launch(
                Manifest.permission.ACCESS_BACKGROUND_LOCATION
            )
        }
    }
}
```

**AndroidManifest.xml**:
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />

<!-- Android 10+ requires explicit declaration -->
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION" />
```

---

## 3. FusedLocationProvider

### 3.1 Setup

```kotlin
class LocationService @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val fusedLocationClient: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)

    suspend fun getCurrentLocation(): Location? {
        if (!hasLocationPermission()) {
            throw PermissionDeniedException("Location permission required")
        }

        return suspendCancellableCoroutine { continuation ->
            fusedLocationClient.getCurrentLocation(
                Priority.PRIORITY_HIGH_ACCURACY,
                CancellationTokenSource().token
            ).addOnSuccessListener { location ->
                continuation.resume(location)
            }.addOnFailureListener { exception ->
                continuation.resumeWithException(exception)
            }
        }
    }

    suspend fun getLastKnownLocation(): Location? {
        if (!hasLocationPermission()) {
            return null
        }

        return suspendCancellableCoroutine { continuation ->
            fusedLocationClient.lastLocation
                .addOnSuccessListener { location ->
                    continuation.resume(location)
                }
                .addOnFailureListener { exception ->
                    continuation.resumeWithException(exception)
                }
        }
    }

    private fun hasLocationPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }
}
```

---

### 3.2 getCurrentLocation vs getLastLocation

| Method | When to Use | Accuracy | Battery | Latency |
|--------|-------------|----------|---------|---------|
| **getCurrentLocation()** | Need fresh location | High (~50m, often better) | Medium | 1-5s |
| **getLastLocation()** | Quick estimate OK | Variable (could be stale) | Low | <100ms |

**Recommendation**: Use getCurrentLocation() for attendance (need fresh, accurate location)

```kotlin
// For attendance clock-in
suspend fun clockIn() {
    val location = locationService.getCurrentLocation()  // Fresh location

    if (location == null) {
        throw LocationUnavailableException("Unable to determine location")
    }

    // Verify accuracy
    if (location.accuracy > 50) {  // meters
        throw AccuracyTooLowException("GPS accuracy too low: ${location.accuracy}m")
    }

    // Submit to API
    attendanceApi.clockIn(
        lat = location.latitude,
        lng = location.longitude,
        accuracy = location.accuracy
    )
}
```

---

### 3.3 Location Request Configuration

```kotlin
val locationRequest = LocationRequest.Builder(
    Priority.PRIORITY_HIGH_ACCURACY,
    10000  // Interval: 10 seconds
).apply {
    setMinUpdateIntervalMillis(5000)  // Fastest: 5 seconds
    setMaxUpdateDelayMillis(15000)    // Max delay: 15 seconds
    setWaitForAccurateLocation(true)  // Wait for accurate fix
}.build()

// Request location updates
fusedLocationClient.requestLocationUpdates(
    locationRequest,
    locationCallback,
    Looper.getMainLooper()
)
```

**Priority Levels**:
- `PRIORITY_HIGH_ACCURACY` - GPS (~5-50m, high battery)
- `PRIORITY_BALANCED_POWER_ACCURACY` - WiFi + Cell (~100m, medium battery)
- `PRIORITY_LOW_POWER` - Cell tower (~km, low battery)
- `PRIORITY_PASSIVE` - No new locations, piggyback on other apps

---

## 4. Geofencing

### 4.1 Setup Geofences

```kotlin
class GeofenceManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val geofencingClient = LocationServices.getGeofencingClient(context)

    suspend fun addGeofence(
        id: String,
        latitude: Double,
        longitude: Double,
        radiusMeters: Float
    ) {
        val geofence = Geofence.Builder()
            .setRequestId(id)
            .setCircularRegion(latitude, longitude, radiusMeters)
            .setExpirationDuration(Geofence.NEVER_EXPIRE)
            .setTransitionTypes(
                Geofence.GEOFENCE_TRANSITION_ENTER or
                Geofence.GEOFENCE_TRANSITION_EXIT
            )
            .build()

        val request = GeofencingRequest.Builder()
            .setInitialTrigger(GeofencingRequest.INITIAL_TRIGGER_ENTER)
            .addGeofence(geofence)
            .build()

        val pendingIntent = getGeofencePendingIntent()

        if (ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            geofencingClient.addGeofences(request, pendingIntent)
        }
    }

    private fun getGeofencePendingIntent(): PendingIntent {
        val intent = Intent(context, GeofenceBroadcastReceiver::class.java)
        return PendingIntent.getBroadcast(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
        )
    }
}

// Receiver
class GeofenceBroadcastReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val geofencingEvent = GeofencingEvent.fromIntent(intent) ?: return

        if (geofencingEvent.hasError()) {
            val errorMessage = GeofenceStatusCodes.getStatusCodeString(
                geofencingEvent.errorCode
            )
            Log.e("Geofence", errorMessage)
            return
        }

        when (geofencingEvent.geofenceTransition) {
            Geofence.GEOFENCE_TRANSITION_ENTER -> {
                // User entered geofence
                val geofence = geofencingEvent.triggeringGeofences?.firstOrNull()
                notifyGeofenceEnter(geofence?.requestId)
            }
            Geofence.GEOFENCE_TRANSITION_EXIT -> {
                // User exited geofence
            }
        }
    }
}
```

**Limits**: Max 100 geofences per app

---

## 5. Common Issues

### Issue 1: Location Disabled by User

```kotlin
fun isLocationEnabled(): Boolean {
    val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    return locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
           locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
}

// Prompt user to enable
if (!isLocationEnabled()) {
    AlertDialog.Builder(context)
        .setTitle("Location Services Disabled")
        .setMessage("Please enable location services to use this feature.")
        .setPositiveButton("Enable") { _, _ ->
            val intent = Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
            context.startActivity(intent)
        }
        .setNegativeButton("Cancel", null)
        .show()
}
```

---

### Issue 2: GPS Accuracy Too Low

```kotlin
suspend fun getAccurateLocation(maxAttempts: Int = 3): Location {
    repeat(maxAttempts) { attempt ->
        val location = locationService.getCurrentLocation()

        if (location != null && location.accuracy <= 50) {
            // Accuracy good (≤50m)
            return location
        }

        // Wait and retry
        delay(2000)
    }

    throw AccuracyException("Unable to get accurate location after $maxAttempts attempts")
}
```

---

### Issue 3: Battery Optimization Kills Location Updates

**Solution**: Request to disable battery optimization (for continuous tracking)

```kotlin
fun requestBatteryOptimizationExemption() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val packageName = context.packageName

        if (!powerManager.isIgnoringBatteryOptimizations(packageName)) {
            val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = Uri.parse("package:$packageName")
            }
            context.startActivity(intent)
        }
    }
}
```

**Use sparingly**: Only for apps requiring continuous location (not for our use case)

---

## 6. Production Checklist

- [ ] Request FINE + COARSE together (Android 12 requirement)
- [ ] Incremental requests (foreground first, then background - Android 11 requirement)
- [ ] Show rationale before requesting (best practice)
- [ ] Handle permanently denied (redirect to settings)
- [ ] Check location services enabled
- [ ] Verify GPS accuracy before using (≤50m for attendance)
- [ ] Use getCurrentLocation() for fresh location (not getLastLocation)
- [ ] Handle location unavailable gracefully
- [ ] Test on different Android versions (API 21-34)
- [ ] Test with location disabled
- [ ] Test with permission denied

---

## Summary

This guide ensures **correct GPS implementation for Attendance module**:

✅ Runtime permissions (correct flow, rationale, settings)
✅ Android 12 requirement (request FINE + COARSE together)
✅ Android 11 requirement (incremental foreground → background)
✅ FusedLocationProvider (getCurrentLocation vs getLastLocation)
✅ GPS accuracy validation (≤50m for attendance)
✅ Location services check
✅ Geofencing (enter/exit detection)
✅ Common issues (disabled GPS, low accuracy, battery optimization)

**Required for Attendance module GPS check-in/out.**

---

**Document Version**: 1.0
**Based on**: developer.android.com October 2025, Google Play Services
**Required for**: Attendance module implementation
