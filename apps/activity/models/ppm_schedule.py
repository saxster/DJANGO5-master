"""
PPM Schedule Model Shim
=======================

PPM templates live in the ``job`` table (identifier = ``PPM``). This proxy
model keeps API imports working without creating a new table during the
transition to V2 endpoints.
"""

from __future__ import annotations

from apps.activity.models.job import Job
from apps.activity.managers.job import JobManager


class PPMScheduleManager(JobManager):
    """Return only jobs that represent PPM schedules."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(identifier='PPM')


class PPMSchedule(Job):
    """Proxy model that surfaces PPM templates as dedicated objects."""

    objects = PPMScheduleManager()

    class Meta:
        proxy = True
        verbose_name = "PPM Schedule"
        verbose_name_plural = "PPM Schedules"


__all__ = ['PPMSchedule']
