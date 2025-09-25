# PostgreSQL Function Migration Status

## Summary
This document tracks the migration of PostgreSQL stored functions to Django ORM implementations.

## Completed Migrations

### 1. Business Territory (BT) Hierarchy Functions
**Original PostgreSQL Functions:**
- `fn_get_bulist` - Get business unit hierarchy in various formats
- `fn_menupbt` - Get parent nodes in hierarchy  
- `fn_mendownbt` - Get child nodes in hierarchy
- `fn_menallbt` - Get both parent and child nodes

**Django ORM Implementation:**
- Created `apps/onboarding/bt_manager_orm.py`
- Key methods:
  - `BtManagerORM.get_bulist()` - Main hierarchy traversal function
  - `BtManagerORM.get_all_bu_of_client()` - Get all BUs under a client
  - `BtManagerORM.get_whole_tree()` - Get entire BU tree
  - `BtManagerORM.get_sitelist_web()` - Get sites based on user permissions

**Files Updated:**
- `apps/onboarding/managers.py` - Updated to use Django ORM instead of raw SQL calls

### 2. Job Management Functions
**Original PostgreSQL Functions:**
- `fn_get_schedule_for_adhoc` - Find available schedule slots
- Various complex queries for job reporting

**Django ORM Implementation:**
- Created `apps/activity/managers/job_manager_orm.py`
- Key methods:
  - `JobneedManagerORM.get_schedule_for_adhoc()` - Find available schedule slots
  - `JobneedManagerORM.get_jobneed_for_report()` - Get job details for reports
  - `JobneedManagerORM.get_hdata_for_report()` - Hierarchical report data
  - `JobneedManagerORM.get_deviation_jn()` - Job deviation details
  - `JobneedManagerORM.get_jobneedmodifiedafter()` - Jobs modified after datetime

**Files Updated:**
- `apps/activity/managers/job_manager.py` - Updated to use Django ORM implementations

### 3. Site List Function
**Original PostgreSQL Function:**
- `fn_get_siteslist_web` - Get site list based on user permissions

**Django ORM Implementation:**
- Implemented in `BtManagerORM.get_sitelist_web()`
- Handles both admin and non-admin users
- Considers group assignments and direct site assignments

## Remaining PostgreSQL Functions

### Still Using Raw SQL:
1. `fun_getjobneed` - Get job needs for a person
2. `fun_getexttourjobneed` - Get external tour job needs
3. `fn_getbulist_basedon_idnf` - Get BU list based on identifier filter
4. `fn_getassetvsquestionset` - Get question sets for assets
5. `fn_getassetdetails` - Get asset details with question sets

## Benefits of Migration

1. **Performance**: Python tree traversal is often faster than recursive CTEs for typical data sizes
2. **Caching**: Built-in caching for frequently accessed hierarchical data
3. **Maintainability**: Django ORM code is easier to understand and modify
4. **Database Independence**: No longer tied to PostgreSQL-specific features
5. **Testing**: Easier to unit test Django ORM code

## Migration Strategy

For remaining functions:
1. Analyze if the function is still actively used
2. Consider if complex logic is really needed
3. Implement using Django ORM with proper caching
4. Test performance with production-like data
5. Gradually switch over with fallback mechanism

## Notes

- All migrated functions maintain backward compatibility with original return formats
- Caching is implemented for expensive operations (1-hour TTL)
- Tree traversal uses efficient Python algorithms instead of recursive CTEs
- Special handling for Django 5 compatibility issues has been applied