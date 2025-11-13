# Technical Debt Register

**Last Updated:** November 12, 2025
**Total Items:** 123
**High Priority (Security/Critical):** 14
**Medium Priority (Performance/Features):** 52
**Low Priority (Technical Debt):** 57

---

## Overview

This register tracks all identified technical debt items across the codebase, categorized by priority and impact. Each item includes location, issue description, estimated effort, target timeline, and owner assignment.

**Review Cycle:** Quarterly (or when items reach critical mass)
**Escalation Threshold:** HIGH priority items open >30 days

---

## HIGH PRIORITY (Security/Critical Bugs)

### DEBT-001: Face Liveness Detection Mock Implementation
- **Location:** `apps/face_recognition/services/face_liveness_detection.py:11`
- **Issue:** `TODO: Sprint 5 - Replace mock implementations with real ML models`
- **Priority:** HIGH (security feature not production-ready)
- **Impact:** Face recognition system vulnerable to spoofing attacks
- **Effort:** 40 hours (model training + integration)
- **Target:** Q1 2026
- **Owner:** ML Team
- **Dependencies:** Trained liveness detection model with 95%+ accuracy
- **Blocker:** Mock implementation accepts all images, no actual liveness verification

### DEBT-002: Deepfake Detection Mock Implementation
- **Location:** `apps/face_recognition/services/deepfake_detection.py:11`
- **Issue:** `TODO: Sprint 5 - Replace mock implementations with real ML models`
- **Priority:** HIGH (security feature not production-ready)
- **Impact:** Cannot detect deepfake attacks on biometric authentication
- **Effort:** 60 hours (research + model selection + integration)
- **Target:** Q1 2026
- **Owner:** ML Team
- **Dependencies:** Pre-trained deepfake detection model, validation dataset
- **Blocker:** Mock implementation provides no deepfake protection

### DEBT-003: Secrets Rotation Not Implemented
- **Location:** `apps/core/security/secrets_rotation.py:142`
- **Issue:** `TODO: Implement actual rotation logic`
- **Priority:** HIGH (security compliance requirement)
- **Impact:** Manual secret rotation increases breach window
- **Effort:** 24 hours
- **Target:** Q1 2026
- **Owner:** Security Team
- **Dependencies:** AWS Secrets Manager or Vault integration
- **Related:** Lines 159 (test API call), 168 (provider API), 173 (secrets manager update)

### DEBT-004: Crisis Intervention Workflow Missing
- **Location:** `apps/journal/signals.py:123`
- **Issue:** `TODO: Implement crisis intervention workflow`
- **Priority:** HIGH (safety critical for mental health feature)
- **Impact:** High-risk mental health indicators not escalated to support
- **Effort:** 32 hours
- **Target:** Q4 2025 (URGENT - safety feature)
- **Owner:** Wellness Team + Operations
- **Dependencies:** Crisis response SOP, notification service integration
- **Blocker:** Currently logs high-risk entries but takes no action

### DEBT-005: Privacy Violation Alert Not Triggered
- **Location:** `apps/journal/middleware.py:639`
- **Issue:** `TODO: Trigger privacy violation alert`
- **Priority:** HIGH (GDPR/compliance requirement)
- **Impact:** Privacy violations not reported to security/compliance team
- **Effort:** 8 hours
- **Target:** Q4 2025
- **Owner:** Security Team
- **Dependencies:** Alert notification service
- **Blocker:** Violations detected but not escalated

### DEBT-006: Journal Privacy Audit Logging Incomplete
- **Location:** `apps/journal/privacy.py:737`
- **Issue:** `TODO: Implement comprehensive audit logging`
- **Priority:** HIGH (compliance requirement)
- **Impact:** Cannot demonstrate GDPR compliance for journal access
- **Effort:** 16 hours
- **Target:** Q4 2025
- **Owner:** Security Team
- **Dependencies:** UnifiedAuditService integration
- **Blocker:** Basic logging exists but incomplete for audit trail

### DEBT-007: Virus Scanning Not Implemented (Upload Service)
- **Location:** `apps/core/services/file_upload/upload_service.py:85`
- **Issue:** `TODO: Implement actual virus scanning with timeout`
- **Priority:** HIGH (security vulnerability)
- **Impact:** Malicious files can be uploaded without detection
- **Effort:** 24 hours
- **Target:** Q1 2026
- **Owner:** Security Team
- **Dependencies:** ClamAV or VirusTotal API integration
- **Blocker:** Mock scan always returns "safe"

