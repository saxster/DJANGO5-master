"""
Task Model Shim
===============

Provides a lightweight proxy model over ``Jobneed`` so newer API layers that
expect ``apps.activity.models.task`` continue to import cleanly. The existing
database schema already stores task/tour executions inside the ``jobneed``
table, so this proxy simply exposes friendlier attribute names while keeping
storage untouched.

The proxy intentionally keeps logic minimal—callers should continue to use the
established ``Jobneed`` fields for persistence. This shim only exists to avoid
import errors during the V1→V2 transition.
"""

from __future__ import annotations

from apps.activity.models.job import Jobneed


class Task(Jobneed):
    """
    Thin proxy over ``Jobneed`` for backward compatibility.

    No schema changes or new tables are introduced; Django treats this as a
    proxy so migrations remain unaffected.
    """

    class Meta:
        proxy = True
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    # Convenience accessors used by new serializers/viewsets. They map the
    # expected V2 attribute names onto the existing schema so AttributeErrors
    # are avoided even if the richer contract is not fully implemented yet.
    @property
    def title(self) -> str:
        return getattr(self, "jobdesc", "")

    @title.setter
    def title(self, value: str) -> None:
        self.jobdesc = value

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


__all__ = ['Task']
