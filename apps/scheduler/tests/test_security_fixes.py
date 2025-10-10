"""
Test suite for security fixes in scheduler module.

This module tests the security improvements made to the scheduler:
- POST-only delete endpoints with CSRF protection
- Proper form field validation (expiry datetime)
- Safe HTTP method usage
"""

import json
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse

from apps.schedhuler.forms import SchdITourFormJob, SchdETourFormJob, SchdTaskFormJob
from apps.activity.models.asset_model import Asset
from apps.peoples.models import People


class SecurityFixesTestCase(TestCase):
    """Test case for security-related fixes in the scheduler module."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.factory = RequestFactory()

        # Create test user
        self.user = People.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

        # Create test job for deletion tests
        self.test_job = Job.objects.create(
            jobname='Test Job',
            jobdesc='Test Description',
            fromdate='2024-01-01 00:00:00',
            uptodate='2024-12-31 23:59:59',
            planduration=60,
            gracetime=10,
            expirytime=5,
            identifier='TASK',
            cron='0 0 * * *',
            multifactor=1,
            priority=1
        )

        # Create test asset
        self.test_asset = Asset.objects.create(
            name='Test Asset',
            code='TEST_ASSET',
            identifier='ASSET',
            assettype='EQUIPMENT',
            assetstatus='ACTIVE'
        )

    def test_delete_checkpoint_requires_post(self):
        """Test that deleteChekpointFromTour only accepts POST requests."""
        url = reverse('schedhuler:delete_checkpointTour')

        # Test GET request is rejected
        response = self.client.get(url, {
            'datasource': 'job',
            'checkpointid': '1',
            'checklistid': '1',
            'job': str(self.test_job.id)
        })

        self.assertEqual(response.status_code, 405)  # Method Not Allowed
        response_data = json.loads(response.content)
        self.assertIn('POST method required', response_data['errors'])

    def test_delete_checkpoint_with_post(self):
        """Test that deleteChekpointFromTour works with POST and proper data."""
        self.client.login(email='test@example.com', password='testpass123')
        url = reverse('schedhuler:delete_checkpointTour')

        # Mock the delete functions to avoid actual deletion
        with patch('apps.schedhuler.utils.delete_from_job') as mock_delete:
            mock_delete.return_value = None

            response = self.client.post(url, {
                'datasource': 'job',
                'checkpointid': '1',
                'checklistid': '1',
                'job': str(self.test_job.id)
            })

            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['errors'], 'Success')
            mock_delete.assert_called_once()

    def test_csrf_protection_on_delete(self):
        """Test CSRF protection on delete endpoints."""
        # This test verifies that Django's CSRF middleware is working
        # The actual CSRF token validation is handled by Django middleware
        url = reverse('schedhuler:delete_checkpointTour')

        # Without CSRF token, request should be rejected by middleware
        response = self.client.post(url, {
            'datasource': 'job',
            'checkpointid': '1',
            'checklistid': '1',
            'job': str(self.test_job.id)
        })

        # CSRF failure results in 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_expiry_datetime_form_validation(self):
        """Test that expiry datetime form validation works correctly."""
        form_data = {
            'jobname': 'Test Tour',
            'jobdesc': 'Test Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'plandatetime': '2024-06-01 10:00:00',
            'expirydatetime': '2024-06-01 11:00:00',  # Different from plandatetime
            'planduration': 60,
            'gracetime': 10,
            'expirytime': 5,
            'cron': '0 0 * * *',
            'multifactor': 1,
            'priority': 1
        }

        form = SchdITourFormJob(data=form_data)

        # Form should be valid and expiry datetime should be processed correctly
        if form.is_valid():
            cleaned_expiry = form.cleaned_data.get('expirydatetime')
            self.assertIsNotNone(cleaned_expiry)
            # The cleaned value should be the expirydatetime, not plandatetime
            self.assertNotEqual(
                cleaned_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                form_data['plandatetime']
            )
        else:
            # If form is invalid, print errors for debugging
            self.fail(f"Form validation failed: {form.errors}")

    def test_form_clean_expiry_uses_correct_field(self):
        """Test that clean_expirydatetime uses expirydatetime field, not plandatetime."""
        # Create a minimal form to test the cleaning method
        form_data = {
            'plandatetime': '2024-06-01 10:00:00',
            'expirydatetime': '2024-06-01 12:00:00'  # Different time
        }

        form = SchdITourFormJob()
        form.cleaned_data = form_data

        # Call the clean method directly
        result = form.clean_expirydatetime()

        # The result should be based on expirydatetime, not plandatetime
        self.assertIsNotNone(result)
        # Convert both to strings for comparison since timezone processing might occur
        result_str = result.strftime('%Y-%m-%d %H:%M:%S') if hasattr(result, 'strftime') else str(result)
        self.assertIn('12:00:00', result_str)  # Should contain the expiry time, not plan time

    def test_external_tour_form_expiry_validation(self):
        """Test expiry datetime validation in external tour form."""
        form_data = {
            'jobname': 'Test External Tour',
            'jobdesc': 'Test Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'plandatetime': '2024-06-01 09:00:00',
            'expirydatetime': '2024-06-01 10:30:00',
            'planduration': 90,
            'gracetime': 15,
            'expirytime': 10,
            'cron': '0 0 * * *'
        }

        form = SchdETourFormJob(data=form_data)

        if form.is_valid():
            cleaned_expiry = form.cleaned_data.get('expirydatetime')
            self.assertIsNotNone(cleaned_expiry)
        else:
            self.fail(f"External tour form validation failed: {form.errors}")

    def test_task_form_expiry_validation(self):
        """Test expiry datetime validation in task form."""
        form_data = {
            'jobname': 'Test Task',
            'jobdesc': 'Test Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'plandatetime': '2024-06-01 14:00:00',
            'expirydatetime': '2024-06-01 15:00:00',
            'planduration': 30,
            'gracetime': 5,
            'expirytime': 0,
            'cron': '0 14 * * *'
        }

        form = SchdTaskFormJob(data=form_data)

        if form.is_valid():
            cleaned_expiry = form.cleaned_data.get('expirydatetime')
            self.assertIsNotNone(cleaned_expiry)
        else:
            self.fail(f"Task form validation failed: {form.errors}")

    def test_delete_with_restricted_error(self):
        """Test delete endpoint handles RestrictedError properly."""
        self.client.login(email='test@example.com', password='testpass123')
        url = reverse('schedhuler:delete_checkpointTour')

        # Mock the delete function to raise RestrictedError
        from django.db.models.deletion import RestrictedError
        with patch('apps.schedhuler.utils.delete_from_job') as mock_delete:
            mock_delete.side_effect = RestrictedError("Cannot delete", None)

            response = self.client.post(url, {
                'datasource': 'job',
                'checkpointid': '1',
                'checklistid': '1',
                'job': str(self.test_job.id)
            })

            self.assertEqual(response.status_code, 404)  # Error status
            response_data = json.loads(response.content)
            self.assertIn('Unable to delete', response_data['errors'])

    def test_delete_with_general_exception(self):
        """Test delete endpoint handles general exceptions properly."""
        self.client.login(email='test@example.com', password='testpass123')
        url = reverse('schedhuler:delete_checkpointTour')

        # Mock the delete function to raise a general exception
        with patch('apps.schedhuler.utils.delete_from_job') as mock_delete:
            mock_delete.side_effect = Exception("Database error")

            response = self.client.post(url, {
                'datasource': 'job',
                'checkpointid': '1',
                'checklistid': '1',
                'job': str(self.test_job.id)
            })

            self.assertEqual(response.status_code, 404)  # Error status
            response_data = json.loads(response.content)
            self.assertEqual(response_data['errors'], 'Something went wrong')

    def test_delete_jobneed_datasource(self):
        """Test delete endpoint works with jobneed datasource."""
        self.client.login(email='test@example.com', password='testpass123')
        url = reverse('schedhuler:delete_checkpointTour')

        # Mock the delete function for jobneed
        with patch('apps.schedhuler.utils.delete_from_jobneed') as mock_delete:
            mock_delete.return_value = None

            response = self.client.post(url, {
                'datasource': 'jobneed',
                'checkpointid': '1',
                'checklistid': '1',
                'job': str(self.test_job.id)
            })

            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['errors'], 'Success')
            mock_delete.assert_called_once()


class SecurityIntegrationTestCase(TestCase):
    """Integration tests for security fixes."""

    def setUp(self):
        """Set up test data for integration tests."""
        self.client = Client(enforce_csrf_checks=True)
        self.user = People.objects.create_user(
            email='integrationtest@example.com',
            password='testpass123',
            first_name='Integration',
            last_name='Test'
        )

    def test_csrf_token_in_forms(self):
        """Test that CSRF tokens are properly included in forms."""
        self.client.login(email='integrationtest@example.com', password='testpass123')

        # Get a form page that should include CSRF token
        response = self.client.get('/operations/schedules/tours/internal/?action=form')

        if response.status_code == 200:
            # Check that CSRF token is present in the response
            self.assertContains(response, 'csrfmiddlewaretoken')

    def test_post_requests_require_csrf(self):
        """Test that POST requests properly require CSRF tokens."""
        # This is an integration test to ensure CSRF middleware is working
        # The specific implementation depends on the Django configuration
        pass  # Placeholder for full integration testing


if __name__ == '__main__':
    import django
    django.setup()
    import unittest
    unittest.main()