# Asset Function Migration Guide

## Overview
This document describes the migration of PostgreSQL functions `fn_getassetdetails` and `fn_getassetvsquestionset` to Django ORM.

## Migrated Functions

### 1. fn_getassetvsquestionset
**Purpose**: Get question sets associated with an asset

**PostgreSQL Function**:
- Searches `questionset` table for entries where asset ID is in `assetincludes` array
- Returns either IDs (space-separated) or names (tilde-separated)

**Django ORM Implementation**:
```python
AssetManagerORM.get_asset_vs_questionset(bu_id, asset_id, return_type)
```

**Features**:
- Uses PostgreSQL array field operations (`__contains`)
- Implements caching (1-hour TTL)
- Maintains exact output format as PostgreSQL function

### 2. fn_getassetdetails
**Purpose**: Get asset details modified after a certain datetime

**PostgreSQL Function**:
- Returns assets with `mdtz >= _mdtz` for a given site
- Joins with `bt` table for service provider name
- Calls `fn_getassetvsquestionset` for each asset

**Django ORM Implementation**:
```python
AssetManagerORM.get_asset_details(mdtz, site_id)
```

**Features**:
- Uses `select_related` for efficient joins
- Calls Django ORM version of `get_asset_vs_questionset`
- Returns exact same field structure
- Alternative optimized version available using subqueries

## Implementation Details

### File Structure
- **Django ORM Implementation**: `apps/activity/managers/asset_manager_orm.py`
- **Updated GraphQL Resolver**: `apps/service/queries/asset_queries.py`
- **Fallback Version**: `apps/service/queries/asset_queries_with_fallback.py`

### Key Changes

1. **Asset Query Optimization**:
   - Uses `select_related` for all foreign key relationships
   - Prefetches related data to minimize queries
   - Implements caching for question set lookups

2. **Data Type Handling**:
   - UUID fields converted to strings
   - Decimal capacity converted to float
   - Geography fields handled natively by Django

3. **Performance Considerations**:
   - Question set lookups are cached
   - Alternative implementation with subqueries for large datasets
   - Feature flag for gradual rollout

## Migration Strategy

### 1. Feature Flag Approach
Set environment variable to control which implementation is used:
```bash
# Use Django ORM (new)
export USE_DJANGO_ORM_FOR_ASSETS=true

# Use PostgreSQL function (current)
export USE_DJANGO_ORM_FOR_ASSETS=false
```

### 2. Testing
Run the test script to verify compatibility:
```bash
python test_asset_orm_migration.py
```

### 3. Gradual Rollout
1. Deploy with feature flag disabled (PostgreSQL function)
2. Test with specific clients/environments
3. Monitor performance and accuracy
4. Gradually enable for all users
5. Remove PostgreSQL functions after full migration

## Performance Comparison

The Django ORM implementation may have different performance characteristics:

**Advantages**:
- Better caching capabilities
- Easier to optimize with Django's query tools
- No database round-trips for question set lookups (cached)

**Potential Disadvantages**:
- Multiple queries vs. single stored procedure call
- May be slower for very large result sets without optimization

## Monitoring

Track these metrics during migration:
1. Response time comparison
2. Database query count
3. Memory usage (due to caching)
4. Error rates

## Rollback Plan

If issues occur:
1. Set `USE_DJANGO_ORM_FOR_ASSETS=false`
2. The PostgreSQL functions remain in place
3. No code changes needed

## Next Steps

1. Test with production-like data volumes
2. Monitor performance in staging environment
3. Create similar migrations for remaining functions:
   - `fun_getjobneed`
   - `fun_getexttourjobneed`
   - `fn_getbulist_basedon_idnf`