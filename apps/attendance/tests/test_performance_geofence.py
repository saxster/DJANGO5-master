"""
Performance and load tests for geofence calculations

Tests the scalability and performance characteristics of geofence operations
under various load conditions and data sizes.
"""

import pytest
import time
import threading
import random
from django.test import TestCase, TransactionTestCase
from django.contrib.gis.geos import Point, Polygon
from concurrent.futures import ThreadPoolExecutor, as_completed

from apps.attendance.services.geospatial_service import GeospatialService


@pytest.mark.performance
class TestGeofencePerformance(TestCase):
    """Performance tests for geofence operations"""

    def setUp(self):
        """Set up test data for performance tests"""
        # Create various test geofences of different complexities

        # Simple circular geofence (NYC center, 10km radius)
        self.simple_circular = (40.7128, -74.0060, 10.0)

        # Complex polygon geofence (Manhattan outline)
        self.complex_polygon = Polygon([
            (-74.0479, 40.6829), (-73.9441, 40.8176), (-73.9297, 40.7969),
            (-74.0151, 40.7005), (-74.0094, 40.7589), (-73.9734, 40.7614),
            (-73.9496, 40.7869), (-73.9568, 40.8007), (-73.9734, 40.7987),
            (-73.9913, 40.7589), (-74.0151, 40.7589), (-74.0479, 40.6829)
        ], srid=4326)

        # Very complex polygon with many vertices (simulated building outline)
        vertices = []
        center_lat, center_lon = 40.7128, -74.0060
        for i in range(100):  # 100-sided polygon
            angle = (i / 100) * 2 * 3.14159
            lat_offset = 0.001 * (0.8 + 0.4 * random.random()) * (1 if i % 2 else -1)
            lon_offset = 0.001 * (0.8 + 0.4 * random.random()) * (1 if i % 2 else -1)
            vertices.append((
                center_lon + lon_offset * (1 + 0.1 * (i % 10)),
                center_lat + lat_offset * (1 + 0.1 * (i % 10))
            ))
        vertices.append(vertices[0])  # Close polygon
        self.very_complex_polygon = Polygon(vertices, srid=4326)

        # Generate test points for validation
        self.test_points = [
            (40.7128 + random.uniform(-0.1, 0.1), -74.0060 + random.uniform(-0.1, 0.1))
            for _ in range(1000)
        ]

    def test_circular_geofence_performance(self):
        """Test performance of circular geofence calculations"""
        start_time = time.time()

        for lat, lon in self.test_points:
            GeospatialService.is_point_in_geofence(lat, lon, self.simple_circular)

        end_time = time.time()
        duration = end_time - start_time

        print(f"Circular geofence: {len(self.test_points)} validations in {duration:.3f}s")
        print(f"Rate: {len(self.test_points)/duration:.0f} validations/second")

        # Should process at least 1000 validations per second
        self.assertLess(duration, 1.0)

    def test_complex_polygon_performance(self):
        """Test performance of complex polygon geofence calculations"""
        start_time = time.time()

        for lat, lon in self.test_points:
            GeospatialService.is_point_in_geofence(lat, lon, self.complex_polygon)

        end_time = time.time()
        duration = end_time - start_time

        print(f"Complex polygon: {len(self.test_points)} validations in {duration:.3f}s")
        print(f"Rate: {len(self.test_points)/duration:.0f} validations/second")

        # Should complete within reasonable time (allow more time for complex polygons)
        self.assertLess(duration, 5.0)

    def test_very_complex_polygon_performance(self):
        """Test performance with very complex polygon (100+ vertices)"""
        start_time = time.time()

        for lat, lon in self.test_points[:100]:  # Test with fewer points for very complex geofence
            GeospatialService.is_point_in_geofence(lat, lon, self.very_complex_polygon)

        end_time = time.time()
        duration = end_time - start_time

        print(f"Very complex polygon: 100 validations in {duration:.3f}s")
        print(f"Rate: {100/duration:.0f} validations/second")

        # Should complete within reasonable time
        self.assertLess(duration, 2.0)

    def test_distance_calculation_performance(self):
        """Test performance of distance calculations"""
        # Test points around the world
        global_points = [
            (40.7128, -74.0060),  # NYC
            (34.0522, -118.2437), # LA
            (51.5074, -0.1278),   # London
            (35.6762, 139.6503),  # Tokyo
            (-33.8688, 151.2093), # Sydney
            (55.7558, 37.6176),   # Moscow
            (19.4326, -99.1332),  # Mexico City
            (-22.9068, -43.1729), # Rio de Janeiro
        ]

        start_time = time.time()

        # Calculate distances between all pairs
        distances = []
        for i, (lat1, lon1) in enumerate(global_points):
            for j, (lat2, lon2) in enumerate(global_points[i+1:], i+1):
                distance = GeospatialService.haversine_distance(lat1, lon1, lat2, lon2)
                distances.append(distance)

        end_time = time.time()
        duration = end_time - start_time

        print(f"Distance calculations: {len(distances)} calculations in {duration:.3f}s")
        print(f"Rate: {len(distances)/duration:.0f} calculations/second")

        # Should be very fast
        self.assertLess(duration, 0.1)

    def test_coordinate_validation_performance(self):
        """Test performance of coordinate validation"""
        test_coordinates = [
            (random.uniform(-90, 90), random.uniform(-180, 180))
            for _ in range(10000)
        ]

        start_time = time.time()

        for lat, lon in test_coordinates:
            try:
                GeospatialService.validate_coordinates(lat, lon)
            except:
                pass  # Some coordinates might be invalid, that's expected

        end_time = time.time()
        duration = end_time - start_time

        print(f"Coordinate validation: {len(test_coordinates)} validations in {duration:.3f}s")
        print(f"Rate: {len(test_coordinates)/duration:.0f} validations/second")

        # Should be very fast
        self.assertLess(duration, 0.5)

    def test_point_creation_performance(self):
        """Test performance of Point geometry creation"""
        start_time = time.time()

        points = []
        for lat, lon in self.test_points:
            try:
                point = GeospatialService.create_point(lat, lon)
                points.append(point)
            except:
                pass  # Some coordinates might be invalid

        end_time = time.time()
        duration = end_time - start_time

        print(f"Point creation: {len(points)} points in {duration:.3f}s")
        print(f"Rate: {len(points)/duration:.0f} points/second")

        # Should be reasonably fast
        self.assertLess(duration, 2.0)