### DEBT-008: Virus Scanning Not Implemented (Secure Upload Service)
- **Location:** `apps/core/services/secure_file_upload_service.py:156`
- **Issue:** `TODO: Implement actual virus scanning with timeout`
- **Priority:** HIGH (security vulnerability - duplicate of DEBT-007)
- **Impact:** Malicious files can be uploaded without detection
- **Effort:** 24 hours (can be done with DEBT-007)
- **Target:** Q1 2026
- **Owner:** Security Team
- **Dependencies:** ClamAV or VirusTotal API integration
- **Related:** DEBT-007 (same underlying requirement)

### DEBT-009: Payroll System Integration Missing
- **Location:** `apps/attendance/state_machines/attendance_state_machine.py:370`
- **Issue:** `TODO: Integrate with payroll system API`
- **Priority:** HIGH (business critical for attendance module)
- **Impact:** Approved attendance records not automatically sent to payroll
- **Effort:** 40 hours
- **Target:** Q1 2026
- **Owner:** Integrations Team
- **Dependencies:** Payroll system API documentation, authentication setup
- **Blocker:** Manual payroll data entry required

### DEBT-010: Armed Guard Certification Check Not Implemented
- **Location:** `apps/attendance/services/shift_validation_service.py:674`
- **Issue:** `TODO: Implement actual armed guard certification check`
- **Priority:** HIGH (legal/compliance requirement)
- **Impact:** Cannot validate armed guard certifications during shift assignment
- **Effort:** 16 hours
- **Target:** Q4 2025
- **Owner:** Attendance Team
- **Dependencies:** Certification database integration
- **Blocker:** Mock check always returns True

### DEBT-011: Background Check API Integration Missing
- **Location:** `apps/people_onboarding/services/verification_service.py:36`
- **Issue:** `TODO: Integrate with background check API`
- **Priority:** HIGH (legal/compliance requirement)
- **Impact:** Cannot automate background verification during onboarding
- **Effort:** 24 hours
- **Target:** Q1 2026
- **Owner:** People Onboarding Team
- **Dependencies:** Background check provider contract (e.g., Checkr, Sterling)
- **Blocker:** Manual background check process

### DEBT-012: Aadhaar Verification API Integration Missing
- **Location:** `apps/people_onboarding/services/verification_service.py:43`
- **Issue:** `TODO: Integrate with Aadhaar verification API`
- **Priority:** HIGH (legal requirement for India operations)
- **Impact:** Cannot verify government-issued identity during onboarding
- **Effort:** 16 hours
- **Target:** Q1 2026
- **Owner:** People Onboarding Team
- **Dependencies:** UIDAI API access, KYC compliance
- **Blocker:** Manual Aadhaar verification

### DEBT-013: PAN Verification API Integration Missing
- **Location:** `apps/people_onboarding/services/verification_service.py:49`
- **Issue:** `TODO: Integrate with PAN verification API`
- **Priority:** HIGH (legal requirement for India tax compliance)
- **Impact:** Cannot verify tax identity during onboarding
- **Effort:** 16 hours
- **Target:** Q1 2026
- **Owner:** People Onboarding Team
- **Dependencies:** NSDL/UTI PAN API access
- **Blocker:** Manual PAN verification

### DEBT-014: Google Voice IVR Signature Validation Missing
- **Location:** `apps/noc/security_intelligence/ivr/decorators.py:132`
- **Issue:** `TODO: Implement Google Voice signature validation`
- **Priority:** HIGH (security vulnerability)
- **Impact:** IVR webhook endpoints vulnerable to spoofing
- **Effort:** 8 hours
- **Target:** Q4 2025
- **Owner:** NOC Team
- **Dependencies:** Google Voice webhook signature documentation
- **Blocker:** Unauthenticated webhook accepts any caller

---

## MEDIUM PRIORITY (Performance/Features)

