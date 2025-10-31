# Type-Safe API Contracts

> **Comprehensive data contracts for Kotlin/Swift mobile codegen with Pydantic validation**

---

## Quick Access

### OpenAPI Schema (REST v1/v2)

```bash
curl http://localhost:8000/api/schema/swagger.json > openapi.json
```

### WebSocket Message Schema

```bash
cat docs/api-contracts/websocket-messages.json
```

### Interactive API Documentation

```bash
open http://localhost:8000/api/schema/swagger/
open http://localhost:8000/api/schema/redoc/
```

### Schema Metadata

```bash
curl http://localhost:8000/api/schema/metadata/
```

---

## Architecture

### Three API Surfaces with Complete Type Safety

| API Type | Validation | Codegen | Example |
|----------|-----------|---------|---------|
| **REST v1** | DRF Serializers | OpenAPI Generator | `TaskSyncSerializer` |
| **REST v2** | Pydantic + DRF | OpenAPI Generator | `VoiceSyncRequestSerializer` |
| **WebSocket** | Pydantic Messages | JSON Schema | `SyncStartMessage` |

**Note**: Legacy query layer removed Oct 2025. See `REST_API_MIGRATION_COMPLETE.md` for details.

---

## REST v2 Pattern (Type-Safe)

### 1. Define Pydantic Model

```python
from apps.core.validation.pydantic_base import BusinessLogicModel
from pydantic import Field
from typing import List

class VoiceDataItem(BusinessLogicModel):
    timestamp: str
    audio_base64: str
    duration_ms: int

class VoiceSyncDataModel(BusinessLogicModel):
    device_id: str = Field(..., min_length=5)
    voice_data: List[VoiceDataItem] = Field(..., max_items=100)
```

### 2. Create DRF Serializer with Pydantic Integration

```python
from apps.core.serializers.pydantic_integration import PydanticSerializerMixin
from rest_framework import serializers

class VoiceSyncRequestSerializer(PydanticSerializerMixin, serializers.Serializer):
    pydantic_model = VoiceSyncDataModel  # ✅ Auto-validation
    full_validation = True

    device_id = serializers.CharField(...)  # For OpenAPI schema
    voice_data = serializers.ListField(...)
```

### 3. Use in View with Standardized Responses

```python
from apps.core.api_responses import create_success_response, create_error_response
from rest_framework.views import APIView
from rest_framework.response import Response

class SyncVoiceView(APIView):
    def post(self, request):
        serializer = VoiceSyncRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(create_error_response(
                serializer.errors
            ), status=400)

        result = process_voice_data(serializer.validated_data)
        return Response(create_success_response(result))
```

---

## WebSocket Pattern (Type-Safe)

### Define Message Models

```python
from pydantic import BaseModel

class SyncStartMessage(BaseModel):
    type: str = "sync_start"
    device_id: str
    timestamp: str

class SyncDataMessage(BaseModel):
    type: str = "sync_data"
    batch_id: str
    data: dict
```

### Parse and Handle Messages

```python
from apps.api.websocket_messages import parse_websocket_message
import json

async def receive(self, text_data):
    raw = json.loads(text_data)
    validated = parse_websocket_message(raw)  # ✅ Type-safe

    if isinstance(validated, SyncStartMessage):
        await self._handle_sync_start(validated)  # ✅ Type hints
    elif isinstance(validated, SyncDataMessage):
        await self._handle_sync_data(validated)
```

---

## Pydantic Domain Models

### Enhanced Schemas for Kotlin Codegen (14 total)

```python
# apps/service/pydantic_schemas/
task_enhanced_schema.py          # TaskDetailSchema (30 fields)
asset_enhanced_schema.py         # AssetDetailSchema (25 fields)
ticket_enhanced_schema.py        # TicketDetailSchema (20 fields)
attendance_enhanced_schema.py    # AttendanceDetailSchema (10 fields)
location_enhanced_schema.py      # LocationDetailSchema (15 fields)
question_enhanced_schema.py      # QuestionDetailSchema (15 fields)
```

