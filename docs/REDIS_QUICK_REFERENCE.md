# 🔥 **Redis Quick Reference - IntelliWiz Platform**

## 🚨 **Emergency Commands (Print & Post)**

### **Critical Health Checks**
```bash
# Overall Redis health
python manage.py health_check --component redis

# Memory status
python manage.py optimize_redis_memory --check-only

# Performance dashboard
# URL: /admin/redis/dashboard/

# Sentinel status (if HA enabled)
python manage.py sentinel_admin --status
```

### **Emergency Actions**

| **Problem** | **Quick Fix** | **Command** |
|-------------|---------------|-------------|
| **Redis Down** | Restart service | `sudo systemctl restart redis-youtility` |
| **High Memory** | Optimize memory | `python manage.py optimize_redis_memory --force` |
| **Cache Issues** | Clear cache | `python manage.py clear_cache --all` |
| **Backup Needed** | Create backup | `python manage.py backup_redis --type full` |

---

## 📊 **Performance Thresholds**

| **Metric** | **Target** | **Warning** | **Critical** |
|------------|------------|-------------|--------------|
| **Memory Usage** | <70% | 70-85% | >85% |
| **Hit Ratio** | >90% | 80-90% | <80% |
| **Fragmentation** | <1.5 | 1.5-2.0 | >2.0 |
| **Connections** | <5K | 5K-8K | >8K |
| **Ops/Second** | <8K | 8K-15K | >15K |

---

## 💾 **Backup & Recovery**

### **Quick Backup Commands**
```bash
# Immediate full backup
python manage.py backup_redis --type full --compress

# List recent backups
python manage.py backup_redis --list --days-back 7

# Emergency restore (⚠️ DANGEROUS)
python manage.py restore_redis --backup-id <ID> --confirm
```

### **Backup Schedule**
- **RDB Snapshots**: Every hour
- **Full Backup**: Daily 3:30 AM
- **Cleanup**: Weekly Sunday 2:00 AM
- **Verification**: Daily 5:00 AM

---

## 🔧 **Configuration Files**

### **Standalone Redis**
- **Config**: `/etc/redis/redis.conf`
- **Logs**: `/var/log/redis/redis-server.log`
- **Data**: `/var/lib/redis/`
- **Service**: `redis-youtility.service`

### **Sentinel High Availability**
- **Master Config**: `/etc/redis/redis-master.conf`
- **Replica Config**: `/etc/redis/redis-replica.conf`
- **Sentinel Configs**: `/etc/redis/sentinel-{1,2,3}.conf`
- **Cluster Control**: `./scripts/sentinel_cluster.sh`

---

## 🔒 **Security Checklist**

- [ ] Strong password configured (32+ chars)
- [ ] Dangerous commands disabled/renamed
- [ ] Network access restricted to app servers
- [ ] SSL/TLS enabled for multi-server (recommended)
- [ ] Backup files encrypted
- [ ] Regular security audits scheduled

---

## 📞 **Escalation Contacts**

**On-Call Order:**
1. **DevOps Team Lead**: Primary contact
2. **Senior Backend Developer**: Secondary
3. **CTO/Technical Director**: Final escalation

**External Support:**
- Redis Enterprise Support (if applicable)
- Cloud Provider Support
- System Integrator Support

---

## 🔗 **Important URLs**

- **Performance Dashboard**: `/admin/redis/dashboard/`
- **Health Checks**: `/health/redis/`
- **Celery Monitoring**: `/admin/celery/`
- **Main Admin**: `/admin/django/`

---

## 📋 **Daily Checklist (5 minutes)**

**Morning (9:00 AM):**
- [ ] Check Redis dashboard - any red alerts?
- [ ] Verify overnight backup completion
- [ ] Review memory usage trends
- [ ] Check for any failed tasks in Celery

**Evening (6:00 PM):**
- [ ] Review day's performance summary
- [ ] Check backup verification status
- [ ] Note any issues for follow-up
- [ ] Plan next day's maintenance (if any)

---

## 🆘 **Emergency Phone Tree**

**Step 1:** Check dashboard and logs (2 minutes)
**Step 2:** Attempt quick fix (3 minutes)
**Step 3:** Escalate to on-call DevOps (if not resolved in 5 minutes)
**Step 4:** Conference call with senior team (if critical outage)

---

**💡 Remember: When in doubt, check the dashboard first!**
**Dashboard URL**: `/admin/redis/dashboard/`

**📚 Full Documentation**: `docs/REDIS_OPERATIONS_GUIDE.md`

---

*IntelliWiz Redis Infrastructure - Enterprise Grade*
*Last Updated: Generated during Redis optimization implementation*