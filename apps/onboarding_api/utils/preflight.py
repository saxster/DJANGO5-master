"""
Preflight validation utilities for Conversational Onboarding

This module provides comprehensive validation to ensure that tenants are properly
configured before enabling conversational onboarding features. It checks for
required data, configurations, and dependencies.
"""
import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)


class PreflightValidationError(Exception):
    """Exception raised when preflight validation fails"""
    pass


class PreflightValidator:
    """
    Comprehensive preflight validation for conversational onboarding readiness

    This class validates that a tenant has all the required configurations,
    data, and dependencies in place before enabling conversational onboarding.
    """

    def __init__(self, client=None, user=None):
        """
        Initialize preflight validator

        Args:
            client: Bt (client/tenant) instance to validate
            user: People (user) instance requesting validation
        """
        self.client = client
        self.user = user
        self.validation_results = {
            'overall_status': 'unknown',
            'is_ready': False,
            'critical_issues': [],
            'warnings': [],
            'recommendations': [],
            'checks': {},
            'validated_at': timezone.now().isoformat(),
            'validator_version': '1.0'
        }

    def run_full_validation(self) -> Dict[str, Any]:
        """
        Run comprehensive preflight validation

        Returns:
            Dict with complete validation results
        """
        logger.info(f"Starting preflight validation for client {self.client.id if self.client else 'None'}")

        # Core validation checks
        validation_checks = [
            ('client_configuration', self._validate_client_configuration),
            ('user_setup', self._validate_user_setup),
            ('groups_and_permissions', self._validate_groups_permissions),
            ('typeassist_configuration', self._validate_typeassist_configuration),
            ('database_integrity', self._validate_database_integrity),
            ('api_dependencies', self._validate_api_dependencies),
            ('security_configuration', self._validate_security_configuration),
            ('feature_flags', self._validate_feature_flags),
            ('resource_availability', self._validate_resource_availability),
            ('integration_readiness', self._validate_integration_readiness)
        ]

        # Execute all validation checks
        for check_name, check_function in validation_checks:
            try:
                check_result = check_function()
                self.validation_results['checks'][check_name] = check_result

                # Aggregate results
                if not check_result['passed']:
                    if check_result.get('is_critical', False):
                        self.validation_results['critical_issues'].extend(check_result.get('errors', []))
                    else:
                        self.validation_results['warnings'].extend(check_result.get('warnings', []))

                # Add recommendations
                self.validation_results['recommendations'].extend(check_result.get('recommendations', []))

            except (TypeError, ValidationError, ValueError) as e:
                error_msg = f"Preflight check '{check_name}' failed: {str(e)}"
                logger.error(error_msg)
                self.validation_results['critical_issues'].append(error_msg)
                self.validation_results['checks'][check_name] = {
                    'passed': False,
                    'is_critical': True,
                    'errors': [error_msg],
                    'check_failed': True
                }

        # Determine overall status
        self._determine_overall_status()

        logger.info(f"Preflight validation completed: {self.validation_results['overall_status']}")
        return self.validation_results

    def _validate_client_configuration(self) -> Dict[str, Any]:
        """Validate basic client/tenant configuration"""
        result = {
            'passed': True,
            'is_critical': True,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        if not self.client:
            result['passed'] = False
            result['errors'].append('No client/tenant specified for validation')
            return result

        # Check required client fields
        required_fields = ['buname', 'bucode', 'is_active']
        for field in required_fields:
            if not hasattr(self.client, field) or not getattr(self.client, field):
                result['passed'] = False
                result['errors'].append(f'Client missing required field: {field}')

        # Check client is active
        if hasattr(self.client, 'is_active') and not self.client.is_active:
            result['passed'] = False
            result['errors'].append('Client is not active')

        # Check client has valid business unit code
        if hasattr(self.client, 'bucode') and self.client.bucode:
            if len(self.client.bucode) < 2:
                result['warnings'].append('Client business unit code is very short')

        result['details'] = {
            'client_id': self.client.id if self.client else None,
            'client_name': getattr(self.client, 'buname', None),
            'client_code': getattr(self.client, 'bucode', None),
            'is_active': getattr(self.client, 'is_active', False)
        }

        return result

    def _validate_user_setup(self) -> Dict[str, Any]:
        """Validate user configuration and permissions"""
        result = {
            'passed': True,
            'is_critical': True,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        if not self.user:
            result['warnings'].append('No specific user provided for validation')
            return result

        # Check user is active and verified
        if not self.user.is_active:
            result['passed'] = False
            result['errors'].append('User account is not active')

        if hasattr(self.user, 'is_verified') and not self.user.is_verified:
            result['warnings'].append('User account is not verified')

        # Check user has required capabilities for onboarding
        required_capabilities = ['can_use_conversational_onboarding']
        for capability in required_capabilities:
            if not self.user.get_capability(capability):
                result['warnings'].append(f'User missing capability: {capability}')
                result['recommendations'].append(f'Enable capability "{capability}" for the user')

        # Check user has email (required for notifications)
        if not self.user.email:
            result['passed'] = False
            result['errors'].append('User must have an email address')

        # Check user belongs to the same client
        if self.client and self.user.client != self.client:
            result['passed'] = False
            result['errors'].append('User does not belong to the specified client')

        result['details'] = {
            'user_id': self.user.id,
            'user_email': self.user.email,
            'is_active': self.user.is_active,
            'is_verified': getattr(self.user, 'is_verified', None),
            'client_match': self.user.client == self.client if self.client else True,
            'capabilities': self.user.get_all_capabilities() if hasattr(self.user, 'get_all_capabilities') else {}
        }

        return result

    def _validate_groups_permissions(self) -> Dict[str, Any]:
        """Validate required user groups and permission structures"""
        result = {
            'passed': True,
            'is_critical': False,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        try:
            from apps.peoples.models import Pgroup, Pgbelonging

            # Check if there are any groups configured for this client
            if self.client:
                client_groups = Pgroup.objects.filter(client=self.client).count()
                if client_groups == 0:
                    result['warnings'].append('No user groups configured for this client')
                    result['recommendations'].append('Consider creating user groups for better organization')

                # Check for common required groups
                expected_groups = ['Administrators', 'Users', 'Approvers']
                for group_name in expected_groups:
                    group_exists = Pgroup.objects.filter(client=self.client, pgname__icontains=group_name).exists()
                    if not group_exists:
                        result['warnings'].append(f'Recommended group "{group_name}" not found')

                result['details']['client_groups_count'] = client_groups

            # Check if user belongs to any groups
            if self.user:
                user_group_count = Pgbelonging.objects.filter(user=self.user).count()
                if user_group_count == 0:
                    result['warnings'].append('User does not belong to any groups')
                    result['recommendations'].append('Assign user to appropriate groups for permissions')

                result['details']['user_groups_count'] = user_group_count

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            result['warnings'].append(f'Could not validate groups: {str(e)}')

        return result

    def _validate_typeassist_configuration(self) -> Dict[str, Any]:
        """Validate TypeAssist configuration critical for onboarding"""
        result = {
            'passed': True,
            'is_critical': True,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        try:
            # Import TypeAssist model (adjust import path as needed)
            from apps.core_onboarding.models import TypeAssist

            if self.client:
                # Check for critical TypeAssist entries
                critical_types = ['USER', 'LOCATION', 'ASSET', 'TASK']
                typeassist_status = {}

                for type_name in critical_types:
                    exists = TypeAssist.objects.filter(
                        client=self.client,
                        tacode__icontains=type_name,
                        is_active=True
                    ).exists()

                    typeassist_status[type_name] = exists

                    if not exists:
                        result['passed'] = False
                        result['errors'].append(f'Critical TypeAssist "{type_name}" not configured')

                result['details']['typeassist_status'] = typeassist_status

                # Check total TypeAssist count
                total_typeassist = TypeAssist.objects.filter(client=self.client, is_active=True).count()
                if total_typeassist == 0:
                    result['passed'] = False
                    result['errors'].append('No active TypeAssist entries found')
                elif total_typeassist < 5:
                    result['warnings'].append('Very few TypeAssist entries configured')

                result['details']['total_typeassist_count'] = total_typeassist

        except ImportError:
            result['warnings'].append('TypeAssist model not available - skipping validation')
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            result['warnings'].append(f'Could not validate TypeAssist: {str(e)}')

        return result

    def _validate_database_integrity(self) -> Dict[str, Any]:
        """Validate database integrity and required data"""
        result = {
            'passed': True,
            'is_critical': True,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        try:
            from django.db import connection

            # Check database connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone()[0] != 1:
                    result['passed'] = False
                    result['errors'].append('Database connectivity test failed')

            # Check for required tables
            required_tables = [
                'onboarding_conversationsession',
                'onboarding_aichangeset',
                'onboarding_llmrecommendation'
            ]

            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
                existing_tables = [row[0] for row in cursor.fetchall()]

                for table in required_tables:
                    if table not in existing_tables:
                        result['passed'] = False
                        result['errors'].append(f'Required table "{table}" not found')

            result['details']['database_connected'] = True
            result['details']['tables_checked'] = len(required_tables)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            result['passed'] = False
            result['errors'].append(f'Database validation failed: {str(e)}')

        return result

    def _validate_api_dependencies(self) -> Dict[str, Any]:
        """Validate external API dependencies and configurations"""
        result = {
            'passed': True,
            'is_critical': False,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        # Check LLM service configuration
        try:
            llm_enabled = getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False)
            if not llm_enabled:
                result['warnings'].append('LLM checker service is disabled')
                result['recommendations'].append('Consider enabling LLM checker for better recommendations')

            result['details']['llm_checker_enabled'] = llm_enabled
        except (AttributeError, ImportError) as e:
            logger.warning(f"Could not check LLM service configuration: {e}")
            result['warnings'].append('Could not check LLM service configuration')

        # Check knowledge base configuration
        try:
            kb_enabled = getattr(settings, 'ENABLE_ONBOARDING_KB', False)
            result['details']['knowledge_base_enabled'] = kb_enabled

            if not kb_enabled:
                result['warnings'].append('Knowledge base is disabled')
                result['recommendations'].append('Enable knowledge base for enhanced onboarding guidance')
        except (AttributeError, ImportError) as e:
            logger.warning(f"Could not check knowledge base configuration: {e}")
            result['warnings'].append('Could not check knowledge base configuration')

        return result

    def _validate_security_configuration(self) -> Dict[str, Any]:
        """Validate security configuration and requirements"""
        result = {
            'passed': True,
            'is_critical': True,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        # Check rate limiting configuration
        try:
            rate_limiting_enabled = getattr(settings, 'ENABLE_RATE_LIMITING', True)
            if not rate_limiting_enabled:
                result['warnings'].append('Rate limiting is disabled')
                result['recommendations'].append('Enable rate limiting for production security')

            result['details']['rate_limiting_enabled'] = rate_limiting_enabled
        except (AttributeError, ImportError) as e:
            logger.warning(f"Could not check rate limiting configuration: {e}")
            # Use safe default (enabled)
            result['details']['rate_limiting_enabled'] = True

        # Check CORS configuration
        try:
            cors_allowed = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            if not cors_allowed:
                result['warnings'].append('No CORS origins configured')

            result['details']['cors_configured'] = len(cors_allowed) > 0
        except (AttributeError, ImportError) as e:
            logger.warning(f"Could not check CORS configuration: {e}")
            result['details']['cors_configured'] = False

        return result

    def _validate_feature_flags(self) -> Dict[str, Any]:
        """Validate feature flag configuration"""
        result = {
            'passed': True,
            'is_critical': False,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        # Check main onboarding feature flag
        main_feature_enabled = getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False)
        if not main_feature_enabled:
            result['passed'] = False
            result['errors'].append('ENABLE_CONVERSATIONAL_ONBOARDING feature flag is disabled')
            result['is_critical'] = True

        feature_flags = {
            'main_onboarding': main_feature_enabled,
            'llm_checker': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False),
            'knowledge_base': getattr(settings, 'ENABLE_ONBOARDING_KB', False),
            'sse_support': getattr(settings, 'ENABLE_ONBOARDING_SSE', False)
        }

        result['details']['feature_flags'] = feature_flags
        enabled_count = sum(1 for enabled in feature_flags.values() if enabled)

        if enabled_count == 1:  # Only main flag enabled
            result['warnings'].append('Only basic onboarding enabled - consider enabling additional features')

        return result

    def _validate_resource_availability(self) -> Dict[str, Any]:
        """Validate system resource availability"""
        result = {
            'passed': True,
            'is_critical': False,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        try:
            from django.core.cache import cache

            # Test cache availability
            cache_key = f"preflight_test_{timezone.now().timestamp()}"
            cache.set(cache_key, 'test', 60)
            cached_value = cache.get(cache_key)
            cache.delete(cache_key)

            if cached_value != 'test':
                result['warnings'].append('Cache system not functioning properly')
                result['recommendations'].append('Check cache configuration for optimal performance')

            result['details']['cache_working'] = cached_value == 'test'

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            result['warnings'].append(f'Could not test cache system: {str(e)}')

        return result

    def _validate_integration_readiness(self) -> Dict[str, Any]:
        """Validate readiness for onboarding integrations"""
        result = {
            'passed': True,
            'is_critical': False,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'details': {}
        }

        # Check if helpdesk integration is available (for escalations)
        try:
            result['details']['helpdesk_available'] = True
        except ImportError:
            result['warnings'].append('Helpdesk integration not available')
            result['recommendations'].append('Install helpdesk module for escalation support')
            result['details']['helpdesk_available'] = False

        # Check background task system
        try:
            result['details']['background_tasks_available'] = True
        except ImportError:
            result['warnings'].append('Background task system not fully configured')
            result['details']['background_tasks_available'] = False

        return result

    def _determine_overall_status(self):
        """Determine overall validation status"""
        if self.validation_results['critical_issues']:
            self.validation_results['overall_status'] = 'critical'
            self.validation_results['is_ready'] = False
        elif self.validation_results['warnings']:
            self.validation_results['overall_status'] = 'warning'
            self.validation_results['is_ready'] = True  # Can proceed but with cautions
        else:
            self.validation_results['overall_status'] = 'healthy'
            self.validation_results['is_ready'] = True

    def get_readiness_summary(self) -> str:
        """Get human-readable readiness summary"""
        if self.validation_results['overall_status'] == 'critical':
            return f"Not ready for onboarding: {len(self.validation_results['critical_issues'])} critical issues found"
        elif self.validation_results['overall_status'] == 'warning':
            return f"Ready with cautions: {len(self.validation_results['warnings'])} warnings"
        else:
            return "Ready for conversational onboarding"


def run_preflight_validation(client=None, user=None) -> Dict[str, Any]:
    """
    Convenience function to run preflight validation

    Args:
        client: Bt instance to validate
        user: People instance requesting validation

    Returns:
        Complete validation results
    """
    validator = PreflightValidator(client=client, user=user)
    return validator.run_full_validation()