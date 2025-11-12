# Condition Polling Migration Guide

## Overview

The condition polling utility (`apps.core.testing.condition_polling`) provides event-driven waiting for tests, replacing arbitrary `time.sleep()` calls with intelligent condition polling.

**Benefits:**
- Tests complete faster when conditions are met (no waiting for fixed sleep duration)
- Eliminates flaky tests caused by timing assumptions
- Makes test intent explicit (wait for *what*, not "wait 5 seconds")
- Automatic error messages with elapsed time and context
- Continues polling even if condition evaluation throws exceptions

## Why Replace time.sleep()?

### Problem: Arbitrary Delays
```python
# BAD: Sleep for 2 seconds, hope the background job finishes
time.sleep(2)
cache_value = cache.get('result')  # Still None? Too bad!
```

**Issues:**
- No guarantee the condition is actually met after 2 seconds
- Test takes minimum 2 seconds regardless of when condition becomes true
- In CI with slow/overloaded systems, 2 seconds might not be enough
- Makes tests non-deterministic and flaky

### Solution: Event-Driven Polling
```python
# GOOD: Poll every 0.1s until result appears
from apps.core.testing import wait_for_cache

cache_value = wait_for_cache('result', timeout=5, interval=0.1)
# Completes instantly if 'result' is already set
# Keeps checking until timeout=5s if not
```

**Benefits:**
- Fast completion when condition is immediately true
- Reasonable timeout (5s) prevents hanging forever
- Clear intent: "wait for cache key to exist"
- Automatic error messages showing elapsed time

---

## Common Patterns

### Pattern 1: Wait for Cache Key to Exist

**Before (with time.sleep):**
```python
def test_background_task():
    # Kick off background task
    call_background_task.delay()

    # Sleep hoping task completes
    time.sleep(2)

    # Check if result is in cache
    result = cache.get('task_result')
    assert result == 'success', f"Expected 'success', got {result}"
```

**After (with condition polling):**
```python
from apps.core.testing import wait_for_cache

def test_background_task():
    # Kick off background task
    call_background_task.delay()

    # Wait for result to appear in cache
    result = wait_for_cache(
        'task_result',
        timeout=5,
        interval=0.1,
        expected_value='success'
    )
    assert result == 'success'
```

---

### Pattern 2: Wait for Database Object to Be Created

**Before (with time.sleep):**
```python
def test_async_user_creation():
    # Start async user creation
    create_user_async.delay(username='newuser')

    # Sleep hoping user is created
    time.sleep(1)

    # Try to get user
    try:
        user = User.objects.get(username='newuser')
        assert user.email == 'new@example.com'
    except User.DoesNotExist:
        self.fail("User was not created")
```

**After (with condition polling):**
```python
from apps.core.testing import wait_for_db_object

def test_async_user_creation():
    # Start async user creation
    create_user_async.delay(username='newuser')

    # Wait for user to appear in database
    user = wait_for_db_object(
        User,
        {'username': 'newuser'},
        attributes={'email': 'new@example.com'},
        timeout=5
    )
    assert user.email == 'new@example.com'
```

---

### Pattern 3: Wait for Specific Value

**Before (with time.sleep):**
```python
def test_status_transitions():
    task = Task.objects.create(name='test', status='pending')

    # Start processing
    process_task.delay(task.id)

    # Sleep hoping task completes
    time.sleep(3)

    # Refresh and check status
    task.refresh_from_db()
    assert task.status == 'completed'
```

**After (with condition polling):**
```python
from apps.core.testing import wait_for_value

def test_status_transitions():
    task = Task.objects.create(name='test', status='pending')

    # Start processing
    process_task.delay(task.id)

    # Wait for status to change to 'completed'
    def get_status():
        task.refresh_from_db()
        return task.status

    wait_for_value(
        getter=get_status,
        expected='completed',
        timeout=5,
        interval=0.1
    )
```

---

### Pattern 4: Wait for Custom Condition

**Before (with time.sleep):**
```python
def test_concurrent_updates():
    user = User.objects.create(username='test', balance=100)

    # Start multiple concurrent operations
    for i in range(10):
        update_balance.delay(user.id, amount=1)

    # Sleep hoping all updates complete
    time.sleep(5)

    # Check if all operations finished
    user.refresh_from_db()
    assert user.balance == 110
```

**After (with condition polling):**
```python
from apps.core.testing import poll_until

def test_concurrent_updates():
    user = User.objects.create(username='test', balance=100)

    # Start multiple concurrent operations
    for i in range(10):
        update_balance.delay(user.id, amount=1)

    # Wait for all updates to complete
    def all_updates_done():
        user.refresh_from_db()
        return user.balance == 110

    poll_until(
        condition=all_updates_done,
        timeout=5,
        interval=0.1,
        error_message="Balance did not reach 110 after 5 seconds"
    )
```

