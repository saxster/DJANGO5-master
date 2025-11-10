"""
Tour Model Shim
===============

The legacy schema models patrols/tours as ``Jobneed`` rows with identifiers
``INTERNALTOUR``/``EXTERNALTOUR``. Modernized APIs, however, import
``apps.activity.models.tour`` expecting a dedicated model. To preserve
compatibility without new migrations, we expose a proxy model that simply
reuses the existing ``jobneed`` table.
"""

from __future__ import annotations

from apps.activity.models.job import Jobneed
from apps.activity.managers.job import JobneedManager


class TourManager(JobneedManager):
    """Filters Jobneeds down to the tour identifiers."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'])


class Tour(Jobneed):
    """Proxy model exposing tours without duplicating schema."""

    objects = TourManager()

    class Meta:
        proxy = True
        verbose_name = "Tour"
        verbose_name_plural = "Tours"

    @property
    def status(self) -> str:
        return getattr(self, "jobstatus", "")

    @status.setter
    def status(self, value: str) -> None:
        self.jobstatus = value

    @property
    def assigned_to_id(self) -> int | None:
        return getattr(self, "people_id", None)

    @property
    def assigned_to(self):
        return getattr(self, "people", None)

    @property
    def scheduled_date(self):
        return getattr(self, "plandatetime", None)


__all__ = ['Tour']
