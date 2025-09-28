"""
Test suite for Conversational Onboarding API

This package contains comprehensive tests for all aspects of the
conversational onboarding system including security, performance,
and functional testing.
"""

# Test configuration
TEST_CONFIGURATION = {
    'run_performance_tests': True,
    'run_security_tests': True,
    'run_integration_tests': True,
    'performance_thresholds': {
        'max_response_time_ms': 5000,
        'min_success_rate': 0.95,
        'max_memory_increase_mb': 100
    },
    'security_requirements': {
        'require_authentication': True,
        'require_tenant_scoping': True,
        'require_audit_logging': True
    }
}

# Test markers for pytest
pytest_markers = {
    'unit': 'Unit tests - fast, isolated tests',
    'integration': 'Integration tests - test component interactions',
    'security': 'Security tests - validate security controls',
    'performance': 'Performance tests - validate performance requirements',
    'slow': 'Slow tests - may take longer to run'
}

# Import key test classes for easier access
    EscalationTestCase,
)

    FailoverTestCase,
)

    ResourceUtilizationTestCase,
)

__all__ = [
    # Configuration
    'TEST_CONFIGURATION',
    'pytest_markers',

    # Comprehensive tests
    'ConversationalOnboardingBaseTestCase',
    'ConversationStartTestCase',
    'ConcurrencyTestCase',
    'SecurityTestCase',
    'PreflightValidationTestCase',
    'MonitoringTestCase',
    'EscalationTestCase',

    # Security tests
    'TenantScopeValidationTestCase',
    'IdempotencyTestCase',
    'SecurityAuditTestCase',
    'SecurityDecoratorTestCase',
    'SecurityHardeningTestCase',
    'AuthorizationTestCase',
    'SecurityViolationTestCase',
    'SecurityRegressionTestCase',
    'FailoverTestCase',

    # Performance tests
    'PerformanceBaseTestCase',
    'AdvisoryLockPerformanceTestCase',
    'APIPerformanceTestCase',
    'LoadTestCase',
    'CachePerformanceTestCase',
    'DatabasePerformanceTestCase',
    'ResourceUtilizationTestCase',
]