---

## API Reference

### `poll_until(condition, timeout=5, interval=0.1, error_message=None)`

Poll a condition function until it returns `True` or timeout is reached.

**Parameters:**
- `condition` (callable) - Function that returns `True` when condition is met
- `timeout` (float) - Maximum wait time in seconds (default: 5)
- `interval` (float) - Time between checks in seconds (default: 0.1)
- `error_message` (str) - Custom message on timeout (optional)

**Returns:** None

**Raises:** `ConditionTimeoutError` if condition not met within timeout

**Example:**
```python
from apps.core.testing import poll_until

poll_until(
    lambda: cache.get('processing_done'),
    timeout=10,
    error_message="Processing did not complete"
)
```

---

### `wait_for_value(getter, expected, timeout=5, interval=0.1, error_message=None)`

Wait for a getter function to return a specific value.

**Parameters:**
- `getter` (callable) - Function that returns the value to check
- `expected` - The expected value to match
- `timeout` (float) - Maximum wait time in seconds (default: 5)
- `interval` (float) - Time between checks in seconds (default: 0.1)
- `error_message` (str) - Custom message on timeout (optional)

**Returns:** The expected value

**Raises:** `ConditionTimeoutError` if value doesn't match within timeout

**Example:**
```python
from apps.core.testing import wait_for_value

# Wait for user status to become 'active'
status = wait_for_value(
    getter=lambda: User.objects.get(id=user_id).status,
    expected='active',
    timeout=10
)
```

---

### `wait_for_cache(cache_key, timeout=5, interval=0.1, expected_value=None)`

Wait for a cache key to exist (and optionally match a value).

**Parameters:**
- `cache_key` (str) - Django cache key to monitor
- `timeout` (float) - Maximum wait time in seconds (default: 5)
- `interval` (float) - Time between checks in seconds (default: 0.1)
- `expected_value` (optional) - If provided, value must equal this

**Returns:** The cache value when key is set

**Raises:** `ConditionTimeoutError` if cache key not set within timeout

**Examples:**
```python
from apps.core.testing import wait_for_cache

# Wait for cache key to be set
value = wait_for_cache('processing:complete', timeout=10)

# Wait for cache key with specific value
value = wait_for_cache(
    'counter:value',
    expected_value=42,
    timeout=5
)
```

---

### `wait_for_db_object(model, filter_kwargs, timeout=5, interval=0.1, attributes=None)`

Wait for a database object matching filters to exist with optional attribute values.

**Parameters:**
- `model` - Django model class
- `filter_kwargs` (dict) - Filters for `model.objects.filter()`
- `timeout` (float) - Maximum wait time in seconds (default: 5)
- `interval` (float) - Time between checks in seconds (default: 0.1)
- `attributes` (dict) - Optional dict of `{attribute: expected_value}` to verify

**Returns:** The matched database object

**Raises:** `ConditionTimeoutError` if object not found or attributes don't match

**Examples:**
```python
from apps.core.testing import wait_for_db_object

# Wait for user to be created
user = wait_for_db_object(
    User,
    {'username': 'testuser'},
    timeout=5
)

# Wait for object with specific attribute values
task = wait_for_db_object(
    Task,
    {'id': task_id},
    attributes={'status': 'completed', 'error': None},
    timeout=10
)
```

---

### `wait_for_condition_with_value(condition, value_getter, timeout=5, interval=0.1, error_message=None)`

Wait for a condition while also fetching a value.

**Parameters:**
- `condition` (callable) - Function that returns `True` when ready
- `value_getter` (callable) - Function that returns the value
- `timeout` (float) - Maximum wait time in seconds (default: 5)
- `interval` (float) - Time between checks in seconds (default: 0.1)
- `error_message` (str) - Custom message on timeout (optional)

**Returns:** The value from `value_getter()`

**Raises:** `ConditionTimeoutError` if condition not met within timeout

**Example:**
```python
from apps.core.testing import wait_for_condition_with_value

# Wait for task completion and retrieve result
result = wait_for_condition_with_value(
    condition=lambda: cache.get('task_done'),
    value_getter=lambda: cache.get('task_result'),
    timeout=10
)
```

---

### `wait_for_false(condition, timeout=5, interval=0.1, error_message=None)`

Poll until a condition becomes `False` (opposite of `poll_until`).

**Parameters:**
- `condition` (callable) - Function that returns `False` when done
- `timeout` (float) - Maximum wait time in seconds (default: 5)
- `interval` (float) - Time between checks in seconds (default: 0.1)
- `error_message` (str) - Custom message on timeout (optional)

