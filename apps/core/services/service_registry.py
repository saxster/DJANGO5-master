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
    Decorator to mark a class as injectable.

    Args:
        service_type: Service interface type

    Returns:
        Decorated class
    """
    def decorator(cls):
        # Auto-register the service
        service_registry.register(service_type, cls)
        return cls
    return decorator


def inject(service_type: Type[BaseService], name: Optional[str] = None):
    """
    Decorator to inject a service into a method parameter.

    Args:
        service_type: Service type to inject
        name: Optional service name

    Returns:
        Decorator function
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
    Convenience function to get a service instance.

    Args:
        service_type: Service type
        request_id: Optional request ID

    Returns:
        Service instance
    """
    return service_registry.get(service_type, request_id)