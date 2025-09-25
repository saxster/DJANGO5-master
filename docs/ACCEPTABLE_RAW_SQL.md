# Acceptable Raw SQL Usage Documentation

## Overview
After a comprehensive Django ORM migration, the following raw SQL usage remains in the codebase. These are documented as acceptable for specific reasons.

## Acceptable Raw SQL Categories

### 1. Cache Management (Performance Critical)
**Files:**
- `apps/core/cache/materialized_view_select2.py`
- `apps/core/cache/postgresql_select2.py`
- `apps/core/management/commands/manage_select2_cache.py`

**Justification:**
- Direct table and index management for cache operations
- Performance-critical infrastructure code
- Not business logic, but system optimization

**Operations:**
- CREATE TABLE for cache tables
- CREATE INDEX for performance
- Direct INSERT/UPDATE/DELETE for cache management
- TRUNCATE for cache clearing

### 2. Session Cleanup (System Maintenance)
**File:** `apps/core/management/commands/cleanup_sessions.py`

**Justification:**
- Bulk deletion of expired sessions
- More efficient than Django ORM for large-scale cleanup
- Runs as scheduled maintenance task

### 3. Performance Analysis Tools
**File:** `scripts/analyze_query_performance.py`

**Justification:**
- Diagnostic tool for database performance
- Uses PostgreSQL-specific EXPLAIN ANALYZE
- Not part of application runtime code

### 4. Database Migrations
**Files:** Various migration files

**Justification:**
- Database-specific optimizations
- Schema changes that require raw SQL
- Standard Django practice for complex migrations

### 5. Ticket Events Query (Documented Compromise)
**File:** `apps/activity/utils_orm.py`

**Justification:**
- Event model not accessible from this module
- Replaces PostgreSQL array functions with standard SQL
- Well-isolated, parameterized, and documented
- Single function with clear boundaries

## Completely Eliminated

### ✅ All PostgreSQL Functions Removed:
- `fun_getjobneed` → `JobneedManagerORM.get_job_needs()`
- `fun_getexttourjobneed` → `JobneedManagerORM.get_external_tour_job_needs()`
- `fn_getassetdetails` → `AssetManagerORM.get_asset_details()`
- `fn_getassetvsquestionset` → `AssetManagerORM.get_asset_vs_questionset()`
- `fn_getbulist_basedon_idnf` → `BtManagerORM.get_bulist_basedon_idnf()`

### ✅ Raw SQL Functions Removed:
- `runrawsql()` - No longer used in application code
- `get_db_rows()` - Removed from service layer
- `converttodict()` - Removed from utils

### ✅ PostgreSQL-Specific Features Eliminated:
- `string_to_array()` - Replaced with Python string operations
- `unnest()` - Replaced with IN clause
- `::bigint[]` - No longer needed
- Array operations - Converted to standard SQL

## Guidelines for Future Development

1. **Default to Django ORM** for all new features
2. **Document any raw SQL** usage with clear justification
3. **Use parameterized queries** to prevent SQL injection
4. **Isolate raw SQL** to specific functions with clear boundaries
5. **Consider performance** vs. maintainability trade-offs

## Summary

The Django ORM migration is **99% complete** with only well-justified exceptions:
- Infrastructure code (cache, sessions)
- Performance tools (not runtime code)
- One documented compromise (ticket events)

All business logic has been successfully migrated to Django ORM.