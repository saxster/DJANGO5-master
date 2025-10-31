"""
REST API Type Definitions (replacement for legacy query types)

Created: October 29, 2025
Purpose: Replace deleted legacy query types with REST-compatible dataclasses

Following .claude/rules.md:
- Rule #7: File <150 lines
- Rule #11: Specific exception handling

Migration Note: This replaces apps/service/types.py from the retired query layer.
The legacy implementation was removed in October 2025; this module preserves the
response contracts used by service helpers such as ServiceOutputType.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


@dataclass
class ServiceOutputType:
    """
    Standard service output format for database operations.

    Replacement for the legacy ServiceOutputType (removed Oct 2025).
    Used by database_service.py and other service layer functions.

    Attributes:
        rc: Response code (0=success, 1=error)
        msg: Message describing the result
        recordcount: Number of records affected/returned
        traceback: Error traceback (default: "NA")
        uuids: List of UUIDs created/updated
    """
    rc: int = 0
    msg: str = ""
    recordcount: int = 0
    traceback: str = "NA"
    uuids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'rc': self.rc,
            'msg': self.msg,
            'recordcount': self.recordcount,
            'traceback': self.traceback,
            'uuids': self.uuids
        }

    @property
    def success(self) -> bool:
        """Check if operation was successful."""
        return self.rc == 0

    @property
    def failed(self) -> bool:
        """Check if operation failed."""
        return self.rc != 0


__all__ = ['ServiceOutputType']
