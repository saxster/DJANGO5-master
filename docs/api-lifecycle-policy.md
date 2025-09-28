# API Lifecycle Management Policy

## Overview
This document defines the lifecycle management policy for YOUTILITY5 REST and GraphQL APIs, ensuring predictable evolution while maintaining backward compatibility.

## Version Support Policy

### Supported Versions
- **Current**: v1 (stable)
- **Next**: v2 (planned)
- **Support Window**: Minimum 2 major versions maintained concurrently

### Version Numbering
- **Major versions** (v1, v2): Breaking changes
- **Minor versions** (v1.1, v1.2): Additive, non-breaking changes
- **Patch versions** (v1.1.1): Bug fixes only

## Deprecation Lifecycle

### Phase 1: Active (Status: `active`)
- Endpoint is fully supported
- No deprecation warnings
- Regular updates and bug fixes

### Phase 2: Deprecated (Status: `deprecated`)
- **Duration**: Minimum 90 days
- **Communication**:
  - Release notes announcement
  - Email to registered API consumers
  - Slack/Discord notifications
- **Response Headers** (RFC 9745/8594):
  ```
  Deprecation: @1719792000
  Warning: 299 - "Deprecated API. Use /api/v2/resource instead."
  Link: </docs/migrations/resource-v2>; rel="deprecation"
  X-Deprecated-Replacement: /api/v2/resource
  ```
- **Functionality**: Endpoint continues to work normally
- **GraphQL**: `@deprecated` directive added to schema

### Phase 3: Sunset Warning (Status: `sunset_warning`)
- **Duration**: 30 days before removal
- **Communication**:
  - Warning emails every 7 days
  - Dashboard alerts
  - API analytics reports showing usage
- **Response Headers**:
  ```
  Deprecation: @1719792000
  Sunset: Mon, 31 Jul 2025 23:59:59 GMT
  Warning: 299 - "API will be removed in 15 days on 2025-07-31"
  ```
- **Functionality**: Endpoint still functional but logs increased warnings

### Phase 4: Removed (Status: `removed`)
- **Action**: Endpoint returns 410 Gone
- **Response**:
  ```json
  {
    "error": "Gone",
    "message": "This endpoint was removed on 2025-07-31",
    "replacement": "/api/v2/resource",
    "migration_guide": "https://docs.youtility.in/migrations/resource-v2",
    "status_code": 410
  }
  ```

## Breaking vs Non-Breaking Changes

### Breaking Changes (Require New Major Version)
- Removing endpoints or fields
- Changing field types
- Making required fields out of optional ones
- Changing authentication requirements
- Modifying response structure
- Changing error codes

### Non-Breaking Changes (Same Version)
- Adding new endpoints
- Adding optional fields
- Adding new query parameters
- Deprecating fields (with grace period)
- Performance improvements
- Bug fixes

## GraphQL Evolution Strategy

### Preferred: Schema Evolution (Not Versioning)
GraphQL APIs evolve through continuous schema extension rather than versioning:

1. **Add New Fields**: Don't remove old ones immediately
2. **Deprecate Old Fields**: Use `@deprecated` directive
   ```graphql
   type User {
     name: String @deprecated(reason: "Use fullName instead")
     fullName: String
   }
   ```
3. **Monitor Usage**: Track deprecated field queries
4. **Safe Removal**: Remove only when usage < 1% for 90 days

### If Versioning Required
- Use separate GraphQL endpoints: `/api/v1/graphql/`, `/api/v2/graphql/`
- Maintain schema compatibility within major version

## Deprecation Decision Process

### 1. Proposal Phase
- Submit deprecation proposal with:
  - Reason for deprecation
  - Replacement endpoint/field
  - Estimated impact (client count)
  - Migration complexity assessment
- Review by API governance committee

### 2. Approval Phase
- Technical review: Breaking change assessment
- Business review: Client impact analysis
- Timeline approval: Deprecation + sunset dates

### 3. Announcement Phase (D-Day minus 120 days)
- **D-120**: Announcement to all API consumers
- **D-90**: Deprecation headers activated
- **D-60**: Email reminders to active users
- **D-30**: Sunset warning phase begins
- **D-7**: Final warning emails
- **D-Day**: Endpoint removed

### 4. Monitoring Phase
- Track usage of deprecated endpoints
- Generate weekly migration progress reports
- Alert on high-usage deprecated endpoints
- Offer migration assistance for high-volume consumers

### 5. Removal Phase
- Change status to `removed`
- Return 410 Gone responses
- Maintain redirect for 6 months
- Archive endpoint documentation

## Client SDK Compatibility Matrix

| Backend API Version | Min Kotlin SDK | Min Swift SDK | Support Status |
|---------------------|----------------|---------------|----------------|
| v1.0                | 1.0.0          | 1.0.0         | ✅ Supported   |
| v1.5                | 1.2.0          | 1.2.0         | ✅ Supported   |
| v2.0 (planned)      | 2.0.0          | 2.0.0         | 🔜 Planned     |

## Migration Support Resources

### Documentation
- Migration guides: `/docs/api-migrations/{feature}-v{version}/`
- Code examples: Available in all supported SDKs
- Video tutorials: YouTube playlist

### Developer Support
- Email: api-support@youtility.in
- Slack: #api-migrations
- Office hours: Weekly Tuesdays 10:00-11:00 UTC

### Automated Tools
- SDK migration script generators
- API diff tool: Compare versions side-by-side
- Client code scanner: Identify deprecated usage

## Metrics & KPIs

### Deprecation Health
- **Target**: < 5% traffic on deprecated endpoints at sunset
- **Alert**: > 10% traffic 30 days before sunset
- **Success**: Zero 5xx errors due to removals

### Client Migration Progress
- Weekly reports showing:
  - Clients migrated vs remaining
  - High-volume clients status
  - Usage trends of deprecated endpoints

### Communication Effectiveness
- Email open rates > 60%
- Migration guide page views
- Support ticket volume

## Emergency Procedures

### Rollback Deprecated Removal
If critical client depends on removed endpoint:
1. Restore endpoint immediately (code from git history)
2. Set status to `sunset_warning`
3. Extend sunset date by 30 days
4. Contact client directly for migration plan

### Security Vulnerability in Deprecated API
If security issue found in deprecated endpoint:
1. Accelerate sunset timeline
2. Immediate notification to all users
3. Force upgrade assistance
4. Consider emergency removal if critical

## Version Sunset Schedule (Current)

| Endpoint | API Type | Deprecated | Sunset | Replacement |
|----------|----------|------------|--------|-------------|
| `Mutation.upload_attachment` | GraphQL | 2025-09-27 | 2026-06-30 | `secure_file_upload` |

## Monitoring Commands

```bash
python manage.py api_deprecation_report
python manage.py api_sunset_warnings
python manage.py api_usage_stats --endpoint /api/v1/people/ --days 30
python manage.py api_client_versions
```

## Compliance Requirements

### Regulatory
- Maintain audit trail of all API changes
- Document data structure changes
- Client notification proof (email delivery logs)

### Technical
- All deprecations tracked in `APIDeprecation` model
- All usage logged in `APIDeprecationUsage` model
- Analytics dashboard accessible to stakeholders

### Security
- No deprecated endpoints with known vulnerabilities
- Accelerated sunset for security issues
- Security team approval for all major version changes

---

**Last Updated**: 2025-09-27
**Next Review**: 2025-12-27
**Owner**: API Platform Team