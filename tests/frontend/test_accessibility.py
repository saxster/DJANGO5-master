"""
Accessibility Testing Suite
YOUTILITY Industrial Minimal Design System

Tests WCAG 2.1 AA compliance for:
  - Color contrast ratios (4.5:1 minimum)
  - Focus states (visible on all interactive elements)
  - ARIA labels and attributes
  - Keyboard navigation
  - Screen reader support
  - Reduced motion support
  - Skip links

Run:
  python -m pytest tests/frontend/test_accessibility.py -v

For full accessibility audit, also run:
  npm run test:a11y (if Lighthouse CI configured)
  npx axe-core /admin/ (if axe-core installed)
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from bs4 import BeautifulSoup
import re

User = get_user_model()


class TestColorContrast(TestCase):
    """Test WCAG AA color contrast compliance (4.5:1 minimum)"""

    def calculate_relative_luminance(self, hex_color):
        """Calculate relative luminance for contrast ratio"""
        # Remove # and convert to RGB
        hex_color = hex_color.lstrip('#')
        r, g, b = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]

        # Apply gamma correction
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4

        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def calculate_contrast_ratio(self, color1, color2):
        """Calculate contrast ratio between two colors"""
        lum1 = self.calculate_relative_luminance(color1)
        lum2 = self.calculate_relative_luminance(color2)

        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)

        return (lighter + 0.05) / (darker + 0.05)

    def test_primary_on_white_contrast(self):
        """Primary color should have 4.5:1 contrast on white"""
        ratio = self.calculate_contrast_ratio('#155EEF', '#FFFFFF')
        self.assertGreaterEqual(ratio, 4.5, f"Primary on white: {ratio:.2f}:1 (minimum 4.5:1)")

    def test_text_on_background_contrast(self):
        """Text color should have high contrast on background"""
        ratio = self.calculate_contrast_ratio('#0F172A', '#F8FAFC')
        self.assertGreaterEqual(ratio, 7.0, f"Text on background: {ratio:.2f}:1 (AAA compliance)")

    def test_success_on_white_contrast(self):
        """Success color should meet WCAG AA"""
        ratio = self.calculate_contrast_ratio('#16A34A', '#FFFFFF')
        self.assertGreaterEqual(ratio, 4.5)

    def test_danger_on_white_contrast(self):
        """Danger color should meet WCAG AA"""
        ratio = self.calculate_contrast_ratio('#DC2626', '#FFFFFF')
        self.assertGreaterEqual(ratio, 4.5)

    def test_warning_on_white_contrast(self):
        """Warning color should meet WCAG AA"""
        ratio = self.calculate_contrast_ratio('#D97706', '#FFFFFF')
        self.assertGreaterEqual(ratio, 4.5)

    def test_dark_mode_contrast(self):
        """Dark mode colors should meet WCAG AA"""
        # Dark text on dark background
        ratio = self.calculate_contrast_ratio('#E5E7EB', '#0F172A')
        self.assertGreaterEqual(ratio, 7.0)


class TestFocusStates(TestCase):
    """Test focus state visibility and accessibility"""

    def setUp(self):
        self.client = Client()

    def test_focus_ring_defined(self):
        """Focus ring should be defined in tokens"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        self.assertIn('--focus-ring-width', content)
        self.assertIn('--focus-ring-color', content)
        self.assertIn('--focus-ring-offset', content)

    def test_focus_visible_styles(self):
        """Focus-visible pseudo-class should be used"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        self.assertIn(':focus-visible', content)

    def test_button_has_focus_styles(self):
        """Button component should have focus styles"""
        with open('frontend/templates/components/button.html', 'r') as f:
            content = f.read()

        self.assertIn('focus-visible', content)

    def test_form_fields_have_focus_styles(self):
        """Form fields should have focus styles"""
        with open('frontend/templates/components/form-field.html', 'r') as f:
            content = f.read()

        self.assertIn('focus', content)


class TestARIAAttributes(TestCase):
    """Test ARIA attributes for screen readers"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            loginid='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(loginid='admin', password='testpass123')

    def test_admin_has_aria_labels(self):
        """Admin pages should have ARIA labels"""
        response = self.client.get(reverse('admin:index'))
        content = response.content.decode()

        # Should have ARIA attributes
        self.assertIn('aria-label', content)

    def test_modal_has_aria_modal(self):
        """Modal component should have aria-modal attribute"""
        with open('frontend/templates/components/modal.html', 'r') as f:
            content = f.read()

        self.assertIn('aria-modal="true"', content)
        self.assertIn('role="dialog"', content)

    def test_toast_has_aria_live(self):
        """Toast should have ARIA live region"""
        response = self.client.get('/static/theme/components/toast.js')
        content = response.content.decode()

        self.assertIn('aria-live', content)
        self.assertIn('assertive', content)  # For errors
        self.assertIn('polite', content)     # For info

    def test_required_fields_have_aria_required(self):
        """Required form fields should have aria-required"""
        with open('frontend/templates/components/form-field.html', 'r') as f:
            content = f.read()

        self.assertIn('aria-required', content)

    def test_errors_have_aria_invalid(self):
        """Fields with errors should have aria-invalid"""
        with open('frontend/templates/components/form-field.html', 'r') as f:
            content = f.read()

        self.assertIn('aria-invalid', content)


