"""
Service Registry and Dependency Injection Framework

Provides:
- Service registration and discovery
- Dependency injection
- Service lifecycle management
- Runtime service switching
- Mock service support for testing
"""

import logging
import threading
from typing import Any, Dict, Type, Optional, Callable, Union, get_type_hints
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from apps.core.services.base_service import BaseService

logger = logging.getLogger(__name__)


class ServiceScope(Enum):
    """Service instance scope enumeration."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    REQUEST = "request"


@dataclass
class ServiceRegistration:
    """Service registration metadata."""
    service_type: Type[BaseService]
    implementation: Type[BaseService]
    scope: ServiceScope = ServiceScope.SINGLETON
    factory: Optional[Callable] = None
    dependencies: Dict[str, str] = field(default_factory=dict)
    is_mock: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ServiceRegistry:
    """
    Central registry for service management and dependency injection.

    Features:
    - Service registration with various scopes
    - Automatic dependency resolution
    - Runtime service switching
    - Mock service support
    - Thread-safe singleton management
    """

    def __init__(self):
        self._registrations: Dict[str, ServiceRegistration] = {}
        self._singletons: Dict[str, BaseService] = {}
        self._request_scoped: Dict[str, Dict[str, BaseService]] = defaultdict(dict)
        self._lock = threading.Lock()
        self._resolution_stack: List[str] = []

    def register(
        self,
        service_interface: Type[BaseService],
        implementation: Type[BaseService],
        scope: ServiceScope = ServiceScope.SINGLETON,
        factory: Optional[Callable] = None,
        name: Optional[str] = None
    ) -> 'ServiceRegistry':
        """
        Register a service implementation.

        Args:
            service_interface: Interface type (base class)
            implementation: Concrete implementation class
            scope: Service instance scope
            factory: Optional factory function
            name: Optional service name (defaults to interface name)

        Returns:
            Self for method chaining
        """
        service_name = name or service_interface.__name__

        # Validate implementation
        if not issubclass(implementation, service_interface):
            raise ValueError(f"{implementation.__name__} must implement {service_interface.__name__}")

        # Extract dependencies from type hints
        dependencies = self._extract_dependencies(implementation)

        registration = ServiceRegistration(
            service_type=service_interface,
            implementation=implementation,
            scope=scope,
            factory=factory,
            dependencies=dependencies
        )

        with self._lock:
            self._registrations[service_name] = registration

        logger.debug(f"Registered service: {service_name} -> {implementation.__name__} (scope: {scope.value})")
        return self

    def register_mock(
        self,
        service_interface: Type[BaseService],
        mock_implementation: Any,
        name: Optional[str] = None
    ) -> 'ServiceRegistry':
        """
        Register a mock service for testing.

        Args:
            service_interface: Interface type
            mock_implementation: Mock implementation
            name: Optional service name

        Returns:
            Self for method chaining
        """
        service_name = name or service_interface.__name__

        # Create a wrapper class for the mock
        class MockServiceWrapper(service_interface):
            def __init__(self):
                super().__init__()
                self._mock = mock_implementation

            def __getattr__(self, name):
                return getattr(self._mock, name)

            def get_service_name(self) -> str:
                return f"Mock{service_name}"

        registration = ServiceRegistration(
            service_type=service_interface,
            implementation=MockServiceWrapper,
            scope=ServiceScope.TRANSIENT,
            is_mock=True
        )

        with self._lock:
            self._registrations[service_name] = registration

        logger.debug(f"Registered mock service: {service_name}")
        return self

    def get(self, service_type: Union[Type[BaseService], str], request_id: Optional[str] = None) -> BaseService:
        """
        Get a service instance with dependency injection.

        Args:
            service_type: Service type or name
            request_id: Request ID for request-scoped services

        Returns:
            Service instance

        Raises:
            ValueError: If service not registered or circular dependency detected
        """
        service_name = service_type if isinstance(service_type, str) else service_type.__name__

        if service_name not in self._registrations:
            raise ValueError(f"Service not registered: {service_name}")

        # Check for circular dependencies
        if service_name in self._resolution_stack:
            raise ValueError(f"Circular dependency detected: {' -> '.join(self._resolution_stack + [service_name])}")

        registration = self._registrations[service_name]

        # Handle different scopes
        if registration.scope == ServiceScope.SINGLETON:
            return self._get_singleton(service_name, registration)
        elif registration.scope == ServiceScope.REQUEST:
            return self._get_request_scoped(service_name, registration, request_id)
        else:  # TRANSIENT
            return self._create_instance(service_name, registration, request_id)

    def _get_singleton(self, service_name: str, registration: ServiceRegistration) -> BaseService:
        """Get or create a singleton instance."""
        if service_name not in self._singletons:
            with self._lock:
                # Double-check locking pattern
                if service_name not in self._singletons:
                    self._singletons[service_name] = self._create_instance(service_name, registration)

        return self._singletons[service_name]

    def _get_request_scoped(
        self,
        service_name: str,
        registration: ServiceRegistration,
        request_id: Optional[str]
    ) -> BaseService:
        """Get or create a request-scoped instance."""
        if not request_id:
            raise ValueError(f"Request ID required for request-scoped service: {service_name}")

        if service_name not in self._request_scoped[request_id]:
            self._request_scoped[request_id][service_name] = self._create_instance(
                service_name, registration, request_id
            )

        return self._request_scoped[request_id][service_name]

    def _create_instance(
        self,
        service_name: str,
        registration: ServiceRegistration,
        request_id: Optional[str] = None
    ) -> BaseService:
        """Create a new service instance with dependency injection."""
        try:
            self._resolution_stack.append(service_name)

            # Use factory if provided
            if registration.factory:
                instance = registration.factory()
                if not isinstance(instance, registration.service_type):
                    raise ValueError(f"Factory for {service_name} returned wrong type")
                return instance

            # Resolve dependencies
            dependencies = {}
            for param_name, dep_service_name in registration.dependencies.items():
                dependencies[param_name] = self.get(dep_service_name, request_id)

            # Create instance
            instance = registration.implementation(**dependencies)

            logger.debug(f"Created {registration.scope.value} instance of {service_name}")
            return instance

        finally:
            if service_name in self._resolution_stack:
                self._resolution_stack.remove(service_name)

    def _extract_dependencies(self, implementation: Type[BaseService]) -> Dict[str, str]:
        """Extract dependencies from constructor type hints."""
        dependencies = {}

        try:
            type_hints = get_type_hints(implementation.__init__)
            for param_name, param_type in type_hints.items():
                if param_name == 'return':
                    continue

                # Check if parameter type is a registered service
                if hasattr(param_type, '__name__') and issubclass(param_type, BaseService):
                    dependencies[param_name] = param_type.__name__

        except (TypeError, ValidationError, ValueError) as e:
            logger.warning(f"Could not extract dependencies for {implementation.__name__}: {str(e)}")

        return dependencies

    def is_registered(self, service_type: Union[Type[BaseService], str]) -> bool:
        """
        Check if a service is registered.

        Args:
            service_type: Service type or name

        Returns:
            True if registered
        """
        service_name = service_type if isinstance(service_type, str) else service_type.__name__
        return service_name in self._registrations

    def unregister(self, service_type: Union[Type[BaseService], str]):
        """
        Unregister a service.

        Args:
            service_type: Service type or name
        """
        service_name = service_type if isinstance(service_type, str) else service_type.__name__

        with self._lock:
            if service_name in self._registrations:
                del self._registrations[service_name]

            if service_name in self._singletons:
                del self._singletons[service_name]

        logger.debug(f"Unregistered service: {service_name}")

    def clear_request_scope(self, request_id: str):
        """
        Clear all request-scoped instances for a request.

        Args:
            request_id: Request identifier
        """
        if request_id in self._request_scoped:
            del self._request_scoped[request_id]
            logger.debug(f"Cleared request scope: {request_id}")

    def get_registered_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered services.

        Returns:
            Dictionary of service information
        """
        services = {}
        for name, registration in self._registrations.items():
            services[name] = {
                'interface': registration.service_type.__name__,
                'implementation': registration.implementation.__name__,
                'scope': registration.scope.value,
                'is_mock': registration.is_mock,
                'dependencies': registration.dependencies,
                'has_factory': registration.factory is not None,
                'metadata': registration.metadata
            }
        return services

    def get_service_metrics(self) -> Dict[str, Any]:
        """
        Get registry metrics.

        Returns:
            Dictionary containing registry metrics
        """
        return {
            'total_registrations': len(self._registrations),
            'singleton_instances': len(self._singletons),
            'request_scoped_contexts': len(self._request_scoped),
            'mock_services': sum(1 for reg in self._registrations.values() if reg.is_mock),
            'scope_distribution': {
                scope.value: sum(1 for reg in self._registrations.values() if reg.scope == scope)
                for scope in ServiceScope
            }
        }


