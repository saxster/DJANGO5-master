"""
Comprehensive tests for the GeofenceService
"""

from django.test import TestCase, override_settings
from django.core.cache import cache
from apps.core.services.geofence_service import GeofenceService, GeofenceAuditTrail

class GeofenceServiceTests(TestCase):
    """Test cases for GeofenceService"""
    
    def setUp(self):
        """Set up test data"""
        self.service = GeofenceService()
        
        # Clear cache before each test
        cache.clear()
        
        # Create test polygon (simple square)
        self.test_polygon = Polygon([
            [0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]
        ])
        
        # Create test circular geofence (lat, lon, radius_km)
        self.test_circle = (0.5, 0.5, 0.5)  # Center at (0.5, 0.5) with 0.5km radius
    
    def test_point_in_polygon_geofence(self):
        """Test point-in-polygon detection"""
        # Point inside polygon
        self.assertTrue(
            self.service.is_point_in_geofence(0.5, 0.5, self.test_polygon)
        )
        
        # Point outside polygon
        self.assertFalse(
            self.service.is_point_in_geofence(2.0, 2.0, self.test_polygon)
        )
        
        # Point on edge (should be considered inside)
        self.assertTrue(
            self.service.is_point_in_geofence(0.0, 0.5, self.test_polygon)
        )
    
    def test_point_in_circular_geofence(self):
        """Test point-in-circle detection using Haversine formula"""
        # Point inside circle
        self.assertTrue(
            self.service.is_point_in_geofence(0.5, 0.5, self.test_circle)
        )
        
        # Point outside circle
        self.assertFalse(
            self.service.is_point_in_geofence(2.0, 2.0, self.test_circle)
        )
        
        # Point on edge (approximately)
        # Using small distance that should be within 0.5km radius
        self.assertTrue(
            self.service.is_point_in_geofence(0.50001, 0.50001, self.test_circle)
        )
    
    def test_hysteresis_logic(self):
        """Test hysteresis prevents rapid state changes"""
        # Test case: point near boundary
        lat, lon = 0.0, 0.5  # Point on polygon edge
        
        # Without hysteresis - state can change
        current_state = self.service.is_point_in_geofence(lat, lon, self.test_polygon)
        
        # With hysteresis - should maintain previous state when close to boundary
        with patch.object(self.service, '_calculate_distance_to_polygon_boundary', return_value=10):  # 10m from boundary
            # If previously inside, should stay inside despite being "outside" now
            stabilized_state = self.service.is_point_in_geofence(
                lat, lon, self.test_polygon, use_hysteresis=True, previous_state=True
            )
            self.assertTrue(stabilized_state)  # Should maintain previous state
    
    @patch('apps.onboarding.models.GeofenceMaster.objects.filter')
    def test_get_active_geofences_no_cache(self, mock_filter):
        """Test getting active geofences without cache"""
        # Mock database response
        mock_geofences = [
            {
                'id': 1, 'gfcode': 'GF001', 'gfname': 'Test Geofence',
                'geofence': self.test_polygon, 'alerttext': 'Test Alert',
                'alerttogroup_id': None, 'alerttopeople_id': None
            }
        ]
        mock_filter.return_value.exclude.return_value.values.return_value = mock_geofences
        
        # Test without cache
        geofences = self.service.get_active_geofences(client_id=1, bu_id=1, use_cache=False)
        
        self.assertEqual(len(geofences), 1)
        self.assertEqual(geofences[0]['gfcode'], 'GF001')
        mock_filter.assert_called_once()
    
    @patch('apps.onboarding.models.GeofenceMaster.objects.filter')
    def test_get_active_geofences_with_cache(self, mock_filter):
        """Test getting active geofences with cache"""
        mock_geofences = [
            {
                'id': 1, 'gfcode': 'GF001', 'gfname': 'Test Geofence',
                'geofence': self.test_polygon, 'alerttext': 'Test Alert',
                'alerttogroup_id': None, 'alerttopeople_id': None
            }
        ]
        mock_filter.return_value.exclude.return_value.values.return_value = mock_geofences
        
        # First call - should hit database
        geofences1 = self.service.get_active_geofences(client_id=1, bu_id=1, use_cache=True)
        
        # Second call - should hit cache
        geofences2 = self.service.get_active_geofences(client_id=1, bu_id=1, use_cache=True)
        
        self.assertEqual(geofences1, geofences2)
        # Database should only be called once
        mock_filter.assert_called_once()
    
    @patch.object(GeofenceService, 'get_active_geofences')
    def test_batch_point_checking(self, mock_get_geofences):
        """Test batch checking of multiple points"""
        # Mock geofences data
        mock_get_geofences.return_value = [
            {
                'id': 1, 'gfcode': 'GF001', 'gfname': 'Test Geofence',
                'geofence': self.test_polygon, 'alerttext': 'Test Alert'
            }
        ]
        
        # Test points
        points = [
            (0.5, 0.5),  # Inside polygon
            (2.0, 2.0),  # Outside polygon
        ]
        
        results = self.service.check_multiple_points_in_geofences(
            points=points, client_id=1, bu_id=1
        )
        
        # Point 0 should match geofence
        self.assertEqual(len(results['point_0']), 1)
        self.assertEqual(results['point_0'][0]['gfcode'], 'GF001')
        
        # Point 1 should not match any geofence
        self.assertEqual(len(results['point_1']), 0)
    
    def test_cache_invalidation(self):
        """Test cache invalidation functionality"""
        # Set up cache with test data
        cache_key = self.service.ACTIVE_GEOFENCES_KEY.format(client_id=1, bu_id=1)
        test_data = [{'id': 1, 'gfcode': 'GF001'}]
        cache.set(cache_key, test_data)
        
        # Verify data is cached
        self.assertEqual(cache.get(cache_key), test_data)
        
        # Invalidate cache
        self.service.invalidate_geofence_cache(client_id=1, bu_id=1)
        
        # Verify data is removed
        self.assertIsNone(cache.get(cache_key))
    
    def test_haversine_distance_calculation(self):
        """Test Haversine distance calculation accuracy"""
        # Test known distance (approximately 111km between 1 degree of latitude)
        lat1, lon1 = 0.0, 0.0
        lat2, lon2 = 1.0, 0.0
        
        distance = self.service._haversine_distance(lat1, lon1, lat2, lon2)
        
        # Should be approximately 111km (within 1km tolerance)
        self.assertAlmostEqual(distance, 111.0, delta=1.0)
    
    def test_error_handling_invalid_geofence(self):
        """Test error handling for invalid geofence types"""
        # Invalid geofence type should return False
        result = self.service.is_point_in_geofence(0.5, 0.5, "invalid_geofence")
        self.assertFalse(result)
        
        # Invalid tuple length should return False
        result = self.service.is_point_in_geofence(0.5, 0.5, (0.5, 0.5))  # Missing radius
        self.assertFalse(result)


