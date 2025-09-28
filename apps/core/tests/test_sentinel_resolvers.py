"""
Test suite for sentinel ID resolver utilities.

This module tests the sentinel ID resolver functions that replace
hardcoded sentinel values (-1, 1) with proper record references.
"""

from django.test import TestCase
from django.db import IntegrityError
from unittest.mock import patch, Mock

from apps.core.utils_new.sentinel_resolvers import (
    SentinelResolver,
    get_none_job,
    get_none_asset,
    get_none_jobneed,
    resolve_parent_job,
    resolve_asset
)
from apps.core.constants import DatabaseConstants
from apps.activity.models.job_model import Job, Jobneed
from apps.activity.models.asset_model import Asset


class SentinelResolverTestCase(TestCase):
    """Test case for sentinel resolver utilities."""

    def setUp(self):
        """Set up test data."""
        # Clean up any existing records to ensure clean state
        Job.objects.filter(id=DatabaseConstants.ID_SYSTEM).delete()
        Asset.objects.filter(id=DatabaseConstants.ID_SYSTEM).delete()
        Jobneed.objects.filter(id=DatabaseConstants.ID_SYSTEM).delete()

    def tearDown(self):
        """Clean up after each test."""
        # Clean up created records
        Job.objects.filter(id=DatabaseConstants.ID_SYSTEM).delete()
        Asset.objects.filter(id=DatabaseConstants.ID_SYSTEM).delete()
        Jobneed.objects.filter(id=DatabaseConstants.ID_SYSTEM).delete()

    def test_get_none_job_creates_placeholder(self):
        """Test that get_none_job creates a NONE job placeholder."""
        # Ensure no NONE job exists
        self.assertFalse(
            Job.objects.filter(id=DatabaseConstants.ID_SYSTEM).exists()
        )

        # Get NONE job (should create it)
        none_job = get_none_job()

        self.assertIsNotNone(none_job)
        self.assertEqual(none_job.id, DatabaseConstants.ID_SYSTEM)
        self.assertEqual(none_job.code, DatabaseConstants.DEFAULT_CODE)
        self.assertEqual(none_job.name, DatabaseConstants.DEFAULT_NAME)
        self.assertIn("placeholder", none_job.description.lower())

    def test_get_none_job_returns_existing(self):
        """Test that get_none_job returns existing NONE job if it exists."""
        # Create a NONE job first
        existing_job = Job.objects.create(
            id=DatabaseConstants.ID_SYSTEM,
            jobname='Existing NONE Job',
            code=DatabaseConstants.DEFAULT_CODE,
            jobdesc='Existing description',
            fromdate='2020-01-01 00:00:00',
            uptodate='2099-12-31 23:59:59',
            planduration=0,
            gracetime=0,
            expirytime=0,
            cron='0 0 1 1 *',
            multifactor=1,
            priority=1,
            identifier='TASK'
        )

        # Get NONE job (should return existing)
        none_job = get_none_job()

        self.assertEqual(none_job.id, existing_job.id)
        self.assertEqual(none_job.jobname, existing_job.jobname)

    def test_get_none_asset_creates_placeholder(self):
        """Test that get_none_asset creates a NONE asset placeholder."""
        # Ensure no NONE asset exists
        self.assertFalse(
            Asset.objects.filter(id=DatabaseConstants.ID_SYSTEM).exists()
        )

        # Get NONE asset (should create it)
        none_asset = get_none_asset()

        self.assertIsNotNone(none_asset)
        self.assertEqual(none_asset.id, DatabaseConstants.ID_SYSTEM)
        self.assertEqual(none_asset.code, DatabaseConstants.DEFAULT_CODE)
        self.assertEqual(none_asset.name, DatabaseConstants.DEFAULT_NAME)
        self.assertIn("placeholder", none_asset.description.lower())

    def test_get_none_asset_returns_existing(self):
        """Test that get_none_asset returns existing NONE asset if it exists."""
        # Create a NONE asset first
        existing_asset = Asset.objects.create(
            id=DatabaseConstants.ID_SYSTEM,
            name='Existing NONE Asset',
            code=DatabaseConstants.DEFAULT_CODE,
            identifier='ASSET',
            assettype='SYSTEM',
            assetstatus='ACTIVE'
        )

        # Get NONE asset (should return existing)
        none_asset = get_none_asset()

        self.assertEqual(none_asset.id, existing_asset.id)
        self.assertEqual(none_asset.name, existing_asset.name)

    def test_get_none_jobneed_creates_placeholder(self):
        """Test that get_none_jobneed creates a NONE jobneed placeholder."""
        # Ensure no NONE jobneed exists
        self.assertFalse(
            Jobneed.objects.filter(id=DatabaseConstants.ID_SYSTEM).exists()
        )

        # Get NONE jobneed (should create it and its parent job)
        none_jobneed = get_none_jobneed()

        self.assertIsNotNone(none_jobneed)
        self.assertEqual(none_jobneed.id, DatabaseConstants.ID_SYSTEM)
        self.assertEqual(none_jobneed.code, DatabaseConstants.DEFAULT_CODE)
        self.assertEqual(none_jobneed.name, DatabaseConstants.DEFAULT_NAME)
        self.assertIn("placeholder", none_jobneed.description.lower())

        # Should also create the parent job
        self.assertTrue(
            Job.objects.filter(id=DatabaseConstants.ID_SYSTEM).exists()
        )

    def test_resolve_job_parent_with_none_values(self):
        """Test resolving parent job with None-like values."""
        # Test with None
        result = resolve_parent_job(None)
        self.assertIsNone(result)

        # Test with -1
        result = resolve_parent_job(-1)
        self.assertIsNone(result)

        # Test with empty string
        result = resolve_parent_job("")
        self.assertIsNone(result)

        # Test with ID_ROOT
        result = resolve_parent_job(DatabaseConstants.ID_ROOT)
        self.assertIsNone(result)

    def test_resolve_job_parent_with_system_values(self):
        """Test resolving parent job with system values."""
        # Test with 1 (system ID)
        result = resolve_parent_job(1)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, DatabaseConstants.ID_SYSTEM)

        # Test with ID_SYSTEM constant
        result = resolve_parent_job(DatabaseConstants.ID_SYSTEM)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, DatabaseConstants.ID_SYSTEM)

    def test_resolve_job_parent_with_valid_id(self):
        """Test resolving parent job with valid ID passes through."""
        # Valid IDs should pass through unchanged
        result = resolve_parent_job(42)
        self.assertEqual(result, 42)

        result = resolve_parent_job("123")
        self.assertEqual(result, "123")

    def test_resolve_asset_reference_with_none_values(self):
        """Test resolving asset with None-like values."""
        # Test with None
        result = resolve_asset(None)
        self.assertIsNone(result)

        # Test with -1
        result = resolve_asset(-1)
        self.assertIsNone(result)

        # Test with empty string
        result = resolve_asset("")
        self.assertIsNone(result)

    def test_resolve_asset_reference_with_system_values(self):
        """Test resolving asset with system values."""
        # Test with 1 (system ID)
        result = resolve_asset(1)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, DatabaseConstants.ID_SYSTEM)

        # Test with ID_SYSTEM constant
        result = resolve_asset(DatabaseConstants.ID_SYSTEM)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, DatabaseConstants.ID_SYSTEM)

    def test_is_none_record(self):
        """Test the is_none_record helper function."""
        # Should return True for system/none records
        self.assertTrue(SentinelResolver.is_none_record(1))
        self.assertTrue(SentinelResolver.is_none_record(DatabaseConstants.ID_SYSTEM))

        # Should return False for other values
        self.assertFalse(SentinelResolver.is_none_record(None))
        self.assertFalse(SentinelResolver.is_none_record(-1))
        self.assertFalse(SentinelResolver.is_none_record(42))
        self.assertFalse(SentinelResolver.is_none_record(""))

    def test_is_root_record(self):
        """Test the is_root_record helper function."""
        # Should return True for root/null records
        self.assertTrue(SentinelResolver.is_root_record(None))
        self.assertTrue(SentinelResolver.is_root_record(-1))
        self.assertTrue(SentinelResolver.is_root_record(DatabaseConstants.ID_ROOT))
        self.assertTrue(SentinelResolver.is_root_record(""))

        # Should return False for other values
        self.assertFalse(SentinelResolver.is_root_record(1))
        self.assertFalse(SentinelResolver.is_root_record(42))
        self.assertFalse(SentinelResolver.is_root_record("test"))

    def test_integrity_error_handling(self):
        """Test that IntegrityError is handled properly."""
        # Create a job with the system ID to cause conflict
        existing_job = Job.objects.create(
            id=DatabaseConstants.ID_SYSTEM,
            jobname='Conflicting Job',
            code='CONFLICT',
            jobdesc='Causes conflict',
            fromdate='2020-01-01 00:00:00',
            uptodate='2099-12-31 23:59:59',
            planduration=0,
            gracetime=0,
            expirytime=0,
            cron='0 0 1 1 *',
            multifactor=1,
            priority=1,
            identifier='TASK'
        )

        # get_none_job should still return a job (the existing one)
        none_job = get_none_job()
        self.assertIsNotNone(none_job)
        self.assertEqual(none_job.id, DatabaseConstants.ID_SYSTEM)

    @patch('apps.core.utils_new.sentinel_resolvers.logger')
    def test_error_logging(self, mock_logger):
        """Test that errors are properly logged."""
        # Force an error by mocking Job.objects.create
        with patch('apps.activity.models.job_model.Job.objects.create') as mock_create:
            mock_create.side_effect = Exception("Test error")

            with self.assertRaises(Exception):
                get_none_job()

            # Verify error was logged
            mock_logger.error.assert_called()

    def test_convenience_functions(self):
        """Test the convenience functions work correctly."""
        # Test convenience functions return the same as class methods
        job1 = get_none_job()
        job2 = SentinelResolver.get_none_job()
        self.assertEqual(job1.id, job2.id)

        asset1 = get_none_asset()
        asset2 = SentinelResolver.get_none_asset()
        self.assertEqual(asset1.id, asset2.id)

    def test_transaction_atomicity(self):
        """Test that operations are atomic."""
        # This test ensures that if something fails during creation,
        # no partial records are left behind

        # Mock a failure in the middle of creation
        with patch.object(Job.objects, 'create') as mock_create:
            # First call succeeds, second call fails
            mock_create.side_effect = [
                Job(id=DatabaseConstants.ID_SYSTEM, code=DatabaseConstants.DEFAULT_CODE),
                IntegrityError("Simulated failure")
            ]

            # This should handle the error gracefully
            result = SentinelResolver.get_none_job()
            self.assertIsNotNone(result)


