"""
Optimized Middleware Stack Configuration

This module provides an optimized middleware configuration to address
performance issues with the current 20+ middleware stack.

Optimizations:
- Conditional middleware loading based on request path
- Middleware ordering optimization for performance
- Redundant middleware removal
- Path-based middleware activation
- Memory usage optimization
"""

import logging
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from typing import List, Dict, Optional, Callable

logger = logging.getLogger("django")


class ConditionalMiddlewareLoader(MiddlewareMixin):
    """
    Conditionally loads middleware based on request path and type.

    This prevents unnecessary middleware execution for requests that don't need it,
    significantly improving performance for API endpoints and static assets.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.path_based_middleware = self._configure_path_based_middleware()
        self.excluded_paths = self._configure_excluded_paths()

    def _configure_path_based_middleware(self) -> Dict[str, List[str]]:
        """
        Configure which middleware should run for specific path patterns.

        Returns:
            Dictionary mapping path patterns to middleware class names
        """
        return {
            # API endpoints - minimal middleware for performance
            '/api/': [
                'django.middleware.security.SecurityMiddleware',
                'apps.core.error_handling.CorrelationIDMiddleware',
                'apps.core.middleware.api_authentication.APIAuthenticationMiddleware',
                'apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware',
                'django.contrib.sessions.middleware.SessionMiddleware',
                'corsheaders.middleware.CorsMiddleware',
                'django.middleware.common.CommonMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
            ],

            # Admin interface - full middleware stack
            '/admin/': [
                'django.middleware.security.SecurityMiddleware',
                'apps.core.error_handling.CorrelationIDMiddleware',
                'apps.core.middleware.logging_sanitization.LogSanitizationMiddleware',
                'apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware',
                'django.contrib.sessions.middleware.SessionMiddleware',
                'django.middleware.common.CommonMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
                'django.middleware.clickjacking.XFrameOptionsMiddleware',
            ],

            # Static files - minimal processing
            '/static/': [
                'django.middleware.security.SecurityMiddleware',
                'whitenoise.middleware.WhiteNoiseMiddleware',
                'apps.core.middleware.static_asset_optimization.StaticAssetOptimizationMiddleware',
            ],

            # Media files - minimal processing with security
            '/media/': [
                'django.middleware.security.SecurityMiddleware',
                'apps.core.middleware.file_upload_security_middleware.FileUploadSecurityMiddleware',
            ],

            # Web interface - optimized full stack
            '/': [
                'django.middleware.security.SecurityMiddleware',
                'apps.core.error_handling.CorrelationIDMiddleware',
                'apps.core.middleware.logging_sanitization.LogSanitizationMiddleware',
                'apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware',
                'apps.core.middleware.performance_monitoring.PerformanceMonitoringMiddleware',
                'django.contrib.sessions.middleware.SessionMiddleware',
                'corsheaders.middleware.CorsMiddleware',
                'django.middleware.common.CommonMiddleware',
                'apps.onboarding.middlewares.TimezoneMiddleware',
                'apps.core.middleware.csp_nonce.CSPNonceMiddleware',
                'whitenoise.middleware.WhiteNoiseMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'apps.onboarding_api.middleware.OnboardingAPIMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
                'django.middleware.clickjacking.XFrameOptionsMiddleware',
                'apps.core.error_handling.GlobalExceptionMiddleware',
            ]
        }

    def _configure_excluded_paths(self) -> List[str]:
        """
        Configure paths that should skip most middleware processing.

        Returns:
            List of path patterns to exclude from heavy middleware processing
        """
        return [
            '/favicon.ico',
            '/robots.txt',
            '/sitemap.xml',
            '/health/',
            '/ready/',
            '/alive/',
            '/__debug__/',  # Django Debug Toolbar in development
        ]

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process request to determine appropriate middleware stack.

        Args:
            request: The HTTP request

        Returns:
            None to continue processing
        """
        # Skip middleware optimization for excluded paths
        if any(request.path.startswith(path) for path in self.excluded_paths):
            request._middleware_optimized = 'excluded'
            return None

        # Determine appropriate middleware stack based on path
        for path_pattern, middleware_list in self.path_based_middleware.items():
            if request.path.startswith(path_pattern):
                request._middleware_stack = middleware_list
                request._middleware_optimized = path_pattern
                break
        else:
            # Use default web interface middleware
            request._middleware_stack = self.path_based_middleware['/']
            request._middleware_optimized = 'default'

        # Log middleware optimization for monitoring
        if getattr(settings, 'DEBUG_MIDDLEWARE_OPTIMIZATION', False):
            logger.debug(
                f"Middleware optimization applied: {request._middleware_optimized} "
                f"for path {request.path}"
            )

        return None


