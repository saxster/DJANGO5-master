# Activity Job Models - Quick Reference

**Last Updated**: November 5, 2025
**Refactoring**: Phase 2 Complete

---

## Import Paths (All Valid)

```python
# ✅ OLD WAY (still works, backward compatible)
from apps.activity.models.job_model import Job, Jobneed, JobneedDetails

# ✅ STANDARD WAY (recommended for existing code)
from apps.activity.models import Job, Jobneed, JobneedDetails

# ✅ NEW WAY (recommended for new code)
from apps.activity.models.job import Job, Jobneed, JobneedDetails

# ✅ ENUM IMPORTS (new capability)
from apps.activity.models.job import (
    JobIdentifier,
    JobneedIdentifier,
    Priority,
    ScanType,
    Frequency,
    JobStatus,
    JobType,
    AnswerType,
    AvptType,
)
```

---

## Module Structure

```
apps/activity/models/job/
├── __init__.py          - Exports for backward compatibility
├── enums.py            - All TextChoices enums (9 classes)
├── job.py              - Job model (work template)
├── jobneed.py          - Jobneed model (execution instance)
└── jobneed_details.py  - JobneedDetails model (checklist items)
```

---

## Model Relationships

```
Job (Template)
  └─ has many Jobneed (Instances)
       └─ has many JobneedDetails (Checklist Items)
```

**Example:**
```python
# Job: "Daily Pump Check" (template)
#   ├─ Jobneed: "2025-11-05 10:00" (instance 1)
#   │    ├─ JobneedDetails: Question 1
#   │    ├─ JobneedDetails: Question 2
#   │    └─ JobneedDetails: Question 3
#   ├─ Jobneed: "2025-11-06 10:00" (instance 2)
#   └─ Jobneed: "2025-11-07 10:00" (instance 3)
```

---

## Key Fields Reference

### Job Model (apps/activity/models/job/job.py)
```python
jobname          # CharField(200) - Job name
identifier       # CharField(100) - Job type (TASK, TOUR, PPM, etc.)
frequency        # CharField(55)  - Schedule frequency (DAILY, WEEKLY, etc.)
cron             # CharField(200) - Cron expression
qset             # FK QuestionSet - Question set for checklist
asset            # FK Asset - Asset to operate on
parent           # FK self - Parent job for hierarchical tours
priority         # CharField(100) - HIGH, MEDIUM, LOW
enable           # BooleanField - Active/inactive
```

### Jobneed Model (apps/activity/models/job/jobneed.py)
```python
job              # FK Job - Parent job template
jobstatus        # CharField(60) - ASSIGNED, INPROGRESS, COMPLETED, etc.
jobtype          # CharField(50) - SCHEDULE or ADHOC
plandatetime     # DateTimeField - Scheduled time
starttime        # DateTimeField - Actual start time
endtime          # DateTimeField - Actual end time
people           # FK People - Assigned person
gpslocation      # PointField - GPS coordinates
journeypath      # LineStringField - Path traveled
ticket           # FK Ticket - Related ticket
```

### JobneedDetails Model (apps/activity/models/job/jobneed_details.py)
```python
jobneed          # FK Jobneed - Parent jobneed
question         # FK Question - Question being answered
seqno            # SmallIntegerField - Display order
answer           # CharField(250) - Answer text
answertype       # CharField(50) - CHECKBOX, DATE, DROPDOWN, etc.
alerts           # BooleanField - Alert triggered
transcript       # TextField - Audio transcript
transcript_status # CharField(20) - PENDING, PROCESSING, COMPLETED, FAILED
```

---

## Enum Reference

### JobIdentifier (Job types)
```python
TASK, TICKET, INTERNALTOUR, EXTERNALTOUR, PPM, OTHER,
SITEREPORT, INCIDENTREPORT, ASSETLOG, ASSETMAINTENANCE, GEOFENCE
```

### JobneedIdentifier (Jobneed types, superset of Job)
```python
All JobIdentifier values, plus:
ASSETAUDIT, POSTING_ORDER, SITESURVEY
```

### Priority
```python
HIGH, MEDIUM, LOW
```

### ScanType
```python
NONE, QR, NFC, SKIP, ENTERED
```