class GeofenceAuditTrailTests(TestCase):
    """Test cases for GeofenceAuditTrail"""
    
    def setUp(self):
        """Set up test data"""
        self.audit_trail = GeofenceAuditTrail()
        cache.clear()
    
    def test_log_geofence_modification(self):
        """Test logging geofence modifications"""
        # Log a modification
        self.audit_trail.log_geofence_modification(
            geofence_id=1,
            user_id=100,
            action='UPDATE',
            changes={'gfname': 'New Name'}
        )
        
        # Check if audit entry was cached
        today = datetime.now().strftime('%Y%m%d')
        audit_key = f"geofence_audit:1:{today}"
        cached_audits = cache.get(audit_key)
        
        self.assertIsNotNone(cached_audits)
        self.assertEqual(len(cached_audits), 1)
        self.assertEqual(cached_audits[0]['action'], 'UPDATE')
        self.assertEqual(cached_audits[0]['user_id'], 100)
    
    def test_log_geofence_violation(self):
        """Test logging geofence violations"""
        # Log a violation
        self.audit_trail.log_geofence_violation(
            people_id=200,
            geofence_id=1,
            violation_type='ENTRY',
            location=(0.5, 0.5),
            additional_data={'alert_sent': True}
        )
        
        # Check if violation was cached
        today = datetime.now().strftime('%Y%m%d')
        violation_key = f"geofence_violations:{today}"
        cached_violations = cache.get(violation_key)
        
        self.assertIsNotNone(cached_violations)
        self.assertEqual(len(cached_violations), 1)
        self.assertEqual(cached_violations[0]['violation_type'], 'ENTRY')
        self.assertEqual(cached_violations[0]['people_id'], 200)
        self.assertEqual(cached_violations[0]['location']['lat'], 0.5)
    
    def test_get_recent_violations(self):
        """Test retrieving recent violations"""
        # Log multiple violations over multiple days
        for i in range(3):
            self.audit_trail.log_geofence_violation(
                people_id=200 + i,
                geofence_id=1,
                violation_type='ENTRY',
                location=(0.5, 0.5)
            )
        
        # Retrieve recent violations
        violations = self.audit_trail.get_recent_violations(days=1)
        
        self.assertEqual(len(violations), 3)
        # Should be sorted by timestamp (newest first)
        timestamps = [v['timestamp'] for v in violations]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))
    
    def test_violation_cache_limit(self):
        """Test that violation cache doesn't exceed limits"""
        # Log more than 1000 violations
        for i in range(1001):
            self.audit_trail.log_geofence_violation(
                people_id=i,
                geofence_id=1,
                violation_type='ENTRY',
                location=(0.5, 0.5)
            )
        
        # Check that cache was trimmed to 1000
        today = datetime.now().strftime('%Y%m%d')
        violation_key = f"geofence_violations:{today}"
        cached_violations = cache.get(violation_key)
        
        self.assertEqual(len(cached_violations), 1000)