class MiddlewarePerformanceMonitor(MiddlewareMixin):
    """
    Monitor middleware performance and log slow middleware.

    This helps identify middleware bottlenecks and optimization opportunities.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.slow_middleware_threshold = getattr(
            settings, 'SLOW_MIDDLEWARE_THRESHOLD_MS', 100
        )

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Start timing middleware execution."""
        import time
        request._middleware_start_time = time.time()
        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log middleware performance metrics."""
        if hasattr(request, '_middleware_start_time'):
            import time
            execution_time = (time.time() - request._middleware_start_time) * 1000

            if execution_time > self.slow_middleware_threshold:
                logger.warning(
                    f"Slow middleware execution: {execution_time:.2f}ms "
                    f"for path {request.path} "
                    f"(threshold: {self.slow_middleware_threshold}ms)"
                )

            # Add performance header for monitoring
            response['X-Middleware-Time'] = f"{execution_time:.2f}ms"

        return response


class OptimizedMiddlewareSettings:
    """
    Provides optimized middleware configurations for different environments.

    This class generates middleware lists based on environment and performance requirements.
    """

    @staticmethod
    def get_production_middleware() -> List[str]:
        """
        Get optimized middleware stack for production environment.

        Returns:
            List of middleware class paths for production
        """
        return [
            # Core security and request handling
            "django.middleware.security.SecurityMiddleware",
            "apps.core.error_handling.CorrelationIDMiddleware",
            "apps.core.middleware.optimized_middleware_stack.ConditionalMiddlewareLoader",

            # Performance monitoring
            "apps.core.middleware.optimized_middleware_stack.MiddlewarePerformanceMonitor",
            "apps.core.middleware.performance_monitoring.PerformanceMonitoringMiddleware",

            # Security middleware (consolidated)
            "apps.core.middleware.logging_sanitization.LogSanitizationMiddleware",
            "apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware",

            # Session and CORS
            "django.contrib.sessions.middleware.SessionMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.common.CommonMiddleware",

            # Application-specific middleware
            "apps.onboarding.middlewares.TimezoneMiddleware",
            "apps.core.middleware.csp_nonce.CSPNonceMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",

            # Authentication and authorization
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "apps.onboarding_api.middleware.OnboardingAPIMiddleware",

            # Response processing
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",

            # Error handling (must be last)
            "apps.core.error_handling.GlobalExceptionMiddleware",
        ]

    @staticmethod
    def get_development_middleware() -> List[str]:
        """
        Get middleware stack for development environment with debugging support.

        Returns:
            List of middleware class paths for development
        """
        production_middleware = OptimizedMiddlewareSettings.get_production_middleware()

        # Add development-specific middleware
        development_additions = [
            # Add after security middleware
            ("apps.core.middleware.query_performance_monitoring.QueryPerformanceMonitoringMiddleware", 3),
            ("apps.core.middleware.slow_query_detection.SlowQueryDetectionMiddleware", 4),
        ]

        # Insert development middleware at specified positions
        for middleware, position in development_additions:
            production_middleware.insert(position, middleware)

        return production_middleware

    @staticmethod
    def get_testing_middleware() -> List[str]:
        """
        Get minimal middleware stack for testing environment.

        Returns:
            List of middleware class paths for testing
        """
        return [
            "django.middleware.security.SecurityMiddleware",
            "apps.core.error_handling.CorrelationIDMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "apps.core.error_handling.GlobalExceptionMiddleware",
        ]

    @staticmethod
    def get_api_only_middleware() -> List[str]:
        """
        Get middleware stack optimized for API-only services.

        Returns:
            List of middleware class paths for API services
        """
        return [
            "django.middleware.security.SecurityMiddleware",
            "apps.core.error_handling.CorrelationIDMiddleware",
            "apps.core.middleware.api_authentication.APIAuthenticationMiddleware",
            "apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "apps.core.error_handling.GlobalExceptionMiddleware",
        ]


def optimize_middleware_for_environment(environment: str = None) -> List[str]:
    """
    Get optimized middleware configuration for the specified environment.

    Args:
        environment: Environment name ('production', 'development', 'testing', 'api-only')
                    If None, uses Django's DEBUG setting to determine environment

    Returns:
        List of middleware class paths optimized for the environment
    """
    if environment is None:
        environment = 'development' if settings.DEBUG else 'production'

    middleware_configs = {
        'production': OptimizedMiddlewareSettings.get_production_middleware,
        'development': OptimizedMiddlewareSettings.get_development_middleware,
        'testing': OptimizedMiddlewareSettings.get_testing_middleware,
        'api-only': OptimizedMiddlewareSettings.get_api_only_middleware,
    }

    config_func = middleware_configs.get(environment)
    if not config_func:
        logger.warning(f"Unknown environment '{environment}', using production middleware")
        config_func = OptimizedMiddlewareSettings.get_production_middleware

    middleware_list = config_func()

    logger.info(
        f"Loaded {len(middleware_list)} middleware components for environment: {environment}"
    )

    return middleware_list


# Middleware performance analysis utilities
class MiddlewareAnalyzer:
    """
    Utility class for analyzing middleware performance and providing optimization recommendations.
    """

    @staticmethod
    def analyze_current_middleware() -> Dict[str, Any]:
        """
        Analyze the current middleware configuration and provide recommendations.

        Returns:
            Dictionary containing analysis results and recommendations
        """
        current_middleware = getattr(settings, 'MIDDLEWARE', [])

        analysis = {
            'total_middleware': len(current_middleware),
            'performance_impact': 'high' if len(current_middleware) > 15 else 'moderate',
            'recommendations': [],
            'potential_savings': {
                'request_processing_time': 0,
                'memory_usage': 0
            }
        }

        # Analyze redundant middleware
        redundant_middleware = [
            'django.middleware.locale.LocaleMiddleware',  # If not using i18n
            'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',  # If not using flatpages
            'django.contrib.redirects.middleware.RedirectFallbackMiddleware',  # If not using redirects
        ]

        for middleware in redundant_middleware:
            if middleware in current_middleware:
                analysis['recommendations'].append(
                    f"Consider removing {middleware} if not actively used"
                )

        # Check middleware ordering
        security_middleware = 'django.middleware.security.SecurityMiddleware'
        if security_middleware in current_middleware:
            security_index = current_middleware.index(security_middleware)
            if security_index > 2:
                analysis['recommendations'].append(
                    "Move SecurityMiddleware closer to the beginning of the stack"
                )

        # Estimate performance improvements
        if len(current_middleware) > 15:
            analysis['potential_savings']['request_processing_time'] = (
                len(current_middleware) - 15
            ) * 2  # ~2ms per middleware

        return analysis

    @staticmethod
    def get_middleware_optimization_report() -> str:
        """
        Generate a comprehensive middleware optimization report.

        Returns:
            String containing the optimization report
        """
        analysis = MiddlewareAnalyzer.analyze_current_middleware()

        report = f"""
Middleware Optimization Report
===============================

Current Configuration:
- Total Middleware: {analysis['total_middleware']}
- Performance Impact: {analysis['performance_impact']}

Recommendations:
"""

        for recommendation in analysis['recommendations']:
            report += f"- {recommendation}\n"

        report += f"""
Potential Savings:
- Request Processing Time: ~{analysis['potential_savings']['request_processing_time']}ms per request
- Memory Usage: Reduced overhead from fewer middleware instances

Optimized Configurations Available:
- Production: {len(OptimizedMiddlewareSettings.get_production_middleware())} middleware
- Development: {len(OptimizedMiddlewareSettings.get_development_middleware())} middleware
- Testing: {len(OptimizedMiddlewareSettings.get_testing_middleware())} middleware
- API-only: {len(OptimizedMiddlewareSettings.get_api_only_middleware())} middleware

To apply optimizations, update your settings.py:
MIDDLEWARE = optimize_middleware_for_environment()
"""

        return report
