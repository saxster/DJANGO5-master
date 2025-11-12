"""
Comprehensive Tests for Celery Correlation ID Propagation

Tests correlation ID propagation from HTTP requests to Celery tasks via signals.

Test Coverage:
- Correlation ID injection into task headers
- Correlation ID restoration in task execution
- Correlation ID cleanup after task completion
- Signal handler registration
- Thread-local isolation in workers
- Missing correlation ID handling

Compliance:
- .claude/rules.md Rule #11 (specific exceptions)
"""

import uuid
import pytest
from unittest.mock import Mock, patch, MagicMock
from celery import signals

from apps.core.tasks.celery_correlation_id import (
    inject_correlation_id_into_task_headers,
    restore_correlation_id_on_task_start,
    clear_correlation_id_on_task_complete,
    get_correlation_id,
    set_correlation_id,
    setup_correlation_id_propagation,
    CORRELATION_ID_HEADER
)


class TestCeleryCorrelationIDInjection:
    """Test correlation ID injection into task headers."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear any existing correlation ID
        set_correlation_id(None)

    def teardown_method(self):
        """Clean up thread-local storage."""
        set_correlation_id(None)

    def test_injects_correlation_id_into_headers(self):
        """Test that correlation ID is injected into task headers."""
        # Set correlation ID in thread-local
        test_correlation_id = str(uuid.uuid4())
        set_correlation_id(test_correlation_id)

        # Mock headers dict
        headers = {}

        # Call signal handler
        inject_correlation_id_into_task_headers(
            sender='test_task',
            headers=headers
        )

        # Should have correlation_id in headers
        assert CORRELATION_ID_HEADER in headers
        assert headers[CORRELATION_ID_HEADER] == test_correlation_id

    def test_skips_injection_when_no_correlation_id(self):
        """Test that injection is skipped when no correlation ID exists."""
        # No correlation ID set
        headers = {}

        # Call signal handler
        inject_correlation_id_into_task_headers(
            sender='test_task',
            headers=headers
        )

        # Should not have correlation_id in headers
        assert CORRELATION_ID_HEADER not in headers

    def test_handles_none_headers(self):
        """Test that handler doesn't crash with None headers."""
        test_correlation_id = str(uuid.uuid4())
        set_correlation_id(test_correlation_id)

        # Call with None headers (should not raise exception)
        try:
            inject_correlation_id_into_task_headers(
                sender='test_task',
                headers=None
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            pytest.fail(f"Handler raised exception with None headers: {e}")

    def test_preserves_existing_headers(self):
        """Test that existing headers are preserved."""
        test_correlation_id = str(uuid.uuid4())
        set_correlation_id(test_correlation_id)

        headers = {
            'task_id': 'test-task-id',
            'retries': 0,
            'eta': 'some-eta-value'
        }

        inject_correlation_id_into_task_headers(
            sender='test_task',
            headers=headers
        )

        # Should preserve all existing headers
        assert headers['task_id'] == 'test-task-id'
        assert headers['retries'] == 0
        assert headers['eta'] == 'some-eta-value'

        # And add correlation_id
        assert headers[CORRELATION_ID_HEADER] == test_correlation_id


class TestCeleryCorrelationIDRestoration:
    """Test correlation ID restoration in task execution."""

    def setup_method(self):
        """Set up test fixtures."""
        set_correlation_id(None)

    def teardown_method(self):
        """Clean up thread-local storage."""
        set_correlation_id(None)

    def test_restores_correlation_id_from_headers(self):
        """Test that correlation ID is restored from task headers."""
        test_correlation_id = str(uuid.uuid4())

        # Mock task with request containing correlation_id
        task = Mock()
        task.request = Mock()
        task.request.correlation_id = test_correlation_id

        # Call signal handler
        restore_correlation_id_on_task_start(
            sender=task,
            task_id='test-task-id'
        )

        # Should restore to thread-local
        retrieved_id = get_correlation_id()
        assert retrieved_id == test_correlation_id

    def test_handles_missing_correlation_id_in_headers(self):
        """Test that handler doesn't crash when correlation ID is missing."""
        # Mock task without correlation_id
        task = Mock()
        task.request = Mock(spec=[])  # No correlation_id attribute

        # Should not raise exception
        try:
            restore_correlation_id_on_task_start(
                sender=task,
                task_id='test-task-id'
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            pytest.fail(f"Handler raised exception with missing correlation_id: {e}")

        # Should have no correlation ID set
        retrieved_id = get_correlation_id()
        assert retrieved_id is None

    def test_handles_none_task(self):
        """Test that handler doesn't crash with None task."""
        try:
            restore_correlation_id_on_task_start(
                sender=None,
                task_id='test-task-id'
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            pytest.fail(f"Handler raised exception with None task: {e}")

    def test_overwrites_existing_correlation_id(self):
        """Test that task correlation ID overwrites existing thread-local."""
        # Set initial correlation ID
        initial_id = str(uuid.uuid4())
        set_correlation_id(initial_id)

        # Mock task with different correlation ID
        task_correlation_id = str(uuid.uuid4())
        task = Mock()
        task.request = Mock()
        task.request.correlation_id = task_correlation_id

        # Restore from task
        restore_correlation_id_on_task_start(
            sender=task,
            task_id='test-task-id'
        )

        # Should use task's correlation ID
        retrieved_id = get_correlation_id()
        assert retrieved_id == task_correlation_id
        assert retrieved_id != initial_id


class TestCeleryCorrelationIDCleanup:
    """Test correlation ID cleanup after task completion."""

    def setup_method(self):
        """Set up test fixtures."""
        set_correlation_id(None)

    def teardown_method(self):
        """Clean up thread-local storage."""
        set_correlation_id(None)

    def test_clears_correlation_id_after_task_complete(self):
        """Test that correlation ID is cleared after task completion."""
        # Set correlation ID
        test_correlation_id = str(uuid.uuid4())
        set_correlation_id(test_correlation_id)

        # Call cleanup handler
        clear_correlation_id_on_task_complete(
            sender=Mock(),
            task_id='test-task-id'
        )

        # Should be cleared
        retrieved_id = get_correlation_id()
        assert retrieved_id is None

    def test_cleanup_is_idempotent(self):
        """Test that cleanup can be called multiple times safely."""
        # Call cleanup multiple times
        for _ in range(3):
            try:
                clear_correlation_id_on_task_complete(
                    sender=Mock(),
                    task_id='test-task-id'
                )
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                pytest.fail(f"Cleanup raised exception: {e}")

        # Should still be None
        retrieved_id = get_correlation_id()
        assert retrieved_id is None

    def test_cleanup_with_none_sender(self):
        """Test cleanup with None sender."""
        set_correlation_id(str(uuid.uuid4()))

        try:
            clear_correlation_id_on_task_complete(
                sender=None,
                task_id='test-task-id'
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            pytest.fail(f"Cleanup raised exception with None sender: {e}")

        # Should still clear
        retrieved_id = get_correlation_id()
        assert retrieved_id is None


class TestCeleryCorrelationIDSetup:
    """Test correlation ID setup and signal registration."""

    @patch('apps.core.tasks.celery_correlation_id.signals')
    def test_setup_registers_all_signal_handlers(self, mock_signals):
        """Test that setup registers all required signal handlers."""
        # Call setup
        setup_correlation_id_propagation()

        # Should connect all 3 signal handlers
        assert mock_signals.before_task_publish.connect.called
        assert mock_signals.task_prerun.connect.called
        assert mock_signals.task_postrun.connect.called

    @patch('apps.core.tasks.celery_correlation_id.signals')
    def test_setup_is_idempotent(self, mock_signals):
        """Test that setup can be called multiple times safely."""
        # Call setup multiple times
        for _ in range(3):
            try:
                setup_correlation_id_propagation()
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                pytest.fail(f"Setup raised exception: {e}")

        # Signal connections should succeed (even if already connected)
        assert mock_signals.before_task_publish.connect.called
        assert mock_signals.task_prerun.connect.called
        assert mock_signals.task_postrun.connect.called


@pytest.mark.integration
class TestCeleryCorrelationIDEndToEnd:
    """End-to-end integration tests for correlation ID propagation."""

    def setup_method(self):
        """Set up test fixtures."""
        set_correlation_id(None)

    def teardown_method(self):
        """Clean up thread-local storage."""
        set_correlation_id(None)

    def test_full_propagation_cycle(self):
        """Test full cycle: HTTP → Task Publish → Task Execute → Cleanup."""
        test_correlation_id = str(uuid.uuid4())

        # 1. HTTP Request sets correlation ID
        set_correlation_id(test_correlation_id)

        # 2. Task publishing injects into headers
        headers = {}
        inject_correlation_id_into_task_headers(
            sender='test_task',
            headers=headers
        )

        assert headers[CORRELATION_ID_HEADER] == test_correlation_id

        # 3. Simulate task execution (new thread/worker)
        # Clear thread-local to simulate new worker
        set_correlation_id(None)

        # 4. Task prerun restores from headers
        task = Mock()
        task.request = Mock()
        task.request.correlation_id = headers[CORRELATION_ID_HEADER]

        restore_correlation_id_on_task_start(
            sender=task,
            task_id='test-task-id'
        )

        # Should restore correlation ID
        retrieved_id = get_correlation_id()
        assert retrieved_id == test_correlation_id

        # 5. Task postrun clears correlation ID
        clear_correlation_id_on_task_complete(
            sender=task,
            task_id='test-task-id'
        )

        # Should be cleared
        final_id = get_correlation_id()
        assert final_id is None

    def test_propagation_with_multiple_tasks(self):
        """Test correlation ID isolation between multiple tasks."""
        correlation_ids = [str(uuid.uuid4()) for _ in range(3)]
        headers_list = []

        # Publish multiple tasks with different correlation IDs
        for correlation_id in correlation_ids:
            set_correlation_id(correlation_id)

            headers = {}
            inject_correlation_id_into_task_headers(
                sender='test_task',
                headers=headers
            )

            headers_list.append(headers)

        # Verify each task has correct correlation ID
        for i, headers in enumerate(headers_list):
            expected_id = correlation_ids[i]
            actual_id = headers.get(CORRELATION_ID_HEADER)

            assert actual_id == expected_id

    def test_propagation_without_initial_correlation_id(self):
        """Test task execution when no correlation ID was set initially."""
        # No correlation ID set

        # 1. Task publishing (no correlation ID to inject)
        headers = {}
        inject_correlation_id_into_task_headers(
            sender='test_task',
            headers=headers
        )

        assert CORRELATION_ID_HEADER not in headers

        # 2. Task execution without correlation ID
        task = Mock()
        task.request = Mock(spec=[])  # No correlation_id

        restore_correlation_id_on_task_start(
            sender=task,
            task_id='test-task-id'
        )

        # Should have no correlation ID
        retrieved_id = get_correlation_id()
        assert retrieved_id is None

        # 3. Cleanup should still work
        clear_correlation_id_on_task_complete(
            sender=task,
            task_id='test-task-id'
        )

        final_id = get_correlation_id()
        assert final_id is None


class TestCeleryCorrelationIDThreadSafety:
    """Thread safety tests for Celery correlation ID propagation."""

    def test_thread_isolation_during_propagation(self):
        """Test that correlation IDs are isolated between worker threads."""
        import threading

        results = {}

        def worker_thread(thread_id):
            # Simulate unique correlation ID for each worker
            correlation_id = str(uuid.uuid4())

            # Set correlation ID (simulating HTTP request)
            set_correlation_id(correlation_id)

            # Inject into task headers
            headers = {}
            inject_correlation_id_into_task_headers(
                sender='test_task',
                headers=headers
            )

            # Simulate task execution
            task = Mock()
            task.request = Mock()
            task.request.correlation_id = headers.get(CORRELATION_ID_HEADER)

            restore_correlation_id_on_task_start(
                sender=task,
                task_id=f'task-{thread_id}'
            )

            # Retrieve correlation ID
            retrieved_id = get_correlation_id()

            # Store results
            results[thread_id] = {
                'original': correlation_id,
                'header': headers.get(CORRELATION_ID_HEADER),
                'retrieved': retrieved_id
            }

            # Cleanup
            clear_correlation_id_on_task_complete(
                sender=task,
                task_id=f'task-{thread_id}'
            )

        # Create 5 worker threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker_thread, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify each thread had its own isolated correlation ID
        assert len(results) == 5

        for thread_id, data in results.items():
            assert data['original'] == data['header']
            assert data['original'] == data['retrieved']

        # All correlation IDs should be unique
        all_ids = [data['original'] for data in results.values()]
        assert len(all_ids) == len(set(all_ids))
