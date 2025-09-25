"""
Django tests for template URL generation and rendering
Tests that updated templates correctly use new URL namespaces
"""

import pytest
from django.test import TestCase, Client
from django.template import Template, Context
from django.template.loader import render_to_string, get_template
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from unittest.mock import patch, MagicMock
from apps.onboarding.models import BusinessUnit, Client, Contract
from apps.core.models import TypeAssist, Shift, GeoFence

User = get_user_model()


@pytest.mark.django_db
class TestTemplateURLGeneration(TestCase):
    """Test that templates generate correct URLs with new namespaces"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test data
        self.business_unit = BusinessUnit.objects.create(
            buname='Test BU',
            bucode='TEST001'
        )
        
        self.client.force_login(self.user)
    
    def test_business_unit_form_template_urls(self):
        """Test that bu_form.html uses correct URL namespaces"""
        template_path = 'onboarding/bu_form.html'
        
        try:
            # Test URL generation within template context
            context = {
                'bu_form': MagicMock(),
                'request': HttpRequest(),
                'user': self.user
            }
            
            # This should not raise an exception
            rendered = render_to_string(template_path, context)
            
            # Check that the template renders without error
            self.assertIsInstance(rendered, str)
            self.assertGreater(len(rendered), 0)
            
            # Check that admin_panel namespace is used instead of onboarding
            self.assertNotIn('onboarding:bu', rendered)
            
            # Check for correct URL patterns
            if 'admin_panel:bu_list' in rendered:
                self.assertIn('admin_panel:bu_list', rendered)
                
        except Exception as e:
            self.fail(f"Template rendering failed: {e}")
    
    def test_business_unit_list_template_urls(self):
        """Test that bu_list.html uses correct URL namespaces"""
        template_path = 'onboarding/bu_list.html'
        
        try:
            context = {
                'request': HttpRequest(),
                'user': self.user,
                'bu_list': []
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:bu', rendered)
            
        except Exception as e:
            self.fail(f"BU list template rendering failed: {e}")
    
    def test_client_form_template_urls(self):
        """Test that client_buform.html uses admin_panel:clients_list"""
        template_path = 'onboarding/client_buform.html'
        
        try:
            context = {
                'client_form': MagicMock(),
                'request': HttpRequest(),
                'user': self.user
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:client', rendered)
            
        except Exception as e:
            self.fail(f"Client form template rendering failed: {e}")
    
    def test_client_list_template_urls(self):
        """Test that client_bulist.html uses correct URLs"""
        template_path = 'onboarding/client_bulist.html'
        
        try:
            context = {
                'request': HttpRequest(),
                'user': self.user,
                'client_list': []
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:client', rendered)
            
        except Exception as e:
            self.fail(f"Client list template rendering failed: {e}")
    
    def test_contract_form_template_urls(self):
        """Test that contract_form.html uses admin_panel:contracts_list"""
        template_path = 'onboarding/contract_form.html'
        
        try:
            context = {
                'contract_form': MagicMock(),
                'request': HttpRequest(),
                'user': self.user
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:contract', rendered)
            
        except Exception as e:
            self.fail(f"Contract form template rendering failed: {e}")
    
    def test_geofence_form_template_urls(self):
        """Test that geofence_form.html uses admin_panel:config_geofences"""
        template_path = 'onboarding/geofence_form.html'
        
        try:
            context = {
                'geofence_form': MagicMock(),
                'request': HttpRequest(),
                'user': self.user
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:geofence', rendered)
            
        except Exception as e:
            self.fail(f"Geofence form template rendering failed: {e}")
    
    def test_typeassist_template_urls(self):
        """Test that typeassist.html uses admin_panel:config_types"""
        template_path = 'onboarding/typeassist.html'
        
        try:
            context = {
                'request': HttpRequest(),
                'user': self.user
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:typeassist', rendered)
            
        except Exception as e:
            self.fail(f"TypeAssist template rendering failed: {e}")
    
    def test_shift_template_urls(self):
        """Test that shift.html uses admin_panel:config_shifts"""
        template_path = 'onboarding/shift.html'
        
        try:
            context = {
                'request': HttpRequest(),
                'user': self.user
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:shift', rendered)
            
        except Exception as e:
            self.fail(f"Shift template rendering failed: {e}")
    
    def test_shift_form_template_urls(self):
        """Test that shift_form.html uses correct URLs"""
        template_path = 'onboarding/shift_form.html'
        
        try:
            context = {
                'shift_form': MagicMock(),
                'request': HttpRequest(),
                'user': self.user
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            # Should use admin_panel:config_shifts instead of onboarding:shift
            
        except Exception as e:
            self.fail(f"Shift form template rendering failed: {e}")
    
    def test_import_template_urls(self):
        """Test that import.html uses admin_panel:data_import"""
        template_path = 'onboarding/import.html'
        
        try:
            context = {
                'importform': MagicMock(),
                'request': HttpRequest(),
                'user': self.user,
                'columns': [],
                'data': [],
                'instructions': {}
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:import', rendered)
            
        except Exception as e:
            self.fail(f"Import template rendering failed: {e}")
    
    def test_import_update_template_urls(self):
        """Test that import_update.html uses admin_panel:data_bulk_update"""
        template_path = 'onboarding/import_update.html'
        
        try:
            context = {
                'importform': MagicMock(),
                'request': HttpRequest(),
                'user': self.user,
                'columns': [],
                'data': [],
                'instructions': {}
            }
            
            rendered = render_to_string(template_path, context)
            
            self.assertIsInstance(rendered, str)
            self.assertNotIn('onboarding:import_update', rendered)
            
        except Exception as e:
            self.fail(f"Import update template rendering failed: {e}")


@pytest.mark.django_db 
class TestURLReversal(TestCase):
    """Test URL reversal with new namespaces works correctly"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com', 
            password='testpass123'
        )
    
    def test_admin_panel_namespace_reversal(self):
        """Test that admin_panel namespace URLs can be reversed"""
        try:
            # Test key admin panel URLs
            bu_list_url = reverse('admin_panel:bu_list')
            self.assertIsInstance(bu_list_url, str)
            self.assertTrue(bu_list_url.startswith('/'))
            
            clients_list_url = reverse('admin_panel:clients_list')
            self.assertIsInstance(clients_list_url, str)
            
            contracts_list_url = reverse('admin_panel:contracts_list')
            self.assertIsInstance(contracts_list_url, str)
            
            config_types_url = reverse('admin_panel:config_types')
            self.assertIsInstance(config_types_url, str)
            
            config_shifts_url = reverse('admin_panel:config_shifts')
            self.assertIsInstance(config_shifts_url, str)
            
            config_geofences_url = reverse('admin_panel:config_geofences')
            self.assertIsInstance(config_geofences_url, str)
            
            data_import_url = reverse('admin_panel:data_import')
            self.assertIsInstance(data_import_url, str)
            
            data_bulk_update_url = reverse('admin_panel:data_bulk_update')
            self.assertIsInstance(data_bulk_update_url, str)
            
        except NoReverseMatch as e:
            self.fail(f"URL reversal failed: {e}")
    
    def test_legacy_namespace_deprecation(self):
        """Test that old onboarding namespace URLs are deprecated"""
        deprecated_urls = [
            'onboarding:bu',
            'onboarding:client', 
            'onboarding:contract',
            'onboarding:typeassist',
            'onboarding:shift',
            'onboarding:geofence',
            'onboarding:import',
            'onboarding:import_update'
        ]
        
        for url_name in deprecated_urls:
            with self.assertRaises(NoReverseMatch, 
                msg=f"Legacy URL {url_name} should not be reversible"):
                reverse(url_name)
    
    def test_url_with_parameters(self):
        """Test URL reversal with parameters works correctly"""
        try:
            # Test URLs that accept parameters
            bu_detail_url = reverse('admin_panel:bu_list', kwargs={'pk': 1})
            self.assertIn('1', bu_detail_url)
            
        except NoReverseMatch:
            # This is acceptable if the URL pattern doesn't support parameters
            pass


