"""Shared helpers for mobile sync service modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class SyncResult:
    """Normalized result container for mobile sync operations."""

    records: Sequence[Mapping[str, object]]
    record_type: Optional[str]
    message: str
    records_json: Optional[str] = None
    typed_records: Optional[Sequence[Mapping[str, object]]] = None

    @property
    def count(self) -> int:
        return len(self.records)


def build_select_output(
    *,
    records: Iterable[Mapping[str, object]],
    record_type: Optional[str],
    message: str,
    records_json: Optional[str] = None,
    typed_records: Optional[Iterable[Mapping[str, object]]] = None,
) -> SyncResult:
    """Factory helper producing the legacy SelectOutput-style payload."""

    materialised_records = tuple(records)
    materialised_typed = tuple(typed_records) if typed_records is not None else None

    return SyncResult(
        records=materialised_records,
        record_type=record_type,
        message=message,
        records_json=records_json,
        typed_records=materialised_typed,
    )
