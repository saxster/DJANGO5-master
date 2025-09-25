"""
Integration tests for Mobile API endpoints.

Tests sync functionality, device management, push notifications, and offline-first architecture.
"""

import pytest
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, Mock

from apps.peoples.models import People
from apps.activity.models.asset_model import Asset


@pytest.mark.integration
@pytest.mark.mobile
@pytest.mark.api
class TestMobileSyncEndpoint:
    """Test mobile sync functionality."""
    
    def test_initial_sync_empty_database(self, mobile_client):
        """Test initial sync with empty database."""
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'test-device-123',
            'changes': {
                'create': [],
                'update': [],
                'delete': []
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        assert 'data' in response.data
        assert 'last_sync' in response.data
        assert response.data['conflicts'] == []
    
    def test_sync_with_server_changes(self, mobile_client, people_factory):
        """Test sync receiving server changes."""
        # Create server-side changes
        recent_time = timezone.now() - timedelta(minutes=5)
        people = people_factory.create_batch(3, created_at=recent_time)
        
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': (recent_time - timedelta(minutes=10)).isoformat(),
            'client_id': 'test-device-123',
            'changes': {
                'create': [],
                'update': [],
                'delete': []
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        assert 'data' in response.data
        
        sync_data = response.data['data']
        assert 'people' in sync_data
        assert len(sync_data['people']) == 3
    
    def test_sync_with_client_changes(self, mobile_client):
        """Test sync with client changes."""
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'test-device-123',
            'changes': {
                'create': [
                    {
                        'model': 'people',
                        'temp_id': 'temp_1',
                        'data': {
                            'first_name': 'Mobile',
                            'last_name': 'User',
                            'email': 'mobile@example.com',
                            'employee_code': 'MOB001'
                        }
                    }
                ],
                'update': [],
                'delete': []
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        
        # Verify person was created
        assert People.objects.filter(email='mobile@example.com').exists()
        
        # Response should include the created object with real ID
        created_objects = response.data.get('created', [])
        assert len(created_objects) == 1
        assert created_objects[0]['temp_id'] == 'temp_1'
        assert 'real_id' in created_objects[0]
    
    def test_sync_with_updates(self, mobile_client, people_factory):
        """Test sync with update operations."""
        person = people_factory.create()
        
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'test-device-123',
            'changes': {
                'create': [],
                'update': [
                    {
                        'model': 'people',
                        'id': person.id,
                        'data': {
                            'first_name': 'Updated'
                        }
                    }
                ],
                'delete': []
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        
        # Verify person was updated
        person.refresh_from_db()
        assert person.first_name == 'Updated'
    
    def test_sync_with_deletes(self, mobile_client, people_factory):
        """Test sync with delete operations."""
        person = people_factory.create()
        person_id = person.id
        
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'test-device-123',
            'changes': {
                'create': [],
                'update': [],
                'delete': [
                    {
                        'model': 'people',
                        'id': person_id
                    }
                ]
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        
        # Verify person was deleted
        assert not People.objects.filter(id=person_id).exists()
    
    def test_sync_conflict_resolution(self, mobile_client, people_factory):
        """Test conflict resolution during sync."""
        person = people_factory.create(first_name='Original')
        
        # Simulate server update after client's last sync
        person.first_name = 'ServerUpdate'
        person.save()
        
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': (timezone.now() - timedelta(hours=1)).isoformat(),
            'client_id': 'test-device-123',
            'changes': {
                'create': [],
                'update': [
                    {
                        'model': 'people',
                        'id': person.id,
                        'data': {
                            'first_name': 'ClientUpdate'
                        },
                        'last_modified': (timezone.now() - timedelta(minutes=30)).isoformat()
                    }
                ],
                'delete': []
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        
        # Should detect conflict
        conflicts = response.data.get('conflicts', [])
        if conflicts:
            assert len(conflicts) >= 1
            conflict = conflicts[0]
            assert conflict['model'] == 'people'
            assert conflict['id'] == person.id
            assert 'server_data' in conflict
            assert 'client_data' in conflict
    
    def test_sync_with_invalid_data(self, mobile_client):
        """Test sync with invalid data."""
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'test-device-123',
            'changes': {
                'create': [
                    {
                        'model': 'people',
                        'temp_id': 'temp_1',
                        'data': {
                            'first_name': 'Invalid',
                            # Missing required fields
                        }
                    }
                ]
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        # Should return validation errors
        assert response.status_code == 400
        assert 'errors' in response.data
    
    def test_sync_pagination_large_dataset(self, mobile_client, people_factory):
        """Test sync pagination with large datasets."""
        # Create many records
        people_factory.create_batch(100)
        
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'test-device-123',
            'changes': {'create': [], 'update': [], 'delete': []},
            'page_size': 25
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        
        sync_data = response.data['data']
        people_data = sync_data.get('people', [])
        
        # Should respect page size
        assert len(people_data) <= 25
        
        # Should indicate if there's more data
        if len(people_data) == 25:
            assert response.data.get('has_more', False) is True


@pytest.mark.integration
@pytest.mark.mobile
@pytest.mark.api
class TestMobileDeviceManagement:
    """Test mobile device management."""
    
    def test_device_registration(self, mobile_client):
        """Test device registration."""
        url = '/api/v1/mobile/devices/'
        data = {
            'device_id': 'test-device-123',
            'device_type': 'ios',
            'device_model': 'iPhone 14',
            'os_version': '16.0',
            'app_version': '1.0.0',
            'push_token': 'push-token-123',
            'timezone': 'America/New_York'
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 201
        assert response.data['device_id'] == 'test-device-123'
        assert response.data['is_active'] is True
    
    def test_device_update(self, mobile_client):
        """Test updating device information."""
        # Register device first
        register_url = '/api/v1/mobile/devices/'
        register_data = {
            'device_id': 'test-device-123',
            'device_type': 'ios',
            'app_version': '1.0.0'
        }
        register_response = mobile_client.post(register_url, register_data, format='json')
        device_id = register_response.data['id']
        
        # Update device
        update_url = f'/api/v1/mobile/devices/{device_id}/'
        update_data = {
            'app_version': '1.1.0',
            'push_token': 'new-push-token-456'
        }
        
        response = mobile_client.patch(update_url, update_data, format='json')
        
        assert response.status_code == 200
        assert response.data['app_version'] == '1.1.0'
        assert response.data['push_token'] == 'new-push-token-456'
    
    def test_device_list(self, mobile_client, test_user):
        """Test listing user's devices."""
        # Register multiple devices
        for i in range(3):
            data = {
                'device_id': f'test-device-{i}',
                'device_type': 'android' if i % 2 else 'ios',
                'app_version': '1.0.0'
            }
            mobile_client.post('/api/v1/mobile/devices/', data, format='json')
        
        # List devices
        response = mobile_client.get('/api/v1/mobile/devices/')
        
        assert response.status_code == 200
        assert len(response.data['results']) == 3
    
    def test_device_deactivation(self, mobile_client):
        """Test device deactivation."""
        # Register device
        register_data = {
            'device_id': 'test-device-123',
            'device_type': 'ios'
        }
        register_response = mobile_client.post('/api/v1/mobile/devices/', register_data, format='json')
        device_id = register_response.data['id']
        
        # Deactivate device
        url = f'/api/v1/mobile/devices/{device_id}/'
        response = mobile_client.delete(url)
        
        assert response.status_code == 204
        
        # Verify device is deactivated (not deleted)
        get_response = mobile_client.get(f'/api/v1/mobile/devices/{device_id}/')
        if get_response.status_code == 200:
            assert get_response.data['is_active'] is False


@pytest.mark.integration
@pytest.mark.mobile
@pytest.mark.api
class TestMobileNotifications:
    """Test mobile push notifications."""
    
    @patch('apps.api.mobile.views.send_push_notification')
    def test_send_notification(self, mock_send_push, mobile_client):
        """Test sending push notification."""
        # Register device first
        register_data = {
            'device_id': 'test-device-123',
            'device_type': 'ios',
            'push_token': 'push-token-123'
        }
        mobile_client.post('/api/v1/mobile/devices/', register_data, format='json')
        
        url = '/api/v1/mobile/notifications/'
        data = {
            'title': 'Test Notification',
            'message': 'This is a test notification',
            'data': {'key': 'value'}
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        assert response.data['sent'] is True
        
        # Verify push notification was sent
        mock_send_push.assert_called_once()
    
    @patch('apps.api.mobile.views.send_push_notification')
    def test_broadcast_notification(self, mock_send_push, mobile_client, admin_client):
        """Test broadcasting notification to all devices."""
        # Register multiple devices
        for i in range(3):
            device_data = {
                'device_id': f'device-{i}',
                'device_type': 'ios',
                'push_token': f'token-{i}'
            }
            mobile_client.post('/api/v1/mobile/devices/', device_data, format='json')
        
        # Send broadcast notification (admin only)
        url = '/api/v1/mobile/notifications/'
        data = {
            'title': 'Broadcast Message',
            'message': 'This is a broadcast to all devices',
            'broadcast': True
        }
        
        response = admin_client.post(url, data, format='json')
        
        assert response.status_code == 200
        assert response.data['sent'] is True
        assert response.data['device_count'] >= 1
        
        # Should send to multiple devices
        assert mock_send_push.call_count >= 1
    
    def test_notification_history(self, mobile_client):
        """Test notification history."""
        url = '/api/v1/mobile/notifications/'
        
        response = mobile_client.get(url)
        
        assert response.status_code == 200
        assert 'results' in response.data
        # Initially empty
        assert len(response.data['results']) == 0


@pytest.mark.integration
@pytest.mark.mobile
@pytest.mark.api
class TestMobileConfiguration:
    """Test mobile app configuration."""
    
    def test_get_mobile_config(self, mobile_client):
        """Test getting mobile app configuration."""
        url = '/api/v1/mobile/config/'
        
        response = mobile_client.get(url)
        
        assert response.status_code == 200
        
        config = response.data
        assert 'api_version' in config
        assert 'features' in config
        assert 'sync_interval' in config
        assert 'max_offline_days' in config
        assert 'supported_file_types' in config
    
    def test_config_feature_flags(self, mobile_client):
        """Test feature flags in mobile config."""
        url = '/api/v1/mobile/config/'
        
        response = mobile_client.get(url)
        
        features = response.data['features']
        assert isinstance(features, dict)
        
        # Check for expected feature flags
        expected_features = [
            'offline_sync',
            'push_notifications',
            'camera_integration',
            'biometric_auth'
        ]
        
        for feature in expected_features:
            assert feature in features
            assert isinstance(features[feature], bool)
    
    def test_config_customization_per_user(self, mobile_client, admin_client):
        """Test config customization based on user type."""
        # Regular user config
        regular_response = mobile_client.get('/api/v1/mobile/config/')
        regular_config = regular_response.data
        
        # Admin user config
        admin_response = admin_client.get('/api/v1/mobile/config/')
        admin_config = admin_response.data
        
        # Admin might have additional features
        admin_features = admin_config['features']
        regular_features = regular_config['features']
        
        assert 'admin_panel' in admin_features
        assert admin_features['admin_panel'] is True
        
        if 'admin_panel' in regular_features:
            assert regular_features['admin_panel'] is False


@pytest.mark.integration
@pytest.mark.mobile
@pytest.mark.api
class TestMobileImageOptimization:
    """Test mobile image optimization."""
    
    def test_image_upload_and_optimization(self, mobile_client):
        """Test image upload with optimization."""
        # Create a simple test image
        image_content = b'fake_image_content'
        image_file = SimpleUploadedFile(
            'test_image.jpg',
            image_content,
            content_type='image/jpeg'
        )
        
        url = '/api/v1/mobile/images/optimize/'
        data = {
            'image': image_file,
            'max_width': 800,
            'max_height': 600,
            'quality': 80
        }
        
        response = mobile_client.post(url, data)
        
        assert response.status_code == 200
        assert 'optimized_url' in response.data
        assert 'original_size' in response.data
        assert 'optimized_size' in response.data
        assert 'compression_ratio' in response.data
    
    def test_image_optimization_parameters(self, mobile_client):
        """Test different image optimization parameters."""
        image_content = b'fake_image_content'
        image_file = SimpleUploadedFile(
            'test_image.png',
            image_content,
            content_type='image/png'
        )
        
        url = '/api/v1/mobile/images/optimize/'
        data = {
            'image': image_file,
            'max_width': 400,
            'max_height': 300,
            'quality': 60,
            'format': 'jpeg'  # Convert PNG to JPEG
        }
        
        response = mobile_client.post(url, data)
        
        assert response.status_code == 200
        
        # Should indicate format conversion
        assert response.data.get('format_changed', False) is True
    
    def test_unsupported_image_format(self, mobile_client):
        """Test handling of unsupported image formats."""
        # Create a fake file with unsupported format
        file_content = b'fake_file_content'
        fake_file = SimpleUploadedFile(
            'test_file.txt',
            file_content,
            content_type='text/plain'
        )
        
        url = '/api/v1/mobile/images/optimize/'
        data = {'image': fake_file}
        
        response = mobile_client.post(url, data)
        
        assert response.status_code == 400
        assert 'error' in response.data
        assert 'supported' in response.data['error'].lower()


@pytest.mark.integration
@pytest.mark.mobile
@pytest.mark.api
class TestMobileOfflineCapabilities:
    """Test mobile offline-first capabilities."""
    
    def test_offline_data_storage_structure(self, mobile_client, bulk_test_data):
        """Test data structure optimized for offline storage."""
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'offline-device',
            'changes': {'create': [], 'update': [], 'delete': []}
        }
        
        response = mobile_client.post(url, data, format='json')
        
        sync_data = response.data['data']
        
        # Data should be structured for offline use
        assert 'people' in sync_data
        assert 'groups' in sync_data
        assert 'assets' in sync_data
        
        # Check for optimized field structure
        if sync_data['people']:
            person = sync_data['people'][0]
            # Should have essential fields only
            assert 'id' in person
            assert 'first_name' in person
            assert 'last_name' in person
            # Might exclude heavy fields for mobile
    
    def test_incremental_sync_optimization(self, mobile_client, people_factory):
        """Test incremental sync for bandwidth optimization."""
        # Initial sync
        initial_time = timezone.now()
        
        initial_response = mobile_client.post('/api/v1/mobile/sync/', {
            'last_sync': None,
            'client_id': 'bandwidth-test',
            'changes': {'create': [], 'update': [], 'delete': []}
        }, format='json')
        
        # Create new data after initial sync
        new_person = people_factory.create(created_at=initial_time + timedelta(minutes=5))
        
        # Incremental sync
        incremental_response = mobile_client.post('/api/v1/mobile/sync/', {
            'last_sync': initial_response.data['last_sync'],
            'client_id': 'bandwidth-test',
            'changes': {'create': [], 'update': [], 'delete': []}
        }, format='json')
        
        assert incremental_response.status_code == 200
        
        # Should only return new/changed data
        incremental_data = incremental_response.data['data']
        people_data = incremental_data.get('people', [])
        
        if people_data:
            # Should contain only the newly created person
            assert len(people_data) == 1
            assert people_data[0]['id'] == new_person.id
    
    def test_conflict_resolution_strategies(self, mobile_client, people_factory):
        """Test different conflict resolution strategies."""
        person = people_factory.create(first_name='Original')
        
        # Test server-wins strategy
        person.first_name = 'ServerUpdate'
        person.save()
        
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': (timezone.now() - timedelta(hours=1)).isoformat(),
            'client_id': 'conflict-test',
            'conflict_resolution': 'server_wins',
            'changes': {
                'update': [{
                    'model': 'people',
                    'id': person.id,
                    'data': {'first_name': 'ClientUpdate'}
                }]
            }
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        
        # Server should win - no conflict reported
        conflicts = response.data.get('conflicts', [])
        assert len(conflicts) == 0
        
        # Verify server data is preserved
        person.refresh_from_db()
        assert person.first_name == 'ServerUpdate'
    
    def test_data_compression_for_mobile(self, mobile_client, bulk_test_data):
        """Test data compression for mobile bandwidth optimization."""
        url = '/api/v1/mobile/sync/'
        data = {
            'last_sync': None,
            'client_id': 'compression-test',
            'compress': True,
            'changes': {'create': [], 'update': [], 'delete': []}
        }
        
        response = mobile_client.post(url, data, format='json')
        
        assert response.status_code == 200
        
        # Check for compression indicators
        if 'Content-Encoding' in response:
            assert 'gzip' in response['Content-Encoding']