### Frequency
```python
NONE, DAILY, WEEKLY, MONTHLY, BIMONTHLY, QUARTERLY,
HALFYEARLY, YEARLY, FORTNIGHTLY
```

### JobStatus (State machine)
```python
ASSIGNED → INPROGRESS → COMPLETED → AUTOCLOSED
PARTIALLYCOMPLETED, MAINTENANCE, STANDBY, WORKING
```

### JobType
```python
SCHEDULE, ADHOC
```

### AnswerType
```python
CHECKBOX, DATE, DROPDOWN, EMAILID, MULTILINE, NUMERIC,
SIGNATURE, SINGLELINE, TIME, RATING, BACKCAMERA, FRONTCAMERA,
PEOPLELIST, SITELIST, NONE, METERREADING, MULTISELECT
```

### AvptType (Attachment types)
```python
BACKCAMPIC, FRONTCAMPIC, AUDIO, VIDEO, NONE
```

---

## Common Queries

### Get all active jobs
```python
from apps.activity.models import Job

active_jobs = Job.objects.filter(enable=True)
```

### Get jobneeds for a specific job
```python
job = Job.objects.get(id=1)
jobneeds = job.jobs.all()  # Related name: 'jobs'
```

### Get in-progress jobneeds
```python
from apps.activity.models import Jobneed

in_progress = Jobneed.objects.filter(
    jobstatus=Jobneed.JobStatus.INPROGRESS
)
```

### Get jobneed details with answers
```python
jobneed = Jobneed.objects.get(id=1)
details = jobneed.jobneeddetails_set.all()

# With related data
details = jobneed.jobneeddetails_set.select_related('question').all()
```

### Create adhoc jobneed
```python
from apps.activity.models import Jobneed

jobneed = Jobneed.objects.create(
    jobdesc="Emergency inspection",
    jobtype=Jobneed.JobType.ADHOC,
    priority=Jobneed.Priority.HIGH,
    tenant=current_tenant,
    # ... other fields
)
```

---

## State Machine (Jobneed)

```
ASSIGNED
   ↓
INPROGRESS (worker starts)
   ↓
COMPLETED (all details answered)
   ↓
AUTOCLOSED (reviewed/approved)
```

**Branch states:**
- `PARTIALLYCOMPLETED` - Some details answered
- `MAINTENANCE` - Under maintenance
- `STANDBY` - On hold
- `WORKING` - Active work in progress

---

## Backward Compatibility

### ✅ Naming Aliases
```python
# Old naming (uppercase N) - DEPRECATED but still works
from apps.activity.models.job_model import JobNeed, JobNeedDetails

# New naming (lowercase n) - RECOMMENDED
from apps.activity.models.job import Jobneed, JobneedDetails
```

### ✅ All Import Paths Valid
- `from apps.activity.models.job_model import ...` ✅
- `from apps.activity.models import ...` ✅
- `from apps.activity.models.job import ...` ✅

---

## File Locations

### Production Code
```
apps/activity/models/job/
├── __init__.py          (62 lines)
├── enums.py            (131 lines)
├── job.py              (122 lines)
├── jobneed.py          (131 lines)
└── jobneed_details.py  (135 lines)
```

### Deprecated (backup, will be deleted)
```
apps/activity/models/
├── job_model.py              (804 lines, ORIGINAL - untouched)
└── job_model_deprecated.py   (813 lines, BACKUP with warning)
```

---

## Testing

### Run job model tests
```bash
pytest apps/activity/tests/test_models.py -v
pytest apps/activity/tests/ -k job -v
```

### Import validation
```bash
python -c "from apps.activity.models.job import Job, Jobneed, JobneedDetails"
```

---

## Need Help?

- **Full details**: See `ACTIVITY_MODELS_JOB_REFACTORING_COMPLETE.md`
- **Architecture**: See `docs/architecture/SYSTEM_ARCHITECTURE.md`
- **Refactoring patterns**: See `docs/architecture/REFACTORING_PATTERNS.md`

---

**Quick Ref Version**: 1.0
**Agent**: Agent 6 - Activity Models Refactor
**Status**: Production Ready ✅