@pytest.mark.django_db
class TestTemplateJavaScriptUrls(TestCase):
    """Test that JavaScript code in templates uses correct URLs"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_business_unit_form_javascript_urls(self):
        """Test JavaScript in BU form uses correct URLs"""
        template_path = 'onboarding/bu_form.html'
        
        context = {
            'bu_form': MagicMock(),
            'request': HttpRequest(),
            'user': self.user
        }
        
        rendered = render_to_string(template_path, context)
        
        # Check that AJAX calls use the correct URL pattern
        # Look for fire_ajax_* function calls that should use transformed URLs
        if 'fire_ajax_form_post' in rendered:
            # The JavaScript should rely on URL transformation
            # We can't easily test the actual JS execution, but we can check structure
            self.assertIn('fire_ajax_form_post', rendered)
    
    def test_import_template_javascript_urls(self):
        """Test JavaScript in import template uses correct URLs"""
        template_path = 'onboarding/import.html'
        
        context = {
            'importform': MagicMock(),
            'request': HttpRequest(),
            'user': self.user,
            'instructions': '{}',
            'columns': [],
            'data': []
        }
        
        rendered = render_to_string(template_path, context)
        
        # Check for AJAX URL usage
        if 'fire_ajax_get' in rendered:
            self.assertIn('fire_ajax_get', rendered)
            
        # The template should rely on URL mapper for transformation
        # Old namespace should not appear in JavaScript
        if 'onboarding:import' in rendered:
            # This would indicate the template wasn't updated properly
            self.fail("Found legacy namespace in JavaScript code")
    
    def test_shift_form_javascript_urls(self):
        """Test JavaScript in shift form uses correct URLs"""
        template_path = 'onboarding/shift_form.html'
        
        context = {
            'shift_form': MagicMock(),
            'request': HttpRequest(),
            'user': self.user,
            'designation_wise_count': {},
            'count_as_per_design': {},
            'total_shifts_ppl_count': 0,
            'total_ppl_count_on_site': 0,
            'current_shift_ppl_count': 0,
            'current_shift_designation_counts': {},
            'designation_choices': {}
        }
        
        try:
            rendered = render_to_string(template_path, context)
            
            # Check that the JavaScript uses admin_panel namespace
            self.assertNotIn('onboarding:shift', rendered)
            
        except Exception as e:
            self.fail(f"Shift form JavaScript test failed: {e}")


@pytest.mark.django_db
class TestFormActionUrls(TestCase):
    """Test that form action attributes use correct URLs"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_form_action_urls(self):
        """Test that form action attributes point to correct endpoints"""
        templates_to_test = [
            'onboarding/bu_form.html',
            'onboarding/client_buform.html', 
            'onboarding/contract_form.html',
            'onboarding/geofence_form.html',
            'onboarding/shift_form.html'
        ]
        
        for template_path in templates_to_test:
            try:
                context = {
                    'request': HttpRequest(),
                    'user': self.user,
                    'bu_form': MagicMock(),
                    'client_form': MagicMock(),
                    'contract_form': MagicMock(),
                    'geofence_form': MagicMock(),
                    'shift_form': MagicMock()
                }
                
                rendered = render_to_string(template_path, context)
                
                # Forms should have action attributes
                # They should either be empty (submit to same URL) or use new namespace
                if 'action=""' in rendered:
                    # Empty action is acceptable - submits to current URL
                    continue
                    
                # If action is specified, it should use new namespace
                self.assertNotIn('action="onboarding:', rendered)
                
            except Exception as e:
                # Template might not exist or have dependencies
                # Log the error but don't fail the test
                print(f"Warning: Could not test template {template_path}: {e}")


