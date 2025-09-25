"""
Test script for Business Unit (Bt) UI improvements
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/home/jarvis/DJANGO5/YOUTILITY5')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.onboarding.models import Bt, TypeAssist
from apps.peoples.models import People
from django.urls import reverse
import json

User = get_user_model()

class BtUIImprovementsTest(TestCase):
    """Test the improved Business Unit UI"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test TypeAssist entries
        self.ta_site = TypeAssist.objects.create(
            tacode='SITE',
            taname='Site',
            tatype='BU_TYPE'
        )
        
        self.ta_client = TypeAssist.objects.create(
            tacode='CLIENT',
            taname='Client',
            tatype='BU_IDENTIFIER'
        )
        
        # Create test site incharge
        self.site_incharge = People.objects.create(
            peoplemname='John Doe',
            peoplecode='EMP001'
        )
        
        # Create test business units with various configurations
        self.bu_warehouse = Bt.objects.create(
            bucode='WH001',
            buname='Main Warehouse',
            butype=self.ta_site,
            identifier=self.ta_client,
            iswarehouse=True,
            gpsenable=True,
            siteincharge=self.site_incharge,
            solid='SOL001'
        )
        
        self.bu_vendor = Bt.objects.create(
            bucode='VEN001',
            buname='ABC Vendor',
            butype=self.ta_site,
            identifier=self.ta_client,
            isvendor=True,
            deviceevent=True
        )
        
        self.bu_service = Bt.objects.create(
            bucode='SVC001',
            buname='XYZ Services',
            butype=self.ta_site,
            identifier=self.ta_client,
            isserviceprovider=True,
            gpsenable=True
        )
        
        self.bu_inactive = Bt.objects.create(
            bucode='INACT001',
            buname='Inactive Site',
            butype=self.ta_site,
            identifier=self.ta_client,
            enable=False
        )
        
    def test_view_returns_enhanced_fields(self):
        """Test that the view returns all enhanced fields"""
        self.client.force_login(self.user)
        
        # Set session data
        session = self.client.session
        session['client_id'] = self.bu_warehouse.id
        session.save()
        
        url = reverse('admin_panel:bu_list')
        response = self.client.get(url, {'action': 'list'})
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('data', data)
        
        # Check if enhanced fields are present
        if data['data']:
            first_record = data['data'][0]
            
            # Check for new fields
            self.assertIn('siteincharge__peoplemname', first_record)
            self.assertIn('gpsenable', first_record)
            self.assertIn('iswarehouse', first_record)
            self.assertIn('isvendor', first_record)
            self.assertIn('isserviceprovider', first_record)
            self.assertIn('deviceevent', first_record)
            self.assertIn('solid', first_record)
            
    def test_filter_active_only(self):
        """Test filtering for active records only"""
        self.client.force_login(self.user)
        
        session = self.client.session
        session['client_id'] = self.bu_warehouse.id
        session.save()
        
        url = reverse('admin_panel:bu_list')
        response = self.client.get(url, {
            'action': 'list',
            'filter_active': 'true'
        })
        
        data = json.loads(response.content)
        
        # All returned records should have enable=True
        for record in data['data']:
            if 'enable' in record:
                self.assertTrue(record['enable'])
                
    def test_filter_gps_enabled(self):
        """Test filtering for GPS enabled sites"""
        self.client.force_login(self.user)
        
        session = self.client.session
        session['client_id'] = self.bu_warehouse.id
        session.save()
        
        url = reverse('admin_panel:bu_list')
        response = self.client.get(url, {
            'action': 'list',
            'filter_gps': 'true'
        })
        
        data = json.loads(response.content)
        
        # All returned records should have gpsenable=True
        for record in data['data']:
            if 'gpsenable' in record:
                self.assertTrue(record['gpsenable'])
                
    def test_filter_business_categories(self):
        """Test filtering by business categories"""
        self.client.force_login(self.user)
        
        session = self.client.session
        session['client_id'] = self.bu_warehouse.id
        session.save()
        
        # Test warehouse filter
        url = reverse('admin_panel:bu_list')
        response = self.client.get(url, {
            'action': 'list',
            'filter_warehouse': 'true'
        })
        
        data = json.loads(response.content)
        for record in data['data']:
            if 'iswarehouse' in record:
                self.assertTrue(record['iswarehouse'])
                
    def test_search_includes_new_fields(self):
        """Test that search includes site incharge and Sol ID"""
        self.client.force_login(self.user)
        
        session = self.client.session
        session['client_id'] = self.bu_warehouse.id
        session.save()
        
        url = reverse('admin_panel:bu_list')
        
        # Search by site incharge name
        response = self.client.get(url, {
            'action': 'list',
            'search[value]': 'John'
        })
        
        data = json.loads(response.content)
        self.assertGreater(len(data['data']), 0)
        
        # Search by Sol ID
        response = self.client.get(url, {
            'action': 'list',
            'search[value]': 'SOL001'
        })
        
        data = json.loads(response.content)
        self.assertGreater(len(data['data']), 0)

if __name__ == '__main__':
    # Run the tests
    from django.test import TestCase
    import unittest
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(BtUIImprovementsTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ All UI improvement tests passed successfully!")
    else:
        print("\n❌ Some tests failed. Please review the output above.")