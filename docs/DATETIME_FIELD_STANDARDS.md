# DateTime Field Standards

> **Last Updated**: November 3, 2025
> **Status**: Enforced via pre-commit hooks
> **Compliance**: Python 3.12+, Django 5.2.1

## Table of Contents

- [Overview](#overview)
- [Core Principles](#core-principles)
- [Import Standards](#import-standards)
- [Model Field Patterns](#model-field-patterns)
- [Datetime Creation](#datetime-creation)
- [Constants Usage](#constants-usage)
- [Common Patterns](#common-patterns)
- [Anti-Patterns](#anti-patterns)
- [Migration Guide](#migration-guide)
- [Testing](#testing)
- [Enforcement](#enforcement)

---

## Overview

This document defines mandatory datetime handling standards for the Django 5.2.1 enterprise facility management platform. All datetime operations must be **timezone-aware** and use **Python 3.12+ compatible patterns**.

### Why These Standards Matter

1. **Python 3.12+ Compatibility**: `datetime.utcnow()` is deprecated and will be removed
2. **Timezone Safety**: Naive datetimes cause bugs across timezones and DST transitions
3. **Maintainability**: Centralized constants eliminate magic numbers
4. **Consistency**: Uniform patterns across 2,397+ Python files

### Compliance Status

✅ **100% of production code** eliminates deprecated `datetime.utcnow()`
✅ **95%+ adoption** of `timezone.now()` for current time
✅ **Zero blocking I/O** in request paths (no `time.sleep()` in views)
✅ **Automated enforcement** via pre-commit hooks

---

## Core Principles

### 1. Always Use Timezone-Aware Datetimes

**WHY**: Django with `USE_TZ=True` (our setting) stores all datetimes in UTC. Naive datetimes cause silent bugs.

```python
# ✅ CORRECT: Timezone-aware
from django.utils import timezone
now = timezone.now()  # Returns aware datetime in UTC

# ❌ WRONG: Naive datetime
from datetime import datetime
now = datetime.now()  # Returns naive datetime - DO NOT USE
```

### 2. Never Use Deprecated Patterns

Python 3.12 deprecated these methods (will be removed in future Python versions):

```python
# ❌ DEPRECATED (Python 3.12+)
datetime.utcnow()                    # Use timezone.now() instead
datetime.utcfromtimestamp(ts)        # Use fromtimestamp(ts, tz=timezone.utc)

# ✅ CORRECT Replacements
from django.utils import timezone
now = timezone.now()
dt = datetime.fromtimestamp(ts, tz=timezone.utc)
```

### 3. Use Centralized Constants

**WHY**: `86400` is a magic number. `SECONDS_IN_DAY` is self-documenting.

```python
# ❌ WRONG: Magic numbers
cache.set(key, value, 86400)         # What is 86400?
timeout = 3600                       # What is 3600?

# ✅ CORRECT: Named constants
from apps.core.constants.datetime_constants import SECONDS_IN_DAY, SECONDS_IN_HOUR
cache.set(key, value, SECONDS_IN_DAY)  # Crystal clear
timeout = SECONDS_IN_HOUR              # Self-documenting
```

---

## Import Standards

### Standard Import Pattern (Python 3.12+ Compatible)

```python
# ✅ CORRECT: Aliased import to avoid conflict
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone

# Now you can use both:
utc_tz = dt_timezone.utc                    # Python's timezone
current_time = timezone.now()                # Django's timezone.now()
```

### Common Import Combinations

```python
# For basic datetime operations
from datetime import datetime, timedelta
from django.utils import timezone

# For timezone-aware creation
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone

# For constants
from apps.core.constants.datetime_constants import (
    SECONDS_IN_DAY,
    SECONDS_IN_HOUR,
    SECONDS_IN_WEEK,
    MINUTES_IN_HOUR,
    COMMON_TIMEDELTAS,
)
```

### ❌ FORBIDDEN Imports

```python
# ❌ WRONG: Name collision with django.utils.timezone
from datetime import timezone
from django.utils import timezone  # ImportError or subtle bugs!

# ❌ WRONG: Wildcard imports
from datetime import *
```

---

## Model Field Patterns

### Timestamp Fields (Creation & Modification)

**Standard Pattern**: Use `auto_now_add` for creation, `auto_now` for updates.

```python
from django.db import models

class MyModel(models.Model):
    # ✅ CORRECT: Auto-managed timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional: Add indexes for query performance
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

**Field Naming Convention**: Use `created_at` and `updated_at` (not `cdtz`/`mdtz`).

### Event Timestamps (User-Defined)

**Pattern**: Use `default=timezone.now` for user-controlled timestamps.

```python
from django.utils import timezone

class Ticket(models.Model):
    # ✅ CORRECT: User can override, defaults to now
    event_time = models.DateTimeField(default=timezone.now)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    # ❌ WRONG: Do NOT use callable with parentheses
    event_time = models.DateTimeField(default=timezone.now())  # BUG!
```

**Key Difference**:
- `auto_now_add=True`: Cannot be overridden, always set on creation
- `default=timezone.now`: Can be overridden, defaults to current time

### Optional Timestamps

```python
class WorkOrder(models.Model):
    # ✅ CORRECT: Nullable for optional events
    completed_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
```

### Complete Example

```python
from django.db import models
from django.utils import timezone

class Ticket(models.Model):
    """
    Helpdesk ticket with proper datetime fields.
    """
    # Auto-managed timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # User-defined timestamps
    due_date = models.DateTimeField(default=timezone.now)

    # Optional event timestamps
    escalated_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['due_date']),
        ]
```

---

## Datetime Creation

### Current Time

```python
from django.utils import timezone

# ✅ CORRECT: Always timezone-aware
now = timezone.now()

# ✅ CORRECT: For specific dates (test fixtures, etc.)
from datetime import datetime, timezone as dt_timezone
specific_date = datetime(2025, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
```

### From Timestamp

```python
from datetime import datetime, timezone as dt_timezone

# ✅ CORRECT: Timezone-aware from timestamp
timestamp = 1234567890
dt = datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)

# ❌ DEPRECATED: Naive datetime
dt = datetime.utcfromtimestamp(timestamp)  # Python 3.12+
```

### Relative Datetimes

```python
from datetime import timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY, COMMON_TIMEDELTAS

# ✅ CORRECT: Using timedelta
yesterday = timezone.now() - timedelta(days=1)
one_hour_ago = timezone.now() - timedelta(hours=1)

# ✅ CORRECT: Using constants dictionary
one_week_ago = timezone.now() - COMMON_TIMEDELTAS['ONE_WEEK']
thirty_days_ago = timezone.now() - COMMON_TIMEDELTAS['ONE_MONTH']
```

---

## Constants Usage

### Available Constants

From `apps/core/constants/datetime_constants.py`:

```python
# Time Conversion
SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 3600
SECONDS_IN_DAY = 86400
SECONDS_IN_WEEK = 604800

MINUTES_IN_HOUR = 60
MINUTES_IN_DAY = 1440
MINUTES_IN_WEEK = 10080

HOURS_IN_DAY = 24
HOURS_IN_WEEK = 168

DAYS_IN_WEEK = 7
DAYS_IN_MONTH_APPROX = 30
DAYS_IN_YEAR = 365
```

### Cache Timeouts

```python
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
from django.core.cache import cache

# ✅ CORRECT: Self-documenting cache timeouts
cache.set('user_session', data, SECONDS_IN_HOUR)        # 1 hour
cache.set('daily_report', report, SECONDS_IN_DAY)       # 24 hours
cache.set('weekly_metrics', metrics, SECONDS_IN_WEEK)   # 7 days

# ❌ WRONG: Magic numbers
cache.set('user_session', data, 3600)                   # What is 3600?
cache.set('daily_report', report, 86400)                # What is 86400?
```

### Rate Limiting

```python
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

# ✅ CORRECT: Clear rate limit windows
RATE_LIMIT_CONFIG = {
    'anonymous': {'calls': 10, 'period': SECONDS_IN_HOUR},
    'authenticated': {'calls': 100, 'period': SECONDS_IN_HOUR},
}

# ❌ WRONG: Magic number obscures intent
RATE_LIMIT_CONFIG = {
    'anonymous': {'calls': 10, 'period': 3600},  # What is 3600?
}
```

### Session Configuration

```python
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

# ✅ CORRECT: Settings files
SESSION_COOKIE_AGE = 2 * SECONDS_IN_HOUR  # 2 hours
SESSION_SAVE_EVERY_REQUEST = True

# ❌ WRONG: Hardcoded calculation
SESSION_COOKIE_AGE = 2 * 60 * 60  # Harder to read
```

---

## Common Patterns

### Database Query Filters

```python
from datetime import timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import COMMON_TIMEDELTAS

# ✅ CORRECT: Timezone-aware range queries
cutoff = timezone.now() - timedelta(days=30)
recent_tickets = Ticket.objects.filter(created_at__gte=cutoff)

# ✅ CORRECT: Using common timedelta constants
one_week_ago = timezone.now() - COMMON_TIMEDELTAS['ONE_WEEK']
recent_items = Item.objects.filter(updated_at__gte=one_week_ago)

# ✅ CORRECT: Complex date ranges
start_of_day = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
today_items = Item.objects.filter(created_at__gte=start_of_day)
```

### Celery Task Scheduling

```python
from datetime import timedelta
from django.utils import timezone

# ✅ CORRECT: Schedule with timezone-aware datetime
task.apply_async(
    args=[user_id],
    eta=timezone.now() + timedelta(hours=2)
)

# ✅ CORRECT: Countdown in seconds
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
task.apply_async(
    args=[user_id],
    countdown=SECONDS_IN_HOUR  # 1 hour from now
)
```

### Duration Calculations

```python
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

# ✅ CORRECT: Convert timedelta to hours
time_diff = timezone.now() - ticket.created_at
hours_open = time_diff.total_seconds() / SECONDS_IN_HOUR

# ✅ CORRECT: Human-readable duration
def format_duration(timedelta_obj):
    seconds = timedelta_obj.total_seconds()
    hours = int(seconds / SECONDS_IN_HOUR)
    minutes = int((seconds % SECONDS_IN_HOUR) / SECONDS_IN_MINUTE)
    return f"{hours}h {minutes}m"
```

### API Serialization

Django REST Framework automatically handles timezone-aware datetimes:

```python
from rest_framework import serializers

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'title', 'created_at', 'updated_at']
        # created_at and updated_at automatically serialized to ISO 8601 with timezone
```

---

## Anti-Patterns

### ❌ Deprecated datetime.utcnow()

```python
# ❌ WRONG: Deprecated in Python 3.12+
from datetime import datetime
now = datetime.utcnow()  # Returns NAIVE datetime, will be removed

# ✅ CORRECT: Use Django's timezone.now()
from django.utils import timezone
now = timezone.now()  # Returns AWARE datetime in UTC
```

### ❌ Naive datetime.now()

```python
# ❌ WRONG: Naive datetime (no timezone info)
from datetime import datetime
now = datetime.now()  # What timezone? Ambiguous!

# ✅ CORRECT: Timezone-aware
from django.utils import timezone
now = timezone.now()  # Clear: UTC datetime
```

### ❌ Import Name Collisions

```python
# ❌ WRONG: Imports conflict
from datetime import timezone
from django.utils import timezone  # Overwrites previous import!

# ✅ CORRECT: Alias to avoid collision
from datetime import timezone as dt_timezone
from django.utils import timezone
```

### ❌ Magic Numbers

```python
# ❌ WRONG: Magic numbers everywhere
cache.set(key, value, 86400)
timeout = 3600
window = 604800

# ✅ CORRECT: Named constants
from apps.core.constants.datetime_constants import (
    SECONDS_IN_DAY, SECONDS_IN_HOUR, SECONDS_IN_WEEK
)
cache.set(key, value, SECONDS_IN_DAY)
timeout = SECONDS_IN_HOUR
window = SECONDS_IN_WEEK
```

### ❌ Blocking time.sleep() in Request Paths

```python
# ❌ WRONG: Blocks worker thread
def my_view(request):
    import time
    time.sleep(5)  # BLOCKS THE ENTIRE WORKER!
    return Response(data)

# ✅ CORRECT: Use Celery for delays
from background_tasks.example import delayed_task

def my_view(request):
    delayed_task.apply_async(args=[data], countdown=5)
    return Response({'status': 'scheduled'})
```

---

## Migration Guide

### From datetime.utcnow() to timezone.now()

```python
# Before
from datetime import datetime
now = datetime.utcnow()

# After
from django.utils import timezone
now = timezone.now()
```

### From Magic Numbers to Constants

```python
# Before
cache.set('key', 'value', 3600)

# After
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
cache.set('key', 'value', SECONDS_IN_HOUR)
```

### From Naive to Aware Datetimes

```python
# Before (naive datetime)
from datetime import datetime
naive_dt = datetime(2025, 1, 1, 12, 0, 0)

# After (timezone-aware)
from datetime import datetime, timezone as dt_timezone
aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)

# Or use Django's make_aware
from django.utils import timezone
aware_dt = timezone.make_aware(naive_dt, timezone.utc)
```

---

## Testing

### Test Fixtures

```python
import pytest
from datetime import timedelta
from django.utils import timezone

@pytest.fixture
def test_timestamps():
    """Generate consistent test timestamps."""
    now = timezone.now()
    return {
        'now': now,
        'yesterday': now - timedelta(days=1),
        'one_week_ago': now - timedelta(days=7),
        'one_month_ago': now - timedelta(days=30),
    }

def test_ticket_age(test_timestamps):
    ticket = Ticket.objects.create(
        title="Test",
        created_at=test_timestamps['one_week_ago']
    )
    age = timezone.now() - ticket.created_at
    assert age.days == 7
```

### Freezing Time in Tests

```python
from freezegun import freeze_time
from django.utils import timezone

@freeze_time("2025-01-01 12:00:00")
def test_with_frozen_time():
    now = timezone.now()
    assert now.year == 2025
    assert now.month == 1
    assert now.day == 1
```

---

## Enforcement

### Pre-Commit Hooks

Located in `.githooks/pre-commit-legacy-code-check`:

```bash
# Check for deprecated datetime.utcnow()
if grep -n 'datetime\.utcnow()' "$file"; then
    echo "❌ ERROR: datetime.utcnow() is deprecated (Python 3.12+)"
    echo "   Use timezone.now() from django.utils instead"
    exit 1
fi

# Check for unaliased timezone import
if grep -n '^from datetime import timezone$' "$file"; then
    echo "❌ ERROR: Use 'from datetime import timezone as dt_timezone'"
    exit 1
fi

# Check for magic time numbers
if grep -n '\b(86400|3600|604800)\b' "$file" | grep -v 'datetime_constants'; then
    echo "⚠️  WARNING: Magic time number found"
    echo "   Use SECONDS_IN_DAY, SECONDS_IN_HOUR, SECONDS_IN_WEEK constants"
    exit 1
fi
```

### Code Quality Validation

Run validation script:

```bash
python scripts/validate_code_quality.py --verbose
```

Checks include:
- No `time.sleep()` in views/viewsets
- No `datetime.utcnow()` usage
- Proper timezone imports
- Constants usage compliance

---

## Quick Reference

### Most Common Patterns

| Task | Pattern |
|------|---------|
| Get current time | `timezone.now()` |
| Yesterday | `timezone.now() - timedelta(days=1)` |
| One hour ago | `timezone.now() - timedelta(hours=1)` |
| Cache timeout (1 hour) | `cache.set(key, val, SECONDS_IN_HOUR)` |
| Model creation timestamp | `models.DateTimeField(auto_now_add=True)` |
| Model update timestamp | `models.DateTimeField(auto_now=True)` |
| Event timestamp | `models.DateTimeField(default=timezone.now)` |
| Optional timestamp | `models.DateTimeField(null=True, blank=True)` |

### Must-Know Constants

```python
from apps.core.constants.datetime_constants import (
    SECONDS_IN_MINUTE,  # 60
    SECONDS_IN_HOUR,    # 3600
    SECONDS_IN_DAY,     # 86400
    SECONDS_IN_WEEK,    # 604800
)
```

---

## Additional Resources

- **Constants Module**: `apps/core/constants/datetime_constants.py`
- **Utility Functions**: `apps/core/utils_new/datetime_utilities.py`
- **CLAUDE.md**: Project-wide datetime standards
- **`.claude/rules.md`**: Enforced datetime rules
- **Django Docs**: https://docs.djangoproject.com/en/5.2/topics/i18n/timezones/
- **Python 3.12 Deprecations**: https://docs.python.org/3/whatsnew/3.12.html

---

**Questions or Issues?**
- Check existing tests: `apps/core/tests/test_datetime_utilities.py`
- Review timezone tests: `apps/core/tests/test_timezone_normalization.py`
- Check DST handling: `apps/scheduler/tests/test_dst_transitions.py`

---

**Last Updated**: November 3, 2025
**Maintainer**: Development Team
**Compliance Level**: A- (92% → Target: A+ 98%)
