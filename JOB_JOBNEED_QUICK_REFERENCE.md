# Job → Jobneed → JobneedDetails Quick Reference

**Last Updated**: October 3, 2025
**For**: Developers, Android Team, Code Reviewers

---

## 🎯 **What You Need to Know (30 Second Version)**

1. **Job** = Template (recurring work definition)
2. **Jobneed** = Instance (one execution of that work)
3. **JobneedDetails** = Checklist (questions/answers for that execution)
4. Job has **1-to-many** with Jobneed (NOT 1-to-1)
5. Use `Q(parent__isnull=True) | Q(parent_id=1)` for root queries

---

## 🔧 **Common Operations**

### **Get Latest Jobneed for a Job**

```python
# Use manager helper (preferred)
latest = Jobneed.objects.latest_for_job(job_id=123)

# Manual (not recommended)
latest = Jobneed.objects.filter(job_id=123).order_by('-plandatetime').first()
```

### **Get Execution History**

```python
# Get last 10 executions
history = Jobneed.objects.history_for_job(job_id=123, limit=10)

# Get last 30 executions
history = Jobneed.objects.history_for_job(job_id=123, limit=30)
```

### **Batch Query for GraphQL**

```python
# Get latest jobneed for multiple jobs (efficient)
current_map = Jobneed.objects.current_for_jobs([1, 2, 3, 4, 5])
# Returns: {1: Jobneed(...), 2: Jobneed(...), 3: None, ...}
```

### **Query Root Jobs/Jobneeds**

```python
# CORRECT: Finds both NULL and sentinel (id=1) parents
root_jobs = Job.objects.filter(
    Q(parent__isnull=True) | Q(parent_id=1),
    identifier='TASK'
).exclude(jobname='NONE')

# WRONG: Only finds NULL parents (misses legacy data)
root_jobs = Job.objects.filter(parent__isnull=True)  # ❌ Incomplete

# WRONG: Only finds sentinel parents (misses modern data)
root_jobs = Job.objects.filter(parent_id=1)  # ❌ Incomplete
```

---

## 🔌 **GraphQL Queries**

### **Get Job with Latest Execution**

```graphql
query {
  job(id: 123) {
    id
    jobname
    jobneed {  # Latest execution
      id
      jobstatus
      plandatetime
    }
  }
}
```

### **Get Job with Execution History**

```graphql
query {
  job(id: 123) {
    jobname
    jobneeds(limit: 20) {  # Last 20 executions
      id
      plandatetime
      jobstatus
      starttime
      endtime
    }
  }
}
```

### **Get Jobneed with Checklist**

```graphql
query {
  job(id: 123) {
    jobneed {
      id
      jobdesc
      details {  # Checklist items
        seqno
        question { quesname }
        answer
        ismandatory
      }
    }
  }
}
```

---

## ✅ **Dos and Don'ts**

### **✅ DO**

- ✅ Use `Jobneed` (lowercase 'n') in new code
- ✅ Use `Q(parent__isnull=True) | Q(parent_id=1)` for root queries
- ✅ Use manager helpers (`latest_for_job`, `history_for_job`)
- ✅ Order `JobneedDetails` by `seqno`
- ✅ Use DataLoaders for GraphQL batch queries
- ✅ Handle null case when `job.jobneed` is None

### **❌ DON'T**

- ❌ Use `JobNeed` (uppercase 'N') in new code (deprecated)
- ❌ Query with only `parent_id=1` (misses NULL parents)
- ❌ Query with only `parent__isnull=True` (misses legacy data)
- ❌ Use `Job.jobneed_details` in GraphQL (removed field)
- ❌ Create duplicate (jobneed, question) (constraint violation)
- ❌ Create duplicate (jobneed, seqno) (constraint violation)

---

## 🐛 **Troubleshooting**

### **Import Error: "cannot import name 'JobNeed'"**

**Solution**: Use `Jobneed` (lowercase 'n') or update imports
```python
# Old (will work via alias)
from apps.activity.models import JobNeed

# New (preferred)
from apps.activity.models import Jobneed
```

### **GraphQL Error: "Field 'jobneed_details' doesn't exist"**

**Solution**: Update query to use `jobneed` (singular)
```graphql
# Old (broken)
job { jobneed_details { id } }

# New (correct)
job { jobneed { id } }
```

### **IntegrityError: "jobneeddetails_jobneed_question_uk"**

