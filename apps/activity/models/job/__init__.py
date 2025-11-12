"""
Job Domain Models Package

Split from god file apps/activity/models/job_model.py (804 lines)
into focused modules following refactoring pattern.

Domain Model Hierarchy:
  Job (Template) → Jobneed (Instance) → JobneedDetails (Checklist)

## Module Structure:
- enums.py: All TextChoices enums (127 lines)
- job.py: Job model - work template/definition (147 lines)
- jobneed.py: Jobneed model - execution instance (145 lines)
- jobneed_details.py: JobneedDetails model - checklist items (136 lines)

## Backward Compatibility:
All imports from apps.activity.models.job_model remain valid:
  from apps.activity.models.job_model import Job, Jobneed, JobneedDetails
  from apps.activity.models import Job, Jobneed, JobneedDetails

Both continue to work via __init__.py exports.
"""

from .enums import (
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
from .job import Job, other_info, geojson_jobnjobneed
from .jobneed import Jobneed
from .jobneed_details import JobneedDetails

# Backward compatibility aliases (deprecated naming convention)
# DEPRECATED: Use Jobneed and JobneedDetails (lowercase 'n')
JobNeed = Jobneed
JobNeedDetails = JobneedDetails

__all__ = [
    # Models
    'Job',
    'Jobneed',
    'JobneedDetails',
    'other_info',
    'geojson_jobnjobneed',
    # Backward compatibility aliases
    'JobNeed',
    'JobNeedDetails',
    # Enums
    'JobIdentifier',
    'JobneedIdentifier',
    'Priority',
    'ScanType',
    'Frequency',
    'JobStatus',
    'JobType',
    'AnswerType',
    'AvptType',
]
