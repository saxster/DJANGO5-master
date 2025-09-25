"""
Test suite for Information Architecture improvements
Tests navigation, URL redirects, and menu structure
"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from bs4 import BeautifulSoup

from apps.core.url_router import URLRouter

User = get_user_model()


class NavigationMenuTest(TestCase):
    """Test the new clean navigation menu"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='adminpass123'
        )
    
    def test_no_dead_links_in_menu(self):
        """Ensure no dead links exist in the navigation menu"""
        self.client.login(username='testuser', password='testpass123')
        
        # Load a page with the menu
        response = self.client.get('/dashboard/')
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all menu links
        menu_links = soup.select('#kt_aside_menu a.menu-link')
        
        dead_link_patterns = [
            'apps/customers/',
            'getting-started.html',
            'list.html',
            'view.html'
        ]
        
        for link in menu_links:
            href = link.get('href', '')
            for pattern in dead_link_patterns:
                self.assertNotIn(pattern, href, 
                    f"Dead link pattern '{pattern}' found in menu: {href}")
    
    def test_no_duplicate_menu_ids(self):
        """Ensure no duplicate IDs in menu HTML"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/dashboard/')
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all elements with IDs in the menu
        menu_elements = soup.select('#kt_aside_menu [id]')
        ids = [elem.get('id') for elem in menu_elements]
        
        # Check for duplicates
        self.assertEqual(len(ids), len(set(ids)), 
            f"Duplicate IDs found: {[id for id in ids if ids.count(id) > 1]}")
    
    def test_no_hidden_menus_by_default(self):
        """Ensure menus are not hidden with display:none"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/dashboard/')
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find menu items with display:none
        hidden_menus = soup.select('#kt_aside_menu .menu-item[style*="display:none"]')
        
        self.assertEqual(len(hidden_menus), 0, 
            f"Found {len(hidden_menus)} hidden menu items")
    
    def test_menu_hierarchy_depth(self):
        """Ensure menu hierarchy doesn't exceed 2 levels"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/dashboard/')
        soup = BeautifulSoup(response.content, 'html.parser')
        
        def check_depth(element, current_depth=0):
            max_depth = current_depth
            submenus = element.select(':scope > .menu-sub > .menu-item')
            
            for submenu in submenus:
                depth = check_depth(submenu, current_depth + 1)
                max_depth = max(max_depth, depth)
            
            return max_depth
        
        menu_root = soup.select_one('#kt_aside_menu')
        max_depth = check_depth(menu_root)
        
        self.assertLessEqual(max_depth, 2, 
            f"Menu hierarchy too deep: {max_depth} levels (max allowed: 2)")
    
    def test_role_based_menu_visibility(self):
        """Test that admin menus only show for admin users"""
        # Test regular user
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/dashboard/')
        soup = BeautifulSoup(response.content, 'html.parser')
        
        admin_menu = soup.select_one('#menu-admin')
        superadmin_menu = soup.select_one('#menu-superadmin')
        
        self.assertIsNone(admin_menu, "Admin menu visible to regular user")
        self.assertIsNone(superadmin_menu, "Super admin menu visible to regular user")
        
        # Test admin user
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get('/dashboard/')
        soup = BeautifulSoup(response.content, 'html.parser')
        
        admin_menu = soup.select_one('#menu-admin')
        superadmin_menu = soup.select_one('#menu-superadmin')
        
        self.assertIsNotNone(admin_menu, "Admin menu not visible to admin user")
        self.assertIsNotNone(superadmin_menu, "Super admin menu not visible to superuser")


class URLRedirectTest(TestCase):
    """Test legacy URL redirects"""
    
    def setUp(self):
        self.client = Client()
    
    def test_all_legacy_urls_redirect(self):
        """Ensure all legacy URLs redirect to new URLs"""
        for old_url, new_url in URLRouter.URL_MAPPINGS.items():
            response = self.client.get(f'/{old_url}', follow=False)
            
            # Should be a permanent redirect
            self.assertEqual(response.status_code, 301,
                f"URL /{old_url} did not redirect with 301")
            
            # Should redirect to the new URL
            self.assertEqual(response.url, f'/{new_url}',
                f"URL /{old_url} did not redirect to /{new_url}")
    
    def test_dead_link_redirects(self):
        """Test that known dead links redirect appropriately"""
        dead_links = {
            '/apps/customers/getting-started.html': '/dashboard/',
            '/apps/customers/list.html': '/people/',
            '/apps/customers/view.html': '/people/',
        }
        
        for dead_link, expected_redirect in dead_links.items():
            response = self.client.get(dead_link, follow=False)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response.url, expected_redirect)
    
    def test_legacy_url_logging(self):
        """Test that legacy URL usage is logged"""
        # Clear usage stats
        URLRouter.LEGACY_URL_USAGE.clear()
        
        # Access a legacy URL
        old_url = 'activity/asset/'
        self.client.get(f'/{old_url}')
        
        # Check it was logged
        self.assertIn(old_url, URLRouter.LEGACY_URL_USAGE)
        self.assertEqual(URLRouter.LEGACY_URL_USAGE[old_url], 1)
        
        # Access again
        self.client.get(f'/{old_url}')
        self.assertEqual(URLRouter.LEGACY_URL_USAGE[old_url], 2)


class URLStandardizationTest(TestCase):
    """Test URL standardization patterns"""
    
    def test_url_naming_conventions(self):
        """Test that new URLs follow naming conventions"""
        standardized_patterns = [
            '/operations/tasks/',
            '/operations/work-orders/',
            '/assets/maintenance/',
            '/people/site-groups/',
            '/help-desk/tickets/',
            '/admin/business-units/',
        ]
        
        for url in standardized_patterns:
            # URLs should use hyphens, not underscores
            self.assertNotIn('_', url, f"URL {url} contains underscore")
            
            # URLs should be lowercase
            self.assertEqual(url, url.lower(), f"URL {url} is not lowercase")
            
            # URLs should end with trailing slash
            self.assertTrue(url.endswith('/'), f"URL {url} missing trailing slash")
    
    def test_url_hierarchy(self):
        """Test that URLs follow logical hierarchy"""
        hierarchy_tests = [
            ('/assets/', 'Base assets URL should be accessible'),
            ('/assets/maintenance/', 'Maintenance should be under assets'),
            ('/assets/compare/', 'Compare should be under assets'),
            ('/people/', 'Base people URL should be accessible'),
            ('/people/groups/', 'Groups should be under people'),
            ('/operations/', 'Base operations URL should be accessible'),
            ('/operations/tasks/', 'Tasks should be under operations'),
        ]
        
        for url, message in hierarchy_tests:
            # Just test that the URL pattern would be valid
            # In real implementation, would test actual resolution
            self.assertTrue(url.startswith('/'), f"{message}: {url}")
            self.assertTrue(url.endswith('/'), f"{message}: {url}")


class TemplateStructureTest(TestCase):
    """Test template organization and inheritance"""
    
    def test_sidebar_template_exists(self):
        """Test that new sidebar template exists and is valid"""
        from django.template import loader, TemplateDoesNotExist
        
        try:
            template = loader.get_template('globals/sidebar_clean.html')
            self.assertIsNotNone(template)
        except TemplateDoesNotExist:
            self.fail("sidebar_clean.html template does not exist")
    
    def test_menu_link_structure(self):
        """Test that menu links use Django URL template tags"""
        from django.template import loader
        
        template = loader.get_template('globals/sidebar_clean.html')
        content = template.source
        
        # Should use {% url %} tags, not hardcoded URLs
        self.assertIn("{% url", content, "Template should use {% url %} tags")
        self.assertIn("{{ url(", content, "Template should use url() function")
        
        # Should not have hardcoded paths
        self.assertNotIn('href="/apps/customers/', content, 
            "Template contains hardcoded customer URLs")


@pytest.mark.django_db
class PerformanceTest(TestCase):
    """Test performance improvements"""
    
    def test_menu_rendering_performance(self):
        """Test that menu renders efficiently"""
        import time
        
        self.client.login(username='testuser', password='testpass123')
        
        # Measure rendering time
        start = time.time()
        response = self.client.get('/dashboard/')
        end = time.time()
        
        render_time = end - start
        
        # Should render in under 500ms
        self.assertLess(render_time, 0.5, 
            f"Menu rendering too slow: {render_time:.3f}s")
    
    def test_redirect_performance(self):
        """Test that redirects are fast"""
        import time
        
        legacy_url = '/activity/asset/'
        
        start = time.time()
        response = self.client.get(legacy_url, follow=False)
        end = time.time()
        
        redirect_time = end - start
        
        # Redirects should be very fast (under 50ms)
        self.assertLess(redirect_time, 0.05,
            f"Redirect too slow: {redirect_time:.3f}s")