# Pydantic Integration Guide

## Overview

This guide demonstrates how to leverage the comprehensive Pydantic integration that has been added to enhance code reliability, type safety, and validation throughout the Django application.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Base Models](#base-models)
3. [Service Layer Integration](#service-layer-integration)
4. [DRF Serializer Integration](#drf-serializer-integration)
5. [GraphQL Integration](#graphql-integration)
6. [JSON Field Validation](#json-field-validation)
7. [Middleware Integration](#middleware-integration)
8. [Examples](#examples)
9. [Migration Strategy](#migration-strategy)
10. [Best Practices](#best-practices)

## Core Concepts

The Pydantic integration provides several key enhancements:

- **Runtime Type Safety**: Automatic validation of data types at runtime
- **Business Rule Validation**: Comprehensive business logic validation
- **Security Enhancement**: Built-in XSS and SQL injection protection
- **Multi-tenant Support**: Tenant-aware validation patterns
- **Django Compatibility**: Seamless integration with existing Django patterns

## Base Models

### Available Base Models

```python
from apps.core.validation.pydantic_base import (
    BaseDjangoModel,        # Basic Pydantic-Django integration
    TenantAwareModel,      # Multi-tenant validation
    TimestampModel,        # Timestamp validation
    AuditModel,           # Audit trail support
    SecureModel,          # Security-focused validation
    BusinessLogicModel    # Full enterprise features
)
```

### Creating Your First Pydantic Model

```python
from apps.core.validation.pydantic_base import BusinessLogicModel
from pydantic import Field
from typing import Optional

class TaskData(BusinessLogicModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: int = Field(1, ge=1, le=5)
    assigned_to: Optional[int] = Field(None, gt=0)

    def validate_business_rules(self, context=None):
        """Custom business validation."""
        if self.priority >= 4 and not self.assigned_to:
            raise ValueError("High priority tasks must be assigned")
```

## Service Layer Integration

### Converting Existing Dataclasses

#### Before (Dataclass)
```python
@dataclass
class AuthenticationResult:
    success: bool
    user: Optional[People] = None
    redirect_url: Optional[str] = None
    error_message: Optional[str] = None
```

#### After (Pydantic)
```python
from apps.peoples.validation.authentication_models import AuthenticationResult

# Enhanced with validation, security, and type safety
result = AuthenticationResult.create_success(
    user_id=user.id,
    redirect_url="/dashboard/"
)

# Automatic validation
if result.is_successful():
    # Type-safe access to properties
    print(f"Redirecting to: {result.redirect_url}")
```

### Using Enhanced Authentication Models

```python
from apps.peoples.validation.authentication_models import (
    AuthenticationResult,
    UserContext,
    LoginRequest
)

def authenticate_user(request):
    # Validate login request
    login_data = LoginRequest.model_validate(request.data)

    # Create user context
    user_context = UserContext.from_user_and_request(user, request)

    # Validate business rules
    user_context.validate_business_rules()

    # Return typed result
    return AuthenticationResult.create_success(user_id=user.id)
```

## DRF Serializer Integration

### Enhanced Serializers with Pydantic

```python
from apps.core.serializers.pydantic_integration import PydanticModelSerializer
from apps.peoples.models import People

class PersonData(BusinessLogicModel):
    peoplecode: str = create_code_field("Person code")
    peoplename: str = create_name_field("Person name")
    email: str = create_email_field("Email address")

    def validate_business_rules(self, context=None):
        """Custom validation logic."""
        pass

class PeopleSerializer(PydanticModelSerializer):
    pydantic_model = PersonData

    class Meta:
        model = People
        fields = ['id', 'peoplecode', 'peoplename', 'email', 'enable']

# Usage in ViewSet
@validate_with_pydantic(PersonData)
def create_person(request, validated_data: PersonData):
    # validated_data is fully validated Pydantic model
    person_dict = validated_data.to_django_dict()
    person = People.objects.create(**person_dict)
    return Response({"success": True, "id": person.id})
```

### ViewSet Integration

```python
from apps.core.serializers.pydantic_integration import PydanticViewSetMixin

class PeopleViewSet(PydanticViewSetMixin, ModelViewSet):
    serializer_class = PeopleSerializer

    def create(self, request):
        # Get validated Pydantic data
        pydantic_data = self.get_pydantic_data()

        # Create using Pydantic data
        instance = self.perform_create_with_pydantic(pydantic_data)

        # Return standardized response
        return Response(
            PydanticResponseSerializer.create_success_response(
                data=self.get_serializer(instance).data,
                message="Person created successfully"
            )
        )
```

## GraphQL Integration

### Enhanced GraphQL Validation

```python
from apps.core.graphql.pydantic_validators import (
    validate_graphql_input_with_pydantic,
    EnhancedGraphQLMutation
)

class CreatePersonInput(BusinessLogicModel):
    peoplecode: str = create_code_field("Person code")
    peoplename: str = create_name_field("Person name")
    email: str = create_email_field("Email address")

class CreatePersonMutation(EnhancedGraphQLMutation):
    pydantic_model = CreatePersonInput

    class Arguments:
        input = CreatePersonInput.Input(required=True)

    person = Field(PersonType)
    success = Boolean()

    @classmethod
    def mutate_with_validation(cls, root, info, validated_data, **kwargs):
        # validated_data is fully validated Pydantic model
        person_data = validated_data.to_django_dict()
        person = People.objects.create(**person_data)

        return CreatePersonMutation(person=person, success=True)

# Alternative decorator approach
@validate_graphql_input_with_pydantic(CreatePersonInput)
def resolve_create_person(self, info, input, validated_data):
    # Type-safe access to validated data
    return People.objects.create(**validated_data.to_django_dict())
```

## JSON Field Validation

### Validating Complex JSON Fields

```python
from apps.core.validation.json_field_models import (
    PeopleExtrasData,
    ConversationContextData,
    validate_json_field
)

# Model with JSON field
class People(models.Model):
    people_extras = models.JSONField(default=dict)

    def clean(self):
        """Validate JSON field with Pydantic."""
        if self.people_extras:
            try:
                # Validate using Pydantic model
                validated = validate_json_field(
                    self.people_extras,
                    PeopleExtrasData
                )
                self.people_extras = validated
            except ValueError as e:
                raise ValidationError(f"Invalid people_extras: {e}")

# Usage in views
def update_user_preferences(request, user_id):
    user = get_object_or_404(People, id=user_id)

    # Validate JSON data with Pydantic
    preferences = PeopleExtrasData.model_validate(request.data)

    # Perform business validation
    preferences.validate_business_rules()

    # Update user
    user.people_extras = preferences.model_dump()
    user.save()

    return JsonResponse({"success": True})
```

### LLM Service Integration

```python
from apps.onboarding_api.validation.llm_models import (
    LLMContextData,
    LLMResponse,
    RecommendationData
)

class EnhancedLLMService:
    def process_conversation(self, context_data: dict) -> LLMResponse:
        # Validate input context
        validated_context = LLMContextData.model_validate(context_data)

        # Perform business validation
        validated_context.validate_business_rules()

        # Process with LLM (mock)
        response_data = {
            "response_id": "resp_123",
            "content": "Generated response",
            "confidence_score": 0.95,
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "processing_time_ms": 500
        }

        # Validate response
        response = LLMResponse.model_validate(response_data)

        # Check safety before returning
        if not response.is_safe_for_display():
            raise ValueError("Response failed safety checks")

        return response
```

## Middleware Integration

### Automatic Request Validation

Add to Django settings:

```python
# settings.py
MIDDLEWARE = [
    # ... existing middleware
    'apps.core.middleware.pydantic_validation_middleware.PydanticValidationMiddleware',
    # ... rest of middleware
]
```

### Using Validation Decorators

```python
from apps.core.middleware.pydantic_validation_middleware import (
    validate_with_pydantic,
    PydanticRequestValidator
)

@api_view(['POST'])
@validate_with_pydantic(CreatePersonInput, full_validation=True)
def create_person_view(request, validated_data: CreatePersonInput):
    # validated_data is fully validated
    person = People.objects.create(**validated_data.to_django_dict())
    return Response({"id": person.id})

# Manual validation in views
@api_view(['POST'])
def manual_validation_view(request):
    validated_data = PydanticRequestValidator.validate_request_data(
        request, CreatePersonInput, partial=False
    )

    # Process validated data
    return Response(validated_data.model_dump())
```

## Examples

### Complete CRUD Example

```python
from apps.core.validation.pydantic_base import BusinessLogicModel
from apps.core.serializers.pydantic_integration import PydanticModelSerializer
from pydantic import Field
from typing import Optional

# 1. Define Pydantic Model
class TaskModel(BusinessLogicModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: int = Field(1, ge=1, le=5)
    status: str = Field("pending")

    def validate_business_rules(self, context=None):
        if self.priority >= 4 and self.status == "pending":
            if not context or not context.get('assigned_to'):
                raise ValueError("High priority tasks must be assigned")

# 2. Create Enhanced Serializer
class TaskSerializer(PydanticModelSerializer):
    pydantic_model = TaskModel

    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'priority', 'status', 'created_at']

# 3. Enhanced ViewSet
class TaskViewSet(PydanticViewSetMixin, ModelViewSet):
    serializer_class = TaskSerializer
    queryset = Task.objects.all()

    def create(self, request):
        # Get validated Pydantic data
        pydantic_data = self.get_pydantic_data()

        # Add context for business validation
        context = {'assigned_to': request.data.get('assigned_to')}
        pydantic_data.validate_business_rules(context)

        # Create task
        task = self.perform_create_with_pydantic(pydantic_data)

        return Response(
            PydanticResponseSerializer.create_success_response(
                data=self.get_serializer(task).data
            )
        )
```

### Service Integration Example

```python
from apps.core.validation.pydantic_base import BusinessLogicModel

class TaskService:
    @staticmethod
    def create_task(task_data: dict, user) -> Task:
        # Validate with Pydantic
        validated_data = TaskModel.model_validate(task_data)

        # Add audit information
        validated_data.set_audit_fields(user, is_create=True)

        # Validate business rules with context
        context = {'user': user, 'is_create': True}
        validated_data.validate_business_rules(context)

        # Create task
        task = Task.objects.create(**validated_data.to_django_dict())

        logger.info(f"Task created: {task.id}", extra={
            'user_id': user.id,
            'task_priority': validated_data.priority
        })

        return task
```

## Migration Strategy

### Phase 1: Foundation (Week 1)
- Add Pydantic to requirements
- Implement base models and middleware
- Test with one simple model

### Phase 2: Service Layer (Week 2-3)
- Convert authentication service
- Enhance LLM services
- Add JSON field validation to critical models

### Phase 3: API Enhancement (Week 4-5)
- Integrate with DRF serializers
- Enhance GraphQL validation
- Add comprehensive error handling

### Phase 4: Full Integration (Week 6-8)
- Complete remaining services
- Add configuration validation
- Performance optimization

### Backward Compatibility

All integration patterns maintain 100% backward compatibility:

```python
# Existing code continues to work
serializer = PeopleSerializer(data=request.data)
if serializer.is_valid():
    serializer.save()

# Enhanced version provides additional validation
class PeopleSerializer(PydanticModelSerializer):
    pydantic_model = PersonData  # Adds Pydantic validation

    # All existing methods continue to work
    def validate_email(self, value):
        # Custom DRF validation still works
        return value
```

## Best Practices

### 1. Model Organization
```python
# Organize models by domain
apps/peoples/validation/
├── __init__.py
├── authentication_models.py
├── profile_models.py
└── permission_models.py
```

### 2. Validation Layers
```python
class ComprehensiveModel(BusinessLogicModel):
    # Layer 1: Field-level validation (automatic)
    email: str = create_email_field()

    # Layer 2: Model-level validation
    @validator('email')
    def validate_email_domain(cls, value):
        if not value.endswith('@company.com'):
            raise ValueError('Must use company email')
        return value

    # Layer 3: Business rule validation
    def validate_business_rules(self, context=None):
        if context and context.get('department') == 'finance':
            # Special validation for finance department
            pass
```

### 3. Error Handling
```python
from pydantic import ValidationError
from apps.core.error_handling import ErrorHandler

try:
    validated_data = MyModel.model_validate(data)
except ValidationError as e:
    # Log validation errors
    ErrorHandler.handle_exception(e, context={
        'model': 'MyModel',
        'data_keys': list(data.keys())
    })

    # Convert to user-friendly format
    errors = [f"{error['loc'][0]}: {error['msg']}" for error in e.errors()]
    return Response({'errors': errors}, status=400)
```

### 4. Testing Enhanced Models
```python
import pytest
from pydantic import ValidationError

def test_task_model_validation():
    # Valid data
    valid_data = {
        'title': 'Test Task',
        'priority': 3,
        'status': 'pending'
    }
    task = TaskModel.model_validate(valid_data)
    assert task.title == 'Test Task'

    # Invalid data
    with pytest.raises(ValidationError) as exc_info:
        TaskModel.model_validate({'title': '', 'priority': 10})

    errors = exc_info.value.errors()
    assert any(error['type'] == 'string_too_short' for error in errors)

def test_business_rules():
    task_data = {'title': 'High Priority Task', 'priority': 5, 'status': 'pending'}
    task = TaskModel.model_validate(task_data)

    # Should raise error for high priority unassigned task
    with pytest.raises(ValueError, match="High priority tasks must be assigned"):
        task.validate_business_rules()
```

### 5. Performance Considerations
```python
# Cache validated models when possible
from functools import lru_cache

class OptimizedService:
    @lru_cache(maxsize=100)
    def get_validated_config(self, config_json: str):
        return ConfigModel.model_validate_json(config_json)

    # Use partial validation for updates
    def update_partial(self, instance, update_data):
        # Only validate changed fields
        validated = TaskModel.model_validate(update_data, partial=True)
        return validated
```

## Benefits Achieved

### 1. Type Safety
- Runtime type checking prevents type-related bugs
- IDE support with proper autocomplete and error detection
- Self-documenting code with clear type annotations

### 2. Enhanced Validation
- Comprehensive field validation beyond Django's capabilities
- Business rule validation with context awareness
- Multi-layer validation (field → model → business rules)

### 3. Security
- Built-in XSS and SQL injection protection
- Input sanitization at the Pydantic level
- Security-focused validation patterns

### 4. Developer Experience
- Clear error messages with field-level detail
- Automatic API documentation generation
- Consistent patterns across the application

### 5. Maintainability
- Centralized validation logic
- Easy to test and modify validation rules
- Clear separation of concerns

This Pydantic integration provides a solid foundation for building reliable, type-safe Django applications while maintaining full backward compatibility with existing patterns.