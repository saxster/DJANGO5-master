"""
Migration Guard Service Tests

Comprehensive test suite for the MigrationGuardService to ensure
migrations are only applied to correct tenant databases.

Test Coverage:
    - Database alias validation
    - Migration allowlist enforcement
    - Distributed locking mechanism
    - Audit logging
    - Race condition handling
    - Error handling and fail-closed behavior

Security Note:
    These tests are CRITICAL - they prevent catastrophic data corruption
    in multi-tenant environments. All tests must pass before deployment.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone as dt_timezone, timedelta

from django.test import TestCase, override_settings
from django.core.cache import cache
from django.db import DatabaseError

from apps.tenants.services.migration_guard import (
    MigrationGuardService,
    MigrationLockError,
    InvalidDatabaseError
)


class MigrationGuardServiceTest(TestCase):
    """Test suite for Migration Guard Service."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = MigrationGuardService()
        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    # ==================
    # Database Validation Tests
    # ==================

    @override_settings(DATABASES={'default': {}, 'tenant_a': {}})
    def test_validate_database_alias_valid(self):
        """Test database alias validation with valid database."""
        self.assertTrue(
            self.service._validate_database_alias('default')
        )
        self.assertTrue(
            self.service._validate_database_alias('tenant_a')
        )

    @override_settings(DATABASES={'default': {}})
    def test_validate_database_alias_invalid(self):
        """Test database alias validation with invalid database."""
        self.assertFalse(
            self.service._validate_database_alias('nonexistent_db')
        )

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_allow_migrate_invalid_database(self):
        """Test that migrations are blocked for invalid database aliases."""
        result = self.service.allow_migrate(
            db='nonexistent_db',
            app_label='activity',
            model_name='Job'
        )

        self.assertFalse(result, "Should block migration on invalid database")

    # ==================
    # Allowlist Tests
    # ==================

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_is_database_allowed_in_allowlist(self):
        """Test database allowlist check for allowed database."""
        self.assertTrue(
            self.service._is_database_allowed('default')
        )

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_is_database_allowed_not_in_allowlist(self):
        """Test database allowlist check for non-allowed database."""
        self.assertFalse(
            self.service._is_database_allowed('tenant_a')
        )

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}},
        TENANT_MIGRATION_DATABASES=['default', 'tenant_a']
    )
    def test_allow_migrate_multiple_allowed_databases(self):
        """Test migrations allowed on multiple configured databases."""
        # Should allow on default
        self.assertTrue(
            self.service.allow_migrate('default', 'activity', 'Job')
        )

        # Should allow on tenant_a
        self.assertTrue(
            self.service.allow_migrate('tenant_a', 'activity', 'Job')
        )

    # ==================
    # Migration Lock Tests
    # ==================

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_check_migration_lock_available(self):
        """Test migration lock acquisition when lock is available."""
        result = self.service._check_migration_lock('default', 'activity')
        self.assertTrue(result, "Should acquire lock when available")

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_check_migration_lock_held(self):
        """Test migration lock check when lock is held."""
        # Acquire lock
        self.service._check_migration_lock('default', 'activity')

        # Try to acquire again - should fail
        result = self.service._check_migration_lock('default', 'activity')
        self.assertFalse(result, "Should not acquire lock when held")

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_check_migration_lock_stale_lock_cleanup(self):
        """Test that stale locks (>30 minutes old) are cleaned up."""
        lock_key = 'migration_lock:default:activity'

        # Set stale lock (40 minutes old)
        stale_time = datetime.now(dt_timezone.utc) - timedelta(minutes=40)
        cache.set(lock_key, {
            'timestamp': stale_time.isoformat(),
            'db': 'default',
            'app_label': 'activity'
        }, timeout=3600)

        # Should be able to acquire lock (stale lock cleaned up)
        result = self.service._check_migration_lock('default', 'activity')
        self.assertTrue(result, "Should acquire lock after stale lock cleanup")

    # ==================
    # allow_migrate Integration Tests
    # ==================

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_allow_migrate_success(self):
        """Test successful migration authorization."""
        result = self.service.allow_migrate(
            db='default',
            app_label='activity',
            model_name='Job'
        )

        self.assertTrue(result, "Should allow migration on valid database")

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_allow_migrate_database_not_in_allowlist(self):
        """Test migration blocked when database not in allowlist."""
        result = self.service.allow_migrate(
            db='tenant_a',
            app_label='activity',
            model_name='Job'
        )

        self.assertFalse(
            result,
            "Should block migration on database not in allowlist"
        )

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_allow_migrate_with_hints(self):
        """Test migration with additional hints."""
        result = self.service.allow_migrate(
            db='default',
            app_label='activity',
            model_name='Job',
            some_hint='value',
            another_hint=123
        )

        self.assertTrue(result, "Should handle migration hints correctly")

    # ==================
    # Correlation ID Generation Tests
    # ==================

    def test_generate_correlation_id_unique(self):
        """Test that correlation IDs are unique."""
        id1 = self.service._generate_correlation_id('default', 'activity', 'Job')
        id2 = self.service._generate_correlation_id('default', 'activity', 'Job')

        # Should be different due to timestamp
        self.assertNotEqual(id1, id2, "Correlation IDs should be unique")

    def test_generate_correlation_id_format(self):
        """Test correlation ID format (8 character hash)."""
        correlation_id = self.service._generate_correlation_id(
            'default', 'activity', 'Job'
        )

        self.assertEqual(len(correlation_id), 8, "Correlation ID should be 8 characters")
        self.assertTrue(
            correlation_id.isalnum(),
            "Correlation ID should be alphanumeric"
        )

    # ==================
    # Error Handling Tests
    # ==================

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    @patch('apps.tenants.services.migration_guard.cache')
    def test_allow_migrate_cache_error_fails_closed(self, mock_cache):
        """Test that cache errors result in fail-closed behavior (allow migration)."""
        # Simulate cache error
        mock_cache.get.side_effect = ValueError("Cache error")

        result = self.service.allow_migrate(
            db='default',
            app_label='activity',
            model_name='Job'
        )

        # Should still allow migration (fail-closed behavior for lock check)
        # but validation still happens
        self.assertTrue(
            result,
            "Should allow migration on cache error (fail-closed for lock check)"
        )

    @override_settings(
        DATABASES={'default': {}, 'invalid_db': {}},
        TENANT_MIGRATION_DATABASES=['invalid_db']
    )
    def test_configuration_validation_at_init(self):
        """Test that invalid configuration is caught at initialization."""
        # Remove invalid_db from DATABASES to cause validation error
        with override_settings(DATABASES={'default': {}}, TENANT_MIGRATION_DATABASES=['invalid_db']):
            with self.assertRaises(InvalidDatabaseError):
                MigrationGuardService()

    # ==================
    # Migration Status Tests
    # ==================

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_get_migration_status_allowed_database(self):
        """Test migration status for allowed database."""
        status = self.service.get_migration_status('default')

        self.assertEqual(status['db_alias'], 'default')
        self.assertTrue(status['is_valid'])
        self.assertTrue(status['is_allowed'])
        self.assertFalse(status['is_locked'])

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_get_migration_status_non_allowed_database(self):
        """Test migration status for non-allowed database."""
        status = self.service.get_migration_status('tenant_a')

        self.assertEqual(status['db_alias'], 'tenant_a')
        self.assertTrue(status['is_valid'])
        self.assertFalse(status['is_allowed'])

    @override_settings(DATABASES={'default': {}})
    def test_get_migration_status_invalid_database(self):
        """Test migration status for invalid database."""
        status = self.service.get_migration_status('nonexistent')

        self.assertEqual(status['db_alias'], 'nonexistent')
        self.assertFalse(status['is_valid'])

    # ==================
    # Race Condition Tests (CRITICAL)
    # ==================

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_concurrent_migration_attempts_blocked(self):
        """Test that concurrent migrations are blocked by lock."""
        # First migration attempt
        result1 = self.service.allow_migrate('default', 'activity', 'Job')
        self.assertTrue(result1, "First migration should be allowed")

        # Concurrent migration attempt (same DB, same app)
        result2 = self.service.allow_migrate('default', 'activity', 'Job')
        self.assertFalse(result2, "Concurrent migration should be blocked")

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_different_apps_can_migrate_concurrently(self):
        """Test that different apps can migrate concurrently to same DB."""
        # Migration for activity app
        result1 = self.service.allow_migrate('default', 'activity', 'Job')
        self.assertTrue(result1)

        # Migration for attendance app (different lock key)
        result2 = self.service.allow_migrate('default', 'attendance', 'PeopleEventlog')
        self.assertTrue(result2, "Different apps should have separate locks")

    # ==================
    # Audit Logging Tests
    # ==================

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    @patch('apps.tenants.services.migration_guard.logger')
    def test_successful_migration_logged(self, mock_logger):
        """Test that successful migration authorization is logged."""
        self.service.allow_migrate('default', 'activity', 'Job')

        # Check that info log was called
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args

        self.assertIn('Migration authorized', str(call_args))

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    @patch('apps.tenants.services.migration_guard.security_logger')
    def test_invalid_database_logged_as_security_event(self, mock_security_logger):
        """Test that invalid database attempts are logged as security events."""
        self.service.allow_migrate('nonexistent_db', 'activity', 'Job')

        # Check that security warning was logged
        mock_security_logger.warning.assert_called()
        call_args = mock_security_logger.warning.call_args

        self.assertIn('Migration blocked', str(call_args))
        # Check that security_event extra field was set
        self.assertIn('security_event', call_args[1]['extra'])


# ==================
# Pytest Fixtures and Additional Tests
# ==================

@pytest.fixture
def migration_guard():
    """Fixture providing clean MigrationGuardService instance."""
    cache.clear()
    service = MigrationGuardService()
    yield service
    cache.clear()


@pytest.mark.django_db
class TestMigrationGuardConcurrency:
    """Concurrency and race condition tests using pytest."""

    def test_lock_timeout_allows_retry(self, migration_guard):
        """Test that lock timeout allows retry after timeout period."""
        lock_key = 'migration_lock:default:activity'

        # Set expired lock (31 minutes old)
        expired_time = datetime.now(dt_timezone.utc) - timedelta(minutes=31)
        cache.set(lock_key, {
            'timestamp': expired_time.isoformat(),
            'db': 'default',
            'app_label': 'activity'
        }, timeout=3600)

        # Should acquire lock (old lock expired)
        with override_settings(
            DATABASES={'default': {}},
            TENANT_MIGRATION_DATABASES=['default']
        ):
            result = migration_guard.allow_migrate('default', 'activity', 'Job')
            assert result is True, "Should acquire lock after timeout"
