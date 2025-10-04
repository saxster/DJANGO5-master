# 🔥 **Redis Operations Guide - IntelliWiz Django Platform**

## 📋 **Executive Summary**

This comprehensive guide provides operational procedures for the Redis infrastructure supporting the IntelliWiz Django 5.2.1 enterprise facility management platform. The Redis implementation provides high-performance caching, session management, task queue brokering, and WebSocket channel layers with enterprise-grade security, monitoring, and high availability.

### **🎯 Redis Usage Overview**

| **Service** | **Database** | **Purpose** | **Performance Impact** |
|-------------|--------------|-------------|----------------------|
| **Django Cache** | DB 1 | Query caching, template fragments | 🔥 **CRITICAL** - 90%+ response time improvement |
| **Celery Broker** | DB 0 | Task queue management | 🔥 **CRITICAL** - Background processing |
| **Celery Results** | DB 1 | Task result storage | 🟡 **HIGH** - Task completion tracking |
| **WebSocket Channels** | DB 2 | Real-time communication | 🟡 **HIGH** - Live features |
| **Sessions** | DB 4 | User session storage | 🟡 **HIGH** - Authentication state |
| **Select2 Cache** | MaterializedView | Form dropdown optimization | 🟢 **MEDIUM** - UI responsiveness |

---

## 🚀 **Quick Reference - Emergency Procedures**

### **🚨 Critical Incidents**

| **Scenario** | **Immediate Action** | **Command** |
|--------------|---------------------|-------------|
| **Redis Down** | Check service status | `sudo systemctl status redis-youtility` |
| **High Memory** | Trigger optimization | `python manage.py optimize_redis_memory --force` |
| **Cache Miss Storm** | Warm critical caches | `python manage.py warm_cache --critical` |
| **Sentinel Failover** | Check cluster status | `python manage.py sentinel_admin --status` |
| **Backup Failure** | Manual backup | `python manage.py backup_redis --type full` |

### **📊 Health Check Commands**

```bash
# Complete Redis health assessment
python manage.py health_check --component redis

# Memory and performance status
python manage.py optimize_redis_memory --check-only

# Sentinel cluster status (if HA enabled)
python manage.py sentinel_admin --status

# Performance dashboard
# Access: /admin/redis/dashboard/
```

---

## 🔧 **Installation & Setup Procedures**

### **1. Standalone Redis Setup**

```bash
# Security-hardened standalone setup
./scripts/setup_redis_secure.sh production

# Development setup
./scripts/setup_redis_secure.sh development

# Verify installation
redis-cli ping
python manage.py health_check --component redis
```

### **2. High Availability Sentinel Setup**

```bash
# Complete Sentinel cluster setup (3 nodes)
./scripts/setup_redis_sentinel.sh

# Enable Sentinel in Django
echo "REDIS_SENTINEL_ENABLED=true" >> .env.production

# Validate Sentinel cluster
python manage.py sentinel_admin --validate

# Test failover capability
./scripts/test_sentinel_failover.sh
```

### **3. Environment Configuration**

**Production Environment:**
```bash
# Copy and customize environment template
cp config/redis/redis.env.template .env.redis.production

# Required environment variables:
REDIS_PASSWORD=your_secure_password_min_32_chars
REDIS_MAX_MEMORY=2gb
REDIS_SENTINEL_ENABLED=true  # For HA setup
```

**Development Environment:**
```bash
# Development environment with simpler config
cp config/redis/redis.env.template .env.redis.development

# Development defaults:
REDIS_PASSWORD=dev_redis_password_2024
REDIS_MAX_MEMORY=512mb
REDIS_SENTINEL_ENABLED=false  # Standalone for development
```

---

## 📊 **Performance Monitoring & Optimization**

### **Real-Time Performance Dashboard**

**Access:** `/admin/redis/dashboard/`

**Key Metrics:**
- **Memory Usage**: Target <70% (Warning: 70-85%, Critical: >85%)
- **Hit Ratio**: Target >90% (Warning: 80-90%, Critical: <80%)
- **Operations/Second**: Monitor for load patterns
- **Fragmentation Ratio**: Target <1.5 (Warning: 1.5-2.0, Critical: >2.0)
- **Connection Count**: Monitor for connection leaks

