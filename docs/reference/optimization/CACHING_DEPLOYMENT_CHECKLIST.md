# Caching Implementation Deployment Checklist

**Pre-deployment validation and activation steps**

---

## ✅ Pre-Deployment Validation

Run validation script:
```bash
./scripts/validate_caching_implementation.sh
```

Expected output: `✓ All checks passed!`

---

## 🚀 Deployment Steps

### Step 1: Enable Cache Monitoring Middleware

**File:** `intelliwiz_config/settings/middleware.py`

Add to `MIDDLEWARE` list:
```python
MIDDLEWARE = [
    # ... existing middleware ...
    'apps.core.middleware.cache_monitoring.CacheMonitoringMiddleware',
]
```

### Step 2: Apply Query Optimizations

```bash
# Preview changes first
python scripts/optimize_count_to_exists.py --dry-run --path apps/

# Review output, then apply
python scripts/optimize_count_to_exists.py --path apps/
```

### Step 3: Verify Redis Configuration

Check Redis is running:
```bash
redis-cli ping  # Should return: PONG
```

Verify cache databases:
```bash
redis-cli INFO keyspace
```

### Step 4: Test Cache Functionality

```python
# Django shell
python manage.py shell

from apps.core.utils_new.cache_utils import cache_result, get_cache_stats

# Test basic caching
@cache_result(timeout=60)
def test_func():
    return "cached"

print(test_func())  # Should work
print(get_cache_stats())  # Should show stats
```

### Step 5: Deploy to Staging

1. Deploy code to staging environment
2. Enable monitoring middleware
3. Monitor logs for 24 hours
4. Check cache hit rate (target: >60%)

### Step 6: Production Deployment

1. Deploy during low-traffic period
2. Monitor cache hit rates
3. Watch for errors in logs
4. Verify dashboard performance improvements

---

## 📊 Post-Deployment Monitoring

### Week 1: Active Monitoring

**Daily checks:**
- [ ] Cache hit rate ≥ 60%
- [ ] Dashboard load time < 500ms
- [ ] No cache-related errors in logs
- [ ] Redis memory usage stable

**Commands:**
```bash
# Check cache stats
curl http://localhost:8000/reports/cache-statistics/

# Monitor logs
tail -f logs/cache.log | grep "Cache Statistics"

# Check Redis memory
redis-cli INFO memory
```

### Week 2-4: Tuning Period

**Adjust based on metrics:**
- Fine-tune TTLs if hit rate is low
- Warm cache for frequently accessed data
- Identify patterns for additional caching

---

## 🔧 Configuration Options

### Cache TTL Adjustments

**File:** `apps/reports/services/dashboard_cache_service.py`

```python
class DashboardCacheService:
    METRICS_TIMEOUT = 300   # Increase if data changes less frequently
    CHART_DATA_TIMEOUT = 600
    SUMMARY_TIMEOUT = 900
```

### Monitoring Settings

**File:** `apps/core/middleware/cache_monitoring.py`

```python
class CacheMonitoringMiddleware:
    LOG_INTERVAL = 100          # Log stats every N requests
    SLOW_CACHE_THRESHOLD = 50   # Threshold for slow cache warnings (ms)
```

---

## 🚨 Rollback Plan

If issues occur:

### Quick Disable (No Code Changes)

**Option 1:** Comment out middleware
```python
MIDDLEWARE = [
    # 'apps.core.middleware.cache_monitoring.CacheMonitoringMiddleware',  # DISABLED
]
```

**Option 2:** Flush Redis cache
```bash
redis-cli FLUSHDB  # Clears all cached data
```

### Full Rollback

```bash
git revert <commit_hash>
python manage.py migrate
systemctl restart gunicorn
```

---

## 📈 Success Metrics

Track these metrics for 1 week:

| Metric | Baseline | Target | Actual |
|--------|----------|--------|--------|
| Cache hit rate | 0% | ≥60% | ___ % |
| Dashboard load time | 2500ms | <500ms | ___ ms |
| Database queries/min | 1500 | <400 | ___ |
| Redis memory usage | 0 MB | <100 MB | ___ MB |

---

## 🐛 Troubleshooting

### Cache Not Working

**Symptom:** Cache hit rate = 0%

**Checks:**
1. Redis running? `redis-cli ping`
2. Middleware enabled?
3. Cache imports working?
4. Check logs for errors

**Fix:**
```bash
# Restart Redis
sudo systemctl restart redis

# Clear cache and try again
redis-cli FLUSHDB
```

### Low Hit Rate (<40%)

**Symptom:** Cache hit rate below expectations

**Possible causes:**
1. TTL too short
2. Cache keys not stable
3. Not enough operations cached

**Fix:**
1. Increase TTLs in service classes
2. Review cache key generation
3. Add more `@cache_result` decorators

### High Memory Usage

**Symptom:** Redis using >500 MB

**Checks:**
```bash
redis-cli INFO memory
redis-cli DBSIZE
```

**Fix:**
1. Review TTLs (reduce if too long)
2. Check for memory leaks
3. Implement cache eviction policy

---

## 📞 Support

### During Deployment

- **Primary:** Review logs in real-time
- **Secondary:** Check cache statistics endpoint
- **Tertiary:** Redis monitoring

### Post-Deployment

- **Week 1:** Daily monitoring
- **Week 2-4:** Bi-weekly review
- **Month 2+:** Monthly review

---

## ✅ Deployment Checklist

### Pre-Deployment

- [ ] Validation script passed
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Redis configured and running
- [ ] Staging environment tested

### Deployment

- [ ] Middleware enabled
- [ ] Query optimizations applied
- [ ] Configuration verified
- [ ] Logs monitored

### Post-Deployment (Week 1)

- [ ] Cache hit rate ≥ 60%
- [ ] Dashboard performance improved
- [ ] No errors in logs
- [ ] Memory usage acceptable
- [ ] Team trained on new features

### Sign-Off

- [ ] Technical lead approval
- [ ] Operations team notified
- [ ] Documentation complete
- [ ] Monitoring configured
- [ ] Rollback plan ready

---

**Deployment Date:** ___________  
**Deployed By:** ___________  
**Approved By:** ___________

**Status:** ⬜ Pending | ⬜ In Progress | ⬜ Complete | ⬜ Rolled Back
