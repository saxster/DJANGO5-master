# Django ORM Migration Guide

## Quick Start

This guide helps you test and deploy the Django ORM implementations that replace PostgreSQL functions.

## Testing the Migrations

### 1. Run the Test Suite

First, ensure your Django server is running and database is accessible.

```bash
# Basic test suite
python test_orm_migrations.py

# Individual asset function test
python test_asset_orm_migration.py
```

### 2. Validate Data Integrity

Run the validation script to ensure data consistency:

```bash
python validate_orm_migrations.py
```

This will:
- Compare ORM results with PostgreSQL function results
- Check for missing or extra records
- Validate field-level data consistency
- Generate a detailed JSON report

### 3. Performance Benchmarking

To compare performance between ORM and PostgreSQL:

```bash
# Run with default settings (10 iterations)
python benchmark_orm_performance.py

# Run with more iterations for accuracy
python benchmark_orm_performance.py --iterations 50 --warmup 5
```

## Enabling ORM Implementations

### Feature Flags

The migrations use environment variables for gradual rollout:

#### Asset Functions
```bash
# Enable Django ORM for asset functions
export USE_DJANGO_ORM_FOR_ASSETS=true

# Disable (use PostgreSQL functions)
export USE_DJANGO_ORM_FOR_ASSETS=false
```

### Configuration Files

Add to your `.env` file or environment configuration:

```env
# Django ORM Feature Flags
USE_DJANGO_ORM_FOR_ASSETS=true
USE_DJANGO_ORM_FOR_JOBS=true
USE_DJANGO_ORM_FOR_BUSINESS_UNITS=true
USE_DJANGO_ORM_FOR_CAPABILITIES=true
```

### Django Settings

In your Django settings, you can control feature flags programmatically:

```python
# settings/production.py
import os

# ORM Migration Feature Flags
ORM_FEATURES = {
    'USE_ASSET_ORM': os.environ.get('USE_DJANGO_ORM_FOR_ASSETS', 'false').lower() == 'true',
    'USE_JOB_ORM': os.environ.get('USE_DJANGO_ORM_FOR_JOBS', 'false').lower() == 'true',
    'USE_BU_ORM': os.environ.get('USE_DJANGO_ORM_FOR_BUSINESS_UNITS', 'false').lower() == 'true',
    'USE_CAPABILITY_ORM': os.environ.get('USE_DJANGO_ORM_FOR_CAPABILITIES', 'false').lower() == 'true',
}
```

## Deployment Strategy

### Phase 1: Testing (Current)
1. Run all test scripts in development environment
2. Validate data integrity
3. Review performance benchmarks
4. Fix any issues found

### Phase 2: Staging Deployment
1. Enable feature flags in staging environment
2. Monitor application logs for errors
3. Run validation scripts against staging data
4. Performance test with realistic load

### Phase 3: Production Rollout
1. **Canary Deployment** (Recommended)
   ```bash
   # Enable for 10% of traffic
   export USE_DJANGO_ORM_FOR_ASSETS=true
   ```

2. **Monitor Key Metrics**
   - Response times
   - Database query count
   - Error rates
   - Memory usage

3. **Gradual Increase**
   - 10% → 25% → 50% → 100%
   - Monitor at each stage

### Phase 4: Cleanup
After successful deployment:
1. Remove PostgreSQL function calls from codebase
2. Drop unused PostgreSQL functions
3. Remove feature flag checks

## Monitoring

### Key Metrics to Track

1. **Performance Metrics**
   - API response times
   - Database query execution time
   - Number of database queries per request

2. **Error Metrics**
   - 500 error rates
   - Database connection errors
   - Timeout errors

3. **Business Metrics**
   - Report generation success rate
   - GraphQL query success rate

### Logging

Enable detailed logging for ORM migrations:

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'orm_migration': {
            'class': 'logging.FileHandler',
            'filename': 'orm_migration.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'apps.activity.managers': {
            'handlers': ['orm_migration'],
            'level': 'INFO',
        },
        'apps.onboarding.managers': {
            'handlers': ['orm_migration'],
            'level': 'INFO',
        },
    },
}
```

## Rollback Procedures

If issues occur during deployment:

### Immediate Rollback
```bash
# Disable all ORM features
export USE_DJANGO_ORM_FOR_ASSETS=false
export USE_DJANGO_ORM_FOR_JOBS=false
export USE_DJANGO_ORM_FOR_BUSINESS_UNITS=false
export USE_DJANGO_ORM_FOR_CAPABILITIES=false
```

### Selective Rollback
```bash
# Disable only problematic feature
export USE_DJANGO_ORM_FOR_ASSETS=false
```

### No Code Changes Required
- Original PostgreSQL functions remain in place
- Feature flags instantly switch implementations
- No deployment needed for rollback

## Troubleshooting

### Common Issues

1. **Performance Degradation**
   - Enable query caching
   - Review query optimization
   - Add database indexes if needed

2. **Data Mismatches**
   - Check timezone handling
   - Verify JSON field extraction
   - Review null value handling

3. **Memory Issues**
   - Implement query pagination
   - Use `iterator()` for large result sets
   - Clear caches periodically

### Debug Mode

Enable detailed query logging:

```python
# Temporarily in Django shell
from django.db import connection
connection.force_debug_cursor = True

# View queries
from django.db import connection
print(connection.queries)
```

## Support

For issues or questions:
1. Check `orm_migration.log` for errors
2. Run validation scripts to identify data issues
3. Review performance benchmarks
4. Check Django debug toolbar for query analysis

## Appendix: Function Reference

### Migrated Functions

| PostgreSQL Function | Django ORM Implementation | Location |
|-------------------|--------------------------|----------|
| fn_getassetdetails | AssetManagerORM.get_asset_details() | apps/activity/managers/asset_manager_orm.py |
| fn_getassetvsquestionset | AssetManagerORM.get_asset_vs_questionset() | apps/activity/managers/asset_manager_orm.py |
| fun_getjobneed | JobneedManagerORM.get_job_needs() | apps/activity/managers/job_manager_orm.py |
| fun_getexttourjobneed | JobneedManagerORM.get_external_tour_job_needs() | apps/activity/managers/job_manager_orm.py |
| fn_getbulist_basedon_idnf | BtManagerORM.get_bulist_basedon_idnf() | apps/onboarding/bt_manager_orm.py |
| get_web_caps_for_client | CapabilityManager.get_web_caps_for_client_orm() | apps/peoples/managers.py |

### Test Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| test_orm_migrations.py | Comprehensive test suite | `python test_orm_migrations.py` |
| validate_orm_migrations.py | Data integrity validation | `python validate_orm_migrations.py` |
| benchmark_orm_performance.py | Performance comparison | `python benchmark_orm_performance.py --iterations 50` |
| test_asset_orm_migration.py | Asset function specific tests | `python test_asset_orm_migration.py` |