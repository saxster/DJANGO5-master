# Exception Handling Quick Reference Guide

**For**: Development Team  
**Purpose**: Quick patterns for replacing broad `except Exception` handlers  
**Rule**: .claude/rules.md #1 - NO GENERIC EXCEPTIONS

## Import First

```python
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    FILE_EXCEPTIONS,
    JSON_EXCEPTIONS,
    PARSING_EXCEPTIONS,
    BUSINESS_LOGIC_EXCEPTIONS
)
```

## Pattern 1: Database Operations

### ❌ Before
```python
try:
    user.save()
except Exception as e:
    logger.error(f"Save failed: {e}")
```

### ✅ After
```python
try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(
        f"Database error saving user {user.id}: {e}",
        exc_info=True,
        extra={'user_id': user.id, 'username': user.username}
    )
    raise  # Re-raise for transaction rollback
```

## Pattern 2: Network API Calls

### ❌ Before
```python
try:
    response = requests.get(url)
    return response.json()
except Exception as e:
    logger.error(f"API failed: {e}")
    return None
```

### ✅ After
```python
try:
    response = requests.get(url, timeout=(5, 15))  # REQUIRED
    response.raise_for_status()
    return response.json()
except requests.Timeout as e:
    logger.warning(f"API timeout for {url}: {e}")
    return None  # Graceful fallback
except requests.HTTPError as e:
    logger.error(
        f"HTTP {e.response.status_code} from {url}: {e}",
        exc_info=True,
        extra={'url': url, 'status': e.response.status_code}
    )
    raise  # Re-raise for critical errors
except NETWORK_EXCEPTIONS as e:
    logger.error(
        f"Network error calling {url}: {e}",
        exc_info=True,
        extra={'url': url}
    )
    return None
```

## Pattern 3: File Operations

### ❌ Before
```python
try:
    with open(path, 'r') as f:
        return f.read()
except Exception as e:
    logger.error(f"Read failed: {e}")
    return ""
```

### ✅ After
```python
try:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
except FileNotFoundError as e:
    logger.warning(f"File not found: {path}")
    return get_default_content()  # Fallback
except PermissionError as e:
    logger.error(
        f"Permission denied reading {path}: {e}",
        exc_info=True,
        extra={'path': path}
    )
    raise  # Critical error
except FILE_EXCEPTIONS as e:
    logger.error(
        f"File error reading {path}: {e}",
        exc_info=True,
        extra={'path': path}
    )
    raise
```

## Pattern 4: JSON Parsing

### ❌ Before
```python
try:
    data = json.loads(json_string)
    return data
except Exception as e:
    logger.error(f"Parse failed: {e}")
    return {}
```

### ✅ After
```python
try:
    data = json.loads(json_string)
    # Validate required keys
    if 'id' not in data:
        raise KeyError("Missing required key: id")
    return data
except json.JSONDecodeError as e:
    logger.error(
        f"Invalid JSON format: {e}",
        exc_info=True,
        extra={'json_length': len(json_string)}
    )
    return {}
except KeyError as e:
    logger.error(f"Missing required JSON key: {e}")
    return {}
except JSON_EXCEPTIONS as e:
    logger.error(f"JSON processing error: {e}", exc_info=True)
    return {}
```

## Pattern 5: Data Parsing/Validation

### ❌ Before
```python
try:
    value = int(data['count'])
    return calculate(value)
except Exception as e:
    logger.error(f"Failed: {e}")
    return 0
```

### ✅ After
```python
try:
    value = int(data['count'])
    return calculate(value)
except KeyError as e:
    logger.error(f"Missing required field: {e}")
    return 0
except ValueError as e:
    logger.error(
        f"Invalid number format: {e}",
        exc_info=True,
        extra={'value': data.get('count')}
    )
    return 0
except PARSING_EXCEPTIONS as e:
    logger.error(
        f"Data parsing error: {e}",
        exc_info=True,
        extra={'data': data}
    )
    return 0
```

## Pattern 6: Business Logic

### ❌ Before
```python
try:
    validate_ticket(ticket)
    process_ticket(ticket)
except Exception as e:
    logger.error(f"Failed: {e}")
```

### ✅ After
```python
from django.core.exceptions import ValidationError

try:
    validate_ticket(ticket)
    process_ticket(ticket)
except ValidationError as e:
    logger.warning(
        f"Ticket validation failed: {e}",
        extra={'ticket_id': ticket.id}
    )
    raise  # Let caller handle
except BUSINESS_LOGIC_EXCEPTIONS as e:
    logger.error(
        f"Business logic error processing ticket {ticket.id}: {e}",
        exc_info=True,
        extra={'ticket_id': ticket.id, 'status': ticket.status}
    )
    raise
```