### Usage

#### Runtime Validation

```python
from apps.service.pydantic_schemas import TaskDetailSchema

# Validates immediately
task_data = TaskDetailSchema(**request_data)
```

#### Convert to Django Model

```python
# Use to_django_dict() method
task = Jobneed(**task_data.to_django_dict())
```

## Standard Response Envelope

### ALL v2 Endpoints Use This Format

```python
from apps.core.api_responses import APIResponse, APIError, create_success_response

# Success response
return Response(create_success_response(
    data={'id': 123, 'name': 'Test'},
    execution_time_ms=25.5
))

# Error response
return Response(create_error_response([
    APIError(field='device_id', message='Required', code='REQUIRED')
]), status=400)
```

### Response Structure

```python
{
    "success": true,
    "data": {
        "id": 123,
        "name": "Test"
    },
    "errors": null,
    "meta": {
        "execution_time_ms": 25.5,
        "timestamp": "2025-10-29T10:30:00Z"
    }
}
```

---

## Kotlin Mapping

### Response Envelope

```kotlin
data class APIResponse<T>(
    val success: Boolean,
    val data: T?,
    val errors: List<APIError>?,
    val meta: APIMeta
)

data class APIError(
    val field: String?,
    val message: String,
    val code: String
)

data class APIMeta(
    val executionTimeMs: Double?,
    val timestamp: String
)
```

### Generated Models (Example)

```kotlin
data class TaskDetailSchema(
    val id: Int,
    val name: String,
    val status: TaskStatus,
    val assignedTo: List<Int>,
    val dueDate: String?,
    val priority: TaskPriority
)

enum class TaskStatus {
    PENDING,
    IN_PROGRESS,
    COMPLETED,
    CANCELLED
}
```

---

## For Mobile Teams

### Complete Guides

- **Kotlin Codegen Guide**: `docs/mobile/kotlin-codegen-guide.md`
- **Migration Guide**: `docs/mobile/MIGRATION_GUIDE_TYPE_SAFE_CONTRACTS.md`
- **WebSocket Contracts**: `docs/api-contracts/websocket-messages.json`
- **Kotlin Example**: `docs/api-contracts/WebSocketMessage.kt.example`

### OpenAPI Generator Command

```bash
# Generate Kotlin models from OpenAPI schema
openapi-generator-cli generate \
  -i http://localhost:8000/api/schema/swagger.json \
  -g kotlin \
  -o mobile/generated/kotlin \
  --additional-properties=library=jvm-retrofit2
```

---

## Validation Benefits

### Type Safety

- ✅ Runtime validation catches errors early
- ✅ IDE autocomplete for all fields
- ✅ Compile-time type checking
- ✅ Reduced manual QA effort

### Documentation

- ✅ Self-documenting APIs via OpenAPI
- ✅ Interactive testing with Swagger UI
- ✅ Automated mobile SDK generation
- ✅ Contract-first development

### Error Prevention

- ✅ Catches field mismatches before production
- ✅ Validates data types and constraints
- ✅ Clear error messages for debugging
- ✅ Prevents null pointer exceptions

---

## Migration from the Legacy Query Layer

The legacy query layer was removed in Oct 2025. All functionality migrated to REST v2 with Pydantic validation.

### What Changed

- **Before**: Legacy query endpoints with custom mutations
- **After**: REST v2 endpoints with OpenAPI schemas
- **Migration**: See `REST_API_MIGRATION_COMPLETE.md`

### Benefits of REST v2

1. Better mobile SDK generation (OpenAPI)
2. Simpler authentication (no legacy query middleware)
3. Standard HTTP semantics (caching, status codes)
4. Wider ecosystem support

---

**Last Updated**: October 29, 2025
**Maintainer**: API Team
**Reference**: `DATA_CONTRACTS_COMPREHENSIVE_COMPLETE.md`