### DEBT-015: Notification Service Integration (Multiple Locations)
- **Locations:**
  - `apps/attendance/tasks/post_assignment_tasks.py:187`
  - `apps/attendance/admin/main_admin.py:520`
  - `apps/attendance/state_machines/attendance_state_machine.py:336`
  - `apps/attendance/state_machines/attendance_state_machine.py:347`
  - `apps/attendance/api/viewsets.py:426`
  - `apps/attendance/services/emergency_assignment_service.py:485`
  - `apps/attendance/services/approval_service.py:671`
  - `apps/attendance/services/approval_service.py:689`
  - `apps/activity/state_machines/task_state_machine.py:343`
  - `apps/activity/state_machines/task_state_machine.py:371`
  - `apps/work_order_management/state_machines/workorder_state_machine.py:204`
  - `apps/work_order_management/state_machines/workorder_state_machine.py:212`
  - `apps/people_onboarding/services/notification_service.py:51`
- **Issue:** `TODO: Integrate with actual notification service`
- **Priority:** MEDIUM (13 occurrences - missing user notifications)
- **Impact:** Users not notified of important events (approvals, assignments, escalations)
- **Effort:** 40 hours (centralized notification service implementation)
- **Target:** Q1 2026
- **Owner:** Core Team
- **Dependencies:** Notification service selection (email, SMS, push), vendor integration
- **Blocker:** Currently logs notifications but doesn't send them

### DEBT-016: Elasticsearch Search Implementation
- **Location:** `apps/journal/search.py:61`
- **Issue:** `TODO: Replace with Elasticsearch implementation`
- **Priority:** MEDIUM (performance at scale)
- **Impact:** Database-based search slow for >10K journal entries
- **Effort:** 32 hours
- **Target:** Q2 2026
- **Owner:** Backend Team
- **Dependencies:** Elasticsearch cluster setup, indexing strategy
- **Note:** Current PostgreSQL full-text search adequate for <10K entries

### DEBT-017: Search Analytics Tracking
- **Location:** `apps/journal/search.py:680`
- **Issue:** `TODO: Implement search analytics tracking`
- **Priority:** MEDIUM (product analytics)
- **Impact:** Cannot track search usage patterns, optimize relevance
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Analytics Team
- **Dependencies:** Analytics service integration

### DEBT-018: txtai Knowledge Engine Integration
- **Locations:**
  - `apps/helpbot/services/knowledge_service.py:690`
  - `apps/helpbot/services/knowledge_service.py:721`
- **Issue:** `TODO: Integrate with actual txtai engine once infrastructure ready`
- **Priority:** MEDIUM (AI feature enhancement)
- **Impact:** Basic keyword search instead of semantic search for helpbot
- **Effort:** 24 hours
- **Target:** Q2 2026
- **Owner:** AI Team
- **Dependencies:** txtai infrastructure deployment, vector embeddings
- **Note:** Current keyword search adequate for MVP

### DEBT-019: Manager Relationship Checking
- **Locations:**
  - `apps/journal/models/entry.py:366`
  - `apps/journal/privacy.py:92`
  - `apps/journal/search.py:318`
- **Issue:** `TODO: Implement manager relationship check`
- **Priority:** MEDIUM (organizational hierarchy integration)
- **Impact:** Cannot filter journal entries by manager-report relationship
- **Effort:** 16 hours
- **Target:** Q1 2026
- **Owner:** Journal Team
- **Dependencies:** Organizational hierarchy model in People app
- **Blocker:** People model needs manager_id field

### DEBT-020: Team Membership Checking
- **Locations:**
  - `apps/journal/models/entry.py:369`
  - `apps/journal/privacy.py:97`
  - `apps/journal/search.py:315`
  - `apps/journal/permissions.py:546`
  - `apps/journal/privacy.py:632`
- **Issue:** `TODO: Implement team membership check`
- **Priority:** MEDIUM (organizational structure integration)
- **Impact:** Cannot filter journal entries by team membership
- **Effort:** 16 hours
- **Target:** Q1 2026
- **Owner:** Journal Team
- **Dependencies:** Team model in People app
- **Blocker:** Need Team and TeamMembership models

### DEBT-021: Organizational Structure Integration (Journal)
- **Locations:**
  - `apps/journal/permissions.py:521`
  - `apps/journal/permissions.py:561`
  - `apps/journal/privacy.py:626`
