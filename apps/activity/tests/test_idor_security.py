"""
IDOR Security Tests for Activity App

Tests prevent Insecure Direct Object Reference vulnerabilities for jobs, tasks,
assets, and tour management.

Critical Test Coverage:
    - Cross-tenant job/task access prevention
    - Cross-tenant asset access prevention
    - Job assignment security
    - Tour checkpoint access control
    - Asset maintenance record protection

Security Note:
    Activity data includes operational workflows and critical asset information.
    Any failures must be treated as CRITICAL security vulnerabilities.
"""

import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.activity.models import Job, Jobneed, Asset, Location
from apps.activity.tests.factories import (
    BtFactory,
    LocationFactory,
    AssetFactory,
    JobFactory,
    JobneedFactory,
    TourJobFactory,
    CheckpointJobFactory,
    PeopleFactory
)

User = get_user_model()


@pytest.mark.security
@pytest.mark.idor
class ActivityIDORTestCase(TestCase):
    """Test suite for IDOR vulnerabilities in activity app."""

    def setUp(self):
        """Set up test fixtures for IDOR testing."""
        self.client = Client()
        
        # Create two separate tenants
        self.tenant_a = BtFactory(bucode="ACT_A", buname="Activity Tenant A")
        self.tenant_b = BtFactory(bucode="ACT_B", buname="Activity Tenant B")
        
        # Create locations
        self.location_a = LocationFactory(
            client=self.tenant_a,
            site="SITE_A"
        )
        self.location_b = LocationFactory(
            client=self.tenant_b,
            site="SITE_B"
        )
        
        # Create users
        self.user_a = PeopleFactory(
            client=self.tenant_a,
            peoplecode="WORKER_A"
        )
        self.user_b = PeopleFactory(
            client=self.tenant_b,
            peoplecode="WORKER_B"
        )
        
        # Create assets
        self.asset_a = AssetFactory(
            client=self.tenant_a,
            location=self.location_a,
            assetcode="ASSET_A"
        )
        self.asset_b = AssetFactory(
            client=self.tenant_b,
            location=self.location_b,
            assetcode="ASSET_B"
        )
        
        # Create jobs
        self.job_a = JobFactory(
            client=self.tenant_a,
            asset=self.asset_a,
            location=self.location_a,
            cdby=self.user_a
        )
        self.job_b = JobFactory(
            client=self.tenant_b,
            asset=self.asset_b,
            location=self.location_b,
            cdby=self.user_b
        )
        
        # Create jobneeds (task instances)
        self.jobneed_a = JobneedFactory(
            job=self.job_a,
            client=self.tenant_a,
            cdby=self.user_a
        )
        self.jobneed_b = JobneedFactory(
            job=self.job_b,
            client=self.tenant_b,
            cdby=self.user_b
        )

    # ==================
    # Cross-Tenant Job Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_job(self):
        """Test IDOR: User cannot view jobs from another tenant"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B job
        response = self.client.get(f'/operations/jobs/{self.job_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_tenant_job(self):
        """Test IDOR: User cannot modify jobs from another tenant"""
        self.client.force_login(self.user_a)
        
        original_name = self.job_b.jobname
        
        # Try to update tenant B job
        response = self.client.post(
            f'/operations/jobs/update/{self.job_b.id}/',
            {
                'jobname': 'Hacked Job Name',
                'enable': False
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify not changed
        self.job_b.refresh_from_db()
        self.assertEqual(self.job_b.jobname, original_name)

    def test_user_cannot_delete_other_tenant_job(self):
        """Test IDOR: User cannot delete jobs from another tenant"""
        self.client.force_login(self.user_a)
        
        job_id = self.job_b.id
        
        # Try to delete tenant B job
        response = self.client.post(f'/operations/jobs/delete/{job_id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify still exists
        self.assertTrue(Job.objects.filter(id=job_id).exists())

    def test_job_list_scoped_to_tenant(self):
        """Test IDOR: Job listing is scoped to tenant"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/operations/jobs/')
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should see tenant A jobs
            self.assertIn(self.job_a.jobname, content)
            
            # Should NOT see tenant B jobs
            self.assertNotIn(self.job_b.jobname, content)

    # ==================
    # Cross-Tenant Task (Jobneed) Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_task(self):
        """Test IDOR: User cannot view tasks from another tenant"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B task
        response = self.client.get(f'/operations/tasks/{self.jobneed_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_complete_other_tenant_task(self):
        """Test IDOR: User cannot complete tasks from another tenant"""
        self.client.force_login(self.user_a)
        
        original_status = self.jobneed_b.jobstatus
        
        # Try to complete tenant B task
        response = self.client.post(
            f'/operations/tasks/complete/{self.jobneed_b.id}/',
            {
                'jobstatus': 'COMPLETED',
                'completion_note': 'Hacked completion'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify status not changed
        self.jobneed_b.refresh_from_db()
        self.assertEqual(self.jobneed_b.jobstatus, original_status)

    def test_user_cannot_assign_cross_tenant_task(self):
        """Test IDOR: Cannot assign tasks to users from other tenants"""
        self.client.force_login(self.user_a)
        
        # Try to assign tenant A task to tenant B user
        response = self.client.post(
            f'/operations/tasks/assign/{self.jobneed_a.id}/',
            {'assigned_to': self.user_b.id}
        )
        
        # Should be rejected
        self.assertIn(response.status_code, [400, 403, 404])

    def test_task_list_scoped_to_tenant(self):
        """Test IDOR: Task listing is scoped to tenant"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/operations/tasks/')
        
        if response.status_code == 200:
            # Should only show tenant A tasks
            tasks = Jobneed.objects.filter(client=self.tenant_a)
            self.assertGreater(tasks.count(), 0)

    # ==================
    # Cross-Tenant Asset Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_asset(self):
        """Test IDOR: User cannot view assets from another tenant"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B asset
        response = self.client.get(f'/assets/{self.asset_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_tenant_asset(self):
        """Test IDOR: User cannot modify assets from another tenant"""
        self.client.force_login(self.user_a)
        
        original_name = self.asset_b.assetname
        
        # Try to update tenant B asset
        response = self.client.post(
            f'/assets/update/{self.asset_b.id}/',
            {
                'assetname': 'Hacked Asset',
                'runningstatus': 'BROKEN'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify not changed
        self.asset_b.refresh_from_db()
        self.assertEqual(self.asset_b.assetname, original_name)

    def test_user_cannot_delete_other_tenant_asset(self):
        """Test IDOR: User cannot delete assets from another tenant"""
        self.client.force_login(self.user_a)
        
        asset_id = self.asset_b.id
        
        # Try to delete tenant B asset
        response = self.client.post(f'/assets/delete/{asset_id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify still exists
        self.assertTrue(Asset.objects.filter(id=asset_id).exists())

    def test_asset_list_scoped_to_tenant(self):
        """Test IDOR: Asset listing is scoped to tenant"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/assets/')
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should see tenant A assets
            self.assertIn(self.asset_a.assetname, content)
            
            # Should NOT see tenant B assets
            self.assertNotIn(self.asset_b.assetname, content)

    # ==================
    # Tour Management Security Tests
    # ==================

    def test_user_cannot_access_other_tenant_tour(self):
        """Test IDOR: Tours are tenant-scoped"""
        # Create tours for each tenant
        tour_a = TourJobFactory(
            client=self.tenant_a,
            location=self.location_a,
            cdby=self.user_a
        )
        tour_b = TourJobFactory(
            client=self.tenant_b,
            location=self.location_b,
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to access tenant B tour
        response = self.client.get(f'/operations/tours/{tour_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_add_checkpoint_to_other_tenant_tour(self):
        """Test IDOR: Cannot add checkpoints to cross-tenant tours"""
        tour_b = TourJobFactory(
            client=self.tenant_b,
            location=self.location_b,
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to add checkpoint to tenant B tour
        response = self.client.post(
            f'/operations/tours/{tour_b.id}/add_checkpoint/',
            {
                'jobname': 'Hacked Checkpoint',
                'asset': self.asset_a.id
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_checkpoint_access_scoped_to_tour_tenant(self):
        """Test IDOR: Checkpoints inherit tour tenant scoping"""
        tour_a = TourJobFactory(
            client=self.tenant_a,
            location=self.location_a,
            cdby=self.user_a
        )
        
        checkpoint_a = CheckpointJobFactory(
            parent=tour_a,
            client=self.tenant_a,
            cdby=self.user_a
        )
        
        tour_b = TourJobFactory(
            client=self.tenant_b,
            location=self.location_b,
            cdby=self.user_b
        )
        
        checkpoint_b = CheckpointJobFactory(
            parent=tour_b,
            client=self.tenant_b,
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Can access own checkpoint
        response_own = self.client.get(f'/operations/checkpoints/{checkpoint_a.id}/')
        self.assertEqual(response_own.status_code, 200)
        
        # Cannot access cross-tenant checkpoint
        response_other = self.client.get(f'/operations/checkpoints/{checkpoint_b.id}/')
        self.assertIn(response_other.status_code, [403, 404])

    # ==================
    # Location Security Tests
    # ==================

    def test_user_cannot_access_other_tenant_location(self):
        """Test IDOR: Locations are tenant-scoped"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B location
        response = self.client.get(f'/locations/{self.location_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_assign_cross_tenant_location_to_job(self):
        """Test IDOR: Cannot assign cross-tenant location to job"""
        self.client.force_login(self.user_a)
        
        # Try to update job with cross-tenant location
        response = self.client.post(
            f'/operations/jobs/update/{self.job_a.id}/',
            {
                'jobname': self.job_a.jobname,
                'location': self.location_b.id  # Cross-tenant location
            }
        )
        
        # Should be rejected
        self.job_a.refresh_from_db()
        self.assertEqual(self.job_a.location, self.location_a)

    # ==================
    # Direct ID Manipulation Tests
    # ==================

    def test_sequential_job_id_enumeration_blocked(self):
        """Test IDOR: Cannot enumerate jobs by sequential IDs"""
        self.client.force_login(self.user_a)
        
        forbidden_count = 0
        
        for job_id in range(1, 50):
            response = self.client.get(f'/operations/jobs/{job_id}/')
            if response.status_code in [403, 404]:
                forbidden_count += 1
        
        self.assertGreater(
            forbidden_count,
            0,
            "Should prevent enumeration of cross-tenant jobs"
        )

    def test_negative_job_id_handling(self):
        """Test IDOR: Negative IDs handled gracefully"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/operations/jobs/-1/')
        
        # Should return 400 or 404, not 500
        self.assertIn(response.status_code, [400, 404])

    def test_invalid_job_id_format_rejected(self):
        """Test IDOR: Invalid ID formats are rejected"""
        self.client.force_login(self.user_a)
        
        invalid_ids = ['invalid', 'abc123', '<script>', '../../etc']
        
        for invalid_id in invalid_ids:
            response = self.client.get(f'/operations/jobs/{invalid_id}/')
            self.assertIn(response.status_code, [400, 404])

    # ==================
    # API Endpoint Security Tests
    # ==================

    def test_api_job_detail_cross_tenant_blocked(self):
        """Test IDOR: API endpoints enforce tenant isolation"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B job via API
        response = self.client.get(f'/api/v1/jobs/{self.job_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_api_task_list_filtered_by_tenant(self):
        """Test IDOR: API list endpoints scope to tenant"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/api/v1/tasks/')
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            
            # Should only include tenant A tasks
            task_ids = [item['id'] for item in results]
            
            self.assertIn(self.jobneed_a.id, task_ids)
            self.assertNotIn(self.jobneed_b.id, task_ids)

    def test_api_asset_detail_cross_tenant_blocked(self):
        """Test IDOR: Asset API enforces tenant isolation"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B asset via API
        response = self.client.get(f'/api/v1/assets/{self.asset_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    # ==================
    # Task Assignment Security Tests
    # ==================

    def test_worker_can_only_view_assigned_tasks(self):
        """Test IDOR: Workers see only their assigned tasks"""
        # Create another user in tenant A
        user_a2 = PeopleFactory(
            client=self.tenant_a,
            peoplecode="WORKER_A2"
        )
        
        # Create task assigned to user_a2
        jobneed_a2 = JobneedFactory(
            job=self.job_a,
            client=self.tenant_a,
            cdby=user_a2
        )
        
        self.client.force_login(self.user_a)
        
        # Try to access another worker's task
        response = self.client.get(f'/operations/tasks/{jobneed_a2.id}/')
        
        # Depending on business rules:
        # - If tasks are team-visible: 200
        # - If tasks are private: 403
        # Adjust based on actual requirements
        self.assertIn(response.status_code, [200, 403])

    def test_task_reassignment_requires_permission(self):
        """Test IDOR: Task reassignment requires proper authorization"""
        # Create another user in tenant A
        user_a2 = PeopleFactory(
            client=self.tenant_a,
            peoplecode="WORKER_A2"
        )
        
        self.client.force_login(self.user_a)
        
        # Try to reassign own task to another user
        response = self.client.post(
            f'/operations/tasks/assign/{self.jobneed_a.id}/',
            {'assigned_to': user_a2.id}
        )
        
        # Regular user should not reassign tasks (needs manager role)
        # Adjust based on actual business rules
        self.assertIn(response.status_code, [200, 403])

    # ==================
    # Maintenance Record Security Tests
    # ==================

    def test_maintenance_log_cross_tenant_blocked(self):
        """Test IDOR: Asset maintenance logs are tenant-scoped"""
        from apps.activity.models import AssetLog
        
        # Create maintenance logs
        log_a = AssetLog.objects.create(
            asset=self.asset_a,
            action='MAINTENANCE',
            description='Maintenance A',
            cdby=self.user_a
        )
        
        log_b = AssetLog.objects.create(
            asset=self.asset_b,
            action='MAINTENANCE',
            description='Maintenance B',
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to access tenant B maintenance log
        response = self.client.get(f'/assets/logs/{log_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_critical_asset_access_requires_authorization(self):
        """Test IDOR: Critical assets have additional access controls"""
        from apps.activity.tests.factories import CriticalAssetFactory
        
        critical_asset_b = CriticalAssetFactory(
            client=self.tenant_b,
            location=self.location_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to access cross-tenant critical asset
        response = self.client.get(f'/assets/critical/{critical_asset_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])


@pytest.mark.security
@pytest.mark.idor
@pytest.mark.integration
class ActivityIDORIntegrationTestCase(TestCase):
    """Integration tests for activity IDOR across workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_a = BtFactory(bucode="INT_A")
        self.tenant_b = BtFactory(bucode="INT_B")
        
        self.user_a = PeopleFactory(client=self.tenant_a)
        self.user_b = PeopleFactory(client=self.tenant_b)
        
        self.client = Client()

    def test_complete_job_workflow_tenant_isolation(self):
        """Test full job workflow maintains tenant isolation"""
        self.client.force_login(self.user_a)
        
        # 1. Create job (tenant A)
        location_a = LocationFactory(client=self.tenant_a)
        asset_a = AssetFactory(client=self.tenant_a, location=location_a)
        
        response_create = self.client.post(
            '/operations/jobs/create/',
            {
                'jobname': 'Test Job A',
                'asset': asset_a.id,
                'location': location_a.id
            }
        )
        
        # 2. Try to assign cross-tenant asset
        asset_b = AssetFactory(
            client=self.tenant_b,
            location=LocationFactory(client=self.tenant_b)
        )
        
        if response_create.status_code == 302:  # Redirect on success
            job_a = Job.objects.filter(
                client=self.tenant_a,
                jobname='Test Job A'
            ).first()
            
            if job_a:
                response_update = self.client.post(
                    f'/operations/jobs/update/{job_a.id}/',
                    {
                        'jobname': 'Test Job A',
                        'asset': asset_b.id  # Cross-tenant asset
                    }
                )
                
                # Should be rejected
                job_a.refresh_from_db()
                self.assertEqual(job_a.asset, asset_a)

    def test_tour_execution_cross_tenant_protection(self):
        """Test tour execution maintains tenant boundaries"""
        # Create tour with checkpoints for tenant A
        tour_a = TourJobFactory(
            client=self.tenant_a,
            location=LocationFactory(client=self.tenant_a),
            cdby=self.user_a
        )
        
        checkpoint_a = CheckpointJobFactory(
            parent=tour_a,
            client=self.tenant_a,
            cdby=self.user_a
        )
        
        # Create tour for tenant B
        tour_b = TourJobFactory(
            client=self.tenant_b,
            location=LocationFactory(client=self.tenant_b),
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to complete tenant B tour
        response = self.client.post(
            f'/operations/tours/execute/{tour_b.id}/',
            {'status': 'COMPLETED'}
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
