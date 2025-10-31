"""
Job Managers Module - Backward Compatibility Layer.

Provides Django custom managers for Job, Jobneed, and JobneedDetails models.

Migration Date: 2025-10-10
Original File: apps/activity/managers/job_manager.py (1,782 lines)
New Structure: 3 domain-focused manager files

Before Refactoring:
- 1 monolithic file (1,782 lines - 11.9x over limit)
- 3 Manager classes (69 total methods)
- Mixed concerns (Job, Jobneed, JobneedDetails in one file)

After Refactoring:
- 3 focused files (one per manager class)
- Clear separation of concerns
- Easier navigation and testing
- Maintained backward compatibility

Usage:
    # Old import (still works via this __init__.py):
    from apps.activity.managers.job_manager import JobManager

    # New import (recommended):
    from apps.activity.managers.job import JobManager

    # Direct import (most explicit):
    from apps.activity.managers.job.job_manager import JobManager

Model Registration:
    # In apps/activity/models/job_model.py:
    from apps.activity.managers.job import JobManager

    class Job(BaseModel):
        objects = JobManager()  # Registers custom manager
"""

from .job_manager import JobManager
from .jobneed_manager import JobneedManager
from .jobneed_details_manager import JobneedDetailsManager

__all__ = [
    'JobManager',
    'JobneedManager',
    'JobneedDetailsManager',
]
