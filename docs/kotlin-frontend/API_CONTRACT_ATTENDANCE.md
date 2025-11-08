# API Contract: Attendance Domain

> **Domain:** Attendance & Time Tracking (Check-in/out, GPS, Facial Recognition, Shifts)
> **Version:** 1.0.0
> **Last Updated:** November 7, 2025
> **Base URL:** `/api/v2/attendance/`

---

## 📋 Table of Contents

- [Overview](#overview)
- [Check-in / Check-out](#check-in--check-out)
- [Shift Management](#shift-management)
- [Geofencing & GPS](#geofencing--gps)
- [Fraud Detection](#fraud-detection)
- [Travel Expenses](#travel-expenses)
- [Complete Workflows](#complete-workflows)
- [Error Scenarios](#error-scenarios)

---

## Overview

The Attendance domain handles employee time tracking with GPS validation, facial recognition, and fraud detection.

### Key Features

- **GPS-based Check-in/out** - Location verification within geofence
- **Facial Recognition** - Identity verification with anti-spoofing
- **Shift Management** - Scheduled shifts with assignment tracking
- **Fraud Detection** - GPS spoofing, photo manipulation, behavioral anomalies
- **Travel Expenses** - Conveyance tracking with reimbursement
- **Offline Support** - Queue check-ins offline, sync when connected

### Django Implementation

- **Models:** `apps/attendance/models/attendance_models.py`, `apps/attendance/models/shift_models.py`
- **Viewsets:** `apps/attendance/api/viewsets.py`
- **Services:** `apps/attendance/services/`
- **Permissions:** `apps/attendance/permissions.py`

---

## Check-in / Check-out

### 1. Check In

**Endpoint:** `POST /api/v2/attendance/checkin/`

**Django Implementation:**
- **Viewset:** `apps/attendance/api/viewsets.py:AttendanceViewSet.checkin()`
- **Service:** `apps/attendance/services/clock_in_service.py:ClockInService.process_checkin()`
- **Permissions:** `IsAuthenticated`, `HasActiveShift`

**Purpose:** Record employee arrival with GPS + facial verification

**Request:**
```json
{
  "shift_id": 501,
  "checkin_time": "2025-11-15T08:05:00Z",
  "gps_location": {
    "latitude": 1.290270,
    "longitude": 103.851959,
    "accuracy_meters": 12.5,
    "altitude": 45.3,
    "speed": 0.0
  },
  "face_photo": {
    "photo_data": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "photo_quality_score": 0.92,
    "capture_timestamp": "2025-11-15T08:04:55Z"
  },
  "device_info": {
    "device_id": "device-android-abc123",
    "device_model": "Samsung Galaxy S23",
    "os_version": "Android 14",
    "app_version": "2.1.0",
    "battery_level": 85,
    "network_type": "wifi"
  },
  "consent": {
    "gps_tracking": true,
    "facial_recognition": true,
    "consent_timestamp": "2025-11-15T08:05:00Z"
  }
}
```

**Field Validation:**
- `shift_id`: Required, must be assigned to current user
- `checkin_time`: Required, ISO 8601 UTC
- `gps_location.latitude/longitude`: Required, decimal degrees
- `gps_location.accuracy_meters`: Required, max 50 meters for acceptance
- `face_photo.photo_data`: Required, base64 JPEG, max 5 MB
- `consent.gps_tracking`: Required, must be true
- `consent.facial_recognition`: Required, must be true

**Response (201 Created):**
```json
{
  "id": 7001,
  "attendance_number": "ATT-2025-11-7001",
  "user": {
    "id": 123,
    "name": "John Doe",
    "employee_number": "EMP-123"
  },
  "shift": {
    "id": 501,
    "shift_name": "Morning Shift - Security",
    "scheduled_start": "2025-11-15T08:00:00Z",
    "scheduled_end": "2025-11-15T16:00:00Z",
    "site": {
      "id": 789,
      "site_name": "Downtown Office",
      "address": "123 Main St, Singapore"
    }
  },
  "checkin_time": "2025-11-15T08:05:00Z",
  "checkout_time": null,
  "status": "checked_in",
  "gps_validation": {
    "validated": true,
    "distance_from_site_meters": 8.5,
    "accuracy_meters": 12.5,
    "within_geofence": true,
    "spoofing_detected": false,
    "confidence_score": 0.95
  },
  "face_validation": {
    "validated": true,
    "confidence_score": 0.89,
    "liveness_check_passed": true,
    "spoofing_detected": false,
    "reference_photo_age_days": 15
  },
  "time_status": {
    "is_on_time": true,
    "is_late": false,
    "minutes_late": 0,
    "grace_period_used": true
  },
  "fraud_alerts": [],
  "version": 1,
  "created_at": "2025-11-15T08:05:00Z",
  "correlation_id": "req-checkin-abc123"
}
```

**Error Responses:**

**400 Bad Request** - Already checked in:
```json
{
  "error_code": "ALREADY_CHECKED_IN",
  "message": "You are already checked in",
  "existing_checkin": {
    "id": 7000,
    "checkin_time": "2025-11-15T08:00:00Z",
    "site_name": "Downtown Office"
  },
  "action_required": "checkout_first",
  "correlation_id": "req-checkin-abc123"
}
```

**400 Bad Request** - GPS validation failed:
```json
{
  "error_code": "GPS_VALIDATION_FAILED",
  "message": "Location is outside allowed geofence",
  "details": {
    "distance_from_site_meters": 152.3,
    "max_allowed_meters": 100,
    "accuracy_meters": 12.5,
    "site_location": {
      "latitude": 1.290000,
      "longitude": 103.850000
    },
    "your_location": {
      "latitude": 1.291500,
      "longitude": 103.851959
    }
  },
  "correlation_id": "req-checkin-abc123"
}
```

**400 Bad Request** - Facial recognition failed:
```json
{
  "error_code": "FACE_VERIFICATION_FAILED",
  "message": "Face does not match stored profile",
  "details": {
    "confidence_score": 0.62,
    "threshold": 0.85,
    "liveness_check": true,
    "spoofing_detected": false,
    "photo_quality": 0.78,
    "reason": "confidence_below_threshold"
  },
  "action_required": "retake_photo_better_lighting",
  "correlation_id": "req-checkin-abc123"
}
```

**400 Bad Request** - Fraud detected:
```json
{
  "error_code": "FRAUD_DETECTED",
  "message": "Suspicious activity detected - check-in blocked",
  "fraud_type": "gps_spoofing",
  "details": {
    "spoofing_indicators": [
      "location_jump_impossible_speed",
      "mock_location_provider_detected",
      "gps_accuracy_too_perfect"
    ],
    "confidence": 0.94,
    "previous_location": {
      "latitude": 1.350000,
      "longitude": 103.900000,
      "timestamp": "2025-11-15T07:50:00Z"
    },
    "current_location": {
      "latitude": 1.290270,
      "longitude": 103.851959,
      "timestamp": "2025-11-15T08:05:00Z"
    },
    "distance_meters": 8542,
    "time_elapsed_seconds": 900,
    "required_speed_kmh": 34.2,
    "max_plausible_speed_kmh": 15.0
  },
  "action_required": "manual_review_required",
  "correlation_id": "req-checkin-abc123"
}
```

**403 Forbidden** - No active shift:
```json
{
  "error_code": "NO_ACTIVE_SHIFT",
  "message": "You do not have a shift scheduled for this time",
  "current_time": "2025-11-15T08:05:00Z",
  "next_shift": {
    "id": 502,
    "scheduled_start": "2025-11-16T08:00:00Z",
    "site_name": "North Campus"
  },
  "correlation_id": "req-checkin-abc123"
}
```

---

### 2. Check Out

**Endpoint:** `POST /api/v2/attendance/checkout/`

**Django Implementation:**
- **Viewset:** `apps/attendance/api/viewsets.py:AttendanceViewSet.checkout()`
- **Service:** `apps/attendance/services/clock_in_service.py:ClockInService.process_checkout()`
- **Permissions:** `IsAuthenticated`, `HasActiveCheckin`

**Purpose:** Record employee departure and calculate hours worked

**Request:**
```json
{
  "attendance_id": 7001,
  "checkout_time": "2025-11-15T16:10:00Z",
  "gps_location": {
    "latitude": 1.290280,
    "longitude": 103.851960,
    "accuracy_meters": 15.0
  },
  "face_photo": {
    "photo_data": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "photo_quality_score": 0.88,
    "capture_timestamp": "2025-11-15T16:09:55Z"
  },
  "notes": "Shift completed successfully, all rounds done",
  "version": 1
}
```

**Response (200 OK):**
```json
{
  "id": 7001,
  "attendance_number": "ATT-2025-11-7001",
  "user": {
    "id": 123,
    "name": "John Doe"
  },
  "shift": {
    "id": 501,
    "shift_name": "Morning Shift - Security"
  },
  "checkin_time": "2025-11-15T08:05:00Z",
  "checkout_time": "2025-11-15T16:10:00Z",
  "status": "completed",
  "hours_worked": {
    "total_hours": 8.08,
    "regular_hours": 8.0,
    "overtime_hours": 0.08,
    "break_hours": 0.0
  },
  "time_status": {
    "checked_out_on_time": false,
    "checked_out_late": true,
    "minutes_late": 10,
    "overtime_eligible": true
  },
  "gps_validation": {
    "validated": true,
    "distance_from_site_meters": 9.2,
    "within_geofence": true,
    "spoofing_detected": false
  },
  "face_validation": {
    "validated": true,
    "confidence_score": 0.87,
    "liveness_check_passed": true,
    "spoofing_detected": false
  },
  "pay_calculation": {
    "regular_pay": 80.00,
    "overtime_pay": 1.20,
    "total_pay": 81.20,
    "currency": "SGD"
  },
  "version": 2,
  "updated_at": "2025-11-15T16:10:00Z",
  "correlation_id": "req-checkout-xyz789"
}
```

---

### 3. Get My Shifts

**Endpoint:** `GET /api/v2/attendance/my-shifts/`

**Django Implementation:**
- **Viewset:** `apps/attendance/api/viewsets.py:ShiftViewSet.my_shifts()`
- **Serializer:** `apps/client_onboarding/serializers.py:ShiftSerializer`
- **Permissions:** `IsAuthenticated`

**Purpose:** Get current user's upcoming and active shifts

**Query Parameters:**
- `start_date`: Filter shifts starting after date (ISO 8601)
- `end_date`: Filter shifts ending before date
- `status`: Filter by status: `upcoming,active,completed,cancelled`
- `site_id`: Filter by site

**Request:**
```
GET /api/v2/attendance/my-shifts/?start_date=2025-11-15T00:00:00Z&end_date=2025-11-30T23:59:59Z&status=upcoming,active
```

**Response (200 OK):**
```json
{
  "count": 15,
  "results": [
    {
      "id": 501,
      "shift_name": "Morning Shift - Security",
      "shift_type": "security_guard",
      "scheduled_start": "2025-11-15T08:00:00Z",
      "scheduled_end": "2025-11-15T16:00:00Z",
      "duration_hours": 8.0,
      "status": "active",
      "site": {
        "id": 789,
        "site_name": "Downtown Office",
        "address": "123 Main St, Singapore",
        "latitude": 1.290270,
        "longitude": 103.851959
      },
      "post": {
        "id": 201,
        "post_name": "Main Entrance",
        "post_type": "entry_point",
        "geofence_radius_meters": 50
      },
      "assigned_by": {
        "id": 999,
        "name": "Operations Manager"
      },
      "attendance_status": {
        "checked_in": true,
        "checkin_time": "2025-11-15T08:05:00Z",
        "on_time": true
      },
      "grace_period_minutes": 15,
      "allow_early_checkin_minutes": 30,
      "requires_gps": true,
      "requires_face_photo": true,
      "created_at": "2025-11-10T10:00:00Z"
    },
    {
      "id": 502,
      "shift_name": "Evening Shift - Security",
      "shift_type": "security_guard",
      "scheduled_start": "2025-11-16T16:00:00Z",
      "scheduled_end": "2025-11-17T00:00:00Z",
      "duration_hours": 8.0,
      "status": "upcoming",
      "site": {
        "id": 789,
        "site_name": "Downtown Office",
        "address": "123 Main St, Singapore",
        "latitude": 1.290270,
        "longitude": 103.851959
      },
      "post": {
        "id": 202,
        "post_name": "Parking Garage",
        "post_type": "patrol",
        "geofence_radius_meters": 100
      },
      "attendance_status": {
        "checked_in": false,
        "checkin_time": null,
        "on_time": null
      },
      "grace_period_minutes": 15,
      "created_at": "2025-11-10T10:05:00Z"
    }
  ]
}
```

---

### 4. Get Attendance Records

**Endpoint:** `GET /api/v2/attendance/records/`

**Django Implementation:**
- **Viewset:** `apps/attendance/api/viewsets.py:AttendanceViewSet.list()`
- **Serializer:** `apps/attendance/serializers.py:AttendanceListSerializer`
- **Permissions:** `IsAuthenticated`

**Purpose:** Get paginated attendance history for current user

**Query Parameters:**
- `page`: Page number
- `page_size`: Items per page (max 100)
- `start_date`: Filter records after date
- `end_date`: Filter records before date
- `status`: Filter by status: `checked_in,completed,cancelled`
- `site_id`: Filter by site
- `ordering`: Sort field: `-checkin_time,hours_worked`

**Response (200 OK):**
```json
{
  "count": 150,
  "next": "https://api.example.com/api/v2/attendance/records/?page=2",
  "previous": null,
  "results": [
    {
      "id": 7001,
      "attendance_number": "ATT-2025-11-7001",
      "shift": {
        "id": 501,
        "shift_name": "Morning Shift - Security",
        "site_name": "Downtown Office"
      },
      "checkin_time": "2025-11-15T08:05:00Z",
      "checkout_time": "2025-11-15T16:10:00Z",
      "status": "completed",
      "hours_worked": 8.08,
      "overtime_hours": 0.08,
      "time_status": {
        "on_time_checkin": true,
        "late_checkout": true,
        "minutes_late_checkout": 10
      },
      "pay": {
        "regular_pay": 80.00,
        "overtime_pay": 1.20,
        "total_pay": 81.20,
        "currency": "SGD"
      },
      "created_at": "2025-11-15T08:05:00Z"
    }
  ]
}
```

---

## Shift Management

### 5. Get Shift Details

**Endpoint:** `GET /api/v2/attendance/shifts/{id}/`

**Purpose:** Get complete shift information including assignments and requirements

**Response (200 OK):**
```json
{
  "id": 501,
  "shift_name": "Morning Shift - Security",
  "shift_type": "security_guard",
  "scheduled_start": "2025-11-15T08:00:00Z",
  "scheduled_end": "2025-11-15T16:00:00Z",
  "duration_hours": 8.0,
  "status": "active",
  "site": {
    "id": 789,
    "site_name": "Downtown Office",
    "address": "123 Main St, Singapore",
    "latitude": 1.290270,
    "longitude": 103.851959,
    "geofence_radius_meters": 100
  },
  "post": {
    "id": 201,
    "post_name": "Main Entrance",
    "post_type": "entry_point",
    "description": "Security guard stationed at main entrance",
    "required_capabilities": ["security_license", "first_aid"],
    "equipment_required": ["radio", "flashlight", "access_card"]
  },
  "requirements": {
    "gps_required": true,
    "face_photo_required": true,
    "minimum_checkin_photos": 1,
    "patrol_required": false,
    "patrol_interval_minutes": null
  },
  "assigned_workers": [
    {
      "id": 123,
      "name": "John Doe",
      "assignment_status": "confirmed",
      "attendance_status": "checked_in",
      "checkin_time": "2025-11-15T08:05:00Z"
    }
  ],
  "capacity": {
    "required_workers": 1,
    "assigned_workers": 1,
    "is_fully_staffed": true
  },
  "pay_rates": {
    "hourly_rate": 10.00,
    "overtime_multiplier": 1.5,
    "weekend_multiplier": 2.0,
    "holiday_multiplier": 3.0,
    "currency": "SGD"
  },
  "created_at": "2025-11-10T10:00:00Z",
  "created_by": {
    "id": 999,
    "name": "Operations Manager"
  }
}
```

---

## Geofencing & GPS

### 6. Validate Geofence

**Endpoint:** `POST /api/v2/attendance/geofence/validate/`

**Django Implementation:**
- **Service:** `apps/attendance/services/geospatial_service.py:GeospatialService.validate_geofence()`
- **Permissions:** `IsAuthenticated`

**Purpose:** Pre-validate GPS location before check-in (reduce check-in failures)

**Request:**
```json
{
  "site_id": 789,
  "latitude": 1.290270,
  "longitude": 103.851959,
  "accuracy_meters": 12.5
}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "within_geofence": true,
  "distance_from_site_meters": 8.5,
  "accuracy_meters": 12.5,
  "site": {
    "id": 789,
    "site_name": "Downtown Office",
    "geofence_radius_meters": 100,
    "center_latitude": 1.290270,
    "center_longitude": 103.851959
  },
  "can_checkin": true,
  "warnings": [],
  "correlation_id": "req-geofence-123"
}
```

**Response (200 OK) - Outside geofence:**
```json
{
  "valid": false,
  "within_geofence": false,
  "distance_from_site_meters": 152.3,
  "accuracy_meters": 12.5,
  "site": {
    "id": 789,
    "site_name": "Downtown Office",
    "geofence_radius_meters": 100
  },
  "can_checkin": false,
  "warnings": [
    {
      "code": "OUTSIDE_GEOFENCE",
      "message": "You are 52 meters outside the allowed check-in area",
      "severity": "error"
    }
  ],
  "correlation_id": "req-geofence-123"
}
```

---

### 7. Get Nearby Sites

**Endpoint:** `GET /api/v2/attendance/sites/nearby/`

**Purpose:** Find sites near current GPS location (for flexible check-in)

**Query Parameters:**
- `latitude`: Current latitude
- `longitude`: Current longitude
- `radius_meters`: Search radius (default: 500, max: 5000)

**Request:**
```
GET /api/v2/attendance/sites/nearby/?latitude=1.290270&longitude=103.851959&radius_meters=1000
```

**Response (200 OK):**
```json
{
  "current_location": {
    "latitude": 1.290270,
    "longitude": 103.851959
  },
  "search_radius_meters": 1000,
  "sites_found": 3,
  "sites": [
    {
      "id": 789,
      "site_name": "Downtown Office",
      "address": "123 Main St, Singapore",
      "distance_meters": 8.5,
      "latitude": 1.290270,
      "longitude": 103.851959,
      "has_active_shift": true,
      "geofence_radius_meters": 100,
      "can_checkin": true
    },
    {
      "id": 790,
      "site_name": "North Campus",
      "address": "456 North Rd, Singapore",
      "distance_meters": 452.3,
      "latitude": 1.295000,
      "longitude": 103.855000,
      "has_active_shift": false,
      "geofence_radius_meters": 150,
      "can_checkin": false
    },
    {
      "id": 791,
      "site_name": "Warehouse B",
      "address": "789 Industrial Ave, Singapore",
      "distance_meters": 892.1,
      "latitude": 1.298000,
      "longitude": 103.860000,
      "has_active_shift": true,
      "geofence_radius_meters": 200,
      "can_checkin": true
    }
  ],
  "correlation_id": "req-nearby-456"
}
```

---

## Fraud Detection

### 8. Get Fraud Alerts

**Endpoint:** `GET /api/v2/attendance/fraud/alerts/`

**Purpose:** Get fraud detection alerts for current user (for review/explanation)

**Response (200 OK):**
```json
{
  "alerts": [
    {
      "id": 8001,
      "alert_type": "gps_spoofing",
      "severity": "high",
      "detected_at": "2025-11-15T08:05:00Z",
      "attendance_id": 7001,
      "details": {
        "spoofing_indicators": [
          "location_jump_impossible_speed",
          "mock_location_provider_detected"
        ],
        "confidence": 0.94,
        "previous_location_timestamp": "2025-11-15T07:50:00Z",
        "distance_meters": 8542,
        "time_elapsed_seconds": 900,
        "required_speed_kmh": 34.2
      },
      "status": "under_review",
      "reviewed_by": null,
      "resolution": null,
      "notes": "Automated detection - pending manual review"
    },
    {
      "id": 8002,
      "alert_type": "photo_quality_low",
      "severity": "medium",
      "detected_at": "2025-11-14T08:02:00Z",
      "attendance_id": 7000,
      "details": {
        "quality_score": 0.65,
        "threshold": 0.75,
        "issues": ["poor_lighting", "face_partially_obscured"]
      },
      "status": "resolved",
      "reviewed_by": {
        "id": 999,
        "name": "Supervisor"
      },
      "resolution": "approved_manual_verification",
      "notes": "Reviewed CCTV footage, identity confirmed"
    }
  ]
}
```

---

## Travel Expenses

### 9. Create Conveyance Record

**Endpoint:** `POST /api/v2/attendance/conveyance/`

**Purpose:** Record travel for reimbursement

**Request:**
```json
{
  "attendance_id": 7001,
  "travel_date": "2025-11-15",
  "from_location": {
    "address": "Home",
    "latitude": 1.280000,
    "longitude": 103.840000
  },
  "to_location": {
    "address": "Downtown Office",
    "latitude": 1.290270,
    "longitude": 103.851959
  },
  "transport_mode": "public_transport",
  "distance_km": 12.5,
  "amount": 5.50,
  "currency": "SGD",
  "receipt_photo": "data:image/jpeg;base64,/9j/4AAQ...",
  "notes": "Bus + MRT to site"
}
```

**Response (201 Created):**
```json
{
  "id": 3001,
  "attendance_id": 7001,
  "travel_date": "2025-11-15",
  "from_location": {
    "address": "Home",
    "latitude": 1.280000,
    "longitude": 103.840000
  },
  "to_location": {
    "address": "Downtown Office",
    "latitude": 1.290270,
    "longitude": 103.851959
  },
  "transport_mode": "public_transport",
  "distance_km": 12.5,
  "amount": 5.50,
  "currency": "SGD",
  "status": "pending_approval",
  "receipt_photo_url": "https://storage/receipts/3001.jpg",
  "created_at": "2025-11-15T16:15:00Z",
  "correlation_id": "req-conveyance-789"
}
```

---

## Complete Workflows

### Workflow 1: Daily Attendance (Happy Path)

```
1. Morning - Get My Shifts
   GET /api/v2/attendance/my-shifts/?start_date=2025-11-15T00:00:00Z&end_date=2025-11-15T23:59:59Z
   → Find shift ID 501, site location, geofence

2. Pre-validate GPS (before showing check-in button)
   POST /api/v2/attendance/geofence/validate/
   → Check if within geofence
   → Show "Ready to Check In" if valid

3. Check In
   POST /api/v2/attendance/checkin/
   → GPS + face photo + device info
   → Status: checked_in
   → Store attendance ID 7001

4. End of Shift - Check Out
   POST /api/v2/attendance/checkout/
   → GPS + face photo
   → Hours calculated: 8.08 hours
   → Overtime: 0.08 hours
   → Pay calculated: SGD 81.20

5. (Optional) Add Travel Expense
   POST /api/v2/attendance/conveyance/
   → Receipt photo + distance
   → Pending approval
```

### Workflow 2: Offline Check-In

```
1. User has no network at check-in time
   → Store in local pending queue:
   {
     "temp_id": "temp-att-{uuid}",
     "mobile_id": "device-android-abc123",
     "shift_id": 501,
     "checkin_time": "2025-11-15T08:05:00Z",
     "gps_location": {...},
     "face_photo": {...},
     "sync_status": "pending"
   }

2. Show in UI as "Pending Sync"
   → Local SQLite stores record
   → UI shows clock as started

3. When network returns (WebSocket reconnects)
   → Send SyncDataMessage with pending check-in
   → Server validates and creates record
   → Server returns real ID: 7001
   → Mobile updates: temp-att-{uuid} → 7001

4. Handle conflicts
   → If server says "already checked in at 08:00"
   → Show conflict resolution UI
   → User chooses: keep server (08:00) or local (08:05)
```

### Workflow 3: GPS Spoofing Detected

```
1. User attempts check-in with spoofed GPS
   POST /api/v2/attendance/checkin/
   → Server detects:
     - Impossible speed (8.5 km in 15 minutes)
     - Mock location provider
     - GPS accuracy too perfect (0.1 meters)

2. Server Response: 400 Bad Request
   {
     "error_code": "FRAUD_DETECTED",
     "fraud_type": "gps_spoofing",
     ...
   }

3. Mobile App Behavior:
   → Show error: "Location verification failed"
   → Log fraud attempt locally (for audit)
   → Prompt user to disable mock locations
   → Do NOT retry automatically (fraud attempts logged)

4. Alert created for supervisor review
   → Supervisor reviews CCTV, GPS path, device info
   → Can manually approve or reject
```

---

## Error Scenarios

### Common Errors

**No Active Shift:**
```json
{
  "error_code": "NO_ACTIVE_SHIFT",
  "message": "You do not have a shift scheduled for this time"
}
```

**Already Checked In:**
```json
{
  "error_code": "ALREADY_CHECKED_IN",
  "message": "You are already checked in",
  "existing_checkin": {
    "id": 7000,
    "checkin_time": "2025-11-15T08:00:00Z"
  }
}
```

**GPS Outside Geofence:**
```json
{
  "error_code": "GPS_VALIDATION_FAILED",
  "distance_from_site_meters": 152.3,
  "max_allowed_meters": 100
}
```

**Face Verification Failed:**
```json
{
  "error_code": "FACE_VERIFICATION_FAILED",
  "confidence_score": 0.62,
  "threshold": 0.85,
  "reason": "confidence_below_threshold"
}
```

**Fraud Detected:**
```json
{
  "error_code": "FRAUD_DETECTED",
  "fraud_type": "gps_spoofing",
  "action_required": "manual_review_required"
}
```

---

## Data Models

### Attendance Entry (Kotlin)

```kotlin
data class AttendanceEntry(
    val id: Long,
    val attendanceNumber: String,
    val user: User,
    val shift: Shift,
    val checkinTime: Instant,
    val checkoutTime: Instant?,
    val status: AttendanceStatus,
    val gpsValidation: GpsValidation,
    val faceValidation: FaceValidation,
    val hoursWorked: Double?,
    val overtimeHours: Double?,
    val timeStatus: TimeStatus,
    val pay: PayCalculation?,
    val fraudAlerts: List<FraudAlert>,
    val version: Int,
    val createdAt: Instant,
    val updatedAt: Instant
)

enum class AttendanceStatus {
    CHECKED_IN,
    COMPLETED,
    CANCELLED
}

data class GpsValidation(
    val validated: Boolean,
    val distanceFromSiteMeters: Double,
    val accuracyMeters: Double,
    val withinGeofence: Boolean,
    val spoofingDetected: Boolean,
    val confidenceScore: Double
)

data class FaceValidation(
    val validated: Boolean,
    val confidenceScore: Double,
    val livenessCheckPassed: Boolean,
    val spoofingDetected: Boolean,
    val referencePhotoAgeDays: Int
)

data class TimeStatus(
    val isOnTime: Boolean,
    val isLate: Boolean,
    val minutesLate: Int
)

data class PayCalculation(
    val regularPay: Double,
    val overtimePay: Double,
    val totalPay: Double,
    val currency: String
)
```

---

## Offline Support

### Pending Operations Queue

**Check-in offline:**
1. Store in local Room database with temp ID
2. Mark `sync_status = "pending"`
3. Display in UI as "Pending Sync"
4. When online, send via WebSocket
5. Update temp ID → real ID when sync completes

**Version conflict:**
- Server has attendance 7001 v3
- Mobile has v2 with local edits
- Server sends conflict response
- Mobile shows diff UI, user resolves

---

## Security Notes

### GPS Privacy
- GPS data requires user consent
- Consent recorded with timestamp
- GPS deleted after 90 days (GDPR)
- User can revoke consent (disables GPS features)

### Face Photo Privacy
- Photos encrypted at rest (AES-256)
- Photos deleted after 90 days
- User can request deletion (GDPR right to erasure)
- PII redaction in logs

### Multi-Tenant Isolation
- All requests auto-filtered by `client_id`
- Attempting cross-tenant access returns 403
- Client ID sent in every request header: `X-Client-ID: 42`

---

## Testing Checklist

- [ ] Check-in with valid GPS + face photo
- [ ] Check-in outside geofence (should fail)
- [ ] Check-in with poor photo (should fail)
- [ ] Check-in without active shift (should fail)
- [ ] Check-in when already checked in (should fail)
- [ ] Check-out with time calculation
- [ ] Offline check-in → sync when online
- [ ] GPS spoofing detection
- [ ] Face spoofing detection
- [ ] Version conflict handling
- [ ] Get shifts for date range
- [ ] Geofence pre-validation
- [ ] Nearby sites search
- [ ] Travel expense creation

---

**Document Version:** 1.0.0
**Last Updated:** November 7, 2025
**Next Review:** December 7, 2025