## Decision Tree

```
What operation is being performed?
│
├─ Database query/save? → DATABASE_EXCEPTIONS
│
├─ HTTP request/API call? → NETWORK_EXCEPTIONS + timeout
│
├─ File read/write? → FILE_EXCEPTIONS
│
├─ JSON parse/dumps? → JSON_EXCEPTIONS
│
├─ Data parsing/conversion? → PARSING_EXCEPTIONS
│
└─ Business rule validation? → BUSINESS_LOGIC_EXCEPTIONS
```

## Best Practices

### ✅ DO
- Always add `exc_info=True` for full stack trace
- Include contextual `extra` fields for correlation
- Use specific exceptions first, then broader tuples
- Re-raise critical errors with `raise`
- Provide graceful fallbacks for non-critical errors
- Add timeouts to all network calls: `timeout=(5, 15)`

### ❌ DON'T
- Use bare `except Exception`
- Swallow errors without logging
- Log errors without context
- Return `None` from critical operations
- Forget to validate after parsing
- Make network calls without timeouts

## Exception Type Reference

| Type | When to Use | Common Exceptions |
|------|-------------|-------------------|
| `DATABASE_EXCEPTIONS` | Model.save(), queries, transactions | IntegrityError, OperationalError, DataError |
| `NETWORK_EXCEPTIONS` | requests.get/post, API calls | ConnectionError, Timeout, HTTPError |
| `FILE_EXCEPTIONS` | open(), file I/O | FileNotFoundError, PermissionError, IOError |
| `JSON_EXCEPTIONS` | json.loads/dumps | ValueError, TypeError, KeyError |
| `PARSING_EXCEPTIONS` | Data conversion, validation | ValueError, TypeError, KeyError, AttributeError |
| `BUSINESS_LOGIC_EXCEPTIONS` | Custom validation, rules | ValidationError, ValueError, TypeError |

## Testing Your Changes

### 1. Syntax Check
```bash
python3 -m py_compile path/to/your/file.py
```

### 2. Import Check
```python
python3 -c "from your.module import YourClass; print('✅')"
```

### 3. Unit Test
```python
def test_error_handling(mocker):
    # Mock to raise specific exception
    mocker.patch('Model.objects.get', side_effect=ObjectDoesNotExist)
    
    # Should handle gracefully
    result = service.get_item(123)
    assert result is None
```

## Common Mistakes

### Mistake 1: Too Broad
```python
# ❌ Still too broad
except (ValueError, TypeError, KeyError, AttributeError, IOError):
    pass
```
**Fix**: Use the predefined tuple
```python
# ✅ Use pattern tuple
except PARSING_EXCEPTIONS:
    pass
```

### Mistake 2: No Context
```python
# ❌ No context
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Error: {e}")
```
**Fix**: Add contextual information
```python
# ✅ With context
except DATABASE_EXCEPTIONS as e:
    logger.error(
        f"Database error saving ticket {ticket.id}: {e}",
        exc_info=True,
        extra={'ticket_id': ticket.id, 'status': ticket.status}
    )
```

### Mistake 3: Silent Failure
```python
# ❌ Swallows error
except FILE_EXCEPTIONS:
    pass
```
**Fix**: Log and handle appropriately
```python
# ✅ Logs and provides fallback
except FILE_EXCEPTIONS as e:
    logger.error(f"File error: {e}", exc_info=True)
    return get_default_config()
```

## Pre-Commit Hook

Add to `.pre-commit-config.yaml`:
```yaml
- id: check-broad-exceptions
  name: Check for broad exception handlers
  entry: bash -c 'if git diff --cached --name-only | xargs grep -l "except Exception"; then echo "ERROR: Broad exception handler found"; exit 1; fi'
  language: system
  pass_filenames: false
```

## Help & Resources

- **Exception Patterns**: `apps/core/exceptions/patterns.py`
- **Examples**: See fixed files in apps/y_helpdesk/services/
- **Rules**: `.claude/rules.md` Rule #1
- **Questions**: Ask in #development Slack channel

---

**Quick Reference Version**: 1.0  
**Last Updated**: 2025-11-06  
**Status**: ✅ Active - Use for all new code
