# Job → Jobneed → JobneedDetails Deployment Runbook

**Deployment Date**: TBD (Week of October 7, 2025)
**Owner**: Backend Team
**Reviewer**: Tech Lead + Android Team Lead

---

## ⏱️ **Timeline Overview**

| Week | Phase | Owner | Deliverable |
|------|-------|-------|-------------|
| Week 1 (Oct 3-10) | Pre-deployment validation | Backend | Tests pass, docs complete |
| Week 2 (Oct 10-17) | Staging deployment | Backend | Staging live, Android testing |
| Week 3 (Oct 17-24) | Android integration | Android | App updated, tested |
| Week 4 (Oct 24-31) | Production rollout | Backend + Android | Production deployment |

---

## 🚦 **PRE-DEPLOYMENT CHECKLIST**

### **Step 1: Code Validation**

- [ ] All files committed to git
- [ ] Code review complete
- [ ] `.claude/rules.md` compliance verified
- [ ] No syntax errors: `python -m py_compile apps/activity/models/job_model.py`

### **Step 2: Test Execution**

```bash
# Run all new tests
pytest apps/activity/tests/test_jobneeddetails_constraints.py -v
pytest apps/api/tests/test_job_jobneed_graphql_relationships.py -v
pytest apps/activity/tests/test_parent_handling_unified.py -v
pytest apps/activity/tests/test_naming_compatibility.py -v

# Expected: ALL PASS (43 tests)
```

- [ ] Constraint tests pass (8/8)
- [ ] GraphQL relationship tests pass (12/12)
- [ ] Parent handling tests pass (15/15)
- [ ] Naming compatibility tests pass (8/8)

### **Step 3: Data Analysis (Staging)**

```bash
# Connect to staging database
python manage.py dbshell

-- Check for duplicate JobneedDetails
SELECT jobneed_id, question_id, COUNT(*) as count
FROM jobneeddetails
GROUP BY jobneed_id, question_id
HAVING COUNT(*) > 1;

-- Check for duplicate seqno
SELECT jobneed_id, seqno, COUNT(*) as count
FROM jobneeddetails
GROUP BY jobneed_id, seqno
HAVING COUNT(*) > 1;

-- Expected: 0 rows (no duplicates)
```

- [ ] No duplicate (jobneed, question) pairs
- [ ] No duplicate (jobneed, seqno) pairs

### **Step 4: Run Cleanup Script (If Duplicates Found)**

```bash
# Dry run first
python scripts/cleanup_jobneeddetails_duplicates.py --dry-run

# Review output, then execute
python scripts/cleanup_jobneeddetails_duplicates.py --execute
```

- [ ] Cleanup script executed successfully
- [ ] Duplicates removed (if any existed)
- [ ] Data integrity verified

---

## 🚀 **STAGING DEPLOYMENT**

### **Step 1: Apply Migration**

```bash
# Activate virtual environment
source venv/bin/activate

# Check pending migrations
python manage.py showmigrations activity

# Apply migration
python manage.py migrate activity 0014_add_jobneeddetails_constraints

# Expected output:
# Running migrations:
#   Applying activity.0014_add_jobneeddetails_constraints... OK
```

- [ ] Migration applied successfully
- [ ] No errors in migration output

### **Step 2: Verify Constraints**

```bash
# Check constraints exist in database
python manage.py dbshell

\d jobneeddetails;

-- Should show:
-- "jobneeddetails_jobneed_question_uk" UNIQUE, btree (jobneed_id, question_id)
-- "jobneeddetails_jobneed_seqno_uk" UNIQUE, btree (jobneed_id, seqno)
```

- [ ] `jobneeddetails_jobneed_question_uk` constraint exists
- [ ] `jobneeddetails_jobneed_seqno_uk` constraint exists

### **Step 3: Test Constraint Enforcement**

```bash
# Run constraint violation tests
pytest apps/activity/tests/test_jobneeddetails_constraints.py::JobneedDetailsConstraintsTest::test_unique_jobneed_question_constraint_violation -v

# Expected: PASS (IntegrityError raised as expected)
```

- [ ] Constraint tests pass
- [ ] IntegrityError raised for duplicates

### **Step 4: Deploy Code Changes**

