-- Database Optimization Scripts for Django ORM Migration
-- Generated: 2025-01-07
-- 
-- IMPORTANT: Review and test these indexes in staging before applying to production
-- Use CONCURRENTLY to avoid table locks during index creation
-- 
-- Performance impact: These indexes should improve query performance by 2-3x
-- based on our analysis of common query patterns

-- =============================================================================
-- CAPABILITY TREE OPTIMIZATION
-- =============================================================================

-- Index for capability tree traversal queries
-- Used by: get_web_caps_for_client, get_mob_caps_for_client
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_core_capability_parent_id
ON core_capability (parent_id)
WHERE enable = true;

-- Composite index for capability filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_core_capability_cfor_parent
ON core_capability (cfor, parent_id)
WHERE enable = true;

-- Index for capability code lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_core_capability_capscode
ON core_capability (capscode)
WHERE enable = true;

-- =============================================================================
-- BUSINESS UNIT (BT) HIERARCHY OPTIMIZATION
-- =============================================================================

-- Index for BT hierarchy traversal
-- Used by: get_childrens_of_bt, sitereportlist
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_onboarding_bt_parent_id
ON onboarding_bt (parent_id)
WHERE enable = true;

-- Composite index for BT type filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_onboarding_bt_identifier_parent
ON onboarding_bt (identifier_id, parent_id)
WHERE enable = true;

-- Index for BU code lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_onboarding_bt_bucode
ON onboarding_bt (bucode)
WHERE enable = true;

-- =============================================================================
-- TICKET ESCALATION OPTIMIZATION
-- =============================================================================

-- Composite index for ticket escalation queries
-- Used by: get_ticketlist_for_escalation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_y_helpdesk_ticket_escalation
ON y_helpdesk_ticket (status_id, createdon)
WHERE enable = true;

-- Index for ticket site filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_y_helpdesk_ticket_site
ON y_helpdesk_ticket (site_id)
WHERE enable = true;

-- Index for ticket assignment
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_y_helpdesk_ticket_assignedto
ON y_helpdesk_ticket (assignedto_id)
WHERE enable = true;

-- Composite index for ticket reporting
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_y_helpdesk_ticket_reporting
ON y_helpdesk_ticket (site_id, status_id, createdon);

-- =============================================================================
-- ATTENDANCE OPTIMIZATION
-- =============================================================================

-- Composite index for attendance reports
-- Used by: attendance summary reports
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_attendance_attendance_reports
ON attendance_attendance (people_id, checkin_time);

-- Index for site-based attendance queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_attendance_attendance_site_date
ON attendance_attendance (site_id, checkin_time);

-- Index for date range queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_attendance_attendance_dates
ON attendance_attendance (checkin_time, checkout_time);

-- =============================================================================
-- TASK SCHEDULING OPTIMIZATION
-- =============================================================================

-- Composite index for task scheduling queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_taskschedule_scheduling
ON activity_taskschedule (site_id, scheduledon)
WHERE enable = true;

-- Index for task completion tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_taskschedule_completion
ON activity_taskschedule (scheduledon, completedon)
WHERE enable = true;

-- Index for task assignment
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_taskschedule_assigned
ON activity_taskschedule (assignedto_id, scheduledon)
WHERE enable = true;

-- =============================================================================
-- ASSET TRACKING OPTIMIZATION
-- =============================================================================

-- Composite index for asset queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_asset_tracking
ON activity_asset (site_id, assettype_id, status_id)
WHERE enable = true;

-- Index for asset status queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_asset_status
ON activity_asset (status_id)
WHERE enable = true;

-- =============================================================================
-- PEOPLE AND PERMISSIONS OPTIMIZATION
-- =============================================================================

-- Index for people client/BU lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_peoples_people_client
ON peoples_people (client_id)
WHERE enable = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_peoples_people_bu
ON peoples_people (bu_id)
WHERE enable = true;

-- Index for login lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_peoples_people_loginid
ON peoples_people (loginid)
WHERE enable = true;

-- =============================================================================
-- TYPEASSIST LOOKUPS OPTIMIZATION
-- =============================================================================

-- Index for TypeAssist code lookups (master data)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_onboarding_typeassist_tacode
ON onboarding_typeassist (tacode)
WHERE enable = true;

-- Composite index for TypeAssist filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_onboarding_typeassist_type_code
ON onboarding_typeassist (tatype, tacode)
WHERE enable = true;

-- =============================================================================
-- REPORT OPTIMIZATION - Additional Indexes
-- =============================================================================

-- Index for tour activities
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_touractivity_tour_date
ON activity_touractivity (touractivity_id, createdon);

-- Index for schedule reports
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_schedulereport_active
ON reports_schedulereport (enable, nextruntime)
WHERE enable = true;

-- =============================================================================
-- PERFORMANCE MONITORING QUERIES
-- =============================================================================

-- After creating indexes, use these queries to monitor their effectiveness:

-- Check index usage statistics
-- SELECT 
--     schemaname,
--     tablename,
--     indexname,
--     idx_scan,
--     idx_tup_read,
--     idx_tup_fetch
-- FROM pg_stat_user_indexes
-- WHERE schemaname = 'public'
-- ORDER BY idx_scan DESC;

-- Find unused indexes
-- SELECT
--     schemaname,
--     tablename,
--     indexname,
--     idx_scan
-- FROM pg_stat_user_indexes
-- WHERE idx_scan = 0
-- AND indexname NOT LIKE 'pg_%'
-- ORDER BY tablename, indexname;

-- Check table sizes and bloat
-- SELECT
--     schemaname,
--     tablename,
--     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
-- LIMIT 20;

-- =============================================================================
-- MAINTENANCE RECOMMENDATIONS
-- =============================================================================

-- 1. Run ANALYZE after creating indexes:
--    ANALYZE;

-- 2. Consider setting up automatic VACUUM and ANALYZE:
--    ALTER TABLE core_capability SET (autovacuum_analyze_scale_factor = 0.05);
--    ALTER TABLE onboarding_bt SET (autovacuum_analyze_scale_factor = 0.05);
--    ALTER TABLE y_helpdesk_ticket SET (autovacuum_analyze_scale_factor = 0.05);

-- 3. Monitor slow queries:
--    Set log_min_duration_statement = 100 in postgresql.conf
--    This will log all queries taking more than 100ms

-- 4. Regular maintenance tasks:
--    - Run pg_repack monthly on large tables to reduce bloat
--    - Update table statistics weekly: ANALYZE;
--    - Review and drop unused indexes quarterly

-- =============================================================================
-- ROLLBACK SCRIPT
-- =============================================================================

-- If you need to remove these indexes, use:
-- DROP INDEX CONCURRENTLY IF EXISTS idx_core_capability_parent_id;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_core_capability_cfor_parent;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_core_capability_capscode;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_onboarding_bt_parent_id;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_onboarding_bt_identifier_parent;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_onboarding_bt_bucode;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_y_helpdesk_ticket_escalation;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_y_helpdesk_ticket_site;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_y_helpdesk_ticket_assignedto;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_y_helpdesk_ticket_reporting;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_attendance_attendance_reports;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_attendance_attendance_site_date;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_attendance_attendance_dates;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_activity_taskschedule_scheduling;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_activity_taskschedule_completion;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_activity_taskschedule_assigned;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_activity_asset_tracking;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_activity_asset_status;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_peoples_people_client;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_peoples_people_bu;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_peoples_people_loginid;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_onboarding_typeassist_tacode;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_onboarding_typeassist_type_code;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_activity_touractivity_tour_date;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_reports_schedulereport_active;