### **Automated Monitoring Tasks**

| **Task** | **Frequency** | **Purpose** |
|----------|---------------|-------------|
| **Memory Monitor** | Every 10 minutes | Detect memory issues |
| **Memory Optimization** | Every hour | Automated cleanup |
| **Metrics Collection** | Every 5 minutes | Performance tracking |
| **Trend Analysis** | Every 6 hours | Capacity planning |
| **Capacity Report** | Weekly | Growth projections |

### **Manual Optimization Commands**

```bash
# Memory optimization
python manage.py optimize_redis_memory --force

# Performance analysis
python manage.py redis_admin --analyze --hours 24

# Cache warming
python manage.py warm_cache --all

# Memory status report
python manage.py optimize_redis_memory --check-only --json
```

---

## 💾 **Backup & Recovery Procedures**

### **Automated Backup Schedule**

| **Backup Type** | **Frequency** | **Retention** | **Purpose** |
|-----------------|---------------|---------------|-------------|
| **RDB Snapshots** | Hourly | 7 days | Point-in-time recovery |
| **Full Backup** | Daily 3:30 AM | 30 days | Complete data recovery |
| **Cleanup** | Weekly Sunday | N/A | Storage management |
| **Verification** | Daily 5:00 AM | N/A | Integrity validation |

### **Manual Backup Operations**

```bash
# Create immediate backup
python manage.py backup_redis --type full --compress

# List available backups
python manage.py backup_redis --list --days-back 7

# Verify backup integrity
python manage.py backup_redis --verify --backup-id <backup_id>

# Clean up old backups
python manage.py backup_redis --cleanup --retention-days 14
```

### **Emergency Recovery Procedures**

```bash
# ⚠️ CRITICAL: List available backups for recovery
python manage.py restore_redis --list

# ⚠️ CRITICAL: Restore from backup (creates pre-restore backup)
python manage.py restore_redis --backup-id <backup_id> --confirm

# ⚠️ DANGEROUS: Restore without pre-backup (NOT RECOMMENDED)
python manage.py restore_redis --backup-id <backup_id> --no-pre-backup --confirm
```

---

## 🔒 **Security Best Practices**

### **Production Security Checklist**

- ✅ **Authentication**: Strong password (32+ characters)
- ✅ **Network Security**: Bind to private IPs only
- ✅ **Command Renaming**: Dangerous commands disabled/renamed
- ✅ **Firewall**: Redis ports restricted to application servers
- ✅ **SSL/TLS**: Encrypted connections (recommended for multi-server)
- ✅ **Monitoring**: Security events logged and monitored
- ✅ **Backup Encryption**: Backup files encrypted at rest

### **Security Configuration Validation**

```bash
# Check security configuration
redis-cli CONFIG GET requirepass
redis-cli CONFIG GET bind

# Verify dangerous commands are disabled
redis-cli FLUSHALL  # Should return error
redis-cli CONFIG GET save

# Check connection encryption (if enabled)
redis-cli --tls --cert redis.crt --key redis.key ping
```

---

## 🔥 **Troubleshooting Decision Trees**

### **Problem: Redis Connection Failures**

```
Redis Connection Failed?
├── Check service status
│   ├── ❌ Service Down → Start service → Check logs
│   └── ✅ Service Running → Check network
│       ├── ❌ Network Issues → Check firewall/DNS
│       └── ✅ Network OK → Check authentication
│           ├── ❌ Auth Failed → Verify password
│           └── ✅ Auth OK → Check memory/resources
```

### **Problem: High Memory Usage**

```
Memory Usage >85%?
├── Check fragmentation ratio
│   ├── >2.0 → Run defragmentation
│   └── <2.0 → Analyze cache patterns
│       ├── Low hit ratio → Review TTL settings
│       ├── Large objects → Enable compression
│       └── High eviction → Increase memory limit
```

### **Problem: Poor Performance**

```
Redis Performance Issues?
├── Check hit ratio
│   ├── <80% → Analyze cache patterns + warm caches
│   └── >80% → Check operations rate
│       ├── >10K ops/sec → Consider read replicas
│       └── <10K ops/sec → Check slow log
│           └── Slow queries → Optimize data structures
```

