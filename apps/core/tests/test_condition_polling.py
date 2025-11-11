"""
Tests for condition polling utility.

Tests verify that condition-based waiting works correctly:
- Successful condition polling (returns immediately when true)
- Timeout handling (raises error when timeout exceeded)
- Interval configuration (respects interval parameter)
- Error messages (custom and default error messages)
- Cache operations
- Database object waiting
- Value matching
"""

import pytest
import threading
import time
from django.test import TestCase, TransactionTestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model

from apps.core.testing.condition_polling import (
    poll_until,
    wait_for_value,
    wait_for_cache,
    wait_for_db_object,
    wait_for_condition_with_value,
    wait_for_false,
    ConditionTimeoutError,
)

User = get_user_model()


class ConditionPollingTestCase(TestCase):
    """Test basic condition polling functionality."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_poll_until_immediate_success(self):
        """Test poll_until returns immediately when condition is true."""
        start = time.time()
        poll_until(lambda: True, timeout=5)
        elapsed = time.time() - start

        # Should complete nearly instantly (< 0.1s)
        self.assertLess(elapsed, 0.1)

    def test_poll_until_with_delay(self):
        """Test poll_until waits for condition to become true."""
        flag = {'value': False}
        delay = 0.3

        def set_flag_after_delay():
            time.sleep(delay)
            flag['value'] = True

        # Start thread that will set flag
        thread = threading.Thread(target=set_flag_after_delay)
        thread.start()

        # Poll until flag is set
        start = time.time()
        poll_until(
            lambda: flag['value'],
            timeout=5,
            interval=0.05
        )
        elapsed = time.time() - start
        thread.join()

        # Should take ~delay amount of time
        self.assertGreaterEqual(elapsed, delay)
        self.assertLess(elapsed, delay + 0.2)

    def test_poll_until_timeout(self):
        """Test poll_until raises ConditionTimeoutError on timeout."""
        with self.assertRaises(ConditionTimeoutError) as cm:
            poll_until(lambda: False, timeout=0.2, interval=0.05)

        self.assertIn("not met within 0.2s", str(cm.exception))

    def test_poll_until_custom_error_message(self):
        """Test poll_until includes custom error message on timeout."""
        custom_msg = "Custom error message for debugging"

        with self.assertRaises(ConditionTimeoutError) as cm:
            poll_until(
                lambda: False,
                timeout=0.1,
                interval=0.05,
                error_message=custom_msg
            )

        self.assertIn(custom_msg, str(cm.exception))

    def test_poll_until_with_exception_handling(self):
        """Test poll_until continues polling even if condition raises."""
        call_count = {'value': 0}

        def condition_with_error():
            call_count['value'] += 1
            if call_count['value'] < 3:
                raise ValueError("Temporary error")
            return True

        # Should succeed despite initial exceptions
        poll_until(
            condition_with_error,
            timeout=5,
            interval=0.05
        )

        # Should have been called 3 times
        self.assertEqual(call_count['value'], 3)

    def test_poll_until_interval_respected(self):
        """Test poll_until respects the interval parameter."""
        call_count = {'value': 0}

        def condition():
            call_count['value'] += 1
            return False

        # With 0.3s interval and 0.6s timeout, should check ~2 times
        start = time.time()
        try:
            poll_until(
                condition,
                timeout=0.6,
                interval=0.3
            )
        except ConditionTimeoutError:
            pass

        elapsed = time.time() - start

        # Should have checked approximately 2-3 times
        # Each check takes negligible time, sleep takes the interval time
        self.assertGreaterEqual(call_count['value'], 2)
        # Total time should be at least 2 intervals
        self.assertGreaterEqual(elapsed, 0.5)


class WaitForValueTestCase(TestCase):
    """Test wait_for_value functionality."""

    def test_wait_for_value_immediate(self):
        """Test wait_for_value returns immediately when value matches."""
        start = time.time()
        result = wait_for_value(
            getter=lambda: 42,
            expected=42,
            timeout=5
        )
        elapsed = time.time() - start

        self.assertEqual(result, 42)
        self.assertLess(elapsed, 0.1)

    def test_wait_for_value_with_delay(self):
        """Test wait_for_value waits for matching value."""
        value = {'current': 0}

        def increment_after_delay():
            time.sleep(0.2)
            value['current'] = 42

        thread = threading.Thread(target=increment_after_delay)
        thread.start()

        result = wait_for_value(
            getter=lambda: value['current'],
            expected=42,
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertEqual(result, 42)

    def test_wait_for_value_timeout(self):
        """Test wait_for_value raises on timeout."""
        with self.assertRaises(ConditionTimeoutError):
            wait_for_value(
                getter=lambda: 0,
                expected=42,
                timeout=0.2,
                interval=0.05
            )

    def test_wait_for_value_with_string(self):
        """Test wait_for_value works with string values."""
        status = {'value': 'pending'}

        def update_status():
            time.sleep(0.1)
            status['value'] = 'completed'

        thread = threading.Thread(target=update_status)
        thread.start()

        result = wait_for_value(
            getter=lambda: status['value'],
            expected='completed',
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertEqual(result, 'completed')


class WaitForCacheTestCase(TestCase):
    """Test cache waiting functionality."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_wait_for_cache_key_exists(self):
        """Test wait_for_cache when key is set immediately."""
        cache.set('test_key', 'test_value')

        start = time.time()
        value = wait_for_cache('test_key', timeout=5)
        elapsed = time.time() - start

        self.assertEqual(value, 'test_value')
        self.assertLess(elapsed, 0.1)

    def test_wait_for_cache_key_appears(self):
        """Test wait_for_cache waits for key to be set."""
        def set_cache_after_delay():
            time.sleep(0.2)
            cache.set('delayed_key', 'delayed_value')

        thread = threading.Thread(target=set_cache_after_delay)
        thread.start()

        value = wait_for_cache(
            'delayed_key',
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertEqual(value, 'delayed_value')

    def test_wait_for_cache_timeout(self):
        """Test wait_for_cache raises on timeout."""
        with self.assertRaises(ConditionTimeoutError) as cm:
            wait_for_cache('nonexistent_key', timeout=0.2, interval=0.05)

        self.assertIn("Cache key", str(cm.exception))

    def test_wait_for_cache_with_expected_value(self):
        """Test wait_for_cache with expected value matching."""
        def update_cache():
            time.sleep(0.1)
            cache.set('counter', 42)

        thread = threading.Thread(target=update_cache)
        thread.start()

        value = wait_for_cache(
            'counter',
            expected_value=42,
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertEqual(value, 42)

    def test_wait_for_cache_wrong_value(self):
        """Test wait_for_cache timeout when value doesn't match."""
        cache.set('counter', 10)

        with self.assertRaises(ConditionTimeoutError):
            wait_for_cache(
                'counter',
                expected_value=42,
                timeout=0.2,
                interval=0.05
            )


@pytest.mark.django_db(transaction=True)
class WaitForDbObjectTestCase(TransactionTestCase):
    """Test database object waiting functionality."""

    def test_wait_for_db_object_exists_immediately(self):
        """Test wait_for_db_object when object exists."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        start = time.time()
        result = wait_for_db_object(
            User,
            {'username': 'testuser'},
            timeout=5
        )
        elapsed = time.time() - start

        self.assertEqual(result.id, user.id)
        self.assertLess(elapsed, 0.1)

    def test_wait_for_db_object_appears(self):
        """Test wait_for_db_object waits for object to be created."""
        def create_user_after_delay():
            time.sleep(0.2)
            User.objects.create_user(
                username='delayeduser',
                email='delayed@example.com'
            )

        thread = threading.Thread(target=create_user_after_delay)
        thread.start()

        result = wait_for_db_object(
            User,
            {'username': 'delayeduser'},
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertEqual(result.username, 'delayeduser')

    def test_wait_for_db_object_not_found(self):
        """Test wait_for_db_object raises on timeout."""
        with self.assertRaises(ConditionTimeoutError) as cm:
            wait_for_db_object(
                User,
                {'username': 'nonexistent'},
                timeout=0.2,
                interval=0.05
            )

        self.assertIn("User", str(cm.exception))

    def test_wait_for_db_object_with_attributes(self):
        """Test wait_for_db_object verifies attribute values."""
        def update_user_after_delay():
            time.sleep(0.2)
            user = User.objects.get(username='testuser')
            user.is_active = True
            user.save()

        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=False
        )

        thread = threading.Thread(target=update_user_after_delay)
        thread.start()

        result = wait_for_db_object(
            User,
            {'username': 'testuser'},
            attributes={'is_active': True},
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertTrue(result.is_active)

    def test_wait_for_db_object_multiple_filters(self):
        """Test wait_for_db_object with multiple filter criteria."""
        User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        result = wait_for_db_object(
            User,
            {'username': 'testuser', 'email': 'test@example.com'},
            timeout=5
        )

        self.assertEqual(result.username, 'testuser')
        self.assertEqual(result.email, 'test@example.com')


class WaitForConditionWithValueTestCase(TestCase):
    """Test wait_for_condition_with_value functionality."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_wait_for_condition_with_value_immediate(self):
        """Test immediate return when condition is met."""
        cache.set('task_done', True)
        cache.set('task_result', 'success')

        result = wait_for_condition_with_value(
            condition=lambda: cache.get('task_done'),
            value_getter=lambda: cache.get('task_result'),
            timeout=5
        )

        self.assertEqual(result, 'success')

    def test_wait_for_condition_with_value_delayed(self):
        """Test waiting for condition and returning value."""
        def complete_task():
            time.sleep(0.2)
            cache.set('task_done', True)
            cache.set('task_result', 'completed')

        thread = threading.Thread(target=complete_task)
        thread.start()

        result = wait_for_condition_with_value(
            condition=lambda: cache.get('task_done'),
            value_getter=lambda: cache.get('task_result'),
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertEqual(result, 'completed')

    def test_wait_for_condition_with_value_timeout(self):
        """Test timeout when condition not met."""
        with self.assertRaises(ConditionTimeoutError):
            wait_for_condition_with_value(
                condition=lambda: False,
                value_getter=lambda: 'never',
                timeout=0.1,
                interval=0.05
            )


class WaitForFalseTestCase(TestCase):
    """Test wait_for_false functionality."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_wait_for_false_already_false(self):
        """Test wait_for_false returns immediately when false."""
        start = time.time()
        wait_for_false(lambda: False, timeout=5)
        elapsed = time.time() - start

        self.assertLess(elapsed, 0.1)

    def test_wait_for_false_becomes_false(self):
        """Test wait_for_false waits for condition to become false."""
        flag = {'running': True}

        def stop_after_delay():
            time.sleep(0.2)
            flag['running'] = False

        thread = threading.Thread(target=stop_after_delay)
        thread.start()

        wait_for_false(
            lambda: flag['running'],
            timeout=5,
            interval=0.05
        )
        thread.join()

        self.assertFalse(flag['running'])

    def test_wait_for_false_timeout(self):
        """Test wait_for_false raises on timeout."""
        with self.assertRaises(ConditionTimeoutError):
            wait_for_false(lambda: True, timeout=0.1, interval=0.05)


class ConditionPollingIntegrationTestCase(TestCase):
    """Integration tests for condition polling in realistic scenarios."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_multi_step_async_operation(self):
        """Test polling through multiple stages of async operation."""
        state = {
            'step1_complete': False,
            'step2_complete': False,
            'result': None
        }

        def async_operation():
            # Step 1
            time.sleep(0.1)
            state['step1_complete'] = True
            cache.set('step1_done', True)

            # Step 2
            time.sleep(0.1)
            state['step2_complete'] = True
            cache.set('step2_done', True)

            # Final result
            time.sleep(0.1)
            state['result'] = 'completed'
            cache.set('result', 'success')

        thread = threading.Thread(target=async_operation)
        thread.start()

        # Wait for step 1
        poll_until(
            lambda: cache.get('step1_done'),
            timeout=5,
            interval=0.05
        )
        self.assertTrue(state['step1_complete'])

        # Wait for step 2
        poll_until(
            lambda: cache.get('step2_done'),
            timeout=5,
            interval=0.05
        )
        self.assertTrue(state['step2_complete'])

        # Wait for result
        result = wait_for_cache('result', timeout=5)
        thread.join()

        self.assertEqual(result, 'success')
        self.assertEqual(state['result'], 'completed')

    def test_polling_with_retries_and_failures(self):
        """Test polling handles transient failures gracefully."""
        attempt_count = {'value': 0}

        def condition_with_transient_failures():
            attempt_count['value'] += 1

            # Fail first 2 attempts
            if attempt_count['value'] <= 2:
                raise RuntimeError("Transient error")

            # Succeed on 3rd attempt
            return True

        # Should succeed despite initial failures
        poll_until(
            condition_with_transient_failures,
            timeout=5,
            interval=0.05
        )

        self.assertEqual(attempt_count['value'], 3)
