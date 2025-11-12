"""
Tests for Threat Intelligence Work Order Integration

Validates auto-creation of work orders from threat alerts.
"""
import pytest
from django.test import TestCase
from django.contrib.gis.geos import Point, Polygon
from apps.threat_intelligence.models import (
    ThreatEvent,
    TenantIntelligenceProfile,
    IntelligenceAlert,
)
from apps.threat_intelligence.services.work_order_integration import ThreatWorkOrderService
from apps.work_order_management.models import Wom
from apps.tenants.models import Tenant
from django.utils import timezone


@pytest.mark.django_db
class TestWorkOrderIntegration(TestCase):
    """Test work order auto-creation from threat alerts."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name='Test Facility',
            domain='test.example.com',
        )
        
        # Create monitored area (simple polygon)
        self.monitored_area = Polygon((
            (77.5, 12.9),
            (77.6, 12.9),
            (77.6, 13.0),
            (77.5, 13.0),
            (77.5, 12.9),
        ))
        
        self.profile = TenantIntelligenceProfile.objects.create(
            tenant=self.tenant,
            monitored_locations=self.monitored_area,
            buffer_radius_km=10.0,
            minimum_severity='HIGH',
            minimum_confidence=0.7,
            enable_work_order_creation=True,
            is_active=True,
        )
    
    def test_create_work_order_for_weather_threat(self):
        """Test work order creation for weather threat."""
        event = ThreatEvent.objects.create(
            title='Severe Thunderstorm Warning',
            description='Heavy rain and wind expected',
            category='WEATHER',
            severity='CRITICAL',
            confidence_score=0.9,
            location=Point(77.55, 12.95, srid=4326),
            event_start_time=timezone.now(),
        )
        
        alert = IntelligenceAlert.objects.create(
            threat_event=event,
            intelligence_profile=self.profile,
            tenant=self.tenant,
            severity='CRITICAL',
            urgency_level='IMMEDIATE',
            distance_km=5.0,
        )
        
        work_order = ThreatWorkOrderService.create_work_order_for_alert(alert)
        
        # Verify work order created
        self.assertIsNotNone(work_order)
        self.assertEqual(work_order.tenant, self.tenant)
        self.assertEqual(work_order.priority, 'HIGH')
        self.assertIn('Weather Emergency Response', work_order.description)
        
        # Verify link to alert
        alert.refresh_from_db()
        self.assertEqual(alert.work_order, work_order)
        self.assertTrue(alert.work_order_created)
        
        # Verify work order metadata
        self.assertEqual(work_order.other_data['source'], 'THREAT_INTELLIGENCE')
        self.assertEqual(work_order.other_data['alert_id'], alert.id)
        self.assertEqual(work_order.other_data['threat_category'], 'WEATHER')
    
    def test_create_work_order_for_security_threat(self):
        """Test work order creation for terrorism threat."""
        event = ThreatEvent.objects.create(
            title='Security Alert',
            description='Suspicious activity reported',
            category='TERRORISM',
            severity='HIGH',
            confidence_score=0.85,
            location=Point(77.55, 12.95, srid=4326),
            event_start_time=timezone.now(),
        )
        
        alert = IntelligenceAlert.objects.create(
            threat_event=event,
            intelligence_profile=self.profile,
            tenant=self.tenant,
            severity='HIGH',
            urgency_level='RAPID',
            distance_km=2.0,
        )
        
        work_order = ThreatWorkOrderService.create_work_order_for_alert(alert)
        
        self.assertIsNotNone(work_order)
        self.assertIn('CRITICAL: Security Threat', work_order.description)
        self.assertEqual(work_order.priority, 'HIGH')
        self.assertEqual(work_order.workstatus, Wom.Workstatus.ASSIGNED)
    
    def test_work_order_contains_threat_details(self):
        """Test work order includes formatted threat details."""
        event = ThreatEvent.objects.create(
            title='Infrastructure Failure',
            description='Power grid malfunction',
            category='INFRASTRUCTURE',
            severity='HIGH',
            confidence_score=0.8,
            location=Point(77.55, 12.95, srid=4326),
            location_name='Downtown Grid Station',
            event_start_time=timezone.now(),
        )
        
        alert = IntelligenceAlert.objects.create(
            threat_event=event,
            intelligence_profile=self.profile,
            tenant=self.tenant,
            severity='HIGH',
            urgency_level='STANDARD',
            distance_km=3.5,
        )
        
        work_order = ThreatWorkOrderService.create_work_order_for_alert(alert)
        
        full_desc = work_order.other_data['full_description']
        
        # Verify threat details included
        self.assertIn('Infrastructure', full_desc)
        self.assertIn('Downtown Grid Station', full_desc)
        self.assertIn('3.5km from facility', full_desc)
        self.assertIn('80%', full_desc)  # Confidence score
        self.assertIn(str(alert.id), full_desc)
    
    def test_default_template_for_unknown_category(self):
        """Test fallback to default template for unrecognized categories."""
        event = ThreatEvent.objects.create(
            title='Unknown Event',
            description='Unclassified event',
            category='OTHER',
            severity='MEDIUM',
            confidence_score=0.7,
            location=Point(77.55, 12.95, srid=4326),
            event_start_time=timezone.now(),
        )
        
        alert = IntelligenceAlert.objects.create(
            threat_event=event,
            intelligence_profile=self.profile,
            tenant=self.tenant,
            severity='MEDIUM',
            urgency_level='STANDARD',
            distance_km=10.0,
        )
        
        work_order = ThreatWorkOrderService.create_work_order_for_alert(alert)
        
        self.assertIsNotNone(work_order)
        self.assertIn('Threat Response Required', work_order.description)
        self.assertEqual(work_order.priority, 'MEDIUM')
    
    def test_work_order_creation_is_atomic(self):
        """Test work order creation is transactional."""
        event = ThreatEvent.objects.create(
            title='Test Event',
            category='WEATHER',
            severity='HIGH',
            confidence_score=0.8,
            location=Point(77.55, 12.95, srid=4326),
            event_start_time=timezone.now(),
        )
        
        alert = IntelligenceAlert.objects.create(
            threat_event=event,
            intelligence_profile=self.profile,
            tenant=self.tenant,
            severity='HIGH',
            urgency_level='IMMEDIATE',
            distance_km=5.0,
        )
        
        # Count before
        wo_count_before = Wom.objects.count()
        
        work_order = ThreatWorkOrderService.create_work_order_for_alert(alert)
        
        # Verify atomic creation
        self.assertEqual(Wom.objects.count(), wo_count_before + 1)
        
        alert.refresh_from_db()
        self.assertTrue(alert.work_order_created)
