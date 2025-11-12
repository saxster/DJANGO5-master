"""
Answer Model Shim
=================

Operational V2 code often imports ``apps.activity.models.answer`` expecting a
dedicated answer entity. In the legacy schema, checklist responses live in
``JobneedDetails``. This proxy keeps that single source of truth while
ensuring modern imports do not fail during startup.
"""

from __future__ import annotations

from apps.activity.models.job import JobneedDetails


class Answer(JobneedDetails):
    """Proxy to expose JobneedDetails under the Answer alias."""

    class Meta:
        proxy = True
        verbose_name = "Answer"
        verbose_name_plural = "Answers"


__all__ = ['Answer']
