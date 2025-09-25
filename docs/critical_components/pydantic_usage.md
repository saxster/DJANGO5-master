# Pydantic Usage in YOUTILITY5

## Overview
Pydantic is used in this project primarily for **data validation in GraphQL API endpoints**. It provides type safety and automatic validation for incoming API requests.

## Installation
```bash
pip install pydantic==2.11.5
pip install pydantic_core==2.33.2
```

## Architecture Pattern

### 1. Schema Definitions
**Location**: `/apps/service/pydantic_schemas/`

Pydantic models define the expected data structure and types for API inputs:

```python
from pydantic import BaseModel
from datetime import datetime, date
from typing import List

class PeopleModifiedAfterSchema(BaseModel):
    mdtz: datetime
    ctzoffset: int
    buid: int

class PeopleEventLogHistorySchema(BaseModel):
    mdtz: datetime
    ctzoffset: int
    buid: int
    peopleid: int
    clientid: int
    peventtypeid: List[int]
```

### 2. GraphQL Query Validation
**Location**: `/apps/service/queries/`

GraphQL resolvers use Pydantic for input validation:

```python
from pydantic import ValidationError
from apps.service.pydantic_schemas.people_schema import PeopleModifiedAfterSchema

class PeopleQueries(graphene.ObjectType):
    @staticmethod
    def resolve_get_peoplemodifiedafter(self, info, mdtz, ctzoffset, buid):
        try:
            # Step 1: Create filter dict from raw inputs
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'buid': buid
            }

            # Step 2: Validate with Pydantic
            validated = PeopleModifiedAfterSchema(**filter_data)

            # Step 3: Use validated data (type-safe)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz,      # Guaranteed datetime object
                offset=validated.ctzoffset  # Guaranteed integer
            )

            # Step 4: Query database with validated data
            data = People.objects.get_people_modified_after(
                mdtz=mdtzinput,
                siteid=validated.buid
            )

            return SelectOutputType(nrows=count, records=records, msg=msg)

        except ValidationError as ve:
            # Pydantic validation failed
            log.error("Validation failed", exc_info=True)
            raise GraphQLError(f"Validation failed: {str(ve)}")
```

## Schema Files in Project

| Schema File | Purpose | Key Models |
|------------|---------|------------|
| `people_schema.py` | People/Employee data validation | `PeopleModifiedAfterSchema`, `PeopleEventLogPunchInsSchema` |
| `asset_schema.py` | Asset management validation | `AssetFilterSchema` |
| `job_schema.py` | Job/Task validation | `JobneedModifiedAfterSchema`, `ExternalTourModifiedAfterSchema` |
| `ticket_schema.py` | Ticket system validation | Ticket-related schemas |
| `question_schema.py` | Question/Survey validation | Question-related schemas |
| `bt_schema.py` | Business transaction validation | BT-related schemas |
| `workpermit_schema.py` | Work permit validation | Work permit schemas |
| `typeassist_schema.py` | Type assistance validation | Type assist schemas |

## Benefits of Using Pydantic

### 1. Type Safety
- Automatic type conversion (e.g., string to datetime)
- Runtime type checking
- Clear type hints for IDE support

### 2. Validation
- Automatic validation of required fields
- Custom validators can be added
- Clear, descriptive error messages

### 3. Documentation
- Schema classes serve as API documentation
- Self-documenting code through type hints
- Clear contract between frontend and backend

### 4. Error Handling
- Consistent error format across all endpoints
- Detailed validation error messages
- Graceful handling of invalid inputs

### 5. Separation of Concerns
- Validation logic separate from business logic
- Reusable schemas across multiple endpoints
- Clean, maintainable code structure

## Common Patterns

### Pattern 1: Simple Field Validation
```python
class AssetFilterSchema(BaseModel):
    mdtz: datetime
    ctzoffset: int
    buid: int
```

### Pattern 2: List Field Validation
```python
class PeopleEventLogHistorySchema(BaseModel):
    peventtypeid: List[int]  # Validates list of integers
```

### Pattern 3: Optional Fields
```python
from typing import Optional

class UpdateSchema(BaseModel):
    name: str
    description: Optional[str] = None  # Optional with default
```

### Pattern 4: String Validation for IDs
```python
class JobneedDetailsModifiedAfterSchema(BaseModel):
    jobneedids: str  # Comma-separated IDs as string
    ctzoffset: int
```

## Best Practices

1. **Always validate GraphQL inputs** with Pydantic schemas
2. **Use specific types** (datetime, int, float) instead of generic types
3. **Handle ValidationError** explicitly in resolvers
4. **Log validation failures** for debugging
5. **Keep schemas simple** - one schema per use case
6. **Reuse common patterns** across similar endpoints

## Error Handling Example

```python
try:
    validated = PeopleModifiedAfterSchema(**filter_data)
    # Use validated data...
except ValidationError as ve:
    # Log the error with full details
    log.error("Validation failed", exc_info=True)

    # Return user-friendly error to client
    raise GraphQLError(f"Invalid input: {str(ve)}")
except Exception as e:
    # Handle other unexpected errors
    log.error("Unexpected error", exc_info=True)
    raise GraphQLError(f"Request failed: {str(e)}")
```

## Testing Pydantic Schemas

```python
import pytest
from pydantic import ValidationError
from apps.service.pydantic_schemas.people_schema import PeopleModifiedAfterSchema

def test_valid_schema():
    data = {
        'mdtz': '2024-01-01T10:00:00',
        'ctzoffset': -5,
        'buid': 1
    }
    schema = PeopleModifiedAfterSchema(**data)
    assert schema.buid == 1
    assert schema.ctzoffset == -5

def test_invalid_type():
    data = {
        'mdtz': '2024-01-01T10:00:00',
        'ctzoffset': 'invalid',  # Should be int
        'buid': 1
    }
    with pytest.raises(ValidationError):
        PeopleModifiedAfterSchema(**data)

def test_missing_field():
    data = {
        'mdtz': '2024-01-01T10:00:00',
        'ctzoffset': -5
        # Missing 'buid'
    }
    with pytest.raises(ValidationError):
        PeopleModifiedAfterSchema(**data)
```

## Migration Guide

If you need to add Pydantic validation to a new endpoint:

1. **Create Schema** in `/apps/service/pydantic_schemas/[domain]_schema.py`
2. **Import Schema** in your query/mutation file
3. **Validate Inputs** before processing
4. **Handle Errors** with try/except blocks
5. **Test Schema** with unit tests

## Related Documentation

- [GraphQL Integration](./graphql_integration.md)
- [API Error Handling](./api_error_handling.md)
- [Data Validation Strategy](./data_validation.md)