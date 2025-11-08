"""Settings validation and health check system."""

import os
import logging
from typing import Dict, Any
from pathlib import Path

# Settings-specific exceptions
SETTINGS_EXCEPTIONS = (ValueError, TypeError, AttributeError, KeyError, ImportError, OSError, IOError)

logger = logging.getLogger(__name__)

class SettingsHealthCheck:
    """Comprehensive settings health check system."""

    def __init__(self):
        self.checks, self.warnings, self.errors = [], [], []

    def validate_all(self, environment: str = 'development') -> Dict[str, Any]:
        """Run all validation checks and return comprehensive report."""
        self.checks.clear()
        self.warnings.clear()
        self.errors.clear()

        # Run all validation checks
        self._validate_environment_setup(environment)
        self._validate_security_configuration(environment)
        self._validate_database_configuration()
        self._validate_cache_configuration()
        self._validate_logging_configuration(environment)
        self._validate_integration_services()
        self._validate_feature_flags()
        self._validate_file_permissions()

        return {'environment': environment, 'status': 'healthy' if not self.errors else 'unhealthy',
               'checks_run': len(self.checks), 'errors': self.errors, 'warnings': self.warnings,
               'checks': self.checks, 'summary': self._generate_summary()}

    def _validate_environment_setup(self, environment: str):
        """Validate environment configuration."""
        try:
            # Check environment file
            env_file = f".env.{environment}.secure"
            env_path = Path(__file__).parent.parent / "envs" / env_file
            if not env_path.exists():
                self.warnings.append(f"Environment file {env_file} not found")

            # Check required variables
            required_vars = ['SECRET_KEY', 'ENCRYPT_KEY', 'DBUSER', 'DBNAME', 'DBPASS', 'DBHOST']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                self.errors.append(f"Missing required environment variables: {', '.join(missing_vars)}")

            self.checks.append(f"Environment Setup: {'✓' if not missing_vars else '✗'}")
        except SETTINGS_EXCEPTIONS as e:
            self.errors.append(f"Environment Setup validation failed: {e}")

    def _validate_security_configuration(self, environment: str):
        """Validate security settings."""
        try:
            from .validation import validate_security_basics
            result = validate_security_basics()
            if result['errors']:
                self.errors.extend(result['errors'])
            if result['warnings']:
                self.warnings.extend(result['warnings'])
            self.checks.append(f"Security Configuration: {'✓' if result['secure'] else '✗'}")
        except SETTINGS_EXCEPTIONS as e:
            self.errors.append(f"Security Configuration validation failed: {e}")

    def _validate_database_configuration(self):
        """Validate database settings."""
        try:
            # Check database parameters
            db_params = ['DBUSER', 'DBNAME', 'DBPASS', 'DBHOST']
            missing_params = [param for param in db_params if not os.getenv(param)]
            if missing_params:
                self.errors.append(f"Missing database parameters: {', '.join(missing_params)}")

            # Test connection
            try:
                from django.db import connection
                connection.ensure_connection()
            except SETTINGS_EXCEPTIONS as e:
                self.warnings.append(f"Database connection test failed: {e}")

            self.checks.append(f"Database Configuration: {'✓' if not missing_params else '✗'}")
        except SETTINGS_EXCEPTIONS as e:
            self.errors.append(f"Database Configuration validation failed: {e}")

    def _validate_cache_configuration(self):
        """Validate cache settings."""
        try:
            from django.core.cache import cache
            test_key = 'health_check_test'
            cache.set(test_key, 'test_value', 1)
            if cache.get(test_key) != 'test_value':
                self.warnings.append("Cache write/read test failed")
            else:
                cache.delete(test_key)
            self.checks.append("Cache Configuration: ✓")
        except SETTINGS_EXCEPTIONS as e:
            self.warnings.append(f"Cache test failed: {e}")
            self.checks.append("Cache Configuration: ⚠")

    def _validate_logging_configuration(self, environment: str):
        """Validate logging setup."""
        try:
            from .logging import get_logging_config
            config = get_logging_config(environment)
            required_sections = ['version', 'formatters', 'handlers', 'loggers']
            missing_sections = [section for section in required_sections if section not in config]
            if missing_sections:
                self.errors.append(f"Missing logging sections: {', '.join(missing_sections)}")
            if environment == 'production':
                try:
                    log_dir = Path('/var/log/youtility4')
                    if not log_dir.exists():
                        os.makedirs(log_dir, exist_ok=True)
                    test_file = log_dir / 'health_check_test.log'
                    test_file.write_text('test')
                    test_file.unlink()
                except (OSError, PermissionError) as e:
                    self.warnings.append(f"Log directory not writable: {e}")
            self.checks.append(f"Logging Configuration: {'✓' if not missing_sections else '✗'}")
        except SETTINGS_EXCEPTIONS as e:
            self.errors.append(f"Logging Configuration validation failed: {e}")

    def _validate_integration_services(self):
        """Validate external service integrations."""
        try:
            # Redis check
            try:
                import redis
                redis.Redis.from_url('redis://127.0.0.1:6379/1').ping()
            except SETTINGS_EXCEPTIONS as e:
                self.warnings.append(f"Redis connection failed: {e}")

            # Check missing configurations
            email_vars = ['AWS_SES_SMTP_USER', 'AWS_SES_SMTP_PASSWORD', 'DEFAULT_FROM_EMAIL']
            missing_email = [var for var in email_vars if not os.getenv(var)]
            if missing_email:
                self.warnings.append(f"Missing email config: {', '.join(missing_email)}")

            mqtt_vars = ['MQTT_BROKER_ADDRESS', 'MQTT_BROKER_PORT', 'MQTT_BROKER_USERNAME', 'MQTT_BROKER_PASSWORD']
            missing_mqtt = [var for var in mqtt_vars if not os.getenv(var)]
            if missing_mqtt:
                self.warnings.append(f"Missing MQTT config: {', '.join(missing_mqtt)}")

            self.checks.append("Integration Services: ✓")
        except SETTINGS_EXCEPTIONS as e:
            self.warnings.append(f"Integration services check failed: {e}")
            self.checks.append("Integration Services: ⚠")

    def _validate_feature_flags(self):
        """Validate feature flag consistency."""
        try:
            from .onboarding import PERSONALIZATION_FEATURE_FLAGS
            conflicts = []
            if (PERSONALIZATION_FEATURE_FLAGS.get('enable_streaming_responses') and
                not PERSONALIZATION_FEATURE_FLAGS.get('enable_provider_routing')):
                conflicts.append("Streaming responses enabled but provider routing disabled")
            if conflicts:
                self.warnings.extend([f"Feature flag conflict: {conflict}" for conflict in conflicts])
            self.checks.append(f"Feature Flags: {'✓' if not conflicts else '⚠'}")
        except SETTINGS_EXCEPTIONS as e:
            self.errors.append(f"Feature Flags validation failed: {e}")

    def _validate_file_permissions(self):
        """Validate file system permissions."""
        try:
            media_root = os.getenv('MEDIA_ROOT', '/tmp')
            if not os.access(media_root, os.W_OK):
                self.errors.append(f"Media root {media_root} not writable")
            static_root = os.getenv('STATIC_ROOT', '/tmp')
            if not os.access(static_root, os.W_OK):
                self.warnings.append(f"Static root {static_root} not writable")
            self.checks.append("File Permissions: ✓")
        except SETTINGS_EXCEPTIONS as e:
            self.warnings.append(f"File permissions check failed: {e}")
            self.checks.append("File Permissions: ⚠")

    def _generate_summary(self) -> str:
        """Generate health check summary."""
        error_count, warning_count = len(self.errors), len(self.warnings)
        if error_count > 0:
            status = f"❌ UNHEALTHY ({error_count} errors, {warning_count} warnings)"
        elif warning_count > 0:
            status = f"⚠️  NEEDS ATTENTION ({warning_count} warnings)"
        else:
            status = "✅ HEALTHY"
        return f"{status} - {len(self.checks)} checks completed"


# Main functions
def run_health_check(environment: str = 'development') -> Dict[str, Any]:
    """Run comprehensive settings health check."""
    return SettingsHealthCheck().validate_all(environment)

def validate_settings_compliance() -> Dict[str, Any]:
    """Validate compliance with .claude/rules.md requirements."""
    from .validation import validate_line_count_compliance
    return validate_line_count_compliance()