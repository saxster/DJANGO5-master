"""Context filter helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from django.core.exceptions import ValidationError

from .constants import CalendarContextType
from .types import CalendarContextFilter


def build_context_filter(
    *,
    context_type: Optional[CalendarContextType],
    context_id: Optional[int],
    user_id: int,
    default_client_id: Optional[int],
    default_site_id: Optional[int],
) -> CalendarContextFilter:
    """Resolve the effective context filter for downstream providers."""

    current = CalendarContextFilter(
        people_id=user_id if context_type in (None, CalendarContextType.USER) else None,
        client_id=default_client_id,
        site_id=default_site_id,
    )

    if not context_type:
        return current

    if context_type == CalendarContextType.USER:
        return replace(current, people_id=context_id or user_id)

    if context_id is None:
        raise ValidationError("context_id is required when context_type is provided")

    if context_type == CalendarContextType.SITE:
        return replace(current, site_id=context_id)
    if context_type == CalendarContextType.ASSET:
        return replace(current, asset_id=context_id)
    if context_type == CalendarContextType.CLIENT:
        return replace(current, client_id=context_id)
    if context_type == CalendarContextType.TEAM:
        return replace(current, team_id=context_id)
    if context_type == CalendarContextType.SHIFT:
        return replace(current, shift_id=context_id)

    raise ValidationError(f"Unsupported context_type '{context_type}'")


__all__ = ["build_context_filter"]