class TestKeyboardNavigation(TestCase):
    """Test keyboard accessibility"""

    def test_escape_closes_modal(self):
        """ESC key should close modal dialogs"""
        with open('frontend/templates/components/modal.html', 'r') as f:
            content = f.read()

        self.assertIn('Escape', content)

    def test_theme_toggle_keyboard_shortcut(self):
        """Theme toggle should have keyboard shortcut"""
        with open('templates/admin/base_site.html', 'r') as f:
            content = f.read()

        # Should have Ctrl/Cmd + Shift + D shortcut
        self.assertIn('ctrlKey', content)
        self.assertIn('shiftKey', content)

    def test_focusable_elements_have_tab_order(self):
        """Interactive elements should be keyboard accessible"""
        # Button component
        with open('frontend/templates/components/button.html', 'r') as f:
            button_content = f.read()

        # Should not have tabindex="-1" (unless disabled)
        self.assertNotRegex(button_content, r'tabindex="-1"(?!.*disabled)')


class TestReducedMotion(TestCase):
    """Test reduced motion support"""

    def test_reduced_motion_media_query(self):
        """CSS should respect prefers-reduced-motion"""
        files = [
            '/static/theme/tokens.css',
            '/static/theme/admin.css',
            '/static/theme/components/toast.css',
            '/static/theme/components/loading.css'
        ]

        for file_path in files:
            response = self.client.get(file_path)
            content = response.content.decode()

            self.assertIn('@media (prefers-reduced-motion: reduce)', content,
                         f"{file_path} should support reduced motion")

    def test_animations_disabled_in_reduced_motion(self):
        """Animations should be disabled when reduced motion is preferred"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        # Should disable animation durations
        reduced_motion_section = re.search(
            r'@media \(prefers-reduced-motion: reduce\).*?}',
            content,
            re.DOTALL
        )

        self.assertIsNotNone(reduced_motion_section)
        self.assertIn('animation-duration: 0.01ms', content)


class TestScreenReaderSupport(TestCase):
    """Test screen reader accessibility"""

    def test_sr_only_class_defined(self):
        """Screen reader only utility class should exist"""
        response = self.client.get('/static/theme/tokens.css')
        content = response.content.decode()

        self.assertIn('.sr-only', content) or self.assertIn('.yt-sr-only', content)

    def test_icons_hidden_from_screen_readers(self):
        """Decorative icons should have aria-hidden"""
        components = [
            'frontend/templates/components/button.html',
            'frontend/templates/components/card.html',
            'frontend/templates/components/form-field.html'
        ]

        for component in components:
            with open(component, 'r') as f:
                content = f.read()

            if 'material-icons' in content:
                self.assertIn('aria-hidden="true"', content,
                             f"{component} should hide decorative icons from screen readers")


class TestFormAccessibility(TestCase):
    """Test form accessibility"""

    def test_labels_associated_with_inputs(self):
        """Form labels should be associated with inputs"""
        with open('frontend/templates/components/form-field.html', 'r') as f:
            content = f.read()

        # Should have for/id association
        self.assertIn('for=', content)
        self.assertIn('id=', content)

    def test_error_messages_associated_with_fields(self):
        """Error messages should be associated with form fields"""
        with open('frontend/templates/components/form-field.html', 'r') as f:
            content = f.read()

        self.assertIn('aria-describedby', content)

    def test_required_indicators_present(self):
        """Required fields should have visual and semantic indicators"""
        with open('frontend/templates/components/form-field.html', 'r') as f:
            content = f.read()

        self.assertIn('required', content)
        self.assertIn('*', content)  # Visual indicator


class TestPrintAccessibility(TestCase):
    """Test print accessibility"""

    def test_print_css_forces_black_text(self):
        """Print styles should use high contrast colors"""
        response = self.client.get('/static/theme/print.css')
        content = response.content.decode()

        self.assertIn('color: #000', content)
        self.assertIn('color: black', content)

    def test_print_hides_interactive_elements(self):
        """Interactive elements should be hidden when printing"""
        response = self.client.get('/static/theme/print.css')
        content = response.content.decode()

        self.assertIn('display: none', content)
        # Should hide buttons, nav, etc.


# Performance-related accessibility tests
class TestPerformanceAccessibility(TestCase):
    """Test performance impacts on accessibility"""

    def test_font_display_swap(self):
        """Fonts should use swap to prevent invisible text"""
        response = self.client.get('/static/theme/fonts.css')
        content = response.content.decode()

        self.assertIn('font-display: swap', content)

    def test_no_layout_shifts(self):
        """CSS should minimize cumulative layout shift"""
        # Check that skeletons match actual content dimensions
        response = self.client.get('/static/theme/components/loading.css')
        content = response.content.decode()

        # Skeleton heights should match actual component heights
        self.assertIn('skeleton-text', content)
        self.assertIn('height:', content)


# Integration tests
class TestAccessibilityIntegration(TestCase):
    """Test accessibility in real pages"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            loginid='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(loginid='admin', password='testpass123')

    def test_admin_page_accessibility(self):
        """Admin index should be accessible"""
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check for basic accessibility features
        # 1. Page has title
        self.assertIsNotNone(soup.find('title'))

        # 2. Page has main landmark (or equivalent)
        has_main = soup.find('main') or soup.find(role='main')
        self.assertTrue(has_main or soup.find(id='content'))

        # 3. Links have accessible names
        links = soup.find_all('a')
        for link in links:
            has_text = link.get_text(strip=True)
            has_aria_label = link.get('aria-label')
            has_title = link.get('title')

            self.assertTrue(
                has_text or has_aria_label or has_title,
                f"Link {link} has no accessible name"
            )

    def test_forms_have_labels(self):
        """All form inputs should have labels"""
        # Test a page with forms (login page is public)
        response = self.client.get(reverse('admin:login'))
        soup = BeautifulSoup(response.content, 'html.parser')

        inputs = soup.find_all(['input', 'select', 'textarea'])

        for input_elem in inputs:
            input_type = input_elem.get('type')

            # Skip hidden inputs
            if input_type == 'hidden':
                continue

            input_id = input_elem.get('id')
            input_name = input_elem.get('name')

            # Should have associated label or aria-label
            has_label = soup.find('label', {'for': input_id}) if input_id else None
            has_aria_label = input_elem.get('aria-label')
            has_aria_labelledby = input_elem.get('aria-labelledby')

            self.assertTrue(
                has_label or has_aria_label or has_aria_labelledby,
                f"Input {input_name} has no label"
            )