```bash
# Pull latest code
git pull origin main

# Restart application server
sudo systemctl restart gunicorn

# Restart Celery workers
./scripts/celery_workers.sh restart

# Check services
sudo systemctl status gunicorn
./scripts/celery_workers.sh health
```

- [ ] Application server restarted
- [ ] Celery workers restarted
- [ ] All services healthy

### **Step 5: Verify GraphQL Schema**

```bash
# Access GraphiQL
open https://staging-api.example.com/graphiql/

# Test query:
query {
  job(id: 123) {
    jobneed { id jobstatus }     # NEW field
    jobneeds(limit: 5) { id }    # NEW field
  }
}

# Expected: Success (no errors)
```

- [ ] GraphQL endpoint accessible
- [ ] New fields return data
- [ ] No schema errors

---

## 📱 **ANDROID TEAM COORDINATION**

### **Step 1: Share Documentation**

- [ ] Send `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md` to Android team
- [ ] Schedule kickoff meeting
- [ ] Review breaking changes together
- [ ] Agree on timeline

### **Step 2: Provide Testing Environment**

```
Staging Environment:
- GraphQL: https://staging-api.example.com/graphql/
- GraphiQL: https://staging-api.example.com/graphiql/
- REST API: https://staging-api.example.com/api/v1/
- Swagger: https://staging-api.example.com/api/docs/
```

- [ ] Staging credentials shared
- [ ] Android team can access GraphiQL
- [ ] Sample queries provided

### **Step 3: Support During Migration**

- [ ] Daily sync meetings (Oct 10-17)
- [ ] Slack channel for questions
- [ ] Backend engineer available for pairing

---

## 🧪 **INTEGRATION TESTING**

### **Backend Integration Tests**

```bash
# Test parent handling across all modules
pytest apps/activity/tests/test_parent_handling_unified.py -v

# Test GraphQL end-to-end
pytest apps/api/tests/test_job_jobneed_graphql_relationships.py -v

# Test naming compatibility
pytest apps/activity/tests/test_naming_compatibility.py -v
```

- [ ] All integration tests pass
- [ ] No regressions detected

### **Android Integration Tests**

**Provided by Android Team**:
- [ ] GraphQL queries updated
- [ ] Kotlin models updated
- [ ] Unit tests pass (100%)
- [ ] UI tests pass (critical flows)
- [ ] Offline sync tested
- [ ] Performance benchmarks met (< 500ms)

---

## 📊 **MONITORING & VALIDATION**

### **Application Monitoring**

```bash
# Monitor GraphQL error rates
tail -f /var/log/intelliwiz/graphql.log | grep ERROR

# Monitor database errors
tail -f /var/log/intelliwiz/django.log | grep "jobneeddetails_jobneed"

# Monitor API response times
curl -w "@curl-format.txt" -s "https://staging-api.example.com/graphql/" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { job(id: 123) { jobneed { id } } }"}'
```

**Expected Metrics**:
- GraphQL error rate: < 0.1%
- p95 latency: < 50ms
- Constraint violations: 0
- Import errors: 0

### **Database Monitoring**

```sql
-- Monitor constraint violations (should be 0)
SELECT COUNT(*) FROM pg_stat_user_tables
WHERE schemaname = 'public' AND relname = 'jobneeddetails';

-- Check for slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE query LIKE '%jobneeddetails%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

- [ ] No constraint violations logged
- [ ] Query performance acceptable (< 50ms)

---

## 🔥 **ROLLBACK PLAN**

### **If Critical Issues Arise**

#### **Scenario 1: Constraint Migration Fails**

```bash
# Rollback migration
python manage.py migrate activity 0013_add_spatial_indexes

# Re-run cleanup script
python scripts/cleanup_jobneeddetails_duplicates.py --execute

# Retry migration
python manage.py migrate activity 0014_add_jobneeddetails_constraints
```

#### **Scenario 2: GraphQL Schema Breaks Android**

**Option A: Keep old field temporarily**
```python
# In enhanced_schema.py, add back:
jobneed_details = graphene.Field(lambda: JobneedType,
    deprecation_reason="Use 'jobneed' field instead")

def resolve_jobneed_details(self, info):
    """Deprecated: Use jobneed field."""
    return self.resolve_jobneed(info)
