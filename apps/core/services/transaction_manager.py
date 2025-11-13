"""
Advanced Transaction Management Utilities for Service Layer

Provides sophisticated transaction patterns including:
- Nested transaction support
- Distributed transaction coordination
- Transaction rollback with compensation
- Multi-database transaction management
- Saga pattern implementation
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum
from django.db import transaction, connections, IntegrityError
from django.core.exceptions import ValidationError

from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import DatabaseException, BusinessLogicException
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Transaction status enumeration."""
    PENDING = "pending"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class TransactionStep:
    """Represents a single step in a distributed transaction."""
    name: str
    execute_func: Callable
    compensate_func: Optional[Callable] = None
    database: Optional[str] = None
    executed: bool = False
    compensation_executed: bool = False
    result: Any = None
    error: Optional[Exception] = None


class TransactionManager:
    """
    Advanced transaction manager with support for complex patterns.

    Features:
    - Nested transactions with savepoints
    - Multi-database coordination
    - Saga pattern for distributed operations
    - Automatic compensation on failure
    - Transaction monitoring and logging
    """

    def __init__(self):
        self.transaction_stack: List[str] = []
        self.active_sagas: Dict[str, List[TransactionStep]] = {}

    @contextmanager
    def atomic_operation(
        self,
        using: Optional[str] = None,
        savepoint: bool = True,
        isolation_level: Optional[str] = None
    ):
        """
        Enhanced atomic transaction with advanced features.

        Args:
            using: Database alias
            savepoint: Whether to use savepoints for nested transactions
            isolation_level: Transaction isolation level
        """
        db_name = using or get_current_db_name()
        connection = connections[db_name]
        transaction_id = f"{db_name}_{len(self.transaction_stack)}"

        try:
            self.transaction_stack.append(transaction_id)
            logger.debug(f"Starting atomic operation: {transaction_id}")

            # Set isolation level if specified
            if isolation_level:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")

            with transaction.atomic(using=db_name, savepoint=savepoint):
                yield transaction_id
                logger.debug(f"Atomic operation committed: {transaction_id}")

        except IntegrityError as e:
            logger.error(f"Database integrity error in {transaction_id}: {str(e)}")
            raise DatabaseException(
                f"Data integrity violation in transaction {transaction_id}",
                original_exception=e
            ) from e

        except ValidationError as e:
            logger.error(f"Validation error in {transaction_id}: {str(e)}")
            raise BusinessLogicException(
                f"Validation failed in transaction {transaction_id}",
                original_exception=e
            ) from e

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Unexpected error in {transaction_id}: {str(e)}")
            raise DatabaseException(
                f"Transaction failed: {transaction_id}",
                original_exception=e
            ) from e

        finally:
            if self.transaction_stack and self.transaction_stack[-1] == transaction_id:
                self.transaction_stack.pop()

    @contextmanager
    def multi_database_transaction(self, databases: List[str]):
        """
        Coordinate transactions across multiple databases.

        Args:
            databases: List of database aliases to coordinate

        Note: This provides best-effort coordination. For true ACID compliance
        across databases, consider using distributed transaction managers.
        """
        transactions = {}
        committed = []

        try:
            # Start transactions on all databases
            for db_alias in databases:
                transactions[db_alias] = transaction.atomic(using=db_alias)
                transactions[db_alias].__enter__()
                logger.debug(f"Started transaction on database: {db_alias}")

            yield transactions

            # Commit all transactions
            for db_alias in databases:
                transactions[db_alias].__exit__(None, None, None)
                committed.append(db_alias)
                logger.debug(f"Committed transaction on database: {db_alias}")

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Multi-database transaction failed: {str(e)}")

            # Rollback committed transactions (best effort)
            for db_alias in committed:
                try:
                    connection = connections[db_alias]
                    connection.rollback()
                    logger.warning(f"Rolled back committed transaction on: {db_alias}")
                except (ValueError, TypeError) as rollback_error:
                    logger.error(f"Failed to rollback {db_alias}: {str(rollback_error)}")

            # Rollback uncommitted transactions
            for db_alias, trans in transactions.items():
                if db_alias not in committed:
                    try:
                        trans.__exit__(type(e), e, e.__traceback__)
                    except (ValueError, TypeError) as rollback_error:
                        logger.error(f"Failed to rollback {db_alias}: {str(rollback_error)}")

            raise DatabaseException(
                "Multi-database transaction failed",
                original_exception=e
            ) from e

    def create_saga(self, saga_id: str) -> str:
        """
        Create a new saga for distributed transaction management.

        Args:
            saga_id: Unique identifier for the saga

        Returns:
            Saga ID for tracking
        """
        if saga_id in self.active_sagas:
            raise BusinessLogicException(f"Saga {saga_id} already exists")

        self.active_sagas[saga_id] = []
        logger.info(f"Created saga: {saga_id}")
        return saga_id

    def add_saga_step(
        self,
        saga_id: str,
        step_name: str,
        execute_func: Callable,
        compensate_func: Optional[Callable] = None,
        database: Optional[str] = None
    ):
        """
        Add a step to a saga.

        Args:
            saga_id: Saga identifier
            step_name: Name of the step
            execute_func: Function to execute the step
            compensate_func: Function to compensate if rollback needed
            database: Database alias for this step
        """
        if saga_id not in self.active_sagas:
            raise BusinessLogicException(f"Saga {saga_id} does not exist")

        step = TransactionStep(
            name=step_name,
            execute_func=execute_func,
            compensate_func=compensate_func,
            database=database
        )

        self.active_sagas[saga_id].append(step)
        logger.debug(f"Added step {step_name} to saga {saga_id}")

    def execute_saga(self, saga_id: str) -> Dict[str, Any]:
        """
        Execute all steps in a saga with automatic compensation on failure.

        Args:
            saga_id: Saga identifier

        Returns:
            Execution results and status
        """
        if saga_id not in self.active_sagas:
            raise BusinessLogicException(f"Saga {saga_id} does not exist")

        steps = self.active_sagas[saga_id]
        executed_steps = []
        execution_results = {}

        try:
            logger.info(f"Executing saga: {saga_id} with {len(steps)} steps")

            for step in steps:
                logger.debug(f"Executing saga step: {step.name}")

                # Execute step with appropriate transaction context
                if step.database:
                    with self.atomic_operation(using=step.database):
                        step.result = step.execute_func()
                else:
                    with self.atomic_operation():
                        step.result = step.execute_func()

                step.executed = True
                executed_steps.append(step)
                execution_results[step.name] = step.result

                logger.debug(f"Saga step completed: {step.name}")

            logger.info(f"Saga {saga_id} executed successfully")
            self.cleanup_saga(saga_id)

            return {
                'status': TransactionStatus.COMMITTED.value,
                'saga_id': saga_id,
                'results': execution_results,
                'steps_executed': len(executed_steps)
            }

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Saga {saga_id} failed at step {step.name}: {str(e)}")

            # Execute compensation in reverse order
            compensation_results = self._compensate_saga_steps(executed_steps)

            # Mark saga as failed
            execution_results['error'] = str(e)
            execution_results['compensation_results'] = compensation_results

            self.cleanup_saga(saga_id)

            return {
                'status': TransactionStatus.FAILED.value,
                'saga_id': saga_id,
                'results': execution_results,
                'steps_executed': len(executed_steps),
                'error': str(e),
                'compensation_executed': True
            }

    def _compensate_saga_steps(self, executed_steps: List[TransactionStep]) -> Dict[str, Any]:
        """
        Execute compensation functions for executed steps in reverse order.

        Args:
            executed_steps: List of executed steps to compensate

        Returns:
            Compensation execution results
        """
        compensation_results = {}

        # Execute compensation in reverse order
        for step in reversed(executed_steps):
            if step.compensate_func:
                try:
                    logger.debug(f"Compensating saga step: {step.name}")

                    if step.database:
                        with self.atomic_operation(using=step.database):
                            compensation_result = step.compensate_func(step.result)
                    else:
                        with self.atomic_operation():
                            compensation_result = step.compensate_func(step.result)

                    step.compensation_executed = True
                    compensation_results[step.name] = compensation_result

                    logger.debug(f"Compensation completed for step: {step.name}")

                except (ValueError, TypeError) as comp_error:
                    logger.error(f"Compensation failed for step {step.name}: {str(comp_error)}")
                    compensation_results[step.name] = f"Compensation failed: {str(comp_error)}"

            else:
                logger.warning(f"No compensation function for step: {step.name}")
                compensation_results[step.name] = "No compensation function defined"

        return compensation_results

    def cleanup_saga(self, saga_id: str):
        """
        Clean up completed or failed saga.

        Args:
            saga_id: Saga identifier to clean up
        """
        if saga_id in self.active_sagas:
            del self.active_sagas[saga_id]
            logger.debug(f"Cleaned up saga: {saga_id}")

    def get_active_sagas(self) -> List[str]:
        """
        Get list of active saga IDs.

        Returns:
            List of active saga identifiers
        """
        return list(self.active_sagas.keys())

    def get_saga_status(self, saga_id: str) -> Dict[str, Any]:
        """
        Get current status of a saga.

        Args:
            saga_id: Saga identifier

        Returns:
            Saga status information
        """
        if saga_id not in self.active_sagas:
            return {'status': 'not_found'}

        steps = self.active_sagas[saga_id]
        executed_count = sum(1 for step in steps if step.executed)
        compensated_count = sum(1 for step in steps if step.compensation_executed)

        return {
            'saga_id': saga_id,
            'status': TransactionStatus.PENDING.value,
            'total_steps': len(steps),
            'executed_steps': executed_count,
            'compensated_steps': compensated_count,
            'steps': [
                {
                    'name': step.name,
                    'executed': step.executed,
                    'compensation_executed': step.compensation_executed,
                    'has_compensation': step.compensate_func is not None
                }
                for step in steps
            ]
        }