**Returns:** None

**Raises:** `ConditionTimeoutError` if condition still `True` after timeout

**Example:**
```python
from apps.core.testing import wait_for_false

# Wait for background job to complete (is_running becomes False)
wait_for_false(
    lambda: cache.get('job_is_running', False),
    timeout=30,
    error_message="Background job did not complete"
)
```

---

## Migration Checklist

### Step 1: Identify time.sleep() in Tests
```bash
# Find all test files with time.sleep()
grep -r "time\.sleep" apps/*/tests/ tests/ --include="*.py"
```

### Step 2: Categorize by Pattern

For each `time.sleep()` call, determine the pattern:

1. **Cache waiting** → Use `wait_for_cache()`
2. **Database object waiting** → Use `wait_for_db_object()`
3. **Value waiting** → Use `wait_for_value()`
4. **Custom condition** → Use `poll_until()`
5. **Opposite condition** → Use `wait_for_false()`

### Step 3: Update Import

```python
# Replace
import time
# time.sleep(2)

# With
from apps.core.testing import poll_until, wait_for_cache, wait_for_db_object
```

### Step 4: Replace sleep() Calls

Refer to the patterns above for your use case.

### Step 5: Test Locally

```bash
# Run affected test file
python manage.py test apps.your_app.tests.test_file --verbosity=2

# Or with pytest
pytest apps/your_app/tests/test_file.py -v
```

### Step 6: Verify CI Tests Pass

Ensure tests pass in CI environment with the new polling strategy.

---

## Timeout Guidelines

Choose timeouts based on the operation:

| Operation Type | Recommended Timeout | Interval |
|---|---|---|
| Cache operations | 2-5s | 0.05-0.1s |
| Database writes | 3-5s | 0.1s |
| Celery tasks | 10-30s | 0.5-1s |
| External APIs | 30-60s | 1-5s |
| Background jobs | 30-120s | 2-5s |

**Rule of thumb:** Use `interval = timeout / 50` for balanced polling frequency.

---

## Troubleshooting

### Timeout Too Short
If tests are consistently timing out in CI but pass locally:
- Increase timeout (especially for Celery tasks in slow environments)
- Reduce interval (poll more frequently)
- Check if condition is actually being evaluated correctly

### Test Still Flaky
If tests are still intermittently failing:
- Add logging inside condition function
- Check error messages for clues
- Verify the condition logic is correct
- Consider race conditions in the code being tested

### Performance Regression
If tests are taking too long:
- Reduce timeout if condition is usually met quickly
- Increase interval if polling overhead is significant
- Check for infinite loops in condition evaluation

---

## Example: Complete Migration

**Before:**
```python
import time
from django.test import TestCase
from django.core.cache import cache

class BackgroundTaskTestCase(TestCase):
    def test_task_completion(self):
        cache.clear()

        # Start task
        start_async_processing.delay()

        # Sleep hoping it completes
        time.sleep(3)

        # Check results
        assert cache.get('processing_complete') == True
        assert cache.get('result_count') == 100
```

**After:**
```python
from django.test import TestCase
from django.core.cache import cache
from apps.core.testing import wait_for_cache

class BackgroundTaskTestCase(TestCase):
    def test_task_completion(self):
        cache.clear()

        # Start task
        start_async_processing.delay()

        # Wait for completion
        complete = wait_for_cache(
            'processing_complete',
            expected_value=True,
            timeout=10
        )
        assert complete == True

        # Wait for result count
        count = wait_for_cache(
            'result_count',
            expected_value=100,
            timeout=10
        )
        assert count == 100
```

---

## Implementation Details

### Error Handling
- Condition evaluation errors are logged but don't stop polling
- Exceptions are included in timeout error message
- Use `error_message` parameter for context-specific messages

### Logging
All polling operations log:
- Success: "Condition met after X.XXs"
- Timeout: "Condition poll timeout: [message] (elapsed: X.XXs)"
- Errors: "Condition check failed (will retry): [error]"

### Performance
- Polling overhead is minimal (~1ms per check)
- Total test duration is timeout only if condition never becomes true
- Tests complete instantly if condition is already met

---

## Related Files

- **Utility code:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/testing/condition_polling.py`
- **Tests:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/tests/test_condition_polling.py`
- **Imports:** `from apps.core.testing import poll_until, wait_for_cache, ...`

---

## Contributing

When adding new polling utilities:

1. Follow the naming pattern: `wait_for_*` or `poll_*`
2. Include comprehensive docstrings with examples
3. Add tests in `test_condition_polling.py`
4. Update this guide with API reference
5. Export from `apps.core.testing.__init__.py`

---

**Last Updated:** November 12, 2025