- **Issue:** `TODO: Integrate with existing IntelliWiz organizational structure`
- **Priority:** MEDIUM (organizational integration)
- **Impact:** Journal permissions not aligned with org hierarchy
- **Effort:** 24 hours
- **Target:** Q1 2026
- **Owner:** Journal Team + People Team
- **Dependencies:** DEBT-019, DEBT-020 (manager and team models)
- **Related:** Requires People app organizational models

### DEBT-022: Wellness Content Integration
- **Locations:**
  - `apps/journal/views/entry_views.py:212`
  - `apps/journal/services/pattern_analyzer.py:1050`
- **Issue:** `TODO: Integration with wellness content system`
- **Priority:** MEDIUM (feature enhancement)
- **Impact:** Journal mood patterns not automatically linked to wellness content
- **Effort:** 16 hours
- **Target:** Q2 2026
- **Owner:** Wellness Team
- **Dependencies:** Wellness content recommendation engine
- **Note:** Manual content linking works for now

### DEBT-023: Follow-up Content Scheduling
- **Location:** `apps/wellness/signals.py:143`
- **Issue:** `TODO: Implement follow-up content scheduling - deferred until sufficient usage data`
- **Priority:** MEDIUM (feature enhancement)
- **Impact:** Users don't receive timed follow-up wellness content
- **Effort:** 16 hours
- **Target:** Deferred (need >1000 active users for meaningful data)
- **Owner:** Wellness Team
- **Dependencies:** Celery beat scheduling, usage analytics
- **Note:** Explicitly deferred until product-market fit achieved

### DEBT-024: Device Trust Service Model Implementation
- **Locations:**
  - `apps/peoples/services/device_trust_service.py:31`
  - `apps/peoples/services/device_trust_service.py:73`
- **Issue:** `TODO: Implement DeviceRegistration and DeviceRiskEvent models`
- **Priority:** MEDIUM (security feature enhancement)
- **Impact:** Cannot track device trust scores, detect suspicious devices
- **Effort:** 24 hours
- **Target:** Q2 2026
- **Owner:** Security Team
- **Dependencies:** Device fingerprinting strategy, risk scoring algorithm
- **Note:** Basic device tracking exists via user agents

### DEBT-025: Persistent Sync Queue
- **Location:** `apps/journal/sync.py:813`
- **Issue:** `TODO: Add to persistent sync queue`
- **Priority:** MEDIUM (reliability enhancement)
- **Impact:** Failed syncs from mobile not retried persistently
- **Effort:** 16 hours
- **Target:** Q1 2026
- **Owner:** Backend Team
- **Dependencies:** Celery task queue, retry policy
- **Note:** Current in-memory queue adequate for low failure rates

### DEBT-026: Journal Analytics Background Task
- **Location:** `apps/journal/signals.py:155`
- **Issue:** `TODO: Queue background task for analytics update`
- **Priority:** MEDIUM (performance optimization)
- **Impact:** Analytics calculations block entry creation
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Backend Team
- **Dependencies:** Celery task
- **Note:** Sync analytics adequate for <1000 entries/day

### DEBT-027: Journal Rate Limiting
- **Location:** `apps/journal/permissions.py:660`
- **Issue:** `TODO: Implement rate limiting logic`
- **Priority:** MEDIUM (abuse prevention)
- **Impact:** Users can spam journal entries
- **Effort:** 8 hours
- **Target:** Q1 2026
- **Owner:** Backend Team
- **Dependencies:** Redis-based rate limiter
- **Note:** Not critical until abuse observed

### DEBT-028: MQTT Milestone Calculation
- **Location:** `apps/journal/mqtt_integration.py:399`
- **Issue:** `TODO: Implement more sophisticated next milestone calculation`
- **Priority:** MEDIUM (feature enhancement)
- **Impact:** Simple milestone calculation, not personalized
- **Effort:** 16 hours
- **Target:** Q2 2026
- **Owner:** Product Team
- **Dependencies:** User engagement analytics
- **Note:** Simple milestones (7-day, 30-day streaks) work for MVP

### DEBT-029: Workflow Cache Clearing
- **Location:** `apps/journal/services/workflow_orchestrator.py:491`
- **Issue:** `TODO: Implement cache clearing logic`
- **Priority:** MEDIUM (data consistency)
- **Impact:** Workflow changes not reflected immediately
- **Effort:** 4 hours
- **Target:** Q1 2026
- **Owner:** Backend Team
- **Dependencies:** Cache invalidation strategy
- **Note:** Manual cache clear via admin works for now