---

## 📈 **Capacity Planning Guide**

### **Growth Projection Calculator**

**Current Usage Analysis:**
```bash
# Get current metrics
python manage.py optimize_redis_memory --check-only --json > current_metrics.json

# Weekly capacity report
python manage.py redis_admin --capacity-report --weeks 4
```

**Memory Capacity Planning:**

| **Current Usage** | **Growth Rate/Week** | **Recommended Action** |
|------------------|---------------------|----------------------|
| 0-50% | Any | Monitor trends |
| 50-70% | <5% | Plan for growth |
| 50-70% | >10% | Increase capacity soon |
| 70-85% | Any | Increase capacity immediately |
| >85% | Any | Emergency capacity increase |

**Connection Capacity Planning:**

| **Current Connections** | **Max Clients** | **Action Required** |
|------------------------|-----------------|-------------------|
| <5,000 | 10,000 | Monitor growth |
| 5,000-8,000 | 10,000 | Plan connection pooling |
| >8,000 | 10,000 | Optimize connections immediately |

### **Scaling Decision Matrix**

**Vertical Scaling (Increase Resources):**
- Memory usage >70% consistently
- Single-instance performance sufficient
- Cost-effective for current load

**Horizontal Scaling (Add Replicas):**
- Read-heavy workload (>80% reads)
- Need geographic distribution
- Write performance adequate

**Architecture Change (Clustering):**
- Need >5TB data storage
- Horizontal scaling across multiple masters
- Complex data distribution requirements

---

## 🆘 **Incident Response Playbooks**

### **Playbook 1: Redis Complete Outage**

**Severity:** 🔴 **CRITICAL** - Complete service impact

**Immediate Response (0-5 minutes):**
1. Check Redis service status: `sudo systemctl status redis-youtility`
2. Check system resources: `free -h && df -h`
3. Check Redis logs: `tail -50 /var/log/redis/redis-server.log`
4. Attempt service restart: `sudo systemctl restart redis-youtility`

**Escalation (5-15 minutes):**
1. Check for hardware issues: `dmesg | tail -20`
2. Check network connectivity: `ping redis-host`
3. Verify configuration: `redis-server --test-config`
4. Restore from backup if corruption suspected

**Recovery Validation:**
1. Test Redis connectivity: `redis-cli ping`
2. Verify Django cache: `python manage.py health_check --component redis`
3. Check application functionality: Test login and key features
4. Monitor for 30 minutes to ensure stability

### **Playbook 2: Redis High Memory Usage**

**Severity:** 🟡 **HIGH** - Performance degradation risk

**Assessment (0-2 minutes):**
1. Check current memory: `python manage.py optimize_redis_memory --check-only`
2. Check fragmentation: Redis dashboard `/admin/redis/dashboard/`
3. Identify memory growth pattern: Check last 24h trends

**Mitigation (2-10 minutes):**
1. Trigger memory optimization: `python manage.py optimize_redis_memory --force`
2. Check for memory leaks: Review slow log and client connections
3. Temporary TTL reduction: Reduce cache timeouts if needed

**Long-term Resolution:**
1. Analyze cache usage patterns
2. Optimize data structures and TTL settings
3. Plan memory capacity increase if growth is legitimate

### **Playbook 3: Sentinel Failover Event**

**Severity:** 🟡 **HIGH** - Automatic recovery expected

**Immediate Assessment (0-2 minutes):**
1. Check Sentinel status: `python manage.py sentinel_admin --status`
2. Verify new master: `python manage.py sentinel_admin --masters`
3. Check application connectivity: Test key application functions

**Validation (2-10 minutes):**
1. Verify all replicas reconnected: `python manage.py sentinel_admin --replicas`
2. Check replication lag: Monitor replica sync status
3. Test write operations: Verify data consistency

**Follow-up Actions:**
1. Investigate cause of original master failure
2. Document incident and lessons learned
3. Review failover timing and optimize if needed
4. Plan maintenance for failed master recovery

---

## 🛠️ **Configuration Management**

### **Environment-Specific Configurations**