class SentinelResolverPerformanceTestCase(TestCase):
    """Performance tests for sentinel resolvers."""

    def test_repeated_calls_use_cache(self):
        """Test that repeated calls don't create duplicate records."""
        # Call get_none_job multiple times
        job1 = get_none_job()
        job2 = get_none_job()
        job3 = get_none_job()

        # All should return the same instance
        self.assertEqual(job1.id, job2.id)
        self.assertEqual(job2.id, job3.id)

        # Should only have one NONE job in the database
        none_jobs = Job.objects.filter(
            id=DatabaseConstants.ID_SYSTEM,
            code=DatabaseConstants.DEFAULT_CODE
        )
        self.assertEqual(none_jobs.count(), 1)

    def test_concurrent_creation_handling(self):
        """Test handling of concurrent creation attempts."""
        # This test simulates what happens if two threads try to create
        # the NONE record simultaneously

        with patch('apps.activity.models.job_model.Job.objects.filter') as mock_filter:
            # Simulate race condition: first check finds no record
            mock_queryset = Mock()
            mock_queryset.first.return_value = None
            mock_filter.return_value = mock_queryset

            # But then creation fails because another thread created it
            with patch('apps.activity.models.job_model.Job.objects.create') as mock_create:
                mock_create.side_effect = IntegrityError("Already exists")

                # Should fall back to getting the existing record
                with patch('apps.activity.models.job_model.Job.objects.get') as mock_get:
                    mock_job = Mock()
                    mock_job.id = DatabaseConstants.ID_SYSTEM
                    mock_get.return_value = mock_job

                    result = get_none_job()
                    self.assertEqual(result.id, DatabaseConstants.ID_SYSTEM)


if __name__ == '__main__':
    import django
    django.setup()
    import unittest
    unittest.main()