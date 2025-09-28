"""
Comprehensive tests for service layer integration.

Tests the base service infrastructure, transaction management,
and service registry functionality with high coverage.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError

from apps.core.services import (
    BaseService,
    ServiceException,
    TransactionManager,
    transaction_manager,
    with_transaction,
    ServiceRegistry,
    service_registry,
    injectable,
    inject,
    get_service
)
from apps.core.services.base_service import ServiceMetrics
from apps.core.services.service_registry import ServiceScope, ServiceRegistration
from apps.core.exceptions import BusinessLogicException, DatabaseException


class MockService(BaseService):
    """Mock service for testing."""

    def __init__(self, dependency_service=None):
        super().__init__()
        self.dependency_service = dependency_service
        self.call_history = []

    @BaseService.monitor_performance("test_method")
    def test_method(self, value):
        """Test method with performance monitoring."""
        self.call_history.append(f"test_method_{value}")
        return f"result_{value}"

    @BaseService.monitor_performance("failing_method")
    def failing_method(self):
        """Test method that raises an exception."""
        raise ValueError("Test error")

    def get_service_name(self) -> str:
        return "MockService"


class MockDependentService(BaseService):
    """Mock service with dependencies for testing."""

    def __init__(self, mock_service: MockService):
        super().__init__()
        self.mock_service = mock_service

    def get_service_name(self) -> str:
        return "MockDependentService"


class TestServiceMetrics(TestCase):
    """Test service metrics functionality."""

    def setUp(self):
        self.metrics = ServiceMetrics()

    def test_record_call_success(self):
        """Test recording successful calls."""
        self.metrics.record_call(1.5)
        self.metrics.record_call(2.0)

        self.assertEqual(self.metrics.call_count, 2)
        self.assertEqual(self.metrics.total_duration, 3.5)
        self.assertEqual(self.metrics.error_count, 0)
        self.assertEqual(self.metrics.average_duration, 1.75)

    def test_record_call_with_error(self):
        """Test recording calls with errors."""
        self.metrics.record_call(1.0, error=True)
        self.metrics.record_call(2.0, error=False)

        self.assertEqual(self.metrics.call_count, 2)
        self.assertEqual(self.metrics.error_count, 1)
        self.assertEqual(self.metrics.error_rate, 50.0)

    def test_cache_metrics(self):
        """Test cache hit/miss metrics."""
        self.metrics.record_cache_hit()
        self.metrics.record_cache_hit()
        self.metrics.record_cache_miss()

        self.assertEqual(self.metrics.cache_hits, 2)
        self.assertEqual(self.metrics.cache_misses, 1)
        self.assertEqual(self.metrics.cache_hit_rate, 66.67)  # approximately

    def test_empty_metrics(self):
        """Test metrics with no data."""
        self.assertEqual(self.metrics.average_duration, 0.0)
        self.assertEqual(self.metrics.error_rate, 0.0)
        self.assertEqual(self.metrics.cache_hit_rate, 0.0)


class TestBaseService(TestCase):
    """Test base service functionality."""

    def setUp(self):
        self.service = MockService()

    def test_service_initialization(self):
        """Test service initialization."""
        self.assertEqual(self.service.service_name, "MockService")
        self.assertIsInstance(self.service.metrics, ServiceMetrics)
        self.assertEqual(self.service.metrics.call_count, 0)

    def test_performance_monitoring(self):
        """Test performance monitoring decorator."""
        result = self.service.test_method("test_value")

        self.assertEqual(result, "result_test_value")
        self.assertEqual(self.service.metrics.call_count, 1)
        self.assertTrue(self.service.metrics.total_duration > 0)
        self.assertEqual(self.service.metrics.error_count, 0)

    def test_performance_monitoring_with_error(self):
        """Test performance monitoring with exceptions."""
        with self.assertRaises(ServiceException):
            self.service.failing_method()

        self.assertEqual(self.service.metrics.call_count, 1)
        self.assertEqual(self.service.metrics.error_count, 1)
        self.assertEqual(self.service.metrics.error_rate, 100.0)

    @patch('apps.core.services.base_service.cache')
    def test_cache_operations(self, mock_cache):
        """Test cache operations."""
        mock_cache.get.return_value = "cached_value"
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True

        # Test cache hit
        result = self.service.get_cached_data("test_key")
        self.assertEqual(result, "cached_value")
        self.assertEqual(self.service.metrics.cache_hits, 1)

        # Test cache set
        success = self.service.set_cached_data("test_key", "test_value")
        self.assertTrue(success)

        # Test cache invalidation
        success = self.service.invalidate_cache("test_key")
        self.assertTrue(success)

        # Test cache miss
        mock_cache.get.return_value = None
        result = self.service.get_cached_data("missing_key")
        self.assertIsNone(result)
        self.assertEqual(self.service.metrics.cache_misses, 1)

    def test_business_rule_validation_success(self):
        """Test successful business rule validation."""
        data = {"value": 10, "name": "test"}
        rules = {
            "positive_value": lambda d: d["value"] > 0,
            "has_name": lambda d: bool(d["name"])
        }

        # Should not raise an exception
        self.service.validate_business_rules(data, rules)

    def test_business_rule_validation_failure(self):
        """Test business rule validation failure."""
        data = {"value": -5, "name": ""}
        rules = {
            "positive_value": lambda d: d["value"] > 0,
            "has_name": lambda d: bool(d["name"])
        }

        with self.assertRaises(BusinessLogicException) as context:
            self.service.validate_business_rules(data, rules)

        self.assertIn("Business rule violation", str(context.exception))

    def test_get_service_metrics(self):
        """Test service metrics retrieval."""
        # Generate some metrics
        self.service.test_method("test1")
        self.service.test_method("test2")

        metrics = self.service.get_service_metrics()

        self.assertEqual(metrics['service_name'], "MockService")
        self.assertEqual(metrics['call_count'], 2)
        self.assertEqual(metrics['error_count'], 0)
        self.assertTrue(metrics['total_duration'] > 0)


class TestTransactionManager(TransactionTestCase):
    """Test transaction manager functionality."""

    def setUp(self):
        self.transaction_manager = TransactionManager()

    def test_atomic_operation_success(self):
        """Test successful atomic operation."""
        executed = False

        with self.transaction_manager.atomic_operation():
            executed = True

        self.assertTrue(executed)

    def test_atomic_operation_rollback(self):
        """Test atomic operation rollback on exception."""
        with self.assertRaises(DatabaseException):
            with self.transaction_manager.atomic_operation():
                raise IntegrityError("Test integrity error")

    def test_saga_creation_and_execution(self):
        """Test saga pattern implementation."""
        saga_id = self.transaction_manager.create_saga("test_saga")
        self.assertEqual(saga_id, "test_saga")
        self.assertIn(saga_id, self.transaction_manager.active_sagas)

    def test_saga_step_addition(self):
        """Test adding steps to saga."""
        saga_id = self.transaction_manager.create_saga("test_saga")

        def test_step():
            return "step_result"

        def compensate_step(result):
            return f"compensated_{result}"

        self.transaction_manager.add_saga_step(
            saga_id,
            "test_step",
            test_step,
            compensate_step
        )

        saga_status = self.transaction_manager.get_saga_status(saga_id)
        self.assertEqual(saga_status['total_steps'], 1)
        self.assertEqual(saga_status['steps'][0]['name'], "test_step")

    def test_saga_execution_success(self):
        """Test successful saga execution."""
        saga_id = self.transaction_manager.create_saga("success_saga")

        def step1():
            return "result1"

        def step2():
            return "result2"

        self.transaction_manager.add_saga_step(saga_id, "step1", step1)
        self.transaction_manager.add_saga_step(saga_id, "step2", step2)

        result = self.transaction_manager.execute_saga(saga_id)

        self.assertEqual(result['status'], 'committed')
        self.assertEqual(result['steps_executed'], 2)
        self.assertNotIn(saga_id, self.transaction_manager.active_sagas)

    def test_saga_execution_with_compensation(self):
        """Test saga execution with compensation on failure."""
        saga_id = self.transaction_manager.create_saga("compensation_saga")

        def step1():
            return "result1"

        def compensate1(result):
            return f"compensated_{result}"

        def failing_step():
            raise ValueError("Step failed")

        self.transaction_manager.add_saga_step(saga_id, "step1", step1, compensate1)
        self.transaction_manager.add_saga_step(saga_id, "failing_step", failing_step)

        result = self.transaction_manager.execute_saga(saga_id)

        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['compensation_executed'])
        self.assertNotIn(saga_id, self.transaction_manager.active_sagas)

    def test_with_transaction_decorator(self):
        """Test with_transaction decorator."""
        @with_transaction()
        def test_function():
            return "success"

        result = test_function()
        self.assertEqual(result, "success")

    def test_multi_database_transaction(self):
        """Test multi-database transaction coordination."""
        databases = ['default']  # Using only default for test

        executed = False
        with self.transaction_manager.multi_database_transaction(databases):
            executed = True

        self.assertTrue(executed)


class TestServiceRegistry(TestCase):
    """Test service registry functionality."""

    def setUp(self):
        # Create a clean registry for each test
        self.registry = ServiceRegistry()

    def test_service_registration(self):
        """Test basic service registration."""
        self.registry.register(BaseService, MockService)

        self.assertTrue(self.registry.is_registered(BaseService))
        registration = self.registry._registrations['BaseService']
        self.assertEqual(registration.implementation, MockService)
        self.assertEqual(registration.scope, ServiceScope.SINGLETON)

    def test_service_registration_with_custom_scope(self):
        """Test service registration with custom scope."""
        self.registry.register(
            BaseService,
            MockService,
            scope=ServiceScope.TRANSIENT
        )

        registration = self.registry._registrations['BaseService']
        self.assertEqual(registration.scope, ServiceScope.TRANSIENT)

    def test_singleton_service_retrieval(self):
        """Test singleton service retrieval."""
        self.registry.register(BaseService, MockService, scope=ServiceScope.SINGLETON)

        service1 = self.registry.get(BaseService)
        service2 = self.registry.get(BaseService)

        self.assertIsInstance(service1, MockService)
        self.assertIs(service1, service2)  # Same instance

    def test_transient_service_retrieval(self):
        """Test transient service retrieval."""
        self.registry.register(BaseService, MockService, scope=ServiceScope.TRANSIENT)

        service1 = self.registry.get(BaseService)
        service2 = self.registry.get(BaseService)

        self.assertIsInstance(service1, MockService)
        self.assertIsInstance(service2, MockService)
        self.assertIsNot(service1, service2)  # Different instances

    def test_request_scoped_service_retrieval(self):
        """Test request-scoped service retrieval."""
        self.registry.register(BaseService, MockService, scope=ServiceScope.REQUEST)

        service1 = self.registry.get(BaseService, request_id="req1")
        service2 = self.registry.get(BaseService, request_id="req1")
        service3 = self.registry.get(BaseService, request_id="req2")

        self.assertIs(service1, service2)  # Same request, same instance
        self.assertIsNot(service1, service3)  # Different request, different instance

    def test_dependency_injection(self):
        """Test automatic dependency injection."""
        # Register dependencies
        self.registry.register(MockService, MockService, scope=ServiceScope.SINGLETON)

        # Mock type hints for dependency injection
        with patch('apps.core.services.service_registry.get_type_hints') as mock_get_hints:
            mock_get_hints.return_value = {'mock_service': MockService}
            self.registry.register(MockDependentService, MockDependentService)

        # Get service with injected dependency
        service = self.registry.get(MockDependentService)
        self.assertIsInstance(service, MockDependentService)

    def test_mock_service_registration(self):
        """Test mock service registration for testing."""
        mock_impl = Mock()
        self.registry.register_mock(BaseService, mock_impl)

        service = self.registry.get(BaseService)
        self.assertIsNotNone(service)

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        # This is a simplified test - in practice would need more complex setup
        with self.assertRaises(ValueError) as context:
            # Simulate circular dependency
            self.registry._resolution_stack = ['ServiceA', 'ServiceB']
            self.registry.get('ServiceA')

        self.assertIn("Circular dependency detected", str(context.exception))

    def test_service_unregistration(self):
        """Test service unregistration."""
        self.registry.register(BaseService, MockService)
        self.assertTrue(self.registry.is_registered(BaseService))

        self.registry.unregister(BaseService)
        self.assertFalse(self.registry.is_registered(BaseService))

    def test_request_scope_cleanup(self):
        """Test request scope cleanup."""
        self.registry.register(BaseService, MockService, scope=ServiceScope.REQUEST)

        service = self.registry.get(BaseService, request_id="req1")
        self.assertIsNotNone(service)

        self.registry.clear_request_scope("req1")
        # Should create a new instance after cleanup
        new_service = self.registry.get(BaseService, request_id="req1")
        self.assertIsNot(service, new_service)

    def test_get_registered_services(self):
        """Test getting registered services information."""
        self.registry.register(BaseService, MockService)

        services = self.registry.get_registered_services()
        self.assertIn('BaseService', services)

        service_info = services['BaseService']
        self.assertEqual(service_info['implementation'], 'MockService')
        self.assertEqual(service_info['scope'], 'singleton')

    def test_service_metrics(self):
        """Test service registry metrics."""
        self.registry.register(BaseService, MockService)

        metrics = self.registry.get_service_metrics()
        self.assertEqual(metrics['total_registrations'], 1)
        self.assertEqual(metrics['singleton_instances'], 0)  # Not instantiated yet

        # Instantiate service
        self.registry.get(BaseService)

        updated_metrics = self.registry.get_service_metrics()
        self.assertEqual(updated_metrics['singleton_instances'], 1)


class TestServiceDecorators(TestCase):
    """Test service-related decorators."""

    def setUp(self):
        self.registry = ServiceRegistry()

    def test_injectable_decorator(self):
        """Test injectable decorator."""
        @injectable(BaseService)
        class TestService(BaseService):
            def get_service_name(self):
                return "TestService"

        # Should be auto-registered
        service = self.registry.get(BaseService)
        self.assertIsInstance(service, TestService)

    def test_inject_decorator(self):
        """Test inject decorator."""
        self.registry.register(MockService, MockService)

        @inject(MockService)
        def test_function(data, MockService=None):
            return MockService.test_method(data)

        result = test_function("test_data")
        self.assertEqual(result, "result_test_data")

    def test_get_service_convenience_function(self):
        """Test get_service convenience function."""
        self.registry.register(MockService, MockService)

        service = get_service(MockService)
        self.assertIsInstance(service, MockService)


@pytest.mark.integration
class TestServiceLayerIntegration(TestCase):
    """Integration tests for the complete service layer."""

    def test_end_to_end_service_workflow(self):
        """Test complete service workflow from registration to execution."""
        # Register service
        service_registry.register(MockService, MockService, scope=ServiceScope.SINGLETON)

        # Get service
        service = get_service(MockService)

        # Execute service method
        result = service.test_method("integration_test")

        # Verify results
        self.assertEqual(result, "result_integration_test")
        self.assertEqual(service.metrics.call_count, 1)

        # Verify singleton behavior
        service2 = get_service(MockService)
        self.assertIs(service, service2)

    def test_transaction_and_service_integration(self):
        """Test integration between transactions and services."""
        service_registry.register(MockService, MockService)

        @with_transaction()
        def transactional_service_call():
            service = get_service(MockService)
            return service.test_method("transactional")

        result = transactional_service_call()
        self.assertEqual(result, "result_transactional")