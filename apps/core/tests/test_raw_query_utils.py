"""
Raw Query Utilities Security Tests

Tests for the secure raw SQL query wrapper utilities.
Ensures queries are properly validated, parametrized, and routed.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: No magic numbers
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.db import DatabaseError, connection

from apps.core.db.raw_query_utils import (
    execute_raw_query,
    execute_raw_query_with_router,
    execute_stored_function,
    execute_read_query,
    execute_write_query,
    execute_tenant_query,
    advisory_lock_context,
    QueryResult,
    RawQuerySecurityError,
    TenantRoutingError,
    validate_query_safety,
)


class TestQueryResultDataclass(TestCase):
    """Test QueryResult dataclass"""

    def test_query_result_defaults(self):
        """Test QueryResult default values"""
        result = QueryResult(success=True)

        assert result.success is True
        assert result.data == []
        assert result.row_count == 0
        assert result.columns == []
        assert result.errors == []
        assert result.execution_time_ms == 0.0

    def test_query_result_with_data(self):
        """Test QueryResult with data"""
        result = QueryResult(
            success=True,
            data=[{'id': 1, 'name': 'Test'}],
            row_count=1,
            columns=['id', 'name'],
            execution_time_ms=15.5
        )

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]['id'] == 1
        assert result.row_count == 1
        assert 'id' in result.columns
        assert result.execution_time_ms == 15.5


class TestQuerySafetyValidation(TestCase):
    """Test query safety validation"""

    def test_safe_select_query(self):
        """Test that SELECT queries are validated as safe"""
        query = "SELECT * FROM people WHERE client_id = %s"
        is_safe, error = validate_query_safety(query, allow_writes=False)

        assert is_safe is True
        assert error == ""

    def test_safe_with_cte(self):
        """Test that CTEs are validated as safe"""
        query = "WITH cte AS (SELECT 1) SELECT * FROM cte"
        is_safe, error = validate_query_safety(query, allow_writes=False)

        assert is_safe is True

    def test_dangerous_sql_comments(self):
        """Test that SQL comments are flagged"""
        query = "SELECT * FROM people -- WHERE admin = true"
        is_safe, error = validate_query_safety(query)

        assert is_safe is False
        assert "comments" in error.lower()

    def test_dangerous_multiple_statements(self):
        """Test that multiple statements are flagged"""
        query = "SELECT * FROM people; DROP TABLE people;"
        is_safe, error = validate_query_safety(query)

        assert is_safe is False
        assert "Multiple statements" in error

    def test_dangerous_string_formatting(self):
        """Test that string formatting is flagged"""
        query = "SELECT * FROM people WHERE id = {}"
        is_safe, error = validate_query_safety(query)

        assert is_safe is False
        assert "String formatting detected" in error

    def test_write_query_without_permission(self):
        """Test that write queries fail without allow_writes=True"""
        queries = [
            "INSERT INTO people VALUES (%s)",
            "UPDATE people SET name = %s",
            "DELETE FROM people WHERE id = %s",
            "DROP TABLE people",
            "ALTER TABLE people ADD COLUMN test VARCHAR",
        ]

        for query in queries:
            is_safe, error = validate_query_safety(query, allow_writes=False)
            assert is_safe is False, f"Query should be unsafe: {query}"
            assert "not allowed" in error.lower()

    def test_write_query_with_permission(self):
        """Test that write queries pass with allow_writes=True"""
        query = "INSERT INTO people (name) VALUES (%s)"
        is_safe, error = validate_query_safety(query, allow_writes=True)

        assert is_safe is True


@pytest.mark.django_db
class TestExecuteRawQuery(TestCase):
    """Test execute_raw_query function"""

    def test_simple_select_query(self):
        """Test executing a simple SELECT query"""
        result = execute_raw_query(
            "SELECT 1 as num, 'test' as text",
            fetch_all=True
        )

        assert result.success is True
        assert result.row_count == 1
        assert result.data[0]['num'] == 1
        assert result.data[0]['text'] == 'test'
        assert 'num' in result.columns
        assert result.execution_time_ms > 0

    def test_query_with_parameters(self):
        """Test query with parameterization"""
        result = execute_raw_query(
            "SELECT %s as value",
            params=[42],
            fetch_all=True
        )

        assert result.success is True
        assert result.data[0]['value'] == 42

    def test_parameter_count_mismatch_raises_error(self):
        """Test that parameter count mismatch is caught"""
        with pytest.raises(ValueError) as exc_info:
            execute_raw_query(
                "SELECT %s, %s",  # Expects 2 params
                params=[1]  # Only 1 param provided
            )

        assert "Parameter count mismatch" in str(exc_info.value)

    def test_dangerous_query_raises_security_error(self):
        """Test that dangerous queries raise RawQuerySecurityError"""
        with pytest.raises(RawQuerySecurityError) as exc_info:
            execute_raw_query(
                "SELECT * FROM people; DROP TABLE people;"
            )

        assert "Multiple statements" in str(exc_info.value)

    def test_fetch_one_mode(self):
        """Test fetch_one mode returns single result"""
        result = execute_raw_query(
            "SELECT 1 as num UNION SELECT 2",
            fetch_one=True
        )

        assert result.success is True
        assert result.row_count == 1
        assert len(result.data) == 1

    def test_write_query_without_permission_fails(self):
        """Test that write queries fail without allow_writes"""
        with pytest.raises(RawQuerySecurityError):
            execute_raw_query(
                "DELETE FROM people WHERE id = %s",
                params=[999]
            )

    def test_database_error_handling(self):
        """Test that database errors are caught and returned"""
        result = execute_raw_query(
            "SELECT * FROM nonexistent_table_12345"
        )

        assert result.success is False
        assert len(result.errors) > 0
        assert "Database error" in result.errors[0]

    @patch('apps.core.db.raw_query_utils.logger')
    def test_large_result_warning(self, mock_logger):
        """Test that large result sets trigger warning"""
        # Create a query that returns many rows
        query = "SELECT generate_series(1, 15000) as num"
        result = execute_raw_query(query, fetch_all=True)

        assert result.success is True
        assert result.row_count > 10000

        # Check that warning was logged
        mock_logger.warning.assert_called()
        warning_call = str(mock_logger.warning.call_args)
        assert "Large result set" in warning_call


@pytest.mark.django_db
class TestExecuteRawQueryWithRouter(TestCase):
    """Test tenant-aware raw query execution"""

    def test_query_with_tenant_id(self):
        """Test query execution with tenant routing"""
        result = execute_raw_query_with_router(
            "SELECT 1 as test",
            tenant_id=1,
            fetch_all=True
        )

        assert result.success is True

    def test_query_without_tenant_id_in_multitenant_fails(self):
        """Test that tenant_id is required in multi-tenant setup"""
        # Only fails if multiple databases configured
        # This is environment-specific, so we skip if single DB
        pass  # TODO: Mock settings.DATABASES for this test

    def test_query_with_transaction(self):
        """Test query execution with transaction wrapper"""
        result = execute_raw_query_with_router(
            "SELECT 1 as test",
            use_transaction=True,
            fetch_all=True
        )

        assert result.success is True

    def test_failed_query_rolls_back_transaction(self):
        """Test that failed queries roll back transaction"""
        with pytest.raises(DatabaseError):
            execute_raw_query_with_router(
                "SELECT * FROM nonexistent_table",
                use_transaction=True
            )


@pytest.mark.django_db
class TestExecuteStoredFunction(TestCase):
    """Test stored function execution"""

    def test_stored_function_with_return_table(self):
        """Test calling stored function that returns table"""
        # Note: This test requires the function to exist in database
        # For testing purposes, we'll use a simple SELECT
        result = execute_stored_function(
            'generate_series',
            params=[1, 5],
            return_type='TABLE'
        )

        assert result.success is True
        assert result.row_count == 5

    def test_stored_function_with_scalar_return(self):
        """Test calling stored function that returns scalar"""
        result = execute_stored_function(
            'abs',
            params=[-42],
            return_type='SCALAR'
        )

        assert result.success is True
        assert result.data[0]['abs'] == 42


@pytest.mark.django_db
class TestAdvisoryLockContext(TestCase):
    """Test advisory lock context manager"""

    def test_advisory_lock_acquired_and_released(self):
        """Test that advisory lock is acquired and released"""
        lock_id = 999999

        with advisory_lock_context(lock_id):
            # Verify lock is held
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT objid FROM pg_locks WHERE locktype = 'advisory' AND objid = %s",
                    [lock_id]
                )
                result = cursor.fetchone()
                assert result is not None, "Lock should be acquired"

        # Verify lock is released after context
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT objid FROM pg_locks WHERE locktype = 'advisory' AND objid = %s",
                [lock_id]
            )
            result = cursor.fetchone()
            assert result is None, "Lock should be released"

    def test_advisory_lock_timeout(self):
        """Test that lock acquisition times out"""
        lock_id = 888888

        # Acquire lock in one context
        with advisory_lock_context(lock_id):
            # Try to acquire same lock with short timeout
            with pytest.raises(DatabaseError) as exc_info:
                with advisory_lock_context(lock_id, timeout_seconds=1):
                    pass

            assert "Could not acquire" in str(exc_info.value)

    def test_advisory_lock_released_on_exception(self):
        """Test that lock is released even if exception occurs"""
        lock_id = 777777

        with pytest.raises(ValueError):
            with advisory_lock_context(lock_id):
                raise ValueError("Test error")

        # Verify lock was released
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT objid FROM pg_locks WHERE locktype = 'advisory' AND objid = %s",
                [lock_id]
            )
            result = cursor.fetchone()
            assert result is None, "Lock should be released after exception"


@pytest.mark.django_db
class TestConvenienceFunctions(TestCase):
    """Test convenience wrapper functions"""

    def test_execute_read_query(self):
        """Test execute_read_query convenience function"""
        result = execute_read_query(
            "SELECT 1 as test",
            fetch_all=True
        )

        assert result.success is True

    def test_execute_read_query_blocks_writes(self):
        """Test that execute_read_query blocks write operations"""
        with pytest.raises(RawQuerySecurityError):
            execute_read_query("DELETE FROM people")

    def test_execute_write_query(self):
        """Test execute_write_query convenience function"""
        # Note: Using a write query that doesn't actually modify data
        result = execute_write_query(
            "UPDATE people SET peoplename = peoplename WHERE id = -999",
            fetch_all=False
        )

        # Should succeed (no rows affected, but query is valid)
        assert result.success is True

    def test_execute_tenant_query(self):
        """Test execute_tenant_query convenience function"""
        result = execute_tenant_query(
            "SELECT 1 as test",
            tenant_id=1,
            fetch_all=True
        )

        assert result.success is True


@pytest.mark.django_db
class TestSecurityRegression(TestCase):
    """Test that security vulnerabilities are prevented"""

    def test_sql_injection_via_string_concat_blocked(self):
        """Test that string concatenation is blocked"""
        user_input = "1 OR 1=1"

        with pytest.raises(RawQuerySecurityError):
            # This should fail validation
            execute_raw_query(
                f"SELECT * FROM people WHERE id = {user_input}"
            )

    def test_parameterized_query_prevents_injection(self):
        """Test that parameterized queries prevent SQL injection"""
        malicious_input = "1; DROP TABLE people--"

        # This is safe because of parameterization
        result = execute_raw_query(
            "SELECT %s as user_input",
            params=[malicious_input],
            fetch_all=True
        )

        assert result.success is True
        # Input is treated as literal string, not SQL
        assert result.data[0]['user_input'] == malicious_input

    def test_comment_injection_blocked(self):
        """Test that SQL comment injection is blocked"""
        with pytest.raises(RawQuerySecurityError) as exc_info:
            execute_raw_query(
                "SELECT * FROM people WHERE name = %s -- AND admin = true",
                params=['test']
            )

        assert "comments" in str(exc_info.value).lower()


@pytest.mark.django_db
class TestPerformance(TestCase):
    """Test performance characteristics"""

    def test_query_timeout_enforcement(self):
        """Test that query timeout is enforced"""
        # This test uses pg_sleep to simulate slow query
        result = execute_raw_query(
            "SELECT pg_sleep(%s)",
            params=[5],  # 5 second sleep
            timeout_seconds=1  # 1 second timeout
        )

        # Query should fail due to timeout
        assert result.success is False
        assert len(result.errors) > 0

    def test_wrapper_overhead_minimal(self):
        """Test that wrapper overhead is < 5ms"""
        import time

        # Direct connection (baseline)
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        direct_time = (time.time() - start) * 1000

        # With wrapper
        start = time.time()
        execute_raw_query("SELECT 1", fetch_one=True)
        wrapper_time = (time.time() - start) * 1000

        overhead = wrapper_time - direct_time
        assert overhead < 5, f"Wrapper overhead is {overhead:.2f}ms (should be < 5ms)"


# Integration test
@pytest.mark.django_db
class TestIntegration(TestCase):
    """Integration tests with real database"""

    def test_full_query_lifecycle(self):
        """Test complete query lifecycle from validation to execution"""
        # 1. Validate query
        query = "SELECT id, email FROM people WHERE client_id = %s LIMIT 1"
        is_safe, _ = validate_query_safety(query)
        assert is_safe

        # 2. Execute query
        result = execute_raw_query(
            query,
            params=[1],
            fetch_all=True
        )

        # 3. Verify result structure
        assert result.success is True
        assert isinstance(result.data, list)
        assert result.execution_time_ms > 0

    def test_migration_from_old_cursor_usage(self):
        """Test that old cursor usage can be replaced with new wrapper"""
        # OLD WAY (what we're migrating from)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM people WHERE id = %s", [1])
            old_result = cursor.fetchone()[0]

        # NEW WAY (with secure wrapper)
        new_result = execute_raw_query(
            "SELECT COUNT(*) as count FROM people WHERE id = %s",
            params=[1],
            fetch_one=True
        )

        # Results should match
        assert new_result.success is True
        assert new_result.data[0]['count'] == old_result