**Development Environment:**
- Single Redis instance (no HA)
- Minimal security (local development)
- Verbose logging for debugging
- Smaller memory limits

**Staging Environment:**
- Sentinel cluster (3 nodes)
- Production-like security
- Performance testing enabled
- Full monitoring and alerting

**Production Environment:**
- Sentinel cluster (3+ nodes)
- Maximum security hardening
- Performance optimization
- Full backup and monitoring

### **Configuration Templates Location**

```
config/redis/
├── redis-production.conf      # Standalone production config
├── redis-development.conf     # Standalone development config
├── redis.env.template         # Environment variables template
├── sentinel/
│   ├── redis-master.conf      # HA master configuration
│   ├── redis-replica.conf     # HA replica configuration
│   ├── redis-sentinel-1.conf  # Sentinel node 1
│   ├── redis-sentinel-2.conf  # Sentinel node 2
│   └── redis-sentinel-3.conf  # Sentinel node 3
```

### **Setup Scripts**

```bash
# Standalone Redis setup
./scripts/setup_redis_secure.sh [development|production]

# High Availability Sentinel setup
./scripts/setup_redis_sentinel.sh

# Cluster management
./scripts/sentinel_cluster.sh [start|stop|restart|status|health]

# Failover testing
./scripts/test_sentinel_failover.sh
```

---

## 📊 **Performance Tuning Guide**

### **Memory Optimization**

**1. Memory Configuration:**
```conf
# Production settings
maxmemory 2gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Enable memory defragmentation
activedefrag yes
active-defrag-threshold-lower 10
```

**2. Data Structure Optimization:**
```conf
# Hash optimization for small objects
hash-max-ziplist-entries 512
hash-max-ziplist-value 64

# List compression
list-max-ziplist-size -2
list-compress-depth 1

# Set optimization for integers
set-max-intset-entries 512
```

**3. Cache Strategy Optimization:**
```python
# Use appropriate TTL for different data types
CACHE_TIMEOUTS = {
    'user_sessions': 7200,      # 2 hours
    'dropdown_data': 3600,      # 1 hour
    'dashboard_metrics': 300,   # 5 minutes
    'real_time_data': 60,       # 1 minute
}

# Enable compression for large payloads
REDIS_COMPRESSION_MIN_SIZE = 1024  # 1KB threshold
```

### **Connection Pool Optimization**

**Development:**
```python
CONNECTION_POOL_KWARGS = {
    'max_connections': 20,
    'retry_on_timeout': True,
    'health_check_interval': 60,
}
```

**Production:**
```python
CONNECTION_POOL_KWARGS = {
    'max_connections': 100,
    'retry_on_timeout': True,
    'health_check_interval': 30,
    'socket_keepalive': True,
    'socket_keepalive_options': {
        'TCP_KEEPIDLE': 1,
        'TCP_KEEPINTVL': 3,
        'TCP_KEEPCNT': 5,
    }
}
```

---

## 🔄 **Operational Procedures**

### **Daily Operations Checklist**

**Morning Checks (5 minutes):**
- [ ] Check Redis dashboard: `/admin/redis/dashboard/`
- [ ] Verify overnight backup completion
- [ ] Review any performance alerts
- [ ] Check memory usage trends

**Evening Review (10 minutes):**
- [ ] Review daily performance summary
- [ ] Check backup verification status
- [ ] Plan any maintenance activities
- [ ] Update capacity planning data

### **Weekly Maintenance (30 minutes):**

**Every Monday:**
- [ ] Review weekly performance trends
- [ ] Analyze capacity growth patterns
- [ ] Clean up old backups (automated)
- [ ] Review and acknowledge alerts
- [ ] Plan scaling activities if needed

**Every Thursday:**
- [ ] Test backup restoration procedures
- [ ] Review security configurations
- [ ] Update documentation if needed
- [ ] Validate monitoring and alerting

### **Monthly Reviews (60 minutes):**

- [ ] Comprehensive performance review
- [ ] Capacity planning assessment
- [ ] Security audit and updates
- [ ] Backup strategy review
- [ ] Disaster recovery testing
- [ ] Team training updates

---

## 🎓 **Training & Knowledge Transfer**

### **New Team Member Onboarding**

