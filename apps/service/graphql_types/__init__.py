"""
GraphQL Type Definitions

Provides typed GraphQL types for Apollo Kotlin codegen.

Organized by category:
- Record types (for SelectOutputType.records_typed)
- Question types (enhanced question schema)
- Custom scalars
"""

from .record_types import (
    QuestionRecordType,
    QuestionSetRecordType,
    LocationRecordType,
    AssetRecordType,
    PgroupRecordType,
    TypeAssistRecordType,
    SelectRecordUnion,
    resolve_typed_record,
)

__all__ = [
    # Record types for SelectOutputType
    'QuestionRecordType',
    'QuestionSetRecordType',
    'LocationRecordType',
    'AssetRecordType',
    'PgroupRecordType',
    'TypeAssistRecordType',
    'SelectRecordUnion',
    # Utilities
    'resolve_typed_record',
]
