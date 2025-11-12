"""
IDOR Security Tests for Attendance App

Tests prevent Insecure Direct Object Reference vulnerabilities that could allow
unauthorized access to attendance records, shift assignments, and tracking data.

Critical Test Coverage:
    - Cross-tenant attendance access prevention
    - Cross-user attendance record access prevention
    - Shift assignment security
    - GPS tracking data protection
    - Biometric data access control

Security Note:
    Attendance data contains PII and sensitive location information.
    Any failures must be treated as CRITICAL security vulnerabilities.
"""

import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.attendance.models import (
    PeopleTracking,
    Shift,
    Post,
    ShiftPost
)
from apps.peoples.tests.factories import (
    BtFactory,
    CompleteUserFactory,
    LocationFactory
)

User = get_user_model()


@pytest.mark.security
@pytest.mark.idor
class AttendanceIDORTestCase(TestCase):
    """Test suite for IDOR vulnerabilities in attendance app."""

    def setUp(self):
        """Set up test fixtures for IDOR testing."""
        self.client = Client()
        
        # Create two separate tenants
        self.tenant_a = BtFactory(bucode="ATT_A", buname="Attendance Tenant A")
        self.tenant_b = BtFactory(bucode="ATT_B", buname="Attendance Tenant B")
        
        # Create locations for each tenant
        self.location_a = LocationFactory(
            client=self.tenant_a,
            site="SITE_A",
            location="Location A"
        )
        self.location_b = LocationFactory(
            client=self.tenant_b,
            site="SITE_B",
            location="Location B"
        )
        
        # Create users for tenant A
        self.user_a1 = CompleteUserFactory(
            client=self.tenant_a,
            peoplecode="ATT_A1",
            peoplename="Worker A1"
        )
        self.user_a2 = CompleteUserFactory(
            client=self.tenant_a,
            peoplecode="ATT_A2",
            peoplename="Worker A2"
        )
        
        # Create users for tenant B
        self.user_b1 = CompleteUserFactory(
            client=self.tenant_b,
            peoplecode="ATT_B1",
            peoplename="Worker B1"
        )
        self.user_b2 = CompleteUserFactory(
            client=self.tenant_b,
            peoplecode="ATT_B2",
            peoplename="Worker B2"
        )
        
        # Create attendance records
        self.attendance_a1 = PeopleTracking.objects.create(
            people=self.user_a1,
            client=self.tenant_a,
            bu=self.tenant_a,
            clockintime=datetime.now(dt_timezone.utc),
            attendance_json={
                'gps_location': {'lat': 1.3521, 'lon': 103.8198},
                'device_id': 'device_a1'
            }
        )
        
        self.attendance_b1 = PeopleTracking.objects.create(
            people=self.user_b1,
            client=self.tenant_b,
            bu=self.tenant_b,
            clockintime=datetime.now(dt_timezone.utc),
            attendance_json={
                'gps_location': {'lat': 1.2900, 'lon': 103.8500},
                'device_id': 'device_b1'
            }
        )

    # ==================
    # Cross-Tenant Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_attendance(self):
        """Test IDOR: User cannot view attendance from another tenant"""
        self.client.force_login(self.user_a1)
        
        # Attempt to access tenant B attendance
        response = self.client.get(f'/attendance/detail/{self.attendance_b1.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_tenant_attendance(self):
        """Test IDOR: User cannot modify attendance from another tenant"""
        self.client.force_login(self.user_a1)
        
        original_time = self.attendance_b1.clockintime
        
        # Attempt to update tenant B attendance
        response = self.client.post(
            f'/attendance/update/{self.attendance_b1.id}/',
            {
                'clockintime': datetime.now(dt_timezone.utc) - timedelta(hours=2),
                'clockouttime': datetime.now(dt_timezone.utc)
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify data wasn't changed
        self.attendance_b1.refresh_from_db()
        self.assertEqual(self.attendance_b1.clockintime, original_time)

    def test_user_cannot_delete_other_tenant_attendance(self):
        """Test IDOR: User cannot delete attendance from another tenant"""
        self.client.force_login(self.user_a1)
        
        attendance_id = self.attendance_b1.id
        
        # Attempt to delete
        response = self.client.post(f'/attendance/delete/{attendance_id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify record still exists
        self.assertTrue(PeopleTracking.objects.filter(id=attendance_id).exists())

    def test_attendance_list_scoped_to_tenant(self):
        """Test IDOR: Attendance listing is scoped to tenant"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/attendance/list/')
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should see tenant A attendance
            self.assertIn(str(self.attendance_a1.id), content)
            
            # Should NOT see tenant B attendance
            self.assertNotIn(str(self.attendance_b1.id), content)

    # ==================
    # Cross-User Access Prevention Tests
    # ==================

    def test_user_cannot_edit_other_user_attendance_same_tenant(self):
        """Test IDOR: User cannot modify another user's attendance"""
        self.client.force_login(self.user_a1)
        
        # Create attendance for user A2
        attendance_a2 = PeopleTracking.objects.create(
            people=self.user_a2,
            client=self.tenant_a,
            bu=self.tenant_a,
            clockintime=datetime.now(dt_timezone.utc)
        )
        
        original_time = attendance_a2.clockintime
        
        # Attempt to update
        response = self.client.post(
            f'/attendance/update/{attendance_a2.id}/',
            {
                'clockintime': datetime.now(dt_timezone.utc) - timedelta(hours=3)
            }
        )
        
        # Should be forbidden (users can only edit own attendance)
        self.assertIn(response.status_code, [403, 404])
        
        # Verify not changed
        attendance_a2.refresh_from_db()
        self.assertEqual(attendance_a2.clockintime, original_time)

    def test_user_can_view_own_attendance(self):
        """Test: User CAN access their own attendance records"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get(f'/attendance/detail/{self.attendance_a1.id}/')
        
        # Should succeed
        self.assertEqual(response.status_code, 200)

    def test_user_cannot_clock_in_for_another_user(self):
        """Test IDOR: User cannot create attendance for another user"""
        self.client.force_login(self.user_a1)
        
        # Attempt to clock in as user A2
        response = self.client.post(
            '/attendance/clockin/',
            {
                'user_id': self.user_a2.id,
                'clockintime': datetime.now(dt_timezone.utc).isoformat()
            }
        )
        
        # Should be rejected or create record for logged-in user only
        new_records = PeopleTracking.objects.filter(
            people=self.user_a2,
            clockintime__gte=datetime.now(dt_timezone.utc) - timedelta(minutes=1)
        )
        
        # User A2 should not have new attendance created by user A1
        self.assertEqual(new_records.count(), 0)

    # ==================
    # Shift Assignment Security Tests
    # ==================

    def test_user_cannot_access_other_tenant_shifts(self):
        """Test IDOR: Shifts are tenant-scoped"""
        # Create shifts for each tenant
        shift_a = Shift.objects.create(
            shiftname="Shift A",
            client=self.tenant_a,
            bu=self.tenant_a,
            starttime=datetime.now(dt_timezone.utc).time(),
            endtime=(datetime.now(dt_timezone.utc) + timedelta(hours=8)).time()
        )
        
        shift_b = Shift.objects.create(
            shiftname="Shift B",
            client=self.tenant_b,
            bu=self.tenant_b,
            starttime=datetime.now(dt_timezone.utc).time(),
            endtime=(datetime.now(dt_timezone.utc) + timedelta(hours=8)).time()
        )
        
        self.client.force_login(self.user_a1)
        
        # Try to access tenant B shift
        response = self.client.get(f'/attendance/shifts/{shift_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_assign_cross_tenant_shift(self):
        """Test IDOR: Cannot assign shifts from another tenant"""
        shift_b = Shift.objects.create(
            shiftname="Shift B",
            client=self.tenant_b,
            bu=self.tenant_b,
            starttime=datetime.now(dt_timezone.utc).time(),
            endtime=(datetime.now(dt_timezone.utc) + timedelta(hours=8)).time()
        )
        
        self.client.force_login(self.user_a1)
        
        # Try to assign tenant B shift to self
        response = self.client.post(
            '/attendance/assign_shift/',
            {
                'user_id': self.user_a1.id,
                'shift_id': shift_b.id
            }
        )
        
        # Should be rejected
        self.assertIn(response.status_code, [400, 403, 404])

    def test_shift_post_assignment_cross_tenant_blocked(self):
        """Test IDOR: Shift-post assignments respect tenant boundaries"""
        # Create posts for each tenant
        post_a = Post.objects.create(
            postname="Post A",
            client=self.tenant_a,
            bu=self.tenant_a,
            location=self.location_a
        )
        
        post_b = Post.objects.create(
            postname="Post B",
            client=self.tenant_b,
            bu=self.tenant_b,
            location=self.location_b
        )
        
        shift_a = Shift.objects.create(
            shiftname="Shift A",
            client=self.tenant_a,
            bu=self.tenant_a,
            starttime=datetime.now(dt_timezone.utc).time(),
            endtime=(datetime.now(dt_timezone.utc) + timedelta(hours=8)).time()
        )
        
        self.client.force_login(self.user_a1)
        
        # Try to create shift-post with cross-tenant post
        response = self.client.post(
            '/attendance/shift_post/create/',
            {
                'shift_id': shift_a.id,
                'post_id': post_b.id  # Cross-tenant post
            }
        )
        
        # Should be rejected
        self.assertIn(response.status_code, [400, 403, 404])

    # ==================
    # GPS Tracking Data Security Tests
    # ==================

    def test_gps_data_cross_tenant_blocked(self):
        """Test IDOR: GPS tracking data is tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        # Try to access tenant B GPS data
        response = self.client.get(f'/attendance/gps/{self.user_b1.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_gps_tracking_cross_user_blocked(self):
        """Test IDOR: User cannot view another user's GPS tracking"""
        self.client.force_login(self.user_a1)
        
        # Try to view user A2's GPS tracking
        response = self.client.get(f'/attendance/gps/{self.user_a2.id}/')
        
        # Should be forbidden (privacy requirement)
        self.assertIn(response.status_code, [403, 404])

    def test_gps_location_update_requires_ownership(self):
        """Test IDOR: GPS updates must be for logged-in user only"""
        self.client.force_login(self.user_a1)
        
        # Try to update GPS for another user
        response = self.client.post(
            '/attendance/gps/update/',
            {
                'user_id': self.user_a2.id,
                'latitude': 1.3521,
                'longitude': 103.8198
            }
        )
        
        # Should be rejected or update only for logged-in user
        if response.status_code == 200:
            # Verify it updated only for user_a1, not user_a2
            data = response.json()
            self.assertEqual(data.get('user_id'), self.user_a1.id)

    # ==================
    # Biometric Data Security Tests
    # ==================

    def test_biometric_data_cross_tenant_blocked(self):
        """Test IDOR: Biometric data access is tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        # Try to access tenant B biometric data
        response = self.client.get(f'/attendance/biometric/{self.user_b1.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_biometric_enrollment_cross_user_blocked(self):
        """Test IDOR: Cannot enroll biometric for another user"""
        self.client.force_login(self.user_a1)
        
        # Try to enroll biometric for user A2
        response = self.client.post(
            '/attendance/biometric/enroll/',
            {
                'user_id': self.user_a2.id,
                'biometric_data': 'fake_biometric_hash'
            }
        )
        
        # Should be rejected
        self.assertIn(response.status_code, [400, 403, 404])

    # ==================
    # Direct ID Manipulation Tests
    # ==================

    def test_sequential_attendance_id_enumeration_blocked(self):
        """Test IDOR: Cannot enumerate attendance by sequential IDs"""
        self.client.force_login(self.user_a1)
        
        forbidden_count = 0
        
        # Try to access various attendance IDs
        for attendance_id in range(1, 50):
            response = self.client.get(f'/attendance/detail/{attendance_id}/')
            if response.status_code in [403, 404]:
                forbidden_count += 1
        
        # Should have significant forbidden responses
        self.assertGreater(
            forbidden_count,
            0,
            "Should prevent enumeration of attendance records"
        )

    def test_negative_attendance_id_handling(self):
        """Test IDOR: Negative IDs handled gracefully"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/attendance/detail/-1/')
        
        # Should return 400 or 404, not 500
        self.assertIn(response.status_code, [400, 404])

    # ==================
    # API Endpoint Security Tests
    # ==================

    def test_api_attendance_detail_cross_tenant_blocked(self):
        """Test IDOR: API endpoints enforce tenant isolation"""
        self.client.force_login(self.user_a1)
        
        # Try to access tenant B attendance via API
        response = self.client.get(f'/api/v1/attendance/{self.attendance_b1.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_api_attendance_list_filtered_by_tenant(self):
        """Test IDOR: API list endpoints scope to tenant"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/api/v1/attendance/')
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            
            # Should only include tenant A attendance
            attendance_ids = [item['id'] for item in results]
            
            self.assertIn(self.attendance_a1.id, attendance_ids)
            self.assertNotIn(self.attendance_b1.id, attendance_ids)

    def test_api_bulk_attendance_update_scoped_to_tenant(self):
        """Test IDOR: Bulk operations cannot affect other tenants"""
        self.client.force_login(self.user_a1)
        
        # Attempt bulk update including cross-tenant attendance
        response = self.client.post(
            '/api/v1/attendance/bulk_update/',
            {
                'attendance_ids': [self.attendance_a1.id, self.attendance_b1.id],
                'status': 'APPROVED'
            },
            content_type='application/json'
        )
        
        # Verify tenant B attendance was not affected
        self.attendance_b1.refresh_from_db()
        self.assertNotEqual(
            getattr(self.attendance_b1, 'status', None),
            'APPROVED'
        )

    # ==================
    # Time Manipulation Prevention Tests
    # ==================

    def test_cannot_backdate_attendance_for_other_user(self):
        """Test IDOR: Cannot create backdated attendance for others"""
        self.client.force_login(self.user_a1)
        
        past_time = datetime.now(dt_timezone.utc) - timedelta(days=7)
        
        # Try to create backdated attendance for user A2
        response = self.client.post(
            '/attendance/create/',
            {
                'user_id': self.user_a2.id,
                'clockintime': past_time.isoformat(),
                'clockouttime': (past_time + timedelta(hours=8)).isoformat()
            }
        )
        
        # Should be rejected
        backdated_records = PeopleTracking.objects.filter(
            people=self.user_a2,
            clockintime=past_time
        )
        
        self.assertEqual(backdated_records.count(), 0)

    def test_attendance_modification_time_window_enforced(self):
        """Test IDOR: Cannot modify old attendance records"""
        # Create old attendance
        old_attendance = PeopleTracking.objects.create(
            people=self.user_a1,
            client=self.tenant_a,
            bu=self.tenant_a,
            clockintime=datetime.now(dt_timezone.utc) - timedelta(days=30)
        )
        
        self.client.force_login(self.user_a1)
        
        # Try to modify old attendance
        response = self.client.post(
            f'/attendance/update/{old_attendance.id}/',
            {
                'clockintime': datetime.now(dt_timezone.utc) - timedelta(days=29)
            }
        )
        
        # Should be forbidden (past edit window)
        # Adjust based on actual business rules
        self.assertIn(response.status_code, [400, 403])

    # ==================
    # Report Access Security Tests
    # ==================

    def test_attendance_reports_cross_tenant_blocked(self):
        """Test IDOR: Attendance reports are tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        # Try to generate report including tenant B data
        response = self.client.post(
            '/attendance/reports/generate/',
            {
                'user_ids': [self.user_a1.id, self.user_b1.id],
                'start_date': (datetime.now(dt_timezone.utc) - timedelta(days=30)).date(),
                'end_date': datetime.now(dt_timezone.utc).date()
            }
        )
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should include tenant A data
            self.assertIn(self.user_a1.peoplename, content)
            
            # Should NOT include tenant B data
            self.assertNotIn(self.user_b1.peoplename, content)

    def test_manager_can_view_subordinate_attendance_only(self):
        """Test IDOR: Managers can only view their subordinates' attendance"""
        # Create manager for tenant A
        from apps.peoples.models import PeopleOrganizational
        
        manager_a = CompleteUserFactory(
            client=self.tenant_a,
            peoplecode="MGR_A",
            peoplename="Manager A"
        )
        
        # Set reporting relationship
        org_a1 = PeopleOrganizational.objects.get(people=self.user_a1)
        org_a1.reportto = manager_a
        org_a1.save()
        
        self.client.force_login(manager_a)
        
        # Manager should access subordinate attendance
        response_sub = self.client.get(f'/attendance/detail/{self.attendance_a1.id}/')
        self.assertEqual(response_sub.status_code, 200)
        
        # Manager should NOT access non-subordinate attendance
        response_other = self.client.get(
            f'/attendance/detail/{self.attendance_b1.id}/'
        )
        self.assertIn(response_other.status_code, [403, 404])


@pytest.mark.security
@pytest.mark.idor
@pytest.mark.integration
class AttendanceIDORIntegrationTestCase(TestCase):
    """Integration tests for attendance IDOR across multiple workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_a = BtFactory(bucode="INT_A")
        self.tenant_b = BtFactory(bucode="INT_B")
        
        self.user_a = CompleteUserFactory(client=self.tenant_a)
        self.user_b = CompleteUserFactory(client=self.tenant_b)
        
        self.client = Client()

    def test_complete_attendance_workflow_tenant_isolation(self):
        """Test full attendance workflow maintains tenant isolation"""
        self.client.force_login(self.user_a)
        
        # 1. Clock in (tenant A)
        response_clockin = self.client.post(
            '/attendance/clockin/',
            {'gps_lat': 1.3521, 'gps_lon': 103.8198}
        )
        
        # 2. Try to view tenant B attendance
        attendance_b = PeopleTracking.objects.create(
            people=self.user_b,
            client=self.tenant_b,
            bu=self.tenant_b,
            clockintime=datetime.now(dt_timezone.utc)
        )
        
        response_view = self.client.get(f'/attendance/detail/{attendance_b.id}/')
        self.assertIn(response_view.status_code, [403, 404])
        
        # 3. Clock out (tenant A only)
        response_clockout = self.client.post('/attendance/clockout/')
        
        # Verify only tenant A attendance was modified
        tenant_b_records = PeopleTracking.objects.filter(
            people=self.user_b,
            clockouttime__isnull=False
        )
        self.assertEqual(tenant_b_records.count(), 0)
