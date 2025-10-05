"""
GraphQL Typed Record Definitions

Replaces graphene.JSONString() with proper typed GraphQL objects.
Enables Apollo Kotlin to generate type-safe sealed classes.

Compliance with .claude/rules.md:
- Rule #7: Classes < 150 lines (split by entity type)
- Rule #11: Specific exception handling

For Apollo Kotlin codegen:
    sealed class SelectRecord {
        data class QuestionRecord(...) : SelectRecord()
        data class LocationRecord(...) : SelectRecord()
        ...
    }
"""

import graphene
from graphene import ObjectType
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# QUESTION DOMAIN RECORDS
# ============================================================================

class QuestionRecordType(ObjectType):
    """
    Typed record for Question.values() output.

    Fields match apps/activity/managers/question_manager.py:344-362
    Maps to Kotlin: data class QuestionRecord
    """
    id = graphene.Int(description="Question ID")
    quesname = graphene.String(description="Question text")
    options = graphene.List(graphene.String, description="Answer options (for DROPDOWN/CHECKBOX)")
    min = graphene.Float(description="Minimum value (for NUMERIC)")
    max = graphene.Float(description="Maximum value (for NUMERIC)")
    alerton = graphene.String(description="Alert condition (legacy)")
    answertype = graphene.String(description="Answer type (TEXT, NUMERIC, DROPDOWN, etc.)")
    isworkflow = graphene.Boolean(description="Whether question triggers workflow")
    enable = graphene.Boolean(description="Whether question is active")

    # Foreign keys
    category_id = graphene.Int(description="Category ID")
    unit_id = graphene.Int(description="Unit ID")
    client_id = graphene.Int(description="Client ID")
    tenant_id = graphene.Int(description="Tenant ID")
    bu_id = graphene.Int(description="Business unit ID")
    cuser_id = graphene.Int(description="Created by user ID")
    muser_id = graphene.Int(description="Modified by user ID")

    # Audit timestamps
    cdtz = graphene.String(description="Creation datetime (ISO 8601)")
    mdtz = graphene.String(description="Modification datetime (ISO 8601)")
    ctzoffset = graphene.Int(description="Client timezone offset (minutes)")


class QuestionSetRecordType(ObjectType):
    """
    Typed record for QuestionSet.values() output.

    Fields match apps/activity/managers/question_manager.py:25-46
    Maps to Kotlin: data class QuestionSetRecord
    """
    id = graphene.Int(description="Question set ID")
    qsetname = graphene.String(description="Question set name")
    type = graphene.String(description="Question set type")
    parent_id = graphene.Int(description="Parent question set ID")
    enable = graphene.Boolean(description="Whether question set is active")

    # Configuration
    assetincludes = graphene.List(graphene.Int, description="Included asset IDs")
    buincludes = graphene.List(graphene.Int, description="Included business unit IDs")
    site_grp_includes = graphene.List(graphene.String, description="Included site group codes")
    site_type_includes = graphene.List(graphene.String, description="Included site type codes")
    show_to_all_sites = graphene.Boolean(description="Show to all sites")

    # Metadata
    seqno = graphene.Int(description="Sequence number")
    url = graphene.String(description="Associated URL")

    # Foreign keys
    bu_id = graphene.Int(description="Business unit ID")
    client_id = graphene.Int(description="Client ID")
    tenant_id = graphene.Int(description="Tenant ID")
    cuser_id = graphene.Int(description="Created by user ID")
    muser_id = graphene.Int(description="Modified by user ID")

    # Audit timestamps
    cdtz = graphene.String(description="Creation datetime (ISO 8601)")
    mdtz = graphene.String(description="Modification datetime (ISO 8601)")
    ctzoffset = graphene.Int(description="Client timezone offset (minutes)")


# ============================================================================
# LOCATION DOMAIN RECORDS
# ============================================================================

class LocationRecordType(ObjectType):
    """
    Typed record for Location.values() output.

    Fields match apps/activity/managers/location_manager.py:33-52
    Maps to Kotlin: data class LocationRecord
    """
    id = graphene.Int(description="Location ID")
    uuid = graphene.String(description="UUID")
    loccode = graphene.String(description="Location code")
    locname = graphene.String(description="Location name")
    locstatus = graphene.String(description="Location status")
    enable = graphene.Boolean(description="Whether location is active")
    iscritical = graphene.Boolean(description="Whether location is critical")

    # Geographic
    gpslocation = graphene.String(description="GPS location (GeoJSON Point)")

    # Hierarchy
    parent_id = graphene.Int(description="Parent location ID")
    type_id = graphene.Int(description="Location type ID")

    # Foreign keys
    bu_id = graphene.Int(description="Business unit ID")
    client_id = graphene.Int(description="Client ID")
    tenant_id = graphene.Int(description="Tenant ID")
    cuser_id = graphene.Int(description="Created by user ID")
    muser_id = graphene.Int(description="Modified by user ID")

    # Audit timestamps
    cdtz = graphene.String(description="Creation datetime (ISO 8601)")
    mdtz = graphene.String(description="Modification datetime (ISO 8601)")
    ctzoffset = graphene.Int(description="Client timezone offset (minutes)")


# ============================================================================
# ASSET DOMAIN RECORDS (estimated fields)
# ============================================================================