@pytest.mark.performance
class TestConcurrentGeofenceOperations(TransactionTestCase):
    """Test geofence operations under concurrent access"""

    def setUp(self):
        """Set up test data for concurrent tests"""
        self.geofence = (40.7128, -74.0060, 5.0)  # 5km radius around NYC
        self.test_points = [
            (40.7128 + random.uniform(-0.05, 0.05), -74.0060 + random.uniform(-0.05, 0.05))
            for _ in range(100)
        ]

    def validate_points_batch(self, points, thread_id):
        """Validate a batch of points in a single thread"""
        results = []
        start_time = time.time()

        for lat, lon in points:
            result = GeospatialService.is_point_in_geofence(lat, lon, self.geofence)
            results.append((lat, lon, result))

        end_time = time.time()
        return {
            'thread_id': thread_id,
            'results': results,
            'duration': end_time - start_time,
            'count': len(results)
        }

    def test_concurrent_geofence_validation(self):
        """Test concurrent geofence validation from multiple threads"""
        num_threads = 10
        points_per_thread = len(self.test_points) // num_threads

        # Split points among threads
        thread_points = [
            self.test_points[i*points_per_thread:(i+1)*points_per_thread]
            for i in range(num_threads)
        ]

        start_time = time.time()

        # Run validations concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(self.validate_points_batch, points, i)
                for i, points in enumerate(thread_points)
            ]

            results = []
            for future in as_completed(futures):
                results.append(future.result())

        end_time = time.time()
        total_duration = end_time - start_time

        # Analyze results
        total_validations = sum(r['count'] for r in results)
        max_thread_duration = max(r['duration'] for r in results)

        print(f"Concurrent validation: {total_validations} validations in {total_duration:.3f}s")
        print(f"Max thread duration: {max_thread_duration:.3f}s")
        print(f"Throughput: {total_validations/total_duration:.0f} validations/second")

        # Should complete efficiently
        self.assertLess(total_duration, 5.0)
        self.assertEqual(total_validations, len(self.test_points))

    def test_thread_safety(self):
        """Test thread safety of geospatial operations"""
        num_threads = 20
        operations_per_thread = 50
        errors = []

        def worker_thread(thread_id):
            """Worker function for thread safety test"""
            thread_errors = []
            try:
                for i in range(operations_per_thread):
                    # Perform various operations
                    lat = 40.7128 + random.uniform(-0.01, 0.01)
                    lon = -74.0060 + random.uniform(-0.01, 0.01)

                    # Validate coordinates
                    GeospatialService.validate_coordinates(lat, lon)

                    # Create point
                    point = GeospatialService.create_point(lat, lon)

                    # Extract coordinates
                    extracted_lon, extracted_lat = GeospatialService.extract_coordinates(point)

                    # Validate geofence
                    is_inside = GeospatialService.is_point_in_geofence(lat, lon, self.geofence)

                    # Calculate distance
                    distance = GeospatialService.haversine_distance(
                        lat, lon, 40.7128, -74.0060
                    )

                    # Basic sanity checks
                    assert abs(extracted_lat - lat) < 0.000001
                    assert abs(extracted_lon - lon) < 0.000001
                    assert distance >= 0
                    assert isinstance(is_inside, bool)

            except Exception as e:
                thread_errors.append(f"Thread {thread_id}: {str(e)}")

            return thread_errors

        # Run threads concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(worker_thread, i)
                for i in range(num_threads)
            ]

            for future in as_completed(futures):
                thread_errors = future.result()
                errors.extend(thread_errors)

        # Should have no errors
        if errors:
            self.fail(f"Thread safety errors: {errors}")

        print(f"Thread safety test: {num_threads} threads, {operations_per_thread} ops each")
        print("All operations completed without errors")


