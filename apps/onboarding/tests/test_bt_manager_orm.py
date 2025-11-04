"""
Tests for BtManagerORM Django ORM implementations.
"""

from django.test import TestCase
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from apps.onboarding.bt_manager_orm import BtManagerORM
from apps.peoples.models import People


class BtManagerORMTestCase(TestCase):
    """Test cases for BT hierarchy ORM implementations"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for BT hierarchy"""
        # Create root type for hierarchy
        root_type = TypeAssist.objects.create(
            tacode='BUTYPE',
            taname='Business Unit Type'
        )

        # Create identifiers with proper hierarchy
        cls.client_type = TypeAssist.objects.create(
            tacode='CLIENT',
            taname='Client',
            tatype=root_type
        )
        cls.site_type = TypeAssist.objects.create(
            tacode='SITE',
            taname='Site',
            tatype=root_type
        )
        
        # Create BT hierarchy
        # Root
        cls.root = Bt.objects.create(
            id=1,
            bucode='ROOT',
            buname='Root',
            butype=cls.client_type
        )

        # Client
        cls.client_bt = Bt.objects.create(
            id=100,
            bucode='CLIENT1',
            buname='Test Client',
            parent=cls.root,
            butype=cls.client_type
        )

        # Sites under client (with identifier set for site filter)
        cls.site1 = Bt.objects.create(
            id=200,
            bucode='SITE1',
            buname='Site 1',
            parent=cls.client_bt,
            butype=cls.site_type,
            identifier=cls.site_type  # Set identifier for SITE filter
        )

        cls.site2 = Bt.objects.create(
            id=201,
            bucode='SITE2',
            buname='Site 2',
            parent=cls.client_bt,
            butype=cls.site_type,
            identifier=cls.site_type  # Set identifier for SITE filter
        )

        # Sub-site
        cls.subsite = Bt.objects.create(
            id=300,
            bucode='SUBSITE1',
            buname='Sub Site 1',
            parent=cls.site1,
            butype=cls.site_type,
            identifier=cls.site_type  # Set identifier for SITE filter
        )
    
    def test_get_all_bu_of_client_array(self):
        """Test getting all BUs under a client as array"""
        result = BtManagerORM.get_all_bu_of_client(100, 'array')
        
        # Should include client and all sites/subsites
        self.assertIsInstance(result, list)
        self.assertIn(200, result)  # Site 1
        self.assertIn(201, result)  # Site 2  
        self.assertIn(300, result)  # Sub site
        # Should not include parent (root)
        self.assertNotIn(1, result)
    
    def test_get_all_bu_of_client_text(self):
        """Test getting all BUs under a client as text"""
        result = BtManagerORM.get_all_bu_of_client(100, 'text')
        
        self.assertIsInstance(result, str)
        self.assertIn('200', result)
        self.assertIn('201', result)
        self.assertIn('300', result)
    
    def test_get_whole_tree(self):
        """Test getting whole BU tree including parents"""
        result = BtManagerORM.get_whole_tree(200)  # Starting from Site 1
        
        self.assertIsInstance(result, list)
        # Should include the site itself
        self.assertIn(200, result)
        # Should include child
        self.assertIn(300, result)
        # Should include parents
        self.assertIn(100, result)  # Client
        # Root (id=1) is excluded by design
    
    def test_get_bulist_parents_only(self):
        """Test getting only parent nodes"""
        result = BtManagerORM.get_bulist(
            bu_id=300,  # Start from subsite
            include_parents=True,
            include_children=False,
            return_type='array'
        )
        
        self.assertIn(300, result)  # Node itself
        self.assertIn(200, result)  # Parent site
        self.assertIn(100, result)  # Client
        self.assertNotIn(201, result)  # Sibling site
    
    def test_get_bulist_children_only(self):
        """Test getting only child nodes"""
        result = BtManagerORM.get_bulist(
            bu_id=100,  # Start from client
            include_parents=False,
            include_children=True,
            return_type='array'
        )
        
        self.assertIn(100, result)  # Node itself
        self.assertIn(200, result)  # Site 1
        self.assertIn(201, result)  # Site 2
        self.assertIn(300, result)  # Subsite
        self.assertNotIn(1, result)  # Root
    
    def test_get_bulist_jsonb_format(self):
        """Test JSONB format output"""
        result = BtManagerORM.get_bulist(
            bu_id=100,
            include_parents=False,
            include_children=True,
            return_type='jsonb'
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('200', result)
        self.assertEqual(result['200']['bucode'], 'SITE1')
        self.assertEqual(result['200']['buname'], 'Site 1')
        self.assertEqual(result['200']['parent_id'], 100)
    
    def test_empty_result(self):
        """Test handling of non-existent BU"""
        result = BtManagerORM.get_all_bu_of_client(99999, 'array')
        self.assertEqual(result, [])
        
        result = BtManagerORM.get_all_bu_of_client(99999, 'text')
        self.assertEqual(result, '')
    
    def test_get_sitelist_web_admin(self):
        """Test site list for admin user"""
        # Create admin user
        from datetime import date
        admin = People.objects.create(
            id=1000,
            peoplecode='ADMIN1',
            peoplename='Admin User',
            client_id=100,
            bu_id=100,  # Set BU ID to match client
            isadmin=True,
            loginid='admin1',
            dateofbirth=date(1980, 1, 1),
            email='admin@example.com',
            mobno='1234567890'  # Add required field
        )
        
        result = BtManagerORM.get_sitelist_web(100, 1000)
        
        self.assertIsInstance(result, list)
        # Admin should see all sites
        site_ids = [r['id'] for r in result]
        self.assertIn(200, site_ids)
        self.assertIn(201, site_ids)
    
    def test_caching(self):
        """Test that results reflect current database state"""
        # First call
        result1 = BtManagerORM.get_all_bu_of_client(100, 'array')

        # Modify data
        new_site = Bt.objects.create(
            id=999,
            bucode='NEWSITE',
            buname='New Site',
            parent=self.__class__.client_bt,
            butype=self.__class__.site_type
        )

        # Second call should include the new site
        result2 = BtManagerORM.get_all_bu_of_client(100, 'array')

        # Results should include new site (no caching by default)
        self.assertIn(999, result2)

        # Clean up
        new_site.delete()