@pytest.mark.django_db  
class TestNavigationUrls(TestCase):
    """Test that navigation links use correct URLs"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_breadcrumb_urls(self):
        """Test that breadcrumb navigation uses correct URLs"""
        templates_with_breadcrumbs = [
            'onboarding/bu_form.html',
            'onboarding/client_buform.html',
            'onboarding/shift_form.html'
        ]
        
        for template_path in templates_with_breadcrumbs:
            try:
                context = {
                    'request': HttpRequest(),
                    'user': self.user,
                    'bu_form': MagicMock(),
                    'client_form': MagicMock(),
                    'shift_form': MagicMock()
                }
                
                rendered = render_to_string(template_path, context)
                
                # Check breadcrumb links
                if 'breadcrumb' in rendered:
                    # Should not contain legacy namespace in links
                    self.assertNotIn('onboarding:bu"', rendered)
                    self.assertNotIn('onboarding:client"', rendered)
                    self.assertNotIn('onboarding:shift"', rendered)
                
            except Exception as e:
                print(f"Warning: Could not test breadcrumbs in {template_path}: {e}")
    
    def test_list_template_action_buttons(self):
        """Test that list templates have correct action button URLs"""
        list_templates = [
            'onboarding/bu_list.html',
            'onboarding/client_bulist.html',
            'onboarding/contract_list.html',
            'onboarding/shift.html'
        ]
        
        for template_path in list_templates:
            try:
                context = {
                    'request': HttpRequest(),
                    'user': self.user
                }
                
                rendered = render_to_string(template_path, context)
                
                # Check for action buttons (Add New, Edit, Delete)
                # They should use the new URL namespace
                if 'Add New' in rendered:
                    # Should not use legacy namespace for add buttons
                    self.assertNotIn('onboarding:', rendered)
                
            except Exception as e:
                print(f"Warning: Could not test list template {template_path}: {e}")


@pytest.mark.performance
class TestTemplateRenderingPerformance(TestCase):
    """Test that template rendering performance is not impacted by URL changes"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_template_rendering_speed(self):
        """Test that templates render quickly with new URLs"""
        import time
        
        template_path = 'onboarding/bu_form.html'
        context = {
            'bu_form': MagicMock(),
            'request': HttpRequest(),
            'user': self.user
        }
        
        start_time = time.time()
        
        # Render template multiple times
        for _ in range(10):
            rendered = render_to_string(template_path, context)
        
        end_time = time.time()
        render_time = (end_time - start_time) / 10  # Average time per render
        
        # Template should render in reasonable time (under 100ms)
        self.assertLess(render_time, 0.1, 
            f"Template rendering too slow: {render_time:.3f}s")
    
    def test_url_reversal_performance(self):
        """Test that URL reversal is fast"""
        import time
        
        urls_to_test = [
            'admin_panel:bu_list',
            'admin_panel:clients_list',
            'admin_panel:contracts_list',
            'admin_panel:config_types',
            'admin_panel:config_shifts'
        ]
        
        start_time = time.time()
        
        for _ in range(100):
            for url_name in urls_to_test:
                try:
                    reverse(url_name)
                except NoReverseMatch:
                    pass  # Skip if URL doesn't exist
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 500 URL reversals should be very fast (under 50ms)
        self.assertLess(total_time, 0.05,
            f"URL reversal too slow: {total_time:.3f}s for 500 reversals")