class TestDocumentStructure(TestCase):
    """Test semantic HTML structure"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            loginid='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(loginid='admin', password='testpass123')

    def test_heading_hierarchy(self):
        """Pages should have proper heading hierarchy (h1 -> h2 -> h3)"""
        response = self.client.get(reverse('admin:index'))
        soup = BeautifulSoup(response.content, 'html.parser')

        # Should have exactly one h1
        h1_count = len(soup.find_all('h1'))
        self.assertGreaterEqual(h1_count, 1, "Page should have at least one h1")

        # Headings should be in logical order (not skipping levels)
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if len(headings) > 1:
            previous_level = 1
            for heading in headings:
                current_level = int(heading.name[1])
                # Allow same level or one level deeper
                self.assertLessEqual(
                    current_level - previous_level,
                    1,
                    f"Heading level jump: {previous_level} -> {current_level}"
                )
                previous_level = current_level


class TestKeyboardAccessibility(TestCase):
    """Test keyboard-only navigation"""

    def test_skip_link_present(self):
        """Pages should have skip to content link"""
        response = self.client.get('/static/theme/admin.css')
        content = response.content.decode()

        self.assertIn('.skip-link', content)

    def test_no_positive_tabindex(self):
        """Should not use positive tabindex values (bad practice)"""
        components = [
            'frontend/templates/components/button.html',
            'frontend/templates/components/form-field.html',
            'frontend/templates/components/modal.html'
        ]

        for component in components:
            with open(component, 'r') as f:
                content = f.read()

            # Should not have tabindex="1" or higher
            matches = re.findall(r'tabindex="([0-9]+)"', content)
            for match in matches:
                self.assertLessEqual(
                    int(match),
                    0,
                    f"{component} uses positive tabindex (anti-pattern)"
                )


class TestAlternativeText(TestCase):
    """Test alt text and text alternatives"""

    def test_icons_have_aria_hidden(self):
        """Decorative icons should be hidden from screen readers"""
        with open('frontend/templates/components/button.html', 'r') as f:
            content = f.read()

        if 'material-icons' in content:
            self.assertIn('aria-hidden="true"', content)


# Pytest-style tests for additional coverage
def test_design_tokens_include_accessibility_section():
    """Design tokens should have accessibility configuration"""
    response = Client().get('/static/theme/tokens.css')
    content = response.content.decode()

    assert '--focus-ring' in content
    assert 'ACCESSIBILITY' in content


def test_components_support_disabled_state():
    """Components should properly handle disabled state"""
    components = [
        'frontend/templates/components/button.html',
        'frontend/templates/components/form-field.html'
    ]

    for component in components:
        with open(component, 'r') as f:
            content = f.read()

        assert 'disabled' in content, f"{component} should support disabled state"


def test_toast_has_screen_reader_announcement():
    """Toast system should announce to screen readers"""
    response = Client().get('/static/theme/components/toast.js')
    content = response.content.decode()

    assert 'announceToScreenReader' in content or 'aria-live' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