# Global service registry instance
service_registry = ServiceRegistry()


def injectable(service_type: Type[BaseService]):
    """
    Decorator to mark a class as injectable with automatic registration.

    Simplifies service registration by automatically adding the decorated class
    to the service registry at import time. Use this for service implementations
    that should be available application-wide without manual registration.

    Features:
    - Automatic service registration at module import
    - Type-safe service interface validation
    - Works with dependency injection via @inject
    - Supports service discovery and testing

    Args:
        service_type: Service interface type (base class) that this implementation
            satisfies. Must be a subclass of BaseService. The decorated class
            must inherit from or implement this interface.

    Returns:
        Decorated class unchanged (decorator is non-invasive).

    Raises:
        ValueError: If decorated class does not implement service_type interface.

    Example:
        >>> # Define service interface
        >>> class NotificationService(BaseService):
        ...     @abstractmethod
        ...     def send_notification(self, user_id, message):
        ...         pass
        ...
        >>> # Register concrete implementation
        >>> @injectable(NotificationService)
        ... class EmailNotificationService(NotificationService):
        ...     def send_notification(self, user_id, message):
        ...         # Send email implementation
        ...         pass
        ...
        >>> # Service automatically registered and available
        >>> service = service_registry.get(NotificationService)
        >>> service.send_notification(user_id=123, message="Hello")

        >>> # Multiple implementations for same interface
        >>> @injectable(NotificationService)
        ... class SMSNotificationService(NotificationService):
        ...     def send_notification(self, user_id, message):
        ...         # Send SMS implementation
        ...         pass

    Common Use Cases:
    - Service layer implementations (data access, business logic)
    - Strategy pattern implementations
    - Plugin architectures
    - Test mock registration

    Related: service_registry.register(), @inject, get_service()
    """
    def decorator(cls):
        # Auto-register the service
        service_registry.register(service_type, cls)
        return cls
    return decorator


