# API Version Compatibility Matrix

## Overview
This document defines compatibility requirements between backend API versions and mobile SDK versions, ensuring graceful degradation and clear upgrade paths.

## Backend API Versions

### v1.0 (Current - Stable)
- **Released**: 2025-09-27
- **Status**: ✅ Fully Supported
- **Support Until**: 2026-12-31 (minimum)
- **Features**:
  - Complete REST API for mobile operations
  - GraphQL with JWT authentication
  - File upload (legacy base64 method)
  - Offline sync capabilities

### v1.5 (Planned - Q4 2025)
- **Release**: 2025-12-15 (planned)
- **Status**: 🔜 In Development
- **Features**:
  - Enhanced file upload security
  - Improved GraphQL dataloaders
  - Extended offline capabilities
  - Performance optimizations

### v2.0 (Planned - Q2 2026)
- **Release**: 2026-06-30 (planned)
- **Status**: 📋 Planned
- **Breaking Changes**:
  - Remove legacy `upload_attachment` mutation
  - Require secure file upload only
  - New authentication flow
  - Enhanced permission model

## Mobile SDK Compatibility

### Kotlin SDK (Android)

| SDK Version | Min API | Target API | Backend Version | Status |
|-------------|---------|------------|-----------------|---------|
| 1.0.0-alpha01 | 24 | 34 | v1.0 | ✅ Current |
| 1.1.0 (planned) | 24 | 34 | v1.0, v1.5 | 🔜 Planned |
| 2.0.0 (planned) | 26 | 35 | v1.5, v2.0 | 📋 Planned |

**Backward Compatibility**:
- Kotlin SDK 1.x guaranteed compatible with Backend v1.x
- Kotlin SDK 2.0 will support both v1.5 and v2.0 APIs during transition

### Swift SDK (iOS)

| SDK Version | Min iOS | Target iOS | Backend Version | Status |
|-------------|---------|------------|-----------------|---------|
| 1.0.0 | 14.0 | 17.0 | v1.0 | ✅ Current |
| 1.1.0 (planned) | 14.0 | 17.0 | v1.0, v1.5 | 🔜 Planned |
| 2.0.0 (planned) | 15.0 | 18.0 | v1.5, v2.0 | 📋 Planned |

**Backward Compatibility**:
- Swift SDK 1.x guaranteed compatible with Backend v1.x
- Swift SDK 2.0 will support both v1.5 and v2.0 APIs during transition

## Feature Compatibility Matrix

| Feature | v1.0 | v1.5 | v2.0 | Notes |
|---------|------|------|------|-------|
| JWT Authentication | ✅ | ✅ | ✅ | Same across all versions |
| Base64 File Upload | ✅ | ⚠️ Deprecated | ❌ Removed | Use multipart instead |
| Multipart File Upload | ✅ | ✅ | ✅ | Preferred method |
| GraphQL Mutations | ✅ | ✅ | ✅ | Some mutations deprecated |
| Offline Sync | ✅ | ✅ | ✅ | Enhanced in v1.5+ |
| Push Notifications | ✅ | ✅ | ✅ | Same across versions |
| Location Tracking | ✅ | ✅ | ✅ | Improved accuracy in v1.5+ |

## API Endpoint Evolution

### REST Endpoints

#### People Management
| Endpoint | v1.0 | v1.5 | v2.0 | Changes |
|----------|------|------|------|---------|
| `GET /api/v1/people/` | ✅ | ✅ | ➡️ `/api/v2/users/` | Renamed in v2.0 |
| `POST /api/v1/people/` | ✅ | ✅ | ➡️ `/api/v2/users/` | Enhanced validation in v2.0 |
| `GET /api/v1/people/{id}/` | ✅ | ✅ | ✅ | Compatible |

#### Job Management
| Endpoint | v1.0 | v1.5 | v2.0 | Changes |
|----------|------|------|------|---------|
| `GET /api/v1/job/` | ✅ | ✅ | ✅ | Compatible |
| `POST /api/v1/job/` | ✅ | ✅ | ✅ | Enhanced in v1.5 |

### GraphQL Mutations

| Mutation | v1.0 | v1.5 | v2.0 | Status |
|----------|------|------|------|--------|
| `upload_attachment` | ✅ | ⚠️ Deprecated | ❌ Removed | Use `secure_file_upload` |
| `secure_file_upload` | ✅ | ✅ | ✅ | Preferred method |
| `token_auth` | ✅ | ✅ | ✅ | Same across versions |

