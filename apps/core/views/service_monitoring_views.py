"""
Service Layer Performance Monitoring Views

Provides comprehensive monitoring and analytics for the service layer including:
- Service performance metrics
- Error rate tracking
- Cache performance analysis
- Transaction success rates
- Service dependency mapping
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from apps.core.services import service_registry, get_service
from apps.core.services.base_service import BaseService
from apps.peoples.services import AuthenticationService
from apps.schedhuler.services import SchedulingService
from apps.work_order_management.services import WorkOrderService


class ServiceMonitoringDashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Main dashboard for service layer monitoring.

    Provides overview of all registered services and their performance metrics.
    """

    template_name = 'core/service_monitoring_dashboard.html'

    def test_func(self):
        """Only allow staff members to access monitoring."""
        return self.request.user.is_staff

    def get(self, request):
        """Render service monitoring dashboard."""
        try:
            # Get registry overview
            registry_metrics = service_registry.get_service_metrics()
            registered_services = service_registry.get_registered_services()

            # Get individual service metrics
            service_metrics = self._collect_service_metrics()

            # Calculate aggregate metrics
            aggregate_metrics = self._calculate_aggregate_metrics(service_metrics)

            context = {
                'registry_metrics': registry_metrics,
                'registered_services': registered_services,
                'service_metrics': service_metrics,
                'aggregate_metrics': aggregate_metrics,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            return render(request, self.template_name, context)

        except (ValueError, TypeError) as e:
            context = {
                'error': f"Error loading service metrics: {str(e)}",
                'registry_metrics': {},
                'service_metrics': {},
                'aggregate_metrics': {}
            }
            return render(request, self.template_name, context)

    def _collect_service_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all registered services."""
        metrics = {}

        # Get metrics from key services
        service_classes = [
            AuthenticationService,
            SchedulingService,
            WorkOrderService
        ]

        for service_class in service_classes:
            try:
                if service_registry.is_registered(service_class):
                    service = get_service(service_class)
                    service_metrics = service.get_service_metrics()
                    metrics[service_class.__name__] = service_metrics
            except (ValueError, TypeError) as e:
                metrics[service_class.__name__] = {
                    'error': str(e),
                    'service_name': service_class.__name__,
                    'call_count': 0,
                    'error_count': 0,
                    'error_rate': 0.0
                }

        return metrics

    def _calculate_aggregate_metrics(self, service_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate aggregate metrics across all services."""
        total_calls = 0
        total_errors = 0
        total_duration = 0.0
        service_count = 0

        for service_name, metrics in service_metrics.items():
            if 'error' not in metrics:
                total_calls += metrics.get('call_count', 0)
                total_errors += metrics.get('error_count', 0)
                total_duration += metrics.get('total_duration', 0.0)
                service_count += 1

        avg_duration = total_duration / total_calls if total_calls > 0 else 0.0
        error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0.0

        return {
            'total_service_calls': total_calls,
            'total_errors': total_errors,
            'overall_error_rate': round(error_rate, 2),
            'average_response_time': round(avg_duration * 1000, 2),  # Convert to ms
            'active_services': service_count,
            'health_status': 'healthy' if error_rate < 5.0 else 'warning' if error_rate < 10.0 else 'critical'
        }


class ServiceMetricsAPIView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    API endpoint for real-time service metrics.

    Provides JSON data for AJAX updates of the monitoring dashboard.
    """

    def test_func(self):
        """Only allow staff members to access metrics API."""
        return self.request.user.is_staff

    def get(self, request):
        """Return service metrics as JSON."""
        try:
            service_name = request.GET.get('service')

            if service_name:
                # Get specific service metrics
                metrics = self._get_specific_service_metrics(service_name)
            else:
                # Get all service metrics
                metrics = self._get_all_service_metrics()

            return JsonResponse({
                'success': True,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            })

        except (ValueError, TypeError) as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, status=500)

    def _get_specific_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """Get metrics for a specific service."""
        service_mapping = {
            'AuthenticationService': AuthenticationService,
            'SchedulingService': SchedulingService,
            'WorkOrderService': WorkOrderService
        }

        if service_name not in service_mapping:
            raise ValueError(f"Unknown service: {service_name}")

        service_class = service_mapping[service_name]
        service = get_service(service_class)
        return service.get_service_metrics()

    def _get_all_service_metrics(self) -> Dict[str, Any]:
        """Get metrics for all services."""
        dashboard_view = ServiceMonitoringDashboardView()
        return dashboard_view._collect_service_metrics()


class ServiceHealthCheckView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Health check endpoint for service layer monitoring.

    Provides simple health status for monitoring systems.
    """

    def test_func(self):
        """Only allow staff members to access health checks."""
        return self.request.user.is_staff

    def get(self, request):
        """Return service health status."""
        try:
            health_status = self._check_service_health()

            response_data = {
                'status': health_status['overall_status'],
                'timestamp': datetime.now().isoformat(),
                'services': health_status['service_statuses'],
                'registry': health_status['registry_status']
            }

            # Return appropriate HTTP status
            status_code = 200 if health_status['overall_status'] == 'healthy' else 503

            return JsonResponse(response_data, status=status_code)

        except (ValueError, TypeError) as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, status=500)

    def _check_service_health(self) -> Dict[str, Any]:
        """Check health of all services."""
        service_statuses = {}
        overall_healthy = True

        # Check key services
        service_classes = [
            AuthenticationService,
            SchedulingService,
            WorkOrderService
        ]

        for service_class in service_classes:
            try:
                service = get_service(service_class)
                metrics = service.get_service_metrics()

                # Determine health based on error rate
                error_rate = metrics.get('error_rate', 0.0)
                if error_rate > 10.0:
                    status = 'unhealthy'
                    overall_healthy = False
                elif error_rate > 5.0:
                    status = 'warning'
                else:
                    status = 'healthy'

                service_statuses[service_class.__name__] = {
                    'status': status,
                    'error_rate': error_rate,
                    'call_count': metrics.get('call_count', 0),
                    'average_duration': metrics.get('average_duration', 0.0)
                }

            except (ValueError, TypeError) as e:
                service_statuses[service_class.__name__] = {
                    'status': 'error',
                    'error': str(e)
                }
                overall_healthy = False

        # Check service registry
        registry_metrics = service_registry.get_service_metrics()
        registry_status = {
            'status': 'healthy',
            'total_registrations': registry_metrics.get('total_registrations', 0),
            'singleton_instances': registry_metrics.get('singleton_instances', 0)
        }

        return {
            'overall_status': 'healthy' if overall_healthy else 'unhealthy',
            'service_statuses': service_statuses,
            'registry_status': registry_status
        }


class ServicePerformanceAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Advanced analytics view for service performance analysis.

    Provides detailed performance analytics and trends.
    """

    template_name = 'core/service_performance_analytics.html'

    def test_func(self):
        """Only allow staff members to access analytics."""
        return self.request.user.is_staff

    def get(self, request):
        """Render performance analytics dashboard."""
        try:
            # Get time range from query parameters
            days = int(request.GET.get('days', 7))
            service_filter = request.GET.get('service', 'all')

            # Generate analytics data
            analytics_data = self._generate_analytics_data(days, service_filter)

            context = {
                'analytics_data': analytics_data,
                'selected_days': days,
                'selected_service': service_filter,
                'available_services': self._get_available_services()
            }

            return render(request, self.template_name, context)

        except (ValueError, TypeError) as e:
            context = {
                'error': f"Error generating analytics: {str(e)}",
                'analytics_data': {},
                'selected_days': 7,
                'selected_service': 'all'
            }
            return render(request, self.template_name, context)

    def _generate_analytics_data(self, days: int, service_filter: str) -> Dict[str, Any]:
        """Generate analytics data for the specified period."""
        # This is a simplified implementation
        # In a real scenario, you'd query historical data from logs or metrics store

        services = self._get_service_metrics_for_analytics(service_filter)

        # Generate mock trend data for demonstration
        trend_data = self._generate_trend_data(days, services)

        return {
            'performance_trends': trend_data,
            'top_performers': self._identify_top_performers(services),
            'bottlenecks': self._identify_bottlenecks(services),
            'cache_analysis': self._analyze_cache_performance(services),
            'error_analysis': self._analyze_errors(services)
        }

    def _get_service_metrics_for_analytics(self, service_filter: str) -> Dict[str, Any]:
        """Get service metrics for analytics."""
        dashboard_view = ServiceMonitoringDashboardView()
        all_metrics = dashboard_view._collect_service_metrics()

        if service_filter == 'all':
            return all_metrics
        else:
            return {service_filter: all_metrics.get(service_filter, {})}

    def _generate_trend_data(self, days: int, services: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate trend data for visualization."""
        # This would typically query historical metrics
        # For demonstration, we'll create mock data
        import random

        trend_data = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_data = {'date': date}

            for service_name, metrics in services.items():
                if 'error' not in metrics:
                    # Generate mock trend data based on current metrics
                    base_calls = metrics.get('call_count', 100)
                    daily_data[f'{service_name}_calls'] = max(1, base_calls + random.randint(-20, 20))
                    daily_data[f'{service_name}_errors'] = random.randint(0, 5)
                    daily_data[f'{service_name}_avg_duration'] = round(
                        metrics.get('average_duration', 0.1) + random.uniform(-0.05, 0.05), 3
                    )

            trend_data.append(daily_data)

        return trend_data

    def _identify_top_performers(self, services: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify top performing services."""
        performers = []
        for service_name, metrics in services.items():
            if 'error' not in metrics:
                score = self._calculate_performance_score(metrics)
                performers.append({
                    'service': service_name,
                    'score': score,
                    'call_count': metrics.get('call_count', 0),
                    'error_rate': metrics.get('error_rate', 0.0),
                    'avg_duration': metrics.get('average_duration', 0.0)
                })

        return sorted(performers, key=lambda x: x['score'], reverse=True)

    def _identify_bottlenecks(self, services: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks."""
        bottlenecks = []
        for service_name, metrics in services.items():
            if 'error' not in metrics:
                avg_duration = metrics.get('average_duration', 0.0)
                error_rate = metrics.get('error_rate', 0.0)

                if avg_duration > 1.0 or error_rate > 5.0:
                    bottlenecks.append({
                        'service': service_name,
                        'issue_type': 'slow_response' if avg_duration > 1.0 else 'high_errors',
                        'avg_duration': avg_duration,
                        'error_rate': error_rate,
                        'severity': 'high' if avg_duration > 2.0 or error_rate > 10.0 else 'medium'
                    })

        return bottlenecks

    def _analyze_cache_performance(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze cache performance across services."""
        total_hits = 0
        total_misses = 0

        for service_name, metrics in services.items():
            if 'error' not in metrics:
                total_hits += metrics.get('cache_hits', 0)
                total_misses += metrics.get('cache_misses', 0)

        total_operations = total_hits + total_misses
        hit_rate = (total_hits / total_operations * 100) if total_operations > 0 else 0.0

        return {
            'total_cache_operations': total_operations,
            'cache_hit_rate': round(hit_rate, 2),
            'cache_hits': total_hits,
            'cache_misses': total_misses,
            'recommendation': self._get_cache_recommendation(hit_rate)
        }

    def _analyze_errors(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze error patterns across services."""
        error_summary = {}
        total_errors = 0

        for service_name, metrics in services.items():
            if 'error' not in metrics:
                error_count = metrics.get('error_count', 0)
                total_errors += error_count
                if error_count > 0:
                    error_summary[service_name] = {
                        'error_count': error_count,
                        'error_rate': metrics.get('error_rate', 0.0)
                    }

        return {
            'total_errors': total_errors,
            'services_with_errors': len(error_summary),
            'error_breakdown': error_summary,
            'recommendation': self._get_error_recommendation(total_errors)
        }

    def _calculate_performance_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate performance score for a service."""
        call_count = metrics.get('call_count', 0)
        error_rate = metrics.get('error_rate', 0.0)
        avg_duration = metrics.get('average_duration', 0.0)

        # Simple scoring algorithm
        score = max(0, 100 - error_rate * 5 - avg_duration * 10)
        return round(score, 2)

    def _get_cache_recommendation(self, hit_rate: float) -> str:
        """Get cache performance recommendation."""
        if hit_rate > 80:
            return "Excellent cache performance"
        elif hit_rate > 60:
            return "Good cache performance, consider optimizing cache keys"
        else:
            return "Cache performance needs improvement, review caching strategy"

    def _get_error_recommendation(self, total_errors: int) -> str:
        """Get error handling recommendation."""
        if total_errors == 0:
            return "No errors detected, excellent service health"
        elif total_errors < 10:
            return "Low error count, monitor for patterns"
        else:
            return "High error count, immediate investigation recommended"

    def _get_available_services(self) -> List[str]:
        """Get list of available services for filtering."""
        return ['all', 'AuthenticationService', 'SchedulingService', 'WorkOrderService']


@method_decorator(staff_member_required, name='dispatch')
class ServiceRegistryManagementView(View):
    """
    Administrative view for managing service registry.

    Allows staff to view and manage service registrations.
    """

    template_name = 'core/service_registry_management.html'

    def get(self, request):
        """Display service registry management interface."""
        try:
            registered_services = service_registry.get_registered_services()
            registry_metrics = service_registry.get_service_metrics()

            context = {
                'registered_services': registered_services,
                'registry_metrics': registry_metrics,
                'active_sagas': self._get_active_sagas()
            }

            return render(request, self.template_name, context)

        except (ValueError, TypeError) as e:
            context = {
                'error': f"Error loading registry data: {str(e)}",
                'registered_services': {},
                'registry_metrics': {}
            }
            return render(request, self.template_name, context)

    def _get_active_sagas(self) -> List[str]:
        """Get list of active sagas from transaction manager."""
        try:
            from apps.core.services import transaction_manager
            return transaction_manager.get_active_sagas()
        except (ValueError, TypeError):
            return []