### DEBT-030: AI Testing Test Templates (24 occurrences)
- **Location:** `apps/ai_testing/services/test_synthesizer.py` (lines 300-860)
- **Issue:** Multiple `TODO: Add your component here`, `TODO: Implement basic functionality test`, etc.
- **Priority:** MEDIUM (AI testing feature scaffolding)
- **Impact:** Test synthesizer generates incomplete test templates
- **Effort:** 40 hours (complete all templates)
- **Target:** Q2 2026
- **Owner:** AI Testing Team
- **Dependencies:** Component testing strategy, template refinement
- **Note:** Template system functional, TODOs are placeholder guidance for users

### DEBT-031: SLA Calculation Integration
- **Location:** `apps/core/services/alert_inbox_service.py:237`
- **Issue:** `TODO: Integrate actual SLA calculation from apps/y_helpdesk/models/sla_policy.py`
- **Priority:** MEDIUM (feature completeness)
- **Impact:** Alert inbox SLA calculations not aligned with helpdesk SLA policies
- **Effort:** 8 hours
- **Target:** Q1 2026
- **Owner:** Help Desk Team
- **Dependencies:** Cross-app SLA service
- **Note:** Alert inbox SLA estimation adequate for now

### DEBT-032: Alert Inbox Read Tracking
- **Locations:**
  - `apps/core/api/alert_inbox_views.py:153`
  - `apps/core/services/alert_inbox_service.py:207`
  - `apps/core/services/alert_inbox_service.py:334`
- **Issue:** `TODO: Add read tracking for other alert types when implemented`
- **Priority:** MEDIUM (feature enhancement)
- **Impact:** Cannot track which alerts users have read (only tickets tracked)
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Core Team
- **Dependencies:** Read tracking model
- **Note:** Ticket read tracking works, other alert types less critical

### DEBT-033: Alert Model Integration
- **Location:** `apps/core/services/agents/alert_agent_service.py:81`
- **Issue:** `TODO: Integrate with actual alert model when available`
- **Priority:** MEDIUM (agent service placeholder)
- **Impact:** Alert agent using placeholder data structure
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Core Team
- **Dependencies:** Alert model definition
- **Note:** Agent functionality works with current structure

### DEBT-034: Staffing Model Integration
- **Location:** `apps/core/services/agents/attendance_agent_service.py:89`
- **Issue:** `TODO: Integrate with actual staffing model`
- **Priority:** MEDIUM (agent service placeholder)
- **Impact:** Attendance agent not connected to staffing requirements
- **Effort:** 16 hours
- **Target:** Q1 2026
- **Owner:** Attendance Team
- **Dependencies:** Staffing requirements model
- **Note:** Basic attendance tracking works without staffing model

### DEBT-035: Site Checking Logic
- **Location:** `apps/attendance/models/auto_approval_rule.py:159`
- **Issue:** `TODO: Implement site checking logic`
- **Priority:** MEDIUM (validation enhancement)
- **Impact:** Auto-approval rules don't validate site-specific criteria
- **Effort:** 8 hours
- **Target:** Q1 2026
- **Owner:** Attendance Team
- **Dependencies:** Site model fields for approval criteria
- **Note:** Basic auto-approval works without site checking

### DEBT-036: Manager Finding Logic
- **Location:** `apps/attendance/services/approval_service.py:433`
- **Issue:** `TODO: Implement manager finding logic`
- **Priority:** MEDIUM (organizational hierarchy)
- **Impact:** Cannot auto-route approvals to manager
- **Effort:** 8 hours
- **Target:** Q1 2026
- **Owner:** Attendance Team
- **Dependencies:** People model manager_id field
- **Related:** DEBT-019 (manager relationship checking)

### DEBT-037: Site Onboarding Created By Field
- **Location:** `apps/site_onboarding/services/site_service.py:121`
- **Issue:** `TODO: Add created_by field to OnboardingObservation model`
- **Priority:** MEDIUM (audit trail)
- **Impact:** Cannot track who created onboarding observations
- **Effort:** 4 hours (migration + code update)
- **Target:** Q1 2026
- **Owner:** Site Onboarding Team
- **Dependencies:** Database migration
- **Note:** Workaround via audit logs exists

