"""
Ontology registrations for Testing Knowledge - November 6, 2025.

Captures all testing patterns and best practices from remediation work:
- Security testing patterns (IDOR, cross-tenant, permissions)
- Performance testing (query count, benchmarking)
- Service layer testing (fixtures, mocks, integration)
- Test organization (naming, markers, coverage)
- Antipatterns and common mistakes

Total: 50+ testing pattern concepts
"""

from apps.ontology.registry import OntologyRegistry

import logging
logger = logging.getLogger(__name__)



def register_testing_knowledge():
    """Register comprehensive testing knowledge with the ontology registry."""
    
    testing_patterns = [
        # ===================================================================
        # SECURITY TESTING PATTERNS (15 concepts)
        # ===================================================================
        
        # IDOR Testing
        {
            "qualified_name": "testing.security.idor_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Insecure Direct Object Reference vulnerability testing - verifies users cannot access resources by ID manipulation",
            "tags": ["security", "idor", "testing", "vulnerability"],
            "criticality": "high",
            "examples": [
                "test_user_cannot_access_other_tenant_user_profile",
                "test_user_cannot_edit_other_tenant_attendance",
                "test_sequential_id_enumeration_prevention"
            ],
            "security_notes": "141 IDOR tests created across 5 apps (Peoples: 24, Attendance: 25, Activity: 29, Work Orders: 29, Helpdesk: 34)",
            "performance_notes": "Should test both blocking AND query count (prevent N+1 in permission checks)",
            "business_value": "Prevents data breaches and cross-tenant data leakage - critical for HIPAA/SOC2 compliance",
            "file_references": [
                "apps/peoples/tests/test_idor_security.py",
                "apps/attendance/tests/test_idor_security.py",
                "apps/activity/tests/test_idor_security.py",
                "apps/work_order_management/tests/test_idor_security.py",
                "apps/y_helpdesk/tests/test_idor_security.py",
                "IDOR_TEST_COVERAGE_REPORT.md"
            ]
        },
        
        # Cross-Tenant Testing
        {
            "qualified_name": "testing.security.cross_tenant_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Multi-tenancy isolation testing - verifies tenant data cannot be accessed across tenant boundaries",
            "tags": ["security", "multi-tenant", "isolation", "testing"],
            "criticality": "high",
            "examples": [
                "test_user_cannot_access_other_tenant_job",
                "test_attendance_list_scoped_to_tenant",
                "test_api_user_list_filtered_by_tenant",
                "test_work_order_reports_cross_tenant_blocked"
            ],
            "security_notes": "40+ cross-tenant tests across all apps - covers views, APIs, reports, and bulk operations",
            "patterns": [
                "Create user_tenant_a and user_tenant_b in setUp",
                "Create resource owned by tenant_a",
                "Login as user_tenant_b",
                "Attempt access - expect 403/404",
                "Verify query filters include client=request.user.client"
            ],
            "business_value": "Essential for SaaS platforms - prevents catastrophic data leakage between customers",
            "file_references": [
                "apps/*/tests/test_idor_security.py",
                ".claude/rules.md (multi-tenant enforcement)"
            ]
        },
        
        # Permission Boundary Testing
        {
            "qualified_name": "testing.security.permission_boundary_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Access control testing - verifies users cannot perform actions outside their permission scope",
            "tags": ["security", "permissions", "authorization", "testing"],
            "criticality": "high",
            "examples": [
                "test_regular_user_cannot_access_admin_functions",
                "test_admin_cannot_escalate_regular_user_to_superuser",
                "test_worker_can_only_view_assigned_tasks",
                "test_approval_requires_assignment"
            ],
            "security_notes": "15+ permission boundary tests - covers admin vs regular users, role-based access, and privilege escalation prevention",
            "patterns": [
                "Test role boundaries (admin/manager/worker)",
                "Test permission decorators (@permission_required)",
                "Test privilege escalation attempts",
                "Test cross-role function access"
            ],
            "antipatterns": [
                "Testing only happy path (authorized users)",
                "Skipping negative tests (unauthorized access)",
                "Not testing permission edge cases"
            ],
            "business_value": "Prevents unauthorized actions and privilege escalation attacks",
            "file_references": [
                "apps/peoples/tests/test_idor_security.py (admin tests)",
                "apps/y_helpdesk/tests/test_idor_security.py (escalation tests)"
            ]
        },
        
        # Authentication Testing
        {
            "qualified_name": "testing.security.authentication_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Authentication mechanism testing - verifies login, logout, session management, and token handling",
            "tags": ["security", "authentication", "session", "testing"],
            "criticality": "high",
            "examples": [
                "test_session_tenant_isolation",
                "test_cookie_manipulation_blocked",
                "test_device_trust_scoring",
                "test_login_throttling"
            ],
            "security_notes": "Covers session security, device trust, rate limiting, and brute force prevention",
            "patterns": [
                "Test valid login credentials",
                "Test invalid credentials handling",
                "Test session creation and isolation",
                "Test rate limiting enforcement",
                "Test device trust scoring"
            ],
            "service_references": [
                "apps.peoples.services.DeviceTrustService (35+ tests)",
                "apps.peoples.services.LoginThrottlingService (40+ tests)"
            ],
            "business_value": "Prevents unauthorized access and brute force attacks",
            "file_references": [
                "tests/peoples/services/test_device_trust_service.py",
                "tests/peoples/services/test_login_throttling_service.py"
            ]
        },
        
        # Authorization Testing
        {
            "qualified_name": "testing.security.authorization_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Authorization logic testing - verifies permission checks, capability validation, and access control",
            "tags": ["security", "authorization", "permissions", "testing"],
            "criticality": "high",
            "examples": [
                "test_effective_permissions_calculation",
                "test_ai_capability_management",
                "test_system_capabilities_protected",
                "test_bulk_capability_updates"
            ],
            "security_notes": "35+ tests for UserCapabilityService - covers CRUD, AI flags, and security boundaries",
            "patterns": [
                "Test permission CRUD operations",
                "Test effective permission calculation",
                "Test capability inheritance",
                "Test security boundary enforcement"
            ],
            "business_value": "Ensures users can only perform authorized actions",
            "file_references": [
                "tests/peoples/services/test_user_capability_service.py"
            ]
        },
        
        # Input Validation Testing
        {
            "qualified_name": "testing.security.input_validation_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Input sanitization and validation testing - prevents injection attacks, path traversal, and malformed data",
            "tags": ["security", "validation", "sanitization", "testing"],
            "criticality": "high",
            "examples": [
                "test_sequential_id_enumeration_blocked",
                "test_negative_id_handling",
                "test_invalid_id_format_rejected",
                "test_attachment_path_traversal_blocked"
            ],
            "security_notes": "20+ input validation tests - covers ID manipulation, path traversal, and format validation",
            "patterns": [
                "Test negative IDs → return 404",
                "Test invalid formats → return 400",
                "Test SQL injection attempts → sanitized",
                "Test path traversal → blocked",
                "Test oversized inputs → rejected"
            ],
            "antipatterns": [
                "Only testing valid inputs",
                "Not testing boundary conditions",
                "Skipping malicious input patterns"
            ],
            "business_value": "Prevents injection attacks and data corruption",
            "file_references": [
                "apps/*/tests/test_idor_security.py (ID manipulation tests)"
            ]
        },
        
        # API Security Testing
        {
            "qualified_name": "testing.security.api_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "REST API endpoint security testing - verifies authentication, authorization, rate limiting, and CSRF protection",
            "tags": ["security", "api", "rest", "testing"],
            "criticality": "high",
            "examples": [
                "test_api_user_detail_cross_tenant_blocked",
                "test_api_attendance_list_filtered_by_tenant",
                "test_api_bulk_operations_scoped_to_tenant",
                "test_csrf_protected_upload_endpoints"
            ],
            "security_notes": "20+ API security tests - covers endpoint isolation, list filtering, bulk operations, and CSRF protection",
            "patterns": [
                "Test unauthenticated access → 401",
                "Test unauthorized access → 403",
                "Test tenant filtering on lists",
                "Test CSRF token requirement",
                "Test rate limiting enforcement",
                "Test bulk operation scoping"
            ],
            "business_value": "Secures API endpoints against common attacks",
            "file_references": [
                "apps/*/tests/test_idor_security.py (API tests)",
                "apps/peoples/api/session_views.py",
                "apps/peoples/api/upload_views.py"
            ]
        },
        
        # Session Security Testing
        {
            "qualified_name": "testing.security.session_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Session management security testing - verifies session isolation, revocation, and cookie security",
            "tags": ["security", "session", "cookies", "testing"],
            "criticality": "high",
            "examples": [
                "test_session_tenant_isolation",
                "test_cookie_manipulation_blocked",
                "test_session_revoke_single",
                "test_session_revoke_all_rate_limited"
            ],
            "security_notes": "Session tests verify tenant isolation and prevent session hijacking",
            "patterns": [
                "Test session creation per tenant",
                "Test session data isolation",
                "Test cookie tampering prevention",
                "Test session revocation",
                "Test concurrent sessions"
            ],
            "business_value": "Prevents session hijacking and cross-tenant session leakage",
            "file_references": [
                "apps/peoples/tests/test_idor_security.py",
                "apps/peoples/api/session_views.py"
            ]
        },
        
        # File Security Testing
        {
            "qualified_name": "testing.security.file_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "File upload/download security testing - verifies path traversal prevention, ownership validation, and permission checks",
            "tags": ["security", "files", "upload", "download", "testing"],
            "criticality": "high",
            "examples": [
                "test_secure_file_download_with_token",
                "test_attachment_path_traversal_blocked",
                "test_csrf_protected_upload_endpoints",
                "test_chunked_upload_workflow"
            ],
            "security_notes": "File security tests prevent path traversal, IDOR, and unauthorized access",
            "patterns": [
                "Test path traversal attempts (../../../etc/passwd)",
                "Test MEDIA_ROOT boundary enforcement",
                "Test ownership validation",
                "Test CSRF protection on uploads",
                "Test token-based download authorization"
            ],
            "service_references": [
                "apps.core.services.SecureFileDownloadService"
            ],
            "business_value": "Prevents unauthorized file access and path traversal attacks",
            "file_references": [
                "apps/y_helpdesk/tests/test_idor_security.py (attachment tests)",
                "apps/peoples/api/upload_views.py",
                "apps/core/services/secure_file_download_service.py"
            ]
        },
        
        # Workflow Security Testing
        {
            "qualified_name": "testing.security.workflow_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Business workflow security testing - verifies state transitions, approval chains, and assignment validation",
            "tags": ["security", "workflow", "validation", "testing"],
            "criticality": "medium",
            "examples": [
                "test_work_order_status_transition_validation",
                "test_approval_workflow_cross_tenant_protection",
                "test_complete_ticket_lifecycle_tenant_isolation",
                "test_task_reassignment_requires_permission"
            ],
            "security_notes": "21+ workflow tests verify business rule enforcement and prevent workflow bypassing",
            "patterns": [
                "Test valid state transitions",
                "Test invalid transition blocking",
                "Test approval chain enforcement",
                "Test assignment validation",
                "Test end-to-end workflows"
            ],
            "business_value": "Ensures business rules are enforced and prevents workflow manipulation",
            "file_references": [
                "apps/work_order_management/tests/test_idor_security.py",
                "apps/y_helpdesk/tests/test_idor_security.py"
            ]
        },
        
        # Rate Limiting Testing
        {
            "qualified_name": "testing.security.rate_limiting_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Rate limiting and throttling testing - verifies brute force prevention and abuse protection",
            "tags": ["security", "rate-limit", "throttling", "testing"],
            "criticality": "high",
            "examples": [
                "test_ip_based_rate_limiting",
                "test_username_based_rate_limiting",
                "test_exponential_backoff_with_jitter",
                "test_distributed_attack_prevention"
            ],
            "security_notes": "40+ throttling tests simulate brute force attacks and verify progressive delays",
            "patterns": [
                "Test rate limit thresholds",
                "Test lockout activation",
                "Test exponential backoff",
                "Test cache failure resilience",
                "Test distributed attacks (multiple IPs)"
            ],
            "service_references": [
                "apps.peoples.services.LoginThrottlingService"
            ],
            "business_value": "Prevents brute force attacks and API abuse",
            "file_references": [
                "tests/peoples/services/test_login_throttling_service.py"
            ]
        },
        
        # Biometric Security Testing
        {
            "qualified_name": "testing.security.biometric_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Biometric data security testing - verifies enrollment, validation, and cross-tenant isolation",
            "tags": ["security", "biometric", "privacy", "testing"],
            "criticality": "high",
            "examples": [
                "test_biometric_data_cross_tenant_blocked",
                "test_biometric_enrollment_cross_user_blocked",
                "test_biometric_enrollment_validation"
            ],
            "security_notes": "Biometric tests ensure privacy and prevent unauthorized enrollment/access",
            "patterns": [
                "Test enrollment authorization",
                "Test cross-tenant isolation",
                "Test cross-user privacy",
                "Test validation logic"
            ],
            "business_value": "Protects sensitive biometric data and ensures privacy compliance",
            "file_references": [
                "apps/attendance/tests/test_idor_security.py"
            ]
        },
        
        # GPS Tracking Security Testing
        {
            "qualified_name": "testing.security.gps_tracking_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "GPS location data security testing - verifies cross-tenant isolation and ownership validation",
            "tags": ["security", "gps", "location", "privacy", "testing"],
            "criticality": "high",
            "examples": [
                "test_gps_data_cross_tenant_blocked",
                "test_gps_tracking_cross_user_blocked",
                "test_gps_location_update_requires_ownership"
            ],
            "security_notes": "GPS tests prevent location data leakage and unauthorized tracking",
            "patterns": [
                "Test location update authorization",
                "Test cross-tenant isolation",
                "Test cross-user privacy",
                "Test consent validation"
            ],
            "business_value": "Protects user privacy and prevents unauthorized location tracking",
            "file_references": [
                "apps/attendance/tests/test_idor_security.py"
            ]
        },
        
        # Report Security Testing
        {
            "qualified_name": "testing.security.report_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "Report and analytics security testing - verifies tenant scoping and data filtering",
            "tags": ["security", "reports", "analytics", "testing"],
            "criticality": "medium",
            "examples": [
                "test_attendance_reports_cross_tenant_blocked",
                "test_work_order_reports_cross_tenant_blocked",
                "test_analytics_dashboard_scoped_to_tenant"
            ],
            "security_notes": "Report tests ensure aggregated data is properly scoped to tenant",
            "patterns": [
                "Test report tenant scoping",
                "Test manager vs worker visibility",
                "Test sensitive data filtering",
                "Test export authorization"
            ],
            "business_value": "Prevents data leakage through reports and analytics",
            "file_references": [
                "apps/attendance/tests/test_idor_security.py",
                "apps/work_order_management/tests/test_idor_security.py",
                "apps/y_helpdesk/tests/test_idor_security.py"
            ]
        },
        
        # Integration Security Testing
        {
            "qualified_name": "testing.security.integration_security_testing",
            "type": "concept",
            "domain": "testing.security",
            "purpose": "End-to-end workflow security testing - verifies security across multiple components",
            "tags": ["security", "integration", "workflow", "testing"],
            "criticality": "medium",
            "examples": [
                "test_complete_attendance_workflow_tenant_isolation",
                "test_complete_job_workflow_tenant_isolation",
                "test_complete_ticket_lifecycle_tenant_isolation"
            ],
            "security_notes": "Integration tests verify security is maintained across entire workflows",
            "patterns": [
                "Test multi-step workflows",
                "Test cross-component security",
                "Test data flow isolation",
                "Test transaction rollback on security failures"
            ],
            "business_value": "Ensures security is maintained across complex workflows",
            "file_references": [
                "apps/*/tests/test_idor_security.py (integration test classes)"
            ]
        },
        
        # ===================================================================
        # PERFORMANCE TESTING PATTERNS (5 concepts)
        # ===================================================================
        
        # Query Count Assertions
        {
            "qualified_name": "testing.performance.query_count_assertions",
            "type": "concept",
            "domain": "testing.performance",
            "purpose": "Database query count testing - verifies N+1 prevention and query optimization",
            "tags": ["performance", "database", "n-plus-one", "testing"],
            "criticality": "medium",
            "examples": [
                "test_tenant_scoping_query_performance",
                "test_permission_check_caching",
                "test_service_layer_response_time"
            ],
            "patterns": [
                "Use django.test.utils.override_settings(DEBUG=True)",
                "Capture queries with connection.queries",
                "Assert len(queries) <= expected_count",
                "Use select_related/prefetch_related",
                "Test with multiple records (N=100+)"
            ],
            "performance_notes": "Always test with realistic data volumes - N+1 issues only appear at scale",
            "examples_code": [
                """
from django.test.utils import override_settings
from django.db import connection

@override_settings(DEBUG=True)
def test_query_count_optimized(self):
    connection.queries_log.clear()
    # Perform operation
    result = MyModel.objects.with_full_details().all()
    list(result)  # Force evaluation
    query_count = len(connection.queries)
    self.assertLessEqual(query_count, 3, "N+1 query detected")
                """
            ],
            "antipatterns": [
                "Testing with only 1-2 records (N+1 issues hidden)",
                "Not forcing queryset evaluation",
                "Testing views without checking query count"
            ],
            "business_value": "Prevents performance degradation and database overload",
            "file_references": [
                "apps/peoples/tests/test_idor_security.py (performance tests)",
                "apps/core/tests/test_code_deduplication_integration.py"
            ]
        },
        
        # Performance Benchmarking
        {
            "qualified_name": "testing.performance.benchmarking",
            "type": "concept",
            "domain": "testing.performance",
            "purpose": "Response time and throughput benchmarking - establishes performance baselines",
            "tags": ["performance", "benchmarking", "profiling", "testing"],
            "criticality": "low",
            "examples": [
                "test_service_layer_response_time",
                "test_service_layer_overhead_acceptable"
            ],
            "patterns": [
                "Use time.perf_counter() for accurate timing",
                "Run multiple iterations (N=100+)",
                "Calculate mean/median/p95/p99",
                "Set acceptable thresholds",
                "Profile memory usage for large operations"
            ],
            "performance_notes": "Run performance tests separately with @pytest.mark.performance to avoid slowing CI",
            "examples_code": [
                """
import pytest
import time

@pytest.mark.performance
def test_response_time_acceptable(self):
    times = []
    for _ in range(100):
        start = time.perf_counter()
        result = expensive_operation()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    mean_time = sum(times) / len(times)
    self.assertLess(mean_time, 0.100, "Mean response time > 100ms")
                """
            ],
            "business_value": "Ensures consistent performance and prevents regressions",
            "file_references": [
                "apps/reports/tests/test_refactored_services.py"
            ]
        },
        
        # Load Testing
        {
            "qualified_name": "testing.performance.load_testing",
            "type": "concept",
            "domain": "testing.performance",
            "purpose": "High-volume and concurrent request testing - verifies system behavior under load",
            "tags": ["performance", "load", "concurrency", "testing"],
            "criticality": "low",
            "examples": [
                "test_full_brute_force_attack_scenario",
                "test_distributed_attack_multiple_ips"
            ],
            "patterns": [
                "Use threading/multiprocessing for concurrent tests",
                "Test with realistic user counts (100+ concurrent)",
                "Monitor resource usage (CPU, memory, DB connections)",
                "Test rate limiting under load",
                "Test cache behavior under concurrent access"
            ],
            "performance_notes": "Load tests should run separately - not in standard test suite",
            "antipatterns": [
                "Testing with single user/thread",
                "Not monitoring resource usage",
                "Not testing concurrent writes"
            ],
            "business_value": "Verifies system handles production load without degradation",
            "file_references": [
                "tests/peoples/services/test_login_throttling_service.py (attack scenarios)"
            ]
        },
        
        # Database Performance Testing
        {
            "qualified_name": "testing.performance.database_testing",
            "type": "concept",
            "domain": "testing.performance",
            "purpose": "Database optimization testing - verifies indexes, query plans, and connection pooling",
            "tags": ["performance", "database", "indexes", "testing"],
            "criticality": "medium",
            "patterns": [
                "Test with realistic data volumes (10K+ records)",
                "Use EXPLAIN to verify index usage",
                "Test bulk operations",
                "Test transaction rollback performance",
                "Monitor connection pool exhaustion"
            ],
            "performance_notes": "Use separate test database with production-like data volumes",
            "business_value": "Prevents database bottlenecks and connection pool exhaustion"
        },
        
        # Caching Performance Testing
        {
            "qualified_name": "testing.performance.caching_testing",
            "type": "concept",
            "domain": "testing.performance",
            "purpose": "Cache effectiveness testing - verifies cache hits, TTL, and invalidation",
            "tags": ["performance", "caching", "redis", "testing"],
            "criticality": "medium",
            "examples": [
                "test_cache_error_handling_check_ip_throttle",
                "test_permission_check_caching"
            ],
            "patterns": [
                "Test cache hit rates",
                "Test cache miss behavior",
                "Test TTL expiration",
                "Test cache invalidation on updates",
                "Test Redis failure resilience"
            ],
            "performance_notes": "Cache tests should verify both performance AND correctness",
            "business_value": "Ensures caching provides performance benefits without staleness",
            "file_references": [
                "tests/peoples/services/test_login_throttling_service.py"
            ]
        },
        
        # ===================================================================
        # SERVICE LAYER TESTING PATTERNS (8 concepts)
        # ===================================================================
        
        # Service Test Patterns
        {
            "qualified_name": "testing.service.service_test_patterns",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Service layer testing methodology - patterns for testing business logic in service classes",
            "tags": ["testing", "service-layer", "architecture", "adr-003"],
            "criticality": "high",
            "examples": [
                "test_device_trust_service.py (35+ tests)",
                "test_login_throttling_service.py (40+ tests)",
                "test_user_capability_service.py (35+ tests)"
            ],
            "patterns": [
                "Test service methods in isolation (unit tests)",
                "Mock external dependencies (database, cache, APIs)",
                "Test integration with real database (integration tests)",
                "Use factories for test data creation",
                "Separate happy path, error handling, and edge cases",
                "Test transaction atomicity with rollback scenarios"
            ],
            "service_references": [
                "apps.peoples.services.DeviceTrustService",
                "apps.peoples.services.LoginThrottlingService",
                "apps.peoples.services.UserCapabilityService"
            ],
            "business_value": "Ensures business logic is correct and resilient",
            "file_references": [
                "tests/peoples/services/test_device_trust_service.py",
                "tests/peoples/services/test_login_throttling_service.py",
                "tests/peoples/services/test_user_capability_service.py",
                "SERVICE_LAYER_TESTS_IMPLEMENTATION_SUMMARY.md"
            ]
        },
        
        # Test Fixtures
        {
            "qualified_name": "testing.service.test_fixtures",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Test data setup patterns - reusable fixtures for consistent test environments",
            "tags": ["testing", "fixtures", "setup", "pytest"],
            "criticality": "medium",
            "patterns": [
                "Use pytest fixtures for shared setup",
                "Use Django TestCase.setUp for per-test setup",
                "Use setUpTestData for class-level setup (faster)",
                "Create factory functions for complex objects",
                "Use @pytest.fixture(scope='module') for expensive setup"
            ],
            "examples_code": [
                """
# Pytest fixture
@pytest.fixture
def sample_user(db):
    return People.objects.create(username='test', client=Client.objects.create())

# Django setUp
def setUp(self):
    self.client_obj = Client.objects.create(name='Test Client')
    self.user = People.objects.create(username='test', client=self.client_obj)

# Django setUpTestData (class-level, faster)
@classmethod
def setUpTestData(cls):
    cls.client_obj = Client.objects.create(name='Test Client')
    cls.user = People.objects.create(username='test', client=cls.client_obj)
                """
            ],
            "antipatterns": [
                "Repeating setup code in every test",
                "Using setUp for expensive operations (use setUpTestData)",
                "Creating fixtures with side effects",
                "Not cleaning up resources in tearDown"
            ],
            "business_value": "Faster test execution and consistent test data"
        },
        
        # Factory Pattern
        {
            "qualified_name": "testing.service.factory_pattern",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Test data factory pattern - programmatic creation of test objects with sensible defaults",
            "tags": ["testing", "factory", "pattern", "test-data"],
            "criticality": "medium",
            "patterns": [
                "Use factory_boy for complex object creation",
                "Define factories for all models",
                "Use SubFactory for relationships",
                "Use Faker for realistic data",
                "Override defaults per test"
            ],
            "examples_code": [
                """
import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker()

class ClientFactory(DjangoModelFactory):
    class Meta:
        model = Client
    name = factory.LazyAttribute(lambda _: fake.company())

class PeopleFactory(DjangoModelFactory):
    class Meta:
        model = People
    username = factory.LazyAttribute(lambda _: fake.email())
    client = factory.SubFactory(ClientFactory)

# Usage in tests
user = PeopleFactory()
user_with_custom_client = PeopleFactory(client=my_client)
                """
            ],
            "business_value": "Reduces boilerplate and improves test maintainability"
        },
        
        # Mock vs Integration Tests
        {
            "qualified_name": "testing.service.mock_vs_integration",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Choosing between mock-based unit tests and integration tests with real dependencies",
            "tags": ["testing", "mocking", "integration", "strategy"],
            "criticality": "high",
            "patterns": [
                "Unit tests: Mock external dependencies (DB, cache, APIs)",
                "Integration tests: Use real database and cache",
                "Mock slow/unreliable external services (APIs, webhooks)",
                "Use real DB for data integrity tests",
                "Use unittest.mock.patch for method-level mocking"
            ],
            "examples_code": [
                """
# Unit test with mocking
from unittest.mock import patch, MagicMock

@patch('apps.peoples.services.cache')
def test_throttling_with_mock_cache(self, mock_cache):
    mock_cache.get.return_value = 5  # Mock cache hit
    service = LoginThrottlingService()
    result = service.check_ip_throttle('192.168.1.1')
    self.assertTrue(result['is_locked'])

# Integration test with real database
def test_device_trust_integration(self):
    # Uses real database
    device = DeviceInfo.objects.create(user=self.user, device_id='test123')
    service = DeviceTrustService()
    result = service.validate_device(self.user, 'test123')
    self.assertEqual(result['trust_score'], 100)
                """
            ],
            "antipatterns": [
                "Mocking everything (no integration tests)",
                "No mocks (tests are slow and brittle)",
                "Mocking Django ORM (use real DB instead)",
                "Not resetting mocks between tests"
            ],
            "business_value": "Balanced test suite: fast unit tests + reliable integration tests",
            "file_references": [
                "tests/peoples/services/test_login_throttling_service.py (mixed approach)"
            ]
        },
        
        # Error Handling Tests
        {
            "qualified_name": "testing.service.error_handling_tests",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Testing error scenarios and exception handling - verifies graceful degradation",
            "tags": ["testing", "error-handling", "resilience", "exceptions"],
            "criticality": "high",
            "examples": [
                "test_validate_device_database_error_handling",
                "test_cache_error_handling_check_ip_throttle",
                "test_capability_update_validation_errors"
            ],
            "patterns": [
                "Test all exception paths",
                "Test database errors (IntegrityError, OperationalError)",
                "Test cache failures (Redis down)",
                "Test external API failures",
                "Verify error logging",
                "Verify fallback behavior"
            ],
            "examples_code": [
                """
from unittest.mock import patch
from django.db import OperationalError

@patch('apps.peoples.models.DeviceInfo.objects.get')
def test_database_error_handling(self, mock_get):
    mock_get.side_effect = OperationalError("DB connection lost")
    service = DeviceTrustService()
    result = service.validate_device(self.user, 'device123')
    # Should fallback gracefully
    self.assertFalse(result['success'])
    self.assertIn('error', result)
                """
            ],
            "antipatterns": [
                "Only testing happy path",
                "Not testing database errors",
                "Not testing cache failures",
                "Catching generic exceptions (except Exception)"
            ],
            "business_value": "Ensures system resilience and graceful degradation",
            "file_references": [
                "tests/peoples/services/test_device_trust_service.py",
                "tests/peoples/services/test_login_throttling_service.py"
            ]
        },
        
        # Transaction Atomicity Tests
        {
            "qualified_name": "testing.service.transaction_atomicity_tests",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Testing database transaction handling - verifies rollback on errors",
            "tags": ["testing", "transactions", "atomicity", "database"],
            "criticality": "high",
            "patterns": [
                "Test transaction rollback on exception",
                "Verify database state after rollback",
                "Test nested transactions",
                "Test savepoints",
                "Use transaction.atomic() in services"
            ],
            "examples_code": [
                """
from django.db import transaction
from django.test import TransactionTestCase

class ServiceTransactionTest(TransactionTestCase):
    def test_rollback_on_error(self):
        initial_count = MyModel.objects.count()
        
        with self.assertRaises(ValueError):
            with transaction.atomic():
                MyModel.objects.create(name='test')
                raise ValueError("Simulated error")
        
        # Should rollback to initial state
        self.assertEqual(MyModel.objects.count(), initial_count)
                """
            ],
            "antipatterns": [
                "Not testing rollback behavior",
                "Using TestCase instead of TransactionTestCase for transaction tests",
                "Not verifying database state after rollback"
            ],
            "business_value": "Prevents partial writes and data corruption",
            "file_references": [
                "tests/peoples/services/test_user_capability_service.py"
            ]
        },
        
        # Security Boundary Tests
        {
            "qualified_name": "testing.service.security_boundary_tests",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Testing security boundaries in service layer - verifies permission checks and data isolation",
            "tags": ["testing", "security", "service-layer", "boundaries"],
            "criticality": "high",
            "examples": [
                "test_system_capabilities_protected",
                "test_security_escalation_flow"
            ],
            "patterns": [
                "Test permission checks before operations",
                "Test tenant isolation in multi-tenant services",
                "Test ownership validation",
                "Test privilege escalation prevention",
                "Test input sanitization"
            ],
            "business_value": "Prevents security violations in business logic layer",
            "file_references": [
                "tests/peoples/services/test_user_capability_service.py",
                "tests/peoples/services/test_device_trust_service.py"
            ]
        },
        
        # Service Integration Tests
        {
            "qualified_name": "testing.service.integration_tests",
            "type": "concept",
            "domain": "testing.service",
            "purpose": "Testing service interactions - verifies services work together correctly",
            "tags": ["testing", "integration", "service-layer", "workflow"],
            "criticality": "medium",
            "examples": [
                "test_enrollment_flow_integration",
                "test_security_escalation_flow",
                "test_full_brute_force_attack_scenario"
            ],
            "patterns": [
                "Test multi-service workflows",
                "Test service-to-service communication",
                "Test event-driven interactions",
                "Test transaction boundaries across services",
                "Test error propagation"
            ],
            "business_value": "Ensures services integrate correctly in production workflows",
            "file_references": [
                "tests/peoples/services/test_device_trust_service.py",
                "tests/peoples/services/test_login_throttling_service.py"
            ]
        },
        
        # ===================================================================
        # TEST ORGANIZATION PATTERNS (6 concepts)
        # ===================================================================
        
        # Test Naming Conventions
        {
            "qualified_name": "testing.organization.naming_conventions",
            "type": "concept",
            "domain": "testing.organization",
            "purpose": "Consistent test naming for clarity and discoverability",
            "tags": ["testing", "conventions", "organization"],
            "criticality": "medium",
            "patterns": [
                "test_<method>_<scenario>_<expected_result>",
                "test_user_cannot_access_other_tenant_profile",
                "test_device_trust_score_increases_with_biometric",
                "Use descriptive names (not test1, test2)",
                "Group related tests in classes"
            ],
            "examples": [
                "Good: test_login_throttle_locks_after_5_attempts",
                "Bad: test_throttle",
                "Good: test_api_returns_404_for_invalid_user_id",
                "Bad: test_api"
            ],
            "antipatterns": [
                "Generic names (test_basic, test_simple)",
                "Names that don't explain what's tested",
                "Mixing multiple scenarios in one test"
            ],
            "business_value": "Faster debugging and better test documentation"
        },
        
        # Pytest Markers
        {
            "qualified_name": "testing.organization.pytest_markers",
            "type": "concept",
            "domain": "testing.organization",
            "purpose": "Test categorization using pytest markers for selective execution",
            "tags": ["testing", "pytest", "markers", "organization"],
            "criticality": "medium",
            "patterns": [
                "@pytest.mark.unit - Unit tests",
                "@pytest.mark.integration - Integration tests",
                "@pytest.mark.security - Security tests",
                "@pytest.mark.performance - Performance tests (slow)",
                "@pytest.mark.idor - IDOR security tests",
                "Configure markers in pytest.ini"
            ],
            "examples_code": [
                """
# pytest.ini
[pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    security: Security tests
    performance: Performance tests (slow)
    idor: IDOR security tests

# Test file
import pytest

@pytest.mark.unit
@pytest.mark.security
def test_permission_check():
    pass

# Run specific markers
# pytest -m unit
# pytest -m "security and not performance"
                """
            ],
            "business_value": "Faster CI/CD by running subsets of tests",
            "file_references": [
                "pytest.ini",
                "IDOR_TEST_COVERAGE_REPORT.md (marker usage examples)"
            ]
        },
        
        # Test Coverage Goals
        {
            "qualified_name": "testing.organization.coverage_goals",
            "type": "concept",
            "domain": "testing.organization",
            "purpose": "Test coverage targets and measurement strategies",
            "tags": ["testing", "coverage", "quality", "metrics"],
            "criticality": "medium",
            "patterns": [
                "Target: 80%+ overall coverage",
                "Target: 90%+ for security-critical code",
                "Target: 70%+ for service layer",
                "Use pytest-cov for measurement",
                "Generate HTML reports for analysis",
                "Exclude migrations and vendored code"
            ],
            "examples_code": [
                """
# Generate coverage report
pytest --cov=apps --cov-report=html:coverage_reports/html --cov-report=term-missing -v

# .coveragerc
[run]
omit =
    */migrations/*
    */tests/*
    */venv/*
    */vendored/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
                """
            ],
            "business_value": "Measurable code quality and confidence in deployments",
            "file_references": [
                "docs/testing/TESTING_AND_QUALITY_GUIDE.md",
                "SERVICE_TEST_COVERAGE_REPORT.md"
            ]
        },
        
        # Test File Organization
        {
            "qualified_name": "testing.organization.file_structure",
            "type": "concept",
            "domain": "testing.organization",
            "purpose": "Test directory structure and file organization patterns",
            "tags": ["testing", "organization", "structure"],
            "criticality": "low",
            "patterns": [
                "apps/<app>/tests/ - App-specific tests",
                "tests/unit/ - Cross-domain unit tests",
                "tests/integration/ - Integration flows spanning apps",
                "tests/performance/ - Performance tests (slow)",
                "test_<module>.py - Mirror source structure",
                "test_<feature>_<aspect>.py - Feature tests"
            ],
            "examples": [
                "apps/peoples/tests/test_idor_security.py",
                "apps/peoples/tests/services/test_device_trust_service.py",
                "tests/integration/test_attendance_workflow.py"
            ],
            "business_value": "Easy test discovery and maintenance"
        },
        
        # Test Data Management
        {
            "qualified_name": "testing.organization.test_data_management",
            "type": "concept",
            "domain": "testing.organization",
            "purpose": "Managing test data - fixtures, factories, and sample data",
            "tags": ["testing", "data", "fixtures", "organization"],
            "criticality": "medium",
            "patterns": [
                "Use factories for object creation",
                "Use fixtures for shared setup",
                "Use sample data files for complex inputs",
                "Clean up test data in tearDown",
                "Use TransactionTestCase for database tests"
            ],
            "antipatterns": [
                "Hardcoding test data in tests",
                "Sharing mutable test data between tests",
                "Not cleaning up test files/uploads",
                "Using production data in tests"
            ],
            "business_value": "Reliable, isolated tests with consistent data"
        },
        
        # Test Documentation
        {
            "qualified_name": "testing.organization.test_documentation",
            "type": "concept",
            "domain": "testing.organization",
            "purpose": "Documenting test suites and test strategies",
            "tags": ["testing", "documentation", "organization"],
            "criticality": "low",
            "patterns": [
                "Write docstrings for test classes",
                "Document test fixtures and helpers",
                "Create test coverage reports",
                "Document known issues/limitations",
                "Link tests to requirements/tickets"
            ],
            "examples_code": [
                '''
class PeoplesIDORTestCase(TestCase):
    """
    IDOR security tests for Peoples app.
    
    Verifies:
    - Cross-tenant data isolation (tests 1-4)
    - Cross-user privacy (tests 5-7)
    - Permission boundaries (tests 8-10)
    - Input validation (tests 11-13)
    
    See: IDOR_TEST_COVERAGE_REPORT.md
    """
    
    def test_user_cannot_access_other_tenant_profile(self):
        """Verify users cannot view profiles from other tenants."""
        # Test implementation...
                '''
            ],
            "business_value": "Better test understanding and maintenance",
            "file_references": [
                "IDOR_TEST_COVERAGE_REPORT.md",
                "SERVICE_LAYER_TESTS_IMPLEMENTATION_SUMMARY.md"
            ]
        },
        
        # ===================================================================
        # TEST ANTIPATTERNS (10 concepts)
        # ===================================================================
        
        # Antipattern: Testing Implementation Details
        {
            "qualified_name": "testing.antipatterns.testing_implementation_details",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Testing private methods and implementation details instead of behavior",
            "tags": ["testing", "antipattern", "bad-practice"],
            "criticality": "medium",
            "why_bad": "Tests break when implementation changes, even if behavior is unchanged",
            "examples": [
                "Bad: Testing private methods directly",
                "Bad: Asserting on internal variable names",
                "Bad: Mocking every internal method call",
                "Good: Test public API and observable behavior"
            ],
            "fix": "Test behavior through public interfaces, not implementation details"
        },
        
        # Antipattern: Brittle Tests
        {
            "qualified_name": "testing.antipatterns.brittle_tests",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Tests that break on minor changes unrelated to tested behavior",
            "tags": ["testing", "antipattern", "fragile"],
            "criticality": "high",
            "why_bad": "Tests become maintenance burden and lose developer trust",
            "examples": [
                "Bad: Hard-coding exact error messages",
                "Bad: Asserting on exact HTML output",
                "Bad: Depending on test execution order",
                "Bad: Hard-coding database IDs"
            ],
            "fix": "Use flexible assertions, test isolation, and avoid hard-coded values"
        },
        
        # Antipattern: Slow Tests
        {
            "qualified_name": "testing.antipatterns.slow_tests",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Tests that take too long to run, slowing development",
            "tags": ["testing", "antipattern", "performance"],
            "criticality": "medium",
            "why_bad": "Developers skip running tests, reducing quality",
            "examples": [
                "Bad: Using time.sleep() in tests",
                "Bad: Creating unnecessary database records",
                "Bad: Not using setUpTestData for class-level fixtures",
                "Bad: Running performance tests in main suite"
            ],
            "fix": "Use mocks, optimize fixtures, separate slow tests with markers"
        },
        
        # Antipattern: Happy Path Only
        {
            "qualified_name": "testing.antipatterns.happy_path_only",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Only testing successful scenarios, ignoring error cases",
            "tags": ["testing", "antipattern", "incomplete"],
            "criticality": "high",
            "why_bad": "Production errors are not caught, leading to runtime failures",
            "examples": [
                "Bad: Only testing valid inputs",
                "Bad: Not testing error handling",
                "Bad: Not testing edge cases",
                "Bad: Not testing unauthorized access"
            ],
            "fix": "Test happy path + error cases + edge cases + security boundaries"
        },
        
        # Antipattern: Shared Mutable State
        {
            "qualified_name": "testing.antipatterns.shared_mutable_state",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Tests that share mutable state, causing test interdependencies",
            "tags": ["testing", "antipattern", "isolation"],
            "criticality": "high",
            "why_bad": "Tests fail intermittently based on execution order",
            "examples": [
                "Bad: Modifying class-level variables in tests",
                "Bad: Not cleaning up files/database records",
                "Bad: Reusing objects across tests",
                "Bad: Global state modifications"
            ],
            "fix": "Isolate tests, clean up in tearDown, use fresh objects per test"
        },
        
        # Antipattern: Test Code Duplication
        {
            "qualified_name": "testing.antipatterns.test_code_duplication",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Duplicating setup code across tests instead of using fixtures",
            "tags": ["testing", "antipattern", "dry"],
            "criticality": "medium",
            "why_bad": "Harder to maintain, inconsistent test data",
            "examples": [
                "Bad: Copy-pasting setup code in every test",
                "Bad: Not using fixtures or factories",
                "Bad: Duplicating helper functions"
            ],
            "fix": "Use fixtures, factories, and helper functions to DRY up tests"
        },
        
        # Antipattern: Unclear Test Failures
        {
            "qualified_name": "testing.antipatterns.unclear_test_failures",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Assertions without clear failure messages",
            "tags": ["testing", "antipattern", "debugging"],
            "criticality": "medium",
            "why_bad": "Hard to debug test failures",
            "examples": [
                "Bad: assertTrue(result) without message",
                "Bad: Generic error messages",
                "Good: self.assertTrue(result, f'Expected trust_score=100, got {result}')"
            ],
            "fix": "Add descriptive assertion messages with actual/expected values"
        },
        
        # Antipattern: Testing External Services
        {
            "qualified_name": "testing.antipatterns.testing_external_services",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Calling real external APIs/services in unit tests",
            "tags": ["testing", "antipattern", "external"],
            "criticality": "high",
            "why_bad": "Tests are slow, brittle, and may cost money or hit rate limits",
            "examples": [
                "Bad: Calling real payment APIs",
                "Bad: Sending real emails",
                "Bad: Making real HTTP requests",
                "Good: Mock external services"
            ],
            "fix": "Mock external services, use integration tests with test environments"
        },
        
        # Antipattern: Generic Exception Catching
        {
            "qualified_name": "testing.antipatterns.generic_exception_catching",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Using except Exception in tests, hiding real errors",
            "tags": ["testing", "antipattern", "exceptions"],
            "criticality": "high",
            "why_bad": "Hides unexpected errors and makes debugging harder",
            "examples": [
                "Bad: try/except Exception: pass",
                "Bad: assertRaises(Exception)",
                "Good: assertRaises(SpecificException)"
            ],
            "fix": "Catch specific exceptions, use assertRaises with exact exception types"
        },
        
        # Antipattern: Not Testing Backwards Compatibility
        {
            "qualified_name": "testing.antipatterns.not_testing_backwards_compatibility",
            "type": "antipattern",
            "domain": "testing.antipatterns",
            "purpose": "What NOT to do: Breaking APIs without testing backwards compatibility",
            "tags": ["testing", "antipattern", "compatibility"],
            "criticality": "medium",
            "why_bad": "Breaks integrations and client applications",
            "examples": [
                "Bad: Removing API fields without deprecation tests",
                "Bad: Changing response formats without version tests",
                "Good: Test old and new API versions"
            ],
            "fix": "Test backwards compatibility, use deprecation warnings"
        },
        
        # ===================================================================
        # TESTING TOOLS & UTILITIES (5 concepts)
        # ===================================================================
        
        # Pytest Framework
        {
            "qualified_name": "testing.tools.pytest_framework",
            "type": "tool",
            "domain": "testing.tools",
            "purpose": "Pytest testing framework - modern Python testing with fixtures and plugins",
            "tags": ["testing", "pytest", "framework"],
            "criticality": "high",
            "features": [
                "Fixtures for test setup/teardown",
                "Markers for test categorization",
                "Parametrize for data-driven tests",
                "Plugins (pytest-cov, pytest-django)",
                "Detailed assertion introspection"
            ],
            "file_references": [
                "pytest.ini",
                "conftest.py"
            ]
        },
        
        # Coverage.py
        {
            "qualified_name": "testing.tools.coverage_py",
            "type": "tool",
            "domain": "testing.tools",
            "purpose": "Code coverage measurement tool - identifies untested code",
            "tags": ["testing", "coverage", "metrics"],
            "criticality": "medium",
            "features": [
                "Line coverage measurement",
                "Branch coverage",
                "HTML reports",
                "Missing line identification",
                "Integration with pytest-cov"
            ]
        },
        
        # Django TestCase
        {
            "qualified_name": "testing.tools.django_testcase",
            "type": "tool",
            "domain": "testing.tools",
            "purpose": "Django's TestCase for database-backed tests with transaction support",
            "tags": ["testing", "django", "database"],
            "criticality": "high",
            "features": [
                "Transaction wrapping for test isolation",
                "Test client for HTTP requests",
                "Fixture loading",
                "Assertion helpers",
                "Test database management"
            ]
        },
        
        # Factory Boy
        {
            "qualified_name": "testing.tools.factory_boy",
            "type": "tool",
            "domain": "testing.tools",
            "purpose": "Test fixture library - generates test data with relationships",
            "tags": ["testing", "fixtures", "factory"],
            "criticality": "medium",
            "features": [
                "Object factory definitions",
                "Relationship handling (SubFactory)",
                "Lazy attributes",
                "Faker integration",
                "Build vs create strategies"
            ]
        },
        
        # Mock Library
        {
            "qualified_name": "testing.tools.mock_library",
            "type": "tool",
            "domain": "testing.tools",
            "purpose": "unittest.mock - mocking library for isolating units under test",
            "tags": ["testing", "mocking", "isolation"],
            "criticality": "high",
            "features": [
                "Mock objects",
                "Patch decorator/context manager",
                "MagicMock for magic methods",
                "Call assertions",
                "Side effects"
            ]
        }
    ]
    
    # Bulk register all testing patterns
    OntologyRegistry.bulk_register(testing_patterns)
    
    return len(testing_patterns)


# Auto-register on module import (if registry available)
try:
    count = register_testing_knowledge()
    logger.info(f"✅ Registered {count} testing knowledge concepts")
except Exception as e:
    logger.error(f"⚠️ Could not auto-register testing knowledge: {e}")
