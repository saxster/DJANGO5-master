"""
Staffing Forecaster Tests

Test workforce forecasting based on historical patterns.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.attendance.services.staffing_forecaster import StaffingForecaster
from apps.attendance.models import Attendance
from apps.client_onboarding.models import Bt, BusinessUnit


@pytest.mark.django_db
class TestStaffingForecaster:
    """Test staffing forecast calculations."""
    
    @pytest.fixture
    def site(self):
        """Create test site."""
        client = BusinessUnit.objects.create(name='Test Client')
        return Bt.objects.create(unitcode='SITE001', client=client)
    
    @pytest.fixture
    def historical_attendance(self, site):
        """Create historical attendance data."""
        now = timezone.now()
        
        for days_ago in range(90):
            date = now - timedelta(days=days_ago)
            Attendance.objects.create(
                site=site,
                checkin=date,
                is_on_time=True
            )
        
        return site
    
    def test_forecast_generation(self, historical_attendance):
        """Test basic forecast generation."""
        forecast = StaffingForecaster.forecast_weekly_staffing(historical_attendance.id)
        
        assert 'site' in forecast
        assert 'shifts' in forecast
        assert 'weekly_summary' in forecast
        assert 'recommendations' in forecast
    
    def test_incident_impact_calculation(self, historical_attendance):
        """Test incident rate impact on staffing needs."""
        impact = StaffingForecaster._calculate_incident_impact(historical_attendance.id, days=30)
        
        assert impact >= 1.0
        assert impact <= 1.5