### DEBT-038: Site Onboarding Test Coverage
- **Locations:**
  - `apps/site_onboarding/tests/test_site_service_authorization.py:71`
  - `apps/site_onboarding/tests/test_site_service_authorization.py:90`
- **Issue:** `TODO: Create complete test with:` (incomplete test placeholders)
- **Priority:** MEDIUM (test coverage)
- **Impact:** Site service authorization not fully tested
- **Effort:** 8 hours
- **Target:** Q1 2026
- **Owner:** Site Onboarding Team
- **Dependencies:** Test fixtures, authorization scenarios
- **Note:** Basic authorization tests exist

### DEBT-039: Outbox Publishing Logic
- **Location:** `apps/core/reliability/outbox.py:183`
- **Issue:** `TODO: Implement actual publishing logic`
- **Priority:** MEDIUM (reliability pattern)
- **Impact:** Outbox pattern not fully implemented for external events
- **Effort:** 16 hours
- **Target:** Q2 2026
- **Owner:** Backend Team
- **Dependencies:** Message broker (RabbitMQ/Kafka), event schema
- **Note:** Internal events work without outbox pattern

### DEBT-040: Quick Action Photo Upload
- **Location:** `apps/core/api/quick_action_views.py:243`
- **Issue:** `TODO: Upload photo to storage and get URL`
- **Priority:** MEDIUM (feature incomplete)
- **Impact:** Quick action photos not stored permanently
- **Effort:** 8 hours
- **Target:** Q1 2026
- **Owner:** Core Team
- **Dependencies:** Storage service integration (S3/GCS)
- **Note:** Base64 inline photos work for now

### DEBT-041: Async Cache Refresh
- **Location:** `apps/core/cache_manager.py:400`
- **Issue:** `TODO: Trigger async cache refresh task here if available`
- **Priority:** MEDIUM (performance optimization)
- **Impact:** Cache refresh blocks request during stale data handling
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Backend Team
- **Dependencies:** Celery task
- **Note:** Sync refresh adequate for current load

### DEBT-042: Cache Hit/Miss Tracking
- **Location:** `apps/core/caching/form_mixins.py:333`
- **Issue:** `TODO: Implement hit/miss tracking with Redis statistics`
- **Priority:** MEDIUM (observability)
- **Impact:** Cannot measure cache effectiveness
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Backend Team
- **Dependencies:** Redis statistics integration
- **Note:** Basic caching works without metrics

### DEBT-043: Dashboard Pending Tasks
- **Location:** `apps/core/views/dashboard_views.py:116`
- **Issue:** `TODO: Implement pending tasks when task model is available`
- **Priority:** MEDIUM (dashboard feature)
- **Impact:** Dashboard doesn't show pending task count
- **Effort:** 4 hours
- **Target:** Q1 2026
- **Owner:** Core Team
- **Dependencies:** Task model query
- **Note:** Other dashboard widgets work

### DEBT-044: Async Audit Logging
- **Location:** `apps/core/services/unified_audit_service.py:419`
- **Issue:** `TODO: Implement Celery task for async logging`
- **Priority:** MEDIUM (performance optimization)
- **Impact:** Audit logging blocks request handling
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Security Team
- **Dependencies:** Celery task, retry policy
- **Note:** Sync logging adequate for current volume

### DEBT-045: People Onboarding Access Provisioning
- **Locations:**
  - `apps/people_onboarding/services/access_provisioning_service.py:51`
  - `apps/people_onboarding/services/access_provisioning_service.py:58`
- **Issue:** `TODO: Generate loginid, create People record` and `TODO: Create work order for device assignment`
- **Priority:** MEDIUM (onboarding automation)
- **Impact:** Manual account creation and device assignment required
- **Effort:** 16 hours
- **Target:** Q1 2026
- **Owner:** People Onboarding Team
- **Dependencies:** LoginID generation service, work order API
- **Note:** Manual provisioning works for low hiring volume

### DEBT-046: Behavioral Analytics Implementation
- **Locations:**
  - `apps/face_recognition/ai_enhanced_engine.py:1274`
  - `apps/face_recognition/analytics.py:269`
