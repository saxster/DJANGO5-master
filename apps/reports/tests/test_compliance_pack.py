"""
Compliance Pack Service Tests

Test monthly compliance audit pack generation.
"""

import pytest
from datetime import datetime
from django.utils import timezone
from apps.reports.services.compliance_pack_service import CompliancePackService
from apps.onboarding.models import BusinessUnit


@pytest.mark.django_db
class TestCompliancePackService:
    """Test compliance pack generation."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return BusinessUnit.objects.create(name='Compliance Test Client')
    
    def test_generate_monthly_pack(self, client):
        """Test monthly compliance pack generation."""
        now = timezone.now()
        pack = CompliancePackService.generate_monthly_pack(
            client_id=client.id,
            month=now.month,
            year=now.year
        )
        
        assert 'metadata' in pack
        assert 'attendance_compliance' in pack
        assert 'patrol_coverage' in pack
        assert 'sla_performance' in pack
        assert 'incident_response' in pack
        assert 'device_uptime' in pack
        assert 'audit_summary' in pack
    
    def test_metadata_structure(self, client):
        """Test pack metadata structure."""
        now = timezone.now()
        pack = CompliancePackService.generate_monthly_pack(
            client_id=client.id,
            month=now.month,
            year=now.year
        )
        
        assert pack['metadata']['client'] == 'Compliance Test Client'
        assert 'generated_at' in pack['metadata']
        assert pack['metadata']['standard'] == 'PSARA/ISO 9001'
    
    def test_attendance_compliance_metrics(self, client):
        """Test attendance compliance calculations."""
        now = timezone.now()
        pack = CompliancePackService.generate_monthly_pack(
            client_id=client.id,
            month=now.month,
            year=now.year
        )
        
        metrics = pack['attendance_compliance']
        assert 'total_shifts' in metrics
        assert 'on_time_shifts' in metrics
        assert 'compliance_rate' in metrics
        assert 0 <= metrics['compliance_rate'] <= 100
