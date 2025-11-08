# Intelliwiz Mobile App - Product Requirements Document (PRD)

> **Product:** Intelliwiz Mobile (Kotlin/Android)
> **Version:** 2.0.0
> **Last Updated:** November 7, 2025
> **Target Release:** Q2 2026

---

## 📋 Executive Summary

**Intelliwiz Mobile** is an offline-first Android application for field workers in facility management, security guarding, and asset maintenance. Built on a Django REST API backend with real-time WebSocket sync, the app enables workers to manage jobs, track attendance, report issues, and access wellness resources - **even without network connectivity**.

### Key Statistics

- **Backend:** Django 5.2.1 + PostgreSQL 14.2 + PostGIS
- **Frontend:** Kotlin 1.9+ + Jetpack Compose + Room SQLite
- **Architecture:** Clean Architecture with 3 layers (Presentation, Domain, Data)
- **Offline-First:** 100% of features work offline, sync when connected
- **Type-Safe:** OpenAPI-generated DTOs, compile-time validation
- **Domains:** 5 (Operations, Attendance, People, Helpdesk, Wellness)
- **Endpoints:** 60+ REST APIs, 1 WebSocket for real-time sync
- **Target Users:** 5,000+ field workers across 200+ sites

---

## 📋 Table of Contents

- [Product Vision](#product-vision)
- [User Personas](#user-personas)
- [System Architecture](#system-architecture)
- [Core Features](#core-features)
- [Technical Requirements](#technical-requirements)
- [Data Integration](#data-integration)
- [Security & Privacy](#security--privacy)
- [Performance Requirements](#performance-requirements)
- [Success Metrics](#success-metrics)
- [Implementation Timeline](#implementation-timeline)

---

## Product Vision

### Problem Statement

Field workers in facility management face critical challenges:

1. **Unreliable Connectivity:** Sites have poor/no network (basements, remote locations)
2. **Complex Workflows:** Jobs require GPS verification, photo documentation, multi-step approvals
3. **Real-Time Coordination:** Supervisors need live visibility into worker status
4. **Data Integrity:** Offline edits create conflicts when syncing
5. **Compliance:** GPS tracking, facial recognition, audit trails required by contracts

### Solution

**An offline-first mobile app** that mirrors backend capabilities locally:

- **Work Offline:** Create jobs, check in/out, answer questions - no network needed
- **Auto-Sync:** Seamless synchronization when network returns
- **Smart Conflicts:** Detect and resolve data conflicts gracefully
- **Real-Time Updates:** WebSocket pushes urgent updates (escalations, reassignments)
- **Secure by Design:** JWT auth, certificate pinning, encrypted storage

---

## User Personas

### Persona 1: Security Guard (Primary)

**Name:** Raj, 32, Security Officer
**Daily Tasks:** Check-in at posts, patrol rounds, incident reporting
**Pain Points:**
- Basement parking has no signal
- Forgot to check out → manual correction needed
- Photo verification fails in low light

**Needs:**
- Reliable offline check-in/out
- GPS validation with clear error messages
- Quick incident reporting with photos
- Shift schedule visibility

**App Features:**
- Attendance (check-in/out with GPS + face)
- Shift calendar
- Incident tickets
- SOS button

---

### Persona 2: Maintenance Technician (Primary)

**Name:** Sarah, 28, HVAC Technician
**Daily Tasks:** Scheduled maintenance, emergency repairs, equipment inspections
**Pain Points:**
- PPM checklists are on paper
- Can't access job history in the field
- Approval delays for urgent repairs

**Needs:**
- Digital checklists with photo uploads
- Asset history (last maintenance date, issues)
- Offline job creation for emergencies
- Push notifications for urgent assignments

**App Features:**
- Operations (jobs, tasks, PPM)
- Asset QR code scanning
- Digital forms/questions
- Photo attachments

---

### Persona 3: Site Supervisor (Secondary)

**Name:** Michael, 42, Operations Supervisor
**Daily Tasks:** Team oversight, job approvals, performance monitoring
**Pain Points:**
- Can't see real-time team status
- Approval workflows require desktop access
- No visibility into SLA breaches

**Needs:**
- Team dashboard (who's on-shift, who's late)
- Mobile approvals
- SLA countdown alerts
- Performance metrics

**App Features:**
- Team view
- Approval workflows
- Analytics dashboards
- Alert notifications

---

## System Architecture

### Frontend-Backend Relationship

```
┌─────────────────────────────────────────────┐
│         Kotlin/Android Mobile App           │
│  ┌────────────┬──────────┬────────────────┐ │
│  │Presentation│  Domain  │  Data Layer    │ │
│  │   (UI)     │(Business)│(Room + Retrofit)│ │
│  └────────────┴──────────┴────────────────┘ │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────┴──────────┐
         │                    │
    ┌────▼─────┐      ┌───────▼────────┐
    │  REST API│      │    WebSocket   │
    │/api/v2/* │      │   /ws/sync/    │
    └────┬─────┘      └───────┬────────┘
         │                    │
         └─────────┬──────────┘
                   │
    ┌──────────────▼──────────────────┐
    │    Django Backend (Source of    │
    │         Truth)                  │
    │  ┌─────────────────────────┐   │
    │  │  PostgreSQL Database    │   │
    │  │  (Normalized, ACID)     │   │
    │  └─────────────────────────┘   │
    └─────────────────────────────────┘
```

**Data Flow:**
1. **Read:** PostgreSQL → Django serializer → REST JSON → DTO → Kotlin entity → Room cache → UI
2. **Write:** UI → Entity → DTO → REST JSON → Django → PostgreSQL
3. **Offline Write:** UI → Entity → Room pending queue → WebSocket sync → PostgreSQL

---

### Two Databases Philosophy

| Database | Purpose | Characteristics | Owned By |
|----------|---------|-----------------|----------|
| **PostgreSQL** | Source of truth | Normalized, ACID, relational | Backend |
| **SQLite (Room)** | Local cache | Denormalized, client-optimized, fast reads | Mobile |

**Why Two Databases?**

**PostgreSQL (Backend):**
- Normalized to eliminate redundancy (People table ≠ PeopleProfile)
- Supports complex queries, joins, aggregations
- Multi-tenant with row-level security
- Handles concurrent writes from 1000+ users

**SQLite (Mobile):**
- Denormalized for offline performance (User combines People + Profile + Organizational)
- No network needed for reads
- Optimized for mobile constraints (storage, CPU)
- Handles single user's data only

**Example:**

**PostgreSQL (3 tables):**
```sql
SELECT p.username, pp.first_name, po.department
FROM peoples_people p
JOIN peoples_peopleprofile pp ON p.id = pp.user_id
JOIN peoples_peopleorganizational po ON p.id = po.user_id
WHERE p.id = 123;
```

**SQLite (1 table):**
```sql
SELECT username, first_name, department
FROM users
WHERE id = 123;
```

**Trade-off:** SQLite uses more storage (denormalized data), but reads are 10x faster and work offline.

---

## Core Features

### Feature 1: Operations Management

**User Stories:**
- As a technician, I want to view my assigned jobs so I can plan my day
- As a worker, I want to create emergency jobs offline so I can respond immediately
- As a supervisor, I want to approve completed jobs so work can be invoiced

**API Endpoints:** 8+ (see API_CONTRACT_OPERATIONS.md)

**Key Screens:**
- Job list (with filters: my jobs, today, urgent)
- Job details (assets, questions, attachments, map)
- Create/edit job
- Job approval (supervisor)

**Offline Support:**
- Create jobs → pending queue
- Update jobs → optimistic UI update
- Answer questions → store locally
- Upload photos → compress and queue
- Sync all when connected

---

### Feature 2: Attendance & Time Tracking

**User Stories:**
- As a guard, I want to check in with GPS + photo so my hours are tracked
- As a worker, I want to view my shifts so I know where to go
- As a supervisor, I want to see who's late so I can adjust staffing

**API Endpoints:** 9+ (see API_CONTRACT_ATTENDANCE.md)

**Key Screens:**
- Check-in/out (with camera + GPS)
- Shift calendar (upcoming shifts)
- Attendance history (timesheet)
- Travel expenses

**Offline Support:**
- Check-in/out stored locally with GPS + photo
- Sync when connected
- Handle "already checked in" conflicts

---

### Feature 3: People & Directory

**User Stories:**
- As a user, I want to view my profile so I can verify my information
- As a technician, I want to search colleagues so I can find experts
- As a supervisor, I want to see my team so I can assign work

**API Endpoints:** 10+ (see API_CONTRACT_PEOPLE.md)

**Key Screens:**
- My profile (view/edit)
- User directory (search, filter)
- Team view (for supervisors)
- Organizational chart

**Offline Support:**
- Cache frequently viewed profiles
- Search works on cached data
- Profile updates queued for sync

---

### Feature 4: Helpdesk & Support

**User Stories:**
- As a worker, I want to report issues so I can get help
- As a user, I want to track my tickets so I know resolution status
- As a support agent, I want to respond on mobile so I can help remotely

**API Endpoints:** 9+ (see API_CONTRACT_HELPDESK.md)

**Key Screens:**
- Create ticket (with photos)
- My tickets (filter by status)
- Ticket conversation (messages + attachments)
- SLA countdown

**Offline Support:**
- Create tickets offline
- Queue messages/attachments
- Sync when connected
- Real-time updates via WebSocket

---

### Feature 5: Wellness & Mental Health

**User Stories:**
- As a worker, I want to track my mood so I can monitor wellbeing
- As a user, I want wellness tips so I can manage stress
- As a manager, I want aggregated wellness trends so I can support my team

**API Endpoints:** 16 (see API_CONTRACT_WELLNESS.md)

**Key Screens:**
- Daily journal entry (mood, stress, sleep)
- Wellness content library (articles, videos)
- Analytics (mood trends, patterns)
- Privacy settings

**Offline Support:**
- Journal entries stored locally
- Sync when connected
- Content cached for offline reading

---

## Technical Requirements

### Minimum Requirements

- **Android OS:** 8.0 (API 26) or higher
- **Storage:** 500 MB free space (for offline cache)
- **RAM:** 2 GB minimum
- **Camera:** Required (for facial recognition, photo attachments)
- **GPS:** Required (for attendance GPS validation)
- **Network:** WiFi or Mobile data (intermittent connectivity supported)

### Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Language** | Kotlin | 1.9+ | Type safety, null safety, coroutines |
| **UI Framework** | Jetpack Compose | Latest | Declarative UI, modern design |
| **Dependency Injection** | Hilt | 2.48+ | Testable architecture |
| **Local Database** | Room | 2.6+ | SQLite with type-safe DAO |
| **Networking** | Retrofit + OkHttp | 2.9+ / 4.12+ | REST API client |
| **Serialization** | kotlinx.serialization | 1.6+ | Type-safe JSON |
| **WebSocket** | OkHttp WebSocket | 4.12+ | Real-time sync |
| **Image Loading** | Coil | 2.5+ | Efficient image loading |
| **Background Tasks** | WorkManager | 2.9+ | Reliable background sync |
| **Auth** | JWT + KeyStore | - | Secure token storage |
| **Date/Time** | kotlinx-datetime | 0.5+ | ISO 8601 support |
| **Permissions** | Accompanist Permissions | 0.33+ | Runtime permissions |

---

## Data Integration

### REST API Integration

**Base URL:** `https://api.intelliwiz.com/api/v2/`

**Authentication:**
```
Authorization: Bearer {access_token}
X-Client-ID: {tenant_id}
```

**Rate Limiting:**
- 600 requests per hour per user
- Retry-After header sent if exceeded
- Mobile should implement exponential backoff

**Pagination:**
- Page-based for browsing (jobs list, tickets list)
- Cursor-based for sync (get updates after timestamp)

**Error Handling:**
- 20+ error codes with specific handling
- Field-level validation errors
- Correlation IDs for debugging

**See:** [API_CONTRACT_FOUNDATION.md](API_CONTRACT_FOUNDATION.md)

---

### WebSocket Real-Time Sync

**URL:** `wss://api.intelliwiz.com/ws/sync/`

**Purpose:**
- Bidirectional sync (client ↔ server)
- Real-time updates (job reassignments, urgent tickets)
- Conflict resolution (optimistic locking)
- Heartbeat (connection health)

**Message Types:**
- CONNECTION_ACCEPTED, SYNC_START, SYNC_DATA, SYNC_ACK
- CONFLICT_DETECTED, CONFLICT_RESOLUTION, CONFLICT_RESOLVED
- HEARTBEAT, HEARTBEAT_ACK
- REALTIME_UPDATE, ERROR

**See:** [WEBSOCKET_MESSAGE_SCHEMA.md](WEBSOCKET_MESSAGE_SCHEMA.md)

---

### OpenAPI Schema Generation

**Workflow:**
1. Backend team updates Django models/serializers
2. CI/CD generates OpenAPI schema (`openapi.yaml`)
3. Schema published to S3/GitHub Pages
4. Mobile team downloads schema
5. Gradle plugin generates 120+ Kotlin DTOs
6. Type-safe API client ready for use

**Benefits:**
- Zero manual DTO writing
- Compile-time errors if API changes
- Always in sync with backend

**See:** [API_SCHEMA_GENERATION_GUIDE.md](API_SCHEMA_GENERATION_GUIDE.md)

---

## Security & Privacy

### Authentication & Authorization

**JWT Token Flow:**
```
1. Login: POST /api/v2/auth/login/
   → Response: {access_token, refresh_token, expires_in, client_id}

2. Store tokens in KeyStore (encrypted)
   → access_token: 15 min lifetime
   → refresh_token: 7 days lifetime

3. Attach to every request:
   Authorization: Bearer {access_token}

4. Token refresh (automatic):
   → When expires_in < 5 minutes
   → POST /api/v2/auth/refresh/
   → Get new access_token
   → Retry original request

5. Logout:
   → POST /api/v2/auth/logout/
   → Clear KeyStore, delete cached data
```

---

### Data Privacy (GDPR Compliant)

**PII Categories:**

| Data Type | Storage | Retention | Encryption |
|-----------|---------|-----------|------------|
| GPS coordinates | SQLite + server | 90 days | AES-256 |
| Face photos | Server only | 90 days | AES-256 |
| Phone, address | SQLite + server | Until deleted | AES-256 |
| Attendance records | SQLite + server | 7 years (payroll) | AES-256 |
| Journal entries | SQLite + server | User-controlled | AES-256 |

**User Rights:**
- Right to access (export data)
- Right to deletion (GDPR erasure)
- Right to revoke consent (disable GPS/facial recognition)

---

### Security Requirements (OWASP Mobile Top 10 2024)

1. **M1: Improper Credential Usage**
   - Store JWT in KeyStore (not SharedPreferences)
   - Clear tokens on logout
   - Auto-refresh before expiry

2. **M2: Inadequate Supply Chain Security**
   - Pin SSL certificates
   - Verify app signatures
   - Use ProGuard for code obfuscation

3. **M3: Insecure Authentication/Authorization**
   - JWT with 15-min expiry
   - Biometric auth (fingerprint/face) for app unlock
   - Session timeout after 30 min inactivity

4. **M4: Insufficient Input/Output Validation**
   - Validate all user inputs client-side
   - Sanitize data before display
   - Use type-safe DTOs (OpenAPI generated)

5. **M5: Insecure Communication**
   - HTTPS/WSS only (no HTTP/WS)
   - Certificate pinning
   - Validate SSL certificates

6. **M6: Inadequate Privacy Controls**
   - User consent for GPS/facial recognition
   - Encrypted local storage
   - Clear privacy policy

7. **M7: Insufficient Binary Protections**
   - ProGuard enabled for release builds
   - Root detection
   - Anti-tampering checks

8. **M8: Security Misconfiguration**
   - No debug logs in production
   - Disable developer options
   - Validate build configs

9. **M9: Insecure Data Storage**
   - Encrypt SQLite database
   - No sensitive data in logs
   - Clear cache on logout

10. **M10: Insufficient Cryptography**
    - Use Android Keystore for key management
    - AES-256 for data encryption
    - TLS 1.2+ for transport

**See:** [skills/android-security-checklist/ANDROID_SECURITY_GUIDE.md](skills/android-security-checklist/ANDROID_SECURITY_GUIDE.md)

---

## Performance Requirements

### Response Time Targets

| Action | Target | Measured At |
|--------|--------|-------------|
| App launch (cold start) | <2 seconds | onCreate → UI visible |
| App launch (warm start) | <500ms | Background → foreground |
| List screen load | <300ms | Navigation → data visible |
| Detail screen load | <500ms | Tap → full data rendered |
| Check-in submit | <1 second | Button tap → confirmation |
| Offline operation | <100ms | Instant UI feedback |
| Sync 100 updates | <5 seconds | WebSocket batch sync |
| Photo upload | <3 seconds | Compress → upload → confirm |

---

### Network Efficiency

**Minimize Data Usage:**
- Compress photos before upload (JPEG quality 80%, max 1920px)
- Pagination (load 20 items, fetch more on scroll)
- Delta sync (only send changed fields)
- Cache responses (ETags, Last-Modified headers)

**Offline-First Benefits:**
- 90% of operations work offline (no API calls)
- Sync only deltas when online (not full dataset)
- Background sync via WorkManager (not blocking UI)

**Target:**
- Daily data usage: <50 MB (without photos)
- With photos: ~200 MB (10 photos × 20 MB)
- Initial app download: <30 MB APK

---

### Battery Efficiency

**Optimization Strategies:**
- GPS: Use Fused Location Provider (low-power mode)
- Sync: Batch operations, sync every 15 min (not real-time for non-urgent)
- WebSocket: Heartbeat every 30s (balance between battery and reliability)
- Background: Use WorkManager with constraints (WiFi + battery not low)

**Target:**
- Battery drain: <5% per hour (with active use)
- Background drain: <1% per hour (with periodic sync)

---

## Success Metrics

### User Engagement

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Daily Active Users (DAU)** | 80% of total users | Analytics |
| **Weekly Active Users (WAU)** | 95% of total users | Analytics |
| **Session duration** | 2-3 hours per shift | Analytics |
| **Feature adoption** | >60% use all 5 domains | Feature usage tracking |
| **Offline usage** | >40% of operations offline | Sync queue metrics |

### Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Crash-free rate** | >99.5% | Firebase Crashlytics |
| **API error rate** | <1% of requests | Backend metrics |
| **Sync success rate** | >99% of operations | Sync telemetry |
| **Photo upload success** | >95% | Upload completion |
| **GPS validation success** | >90% (weather dependent) | Validation metrics |

### Business Impact

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Time savings** | 20 min per worker per day | Time tracking comparison |
| **Paperwork reduction** | 100% digital checklists | Before/after comparison |
| **Approval speed** | <2 hours (from 24h) | Approval time tracking |
| **Incident response** | <15 min (from 1h) | Ticket creation to assignment |

---

## Implementation Timeline

### Phase 0: Foundation (Week 1-2)

- [x] Android Studio setup (Arctic Fox or later)
- [x] Project structure (multi-module: app, domain, data, network, database, common)
- [x] Gradle dependencies
- [x] CI/CD pipeline (GitHub Actions)
- [x] Design system (Compose theme, colors, typography)

### Phase 1: Authentication & Networking (Week 3-4)

- [ ] Login/logout screens
- [ ] JWT token management (KeyStore)
- [ ] Retrofit setup with interceptors
- [ ] OpenAPI schema download
- [ ] DTO generation (120+ classes)
- [ ] Error handling framework

### Phase 2: Offline-First Foundation (Week 5-6)

- [ ] Room database schema (15+ tables)
- [ ] Repository pattern (cache + remote)
- [ ] Pending operations queue
- [ ] WorkManager background sync
- [ ] Offline indicator UI

### Phase 3: Operations Domain (Week 7-9)

- [ ] Job list, details, create/edit screens
- [ ] Asset QR code scanning
- [ ] Questions/forms rendering
- [ ] Photo attachments
- [ ] Job approval workflow
- [ ] Offline job creation + sync

### Phase 4: Attendance Domain (Week 10-11)

- [ ] Check-in/out screens with camera
- [ ] GPS validation
- [ ] Facial recognition integration
- [ ] Shift calendar
- [ ] Attendance history
- [ ] Travel expense tracking

### Phase 5: People & Helpdesk (Week 12-13)

- [ ] Profile screen
- [ ] User directory + search
- [ ] Team view (supervisors)
- [ ] Create ticket screen
- [ ] Ticket list + details
- [ ] Ticket conversation (messages)

### Phase 6: Wellness Domain (Week 14)

- [ ] Journal entry screen
- [ ] Wellness content library
- [ ] Analytics/trends
- [ ] Privacy settings

### Phase 7: Real-Time Sync (Week 15-16)

- [ ] WebSocket client implementation
- [ ] Sync protocol (SYNC_START, SYNC_DATA, ACK)
- [ ] Conflict detection + resolution UI
- [ ] Heartbeat + reconnection
- [ ] Real-time update notifications

### Phase 8: Polish & Testing (Week 17-18)

- [ ] UI/UX polish (animations, transitions)
- [ ] Performance optimization (lazy loading, caching)
- [ ] Security audit (OWASP checklist)
- [ ] Integration testing (100+ test cases)
- [ ] Beta testing with 50 users

**Total Timeline:** 18 weeks (~4.5 months) with 2-3 developers

---

## Non-Functional Requirements

### Reliability

- **Offline capability:** 100% of write operations must work offline
- **Data integrity:** Zero data loss, even with crashes
- **Sync reliability:** 99%+ of offline operations sync successfully
- **Crash rate:** <0.5% (99.5% crash-free)

### Scalability

- **Users per tenant:** Support 5,000+ concurrent users
- **Offline cache:** Handle 10,000+ cached entities
- **Photo storage:** 500+ photos in local cache (auto-cleanup old photos)
- **Sync performance:** Sync 1,000 updates in <30 seconds

### Usability

- **Onboarding:** First-time user completes profile setup in <5 minutes
- **Task completion:** Check-in takes <30 seconds
- **Learning curve:** User completes first job within 15 minutes (no training)
- **Accessibility:** Support TalkBack, large text, high contrast

---

## API Contract Summary

### All Domain Contracts

| Domain | Endpoints | Doc | Status |
|--------|-----------|-----|--------|
| **Foundation** | Auth, pagination, errors, WebSocket protocol | [API_CONTRACT_FOUNDATION.md](API_CONTRACT_FOUNDATION.md) | ✅ Complete |
| **Operations** | Jobs, tours, tasks, PPM, questions | [API_CONTRACT_OPERATIONS.md](API_CONTRACT_OPERATIONS.md) | ✅ Complete |
| **Attendance** | Check-in/out, shifts, GPS, fraud detection | [API_CONTRACT_ATTENDANCE.md](API_CONTRACT_ATTENDANCE.md) | ✅ Complete |
| **People** | Profiles, directory, capabilities, auth | [API_CONTRACT_PEOPLE.md](API_CONTRACT_PEOPLE.md) | ✅ Complete |
| **Helpdesk** | Tickets, SLA, escalations, search | [API_CONTRACT_HELPDESK.md](API_CONTRACT_HELPDESK.md) | ✅ Complete |
| **Wellness** | Journal, content, analytics, privacy | [API_CONTRACT_WELLNESS.md](API_CONTRACT_WELLNESS.md) | ✅ Complete |

**Total Endpoints:** 60+ REST APIs fully documented

---

## Testing Strategy

### Test Pyramid

```
        ┌────────────┐
        │   E2E      │  10% (User flows)
        │  (5 tests) │
        └────────────┘
      ┌────────────────┐
      │  Integration   │  20% (API contracts)
      │  (20 tests)    │
      └────────────────┘
    ┌──────────────────────┐
    │    Unit Tests        │  70% (Business logic)
    │    (100+ tests)      │
    └──────────────────────┘
```

### Test Coverage Targets

- **Domain Layer:** 90%+ (business logic)
- **Data Layer:** 85%+ (repository, DAO, mappers)
- **Presentation Layer:** 60%+ (ViewModels)
- **Overall:** 80%+ code coverage

### Key Test Scenarios

**Unit Tests:**
- DTO serialization/deserialization
- Entity mapping (DTO ↔ Entity)
- Business logic (validation, calculations)
- Offline queue management

**Integration Tests:**
- API contract validation (match OpenAPI schema)
- WebSocket message handling
- Conflict resolution logic
- Database migrations

**E2E Tests:**
- Complete job workflow (create → execute → submit → approve)
- Attendance workflow (check-in → work → check-out)
- Offline sync workflow (work offline 24h → sync all)
- Conflict resolution (concurrent edits)

---

## Documentation Structure

```
docs/kotlin-frontend/
├── README.md (This serves as integration overview)
├── COMPREHENSIVE_PRD.md (This file - product vision)
├── INDEX.md (Navigation hub)
│
├── API Contracts (Complete backend integration specs):
│   ├── API_CONTRACT_FOUNDATION.md (Auth, pagination, errors)
│   ├── API_CONTRACT_OPERATIONS.md (Jobs, tours, tasks)
│   ├── API_CONTRACT_ATTENDANCE.md (Check-in/out, GPS)
│   ├── API_CONTRACT_PEOPLE.md (Users, profiles)
│   ├── API_CONTRACT_HELPDESK.md (Tickets, SLA)
│   └── API_CONTRACT_WELLNESS.md (Journal, content)
│
├── Implementation Guides:
│   ├── KOTLIN_PRD_SUMMARY.md (Architecture, tech stack)
│   ├── CODE_GENERATION_PLAN.md (OpenAPI → DTOs)
│   ├── MAPPING_GUIDE.md (Data transformations)
│   ├── IMPLEMENTATION_ROADMAP.md (18-week plan)
│   └── API_SCHEMA_GENERATION_GUIDE.md (Schema workflow)
│
├── Real-Time Sync:
│   └── WEBSOCKET_MESSAGE_SCHEMA.md (WebSocket protocol)
│
└── Error Prevention (Skills):
    ├── ROOM_IMPLEMENTATION_GUIDE.md (50+ DB errors prevented)
    ├── RETROFIT_ERROR_HANDLING_GUIDE.md (30+ network errors)
    ├── OFFLINE_FIRST_PATTERNS_GUIDE.md (40+ sync errors)
    ├── ANDROID_SECURITY_GUIDE.md (OWASP Mobile 2024)
    ├── KOTLIN_COROUTINES_GUIDE.md (20+ async errors)
    ├── COMPOSE_BEST_PRACTICES_GUIDE.md (15+ UI errors)
    └── ANDROID_PERMISSIONS_GUIDE.md (GPS, camera permissions)
```

---

## Integration Checklist

### Before Implementing Any Feature

- [ ] Read API_CONTRACT_FOUNDATION.md (cross-cutting patterns)
- [ ] Read domain-specific API contract (Operations, Attendance, etc.)
- [ ] Download latest OpenAPI schema
- [ ] Generate DTOs (`./gradlew :network:openApiGenerate`)
- [ ] Read relevant error prevention skill (Room, Retrofit, Offline-First)
- [ ] Review data mapping guide for entity transformations

### During Implementation

- [ ] Use generated DTOs (don't hand-write)
- [ ] Implement offline support (store in pending queue)
- [ ] Handle all error scenarios (20+ error codes)
- [ ] Add version field for optimistic locking
- [ ] Test conflict resolution
- [ ] Add correlation IDs to requests

### After Implementation

- [ ] Write unit tests (domain + data layers)
- [ ] Write integration tests (API contract validation)
- [ ] Test offline → sync workflow
- [ ] Security review (OWASP checklist)
- [ ] Performance profiling

---

## FAQ

**Q: Can mobile app work 100% offline?**
A: Yes for all write operations (create, update). Reads work offline if data previously cached. Initial app launch requires network to fetch user profile and capabilities.

**Q: What happens if user creates same job offline on 2 devices?**
A: Each device assigns unique `mobile_id`. Server creates 2 separate jobs. User can delete duplicate via UI.

**Q: How does multi-tenant isolation work?**
A: `client_id` sent in every request header. Backend auto-filters all queries. Attempting cross-tenant access returns 403.

**Q: Can user work for multiple tenants?**
A: Yes. Login to different tenant → different `client_id` → separate local database. App supports tenant switching.

**Q: What if OpenAPI schema changes?**
A: CI/CD detects breaking changes. If breaking: major version increment + mobile team notified. If compatible: regenerate DTOs, update mappers.

**Q: How do we handle Django's 3-model user structure?**
A: Backend joins models in serializer. Mobile receives denormalized JSON. Store in single `users` table in SQLite.

**Q: What if offline for 1 week?**
A: Pending queue stores unlimited operations. Sync may take longer (batched). No data loss.

**Q: How to test without backend?**
A: Mock Retrofit services using generated DTOs. Return predefined responses. WorkManager can be faked for testing sync.

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **API changes break app** | Medium | High | OpenAPI codegen + CI/CD breaking change detection |
| **Offline conflicts** | High | Medium | Conflict resolution UI + version tracking |
| **GPS spoofing** | Medium | High | Server-side fraud detection + multi-signal validation |
| **Face photo spoofing** | Low | High | Liveness detection + anti-spoofing algorithms |
| **Data loss during sync** | Low | Critical | Pending queue persisted in Room, retry on failure |
| **Performance on low-end devices** | Medium | Medium | Pagination, lazy loading, background processing |
| **Battery drain** | Medium | Medium | Optimize GPS/sync frequency, use WorkManager constraints |

---

## Appendix: Complete Feature Checklist

### Operations Domain
- [ ] Job list (with filters, search, sort)
- [ ] Job details (assets, questions, map, history)
- [ ] Create job (offline-capable)
- [ ] Edit job (with version conflict handling)
- [ ] Answer questions (all 8 question types)
- [ ] Upload attachments (photos, PDFs)
- [ ] Start job (GPS validation)
- [ ] Complete job (digital signature)
- [ ] Submit for approval
- [ ] Approve job (supervisor)
- [ ] Job history/audit trail
- [ ] Asset QR code scanning
- [ ] Tour management
- [ ] PPM scheduling

### Attendance Domain
- [ ] Check-in (GPS + facial recognition)
- [ ] Check-out (calculate hours)
- [ ] View my shifts (calendar)
- [ ] View attendance history
- [ ] Travel expense entry
- [ ] Geofence pre-validation
- [ ] Fraud alert notifications
- [ ] Shift swap requests
- [ ] Overtime tracking
- [ ] Late check-in warnings

### People Domain
- [ ] View my profile
- [ ] Edit profile
- [ ] Upload avatar
- [ ] Change password
- [ ] Search user directory
- [ ] View user details
- [ ] View organizational chart
- [ ] View team members (supervisor)
- [ ] Manage device registrations
- [ ] Update preferences

### Helpdesk Domain
- [ ] Create ticket (with photos)
- [ ] View my tickets
- [ ] View ticket details
- [ ] Add message to ticket
- [ ] Close ticket (with rating)
- [ ] Search similar tickets
- [ ] SLA countdown indicator
- [ ] Request escalation
- [ ] Real-time message notifications
- [ ] Attachment management

### Wellness Domain
- [ ] Daily journal entry (mood, stress, sleep)
- [ ] View wellness content
- [ ] Search content
- [ ] View analytics/trends
- [ ] Privacy settings
- [ ] Notification preferences

### Cross-Cutting Features
- [ ] Login/logout
- [ ] Token refresh (automatic)
- [ ] Offline mode indicator
- [ ] Sync progress indicator
- [ ] Conflict resolution UI
- [ ] Error handling (all 20+ codes)
- [ ] Push notifications
- [ ] Dark mode
- [ ] Multi-language (English, Mandarin)
- [ ] Accessibility (TalkBack support)

**Total Features:** 80+ screens/flows

---

## Conclusion

The Intelliwiz Mobile app is a **comprehensive offline-first solution** for field workers, built on a robust Django REST API backend with real-time WebSocket sync. Complete API contracts and OpenAPI schema generation ensure type-safe, maintainable development with zero ambiguity about backend integration.

**Key Success Factors:**
1. **Complete API documentation** (6 domain contracts + foundation)
2. **Offline-first architecture** (works without network)
3. **Type-safe development** (OpenAPI codegen prevents errors)
4. **Conflict resolution** (graceful handling of concurrent edits)
5. **Security by design** (OWASP Mobile 2024 compliant)
6. **Performance optimized** (battery, network, storage)

**Ready for Implementation:** All contracts defined, schema generation automated, implementation roadmap complete.

---

**Document Version:** 1.0.0
**Last Updated:** November 7, 2025
**Product Owner:** Development Team
**Next Review:** December 7, 2025