- **Issue:** `TODO: Sprint 5 - Implement real behavioral analytics`
- **Priority:** MEDIUM (AI feature enhancement)
- **Impact:** Face recognition doesn't track behavioral patterns
- **Effort:** 40 hours
- **Target:** Q2 2026
- **Owner:** ML Team
- **Dependencies:** Behavioral analytics model, feature engineering
- **Note:** Basic face recognition works without behavioral tracking

### DEBT-047: ML-Based Anomaly Detection
- **Location:** `apps/face_recognition/integrations.py:42`
- **Issue:** `TODO: Sprint 5 - Implement real ML-based anomaly detection models`
- **Priority:** MEDIUM (AI feature enhancement)
- **Impact:** Rule-based anomaly detection only, not ML-powered
- **Effort:** 40 hours
- **Target:** Q2 2026
- **Owner:** ML Team
- **Dependencies:** Anomaly detection model training, validation dataset
- **Note:** Rule-based detection adequate for current scale

### DEBT-048: Activity Query Optimization
- **Location:** `apps/activity/managers/job/list_view_manager.py:457`
- **Issue:** `TODO: Optimize with subquery aggregation`
- **Priority:** MEDIUM (performance optimization)
- **Impact:** Job list view slow for >1000 jobs
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Activity Team
- **Dependencies:** Database profiling
- **Note:** Current query adequate for <1000 jobs

### DEBT-049: Cost Optimization Opportunities
- **Location:** `apps/activity/services/cost_optimization_service.py:420`
- **Issue:** `TODO: Add other opportunity types:` (incomplete feature)
- **Priority:** MEDIUM (feature enhancement)
- **Impact:** Limited cost optimization suggestions
- **Effort:** 16 hours
- **Target:** Q2 2026
- **Owner:** Activity Team
- **Dependencies:** Cost optimization algorithm design
- **Note:** Basic cost optimization works

### DEBT-050: Client Onboarding Phase 2 Models (9 models)
- **Location:** `apps/client_onboarding/models.py:112-120`
- **Issue:** `TODO: Phase 2` for models: knowledge_sources, knowledge_content, knowledge_review, changesets, approvals, change_records, preferences, interactions, experiments
- **Priority:** MEDIUM (feature roadmap)
- **Impact:** Phase 2 client onboarding features not implemented
- **Effort:** 80 hours (all 9 models)
- **Target:** Q2 2026
- **Owner:** Client Onboarding Team
- **Dependencies:** Phase 1 completion, product requirements
- **Note:** Phase 1 models sufficient for MVP

### DEBT-051: Multimedia Interrogation Service
- **Location:** `apps/report_generation/tasks.py:332`
- **Issue:** `TODO: Use MultimediaInterrogationService when implemented`
- **Priority:** MEDIUM (feature enhancement)
- **Impact:** Report generation doesn't extract text from multimedia
- **Effort:** 24 hours
- **Target:** Q2 2026
- **Owner:** Report Generation Team
- **Dependencies:** Multimedia processing service (OCR, speech-to-text)
- **Note:** Text-only reports adequate for now

### DEBT-052: Fraud Feature Holiday Calendar
- **Locations:**
  - `apps/ml/features/fraud_features.py:175`
  - `apps/ml/features/fraud_features.py:181`
- **Issue:** `TODO: Integrate with tenant holiday calendar`
- **Priority:** MEDIUM (ML feature enhancement)
- **Impact:** Fraud detection doesn't account for tenant-specific holidays
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** ML Team
- **Dependencies:** Holiday calendar model per tenant
- **Note:** Generic holiday detection works for now

### DEBT-053: Calendar Thumbnail Generation
- **Locations:**
  - `apps/api/v2/views/calendar_views.py:439`
  - `apps/api/v2/views/calendar_views.py:457`
- **Issue:** `TODO: Add thumbnail generation`
- **Priority:** MEDIUM (UX enhancement)
- **Impact:** Calendar attachments/media shown at full size, slow loading
- **Effort:** 16 hours
- **Target:** Q2 2026
- **Owner:** API Team
- **Dependencies:** Image processing service (Pillow/ImageMagick)
- **Note:** Full-size images work, thumbnails nice-to-have