class AssetRecordType(ObjectType):
    """
    Typed record for Asset.values() output.

    Maps to Kotlin: data class AssetRecord
    """
    id = graphene.Int(description="Asset ID")
    uuid = graphene.String(description="UUID")
    assetcode = graphene.String(description="Asset code")
    assetname = graphene.String(description="Asset name")
    runningstatus = graphene.String(description="Running status")
    type = graphene.String(description="Asset type")
    category = graphene.String(description="Asset category")
    enable = graphene.Boolean(description="Whether asset is active")
    iscritical = graphene.Boolean(description="Whether asset is critical")

    # Geographic
    gpslocation = graphene.String(description="GPS location (GeoJSON Point)")

    # Foreign keys
    location_id = graphene.Int(description="Location ID")
    parent_id = graphene.Int(description="Parent asset ID")
    bu_id = graphene.Int(description="Business unit ID")
    client_id = graphene.Int(description="Client ID")
    tenant_id = graphene.Int(description="Tenant ID")

    # Audit timestamps
    cdtz = graphene.String(description="Creation datetime (ISO 8601)")
    mdtz = graphene.String(description="Modification datetime (ISO 8601)")


# ============================================================================
# PEOPLE DOMAIN RECORDS
# ============================================================================

class PgroupRecordType(ObjectType):
    """
    Typed record for Pgroup (People Group).values() output.

    Fields match apps/peoples/managers.py:631-644
    Maps to Kotlin: data class PgroupRecord
    """
    id = graphene.Int(description="Group ID")
    groupname = graphene.String(description="Group name")
    enable = graphene.Boolean(description="Whether group is active")

    # Foreign keys
    identifier_id = graphene.Int(description="Identifier (type assist) ID")
    bu_id = graphene.Int(description="Business unit ID")
    client_id = graphene.Int(description="Client ID")
    tenant_id = graphene.Int(description="Tenant ID")
    cuser_id = graphene.Int(description="Created by user ID")
    muser_id = graphene.Int(description="Modified by user ID")

    # Audit timestamps
    cdtz = graphene.String(description="Creation datetime (ISO 8601)")
    mdtz = graphene.String(description="Modification datetime (ISO 8601)")
    ctzoffset = graphene.Int(description="Client timezone offset (minutes)")


# ============================================================================
# ONBOARDING DOMAIN RECORDS
# ============================================================================

class TypeAssistRecordType(ObjectType):
    """
    Typed record for TypeAssist.values() output.

    Maps to Kotlin: data class TypeAssistRecord
    """
    id = graphene.Int(description="TypeAssist ID")
    tacode = graphene.String(description="Type assist code")
    taname = graphene.String(description="Type assist name")
    tatype_id = graphene.Int(description="Type assist type ID")
    enable = graphene.Boolean(description="Whether active")

    # Foreign keys
    bu_id = graphene.Int(description="Business unit ID")
    client_id = graphene.Int(description="Client ID")
    tenant_id = graphene.Int(description="Tenant ID")

    # Audit
    cdtz = graphene.String(description="Creation datetime (ISO 8601)")
    mdtz = graphene.String(description="Modification datetime (ISO 8601)")


# ============================================================================
# UNION TYPE FOR POLYMORPHIC RECORDS
# ============================================================================

class SelectRecordUnion(graphene.Union):
    """
    Union type for polymorphic SelectOutputType records.

    Enables Apollo Kotlin to generate sealed class:

    ```kotlin
    sealed class SelectRecord {
        data class QuestionRecord(...) : SelectRecord()
        data class LocationRecord(...) : SelectRecord()
        data class AssetRecord(...) : SelectRecord()
        data class PgroupRecord(...) : SelectRecord()
        data class TypeAssistRecord(...) : SelectRecord()
        data class QuestionSetRecord(...) : SelectRecord()
    }
    ```

    Usage in queries:
    ```graphql
    query {
        getQuestionsmodifiedafter(...) {
            recordsTyped {
                ... on QuestionRecordType {
                    id
                    quesname
                    answertype
                }
            }
        }
    }
    ```
    """
    class Meta:
        types = (
            QuestionRecordType,
            QuestionSetRecordType,
            LocationRecordType,
            AssetRecordType,
            PgroupRecordType,
            TypeAssistRecordType,
        )


# ============================================================================
# TYPE RESOLUTION UTILITIES
# ============================================================================

def resolve_typed_record(record_dict: Dict[str, Any], record_type: str):
    """
    Convert dictionary to appropriate GraphQL record type.

    Args:
        record_dict: Dictionary from Django .values() call
        record_type: Type discriminator (question, location, asset, etc.)

    Returns:
        Appropriate GraphQL record type instance

    Raises:
        ValueError: If record_type is unknown

    Example:
        >>> record = {'id': 1, 'quesname': 'Test?', 'answertype': 'TEXT'}
        >>> typed = resolve_typed_record(record, 'question')
        >>> isinstance(typed, QuestionRecordType)
        True
    """
    type_map = {
        'question': QuestionRecordType,
        'questionset': QuestionSetRecordType,
        'location': LocationRecordType,
        'asset': AssetRecordType,
        'pgroup': PgroupRecordType,
        'typeassist': TypeAssistRecordType,
    }

    record_class = type_map.get(record_type)
    if not record_class:
        logger.error(f"Unknown record type: {record_type}")
        raise ValueError(f"Unknown record type: {record_type}. Supported: {list(type_map.keys())}")

    try:
        return record_class(**record_dict)
    except TypeError as e:
        logger.error(
            f"Failed to create {record_class.__name__} from dict",
            exc_info=True,
            extra={'record_dict_keys': list(record_dict.keys())}
        )
        raise ValueError(f"Invalid record structure for {record_type}: {str(e)}")


__all__ = [
    'QuestionRecordType',
    'QuestionSetRecordType',
    'LocationRecordType',
    'AssetRecordType',
    'PgroupRecordType',
    'TypeAssistRecordType',
    'SelectRecordUnion',
    'resolve_typed_record',
]
