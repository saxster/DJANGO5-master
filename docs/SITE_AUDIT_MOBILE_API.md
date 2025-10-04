# Site Audit Mobile API Documentation

**Version:** 1.0
**Last Updated:** 2025-01-28
**Target:** Android (Kotlin), iOS (Swift)
**Base URL:** `/api/v1/onboarding/site-audit/`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Multipart Form Data Specification](#multipart-form-data-specification)
4. [Core Endpoints](#core-endpoints)
5. [Offline Support](#offline-support)
6. [Real-Time Guidance (WebSocket)](#real-time-guidance-websocket)
7. [Error Handling](#error-handling)
8. [Code Examples](#code-examples)

---

## Overview

The Site Audit Mobile API enables voice-first, multimodal security auditing with:

- **Multimodal Capture:** Voice + Photo + GPS in single request
- **Real-time Guidance:** Next-zone recommendations based on coverage
- **Offline Buffering:** Queue observations when offline, sync when online
- **Multilingual Support:** 10+ languages via STT/translation
- **Progress Tracking:** Real-time audit coverage percentage

---

## Authentication

All requests require bearer token authentication:

```http
Authorization: Bearer <JWT_TOKEN>
```

### Get Access Token

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "username": "auditor@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "expires_in": 3600
}
```

---

## Multipart Form Data Specification

### Audio Upload Specification

| Field | Type | Max Size | Formats | Required |
|-------|------|----------|---------|----------|
| `audio_file` | File | 10 MB | webm, ogg, wav, mp3, m4a | Yes |
| `duration_seconds` | Integer | - | - | Yes |
| `language_code` | String | - | en-US, hi-IN, mr-IN, etc. | Yes |

**Supported Audio Formats:**
- **WebM:** Recommended for Android (native MediaRecorder)
- **OGG/Opus:** High quality, good compression
- **WAV:** Uncompressed, larger files
- **MP3:** Universal compatibility
- **M4A/AAC:** iOS native format

**Audio Quality Settings:**
```kotlin
// Android Kotlin Example
MediaRecorder().apply {
    setAudioSource(MediaRecorder.AudioSource.MIC)
    setOutputFormat(MediaRecorder.OutputFormat.WEBM)
    setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
    setAudioEncodingBitRate(128000) // 128 kbps
    setAudioSamplingRate(48000) // 48 kHz
}
```

### Photo Upload Specification

| Field | Type | Max Size | Formats | Required |
|-------|------|----------|---------|----------|
| `photo_file` | File | 25 MB | jpeg, png, heic, webp | No |
| `compass_direction` | Float | - | 0-360 degrees | No |
| `timestamp` | ISO 8601 | - | - | Yes |

**Image Quality Settings:**
- **Resolution:** Max 4000x3000 pixels
- **Compression:** JPEG quality 85%
- **EXIF Data:** Preserve GPS, orientation, timestamp

```kotlin
// Android Kotlin - Image Compression
val options = BitmapFactory.Options().apply {
    inJustDecodeBounds = false
    inSampleSize = calculateInSampleSize(this, 2000, 2000)
}
val bitmap = BitmapFactory.decodeFile(photoPath, options)
```

### GPS Coordinates Specification

| Field | Type | Format | Required |
|-------|------|--------|----------|
| `latitude` | Float | Decimal degrees (-90 to 90) | Yes |
| `longitude` | Float | Decimal degrees (-180 to 180) | Yes |
| `accuracy` | Float | Meters | Yes |
| `altitude` | Float | Meters above sea level | No |
| `captured_at` | ISO 8601 | `2025-01-28T10:30:00Z` | Yes |

---

## Core Endpoints

### 1. Start Site Audit Session

```http
POST /api/v1/onboarding/site-audit/start/
Content-Type: application/json
```

**Request Body:**
```json
{
  "business_unit_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "site_type": "bank_branch",
  "language": "en",
  "operating_hours_start": "09:00",
  "operating_hours_end": "17:00",
  "primary_gps": {
    "latitude": 12.9716,
    "longitude": 77.5946
  },
  "zones": [
    {
      "zone_type": "gate",
      "zone_name": "Main Entrance",
      "importance_level": "critical"
    },
    {
      "zone_type": "vault",
      "zone_name": "Cash Vault",
      "importance_level": "critical"
    }
  ]
}
```

**Response:**
```json
{
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "site_id": "8d3b0a1c-5234-4def-9876-1234567890ab",
  "zones_created": 15,
  "checkpoints_created": 45,
  "estimated_duration_minutes": 45,
  "next_recommended_zone": {
    "zone_id": "9f4e5d6c-7382-4bcd-8901-2345678901bc",
    "zone_name": "Main Entrance",
    "zone_type": "gate",
    "importance_level": "critical",
    "guidance": "Start with main entrance for access control assessment"
  }
}
```

### 2. Submit Multimodal Observation

```http
POST /api/v1/onboarding/site-audit/observations/
Content-Type: multipart/form-data
```

**Request (Multipart Form Data):**
```
audio_file: (binary audio data)
photo_file: (binary image data, optional)
zone_id: "9f4e5d6c-7382-4bcd-8901-2345678901bc"
language_code: "en-US"
latitude: 12.9716
longitude: 77.5946
accuracy: 5.2
captured_at: "2025-01-28T10:35:42Z"
compass_direction: 45.5
duration_seconds: 28
```

**Response:**
```json
{
  "observation_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "transcript_original": "There are two CCTV cameras at the gate",
  "transcript_english": "There are two CCTV cameras at the gate",
  "enhanced_observation": {
    "entities": [
      {
        "type": "asset",
        "name": "CCTV Camera",
        "count": 2,
        "status": "operational"
      }
    ],
    "compliance_issues": [],
    "confidence_score": 0.92
  },
  "processing_time_ms": 1847,
  "next_guidance": {
    "next_zone_id": "b2c3d4e5-6789-01ab-cdef-234567890abc",
    "next_zone_name": "Perimeter Fence",
    "coverage_percentage": 13.3,
    "zones_remaining": 13
  }
}
```

### 3. Get Session Status

```http
GET /api/v1/onboarding/site-audit/sessions/{session_id}/status/
```

**Response:**
```json
{
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "in_progress",
  "coverage_percentage": 53.3,
  "zones_completed": 8,
  "zones_total": 15,
  "critical_zones_completed": 2,
  "critical_zones_total": 3,
  "elapsed_time_minutes": 24,
  "observations_count": 12,
  "photos_count": 18,
  "estimated_time_remaining_minutes": 21
}
```

### 4. Get Next Recommended Zone

```http
GET /api/v1/onboarding/site-audit/sessions/{session_id}/next-zone/
```

**Response:**
```json
{
  "zone_id": "c3d4e5f6-7890-12ab-cdef-34567890abcd",
  "zone_name": "Control Room",
  "zone_type": "control_room",
  "importance_level": "high",
  "guidance": "Verify CCTV monitoring equipment and recording systems",
  "suggested_checkpoints": [
    "DVR/NVR operational status",
    "Monitor display functionality",
    "Recording storage capacity"
  ],
  "estimated_time_minutes": 5
}
```

### 5. Generate Site Audit Report

```http
POST /api/v1/onboarding/site-audit/sessions/{session_id}/generate-report/
Content-Type: application/json
```

**Request Body:**
```json
{
  "report_format": "bilingual",
  "target_language": "hi",
  "include_photos": true,
  "include_citations": true
}
```

**Response:**
```json
{
  "report_id": "d4e5f6a7-8901-23ab-cdef-4567890abcde",
  "pdf_url": "https://api.example.com/reports/d4e5f6a7.pdf",
  "sops_generated": 8,
  "coverage_plan_created": true,
  "compliance_score": 0.87,
  "citations_count": 12,
  "knowledge_base_id": "e5f6a7b8-9012-34ab-cdef-567890abcdef",
  "report_size_bytes": 2457600
}
```

---

## Offline Support

### Offline Buffering Strategy

**Architecture:**
```
┌──────────────┐
│ Mobile App   │
└──────┬───────┘
       │
       ├─ Online:  POST → Server → Immediate Response
       │
       └─ Offline: POST → IndexedDB/SQLite → Queue for sync
```

### Queue Item Structure

```json
{
  "queue_id": "f6a7b8c9-0123-45ab-cdef-67890abcdef0",
  "endpoint": "/api/v1/onboarding/site-audit/observations/",
  "method": "POST",
  "payload": {
    "zone_id": "...",
    "audio_file_path": "/local/audio/recording_001.webm",
    "photo_file_path": "/local/photos/photo_001.jpg",
    "metadata": { "latitude": 12.97, "longitude": 77.59 }
  },
  "captured_at": "2025-01-28T11:15:30Z",
  "retry_count": 0,
  "status": "pending"
}
```

### Retry Logic

```kotlin
// Exponential Backoff
fun calculateRetryDelay(attemptNumber: Int): Long {
    val baseDelay = 1000L // 1 second
    val maxDelay = 60000L // 60 seconds
    val delay = baseDelay * (2.0.pow(attemptNumber.toDouble())).toLong()
    return min(delay, maxDelay)
}

// Retry Strategy
suspend fun syncQueuedObservations() {
    val queuedItems = database.queueDao().getPendingItems()

    for (item in queuedItems) {
        try {
            val response = apiClient.submitObservation(item.payload)

            if (response.isSuccessful) {
                database.queueDao().markAsSynced(item.queue_id)
                deleteLocalFiles(item)
            } else if (response.code() in 400..499) {
                // Client error - don't retry
                database.queueDao().markAsFailed(item.queue_id, response.message())
            } else {
                // Server error - retry
                val retryDelay = calculateRetryDelay(item.retry_count)
                scheduleRetry(item, retryDelay)
            }
        } catch (e: IOException) {
            // Network error - schedule retry
            val retryDelay = calculateRetryDelay(item.retry_count)
            scheduleRetry(item, retryDelay)
        }
    }
}
```

### Conflict Resolution

If server has newer data:
```json
{
  "conflict_detected": true,
  "server_version": {
    "observation_id": "...",
    "updated_at": "2025-01-28T12:00:00Z"
  },
  "client_version": {
    "queue_id": "...",
    "captured_at": "2025-01-28T11:55:00Z"
  },
  "resolution_strategy": "keep_server",
  "reason": "Server version has AI enhancements"
}
```

---

## Real-Time Guidance (WebSocket)

**Optional feature for streaming next-zone recommendations**

### WebSocket Connection

```kotlin
val wsUrl = "wss://api.example.com/ws/site-audit/${sessionId}/"
val webSocket = OkHttpClient().newWebSocket(
    Request.Builder().url(wsUrl).build(),
    object : WebSocketListener() {
        override fun onMessage(webSocket: WebSocket, text: String) {
            val guidance = Json.decodeFromString<GuidanceMessage>(text)
            handleGuidance(guidance)
        }
    }
)
```

### Message Format

**Server → Client (Guidance):**
```json
{
  "type": "next_zone_recommendation",
  "zone_id": "...",
  "zone_name": "Server Room",
  "priority": "high",
  "reason": "Critical zone with high risk level",
  "estimated_time_minutes": 7
}
```

**Client → Server (Observation Complete):**
```json
{
  "type": "observation_completed",
  "observation_id": "...",
  "zone_id": "...",
  "captured_at": "2025-01-28T12:15:00Z"
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Continue |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Fix request format/data |
| 401 | Unauthorized | Refresh auth token |
| 403 | Forbidden | Check user permissions |
| 413 | Payload Too Large | Compress audio/photo |
| 422 | Unprocessable Entity | Validate input data |
| 429 | Too Many Requests | Implement backoff |
| 500 | Server Error | Retry with backoff |
| 503 | Service Unavailable | Queue for offline sync |

### Error Response Format

```json
{
  "error": {
    "code": "AUDIO_TOO_LONG",
    "message": "Audio duration exceeds 120 seconds",
    "field": "audio_file",
    "details": {
      "max_duration_seconds": 120,
      "actual_duration_seconds": 145
    }
  }
}
```

---

## Code Examples

### Android Kotlin - Complete Observation Submission

```kotlin
suspend fun submitObservation(
    audioFile: File,
    photoFile: File?,
    zoneId: String,
    location: Location
): ObservationResponse {
    val requestBody = MultipartBody.Builder()
        .setType(MultipartBody.FORM)
        .addFormDataPart(
            "audio_file",
            audioFile.name,
            audioFile.asRequestBody("audio/webm".toMediaType())
        )
        .addFormDataPart("zone_id", zoneId)
        .addFormDataPart("language_code", "en-US")
        .addFormDataPart("latitude", location.latitude.toString())
        .addFormDataPart("longitude", location.longitude.toString())
        .addFormDataPart("accuracy", location.accuracy.toString())
        .addFormDataPart("captured_at", Instant.now().toString())
        .addFormDataPart("duration_seconds", getAudioDuration(audioFile).toString())

    photoFile?.let {
        requestBody.addFormDataPart(
            "photo_file",
            it.name,
            it.asRequestBody("image/jpeg".toMediaType())
        )
    }

    val request = Request.Builder()
        .url("${baseUrl}/observations/")
        .header("Authorization", "Bearer $accessToken")
        .post(requestBody.build())
        .build()

    return withContext(Dispatchers.IO) {
        val response = httpClient.newCall(request).execute()
        if (response.isSuccessful) {
            Json.decodeFromString<ObservationResponse>(response.body!!.string())
        } else {
            throw ApiException(response.code, response.message)
        }
    }
}
```

### iOS Swift - Multipart Upload

```swift
func submitObservation(
    audioURL: URL,
    photoURL: URL?,
    zoneId: String,
    location: CLLocation
) async throws -> ObservationResponse {
    var request = URLRequest(url: URL(string: "\(baseURL)/observations/")!)
    request.httpMethod = "POST"
    request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

    let boundary = UUID().uuidString
    request.setValue(
        "multipart/form-data; boundary=\(boundary)",
        forHTTPHeaderField: "Content-Type"
    )

    var body = Data()

    // Audio file
    body.append("--\(boundary)\r\n")
    body.append("Content-Disposition: form-data; name=\"audio_file\"; filename=\"audio.m4a\"\r\n")
    body.append("Content-Type: audio/m4a\r\n\r\n")
    body.append(try Data(contentsOf: audioURL))
    body.append("\r\n")

    // Location data
    body.append("--\(boundary)\r\n")
    body.append("Content-Disposition: form-data; name=\"latitude\"\r\n\r\n")
    body.append("\(location.coordinate.latitude)\r\n")

    body.append("--\(boundary)--\r\n")

    request.httpBody = body

    let (data, response) = try await URLSession.shared.data(for: request)

    guard let httpResponse = response as? HTTPURLResponse,
          (200...299).contains(httpResponse.statusCode) else {
        throw APIError.invalidResponse
    }

    return try JSONDecoder().decode(ObservationResponse.self, from: data)
}
```

---

## Performance Guidelines

### Request Size Limits

| Resource | Limit | Compression |
|----------|-------|-------------|
| Audio (Single) | 10 MB | Opus/AAC recommended |
| Photo (Single) | 25 MB | JPEG 85% quality |
| Total Request | 35 MB | gzip transport compression |

### Recommended Settings

```kotlin
// OkHttp Client Configuration
val client = OkHttpClient.Builder()
    .connectTimeout(30, TimeUnit.SECONDS)
    .readTimeout(60, TimeUnit.SECONDS)  // For audio processing
    .writeTimeout(60, TimeUnit.SECONDS) // For uploads
    .addInterceptor(GzipRequestInterceptor())
    .build()
```

### Battery Optimization

- **GPS:** Use `PRIORITY_BALANCED_POWER_ACCURACY` (±10-50m accuracy)
- **Audio Recording:** Stop recording after 120 seconds automatically
- **Photo Capture:** Limit resolution to 2000x2000 for non-critical zones
- **Background Sync:** Use WorkManager with network constraints

---

**API Support:** api-support@intelliwiz.com
**Documentation Updates:** Check `/api/v1/docs/` for latest OpenAPI spec