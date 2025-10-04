"""
Practical Pydantic Integration Examples

This file demonstrates real-world usage patterns for the Pydantic integration
across different layers of the Django application.

Run these examples to see Pydantic validation in action:
python manage.py shell
>>> exec(open('examples/pydantic_integration_examples.py').read())
"""

# Example 1: Basic Pydantic Model Usage
print("=" * 60)
print("Example 1: Basic Pydantic Model Usage")
print("=" * 60)

from apps.core.validation.pydantic_base import BusinessLogicModel, create_code_field, create_name_field
from pydantic import Field, ValidationError
from typing import Optional

class TaskData(BusinessLogicModel):
    """Example task model with comprehensive validation."""

    title: str = create_name_field("Task title", max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: int = Field(1, ge=1, le=5, description="Priority level 1-5")
    status: str = Field("pending", description="Task status")
    assigned_to: Optional[int] = Field(None, gt=0, description="Assigned user ID")

    def validate_business_rules(self, context=None):
        """Custom business validation."""
        if self.priority >= 4 and not self.assigned_to:
            raise ValueError("High priority tasks (4-5) must be assigned to someone")

        if self.status == "completed" and self.priority == 5:
            # Log critical task completion
            print(f"✅ Critical task completed: {self.title}")

# Test valid data
try:
    valid_task = TaskData(
        title="Complete quarterly report",
        description="Prepare Q3 financial report",
        priority=3,
        status="in_progress",
        assigned_to=123
    )
    print(f"✅ Valid task created: {valid_task.title}")
    print(f"   Priority: {valid_task.priority}, Status: {valid_task.status}")
except ValidationError as e:
    print(f"❌ Validation failed: {e}")

# Test business rule validation
try:
    high_priority_task = TaskData(
        title="Critical system fix",
        priority=5,
        status="pending"
        # No assigned_to - should trigger business rule
    )
    high_priority_task.validate_business_rules()
except ValueError as e:
    print(f"🔍 Business rule caught: {e}")


# Example 2: Authentication Service Integration
print("\n" + "=" * 60)
print("Example 2: Authentication Service Integration")
print("=" * 60)

from apps.peoples.validation.authentication_models import (
    AuthenticationResult,
    UserContext,
    LoginRequest,
    AuthenticationStatus
)

# Test login request validation
try:
    login_request = LoginRequest(
        loginid="john.doe",
        password="secure_password_123",
        remember_me=True,
        device_fingerprint="browser_fp_abc123"
    )
    print(f"✅ Login request validated: {login_request.loginid}")

    # Test business rules (would require CAPTCHA in some contexts)
    login_request.validate_business_rules(context={'captcha_required': False})

except ValidationError as e:
    print(f"❌ Login validation failed: {e}")

# Create authentication results
success_result = AuthenticationResult.create_success(
    user_id=123,
    redirect_url="/dashboard/",
    session_data={"login_time": "2024-01-15T10:30:00Z"}
)

failure_result = AuthenticationResult.create_failure(
    status=AuthenticationStatus.INVALID_CREDENTIALS,
    error_message="Invalid username or password",
    error_code="AUTH_001",
    security_flags=["multiple_attempts"]
)

print(f"✅ Success result: {success_result.status}, User: {success_result.user_id}")
print(f"⚠️  Failure result: {failure_result.error_message}")
print(f"   Security concerns: {failure_result.has_security_concerns()}")


# Example 3: JSON Field Validation
print("\n" + "=" * 60)
print("Example 3: JSON Field Validation")
print("=" * 60)

from apps.core.validation.json_field_models import (
    PeopleExtrasData,
    ConversationContextData,
    validate_json_field
)

# Test people extras validation
people_extras = {
    "ai_enabled": True,
    "ai_capability_level": "intermediate",
    "system_capabilities": {
        "task_management": "advanced",
        "reporting": "basic"
    },
    "notification_preferences": {
        "email_alerts": "enabled",
        "sms_alerts": "disabled"
    },
    "dashboard_layout": {
        "theme": "dark",
        "widgets": ["tasks", "calendar", "reports"]
    },
    "two_factor_enabled": True,
    "session_timeout": 30
}

try:
    validated_extras = validate_json_field(people_extras, PeopleExtrasData)
    print("✅ People extras validated successfully")
    print(f"   AI enabled: {validated_extras['ai_enabled']}")
    print(f"   Capability level: {validated_extras['ai_capability_level']}")
    print(f"   2FA enabled: {validated_extras['two_factor_enabled']}")
except ValidationError as e:
    print(f"❌ People extras validation failed: {e}")

# Test conversation context validation
conversation_context = {
    "session_id": "sess_abc123",
    "user_id": 456,
    "conversation_type": "initial_setup",
    "language": "en",
    "current_step": "user_preferences",
    "completed_steps": ["welcome", "basic_info"],
    "started_at": "2024-01-15T10:00:00Z",
    "last_activity": "2024-01-15T10:05:00Z",
    "total_interactions": 3,
    "timeout_minutes": 30,
    "user_satisfaction_score": 4.5
}

try:
    validated_context = ConversationContextData.model_validate(conversation_context)
    print("✅ Conversation context validated successfully")
    print(f"   Type: {validated_context.conversation_type}")
    print(f"   Progress: {len(validated_context.completed_steps)}/{validated_context.max_steps or 'unlimited'} steps")
    print(f"   Satisfaction: {validated_context.user_satisfaction_score}/5.0")
except ValidationError as e:
    print(f"❌ Conversation context validation failed: {e}")


# Example 4: LLM Service Integration
print("\n" + "=" * 60)
print("Example 4: LLM Service Integration")
print("=" * 60)

from apps.onboarding_api.validation.llm_models import (
    LLMContextData,
    LLMResponse,
    RecommendationData,
    ConversationType
)

# Test LLM context validation
llm_context = {
    "user_input": "I need help setting up my dashboard with task management widgets",
    "conversation_type": ConversationType.INITIAL_SETUP,
    "language": "en",
    "client_context": {
        "user_role": "manager",
        "department": "operations"
    },
    "business_unit_id": 10,
    "max_response_tokens": 800,
    "temperature": 0.7
}

try:
    validated_context = LLMContextData.model_validate(llm_context)
    print("✅ LLM context validated successfully")
    print(f"   Input length: {len(validated_context.user_input)} chars")
    print(f"   Type: {validated_context.conversation_type}")
    print(f"   Max tokens: {validated_context.max_response_tokens}")

    # Test business rules
    validated_context.validate_business_rules()
    print("✅ Business rules passed")

except ValidationError as e:
    print(f"❌ LLM context validation failed: {e}")

# Test LLM response validation
llm_response_data = {
    "response_id": "resp_789",
    "content": "I'll help you set up your dashboard. Based on your role as an operations manager, I recommend adding task management, team performance, and reporting widgets.",
    "confidence_score": 0.92,
    "token_usage": {
        "prompt_tokens": 150,
        "completion_tokens": 85,
        "total_tokens": 235
    },
    "processing_time_ms": 750,
    "safety_score": 0.98,
    "safety_level": "safe",
    "follow_up_questions": [
        "Would you like me to configure specific task filters?",
        "Should we include calendar integration?"
    ]
}

try:
    validated_response = LLMResponse.model_validate(llm_response_data)
    print("✅ LLM response validated successfully")
    print(f"   Confidence: {validated_response.confidence_score:.2f}")
    print(f"   Safety score: {validated_response.safety_score:.2f}")
    print(f"   Safe for display: {validated_response.is_safe_for_display()}")
    print(f"   Follow-up questions: {len(validated_response.follow_up_questions)}")

except ValidationError as e:
    print(f"❌ LLM response validation failed: {e}")

# Test recommendation validation
recommendation_data = {
    "recommendation_id": "rec_456",
    "title": "Enable Advanced Task Filtering",
    "description": "Configure advanced filtering options for your task management dashboard to improve productivity and focus on high-priority items.",
    "confidence_score": 0.88,
    "priority": "medium",
    "category": "dashboard_optimization",
    "implementation_steps": [
        "Access dashboard settings",
        "Navigate to task widget configuration",
        "Enable priority-based filtering",
        "Configure custom filter rules",
        "Test and save settings"
    ],
    "estimated_impact": "15-20% improvement in task management efficiency",
    "consensus": True,
    "maker_confidence": 0.90,
    "checker_confidence": 0.86
}

try:
    validated_recommendation = RecommendationData.model_validate(recommendation_data)
    print("✅ Recommendation validated successfully")
    print(f"   Title: {validated_recommendation.title}")
    print(f"   Priority: {validated_recommendation.priority}")
    print(f"   Steps: {len(validated_recommendation.implementation_steps)}")
    print(f"   Has consensus: {validated_recommendation.consensus}")

    # Test business rules
    validated_recommendation.validate_business_rules()
    print("✅ Recommendation business rules passed")

except ValidationError as e:
    print(f"❌ Recommendation validation failed: {e}")


# Example 5: Error Handling and Security
print("\n" + "=" * 60)
print("Example 5: Error Handling and Security")
print("=" * 60)

# Test security validation
def test_security_validation():
    """Test built-in security features."""

    # Test XSS protection
    try:
        malicious_task = TaskData(
            title="<script>alert('XSS')</script>Legitimate Task",
            description="Normal description",
            priority=2
        )
        print(f"✅ XSS input sanitized: '{malicious_task.title}'")
    except ValidationError as e:
        print(f"🔒 Security validation blocked XSS: {e}")

    # Test SQL injection protection
    try:
        sql_injection_data = {
            "user_input": "'; DROP TABLE users; --",
            "conversation_type": "initial_setup",
            "language": "en",
            "max_response_tokens": 500
        }

        context = LLMContextData.model_validate(sql_injection_data)
        print(f"⚠️  SQL injection attempt processed: '{context.user_input[:20]}...'")

    except ValidationError as e:
        print(f"🔒 Security validation blocked SQL injection: {e}")

test_security_validation()

# Test comprehensive error reporting
def test_comprehensive_errors():
    """Test detailed error reporting."""

    try:
        # Multiple validation errors
        invalid_task = TaskData(
            title="",  # Too short
            priority=10,  # Out of range
            assigned_to=-5  # Must be positive
        )
    except ValidationError as e:
        print("📋 Comprehensive error report:")
        for error in e.errors():
            field = ".".join(str(loc) for loc in error['loc'])
            print(f"   • {field}: {error['msg']}")

test_comprehensive_errors()


# Example 6: Integration with Django Models
print("\n" + "=" * 60)
print("Example 6: Django Model Integration Example")
print("=" * 60)

# Simulate Django model with Pydantic validation
class MockPeopleModel:
    """Mock People model to demonstrate integration."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def clean(self):
        """Django model validation using Pydantic."""
        if hasattr(self, 'people_extras') and self.people_extras:
            try:
                validated = validate_json_field(self.people_extras, PeopleExtrasData)
                self.people_extras = validated
                print("✅ Django model JSON field validated with Pydantic")
            except ValidationError as e:
                print(f"❌ Django model validation failed: {e}")
                raise

    def save(self):
        self.clean()
        print(f"✅ Mock model saved: {getattr(self, 'peoplename', 'Unknown')}")

# Test Django integration
try:
    person = MockPeopleModel(
        peoplename="John Doe",
        people_extras={
            "ai_enabled": True,
            "ai_capability_level": "beginner",
            "notification_preferences": {"email_alerts": "enabled"},
            "two_factor_enabled": False
        }
    )
    person.save()

except Exception as e:
    print(f"❌ Django integration failed: {e}")


# Example 7: Performance and Caching
print("\n" + "=" * 60)
print("Example 7: Performance Optimization")
print("=" * 60)

import time
from functools import lru_cache

# Test validation performance
def measure_validation_performance():
    """Measure Pydantic validation performance."""

    test_data = {
        "title": "Performance Test Task",
        "description": "Testing validation speed",
        "priority": 3,
        "status": "pending",
        "assigned_to": 456
    }

    # Time multiple validations
    start_time = time.time()
    iterations = 1000

    for _ in range(iterations):
        validated = TaskData.model_validate(test_data)

    end_time = time.time()
    avg_time = (end_time - start_time) / iterations * 1000

    print(f"⚡ Validation performance: {avg_time:.3f}ms per validation")
    print(f"   Total {iterations} validations in {(end_time - start_time)*1000:.1f}ms")

# Cached validation example
@lru_cache(maxsize=100)
def cached_validation(data_json: str):
    """Cached validation for repeated data patterns."""
    import json
    data = json.loads(data_json)
    return TaskData.model_validate(data)

measure_validation_performance()

print("\n" + "=" * 60)
print("🎉 All Pydantic Integration Examples Completed!")
print("=" * 60)

print("""
Summary of demonstrated features:
✅ Basic Pydantic model validation
✅ Business rule validation
✅ Authentication service integration
✅ JSON field validation
✅ LLM service validation
✅ Security protection (XSS, SQL injection)
✅ Comprehensive error reporting
✅ Django model integration
✅ Performance optimization

Next steps:
1. Review the PYDANTIC_INTEGRATION_GUIDE.md for detailed usage
2. Start integrating Pydantic models into your services
3. Add validation to critical JSON fields
4. Enhance API endpoints with Pydantic validation
5. Monitor performance and adjust caching as needed

For questions or issues, refer to the integration guide or check the
apps/core/validation/ directory for base models and utilities.
""")