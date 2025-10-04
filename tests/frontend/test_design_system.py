"""
Design System Integration Tests
YOUTILITY Industrial Minimal Design System

Tests:
  - Theme file loading
  - Design token availability
  - Dark mode toggle functionality
  - Component rendering
  - Accessibility compliance
  - Print styles
  - Mobile token export

Run:
  python -m pytest tests/frontend/test_design_system.py -v
"""

import pytest
import json
import re
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from pathlib import Path
from bs4 import BeautifulSoup

User = get_user_model()


class TestDesignSystemFoundation(TestCase):
    """Test design system foundation (tokens, fonts, theme toggle)"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            loginid='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(loginid='admin', password='testpass123')

    def test_tokens_css_exists(self):
        """Design tokens CSS file should exist and be loadable"""
        response = self.client.get('/static/theme/tokens.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for key design tokens
        self.assertIn('--color-primary-600', content)
        self.assertIn('#155EEF', content)
        self.assertIn('--font-sans', content)
        self.assertIn('--space-4', content)

    def test_fonts_css_exists(self):
        """Font declarations CSS should exist"""
        response = self.client.get('/static/theme/fonts.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for font families
        self.assertIn("font-family: 'Inter'", content)
        self.assertIn("font-family: 'JetBrains Mono'", content)
        self.assertIn('font-display: swap', content)

    def test_theme_toggle_js_exists(self):
        """Theme toggle JavaScript should exist"""
        response = self.client.get('/static/theme/theme-toggle.js')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for theme manager
        self.assertIn('ThemeManager', content)
        self.assertIn('window.themeManager', content)
        self.assertIn('localStorage', content)

    def test_dark_mode_tokens(self):
        """Dark mode tokens should be defined"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        # Check for dark mode class
        self.assertIn('.dark {', content)
        self.assertIn('--bg-app: #0B1220', content)
        self.assertIn('--bg-surface: #0F172A', content)

        # Check for media query
        self.assertIn('@media (prefers-color-scheme: dark)', content)

    def test_accessibility_tokens(self):
        """Accessibility tokens should be defined"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        # Focus ring
        self.assertIn('--focus-ring-width', content)
        self.assertIn('--focus-ring-color', content)

        # Reduced motion
        self.assertIn('@media (prefers-reduced-motion: reduce)', content)

        # High contrast
        self.assertIn('@media (prefers-contrast: high)', content)


class TestDjangoAdminTheming(TestCase):
    """Test Django admin theme integration"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            loginid='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(loginid='admin', password='testpass123')

    def test_admin_base_site_template_exists(self):
        """Admin base_site.html template should exist"""
        template_path = Path('templates/admin/base_site.html')
        self.assertTrue(template_path.exists())

    def test_admin_loads_theme_css(self):
        """Admin pages should load theme CSS files"""
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()

        # Check for theme CSS
        self.assertIn('theme/fonts.css', content)
        self.assertIn('theme/tokens.css', content)
        self.assertIn('theme/admin.css', content)

    def test_admin_has_dark_mode_toggle(self):
        """Admin should have dark mode toggle button"""
        response = self.client.get(reverse('admin:index'))
        content = response.content.decode()

        self.assertIn('data-theme-toggle', content)
        self.assertIn('theme-toggle', content)

    def test_admin_css_exists(self):
        """Admin CSS file should exist and contain styles"""
        response = self.client.get('/static/theme/admin.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for admin-specific styles
        self.assertIn('#header', content)
        self.assertIn('.admin-brand', content)
        self.assertIn('.theme-toggle-button', content)

    def test_admin_branding_customized(self):
        """Admin should have custom YOUTILITY branding"""
        response = self.client.get(reverse('admin:index'))
        content = response.content.decode()
        soup = BeautifulSoup(content, 'html.parser')

        # Check for custom branding
        branding = soup.find(id='branding') or soup.find(class_='admin-brand')
        self.assertIsNotNone(branding)


class TestPrintStyles(TestCase):
    """Test print optimization CSS"""

    def test_print_css_exists(self):
        """Print CSS file should exist"""
        response = self.client.get('/static/theme/print.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for print-specific styles
        self.assertIn('@media print', content)
        self.assertIn('.no-print', content)
        self.assertIn('.print-only', content)

    def test_print_qr_code_support(self):
        """QR codes should be preserved at correct size for printing"""
        response = self.client.get('/static/theme/print.css')
        content = response.content.decode()

        self.assertIn('.qr-code', content)
        self.assertIn('3cm', content)  # QR code scanning size

    def test_print_signature_lines(self):
        """Signature lines should be available for compliance docs"""
        response = self.client.get('/static/theme/print.css')
        content = response.content.decode()

        self.assertIn('.signature-line', content)
        self.assertIn('.signature-block', content)


class TestMobileTokenExport(TestCase):
    """Test design token export for Kotlin/Android"""

    def test_design_tokens_json_exists(self):
        """design-tokens.json should exist"""
        tokens_path = Path('design-tokens.json')
        self.assertTrue(tokens_path.exists())

    def test_design_tokens_valid_json(self):
        """design-tokens.json should be valid JSON"""
        with open('design-tokens.json', 'r') as f:
            tokens = json.load(f)

        self.assertIsInstance(tokens, dict)
        self.assertIn('color', tokens)
        self.assertIn('spacing', tokens)
        self.assertIn('typography', tokens)

    def test_design_tokens_color_values(self):
        """Design tokens should contain correct color values"""
        with open('design-tokens.json', 'r') as f:
            tokens = json.load(f)

        # Check primary color
        primary_600 = tokens['color']['primary']['600']['value']
        self.assertEqual(primary_600, '#155EEF')

        # Check neutral scale
        neutral_900 = tokens['color']['neutral']['900']['value']
        self.assertEqual(neutral_900, '#0F172A')

    def test_design_tokens_spacing_values(self):
        """Spacing tokens should use 8pt grid"""
        with open('design-tokens.json', 'r') as f:
            tokens = json.load(f)

        # Check 8pt grid
        self.assertEqual(tokens['spacing']['1']['value'], '4px')
        self.assertEqual(tokens['spacing']['2']['value'], '8px')
        self.assertEqual(tokens['spacing']['4']['value'], '16px')
        self.assertEqual(tokens['spacing']['8']['value'], '32px')

    def test_design_tokens_wcag_annotations(self):
        """Tokens should have WCAG compliance annotations"""
        with open('design-tokens.json', 'r') as f:
            tokens = json.load(f)

        primary_600 = tokens['color']['primary']['600']

        # Check for WCAG annotation
        self.assertIn('$wcagAA', primary_600)
        self.assertTrue(primary_600['$wcagAA'])
        self.assertIn('$contrastRatio', primary_600)


class TestComponents(TestCase):
    """Test reusable component partials"""

    def test_button_component_exists(self):
        """Button component template should exist"""
        template_path = Path('frontend/templates/components/button.html')
        self.assertTrue(template_path.exists())

    def test_form_field_component_exists(self):
        """Form field component template should exist"""
        template_path = Path('frontend/templates/components/form-field.html')
        self.assertTrue(template_path.exists())

    def test_card_component_exists(self):
        """Card component template should exist"""
        template_path = Path('frontend/templates/components/card.html')
        self.assertTrue(template_path.exists())

    def test_badge_component_exists(self):
        """Badge component template should exist"""
        template_path = Path('frontend/templates/components/badge.html')
        self.assertTrue(template_path.exists())

    def test_empty_state_component_exists(self):
        """Empty state component template should exist"""
        template_path = Path('frontend/templates/components/empty-state.html')
        self.assertTrue(template_path.exists())

    def test_modal_component_exists(self):
        """Modal component template should exist"""
        template_path = Path('frontend/templates/components/modal.html')
        self.assertTrue(template_path.exists())


class TestToastNotificationSystem(TestCase):
    """Test toast notification system"""

    def test_toast_js_exists(self):
        """Toast JavaScript file should exist"""
        response = self.client.get('/static/theme/components/toast.js')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for ToastManager class
        self.assertIn('ToastManager', content)
        self.assertIn('window.toast', content)

    def test_toast_css_exists(self):
        """Toast CSS file should exist"""
        response = self.client.get('/static/theme/components/toast.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for toast styles
        self.assertIn('.yt-toast', content)
        self.assertIn('.yt-toast--success', content)
        self.assertIn('.yt-toast--error', content)

    def test_toast_api_methods(self):
        """Toast API should have success, error, warning, info methods"""
        response = self.client.get('/static/theme/components/toast.js')
        content = response.content.decode()

        self.assertIn('success(message, options', content)
        self.assertIn('error(message, options', content)
        self.assertIn('warning(message, options', content)
        self.assertIn('info(message, options', content)


class TestSwaggerUITheming(TestCase):
    """Test Swagger UI theme integration"""

    def test_swagger_template_exists(self):
        """Swagger UI template override should exist"""
        template_path = Path('templates/drf_spectacular/swagger_ui.html')
        self.assertTrue(template_path.exists())

    def test_swagger_css_exists(self):
        """Swagger CSS file should exist"""
        response = self.client.get('/static/theme/swagger.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for swagger-specific styles
        self.assertIn('.swagger-header', content)
        self.assertIn('.swagger-ui', content)

    def test_swagger_uses_design_tokens(self):
        """Swagger CSS should use design tokens"""
        response = self.client.get('/static/theme/swagger.css')
        content = response.content.decode()

        # Should reference CSS custom properties
        self.assertIn('var(--', content)
        self.assertIn('var(--color-primary-600)', content)


class TestResponsiveness(TestCase):
    """Test responsive design"""

    def test_mobile_breakpoints_defined(self):
        """CSS should define mobile breakpoints"""
        files_to_check = [
            '/static/theme/tokens.css',
            '/static/theme/admin.css',
            '/static/theme/swagger.css'
        ]

        for file_path in files_to_check:
            response = self.client.get(file_path)
            content = response.content.decode()

            # Should have media queries for mobile
            self.assertRegex(content, r'@media.*max-width.*640px|768px')

    def test_touch_targets_minimum_size(self):
        """Interactive elements should meet 40px minimum touch target"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        self.assertIn('--hit-target-min: 40px', content)


class TestPerformance(TestCase):
    """Test performance optimizations"""

    def test_font_preload_hints(self):
        """Admin template should preload critical fonts"""
        template_path = Path('templates/admin/base_site.html')
        with open(template_path, 'r') as f:
            content = f.read()

        self.assertIn('rel="preload"', content)
        self.assertIn('as="font"', content)
        self.assertIn('crossorigin', content)

    def test_css_uses_custom_properties(self):
        """CSS should use custom properties (not hardcoded values)"""
        files = [
            '/static/theme/admin.css',
            '/static/theme/swagger.css',
        ]

        for file_path in files:
            response = self.client.get(file_path)
            content = response.content.decode()

            # Should use CSS variables
            var_count = content.count('var(--')
            self.assertGreater(var_count, 20, f"{file_path} should use CSS variables extensively")


class TestDarkMode(TestCase):
    """Test dark mode implementation"""

    def test_dark_mode_class_defined(self):
        """Dark mode class should be defined in tokens.css"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        self.assertIn('.dark {', content)

    def test_system_preference_support(self):
        """Should support prefers-color-scheme media query"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        self.assertIn('@media (prefers-color-scheme: dark)', content)

    def test_theme_toggle_api(self):
        """Theme toggle should expose public API"""
        response = self.client.get('/static/theme/theme-toggle.js')
        content = response.content.decode()

        self.assertIn('window.themeManager', content)
        self.assertIn('.toggle', content)
        self.assertIn('.setTheme', content)
        self.assertIn('.getTheme', content)


class TestComponentFiles(TestCase):
    """Test component file existence and structure"""

    @pytest.mark.parametrize("component", [
        'button.html',
        'form-field.html',
        'card.html',
        'badge.html',
        'empty-state.html',
        'modal.html'
    ])
    def test_component_template_exists(self, component):
        """Component templates should exist"""
        template_path = Path(f'frontend/templates/components/{component}')
        assert template_path.exists(), f"Component {component} template not found"

    def test_loading_css_exists(self):
        """Loading states CSS should exist"""
        response = self.client.get('/static/theme/components/loading.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        self.assertIn('.skeleton', content)
        self.assertIn('.spinner', content)
        self.assertIn('@keyframes skeleton-pulse', content)

    def test_table_css_exists(self):
        """Table component CSS should exist"""
        response = self.client.get('/static/theme/components/table.css')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        self.assertIn('.yt-table', content)
        self.assertIn('.sortable', content)
        self.assertIn('.yt-table--zebra', content)
        self.assertIn('.yt-table--dense', content)


class TestDocumentation(TestCase):
    """Test documentation completeness"""

    def test_font_download_guide_exists(self):
        """Font download guide should exist"""
        guide_path = Path('FONT_DOWNLOAD_GUIDE.md')
        self.assertTrue(guide_path.exists())

    def test_kotlin_code_generation_guide_exists(self):
        """Kotlin code generation guide should exist"""
        guide_path = Path('KOTLIN_CODE_GENERATION.md')
        self.assertTrue(guide_path.exists())

    def test_implementation_status_exists(self):
        """Implementation status document should exist"""
        status_path = Path('DESIGN_SYSTEM_IMPLEMENTATION_STATUS.md')
        self.assertTrue(status_path.exists())

    def test_progress_report_exists(self):
        """Progress report should exist"""
        report_path = Path('IMPLEMENTATION_PROGRESS_REPORT.md')
        self.assertTrue(report_path.exists())


# Pytest fixtures for additional testing
@pytest.fixture
def admin_page(client, admin_user):
    """Fixture for testing admin pages"""
    client.force_login(admin_user)
    return client.get(reverse('admin:index'))


@pytest.fixture
def design_tokens():
    """Fixture for loading design tokens"""
    with open('design-tokens.json', 'r') as f:
        return json.load(f)


# Additional pytest tests
def test_all_colors_have_dark_variants(design_tokens):
    """All semantic colors should have dark mode variants"""
    semantic = design_tokens.get('semantic', {})

    for category in ['background', 'text', 'border']:
        if category in semantic:
            for token_name, token_value in semantic[category].items():
                assert 'light' in token_value, f"{category}.{token_name} missing light variant"
                assert 'dark' in token_value, f"{category}.{token_name} missing dark variant"


def test_spacing_follows_8pt_grid(design_tokens):
    """Spacing values should follow 8pt grid system"""
    spacing = design_tokens.get('spacing', {})

    for key, token in spacing.items():
        value = token.get('value')
        if value and value != '0':
            # Extract numeric value
            numeric_value = int(re.search(r'\d+', value).group())

            # Should be multiple of 4
            assert numeric_value % 4 == 0, f"Spacing {key} ({value}) doesn't follow 8pt grid"


def test_wcag_compliant_colors(design_tokens):
    """Primary colors should have WCAG AA annotations"""
    colors_to_check = [
        ('color', 'primary', '600'),
        ('color', 'success', '600'),
        ('color', 'danger', '600'),
    ]

    for path in colors_to_check:
        token = design_tokens
        for key in path:
            token = token[key]

        # Should have WCAG annotation
        assert '$wcagAA' in token or '$wcagAAA' in token, f"{'.'.join(path)} missing WCAG annotation"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
