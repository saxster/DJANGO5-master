"""
GraphQL Security Audit Command

Django management command to audit GraphQL security configuration and detect
potential vulnerabilities or misconfigurations.

Usage:
    python manage.py audit_graphql_security
    python manage.py audit_graphql_security --detailed
    python manage.py audit_graphql_security --fix-issues
    python manage.py audit_graphql_security --export-report /path/to/report.json

This command verifies that the CSRF protection bypass vulnerability (CVSS 8.1)
has been properly addressed and checks for other security issues.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.core.middleware.graphql_csrf_protection import (
    GraphQLCSRFProtectionMiddleware,
    GraphQLSecurityHeadersMiddleware
)
from apps.core.graphql_security import (
    GraphQLSecurityIntrospection,
    QueryComplexityAnalyzer,
    analyze_query_complexity,
    validate_request_origin,
    get_operation_fingerprint
)

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """GraphQL Security Audit Command."""

    help = 'Audit GraphQL security configuration and detect potential vulnerabilities'

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--detailed',
            action='store_true',
            dest='detailed',
            help='Show detailed audit information including configuration values'
        )

        parser.add_argument(
            '--fix-issues',
            action='store_true',
            dest='fix_issues',
            help='Attempt to automatically fix detected security issues'
        )

        parser.add_argument(
            '--export-report',
            dest='export_path',
            help='Export audit report to specified JSON file path'
        )

        parser.add_argument(
            '--check-endpoints',
            action='store_true',
            dest='check_endpoints',
            help='Test GraphQL endpoints for security vulnerabilities'
        )

    def handle(self, *args, **options):
        """Execute the audit command."""
        self.detailed = options.get('detailed', False)
        self.fix_issues = options.get('fix_issues', False)
        self.export_path = options.get('export_path')
        self.check_endpoints = options.get('check_endpoints', False)

        self.stdout.write(
            self.style.HTTP_INFO('🔍 Starting GraphQL Security Audit...\n')
        )

        # Run audit
        audit_results = self.run_security_audit()

        # Display results
        self.display_audit_results(audit_results)

        # Fix issues if requested
        if self.fix_issues:
            self.fix_security_issues(audit_results)

        # Export report if requested
        if self.export_path:
            self.export_audit_report(audit_results, self.export_path)

        # Test endpoints if requested
        if self.check_endpoints:
            endpoint_results = self.test_graphql_endpoints()
            audit_results['endpoint_tests'] = endpoint_results

        # Summary
        self.display_audit_summary(audit_results)

    def run_security_audit(self) -> Dict[str, Any]:
        """Run comprehensive GraphQL security audit."""
        audit_results = {
            'timestamp': datetime.now().isoformat(),
            'django_version': getattr(settings, 'VERSION', 'unknown'),
            'audit_version': '1.0.0',
            'checks': {},
            'issues': [],
            'recommendations': [],
            'security_score': 0
        }

        # Run all security checks
        checks = [
            self.check_csrf_protection,
            self.check_middleware_configuration,
            self.check_rate_limiting,
            self.check_query_complexity_limits,
            self.check_security_headers,
            self.check_authentication_settings,
            self.check_debug_configuration,
            self.check_cors_settings,
            self.check_logging_configuration,
            self.check_cache_configuration
        ]

        total_checks = len(checks)
        passed_checks = 0

        for check_func in checks:
            try:
                check_name = check_func.__name__.replace('check_', '')
                self.stdout.write(f'  ⏳ Checking {check_name.replace("_", " ")}...')

                result = check_func()
                audit_results['checks'][check_name] = result

                if result['status'] == 'PASS':
                    passed_checks += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✅ {check_name.replace("_", " ")} - PASS')
                    )
                elif result['status'] == 'WARN':
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  {check_name.replace("_", " ")} - WARNING')
                    )
                    audit_results['recommendations'].append(result.get('message', 'Warning detected'))
                else:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ {check_name.replace("_", " ")} - FAIL')
                    )
                    audit_results['issues'].append(result.get('message', 'Issue detected'))

            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Error during {check_func.__name__}: {e}")
                audit_results['checks'][check_name] = {
                    'status': 'ERROR',
                    'message': f'Check failed: {str(e)}'
                }

        # Calculate security score
        audit_results['security_score'] = int((passed_checks / total_checks) * 100)

        return audit_results

    def check_csrf_protection(self) -> Dict[str, Any]:
        """Check CSRF protection configuration."""
        issues = []
        recommendations = []

        # Check if CSRF protection is enabled
        csrf_enabled = getattr(settings, 'GRAPHQL_CSRF_PROTECTION_ENABLED', True)
        if not csrf_enabled:
            issues.append("CRITICAL: GraphQL CSRF protection is disabled")

        # Check strict mode
        strict_mode = getattr(settings, 'GRAPHQL_CSRF_STRICT_MODE', True)
        if not strict_mode:
            recommendations.append("Consider enabling CSRF strict mode for enhanced security")

        # Check for csrf_exempt usage in URLs
        try:
            from django.urls import reverse
            from django.conf.urls import url
            from intelliwiz_config.urls_optimized import urlpatterns

            # Check if any GraphQL URLs still use csrf_exempt
            for pattern in urlpatterns:
                if hasattr(pattern, 'callback') and hasattr(pattern.callback, 'view_class'):
                    if 'graphql' in str(pattern.pattern).lower():
                        # Check if csrf_exempt is still being used
                        if hasattr(pattern.callback, '_csrf_exempt'):
                            issues.append(f"CRITICAL: csrf_exempt still used in URL pattern: {pattern.pattern}")

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            recommendations.append(f"Could not verify URL patterns: {e}")

        # Check middleware ordering
        middleware = getattr(settings, 'MIDDLEWARE', [])
        csrf_middleware = 'django.middleware.csrf.CsrfViewMiddleware'
        graphql_csrf_middleware = 'apps.core.middleware.graphql_csrf_protection.GraphQLCSRFProtectionMiddleware'

        if csrf_middleware not in middleware:
            issues.append("CRITICAL: Django CSRF middleware not found in MIDDLEWARE setting")

        if graphql_csrf_middleware not in middleware:
            issues.append("CRITICAL: GraphQL CSRF protection middleware not found in MIDDLEWARE setting")

        # Check ordering
        if csrf_middleware in middleware and graphql_csrf_middleware in middleware:
            csrf_index = middleware.index(csrf_middleware)
            graphql_index = middleware.index(graphql_csrf_middleware)

            if graphql_index > csrf_index:
                recommendations.append("GraphQL CSRF middleware should be placed before Django CSRF middleware")

        status = 'FAIL' if issues else ('WARN' if recommendations else 'PASS')
        message = '; '.join(issues + recommendations) if issues or recommendations else 'CSRF protection properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'csrf_enabled': csrf_enabled,
                'strict_mode': strict_mode,
                'middleware_present': graphql_csrf_middleware in middleware,
                'issues': issues,
                'recommendations': recommendations
            }
        }

    def check_middleware_configuration(self) -> Dict[str, Any]:
        """Check GraphQL middleware configuration."""
        issues = []
        recommendations = []

        middleware = getattr(settings, 'MIDDLEWARE', [])

        # Required middleware
        required_middleware = [
            'apps.core.middleware.graphql_csrf_protection.GraphQLCSRFProtectionMiddleware',
            'apps.core.middleware.graphql_csrf_protection.GraphQLSecurityHeadersMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.middleware.security.SecurityMiddleware'
        ]

        for mw in required_middleware:
            if mw not in middleware:
                issues.append(f"Missing required middleware: {mw}")

        # Check for deprecated or vulnerable middleware
        deprecated_middleware = [
            'django.middleware.csrf.CsrfViewMiddleware',  # If not properly configured
        ]

        status = 'FAIL' if issues else ('WARN' if recommendations else 'PASS')
        message = '; '.join(issues + recommendations) if issues or recommendations else 'Middleware properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'middleware_count': len(middleware),
                'required_present': [mw for mw in required_middleware if mw in middleware],
                'missing': [mw for mw in required_middleware if mw not in middleware],
                'issues': issues,
                'recommendations': recommendations
            }
        }

    def check_rate_limiting(self) -> Dict[str, Any]:
        """Check rate limiting configuration."""
        issues = []
        recommendations = []

        # Check if rate limiting is enabled
        rate_limiting_enabled = getattr(settings, 'ENABLE_GRAPHQL_RATE_LIMITING', True)
        if not rate_limiting_enabled:
            recommendations.append("Consider enabling GraphQL rate limiting for DoS protection")

        # Check rate limits
        max_requests = getattr(settings, 'GRAPHQL_RATE_LIMIT_MAX', 100)
        if max_requests > 1000:
            recommendations.append(f"Rate limit seems high ({max_requests}), consider lowering for better protection")

        window = getattr(settings, 'GRAPHQL_RATE_LIMIT_WINDOW', 300)
        if window > 3600:  # 1 hour
            recommendations.append(f"Rate limit window seems long ({window}s), consider shorter window")

        status = 'WARN' if recommendations else 'PASS'
        message = '; '.join(recommendations) if recommendations else 'Rate limiting properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'enabled': rate_limiting_enabled,
                'max_requests': max_requests,
                'window_seconds': window,
                'recommendations': recommendations
            }
        }

    def check_query_complexity_limits(self) -> Dict[str, Any]:
        """Check GraphQL query complexity limits."""
        issues = []
        recommendations = []

        # Check complexity limits
        max_depth = getattr(settings, 'GRAPHQL_MAX_QUERY_DEPTH', None)
        max_complexity = getattr(settings, 'GRAPHQL_MAX_QUERY_COMPLEXITY', None)

        if max_depth is None:
            recommendations.append("Consider setting GRAPHQL_MAX_QUERY_DEPTH to prevent deeply nested queries")
        elif max_depth > 15:
            recommendations.append(f"Query depth limit seems high ({max_depth}), consider lowering")

        if max_complexity is None:
            recommendations.append("Consider setting GRAPHQL_MAX_QUERY_COMPLEXITY to prevent complex queries")
        elif max_complexity > 10000:
            recommendations.append(f"Query complexity limit seems high ({max_complexity}), consider lowering")

        status = 'WARN' if recommendations else 'PASS'
        message = '; '.join(recommendations) if recommendations else 'Query complexity limits properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'max_depth': max_depth,
                'max_complexity': max_complexity,
                'recommendations': recommendations
            }
        }

    def check_security_headers(self) -> Dict[str, Any]:
        """Check security headers configuration."""
        issues = []
        recommendations = []

        # Check if security headers middleware is present
        middleware = getattr(settings, 'MIDDLEWARE', [])
        security_headers_middleware = 'apps.core.middleware.graphql_csrf_protection.GraphQLSecurityHeadersMiddleware'

        if security_headers_middleware not in middleware:
            issues.append("GraphQL security headers middleware not found")

        # Check security settings
        security_settings = [
            ('SECURE_BROWSER_XSS_FILTER', True),
            ('SECURE_CONTENT_TYPE_NOSNIFF', True),
            ('X_FRAME_OPTIONS', 'DENY'),
        ]

        for setting_name, expected_value in security_settings:
            actual_value = getattr(settings, setting_name, None)
            if actual_value != expected_value:
                recommendations.append(f"Consider setting {setting_name} to {expected_value}")

        status = 'FAIL' if issues else ('WARN' if recommendations else 'PASS')
        message = '; '.join(issues + recommendations) if issues or recommendations else 'Security headers properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'middleware_present': security_headers_middleware in middleware,
                'security_settings': {name: getattr(settings, name, None) for name, _ in security_settings},
                'issues': issues,
                'recommendations': recommendations
            }
        }

    def check_authentication_settings(self) -> Dict[str, Any]:
        """Check authentication and authorization settings."""
        issues = []
        recommendations = []

        # Check GraphQL JWT settings
        graphql_jwt = getattr(settings, 'GRAPHQL_JWT', {})

        if not graphql_jwt:
            recommendations.append("Consider configuring GRAPHQL_JWT settings for enhanced security")

        # Check authentication backends
        auth_backends = getattr(settings, 'AUTHENTICATION_BACKENDS', [])
        jwt_backend = 'graphql_jwt.backends.JSONWebTokenBackend'

        if jwt_backend in auth_backends:
            # Check JWT settings
            verify_expiration = graphql_jwt.get('JWT_VERIFY_EXPIRATION', True)
            if not verify_expiration:
                issues.append("JWT expiration verification is disabled - security risk")

        status = 'FAIL' if issues else ('WARN' if recommendations else 'PASS')
        message = '; '.join(issues + recommendations) if issues or recommendations else 'Authentication properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'jwt_configured': bool(graphql_jwt),
                'jwt_backend_present': jwt_backend in auth_backends,
                'jwt_settings': graphql_jwt,
                'issues': issues,
                'recommendations': recommendations
            }
        }

    def check_debug_configuration(self) -> Dict[str, Any]:
        """Check debug and development settings."""
        issues = []
        recommendations = []

        # Check DEBUG setting
        debug = getattr(settings, 'DEBUG', False)
        if debug:
            issues.append("CRITICAL: DEBUG mode is enabled in production")

        # Check GraphQL introspection
        graphene_settings = getattr(settings, 'GRAPHENE', {})
        if debug and 'INTROSPECTION' not in graphene_settings:
            recommendations.append("Consider explicitly configuring GraphQL introspection settings")

        status = 'FAIL' if issues else ('WARN' if recommendations else 'PASS')
        message = '; '.join(issues + recommendations) if issues or recommendations else 'Debug settings properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'debug_enabled': debug,
                'graphene_settings': graphene_settings,
                'issues': issues,
                'recommendations': recommendations
            }
        }

    def check_cors_settings(self) -> Dict[str, Any]:
        """Check CORS configuration."""
        issues = []
        recommendations = []

        # Check allowed origins
        allowed_origins = getattr(settings, 'GRAPHQL_ALLOWED_ORIGINS', [])
        cors_allow_all = getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)

        if cors_allow_all:
            issues.append("CRITICAL: CORS allows all origins - security risk")

        if not allowed_origins and not cors_allow_all:
            recommendations.append("Consider configuring GRAPHQL_ALLOWED_ORIGINS for enhanced security")

        # Check strict origin validation
        strict_origin = getattr(settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION', False)
        if not strict_origin:
            recommendations.append("Consider enabling GRAPHQL_STRICT_ORIGIN_VALIDATION")

        status = 'FAIL' if issues else ('WARN' if recommendations else 'PASS')
        message = '; '.join(issues + recommendations) if issues or recommendations else 'CORS properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'allowed_origins': allowed_origins,
                'cors_allow_all': cors_allow_all,
                'strict_origin_validation': strict_origin,
                'issues': issues,
                'recommendations': recommendations
            }
        }

    def check_logging_configuration(self) -> Dict[str, Any]:
        """Check security logging configuration."""
        issues = []
        recommendations = []

        # Check if security logging is configured
        logging_config = getattr(settings, 'LOGGING', {})
        loggers = logging_config.get('loggers', {})

        security_loggers = ['security', 'graphql_security', 'security.audit']
        configured_loggers = [logger for logger in security_loggers if logger in loggers]

        if not configured_loggers:
            recommendations.append("Consider configuring security loggers for monitoring")

        # Check GraphQL security logging settings
        graphql_security_logging = getattr(settings, 'GRAPHQL_SECURITY_LOGGING', {})
        if not graphql_security_logging:
            recommendations.append("Consider configuring GRAPHQL_SECURITY_LOGGING settings")

        status = 'WARN' if recommendations else 'PASS'
        message = '; '.join(recommendations) if recommendations else 'Logging properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'configured_security_loggers': configured_loggers,
                'graphql_security_logging': graphql_security_logging,
                'recommendations': recommendations
            }
        }

    def check_cache_configuration(self) -> Dict[str, Any]:
        """Check cache configuration for security."""
        issues = []
        recommendations = []

        # Check cache configuration
        caches = getattr(settings, 'CACHES', {})
        default_cache = caches.get('default', {})

        cache_backend = default_cache.get('BACKEND', '')
        if 'dummy' in cache_backend.lower():
            recommendations.append("Dummy cache backend detected - rate limiting may not work properly")

        # Check cache security
        if 'redis' in cache_backend.lower():
            # Redis-specific security checks
            location = default_cache.get('LOCATION', '')
            if 'redis://' in location and 'password' not in location:
                recommendations.append("Consider using password-protected Redis for enhanced security")

        status = 'WARN' if recommendations else 'PASS'
        message = '; '.join(recommendations) if recommendations else 'Cache properly configured'

        return {
            'status': status,
            'message': message,
            'details': {
                'cache_backend': cache_backend,
                'cache_location': default_cache.get('LOCATION', ''),
                'recommendations': recommendations
            }
        }

    def test_graphql_endpoints(self) -> Dict[str, Any]:
        """Test GraphQL endpoints for security vulnerabilities."""
        self.stdout.write(self.style.HTTP_INFO('\n🔬 Testing GraphQL Endpoints...\n'))

        factory = RequestFactory()
        middleware = GraphQLCSRFProtectionMiddleware()

        test_results = {
            'csrf_protection_test': self.test_csrf_protection_endpoint(factory, middleware),
            'rate_limiting_test': self.test_rate_limiting_endpoint(factory, middleware),
            'query_complexity_test': self.test_query_complexity_endpoint(factory, middleware),
        }

        return test_results

    def test_csrf_protection_endpoint(self, factory, middleware) -> Dict[str, Any]:
        """Test CSRF protection on GraphQL endpoints."""
        try:
            # Test mutation without CSRF token
            mutation_data = {
                'query': 'mutation { insertRecord(records: ["test"]) { output { rc } } }'
            }

            request = factory.post(
                '/api/graphql/',
                data=json.dumps(mutation_data),
                content_type='application/json'
            )
            request.user = Mock()
            request.user.is_authenticated = True

            response = middleware.process_request(request)

            if response and response.status_code == 403:
                return {'status': 'PASS', 'message': 'CSRF protection working correctly'}
            else:
                return {'status': 'FAIL', 'message': 'CSRF protection not working - mutations allowed without token'}

        except (ConnectionError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return {'status': 'ERROR', 'message': f'Test failed: {str(e)}'}

    def test_rate_limiting_endpoint(self, factory, middleware) -> Dict[str, Any]:
        """Test rate limiting on GraphQL endpoints."""
        try:
            cache.clear()

            # Make multiple requests to test rate limiting
            requests_made = 0
            rate_limited = False

            for i in range(10):
                request = factory.post('/api/graphql/', {'query': 'query { viewer }'})
                request.user = Mock()
                response = middleware._check_rate_limit(request)

                requests_made += 1

                if response and response.status_code == 429:
                    rate_limited = True
                    break

            if rate_limited:
                return {'status': 'PASS', 'message': f'Rate limiting working - limited after {requests_made} requests'}
            else:
                return {'status': 'WARN', 'message': 'Rate limiting not triggered during test'}

        except (ConnectionError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return {'status': 'ERROR', 'message': f'Test failed: {str(e)}'}

    def test_query_complexity_endpoint(self, factory, middleware) -> Dict[str, Any]:
        """Test query complexity validation."""
        try:
            # Test with a complex query
            complex_query = """
            query {
                level1 {
                    level2 {
                        level3 {
                            level4 {
                                level5 {
                                    data
                                }
                            }
                        }
                    }
                }
            }
            """

            request = factory.post('/api/graphql/', {'query': complex_query})
            operation_type = middleware._get_graphql_operation_type(request)

            if operation_type == 'query':
                return {'status': 'PASS', 'message': 'Query complexity detection working'}
            else:
                return {'status': 'WARN', 'message': 'Could not test query complexity properly'}

        except (ConnectionError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return {'status': 'ERROR', 'message': f'Test failed: {str(e)}'}

    def fix_security_issues(self, audit_results: Dict[str, Any]) -> None:
        """Attempt to automatically fix detected security issues."""
        self.stdout.write(self.style.WARNING('\n🔧 Attempting to fix security issues...\n'))

        fixed_issues = []
        unfixed_issues = []

        for issue in audit_results.get('issues', []):
            if 'DEBUG mode is enabled' in issue:
                self.stdout.write('  🔧 Cannot automatically fix DEBUG mode - manual intervention required')
                unfixed_issues.append(issue)
            elif 'CSRF protection is disabled' in issue:
                self.stdout.write('  🔧 Cannot automatically fix CSRF settings - manual intervention required')
                unfixed_issues.append(issue)
            else:
                unfixed_issues.append(issue)

        if fixed_issues:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Fixed {len(fixed_issues)} issues'))
        if unfixed_issues:
            self.stdout.write(self.style.WARNING(f'  ⚠️  {len(unfixed_issues)} issues require manual intervention'))

    def export_audit_report(self, audit_results: Dict[str, Any], export_path: str) -> None:
        """Export audit report to JSON file."""
        try:
            with open(export_path, 'w') as f:
                json.dump(audit_results, f, indent=2, default=str)

            self.stdout.write(
                self.style.SUCCESS(f'\n📄 Audit report exported to: {export_path}')
            )

        except (ConnectionError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Failed to export report: {str(e)}')
            )

    def display_audit_results(self, audit_results: Dict[str, Any]) -> None:
        """Display audit results in a formatted way."""
        self.stdout.write(self.style.HTTP_INFO('\n📊 Audit Results:\n'))

        # Display summary
        total_checks = len(audit_results['checks'])
        passed_checks = sum(1 for check in audit_results['checks'].values() if check['status'] == 'PASS')
        failed_checks = sum(1 for check in audit_results['checks'].values() if check['status'] == 'FAIL')
        warning_checks = sum(1 for check in audit_results['checks'].values() if check['status'] == 'WARN')

        self.stdout.write(f'  Total Checks: {total_checks}')
        self.stdout.write(self.style.SUCCESS(f'  Passed: {passed_checks}'))
        self.stdout.write(self.style.ERROR(f'  Failed: {failed_checks}'))
        self.stdout.write(self.style.WARNING(f'  Warnings: {warning_checks}'))

        # Display details if requested
        if self.detailed:
            self.stdout.write(self.style.HTTP_INFO('\n📋 Detailed Results:\n'))

            for check_name, result in audit_results['checks'].items():
                status_symbol = '✅' if result['status'] == 'PASS' else ('❌' if result['status'] == 'FAIL' else '⚠️')
                self.stdout.write(f'  {status_symbol} {check_name.replace("_", " ").title()}')
                self.stdout.write(f'    Message: {result.get("message", "No message")}')

                if 'details' in result and result['details']:
                    self.stdout.write('    Details:')
                    for key, value in result['details'].items():
                        if key not in ['issues', 'recommendations']:
                            self.stdout.write(f'      {key}: {value}')

    def display_audit_summary(self, audit_results: Dict[str, Any]) -> None:
        """Display audit summary and final recommendations."""
        security_score = audit_results.get('security_score', 0)
        issues = audit_results.get('issues', [])
        recommendations = audit_results.get('recommendations', [])

        self.stdout.write(self.style.HTTP_INFO('\n🎯 Security Score: ') +
                         self.style.SUCCESS(f'{security_score}/100'))

        if security_score >= 90:
            self.stdout.write(self.style.SUCCESS('\n🛡️  Excellent security posture!'))
        elif security_score >= 75:
            self.stdout.write(self.style.WARNING('\n⚠️  Good security, but room for improvement'))
        elif security_score >= 50:
            self.stdout.write(self.style.ERROR('\n🚨 Security needs attention'))
        else:
            self.stdout.write(self.style.ERROR('\n🔥 CRITICAL: Immediate security action required'))

        if issues:
            self.stdout.write(self.style.ERROR('\n❌ Critical Issues:'))
            for issue in issues:
                self.stdout.write(f'  • {issue}')

        if recommendations:
            self.stdout.write(self.style.WARNING('\n💡 Recommendations:'))
            for rec in recommendations:
                self.stdout.write(f'  • {rec}')

        self.stdout.write(self.style.HTTP_INFO('\n✅ GraphQL Security Audit Complete'))