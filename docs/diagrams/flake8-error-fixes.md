# Quick Fix: Flake8 Errors

**Lookup table for common flake8 violations**

---

## Common Errors

| Error Code | Violation | Fix | Example |
|------------|-----------|-----|---------|
| **E722** | Bare except block | Use specific exception from patterns.py | See below |
| **T001** | Print statement | Replace with `logger.info()` or `logger.debug()` | See below |
| **C901** | Complexity >10 | Extract method, simplify conditionals | See below |
| **E501** | Line too long (>120) | Break into multiple lines | Use `\` or implicit continuation |
| **W503** | Line break before operator | Move operator to end of line | Or ignore (style preference) |

---

## E722: Bare Except Block

❌ **FORBIDDEN:**
```python
try:
    user.save()
except:  # ❌ E722: bare except
    logger.error("Error")
```

✅ **FIX:**
```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

try:
    user.save()
except DATABASE_EXCEPTIONS as e:  # ✅ Specific exception
    logger.error(f"Database error: {e}", exc_info=True)
    raise
```

**Available exception groups:**
- `DATABASE_EXCEPTIONS`
- `NETWORK_EXCEPTIONS`
- `FILE_EXCEPTIONS`
- `VALIDATION_EXCEPTIONS`

**Location:** `apps/core/exceptions/patterns.py`

---

## T001: Print Statement

❌ **FORBIDDEN:**
```python
def process_data(data):
    print(f"Processing {len(data)} items")  # ❌ T001: print found
    # ...
```

✅ **FIX:**
```python
import logging
logger = logging.getLogger(__name__)

def process_data(data):
    logger.info(f"Processing {len(data)} items")  # ✅ Proper logging
    # ...
```

**Exception:** CLI scripts can use print with inline ignore:
```python
print("CLI output")  # noqa: T001
```

**Requires:** `pip install flake8-print`

---

## C901: Cyclomatic Complexity > 10

❌ **FORBIDDEN:**
```python
def complex_function(data):
    if condition1:
        if condition2:
            if condition3:
                if condition4:  # ❌ C901: complexity 15
                    # Deep nesting
```

✅ **FIX: Extract methods**
```python
def complex_function(data):
    if not self._validate_preconditions(data):
        return None
    return self._process_data(data)

def _validate_preconditions(self, data):
    return condition1 and condition2

def _process_data(self, data):
    # Simpler logic
```

✅ **FIX: Early returns**
```python
def complex_function(data):
    if not condition1:
        return None
    if not condition2:
        return None
    # Process (reduced nesting)
```

---

## Quick Commands

```bash
# Run flake8
flake8 apps/

# Check specific file
flake8 apps/peoples/models/user_model.py

# Show statistics
flake8 apps/ --statistics

# Ignore specific errors (temporary)
flake8 apps/ --ignore=E501,W503

# Generate report
flake8 apps/ --output-file=flake8_report.txt
```

---

**See also:**
- [RULES.md](../RULES.md) - All mandatory patterns
- [REFERENCE.md](../REFERENCE.md#code-quality-tools) - Validation scripts