```

**Option B: Rollback GraphQL changes**
```bash
git revert <commit-hash>
sudo systemctl restart gunicorn
```

#### **Scenario 3: Performance Regression**

```bash
# Add database index if queries slow
python manage.py dbshell

CREATE INDEX idx_jobneed_job_plandate
ON jobneed(job_id, plandatetime DESC);
```

---

## ✅ **POST-DEPLOYMENT VERIFICATION**

### **Step 1: Smoke Tests (First 1 Hour)**

```bash
# Test critical flows
curl -X POST https://api.example.com/graphql/ \
  -H "Content-Type: application/json" \
  -d '{"query": "query { job(id: 123) { jobneed { id } } }"}'

# Expected: {"data": {"job": {"jobneed": {"id": "1003"}}}}
```

- [ ] GraphQL queries succeed
- [ ] Latest jobneed returns correct data
- [ ] History queries return ordered results
- [ ] No 500 errors in logs

### **Step 2: Performance Verification (First 24 Hours)**

```bash
# Check response times
python scripts/monitor_api_performance.py --endpoint=/graphql/ --duration=1h

# Expected: p95 < 50ms, p99 < 100ms
```

- [ ] p95 latency < 50ms
- [ ] p99 latency < 100ms
- [ ] No slow query warnings
- [ ] No timeout errors

### **Step 3: Data Integrity Check (First Week)**

```bash
# Run weekly constraint check
python manage.py shell

from apps.activity.models import JobneedDetails
from django.db.models import Count

# Should remain 0 forever
duplicates = JobneedDetails.objects.values('jobneed', 'question').annotate(
    count=Count('id')
).filter(count__gt=1).count()

print(f"Duplicates found: {duplicates}")  # Expected: 0
```

- [ ] Zero duplicates found
- [ ] Constraint violations: 0
- [ ] Data integrity maintained

---

## 📞 **INCIDENT RESPONSE**

### **Severity Levels**

| Severity | Response Time | Actions |
|----------|--------------|---------|
| **P0 - Critical** | < 15 min | Page on-call, rollback if needed |
| **P1 - High** | < 1 hour | Investigate, hotfix if possible |
| **P2 - Medium** | < 4 hours | Schedule fix, document workaround |
| **P3 - Low** | Next sprint | Add to backlog |

### **Common Issues & Resolutions**

#### **Issue: Constraint violation errors in production**

**Symptoms**: IntegrityError logs with "jobneeddetails_jobneed_question_uk"

**Root Cause**: Application code creating duplicates

**Resolution**:
```python
# Add duplicate check before creation
existing = JobneedDetails.objects.filter(
    jobneed_id=jobneed_id,
    question_id=question_id
).exists()

if existing:
    # Update instead of create
    JobneedDetails.objects.filter(...).update(answer=new_answer)
else:
    JobneedDetails.objects.create(...)
```

#### **Issue: Android app crashes after deployment**

**Symptoms**: App crashes when loading task details

**Root Cause**: App using old `jobneed_details` field

**Resolution**:
1. Check Android app version (must be >= 2.0)
2. Verify query uses new field names
3. If urgent, add deprecated field back (Option A in rollback)

---

## 📋 **SUCCESS CRITERIA**

| Metric | Target | Verification |
|--------|--------|--------------|
| Migration success rate | 100% | Check `django_migrations` table |
| Constraint violations | 0 | Monitor logs for IntegrityError |
| GraphQL error rate | < 0.1% | Monitor Sentry/logs |
| Android app crashes | 0 | Monitor Crashlytics |
| p95 latency | < 50ms | Monitor APM |
| Import errors | 0 | No ImportError in logs |
| Duplicate data | 0 | Weekly constraint check |

---

## 🎯 **HANDOFF TO ANDROID TEAM**

### **Required Actions for Android**

1. **Read documentation**:
   - `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md`
   - `JOB_JOBNEED_QUICK_REFERENCE.md`

2. **Update GraphQL queries** (Week 2):
   - Replace `job.jobneed_details` → `job.jobneed`
   - Add `job.jobneeds` for history views
   - Add `jobneed.details` for checklist

3. **Update Kotlin models** (Week 2):
   - Add `jobneed: Jobneed?` to Job
   - Add `jobneeds: List<Jobneed>?` to Job
   - Add `details: List<JobneedDetails>?` to Jobneed
   - Add `job: Job?` to Jobneed

4. **Test on staging** (Week 3):
   - All critical flows tested
   - Performance benchmarks met
   - Offline sync validated

5. **Deploy to production** (Week 4):
   - Coordinate deployment time
   - Monitor for issues
   - Have rollback ready

---

## 📝 **DEPLOYMENT SCRIPT**

```bash
#!/bin/bash
# deploy_job_jobneed_refactoring.sh

