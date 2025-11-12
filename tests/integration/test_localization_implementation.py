#!/usr/bin/env python3
"""
Localization Implementation Validation Script

Validates the comprehensive localization implementation across settings,
templates, and translation assets.

Usage: pytest tests/integration/test_localization_implementation.py
"""

import os
import sys
import json
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings_test')

try:
    import django
    django.setup()
except ImportError as e:
    print(f"❌ Django import failed: {e}")
    sys.exit(1)

from django.conf import settings
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import translation
from django.template.loader import render_to_string
from django.http import HttpRequest


class LocalizationValidator:
    """Comprehensive localization validation"""

    def __init__(self):
        self.results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }

    def log_test(self, test_name, passed, message="", details=None):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}: {message}")

        self.results['tests'].append({
            'name': test_name,
            'passed': passed,
            'message': message,
            'details': details or {}
        })

        if passed:
            self.results['passed'] += 1
        else:
            self.results['failed'] += 1

    def test_django_settings(self):
        """Test Django i18n/l10n settings"""
        print("\n🔧 Testing Django Settings...")

        # Test USE_I18N
        use_i18n = getattr(settings, 'USE_I18N', False)
        self.log_test(
            "USE_I18N enabled",
            use_i18n,
            f"USE_I18N = {use_i18n}"
        )

        # Test USE_L10N
        use_l10n = getattr(settings, 'USE_L10N', False)
        self.log_test(
            "USE_L10N enabled",
            use_l10n,
            f"USE_L10N = {use_l10n}"
        )

        # Test LANGUAGES
        languages = getattr(settings, 'LANGUAGES', [])
        has_languages = len(languages) > 1
        self.log_test(
            "Multiple languages configured",
            has_languages,
            f"Found {len(languages)} languages: {[lang[0] for lang in languages]}"
        )

        # Test LOCALE_PATHS
        locale_paths = getattr(settings, 'LOCALE_PATHS', [])
        has_locale_paths = len(locale_paths) > 0
        self.log_test(
            "Locale paths configured",
            has_locale_paths,
            f"Found {len(locale_paths)} locale paths"
        )

        # Test LocaleMiddleware
        middleware = getattr(settings, 'MIDDLEWARE', [])
        has_locale_middleware = 'django.middleware.locale.LocaleMiddleware' in middleware
        self.log_test(
            "LocaleMiddleware installed",
            has_locale_middleware,
            "LocaleMiddleware found in MIDDLEWARE"
        )

    def test_locale_files(self):
        """Test locale file structure"""
        print("\n📁 Testing Locale Files...")

        # Test main locale directory
        main_locale = project_root / 'locale'
        has_main_locale = main_locale.exists()
        self.log_test(
            "Main locale directory exists",
            has_main_locale,
            f"Path: {main_locale}"
        )

        if has_main_locale:
            # Test language directories
            languages = ['en', 'hi']
            for lang in languages:
                lang_dir = main_locale / lang / 'LC_MESSAGES'
                po_file = lang_dir / 'django.po'

                has_lang_dir = lang_dir.exists()
                has_po_file = po_file.exists()

                self.log_test(
                    f"Language {lang} structure",
                    has_lang_dir and has_po_file,
                    f"Directory: {has_lang_dir}, PO file: {has_po_file}"
                )

                # Test PO file content
                if has_po_file:
                    try:
                        with open(po_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            has_translations = 'msgstr' in content and len(content) > 1000
                            self.log_test(
                                f"Language {lang} has translations",
                                has_translations,
                                f"File size: {len(content)} chars"
                            )
                    except Exception as e:
                        self.log_test(
                            f"Language {lang} file readable",
                            False,
                            f"Error: {e}"
                        )

    def test_url_patterns(self):
        """Test localization URL patterns"""
        print("\n🌐 Testing URL Patterns...")

        try:
            # Test i18n URLs
            i18n_url = reverse('set_language')
            self.log_test(
                "set_language URL",
                True,
                f"Resolved to: {i18n_url}"
            )
        except Exception as e:
            self.log_test(
                "set_language URL",
                False,
                f"Error: {e}"
            )

        try:
            # Test JavaScript catalog URL
            js_catalog_url = reverse('javascript-catalog')
            self.log_test(
                "JavaScript catalog URL",
                True,
                f"Resolved to: {js_catalog_url}"
            )
        except Exception as e:
            self.log_test(
                "JavaScript catalog URL",
                False,
                f"Error: {e}"
            )

    def test_translation_functions(self):
        """Test translation functions work"""
        print("\n🔤 Testing Translation Functions...")

        try:
            from django.utils.translation import gettext_lazy as _, activate

            # Test with English
            activate('en')
            en_text = str(_("Page Not Found"))

            # Test with Hindi
            activate('hi')
            hi_text = str(_("Page Not Found"))

            # They should be different if Hindi translation exists
            translations_work = en_text != hi_text

            self.log_test(
                "Translation functions work",
                translations_work,
                f"EN: '{en_text}' vs HI: '{hi_text}'"
            )

            # Reset to default
            activate('en')

        except Exception as e:
            self.log_test(
                "Translation functions work",
                False,
                f"Error: {e}"
            )

    def test_javascript_framework(self):
        """Test JavaScript i18n framework"""
        print("\n📜 Testing JavaScript Framework...")

        js_file = project_root / 'frontend' / 'static' / 'js' / 'modules' / 'core' / 'i18n.js'

        has_js_file = js_file.exists()
        self.log_test(
            "JavaScript i18n file exists",
            has_js_file,
            f"Path: {js_file}"
        )

        if has_js_file:
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                    # Check for key functions
                    has_gettext = 'gettext(' in content
                    has_ngettext = 'ngettext(' in content
                    has_class = 'class IntelliWizI18n' in content

                    framework_complete = has_gettext and has_ngettext and has_class

                    self.log_test(
                        "JavaScript framework complete",
                        framework_complete,
                        f"gettext: {has_gettext}, ngettext: {has_ngettext}, class: {has_class}"
                    )

            except Exception as e:
                self.log_test(
                    "JavaScript framework readable",
                    False,
                    f"Error: {e}"
                )

    def test_template_integration(self):
        """Test template integration"""
        print("\n🎨 Testing Template Integration...")

        # Test base template has i18n
        base_template = project_root / 'frontend' / 'templates' / 'globals' / 'base_accessible.html'

        if base_template.exists():
            try:
                with open(base_template, 'r', encoding='utf-8') as f:
                    content = f.read()

                    has_i18n_load = '{% load i18n %}' in content
                    has_js_include = 'i18n.js' in content
                    has_lang_switcher = 'language_switcher.html' in content

                    template_ready = has_i18n_load and has_js_include and has_lang_switcher

                    self.log_test(
                        "Base template i18n ready",
                        template_ready,
                        f"i18n load: {has_i18n_load}, JS: {has_js_include}, switcher: {has_lang_switcher}"
                    )

            except Exception as e:
                self.log_test(
                    "Base template readable",
                    False,
                    f"Error: {e}"
                )
        else:
            self.log_test(
                "Base template exists",
                False,
                f"Path not found: {base_template}"
            )

    def test_language_switcher(self):
        """Test language switcher component"""
        print("\n🔄 Testing Language Switcher...")

        switcher_file = project_root / 'frontend' / 'templates' / 'globals' / 'components' / 'language_switcher.html'

        has_switcher = switcher_file.exists()
        self.log_test(
            "Language switcher exists",
            has_switcher,
            f"Path: {switcher_file}"
        )

        if has_switcher:
            try:
                with open(switcher_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                    has_form = 'set_language' in content
                    has_select = '<select' in content
                    has_csrf = 'csrf_token' in content

                    switcher_complete = has_form and has_select and has_csrf

                    self.log_test(
                        "Language switcher complete",
                        switcher_complete,
                        f"form: {has_form}, select: {has_select}, csrf: {has_csrf}"
                    )

            except Exception as e:
                self.log_test(
                    "Language switcher readable",
                    False,
                    f"Error: {e}"
                )

    def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Localization Implementation Validation\n")

        self.test_django_settings()
        self.test_locale_files()
        self.test_url_patterns()
        self.test_translation_functions()
        self.test_javascript_framework()
        self.test_template_integration()
        self.test_language_switcher()

        # Summary
        print(f"\n📊 Validation Summary:")
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"📈 Success Rate: {(self.results['passed'] / (self.results['passed'] + self.results['failed']) * 100):.1f}%")

        if self.results['failed'] == 0:
            print("\n🎉 All tests passed! Localization implementation is ready for production.")
        else:
            print(f"\n⚠️  {self.results['failed']} tests failed. Please review the issues above.")

        return self.results['failed'] == 0


def main():
    """Main entry point"""
    validator = LocalizationValidator()
    success = validator.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