**Day 1: Basic Redis Knowledge**
- Redis fundamentals and data structures
- IntelliWiz Redis architecture overview
- Performance dashboard walkthrough
- Basic troubleshooting procedures

**Week 1: Operational Procedures**
- Health monitoring and alerting
- Backup and recovery procedures
- Performance optimization techniques
- Security best practices

**Week 2: Advanced Operations**
- Sentinel cluster management
- Incident response procedures
- Capacity planning and scaling
- Troubleshooting complex issues

### **Skill Development Path**

**Beginner (0-3 months):**
- Understand Redis basic operations
- Monitor performance dashboard
- Execute standard procedures
- Escalate complex issues

**Intermediate (3-12 months):**
- Perform routine maintenance
- Troubleshoot common issues
- Optimize performance settings
- Plan capacity improvements

**Advanced (12+ months):**
- Design Redis architecture changes
- Lead incident response efforts
- Mentor junior team members
- Contribute to strategy and planning

---

## 📞 **Escalation Procedures**

### **Issue Severity Classification**

**🔴 CRITICAL (Immediate Response - 0-15 minutes):**
- Complete Redis outage
- Data corruption detected
- Security breach suspected
- Backup restoration required

**🟡 HIGH (Response within 1 hour):**
- Performance degradation >50%
- Memory usage >90%
- Sentinel failover events
- Backup failures

**🟢 MEDIUM (Response within 4 hours):**
- Cache hit ratio <80%
- Memory fragmentation >2.0
- Connection pool issues
- Configuration optimization needed

### **Contact Information**

**On-Call Rotation:**
- Primary: DevOps Team Lead
- Secondary: Senior Backend Developer
- Escalation: CTO/Technical Director

**External Support:**
- Redis Enterprise Support (if applicable)
- Cloud Provider Support (AWS/Azure/GCP)
- System Integrator Support

---

## 📚 **Additional Resources**

### **Documentation Links**

- **Redis Official Documentation**: https://redis.io/documentation
- **Django Redis Integration**: https://django-redis.readthedocs.io/
- **Celery Redis Broker**: https://docs.celeryproject.org/en/stable/getting-started/brokers/redis.html
- **Redis Sentinel Guide**: https://redis.io/topics/sentinel

### **Internal Documentation**

- `CLAUDE.md`: Project development guidelines
- `docs/PERFORMANCE_OPTIMIZATION_GUIDE.md`: General performance guidance
- `docs/security/`: Security configuration guides
- `apps/core/health_checks/`: Health check implementation
- `apps/core/services/`: Redis service implementations

### **Monitoring and Alerting**

- **Performance Dashboard**: `/admin/redis/dashboard/`
- **Health Check Endpoint**: `/health/redis/`
- **Metrics API**: `/admin/redis/api/metrics/`
- **Celery Monitoring**: `/admin/celery/`

---

## ✅ **Implementation Completion Checklist**

### **Phase 1: Security & Performance ✅**
- [x] Redis configuration hardening
- [x] Connection pool optimization
- [x] Memory management and monitoring
- [x] Enhanced health checks

### **Phase 2: High Availability ✅**
- [x] Backup and persistence system
- [x] Sentinel cluster configuration
- [x] Automatic failover setup
- [x] Disaster recovery procedures

### **Phase 3: Monitoring & Operations ✅**
- [x] Performance monitoring dashboard
- [x] Real-time metrics collection
- [x] Automated alerting system
- [x] Capacity planning tools

### **Phase 4: Documentation & Training ✅**
- [x] Comprehensive operations guide
- [x] Troubleshooting procedures
- [x] Incident response playbooks
- [x] Team training materials

---

**🎉 Redis Enterprise Implementation Complete!**

This Redis infrastructure now provides **enterprise-grade reliability, security, and performance** for the IntelliWiz Django platform with **comprehensive operational procedures** and **automated monitoring**.

**Total Implementation Impact:**
- **Security**: Critical vulnerabilities eliminated
- **Availability**: Single point of failure eliminated
- **Performance**: Comprehensive monitoring and optimization
- **Operations**: Full team enablement and procedures

For questions or support, refer to the troubleshooting guides above or contact the DevOps team.