class GeofenceServiceIntegrationTests(TestCase):
    """Integration tests for GeofenceService with Django models"""

    def setUp(self):
        """Set up test data"""
        # Define a test polygon for edge case testing
        self.test_polygon = [
            [0.0, 0.0],
            [10.0, 0.0],
            [10.0, 10.0],
            [0.0, 10.0],
            [0.0, 0.0]
        ]

    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    })
    def test_full_geofence_workflow(self):
        """Test complete workflow from database to cache to checking"""
        # This would require actual Django model instances
        # Skipping detailed implementation as it would need test database setup
        pass
    
    def test_edge_cases(self):
        """Test various edge cases"""
        service = GeofenceService()
        
        # Test with None values
        result = service.is_point_in_geofence(None, None, self.test_polygon)
        self.assertFalse(result)
        
        # Test with extreme coordinates
        result = service.is_point_in_geofence(90.0, 180.0, self.test_polygon)
        self.assertFalse(result)
        
        # Test empty points list
        results = service.check_multiple_points_in_geofences([], 1, 1)
        self.assertEqual(results, {})


class GeofenceServicePerformanceTests(TestCase):
    """Performance tests for GeofenceService"""
    
    def test_batch_performance(self):
        """Test performance of batch operations"""
        import time
        
        service = GeofenceService()
        
        # Create many test points
        points = [(i * 0.1, j * 0.1) for i in range(10) for j in range(10)]
        
        # Mock geofences
        with patch.object(service, 'get_active_geofences') as mock_get:
            mock_get.return_value = [
                {
                    'id': 1, 'gfcode': 'GF001', 'gfname': 'Test',
                    'geofence': Polygon([
                        [0.0, 0.0], [0.0, 5.0], [5.0, 5.0], [5.0, 0.0], [0.0, 0.0]
                    ]), 'alerttext': 'Test'
                }
            ]
            
            start_time = time.time()
            results = service.check_multiple_points_in_geofences(points, 1, 1)
            end_time = time.time()
            
            # Should complete in reasonable time (less than 1 second for 100 points)
            self.assertLess(end_time - start_time, 1.0)
            self.assertEqual(len(results), 100)  # 10x10 grid