def inject(service_type: Type[BaseService], name: Optional[str] = None):
    """
    Decorator to inject a service dependency into a method parameter.

    Automatically provides service instances to methods via keyword arguments,
    eliminating manual service instantiation and lookup. Enables loose coupling
    and testability by making dependencies explicit and replaceable.

    Features:
    - Automatic dependency resolution from service registry
    - Lazy injection (service created only when method called)
    - Test-friendly (easy to override with mocks)
    - Maintains original function signature
    - No performance overhead when service already provided

    Args:
        service_type: Service interface type to inject. Must be registered
            in service_registry via @injectable or manual registration.
        name: Optional parameter name for injected service. Defaults to
            service_type.__name__. Use when method parameter name differs
            from service class name.

    Returns:
        Decorator function that wraps the method with injection logic.

    Example:
        >>> # Basic service injection
        >>> class UserController:
        ...     @inject(UserService)
        ...     def create_user(self, user_data, UserService=None):
        ...         # UserService automatically injected if not provided
        ...         return UserService.create(user_data)
        ...
        >>> controller = UserController()
        >>> user = controller.create_user({'name': 'John'})

        >>> # Custom parameter name
        >>> @inject(NotificationService, name='notifier')
        ... def send_welcome(user_id, notifier=None):
        ...     notifier.send_notification(user_id, "Welcome!")

        >>> # Multiple injections
        >>> class OrderProcessor:
        ...     @inject(InventoryService)
        ...     @inject(PaymentService)
        ...     def process_order(self, order_data,
        ...                      InventoryService=None,
        ...                      PaymentService=None):
        ...         InventoryService.reserve(order_data['items'])
        ...         PaymentService.charge(order_data['payment'])

        >>> # Testing with mock
        >>> mock_service = Mock(spec=UserService)
        >>> controller.create_user(user_data, UserService=mock_service)

    Common Use Cases:
    - Controller methods needing service layer access
    - Business logic requiring multiple services
    - Testing with dependency injection
    - API endpoints with service dependencies

    Anti-Pattern to Avoid:
        # DON'T: Forget default parameter
        @inject(UserService)
        def create_user(self, user_data):  # Missing UserService parameter!
            return UserService.create(user_data)  # NameError!

        # DO: Include parameter with default None
        @inject(UserService)
        def create_user(self, user_data, UserService=None):
            return UserService.create(user_data)

    Related: @injectable, service_registry.get(), get_service()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            service_name = name or service_type.__name__
            if service_name not in kwargs:
                kwargs[service_name] = service_registry.get(service_type)
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def get_service(service_type: Type[BaseService], request_id: Optional[str] = None) -> BaseService:
    """
    Convenience function to retrieve a service instance from the registry.

    Simplified interface for service_registry.get(). Use when you need a service
    instance directly without decorator injection. Handles service lifecycle based
    on registration scope (singleton, transient, or request-scoped).

    Args:
        service_type: Service interface type to retrieve. Must be registered
            via @injectable or service_registry.register(). Can be interface
            class or string name.
        request_id: Optional request identifier for request-scoped services.
            Required when retrieving services registered with ServiceScope.REQUEST.
            Use request correlation ID or session ID to ensure proper scoping.

    Returns:
        Service instance based on registration scope:
        - SINGLETON: Same instance returned for all calls
        - TRANSIENT: New instance created for each call
        - REQUEST: Same instance within request_id context

    Raises:
        ValueError: If service_type not registered in service_registry
        ValueError: If request_id required but not provided (REQUEST scope)

    Example:
        >>> # Basic service retrieval
        >>> user_service = get_service(UserService)
        >>> user = user_service.create({'name': 'John'})

        >>> # Request-scoped service (e.g., per-request cache)
        >>> cache_service = get_service(CacheService, request_id='req-123')

        >>> # Use in functions without decorator
        >>> def process_order(order_data):
        ...     inventory = get_service(InventoryService)
        ...     payment = get_service(PaymentService)
        ...     inventory.reserve(order_data['items'])
        ...     payment.charge(order_data['total'])

        >>> # String-based lookup
        >>> service = get_service('NotificationService')

    Common Use Cases:
    - One-off service access in utility functions
    - Dynamic service selection based on runtime conditions
    - Legacy code refactoring (gradual migration to @inject)
    - Script-based service usage

    Performance Note:
    - SINGLETON services cached after first call (O(1) subsequent lookups)
    - TRANSIENT services create new instance each call (overhead per call)
    - REQUEST services cached per request_id (O(1) within request)

    Related: @inject (preferred for methods), service_registry.get()
    """
    return service_registry.get(service_type, request_id)