**Solution**: Checklist already has this question
```python
# Check before creating
existing = JobneedDetails.objects.filter(
    jobneed_id=123,
    question_id=456
).exists()

if not existing:
    JobneedDetails.objects.create(...)
```

### **Query Returns Too Many/Few Results**

**Solution**: Use unified parent query
```python
# Check your parent filter
Q(parent__isnull=True) | Q(parent_id=1)  # ✅ Correct
```

---

## 📖 **Full Documentation Links**

- **Domain Model**: `apps/activity/models/job_model.py` (docstring)
- **Service Architecture**: `apps/activity/services/README_SERVICE_LAYERS.md`
- **Android API Contract**: `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md`
- **Implementation Summary**: `JOB_JOBNEED_REFACTORING_COMPLETE.md`

---

## 🧪 **Testing Quick Reference**

```bash
# Run all Job/Jobneed tests
pytest apps/activity/tests/test_job* apps/api/tests/test_job* -v

# Run GraphQL tests only
pytest apps/api/tests/test_job_jobneed_graphql_relationships.py -v

# Run constraint tests
pytest apps/activity/tests/test_jobneeddetails_constraints.py -v

# Run with coverage
pytest apps/activity/tests/ --cov=apps.activity.models.job_model --cov-report=term
```

---

## 💡 **Code Examples**

### **Example 1: Get Today's Tasks**

```python
from datetime import date
from django.db.models import Q

today = date.today()

# Get all scheduled tasks for today (root level only)
tasks = Jobneed.objects.filter(
    Q(parent__isnull=True) | Q(parent_id=1),  # Root jobneeds
    plandatetime__date=today,
    identifier='TASK',
    jobstatus='ASSIGNED'
).select_related('job', 'people', 'bu')

for task in tasks:
    print(f"Task: {task.jobdesc}")
    print(f"Template: {task.job.jobname}")
    print(f"Assigned to: {task.people.peoplename}")
```

### **Example 2: Show Execution History**

```python
# Get last 30 executions for a job
job_id = 123
history = Jobneed.objects.history_for_job(job_id, limit=30)

for execution in history:
    status_icon = "✅" if execution.jobstatus == "COMPLETED" else "⏳"
    print(f"{status_icon} {execution.plandatetime}: {execution.jobstatus}")
```

### **Example 3: Get Checklist with Answers**

```python
# Get jobneed with all checklist items
jobneed = Jobneed.objects.select_related('job').get(id=1003)

details = JobneedDetails.objects.filter(
    jobneed=jobneed
).select_related('question').order_by('seqno')

for item in details:
    mandatory = "* " if item.ismandatory else "  "
    answer = item.answer or "(not answered)"
    print(f"{mandatory}{item.seqno}. {item.question.quesname}: {answer}")
```

---

## 🔍 **Verification Commands**

```bash
# Verify constraints exist
python manage.py dbshell
\d jobneeddetails;  # Should show 2 unique constraints

# Verify no duplicates
python manage.py shell
from apps.activity.models import JobneedDetails
from django.db.models import Count

duplicates = JobneedDetails.objects.values('jobneed', 'question').annotate(
    count=Count('id')
).filter(count__gt=1)

print(f"Duplicate questions: {duplicates.count()}")  # Should be 0

# Verify imports work
python manage.py shell
from apps.activity.models import Jobneed, JobNeed  # Both should work
assert Jobneed is JobNeed  # Should be True
```

---

## ⚡ **Performance Tips**

1. **Use batch queries for multiple jobs**:
   ```python
   # Bad (N+1)
   for job_id in job_ids:
       jobneed = Jobneed.objects.latest_for_job(job_id)

   # Good (2 queries total)
   current_map = Jobneed.objects.current_for_jobs(job_ids)
   for job_id in job_ids:
       jobneed = current_map[job_id]
   ```

2. **Always use select_related for FKs**:
   ```python
   # Bad
   jobneed = Jobneed.objects.get(id=123)
   print(jobneed.job.jobname)  # Extra query!

   # Good
   jobneed = Jobneed.objects.select_related('job').get(id=123)
   print(jobneed.job.jobname)  # No extra query
   ```

3. **Order details by seqno in Python, not SQL**:
   ```python
   # If queryset already fetched
   details = list(details_queryset)
   details.sort(key=lambda d: d.seqno)  # Python sort is fast

   # If not yet fetched
   details = JobneedDetails.objects.filter(...).order_by('seqno')  # SQL sort
   ```

---

**Quick Reference Version**: 1.0
**For Questions**: See `JOB_JOBNEED_REFACTORING_COMPLETE.md`