## Client SDK Feature Support

### Kotlin SDK Features

| Feature | SDK 1.0 | SDK 1.1 | SDK 2.0 |
|---------|---------|---------|---------|
| Offline-first architecture | ✅ | ✅ | ✅ |
| Background sync | ✅ | ✅ | ✅ |
| Secure file upload | ❌ | ✅ | ✅ |
| Advanced caching | ❌ | ✅ | ✅ |
| Coroutine lifecycle management | ❌ | ❌ | ✅ |

### Swift SDK Features

| Feature | SDK 1.0 | SDK 1.1 | SDK 2.0 |
|---------|---------|---------|---------|
| Offline-first architecture | ✅ | ✅ | ✅ |
| Background sync | ✅ | ✅ | ✅ |
| Secure file upload | ❌ | ✅ | ✅ |
| Combine integration | ❌ | ✅ | ✅ |
| SwiftUI-optimized | ❌ | ❌ | ✅ |

## Version Negotiation

### URL Path Versioning (Recommended)
```
GET /api/v1/people/
GET /api/v2/users/
```

### Header Versioning (Alternative)
```
GET /api/people/
Accept-Version: v1
```

### Auto-negotiation
If no version specified, defaults to latest stable (currently v1).

## Upgrade Paths

### From v1.0 to v1.5
- **Breaking Changes**: None
- **Action Required**: None (drop-in compatible)
- **Recommended**: Update SDKs to access new features

### From v1.0 to v2.0
- **Breaking Changes**: Yes (see Migration Guide)
- **Action Required**:
  1. Update SDK to 2.0 or compatible version
  2. Replace `upload_attachment` with `secure_file_upload`
  3. Update endpoint references (people → users)
  4. Test thoroughly in staging environment
- **Recommended**: Migrate during v1.5 period for smoother transition

### From v1.5 to v2.0
- **Breaking Changes**: Minimal
- **Action Required**:
  1. Remove any lingering `upload_attachment` usage
  2. Verify endpoint compatibility
- **Recommended**: Direct upgrade path

## Testing Requirements

### Before Deprecating
- ✅ Replacement endpoint implemented and tested
- ✅ Migration guide written and reviewed
- ✅ SDK updates available (if needed)
- ✅ Analytics show < 10% usage of endpoint

### Before Sunset
- ✅ Usage < 5% for 30 days
- ✅ All high-volume clients migrated
- ✅ Support tickets resolved
- ✅ Rollback plan documented

### After Removal
- ✅ Monitor 410 response rates
- ✅ Check for client errors
- ✅ Provide migration assistance if needed

## Client Communication Timeline

### T-120 Days (Announcement)
- 📧 Email to all registered API consumers
- 📝 Blog post on developer portal
- 📱 In-app notifications for mobile users
- 💬 Slack/Discord announcements

### T-90 Days (Deprecation Activated)
- 🏷️ Deprecation headers active
- 📊 Usage analytics published
- 📚 Migration guide published
- 🎥 Video tutorial released

### T-60 Days (Reminder)
- 📧 Email reminder with usage stats
- 📈 Dashboard showing migration progress
- 🤝 Offer 1-on-1 migration assistance

### T-30 Days (Sunset Warning)
- ⚠️ Sunset headers active
- 📧 Weekly reminder emails
- 🚨 Dashboard alerts
- 📞 Direct outreach to high-volume clients

### T-7 Days (Final Warning)
- 🚨 Final warning email
- 📱 Push notifications
- 🛑 Banner in API documentation

### T-Day (Removal)
- ❌ Endpoint removed
- 📧 Confirmation email
- 📊 Post-removal analytics

## Monitoring Dashboards

### API Lifecycle Dashboard
Access: `/admin/api/lifecycle/`

**Metrics**:
- Active deprecations count
- Sunset warnings count
- Endpoints approaching sunset
- Migration progress by client

### Deprecation Usage Dashboard
Access: `/admin/api/deprecation-usage/`

**Metrics**:
- Daily usage of deprecated endpoints
- Client version distribution
- Top clients by usage
- Migration velocity

## Emergency Contact

**Critical Issues**:
- Email: api-emergency@youtility.in
- Phone: +91-XXXX-XXXXXX
- On-call: PagerDuty escalation

---

**Policy Version**: 1.0
**Effective Date**: 2025-09-27
**Next Review**: 2025-12-27