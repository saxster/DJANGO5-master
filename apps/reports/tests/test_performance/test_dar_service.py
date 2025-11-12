"""
Performance tests for DAR service N+1 optimizations.

Tests verify attendance calculations use database aggregation instead of loops.
"""

import pytest
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.db import connection
from apps.reports.services.dar_service import DARService
from apps.attendance.models import Attendance
from apps.peoples.models import People
from apps.client_onboarding.models import Bt


@pytest.mark.django_db
class TestDARServicePerformance(TestCase):
    """Performance tests for DAR generation."""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data once."""
        cls.site = Bt.objects.filter(pk=1).first() or Bt.objects.create(
            buname='Test Site',
            tenant_id=1
        )
    
    def test_attendance_aggregation_uses_database_calculation(self):
        """Attendance aggregation should use DB calculations, not Python loops."""
        shift_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        shift_end = shift_start + timedelta(hours=24)
        
        # Create 50 attendance records with varying durations
        for i in range(50):
            user = People.objects.create(
                peoplename=f'Guard {i}',
                peopleemail=f'guard{i}@example.com',
                bu_id=1
            )
            
            checkin_time = shift_start + timedelta(hours=1)
            checkout_time = shift_end - timedelta(hours=1, minutes=i)
            
            Attendance.objects.create(
                location=self.site,
                people=user,
                checkin=checkin_time,
                checkout=checkout_time,
                tenant_id=1
            )
        
        # Test query count
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        stats = DARService._get_attendance_stats(
            self.site.id,
            shift_start,
            shift_end
        )
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Should use 3-4 queries max (not 50+ for loop)
        self.assertLessEqual(
            queries_used, 5,
            f"Attendance stats used {queries_used} queries, expected <= 5"
        )
        
        # Verify calculations
        self.assertIn('total_hours_worked', stats)
        self.assertGreater(stats['total_hours_worked'], 0)
        self.assertEqual(stats['guards_assigned'], 50)
        self.assertEqual(stats['guards_present'], 50)
    
    def test_attendance_calculation_scales_constant(self):
        """Query count should not scale with number of attendance records."""
        query_counts = []
        
        for size in [10, 30, 50]:
            shift_start = timezone.now().replace(hour=0, minute=0)
            shift_end = shift_start + timedelta(hours=24)
            
            # Create attendance records
            for i in range(size):
                user = People.objects.create(
                    peoplename=f'User {size}-{i}',
                    peopleemail=f'user{size}{i}@example.com',
                    bu_id=1
                )
                Attendance.objects.create(
                    location=self.site,
                    people=user,
                    checkin=shift_start + timedelta(hours=2),
                    checkout=shift_end - timedelta(hours=2),
                    tenant_id=1
                )
            
            # Measure queries
            connection.force_debug_cursor = True
            query_count_before = len(connection.queries)
            
            stats = DARService._get_attendance_stats(
                self.site.id,
                shift_start,
                shift_end
            )
            
            query_count_after = len(connection.queries)
            queries_used = query_count_after - query_count_before
            query_counts.append(queries_used)
            
            # Clean up
            Attendance.objects.filter(location=self.site).delete()
            People.objects.filter(peopleemail__contains=f'{size}@').delete()
        
        # All sizes should use similar query count
        for count in query_counts:
            self.assertLessEqual(
                count, 6,
                f"Query count {count} should be constant across data sizes"
            )
    
    def test_hours_calculation_accuracy(self):
        """Verify database calculation produces accurate results."""
        shift_start = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        shift_end = shift_start + timedelta(hours=12)
        
        # Create attendance with known duration
        user = People.objects.create(
            peoplename='Test Guard',
            peopleemail='testguard@example.com',
            bu_id=1
        )
        
        checkin = shift_start
        checkout = shift_start + timedelta(hours=8)  # Exactly 8 hours
        
        Attendance.objects.create(
            location=self.site,
            people=user,
            checkin=checkin,
            checkout=checkout,
            tenant_id=1
        )
        
        stats = DARService._get_attendance_stats(
            self.site.id,
            shift_start - timedelta(hours=1),
            shift_end
        )
        
        # Should calculate 8 hours
        self.assertAlmostEqual(
            stats['total_hours_worked'],
            8.0,
            places=1,
            msg="Database aggregation should calculate exact hours"
        )
        
        # Average hours per guard
        self.assertAlmostEqual(
            stats['average_hours_per_guard'],
            8.0,
            places=1
        )


@pytest.mark.django_db
class TestDARIncidentsOptimization(TestCase):
    """Test incident retrieval optimization in DAR service."""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.site = Bt.objects.filter(pk=1).first() or Bt.objects.create(
            buname='Test Site',
            tenant_id=1
        )
        cls.user = People.objects.create(
            peoplename='Test Creator',
            peopleemail='creator@example.com',
            bu_id=1
        )
    
    def test_incidents_with_select_related(self):
        """Incident queries should use select_related for foreign keys."""
        from apps.activity.models.job import Job
        
        shift_start = timezone.now().replace(hour=0, minute=0)
        shift_end = shift_start + timedelta(hours=24)
        
        # Create jobs (incidents) with related data
        for i in range(20):
            Job.objects.create(
                location=self.site,
                created_by=self.user,
                other_data={'priority': 'high', 'description': f'Incident {i}'},
                checkin=shift_start + timedelta(hours=i % 12),
                tenant_id=1
            )
        
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        incidents = DARService._get_incidents(
            self.site.id,
            shift_start,
            shift_end
        )
        
        # Access related data (should not trigger queries)
        for inc in incidents:
            _ = inc.get('created_by')
            _ = inc.get('priority')
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Should use 1 query with select_related
        self.assertLessEqual(
            queries_used, 2,
            f"Incident retrieval used {queries_used} queries, expected <= 2"
        )


@pytest.mark.django_db
class TestDARFullGeneration(TestCase):
    """Test complete DAR generation performance."""
    
    @classmethod
    def setUpTestData(cls):
        """Create comprehensive test data."""
        cls.site = Bt.objects.filter(pk=1).first() or Bt.objects.create(
            buname='Full Test Site',
            tenant_id=1
        )
    
    def test_full_dar_generation_query_efficiency(self):
        """Complete DAR should use optimized queries throughout."""
        from apps.activity.models.job import Job
        
        shift_start = timezone.now().replace(hour=0, minute=0)
        shift_end = shift_start + timedelta(hours=24)
        
        # Create comprehensive data
        # 30 attendance records
        for i in range(30):
            user = People.objects.create(
                peoplename=f'Full Guard {i}',
                peopleemail=f'fullguard{i}@example.com',
                bu_id=1
            )
            Attendance.objects.create(
                location=self.site,
                people=user,
                checkin=shift_start + timedelta(hours=1),
                checkout=shift_end - timedelta(hours=1),
                tenant_id=1
            )
        
        # 15 incidents
        creator = People.objects.create(
            peoplename='Incident Creator',
            peopleemail='incidents@example.com',
            bu_id=1
        )
        for i in range(15):
            Job.objects.create(
                location=self.site,
                created_by=creator,
                other_data={'priority': 'medium'},
                checkin=shift_start + timedelta(hours=i % 12),
                tenant_id=1
            )
        
        # Measure full generation
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        # Get all DAR components
        attendance_stats = DARService._get_attendance_stats(
            self.site.id, shift_start, shift_end
        )
        incidents = DARService._get_incidents(
            self.site.id, shift_start, shift_end
        )
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Should use <10 queries for entire DAR (not 30+ for loops)
        self.assertLessEqual(
            queries_used, 10,
            f"Full DAR generation used {queries_used} queries, expected <= 10"
        )
        
        # Verify data integrity
        self.assertEqual(attendance_stats['guards_assigned'], 30)
        self.assertGreaterEqual(len(incidents), 15)