@pytest.mark.performance
class TestMemoryUsage(TestCase):
    """Test memory usage characteristics of geofence operations"""

    def test_memory_usage_under_load(self):
        """Test memory usage during intensive geofence operations"""
        import gc
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large polygon
        vertices = [
            (random.uniform(-74.1, -73.9), random.uniform(40.6, 40.8))
            for _ in range(1000)
        ]
        vertices.append(vertices[0])  # Close polygon
        large_polygon = Polygon(vertices, srid=4326)

        # Perform many operations
        for i in range(5000):
            lat = random.uniform(40.6, 40.8)
            lon = random.uniform(-74.1, -73.9)

            GeospatialService.is_point_in_geofence(lat, lon, large_polygon)

            # Force garbage collection periodically
            if i % 1000 == 0:
                gc.collect()

        # Get final memory usage
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        memory_growth = final_memory - initial_memory

        print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB")
        print(f"Memory growth: {memory_growth:.1f}MB")

        # Memory growth should be reasonable (less than 50MB for this test)
        self.assertLess(memory_growth, 50)

    def test_no_memory_leaks(self):
        """Test for memory leaks in repeated operations"""
        import gc

        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Perform many operations
        for _ in range(1000):
            lat = random.uniform(40.6, 40.8)
            lon = random.uniform(-74.1, -73.9)

            # Create and discard many objects
            point = GeospatialService.create_point(lat, lon)
            extracted = GeospatialService.extract_coordinates(point)
            formatted = GeospatialService.format_coordinates(lat, lon)
            distance = GeospatialService.haversine_distance(lat, lon, 40.7, -74.0)

        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())

        object_growth = final_objects - initial_objects

        print(f"Object count: {initial_objects} -> {final_objects}")
        print(f"Object growth: {object_growth}")

        # Object growth should be minimal (allow some growth for test infrastructure)
        self.assertLess(object_growth, 100)


@pytest.mark.performance
class TestScalability(TestCase):
    """Test scalability characteristics with large datasets"""

    def test_large_number_of_geofences(self):
        """Test performance with many geofences"""
        # Create 100 different geofences
        geofences = []
        for i in range(100):
            center_lat = 40.7 + random.uniform(-0.1, 0.1)
            center_lon = -74.0 + random.uniform(-0.1, 0.1)
            radius = random.uniform(0.5, 5.0)
            geofences.append((center_lat, center_lon, radius))

        test_point = (40.7128, -74.0060)
        start_time = time.time()

        # Test point against all geofences
        results = []
        for geofence in geofences:
            result = GeospatialService.is_point_in_geofence(
                test_point[0], test_point[1], geofence
            )
            results.append(result)

        end_time = time.time()
        duration = end_time - start_time

        print(f"Large geofence test: 1 point vs {len(geofences)} geofences in {duration:.3f}s")
        print(f"Rate: {len(geofences)/duration:.0f} checks/second")

        # Should be fast
        self.assertLess(duration, 1.0)

    def test_large_number_of_points(self):
        """Test performance with many points against single geofence"""
        # Create 10,000 test points
        large_point_set = [
            (40.7 + random.uniform(-0.2, 0.2), -74.0 + random.uniform(-0.2, 0.2))
            for _ in range(10000)
        ]

        geofence = (40.7128, -74.0060, 10.0)
        start_time = time.time()

        inside_count = 0
        for lat, lon in large_point_set:
            if GeospatialService.is_point_in_geofence(lat, lon, geofence):
                inside_count += 1

        end_time = time.time()
        duration = end_time - start_time

        print(f"Large point test: {len(large_point_set)} points vs 1 geofence in {duration:.3f}s")
        print(f"Rate: {len(large_point_set)/duration:.0f} points/second")
        print(f"Points inside geofence: {inside_count}")

        # Should complete within reasonable time
        self.assertLess(duration, 10.0)

    def test_coordinate_precision_performance(self):
        """Test performance impact of high-precision coordinates"""
        # Test with very high precision coordinates
        high_precision_points = [
            (40.712800123456789, -74.006000987654321),
            (40.712801234567890, -74.006001876543210),
            (40.712802345678901, -74.006002765432109),
        ] * 1000  # Repeat to get 3000 points

        geofence = (40.7128, -74.0060, 1.0)
        start_time = time.time()

        for lat, lon in high_precision_points:
            GeospatialService.is_point_in_geofence(lat, lon, geofence)

        end_time = time.time()
        duration = end_time - start_time

        print(f"High precision test: {len(high_precision_points)} points in {duration:.3f}s")
        print(f"Rate: {len(high_precision_points)/duration:.0f} points/second")

        # Should not be significantly slower than normal precision
        self.assertLess(duration, 5.0)


if __name__ == '__main__':
    # Run performance tests
    pytest.main([__file__, '-v', '--tb=short', '-m', 'performance'])