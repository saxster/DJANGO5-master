"""
Integration tests for Task and Tour system fixes.

This module tests the complete workflow of the fixes applied:
- End-to-end tour creation with proper sentinel handling
- Task scheduling workflow with constants usage
- Mobile update mutations with corrected journeypath logic
- Complete CRUD operations with security fixes
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, Mock

from apps.activity.models.asset_model import Asset
    SchdTaskFormJob
)
from apps.service.utils import save_journeypath_field
from apps.core.constants import JobConstants, DatabaseConstants
from apps.peoples.models import People


class TaskTourIntegrationTestCase(TestCase):
    """Integration tests for the complete task and tour system."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test user
        self.user = People.objects.create_user(
            email='integration@example.com',
            password='testpass123',
            first_name='Integration',
            last_name='Test'
        )

        # Create test asset
        self.test_asset = Asset.objects.create(
            name='Test Asset',
            code='TEST_ASSET',
            identifier='ASSET',
            assettype='EQUIPMENT',
            assetstatus='ACTIVE'
        )

        # Login user
        self.client.login(email='integration@example.com', password='testpass123')

    def test_internal_tour_creation_workflow(self):
        """Test complete internal tour creation with sentinel resolvers."""
        # Test data for internal tour
        tour_data = {
            'jobname': 'Integration Test Internal Tour',
            'jobdesc': 'Test Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'planduration': 60,
            'gracetime': 10,
            'expirytime': 5,
            'cron': '0 0 * * *',
            'multifactor': 1,
            'priority': 1,
            'asssigned_checkpoints': json.dumps([])  # Empty checkpoints for test
        }

        # Mock the checkpoint processing
        with patch('apps.schedhuler.views.Schd_I_TourFormJob.save_checpoints_for_tour'):
            response = self.client.post(
                reverse('schedhuler:create_tour'),
                data=tour_data
            )

        # Should redirect on success (or return success response)
        self.assertIn(response.status_code, [200, 302])

        # Verify job was created with proper sentinel handling
        created_job = Job.objects.filter(
            jobname='Integration Test Internal Tour'
        ).first()

        self.assertIsNotNone(created_job)
        self.assertEqual(created_job.identifier, JobConstants.Identifier.INTERNALTOUR)

        # Verify proper sentinel resolver usage
        # The parent should be None (not -1) for top-level jobs
        self.assertIsNone(created_job.parent)
        # Asset should be None (not -1) if no specific asset
        self.assertIsNone(created_job.asset)

    def test_external_tour_creation_workflow(self):
        """Test complete external tour creation with NONE placeholders."""
        tour_data = {
            'jobname': 'Integration Test External Tour',
            'jobdesc': 'Test Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'planduration': 90,
            'gracetime': 15,
            'expirytime': 10,
            'cron': '0 0 * * *',
            'multifactor': 1,
            'priority': 2
        }

        response = self.client.post(
            reverse('schedhuler:create_externaltour'),
            data=tour_data
        )

        self.assertIn(response.status_code, [200, 302])

        # Verify job was created with NONE placeholders
        created_job = Job.objects.filter(
            jobname='Integration Test External Tour'
        ).first()

        self.assertIsNotNone(created_job)
        self.assertEqual(created_job.identifier, JobConstants.Identifier.EXTERNALTOUR)

        # Verify NONE placeholders were used correctly
        self.assertIsNotNone(created_job.parent)
        self.assertEqual(created_job.parent.id, DatabaseConstants.ID_SYSTEM)
        self.assertIsNotNone(created_job.asset)
        self.assertEqual(created_job.asset.id, DatabaseConstants.ID_SYSTEM)

    def test_task_creation_workflow(self):
        """Test complete task creation workflow."""
        task_data = {
            'jobname': 'Integration Test Task',
            'jobdesc': 'Test Task Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'planduration': 30,
            'gracetime': 5,
            'expirytime': 0,
            'cron': '0 14 * * *',
            'multifactor': 1,
            'priority': 1
        }

        response = self.client.post(
            reverse('schedhuler:create_task'),
            data=task_data
        )

        self.assertIn(response.status_code, [200, 302])

        # Verify task was created properly
        created_job = Job.objects.filter(
            jobname='Integration Test Task'
        ).first()

        self.assertIsNotNone(created_job)
        self.assertEqual(created_job.identifier, JobConstants.Identifier.TASK)

        # Verify NONE placeholder for parent
        self.assertIsNotNone(created_job.parent)
        self.assertEqual(created_job.parent.id, DatabaseConstants.ID_SYSTEM)

    def test_form_expiry_datetime_validation_integration(self):
        """Test that expiry datetime validation works in real forms."""
        from apps.schedhuler.forms import SchdITourFormJob

        # Test with different plan and expiry times
        form_data = {
            'jobname': 'Test Tour with Expiry',
            'jobdesc': 'Test Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'plandatetime': '2024-06-01 10:00:00',
            'expirydatetime': '2024-06-01 12:00:00',  # 2 hours after plan
            'planduration': 120,  # 2 hours
            'gracetime': 15,
            'expirytime': 0,
            'cron': '0 10 * * *',
            'multifactor': 1,
            'priority': 1
        }

        form = SchdITourFormJob(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        # Verify expiry datetime was processed correctly
        cleaned_expiry = form.cleaned_data['expirydatetime']
        self.assertIsNotNone(cleaned_expiry)

        # The cleaned expiry should match the input expiry, not the plan time
        expiry_time = cleaned_expiry.strftime('%H:%M:%S')
        self.assertEqual(expiry_time, '12:00:00')

    def test_delete_checkpoint_security_integration(self):
        """Test complete delete checkpoint workflow with security."""
        # Create a job and jobneed for testing
        test_job = Job.objects.create(
            jobname='Delete Test Job',
            jobdesc='For deletion testing',
            fromdate='2024-01-01 00:00:00',
            uptodate='2024-12-31 23:59:59',
            planduration=60,
            gracetime=10,
            expirytime=5,
            identifier=JobConstants.Identifier.INTERNALTOUR,
            cron='0 0 * * *',
            multifactor=1,
            priority=1
        )

        # Test that GET request is rejected
        url = reverse('schedhuler:delete_checkpointTour')
        get_response = self.client.get(url, {
            'datasource': 'job',
            'checkpointid': '1',
            'checklistid': '1',
            'job': str(test_job.id)
        })

        self.assertEqual(get_response.status_code, 405)  # Method Not Allowed

        # Test successful POST request
        with patch('apps.schedhuler.utils.delete_from_job') as mock_delete:
            mock_delete.return_value = None

            post_response = self.client.post(url, {
                'datasource': 'job',
                'checkpointid': '1',
                'checklistid': '1',
                'job': str(test_job.id)
            })

            self.assertEqual(post_response.status_code, 200)
            response_data = json.loads(post_response.content)
            self.assertEqual(response_data['errors'], 'Success')
            mock_delete.assert_called_once()

    def test_journeypath_logic_integration(self):
        """Test the corrected journeypath logic with sentinel resolvers."""
        # Create a jobneed that should trigger journeypath saving
        none_job = get_none_job()

        test_jobneed = Jobneed.objects.create(
            jobneedname='Test Tour Jobneed',
            code='TEST_JOBNEED',
            job=none_job,
            parent_id=DatabaseConstants.ID_SYSTEM,  # NONE parent (top-level)
            plandatetime='2024-06-01 10:00:00',
            expirydatetime='2024-06-01 11:00:00',
            identifier=JobConstants.Identifier.EXTERNALTOUR,
            jobstatus='COMPLETED'
        )

        # Create jobneed data for the function
        jobneed_data = {
            'uuid': str(test_jobneed.uuid),
            'parent_id': DatabaseConstants.ID_SYSTEM,
            'jobstatus': 'COMPLETED',
            'identifier': JobConstants.Identifier.EXTERNALTOUR
        }

        # Mock the tracking data
        with patch('apps.attendance.models.Tracking.objects.filter') as mock_tracking:
            mock_tracking_instance = Mock()
            mock_tracking_instance.values.return_value = [
                {'lat': 40.7128, 'lng': -74.0060},
                {'lat': 40.7589, 'lng': -73.9851}
            ]
            mock_tracking.return_value = mock_tracking_instance

            # Mock the Jobneed.objects.get call
            with patch('apps.activity.models.job_model.Jobneed.objects.get') as mock_get:
                mock_get.return_value = test_jobneed

                # Test the journeypath saving logic
                with patch('django.contrib.gis.geos.LineString') as mock_linestring:
                    mock_linestring.return_value = Mock()

                    try:
                        save_journeypath_field(jobneed_data)
                        # If we get here without exception, the logic worked
                        journey_path_saved = True
                    except Exception as e:
                        journey_path_saved = False
                        print(f"Journeypath saving failed: {e}")

                    # The function should handle the NONE parent correctly
                    self.assertTrue(journey_path_saved)

    def test_constants_usage_integration(self):
        """Test that constants are used consistently throughout the system."""
        # Create jobs with different identifiers using constants
        test_jobs = []

        identifiers = [
            JobConstants.Identifier.TASK,
            JobConstants.Identifier.INTERNALTOUR,
            JobConstants.Identifier.EXTERNALTOUR
        ]

        for identifier in identifiers:
            job = Job.objects.create(
                jobname=f'Test {identifier} Job',
                jobdesc=f'Test {identifier} Description',
                fromdate='2024-01-01 00:00:00',
                uptodate='2024-12-31 23:59:59',
                planduration=60,
                gracetime=10,
                expirytime=5,
                identifier=identifier,
                cron='0 0 * * *',
                multifactor=1,
                priority=1
            )
            test_jobs.append(job)

        # Test that queries work with constants
        tasks = Job.objects.filter(identifier=JobConstants.Identifier.TASK)
        internal_tours = Job.objects.filter(identifier=JobConstants.Identifier.INTERNALTOUR)
        external_tours = Job.objects.filter(identifier=JobConstants.Identifier.EXTERNALTOUR)

        self.assertEqual(tasks.count(), 1)
        self.assertEqual(internal_tours.count(), 1)
        self.assertEqual(external_tours.count(), 1)

        # Verify the identifiers match
        self.assertEqual(tasks.first().identifier, JobConstants.Identifier.TASK)
        self.assertEqual(internal_tours.first().identifier, JobConstants.Identifier.INTERNALTOUR)
        self.assertEqual(external_tours.first().identifier, JobConstants.Identifier.EXTERNALTOUR)

    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow from creation to completion."""
        # Step 1: Create an internal tour
        tour_data = {
            'jobname': 'E2E Test Tour',
            'jobdesc': 'End-to-end test',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'planduration': 60,
            'gracetime': 10,
            'expirytime': 5,
            'cron': '0 0 * * *',
            'multifactor': 1,
            'priority': 1,
            'asssigned_checkpoints': json.dumps([])
        }

        with patch('apps.schedhuler.views.Schd_I_TourFormJob.save_checpoints_for_tour'):
            create_response = self.client.post(
                reverse('schedhuler:create_tour'),
                data=tour_data
            )

        self.assertIn(create_response.status_code, [200, 302])

        # Step 2: Verify job was created properly
        created_job = Job.objects.filter(jobname='E2E Test Tour').first()
        self.assertIsNotNone(created_job)

        # Step 3: Create a jobneed for the job
        jobneed = Jobneed.objects.create(
            jobneedname='E2E Test Jobneed',
            code='E2E_TEST',
            job=created_job,
            plandatetime='2024-06-01 10:00:00',
            expirydatetime='2024-06-01 11:00:00',
            identifier=JobConstants.Identifier.INTERNALTOUR,
            jobstatus='PENDING'
        )

        # Step 4: Update jobneed status (simulate mobile update)
        jobneed.jobstatus = 'COMPLETED'
        jobneed.save()

        # Step 5: Test journeypath logic would trigger
        jobneed_data = {
            'uuid': str(jobneed.uuid),
            'parent_id': jobneed.parent_id if jobneed.parent_id else None,
            'jobstatus': 'COMPLETED',
            'identifier': JobConstants.Identifier.INTERNALTOUR
        }

        # Mock the journeypath saving (since we don't have actual tracking data)
        with patch('apps.attendance.models.Tracking.objects.filter'):
            with patch('apps.activity.models.job_model.Jobneed.objects.get') as mock_get:
                mock_get.return_value = jobneed
                try:
                    save_journeypath_field(jobneed_data)
                    workflow_completed = True
                except Exception:
                    workflow_completed = False

        # Step 6: Clean up - test deletion security
        with patch('apps.schedhuler.utils.delete_from_job'):
            delete_response = self.client.post(
                reverse('schedhuler:delete_checkpointTour'),
                {
                    'datasource': 'job',
                    'checkpointid': '1',
                    'checklistid': '1',
                    'job': str(created_job.id)
                }
            )

        self.assertEqual(delete_response.status_code, 200)

        # Verify the complete workflow
        self.assertTrue(workflow_completed)

    def test_error_handling_integration(self):
        """Test error handling throughout the integrated system."""
        # Test form validation errors
        invalid_tour_data = {
            'jobname': '',  # Invalid: empty name
            'jobdesc': 'Test Description',
            'fromdate': '2024-01-01 00:00:00',
            'uptodate': '2024-12-31 23:59:59',
            'planduration': -1,  # Invalid: negative duration
            'gracetime': 10,
            'expirytime': 5,
            'cron': 'invalid_cron',  # Invalid: bad cron expression
            'multifactor': 1,
            'priority': 1
        }

        response = self.client.post(
            reverse('schedhuler:create_tour'),
            data=invalid_tour_data
        )

        # Should handle validation errors gracefully
        # Response might be 200 with errors or 400, depending on implementation
        self.assertIn(response.status_code, [200, 400])

        # Test database constraint violations
        with self.assertRaises(Exception):
            # Try to create job with invalid identifier
            Job.objects.create(
                jobname='Invalid Job',
                jobdesc='Test',
                fromdate='2024-01-01 00:00:00',
                uptodate='2024-12-31 23:59:59',
                planduration=60,
                gracetime=10,
                expirytime=5,
                identifier='INVALID_IDENTIFIER',  # Not in choices
                cron='0 0 * * *',
                multifactor=1,
                priority=1
            )


if __name__ == '__main__':
    import django
    django.setup()
    import unittest
    unittest.main()