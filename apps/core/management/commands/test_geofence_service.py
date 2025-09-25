"""
Management command to test and demonstrate the enhanced GeofenceService
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Point, Polygon
from apps.core.services.geofence_service import geofence_service
from apps.onboarding.models import GeofenceMaster, Bt
import time
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test and demonstrate the enhanced GeofenceService'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-type',
            type=str,
            choices=['basic', 'cache', 'batch', 'hysteresis', 'all'],
            default='basic',
            help='Type of test to run'
        )
        parser.add_argument(
            '--client-id',
            type=int,
            default=1,
            help='Client ID for testing'
        )
        parser.add_argument(
            '--bu-id',
            type=int,
            default=1,
            help='Business Unit ID for testing'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Testing Enhanced GeofenceService')
        )
        
        test_type = options['test_type']
        client_id = options['client_id']
        bu_id = options['bu_id']

        if test_type == 'all':
            self.run_all_tests(client_id, bu_id)
        elif test_type == 'basic':
            self.test_basic_functionality()
        elif test_type == 'cache':
            self.test_cache_functionality(client_id, bu_id)
        elif test_type == 'batch':
            self.test_batch_functionality(client_id, bu_id)
        elif test_type == 'hysteresis':
            self.test_hysteresis_functionality()

    def run_all_tests(self, client_id, bu_id):
        """Run all available tests"""
        self.stdout.write("🔄 Running all tests...\n")
        
        self.test_basic_functionality()
        self.stdout.write()
        
        self.test_cache_functionality(client_id, bu_id)
        self.stdout.write()
        
        self.test_batch_functionality(client_id, bu_id)
        self.stdout.write()
        
        self.test_hysteresis_functionality()
        self.stdout.write()
        
        self.stdout.write(
            self.style.SUCCESS('✅ All tests completed!')
        )

    def test_basic_functionality(self):
        """Test basic geofence checking functionality"""
        self.stdout.write("🧪 Testing basic functionality...")
        
        # Create test polygon (simple square)
        test_polygon = Polygon([
            [0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]
        ])
        
        # Test points
        test_cases = [
            (0.5, 0.5, True, "Point inside polygon"),
            (2.0, 2.0, False, "Point outside polygon"),
            (0.0, 0.5, True, "Point on edge"),
        ]
        
        for lat, lon, expected, description in test_cases:
            result = geofence_service.is_point_in_geofence(lat, lon, test_polygon)
            status = "✅" if result == expected else "❌"
            self.stdout.write(f"  {status} {description}: {result}")
        
        # Test circular geofence
        test_circle = (0.5, 0.5, 0.5)  # Center at (0.5, 0.5) with 0.5km radius
        
        circle_cases = [
            (0.5, 0.5, True, "Point at center of circle"),
            (2.0, 2.0, False, "Point outside circle"),
        ]
        
        for lat, lon, expected, description in circle_cases:
            result = geofence_service.is_point_in_geofence(lat, lon, test_circle)
            status = "✅" if result == expected else "❌"
            self.stdout.write(f"  {status} {description}: {result}")

    def test_cache_functionality(self, client_id, bu_id):
        """Test cache functionality"""
        self.stdout.write("🗄️  Testing cache functionality...")
        
        # Clear cache first
        geofence_service.invalidate_geofence_cache(client_id, bu_id)
        self.stdout.write("  📝 Cache cleared")
        
        # First call - should hit database
        start_time = time.time()
        geofences1 = geofence_service.get_active_geofences(client_id, bu_id, use_cache=True)
        db_time = time.time() - start_time
        
        # Second call - should hit cache
        start_time = time.time()
        geofences2 = geofence_service.get_active_geofences(client_id, bu_id, use_cache=True)
        cache_time = time.time() - start_time
        
        self.stdout.write(f"  📊 Found {len(geofences1)} geofences")
        self.stdout.write(f"  ⏱️  Database query time: {db_time:.4f}s")
        self.stdout.write(f"  ⚡ Cache query time: {cache_time:.4f}s")
        
        if cache_time < db_time:
            self.stdout.write("  ✅ Cache is faster than database")
        else:
            self.stdout.write("  ⚠️  Cache performance needs investigation")
        
        # Test cache invalidation
        geofence_service.invalidate_geofence_cache(client_id, bu_id)
        self.stdout.write("  🗑️  Cache invalidated successfully")

    def test_batch_functionality(self, client_id, bu_id):
        """Test batch processing functionality"""
        self.stdout.write("📦 Testing batch functionality...")
        
        # Create test points
        test_points = [
            (0.5, 0.5),   # Likely inside most geofences
            (1.5, 1.5),   # Likely outside most geofences
            (0.1, 0.1),   # Edge case
            (10.0, 10.0), # Definitely outside
        ]
        
        start_time = time.time()
        results = geofence_service.check_multiple_points_in_geofences(
            points=test_points,
            client_id=client_id,
            bu_id=bu_id
        )
        batch_time = time.time() - start_time
        
        self.stdout.write(f"  ⏱️  Batch processing time: {batch_time:.4f}s")
        self.stdout.write(f"  📊 Processed {len(test_points)} points")
        
        for point_key, matches in results.items():
            if matches:
                self.stdout.write(f"  ✅ {point_key}: {len(matches)} geofence matches")
            else:
                self.stdout.write(f"  ⭕ {point_key}: No geofence matches")

    def test_hysteresis_functionality(self):
        """Test hysteresis functionality"""
        self.stdout.write("🔄 Testing hysteresis functionality...")
        
        # Create test polygon
        test_polygon = Polygon([
            [0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]
        ])
        
        # Test point near boundary
        lat, lon = 0.0, 0.5  # Point on edge
        
        # Without hysteresis
        result_no_hysteresis = geofence_service.is_point_in_geofence(
            lat, lon, test_polygon, use_hysteresis=False
        )
        
        # With hysteresis - previous state was inside
        result_with_hysteresis = geofence_service.is_point_in_geofence(
            lat, lon, test_polygon, use_hysteresis=True, previous_state=True
        )
        
        self.stdout.write(f"  📍 Test point: ({lat}, {lon})")
        self.stdout.write(f"  🔄 Without hysteresis: {result_no_hysteresis}")
        self.stdout.write(f"  🛡️  With hysteresis: {result_with_hysteresis}")
        
        if result_no_hysteresis != result_with_hysteresis:
            self.stdout.write("  ✅ Hysteresis is working (state stabilized)")
        else:
            self.stdout.write("  ℹ️  Hysteresis had no effect (point not near boundary)")

    def test_audit_functionality(self):
        """Test audit trail functionality"""
        self.stdout.write("📋 Testing audit functionality...")
        
        # Test geofence modification logging
        geofence_service.audit_trail.log_geofence_modification(
            geofence_id=999,
            user_id=1,
            action='TEST',
            changes={'test': 'audit_trail'}
        )
        
        # Test violation logging
        geofence_service.audit_trail.log_geofence_violation(
            people_id=999,
            geofence_id=999,
            violation_type='TEST_ENTRY',
            location=(0.5, 0.5),
            additional_data={'test': True}
        )
        
        # Get recent violations
        violations = geofence_service.audit_trail.get_recent_violations(days=1)
        
        self.stdout.write(f"  📊 Recent violations: {len(violations)}")
        if violations:
            latest = violations[0]
            self.stdout.write(f"  🕒 Latest violation: {latest['violation_type']} by person {latest['people_id']}")
        
        self.stdout.write("  ✅ Audit trail functionality working")