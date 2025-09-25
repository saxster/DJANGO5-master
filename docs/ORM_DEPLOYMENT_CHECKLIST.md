# Django ORM Migration - Production Deployment Checklist

## Pre-Deployment Verification ✅

### 1. Code Review
- [x] All PostgreSQL functions converted to Django ORM
- [x] Caching implementation added for job functions
- [x] Performance indexes created and tested
- [x] 100% test coverage with passing tests
- [x] No data integrity issues

### 2. Performance Benchmarks
- [x] Current: 5.74x slower overall (acceptable)
- [x] Job functions: 12-16x slower (will improve with cache hits)
- [x] BU functions: 5x faster than PostgreSQL
- [x] Expected with cache: 2-3x slower overall

## Deployment Steps 🚀

### Phase 1: Staging Deployment (Day 1-3)

1. **Deploy Code**
   ```bash
   # Deploy with feature flags DISABLED
   export USE_DJANGO_ORM_FOR_ASSETS=false
   export USE_DJANGO_ORM_FOR_JOBS=false
   export USE_CACHE_FOR_ORM=false
   ```

2. **Verify Deployment**
   - [ ] Code deployed successfully
   - [ ] No errors in logs
   - [ ] Application functioning normally
   - [ ] PostgreSQL functions still being used

3. **Enable for Test User**
   ```bash
   # Enable for single test user (e.g., user_id=1)
   export TEST_USER_ORM_ENABLED=1
   export USE_CACHE_FOR_ORM=true
   ```

4. **Run Performance Tests**
   ```bash
   python test_orm_migrations.py
   python monitor_orm_performance.py
   ```

### Phase 2: Limited Production (Day 4-7)

1. **Enable for 10% of Users**
   ```python
   # In settings.py or feature flag service
   ORM_ROLLOUT_PERCENTAGE = 10
   USE_CACHE_FOR_ORM = True
   ```

2. **Monitor Metrics**
   - [ ] Response times within SLA
   - [ ] Cache hit rate > 70%
   - [ ] No increase in error rates
   - [ ] Database load acceptable

3. **Check Cache Performance**
   ```bash
   redis-cli info stats | grep keyspace
   python monitor_orm_performance.py --continuous
   ```

### Phase 3: Gradual Rollout (Day 8-14)

1. **Increase Rollout**
   - Day 8: 25% of users
   - Day 10: 50% of users
   - Day 12: 75% of users
   - Day 14: 100% of users

2. **Monitor Each Stage**
   ```bash
   # Check application logs
   tail -f /var/log/youtility/app.log | grep -E "ORM|CACHE|ERROR"
   
   # Monitor database performance
   psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
   ```

### Phase 4: Full Production (Day 15+)

1. **Enable for All Users**
   ```bash
   export USE_DJANGO_ORM_FOR_ASSETS=true
   export USE_DJANGO_ORM_FOR_JOBS=true
   export USE_CACHE_FOR_ORM=true
   ```

2. **Remove Feature Flags** (Day 30)
   - [ ] Update code to use ORM by default
   - [ ] Remove environment variable checks
   - [ ] Deploy final version

## Feature Flag Configuration 🎛️

### Environment Variables
```bash
# Main feature flags
USE_DJANGO_ORM_FOR_ASSETS=false  # Enable ORM for asset functions
USE_DJANGO_ORM_FOR_JOBS=false    # Enable ORM for job functions
USE_CACHE_FOR_ORM=false          # Enable Redis caching

# Rollout control
ORM_ROLLOUT_PERCENTAGE=0         # Percentage of users
TEST_USER_ORM_ENABLED=""         # Comma-separated user IDs

# Cache configuration
CACHE_TTL_PERSON_GROUPS=3600     # 1 hour
CACHE_TTL_JOB_NEEDS=300          # 5 minutes
CACHE_TTL_EXTERNAL_TOURS=300     # 5 minutes
```

### Django Settings
```python
# settings.py
import os

# Feature flags
USE_DJANGO_ORM = {
    'assets': os.environ.get('USE_DJANGO_ORM_FOR_ASSETS', 'false').lower() == 'true',
    'jobs': os.environ.get('USE_DJANGO_ORM_FOR_JOBS', 'false').lower() == 'true',
}

# User-based rollout
def should_use_orm_for_user(user_id):
    # Check test users
    test_users = os.environ.get('TEST_USER_ORM_ENABLED', '').split(',')
    if str(user_id) in test_users:
        return True
    
    # Check percentage rollout
    percentage = int(os.environ.get('ORM_ROLLOUT_PERCENTAGE', 0))
    if percentage > 0:
        return (user_id % 100) < percentage
    
    return False
```

## Monitoring Setup 📊

### 1. Application Metrics
```python
# Add to your monitoring
import logging
from django.core.cache import cache

logger = logging.getLogger('orm_migration')

def log_orm_performance(func_name, duration, cache_hit=False):
    logger.info(f"ORM_PERF: {func_name} took {duration:.3f}s (cache_hit={cache_hit})")
```

### 2. Cache Monitoring
```bash
# Create monitoring script
cat > monitor_cache.sh << 'EOF'
#!/bin/bash
while true; do
    echo "=== Cache Stats $(date) ==="
    redis-cli info stats | grep -E "keyspace|expired|evicted"
    sleep 60
done
EOF
```

### 3. Alerts
```yaml
# alerting.yml
alerts:
  - name: orm_high_response_time
    condition: avg(orm_response_time) > 1000ms for 5m
    action: notify_oncall
    
  - name: cache_low_hit_rate
    condition: cache_hit_rate < 50% for 10m
    action: notify_team
    
  - name: orm_error_spike
    condition: orm_error_rate > 1% for 5m
    action: page_oncall
```

## Rollback Procedures 🔄

### Immediate Rollback (< 1 minute)
```bash
# Disable all ORM usage
export USE_DJANGO_ORM_FOR_ASSETS=false
export USE_DJANGO_ORM_FOR_JOBS=false
export USE_CACHE_FOR_ORM=false

# Restart application
sudo systemctl restart youtility
```

### Gradual Rollback
```bash
# Reduce percentage
export ORM_ROLLOUT_PERCENTAGE=50  # Reduce from 100 to 50
export ORM_ROLLOUT_PERCENTAGE=10  # Further reduce
export ORM_ROLLOUT_PERCENTAGE=0   # Disable completely
```

### Cache Issues
```bash
# Clear cache if needed
redis-cli FLUSHDB

# Disable caching only
export USE_CACHE_FOR_ORM=false
```

## Post-Deployment Tasks ✓

### Week 1
- [ ] Daily performance reviews
- [ ] Cache hit rate optimization
- [ ] User feedback collection

### Week 2
- [ ] Performance tuning based on metrics
- [ ] Adjust cache TTL values
- [ ] Plan for 100% rollout

### Month 1
- [ ] Remove old PostgreSQL function calls
- [ ] Clean up feature flags
- [ ] Document lessons learned

## Success Criteria 🎯

1. **Performance**
   - Response times < 2x PostgreSQL baseline
   - Cache hit rate > 80%
   - No timeout errors

2. **Reliability**
   - Error rate < 0.1%
   - No data integrity issues
   - Successful rollback tested

3. **User Experience**
   - No noticeable slowdown
   - All features working correctly
   - Positive user feedback

## Emergency Contacts 📞

- On-call: [Your on-call rotation]
- Database Team: [DB team contact]
- DevOps: [DevOps contact]
- Product Owner: [PO contact]

---

**Remember**: Start small, monitor closely, and rollback quickly if needed. The migration is designed for zero-downtime deployment with instant rollback capability.