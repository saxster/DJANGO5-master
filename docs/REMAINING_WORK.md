# Remaining Work for Django ORM Migration

## Current Status
✅ Successfully migrated:
- Business Territory hierarchy functions (`fn_get_bulist`, etc.)
- Job management functions (5 complex queries)
- Fixed all circular import issues
- Django server now starts without errors

## Remaining PostgreSQL Functions

### 1. **fn_getassetdetails** (ACTIVELY USED)
- **Location**: Used in `apps/service/queries/asset_queries.py` for GraphQL API
- **Purpose**: Get asset details with question sets
- **Priority**: HIGH - This is actively used in production
- **Migration Strategy**: Create Django ORM version in `apps/activity/managers/asset_manager_orm.py`

### 2. **fun_getjobneed** 
- **Location**: Defined in `raw_sql_functions.py`
- **Purpose**: Get job needs for a person for current/upcoming dates
- **Priority**: MEDIUM - Check if actively used
- **Migration Strategy**: Add to `JobneedManagerORM`

### 3. **fun_getexttourjobneed**
- **Location**: Defined in `raw_sql_functions.py`
- **Purpose**: Get external tour job needs
- **Priority**: MEDIUM - Check if actively used
- **Migration Strategy**: Add to `JobneedManagerORM`

### 4. **fn_getbulist_basedon_idnf**
- **Location**: Defined in `raw_sql_functions.py`
- **Purpose**: Get BU list filtered by identifier (CUSTOMER/SITE)
- **Priority**: LOW - May not be actively used
- **Migration Strategy**: Add to `BtManagerORM`

### 5. **fn_getassetvsquestionset**
- **Location**: Defined in `raw_sql_functions.py`
- **Purpose**: Get question sets associated with an asset
- **Priority**: LOW - Used by fn_getassetdetails
- **Migration Strategy**: Convert as part of fn_getassetdetails migration

## Other Remaining Tasks

### 1. **Find Active Usage**
- Search for actual calls to `fun_getjobneed` and `fun_getexttourjobneed`
- Check mobile API endpoints
- Review scheduled tasks/cron jobs

### 2. **Performance Testing**
- Test converted ORM queries with production data volumes
- Compare performance with original PostgreSQL functions
- Optimize with select_related/prefetch_related where needed

### 3. **Migration Strategy**
- Keep PostgreSQL functions as fallback during transition
- Add feature flags to switch between SQL and ORM
- Monitor performance in production

### 4. **Documentation**
- Document all migrated functions
- Create developer guide for using ORM versions
- Update API documentation

## Recommended Next Steps

1. **Immediate**: Migrate `fn_getassetdetails` since it's actively used in GraphQL API
2. **Next**: Check if `fun_getjobneed` and `fun_getexttourjobneed` are actively used
3. **Later**: Migrate remaining functions based on usage analysis
4. **Finally**: Remove unused PostgreSQL functions after confirming no dependencies

## Notes
- All migrated functions should maintain exact same return format
- Use caching where appropriate for expensive queries
- Consider using Django's `Prefetch` objects for complex relationships
- Test thoroughly with edge cases (empty results, large datasets, etc.)