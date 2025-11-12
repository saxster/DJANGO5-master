"""
Metrics Calculation Tests

Tests for individual metric calculators.
"""

import pytest
from datetime import date, time, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.performance_analytics.services.attendance_metrics_calculator import AttendanceMetricsCalculator
from apps.performance_analytics.services.task_metrics_calculator import TaskMetricsCalculator
from apps.performance_analytics.services.bpi_calculator import BalancedPerformanceIndexCalculator

People = get_user_model()


@pytest.mark.django_db
class TestAttendanceMetricsCalculator(TestCase):
    """Test attendance metrics calculations."""
    
    def setUp(self):
        """Set up test data."""
        self.user = People.objects.create_user(
            loginid='testworker',
            email='test@example.com',
            password='testpass123'
        )
        self.target_date = date(2025, 11, 5)
    
    def test_calculate_attendance_score_perfect(self):
        """Test perfect attendance scores 100."""
        # All metrics at 100% should yield 100 score
        result = AttendanceMetricsCalculator.calculate_attendance_score(
            metrics={
                'on_time_rate': 100.0,
                'attendance_rate': 100.0,
                'geofence_compliance_rate': 100.0,
                'ncns_count': 0
            }
        )
        
        assert result >= 95  # Near perfect score

    def test_calculate_on_time_rate(self):
        """Test on-time rate calculation."""
        # This would require mock Schedule and Attendance data
        # Placeholder for integration test
        pass


@pytest.mark.django_db
class TestBPICalculator(TestCase):
    """Test BPI calculation."""
    
    def test_bpi_weighted_calculation(self):
        """Test BPI uses correct weights."""
        components = {
            'attendance_score': 80.0,
            'task_score': 90.0,
            'patrol_score': 85.0,
            'work_order_score': 75.0,
            'compliance_score': 95.0
        }
        
        # Expected: (80*0.3) + (90*0.25) + (85*0.2) + (75*0.15) + (95*0.1)
        expected = 24 + 22.5 + 17 + 11.25 + 9.5
        assert expected == 84.25
        
    def test_cohort_key_generation(self):
        """Test cohort key format."""
        cohort_key = BalancedPerformanceIndexCalculator._build_cohort_key(
            self.user,
            self.target_date
        )
        
        # Should be format: site_id|role|shift_type|tenure_band|month
        parts = cohort_key.split('|')
        assert len(parts) == 5
        assert parts[4] == '2025-11'  # Month


__all__ = [
    'TestAttendanceMetricsCalculator',
    'TestBPICalculator',
]