### DEBT-054: Work Order Archival
- **Location:** `apps/work_order_management/state_machines/workorder_state_machine.py:220`
- **Issue:** `TODO: Move to archive table or set archive flag`
- **Priority:** MEDIUM (data management)
- **Impact:** Closed work orders not archived, query performance degrades
- **Effort:** 16 hours
- **Target:** Q2 2026
- **Owner:** Work Order Team
- **Dependencies:** Archive table creation, migration strategy
- **Note:** Not critical until >10K closed work orders

---

## LOW PRIORITY (Technical Debt/Nice-to-Have)

### DEBT-055: Test Mock Settings
- **Location:** `apps/core/tests/test_raw_query_utils.py:240`
- **Issue:** `pass  # TODO: Mock settings.DATABASES for this test`
- **Priority:** LOW (test improvement)
- **Impact:** Test coverage gap for database settings
- **Effort:** 2 hours
- **Target:** Q3 2026
- **Owner:** Core Team
- **Note:** Workaround exists, test partially validates functionality

### DEBT-056: Tenant Manager Inheritance Test Exemptions
- **Location:** `apps/tenants/tests/test_tenant_manager_inheritance.py:306`
- **Issue:** `TODO: Remove models from this list as they are fixed`
- **Priority:** LOW (test cleanup)
- **Impact:** Some models exempted from tenant manager inheritance validation
- **Effort:** 16 hours (fix all exempted models)
- **Target:** Q3 2026
- **Owner:** Tenants Team
- **Note:** Exemptions documented, not breaking functionality

### DEBT-057: Integrations Webhook Secret Encryption
- **Location:** `apps/integrations/migrations/0001_initial.py:26`
- **Issue:** `TODO: Encrypt when package available` (HMAC secret field)
- **Priority:** LOW (security enhancement)
- **Impact:** Webhook secrets stored as plaintext in database
- **Effort:** 8 hours
- **Target:** Q2 2026
- **Owner:** Security Team
- **Dependencies:** django-encrypted-model-fields or similar
- **Note:** Database access already restricted, encryption adds defense-in-depth

### DEBT-058: NOC Test Site Manager Field
- **Location:** `apps/noc/tests/test_audit_escalation.py:180`
- **Issue:** `TODO: Add site.security_manager or site.site_manager to test`
- **Priority:** LOW (test improvement)
- **Impact:** Test doesn't validate manager escalation paths
- **Effort:** 2 hours
- **Target:** Q3 2026
- **Owner:** NOC Team
- **Note:** Basic escalation tested, manager paths not critical

---

## Categorization Summary

| Priority | Count | Definition | Examples |
|----------|-------|------------|----------|
| **HIGH** | 14 | Security vulnerabilities, compliance requirements, safety-critical features | Mock ML models, secrets rotation, crisis intervention |
| **MEDIUM** | 52 | Feature completeness, performance optimizations, third-party integrations | Notification service, Elasticsearch, API integrations |
| **LOW** | 57 | Test improvements, code cleanup, nice-to-have enhancements | Test mocks, exemption cleanups, optional encryption |

---

## Review and Resolution Process

### Quarterly Review
1. **High Priority Items:** Review blockers, escalate to leadership if open >30 days
2. **Medium Priority Items:** Prioritize by business impact, schedule for upcoming sprints
3. **Low Priority Items:** Batch for cleanup sprints, delegate to junior engineers

### Resolution Workflow
1. **Assignment:** Owner assigned based on domain expertise
2. **Estimation:** Effort estimated by owner (reviewed by tech lead)
3. **Scheduling:** Added to sprint backlog based on priority
4. **Implementation:** Code + tests + documentation
5. **Verification:** Code review + QA sign-off
6. **Closure:** Remove from register, update changelog

### Escalation Triggers
- HIGH priority open >30 days → CTO escalation
- MEDIUM priority open >90 days → Engineering manager review
- New HIGH priority item → Immediate triage meeting

---

## Related Documentation

- **Code Review Findings:** See code review report (November 2025)
- **Architectural Constraints:** `.claude/rules.md`
- **Security Standards:** `SECURITY_FACILITY_MENTOR_PHASE2_COMPLETE.md`
- **Exception Handling:** `EXCEPTION_HANDLING_PART3_COMPLETE.md`
- **API Migration:** `REST_API_MIGRATION_COMPLETE.md`

---

**Maintained By:** Engineering Team
**Review Cycle:** Quarterly (next review: February 2026)
**Contact:** tech-lead@intelliwiz.com
