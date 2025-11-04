"""
Security tests for API v2 device management endpoints.

Ensures device data is isolated per user and cross-device sync state
cannot be accessed by other tenants/users.
"""

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models.device_registry import UserDevice, DeviceSyncState
from apps.client_onboarding.models import Bt

User = get_user_model()


class DeviceViewSecurityTests(TestCase):
    """Verify device endpoints enforce per-user isolation."""

    def setUp(self):
        self.client = Client()
        self.business_unit = Bt.objects.create(btcode='SECURE_BU', btname='Secure BU')

        self.owner = User.objects.create_user(
            loginid='owneruser',
            peoplecode='OWN001',
            peoplename='Owner User',
            email='owner@example.com',
            password='owner-pass',
            bu=self.business_unit
        )

        self.other_user = User.objects.create_user(
            loginid='otheruser',
            peoplecode='OTH001',
            peoplename='Other User',
            email='other@example.com',
            password='other-pass',
            bu=self.business_unit
        )

        self.device = UserDevice.objects.create(
            user=self.owner,
            device_id='device-owner-123',
            device_type='phone',
            priority=40,
            device_name='Owner Phone',
            os_type='Android',
            os_version='14',
            app_version='2.0.0'
        )

        self.sync_state = DeviceSyncState.objects.create(
            device=self.device,
            domain='voice',
            entity_id=uuid4(),
            last_sync_version=5,
            last_modified_at=timezone.now(),
            is_dirty=False
        )

    def test_owner_can_view_device_details(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('api_v2:device-detail', args=[self.device.device_id])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['device_id'], self.device.device_id)

    def test_non_owner_gets_not_found_on_detail(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse('api_v2:device-detail', args=[self.device.device_id])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_owner_cannot_deactivate_device(self):
        self.client.force_login(self.other_user)
        response = self.client.delete(
            reverse('api_v2:device-detail', args=[self.device.device_id])
        )
        self.assertEqual(response.status_code, 404)

        self.device.refresh_from_db()
        self.assertTrue(self.device.is_active)

    def test_non_owner_cannot_access_sync_state(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse('api_v2:device-sync-state', args=[self.device.device_id])
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_receives_sync_state(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('api_v2:device-sync-state', args=[self.device.device_id])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['device_id'], self.device.device_id)
        self.assertEqual(len(payload['data']['sync_state']), 1)
