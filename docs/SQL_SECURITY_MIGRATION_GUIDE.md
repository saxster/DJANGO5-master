# SQL Security Migration Guide for YOUTILITY3

## Overview
This guide helps developers migrate from potentially vulnerable SQL patterns to secure parameterized queries, preventing SQL injection attacks.

## Summary of Changes Made

### 1. Fixed Core Utilities
- **`apps/core/utils_new/db_utils.py`** - Updated `runrawsql()` function to prevent SQL injection
- **`apps/core/utils_new/sql_security.py`** - Created new security module for SQL operations

### 2. Fixed SQL Injection Vulnerabilities
- **`apps/activity/managers/asset_manager.py:238`** - Fixed string interpolation
- **`apps/activity/managers/job_manager.py:279`** - Fixed incorrect parameterization
- **`apps/activity/utils.py:286-294`** - Fixed parameter passing in ticketevents_query
- **`apps/onboarding/managers.py:30-42,70-79`** - Fixed f-string SQL injection

## Migration Patterns

### ❌ VULNERABLE: String Formatting
```python
# Never do this!
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)
cursor.execute("SELECT * FROM users WHERE id = {}".format(user_id))
query = "SELECT * FROM " + table_name + " WHERE id = " + str(id)
```

### ✅ SECURE: Parameterized Queries
```python
# Always use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", [user_id])
cursor.execute("SELECT * FROM users WHERE id = %s AND name = %s", [user_id, name])
```

## Using the New Security Module

### 1. Import the Security Utilities
```python
from apps.core.utils_new.sql_security import SecureSQL, secure_raw_sql
from apps.core.utils_new.db_utils import runrawsql
```

### 2. Execute PostgreSQL Functions Safely
```python
# Instead of:
self.raw(f"select fn_get_bulist({clientid}, false, true, '{type}'::text, null::{rtype}) as id;")

# Use:
results = SecureSQL.execute_function('fn_get_bulist', [clientid, False, True, type])
```

### 3. Build Safe ORDER BY Clauses
```python
# Instead of:
sql = f"SELECT * FROM ticket ORDER BY {column} {direction}"

# Use:
order_clause = SecureSQL.build_safe_order_by('ticket', column, direction)
sql = f"SELECT * FROM ticket WHERE client_id = %s {order_clause}"
cursor.execute(sql, [client_id])
```

### 4. Build Safe IN Clauses
```python
# Instead of:
ids = "1, 2, 3"
sql = f"SELECT * FROM asset WHERE id IN ({ids})"

# Use:
in_clause, in_params = SecureSQL.build_in_clause([1, 2, 3])
sql = f"SELECT * FROM asset WHERE id IN {in_clause}"
cursor.execute(sql, in_params)
```

## Common Patterns to Fix

### 1. Django Raw Queries
```python
# VULNERABLE
Model.objects.raw(f"SELECT * FROM table WHERE id = {id}")

# SECURE
Model.objects.raw("SELECT * FROM table WHERE id = %s", [id])
```

### 2. Using runrawsql()
```python
# VULNERABLE (old way with named_params=True)
runrawsql("SELECT * FROM table WHERE id = {id}", {"id": user_id}, named_params=True)

# SECURE (new way)
runrawsql("SELECT * FROM table WHERE id = %s", [user_id])
# or with named parameters
runrawsql("SELECT * FROM table WHERE id = %(id)s", {"id": user_id})
```

### 3. Dynamic Table/Column Names
```python
# If you MUST use dynamic identifiers, validate them first:
from apps.core.utils_new.sql_security import SecureSQL, ALLOWED_TABLES

table = SecureSQL.validate_identifier(table_name, ALLOWED_TABLES)
# Now 'table' is safe to use in SQL construction
```

## Checklist for Developers

- [ ] Never use string formatting (%, .format(), f-strings) with SQL queries
- [ ] Always use parameterized queries with placeholders (%s or %(name)s)
- [ ] For dynamic identifiers (table/column names), use whitelist validation
- [ ] Use the SecureSQL utilities for common patterns
- [ ] Review all .raw() calls in Django models
- [ ] Test with malicious input (e.g., `'; DROP TABLE users; --`)

## Tools for Detection

### 1. Grep for Vulnerable Patterns
```bash
# Find f-string SQL
grep -r "f[\"'].*SELECT\|f[\"'].*INSERT\|f[\"'].*UPDATE\|f[\"'].*DELETE" apps/

# Find % formatting
grep -r "cursor\.execute.*%" apps/

# Find .format() in SQL
grep -r "\.format(.*SELECT\|\.format(.*INSERT" apps/
```

### 2. Use Static Analysis
Consider using tools like:
- **bandit** - Security linter for Python
- **sqlparse** - SQL parsing library
- **Custom pre-commit hooks** to detect SQL injection patterns

## Testing Your Changes

### 1. Unit Test Example
```python
def test_sql_injection_prevention(self):
    # Try to inject SQL
    malicious_input = "1'; DROP TABLE users; --"

    # This should be safe
    results = SecureSQL.execute_function('fun_getjobneed',
        [malicious_input, 1, 1])

    # Verify tables still exist
    self.assertTrue(User.objects.exists())
```

### 2. Manual Testing
Always test with inputs like:
- `' OR '1'='1`
- `'; DROP TABLE users; --`
- `1 UNION SELECT * FROM users`

## Resources

- [Django Security - SQL Injection](https://docs.djangoproject.com/en/stable/topics/security/#sql-injection-protection)
- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [PostgreSQL Parameterized Queries](https://www.postgresql.org/docs/current/sql-prepare.html)

## Questions or Issues?

If you find any SQL injection vulnerabilities or have questions about secure patterns:
1. Check the `apps/core/utils_new/sql_security.py` module
2. Review this guide
3. Ask the security team for clarification

Remember: **When in doubt, use parameterized queries!**
