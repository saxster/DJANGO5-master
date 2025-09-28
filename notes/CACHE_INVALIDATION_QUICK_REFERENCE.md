# 🚀 Cache Invalidation Quick Reference

## 📋 Common Operations

### **After Schema Changes:**
```bash
python3 manage.py bump_cache_version
python3 manage.py warm_caches
```

### **Daily Health Check:**
```bash
python3 manage.py monitor_cache_ttl --report --save-to-db
```

### **Weekly Optimization Review:**
```bash
python3 manage.py monitor_cache_ttl --recommendations
```

### **Troubleshooting Stale Data:**
```bash
python3 manage.py invalidate_caches --pattern dashboard --tenant-id 1
python3 manage.py invalidate_caches --model People
```

---

## 🔧 **API Quick Reference**

### **Cache with Versioning:**
```python
from apps.core.caching import get_versioned_cache_key

key = get_versioned_cache_key('dashboard:metrics')
cache.set(key, data, 900)
```

### **Validate Cache Keys:**
```python
from apps.core.caching.security import validate_cache_key, sanitize_cache_key, CacheSecurityError

try:
    validate_cache_key(user_input)
    cache.set(user_input, data, 300)
except CacheSecurityError:
    safe_key = sanitize_cache_key(user_input)
    cache.set(safe_key, data, 300)
```

### **Check TTL Health:**
```python
from apps.core.caching.ttl_monitor import get_ttl_health_report

report = get_ttl_health_report()
for pattern, health in report['patterns'].items():
    if health['health_status'] == 'unhealthy':
        print(f"⚠️  {pattern}: {health['recommendation']}")
```

### **Distributed Invalidation:**
```python
from apps.core.caching.distributed_invalidation import publish_invalidation_event

publish_invalidation_event('dashboard:*', reason='data_update')
```

---

## ⚙️ **Configuration**

### **Cache Versioning:**
```python
# In settings.py or .env
CACHE_VERSION = '1.0'
```

### **TTL Monitoring:**
```python
TTL_HEALTH_THRESHOLD = 0.80
TTL_ANOMALY_THRESHOLD = 0.60
```

### **Security Limits:**
```python
MAX_CACHE_ENTRY_SIZE = 1048576
MAX_CACHE_KEY_LENGTH = 250
CACHE_RATE_LIMIT = 1000
```

---

## 🧪 **Testing**

### **Run All Cache Tests:**
```bash
python3 -m pytest apps/core/tests/test_cache_*.py -v
```

### **Run Security Tests Only:**
```bash
python3 -m pytest apps/core/tests/test_cache_security_comprehensive.py -v -m security
```

### **Run Integration Tests:**
```bash
python3 -m pytest apps/core/tests/test_cache_invalidation_advanced.py -v -m integration
```

---

## 🚨 **Troubleshooting**

### **Problem: Cache still stale after model change**
```bash
# Check if signals are wired
python3 manage.py shell -c "from apps.core.caching.invalidation import cache_invalidation_manager; print(cache_invalidation_manager.model_dependencies)"

# Manual invalidation
python3 manage.py invalidate_caches --model YourModel --tenant-id 1
```

### **Problem: Low cache hit ratio**
```bash
# Get recommendations
python3 manage.py monitor_cache_ttl --recommendations

# Check anomalies
python3 manage.py monitor_cache_ttl --anomalies
```

### **Problem: Cache memory growing**
```bash
# Check old version caches
python3 manage.py bump_cache_version --dry-run

# Clear old versions
python3 manage.py bump_cache_version --no-cleanup=False
```

---

## 📊 **Health Metrics**

| Metric | Healthy | Unhealthy |
|--------|---------|-----------|
| Hit Ratio | > 80% | < 60% |
| Memory Usage | < 512MB | > 1GB |
| Anomalies | 0-2 | > 5 |
| TTL Efficiency | 90%+ | < 70% |

---

## 🔗 **Related Documentation**

- Full implementation report: `CACHE_INVALIDATION_ENHANCEMENT_COMPLETE.md`
- Existing caching docs: `docs/caching-strategy-documentation.md`
- Security rules: `.claude/rules.md`
- Code examples: `apps/core/tests/test_cache_*.py`

---

**Last Updated:** 2025-09-27