set -e  # Exit on error

echo "=== Job → Jobneed Refactoring Deployment ==="
echo "Started: $(date)"

# Step 1: Backup database
echo "\n[1/7] Creating database backup..."
pg_dump intelliwiz_db > backup_pre_job_jobneed_$(date +%Y%m%d_%H%M%S).sql

# Step 2: Run cleanup script (dry-run)
echo "\n[2/7] Checking for duplicates..."
python scripts/cleanup_jobneeddetails_duplicates.py --dry-run

# Step 3: Clean duplicates (if any)
read -p "Found duplicates? Run cleanup? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "\n[3/7] Cleaning duplicates..."
    python scripts/cleanup_jobneeddetails_duplicates.py --execute
fi

# Step 4: Apply migration
echo "\n[4/7] Applying migration..."
python manage.py migrate activity 0014_add_jobneeddetails_constraints

# Step 5: Verify constraints
echo "\n[5/7] Verifying constraints..."
python manage.py dbshell << EOF
\d jobneeddetails;
\q
EOF

# Step 6: Run tests
echo "\n[6/7] Running tests..."
pytest apps/activity/tests/test_jobneeddetails_constraints.py -v

# Step 7: Restart services
echo "\n[7/7] Restarting services..."
sudo systemctl restart gunicorn
./scripts/celery_workers.sh restart

echo "\n✅ Deployment complete: $(date)"
echo "Monitor logs: tail -f /var/log/intelliwiz/django.log"
```

**Usage**:
```bash
chmod +x deploy_job_jobneed_refactoring.sh
./deploy_job_jobneed_refactoring.sh
```

---

## 🔍 **POST-DEPLOYMENT MONITORING**

### **First Hour**

```bash
# Watch application logs
tail -f /var/log/intelliwiz/django.log | grep -i "jobneed\|integrity\|constraint"

# Watch GraphQL errors
tail -f /var/log/intelliwiz/graphql.log | grep ERROR

# Monitor response times
watch -n 10 'curl -s -w "%{time_total}\n" -o /dev/null https://api.example.com/graphql/'
```

**Alert Thresholds**:
- Error rate > 1% → Page on-call
- Response time > 200ms → Investigate
- Constraint violations > 0 → Investigate immediately

### **First Day**

- [ ] Monitor Sentry for new errors
- [ ] Check Grafana dashboards
- [ ] Review database slow query log
- [ ] Verify no user complaints

### **First Week**

- [ ] Run full regression test suite
- [ ] Check database constraint violations (should be 0)
- [ ] Review Android app Crashlytics
- [ ] Conduct post-mortem if issues

---

## 📞 **CONTACT INFORMATION**

### **Escalation Path**

| Level | Role | Contact | Response Time |
|-------|------|---------|---------------|
| L1 | Backend On-Call | backend-oncall@example.com | 15 min |
| L2 | Backend Lead | backend-lead@example.com | 30 min |
| L3 | Tech Lead | tech-lead@example.com | 1 hour |

### **Team Contacts**

- **Backend Team**: backend-team@example.com
- **Android Team**: android-team@example.com
- **Database Team**: database-team@example.com
- **DevOps Team**: devops-team@example.com

---

## 🎯 **SIGN-OFF**

### **Pre-Deployment Sign-Off**

- [ ] **Backend Lead**: Code review approved
- [ ] **Tech Lead**: Architecture approved
- [ ] **Android Lead**: API contract reviewed
- [ ] **QA Lead**: Test plan approved
- [ ] **DevOps**: Deployment plan reviewed

### **Post-Deployment Sign-Off**

- [ ] **Backend Lead**: Deployment successful
- [ ] **Android Lead**: App working with new schema
- [ ] **QA Lead**: Regression tests pass
- [ ] **DevOps**: Monitoring in place

---

**Runbook Version**: 1.0
**Last Updated**: October 3, 2025
**Next Review**: After production deployment
