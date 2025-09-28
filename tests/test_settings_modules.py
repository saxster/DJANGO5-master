"""
Comprehensive tests for all settings modules.
Validates configuration integrity, security compliance, and functionality.
"""

import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.exceptions import ImproperlyConfigured


class SettingsModuleTestCase(TestCase):
    """Base test case for settings modules."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class LoggingSettingsTests(SettingsModuleTestCase):
    """Test logging configuration module."""

    def test_get_logging_config_development(self):
        from intelliwiz_config.settings.logging import get_logging_config

        config = get_logging_config('development', self.temp_dir)

        self.assertIsInstance(config, dict)
        self.assertEqual(config['version'], 1)
        self.assertIn('formatters', config)
        self.assertIn('handlers', config)
        self.assertIn('loggers', config)
        self.assertIn('colored', config['formatters'])

    def test_get_logging_config_production(self):
        from intelliwiz_config.settings.logging import get_logging_config

        config = get_logging_config('production', self.temp_dir)

        self.assertIsInstance(config, dict)
        self.assertIn('json', config['formatters'])
        self.assertIn('mail_admins', config['handlers'])
        self.assertIn('security_file', config['handlers'])

    def test_get_logging_config_test(self):
        from intelliwiz_config.settings.logging import get_logging_config

        config = get_logging_config('test', self.temp_dir)

        self.assertIsInstance(config, dict)
        self.assertEqual(config['handlers']['console']['level'], 'ERROR')

    def test_setup_logging_with_fallback(self):
        from intelliwiz_config.settings.logging import setup_logging

        # Should not raise exception even with invalid path
        with patch('logging.config.dictConfig', side_effect=Exception("Test error")):
            with patch('logging.basicConfig') as mock_basic:
                setup_logging('test', '/invalid/path')
                mock_basic.assert_called_once()


class LLMSettingsTests(SettingsModuleTestCase):
    """Test LLM configuration module."""

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_LLM_MODEL': 'gpt-4',
        'ENABLE_PRODUCTION_LLM': 'true'
    })
    def test_llm_providers_configuration(self):
        from intelliwiz_config.settings import llm

        self.assertIn('openai', llm.LLM_PROVIDERS)
        self.assertIn('anthropic', llm.LLM_PROVIDERS)
        self.assertEqual(llm.LLM_PROVIDERS['openai']['model'], 'gpt-4')
        self.assertTrue(llm.ENABLE_PRODUCTION_LLM)

    def test_embedding_providers_configuration(self):
        from intelliwiz_config.settings import llm

        self.assertIn('openai', llm.EMBEDDING_PROVIDERS)
        self.assertIn('local', llm.EMBEDDING_PROVIDERS)
        self.assertEqual(llm.EMBEDDING_PROVIDERS['local']['cost_per_token'], 0.0)

    def test_llm_cost_models(self):
        from intelliwiz_config.settings import llm

        self.assertIn('openai', llm.LLM_COST_MODELS)
        self.assertIn('gpt-4', llm.LLM_COST_MODELS['openai'])
        self.assertIn('input_cost_per_1k', llm.LLM_COST_MODELS['openai']['gpt-4'])


class OnboardingSettingsTests(SettingsModuleTestCase):
    """Test onboarding configuration module."""

    @patch.dict(os.environ, {
        'ENABLE_CONVERSATIONAL_ONBOARDING': 'true',
        'ONBOARDING_APPROVE_THRESHOLD': '0.8',
        'KB_DAILY_EMBED_LIMIT': '50000'
    })
    def test_onboarding_feature_flags(self):
        from intelliwiz_config.settings import onboarding

        self.assertTrue(onboarding.ENABLE_CONVERSATIONAL_ONBOARDING)
        self.assertEqual(onboarding.ONBOARDING_APPROVE_THRESHOLD, 0.8)
        self.assertEqual(onboarding.KB_DAILY_EMBED_LIMIT, 50000)

    def test_knowledge_base_settings(self):
        from intelliwiz_config.settings import onboarding

        self.assertIsInstance(onboarding.KB_ALLOWED_SOURCES, list)
        self.assertIn('docs.python.org', onboarding.KB_ALLOWED_SOURCES)
        self.assertIsInstance(onboarding.KB_BLOCKED_LICENSE_PATTERNS, list)

    def test_personalization_feature_flags(self):
        from intelliwiz_config.settings import onboarding

        self.assertIsInstance(onboarding.PERSONALIZATION_FEATURE_FLAGS, dict)
        self.assertIn('enable_preference_learning', onboarding.PERSONALIZATION_FEATURE_FLAGS)


class SecuritySettingsTests(SettingsModuleTestCase):
    """Test security configuration module."""

    def test_csp_directives(self):
        from intelliwiz_config.settings import security

        self.assertIn('default-src', security.CSP_DIRECTIVES)
        self.assertEqual(security.CSP_DIRECTIVES['default-src'], ["'self'"])
        self.assertIn('frame-ancestors', security.CSP_DIRECTIVES)

    def test_cors_configuration(self):
        from intelliwiz_config.settings import security

        self.assertIsInstance(security.CORS_ALLOWED_ORIGINS, list)
        self.assertTrue(security.CORS_ALLOW_CREDENTIALS)

    def test_security_validation(self):
        from intelliwiz_config.settings.security import validate_security_settings

        result = validate_security_settings()
        self.assertIn('errors', result)
        self.assertIn('warnings', result)
        self.assertIsInstance(result['errors'], list)
        self.assertIsInstance(result['warnings'], list)

    def test_environment_specific_settings(self):
        from intelliwiz_config.settings.security import (
            get_development_security_settings,
            get_production_security_settings,
            get_test_security_settings
        )

        dev_settings = get_development_security_settings()
        prod_settings = get_production_security_settings()
        test_settings = get_test_security_settings()

        self.assertIsInstance(dev_settings, dict)
        self.assertIsInstance(prod_settings, dict)
        self.assertIsInstance(test_settings, dict)

        # Development should be less restrictive
        self.assertTrue(dev_settings['CSP_REPORT_ONLY'])
        self.assertFalse(prod_settings['CSP_REPORT_ONLY'])

        # Test should be minimal
        self.assertFalse(test_settings['ENABLE_API_AUTH'])


class IntegrationsSettingsTests(SettingsModuleTestCase):
    """Test integrations configuration module."""

    @patch.dict(os.environ, {
        'CELERY_BROKER_URL': 'redis://localhost:6379/0',
        'AWS_SES_SMTP_USER': 'test-user',
        'DEFAULT_FROM_EMAIL': 'test@example.com'
    })
    def test_celery_configuration(self):
        from intelliwiz_config.settings import integrations

        self.assertEqual(integrations.CELERY_TASK_SERIALIZER, 'json')
        self.assertEqual(integrations.CELERY_RESULT_SERIALIZER, 'json')
        self.assertTrue(integrations.CELERY_TASK_REJECT_ON_WORKER_LOST)

    def test_cache_configuration(self):
        from intelliwiz_config.settings import integrations

        self.assertIn('default', integrations.CACHES)
        self.assertIn('select2', integrations.CACHES)

    def test_notification_providers(self):
        from intelliwiz_config.settings import integrations

        self.assertIn('slack', integrations.NOTIFICATION_PROVIDERS)
        self.assertIn('email', integrations.NOTIFICATION_PROVIDERS)

    def test_environment_specific_integrations(self):
        from intelliwiz_config.settings.integrations import (
            get_development_integrations,
            get_production_integrations
        )

        dev_integrations = get_development_integrations()
        prod_integrations = get_production_integrations()

        self.assertIsInstance(dev_integrations, dict)
        self.assertIsInstance(prod_integrations, dict)

        # Development should use console email backend
        self.assertEqual(dev_integrations['EMAIL_BACKEND'],
                        'django.core.mail.backends.console.EmailBackend')


class SettingsIntegrationTests(SettingsModuleTestCase):
    """Test integration between settings modules."""

    def test_settings_module_imports(self):
        """Test that all settings modules can be imported without errors."""
        try:
            from intelliwiz_config.settings import logging
            from intelliwiz_config.settings import llm
            from intelliwiz_config.settings import onboarding
            from intelliwiz_config.settings import security
            from intelliwiz_config.settings import integrations
        except ImportError as e:
            self.fail(f"Failed to import settings module: {e}")

    def test_base_settings_can_import_specialized_modules(self):
        """Test that base settings can import from specialized modules."""
        try:
            from intelliwiz_config.settings.base import *
        except ImportError as e:
            self.fail(f"Failed to import base settings: {e}")

    @patch.dict(os.environ, {'DJANGO_SETTINGS_MODULE': 'intelliwiz_config.settings.development'})
    def test_development_settings_loading(self):
        """Test development settings can be loaded."""
        try:
            from intelliwiz_config.settings import development
            self.assertTrue(development.DEBUG)
        except ImportError as e:
            self.fail(f"Failed to load development settings: {e}")

    @patch.dict(os.environ, {'DJANGO_SETTINGS_MODULE': 'intelliwiz_config.settings.production'})
    def test_production_settings_loading(self):
        """Test production settings can be loaded."""
        try:
            from intelliwiz_config.settings import production
            self.assertFalse(production.DEBUG)
        except ImportError as e:
            self.fail(f"Failed to load production settings: {e}")

    def test_settings_line_count_compliance(self):
        """Test that all settings modules comply with 200-line limit."""
        import inspect
        from intelliwiz_config.settings import logging, llm, onboarding, security, integrations
        from intelliwiz_config.settings import base, development, production, test

        modules_to_check = [logging, llm, onboarding, security, integrations, base, development, production, test]

        for module in modules_to_check:
            source_lines = inspect.getsourcelines(module)[0]
            line_count = len(source_lines)
            self.assertLessEqual(line_count, 200,
                               f"{module.__name__} has {line_count} lines, exceeds 200-line limit")


class SettingsSecurityTests(SettingsModuleTestCase):
    """Test security aspects of settings modules."""

    def test_no_hardcoded_secrets(self):
        """Test that no hardcoded secrets exist in settings modules."""
        import inspect
        from intelliwiz_config.settings import logging, llm, onboarding, security, integrations

        modules_to_check = [logging, llm, onboarding, security, integrations]

        dangerous_patterns = [
            'password = "', 'secret = "', 'key = "',
            'token = "', 'api_key = "', 'SECRET_KEY = "'
        ]

        for module in modules_to_check:
            source = inspect.getsource(module)
            for pattern in dangerous_patterns:
                if pattern in source and 'env(' not in source[source.find(pattern):source.find(pattern) + 100]:
                    self.fail(f"Potential hardcoded secret found in {module.__name__}: {pattern}")

    def test_security_validation_functions_exist(self):
        """Test that security validation functions exist and work."""
        from intelliwiz_config.settings.security import validate_security_settings

        result = validate_security_settings()
        self.assertIn('errors', result)
        self.assertIn('warnings', result)


if __name__ == '__main__':
    unittest.main()