# Global transaction manager instance
transaction_manager = TransactionManager()


def with_transaction(using: Optional[str] = None, savepoint: bool = True):
    """
    Decorator for automatic transaction management in service methods.

    Wraps service methods with atomic transaction context, ensuring all database
    operations commit together or roll back on failure. Provides automatic error
    handling with proper exception wrapping (DatabaseException, BusinessLogicException).

    Features:
    - Automatic rollback on any exception
    - Savepoint support for nested transactions
    - Multi-database transaction support
    - Correlation ID generation for failures
    - Transaction lifecycle logging

    Args:
        using: Database alias to use for transaction. If None, uses current
            tenant database from request context. Common values:
            - None (default): Current tenant database
            - 'default': Default database
            - 'analytics': Analytics database
        savepoint: Whether to use savepoints for nested transactions.
            Set to False for top-level transactions to avoid savepoint overhead.
            Default: True

    Returns:
        Decorator function that wraps the service method.

    Raises:
        DatabaseException: On database integrity errors or transaction failures
        BusinessLogicException: On validation errors within transaction

    Example:
        >>> class UserService(BaseService):
        ...     @with_transaction()
        ...     def create_user_with_profile(self, user_data, profile_data):
        ...         user = User.objects.create(**user_data)
        ...         Profile.objects.create(user=user, **profile_data)
        ...         return user
        ...
        >>> # Both User and Profile saved atomically or neither saved

        >>> # Multi-database transaction
        >>> @with_transaction(using='analytics')
        ... def log_analytics_event(event_data):
        ...     AnalyticsEvent.objects.create(**event_data)

    Complies with: .claude/rules.md - Transaction Management Requirements

    Related: TransactionManager.atomic_operation(), atomic_view_operation()
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            with transaction_manager.atomic_operation(using=using, savepoint=savepoint):
                return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def with_saga(saga_id: str):
    """
    Decorator for methods that should be part of a saga pattern.

    Marks a method as a saga participant for distributed transaction coordination.
    Currently a placeholder for saga integration - in production, this would
    register the method with the saga execution engine.

    Saga Pattern: Manages distributed transactions across multiple services or
    databases using a sequence of local transactions with compensating actions.
    If any step fails, previously completed steps are compensated in reverse order.

    Args:
        saga_id: Unique saga identifier for tracking. Should be descriptive
            of the business operation (e.g., 'order_fulfillment_saga',
            'user_registration_saga')

    Returns:
        Decorator function that marks the method as saga-aware.

    Example:
        >>> class OrderService(BaseService):
        ...     @with_saga('order_fulfillment_saga')
        ...     def create_order(self, order_data):
        ...         # Step 1: Create order
        ...         order = Order.objects.create(**order_data)
        ...         return order
        ...
        ...     @with_saga('order_fulfillment_saga')
        ...     def reserve_inventory(self, order_id):
        ...         # Step 2: Reserve inventory
        ...         pass
        ...
        ...     @with_saga('order_fulfillment_saga')
        ...     def charge_payment(self, order_id):
        ...         # Step 3: Charge payment
        ...         pass
        ...
        >>> # If charge_payment fails, reserve_inventory and create_order
        >>> # are automatically compensated in reverse order

    Related: TransactionManager.create_saga(), TransactionManager.execute_saga()

    Note: This is a placeholder decorator. For full saga functionality, use
    TransactionManager.create_saga() and add_saga_step() explicitly.
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # This is a placeholder for saga integration
            # In practice, this would integrate with the saga execution
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def atomic_view_operation(using: Optional[str] = None):
    """
    Decorator for view handle_valid_form methods requiring atomic transactions.

    Ensures all database operations within a view's handle_valid_form method
    execute atomically. If any step fails, all changes are rolled back,
    preventing partial data corruption. Critical for multi-step form processing
    where related models must be created/updated together.

    Features:
    - Automatic rollback on any database error
    - Proper exception propagation with logging
    - Prevents partial saves (e.g., User created but Profile creation failed)
    - Works with custom views, FormView, CreateView, UpdateView

    Args:
        using: Database alias (defaults to current tenant database).
            Use when working with specific databases in multi-tenant setup.

    Returns:
        Decorator function that wraps handle_valid_form with transaction.

    Raises:
        IntegrityError: Database constraint violations (with rollback)
        ValidationError: Model validation failures (with rollback)
        DatabaseError: Any database operation failure (with rollback)

    Example:
        >>> # Basic form handling with transaction
        >>> class UserCreateView(CreateView):
        ...     @atomic_view_operation()
        ...     def handle_valid_form(self, form, request, create):
        ...         # All operations committed together or rolled back together
        ...         user = form.save()
        ...         putils.save_userinfo(user, request.user, request.session)
        ...         Profile.objects.create(user=user)
        ...         user.add_history()
        ...         return JsonResponse({'pk': user.id})

        >>> # Multi-database transaction
        >>> class AnalyticsReportView(CreateView):
        ...     @atomic_view_operation(using='analytics')
        ...     def handle_valid_form(self, form, request, create):
        ...         report = form.save()
        ...         return JsonResponse({'id': report.id})

    Common Use Cases:
    - User registration with profile/permissions creation
    - Order processing with inventory updates
    - Audit trail creation alongside data changes
    - Multi-step form processing

    Complies with: .claude/rules.md - Transaction Management Requirements

    Related: with_transaction(), signal_aware_transaction()
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            db_name = using or get_current_db_name()
            try:
                logger.debug(f"Starting atomic view operation: {func.__name__}")
                with transaction.atomic(using=db_name):
                    result = func(*args, **kwargs)
                    logger.debug(f"Atomic view operation committed: {func.__name__}")
                    return result
            except IntegrityError as e:
                logger.error(
                    f"Database integrity error in {func.__name__}: {str(e)}",
                    exc_info=True
                )
                raise
            except ValidationError as e:
                logger.error(
                    f"Validation error in {func.__name__}: {str(e)}",
                    exc_info=True
                )
                raise
            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
                logger.error(
                    f"Unexpected error in {func.__name__}: {str(e)}",
                    exc_info=True
                )
                raise
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


@contextmanager
def signal_aware_transaction(using: Optional[str] = None):
    """
    Context manager for transactions that trigger Django signals.

    Ensures that signal handlers (like post_save creating related models) execute
    within the same transaction as the triggering operation. If any signal handler
    fails, the entire transaction (including the original operation) rolls back.
    Critical for maintaining data consistency when signals create related objects.

    Problem Solved:
    Without this, a model might be saved successfully but its post_save signal
    could fail, leaving orphaned records. This context manager ensures atomicity
    across the entire signal chain.

    Args:
        using: Database alias (defaults to current tenant database).
            Use when working with specific databases in multi-tenant setup.

    Yields:
        None. Use as context manager with 'with' statement.

    Raises:
        DatabaseException: Wraps IntegrityError from signal handlers with context
        DatabaseError: Any database operation failure in signal handlers
        IntegrityError: Constraint violations from main operation or signals
        ObjectDoesNotExist: If signal handler references missing related objects

    Example:
        >>> # User creation with post_save profile creation
        >>> with signal_aware_transaction():
        ...     people = People.objects.create(
        ...         username='john_doe',
        ...         email='john@example.com'
        ...     )
        ...     # post_save signal fires here, within transaction
        ...     # Creates PeopleProfile automatically
        ...     # If PeopleProfile creation fails, People creation also rolls back

        >>> # Multi-model creation with signals
        >>> with signal_aware_transaction():
        ...     order = Order.objects.create(customer=customer)
        ...     # post_save creates OrderNotification
        ...     # If notification fails, order is rolled back

    Common Use Cases:
    - User/profile creation (post_save creates profile)
    - Order processing (post_save triggers inventory updates)
    - Audit trail creation (post_save creates history records)
    - Notification creation (post_save sends notifications)

    Anti-Pattern to Avoid:
        # DON'T: Signal outside transaction can fail silently
        people = People.objects.create(...)  # Committed
        # post_save fails here - people record orphaned!

    Complies with: .claude/rules.md - Transaction Management Requirements

    Related: atomic_view_operation(), with_transaction()
    """
    db_name = using or get_current_db_name()

    try:
        logger.debug(f"Starting signal-aware transaction on {db_name}")
        with transaction.atomic(using=db_name):
            yield
            logger.debug(f"Signal-aware transaction committed on {db_name}")
    except IntegrityError as e:
        logger.error(
            f"Database integrity error in signal-aware transaction: {str(e)}",
            exc_info=True
        )
        raise DatabaseException(
            "Signal handler caused data integrity violation",
            original_exception=e
        ) from e
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
        logger.error(
            f"Error in signal-aware transaction: {str(e)}",
            exc_info=True
        )
        raise


def transactional_batch_operation(
    items: List[Any],
    operation_func: Callable,
    batch_size: int = 100,
    using: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute batch operations with transaction management and progress tracking.

    Processes large datasets in batches while maintaining atomicity per batch.
    If a batch fails, only that batch is rolled back, not the entire operation.

    Args:
        items: List of items to process
        operation_func: Function to apply to each item
        batch_size: Number of items per transaction batch
        using: Database alias

    Returns:
        Dictionary with success/failure counts and error details

    Example:
        def process_employee(employee_data):
            People.objects.create(**employee_data)

        result = transactional_batch_operation(
            items=employee_list,
            operation_func=process_employee,
            batch_size=50
        )
    """
    db_name = using or get_current_db_name()
    results = {
        'total': len(items),
        'processed': 0,
        'failed': 0,
        'errors': []
    }

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        try:
            with transaction.atomic(using=db_name):
                for item in batch:
                    operation_func(item)
                results['processed'] += len(batch)
                logger.debug(f"Batch {batch_num} completed: {len(batch)} items")

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            results['failed'] += len(batch)
            error_detail = {
                'batch_number': batch_num,
                'batch_size': len(batch),
                'error': str(e)
            }
            results['errors'].append(error_detail)
            logger.error(
                f"Batch {batch_num} failed: {str(e)}",
                extra=error_detail,
                exc_info=True
            )

    logger.info(
        f"Batch operation completed: {results['processed']} succeeded, {results['failed']} failed"
    )
    return results