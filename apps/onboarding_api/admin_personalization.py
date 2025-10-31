"""
Admin interfaces for personalization and experiment management

This module provides comprehensive admin interfaces including:
- Experiment dashboard with real-time metrics
- User preference management views
- A/B test monitoring and control panels
- Cost analytics and budget management
- Alert monitoring and system health
"""

import logging
import json
from typing import Dict, Any, List
from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView
from django.http import JsonResponse
from datetime import timedelta
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from apps.onboarding_api.services.learning import PreferenceProfile
from apps.onboarding_api.services.experiments import (
    Experiment,
    ExperimentAssignment,
    RecommendationInteraction,
    get_experiment_manager
)
from apps.onboarding_api.services.monitoring import (
    get_metrics_collector,
    get_performance_monitor,
    get_alert_manager,
    get_cost_tracker,
    get_experiment_monitor
)

logger = logging.getLogger(__name__)


# Custom Admin Classes
class PreferenceProfileAdmin(ModelAdmin):
    """Admin interface for preference profiles"""
    list_display = ['user', 'client', 'last_updated', 'acceptance_rate_display', 'total_interactions']
    list_filter = ['last_updated', 'client']
    search_fields = ['user__email', 'client__buname', 'client__bucode']
    readonly_fields = ['profile_id', 'last_updated', 'stats_display', 'preference_vector_display']

    fieldsets = (
        ('Basic Information', {
            'fields': ('profile_id', 'user', 'client', 'last_updated')
        }),
        ('Preferences', {
            'fields': ('weights', 'preference_vector_display'),
            'classes': ('collapse',)
        }),
        ('Learning Statistics', {
            'fields': ('stats_display',),
            'classes': ('collapse',)
        })
    )

    def acceptance_rate_display(self, obj):
        """Display acceptance rate as percentage"""
        rate = obj.calculate_acceptance_rate()
        color = 'green' if rate > 0.7 else 'orange' if rate > 0.5 else 'red'
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color, rate
        )
    acceptance_rate_display.short_description = 'Acceptance Rate'

    def total_interactions(self, obj):
        """Display total interactions count"""
        stats = obj.stats or {}
        total = sum([
            stats.get('approvals', 0),
            stats.get('rejections', 0),
            stats.get('modifications', 0),
            stats.get('escalations', 0)
        ])
        return total
    total_interactions.short_description = 'Total Interactions'

    def stats_display(self, obj):
        """Display formatted statistics"""
        if not obj.stats:
            return "No statistics available"

        stats = obj.stats
        html = "<table>"
        for key, value in stats.items():
            if key != 'details':  # Skip detailed breakdown
                html += f"<tr><td><strong>{key.replace('_', ' ').title()}:</strong></td><td>{value}</td></tr>"
        html += "</table>"
        return format_html(html)
    stats_display.short_description = 'Learning Statistics'

    def preference_vector_display(self, obj):
        """Display preference vector summary"""
        if not obj.preference_vector:
            return "No preference vector"

        vector_len = len(obj.preference_vector)
        vector_norm = sum(x*x for x in obj.preference_vector) ** 0.5
        return f"Dimension: {vector_len}, Norm: {vector_norm:.3f}"
    preference_vector_display.short_description = 'Preference Vector'


class ExperimentAdmin(ModelAdmin):
    """Admin interface for experiments"""
    list_display = ['name', 'status', 'owner', 'scope', 'started_at', 'arms_count', 'assignment_count', 'results_link']
    list_filter = ['status', 'scope', 'primary_metric', 'started_at']
    search_fields = ['name', 'description', 'owner__email']
    readonly_fields = ['experiment_id', 'started_at', 'ended_at', 'results_summary']

    fieldsets = (
        ('Basic Information', {
            'fields': ('experiment_id', 'name', 'description', 'owner', 'scope')
        }),
        ('Configuration', {
            'fields': ('arms', 'primary_metric', 'secondary_metrics', 'holdback_pct')
        }),
        ('Safety & Constraints', {
            'fields': ('safety_constraints',),
            'classes': ('collapse',)
        }),
        ('Status & Timeline', {
            'fields': ('status', 'started_at', 'ended_at')
        }),
        ('Results', {
            'fields': ('results_summary',),
            'classes': ('collapse',)
        })
    )

    def arms_count(self, obj):
        """Display number of arms"""
        return obj.get_arm_count()
    arms_count.short_description = 'Arms'

    def assignment_count(self, obj):
        """Display number of assignments"""
        return ExperimentAssignment.objects.filter(experiment=obj).count()
    assignment_count.short_description = 'Assignments'

    def results_link(self, obj):
        """Link to detailed results"""
        if obj.status in ['running', 'completed']:
            url = reverse('admin:experiment_results', args=[obj.experiment_id])
            return format_html('<a href="{}">View Results</a>', url)
        return "No results yet"
    results_link.short_description = 'Results'

    def results_summary(self, obj):
        """Display results summary"""
        if not obj.results:
            return "No results available"

        results = obj.results
        html = "<div>"

        if 'summary' in results:
            summary = results['summary']
            html += f"<p><strong>Best Arm:</strong> {summary.get('best_performing_arm', {}).get('name', 'N/A')}</p>"
            html += f"<p><strong>Statistical Significance:</strong> {summary.get('statistical_significance', {}).get('any_significant', 'Unknown')}</p>"
            html += f"<p><strong>Recommendation:</strong> {summary.get('recommendation', 'N/A')}</p>"

        html += "</div>"
        return format_html(html)
    results_summary.short_description = 'Results Summary'

    def get_urls(self):
        """Add custom URLs for experiment management"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:experiment_id>/results/',
                self.admin_site.admin_view(self.experiment_results_view),
                name='experiment_results'
            ),
            path(
                '<uuid:experiment_id>/actions/',
                self.admin_site.admin_view(self.experiment_actions_view),
                name='experiment_actions'
            ),
        ]
        return custom_urls + urls

    def experiment_results_view(self, request, experiment_id):
        """Detailed experiment results view"""
        try:
            experiment = get_object_or_404(Experiment, experiment_id=experiment_id)
            experiment_manager = get_experiment_manager()
            experiment_monitor = get_experiment_monitor()

            # Get analysis and monitoring data
            analysis = experiment_manager.analyzer.analyze_experiment(experiment)
            monitoring = experiment_monitor.monitor_experiment(str(experiment_id))

            context = {
                'experiment': experiment,
                'analysis': analysis,
                'monitoring': monitoring,
                'title': f'Results: {experiment.name}'
            }

            return render(request, 'admin/experiment_results.html', context)

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error in experiment results view: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    def experiment_actions_view(self, request, experiment_id):
        """Experiment actions (start, pause, promote) view"""
        try:
            experiment = get_object_or_404(Experiment, experiment_id=experiment_id)

            if request.method == 'POST':
                action = request.POST.get('action')
                experiment_manager = get_experiment_manager()

                if action == 'start':
                    experiment_manager.start_experiment(experiment)
                    message = 'Experiment started successfully'
                elif action == 'pause':
                    reason = request.POST.get('reason', 'Manual pause from admin')
                    experiment_manager.pause_experiment(experiment, reason)
                    message = 'Experiment paused successfully'
                elif action == 'complete':
                    experiment_manager.complete_experiment(experiment)
                    message = 'Experiment completed successfully'
                else:
                    message = f'Unknown action: {action}'

                return JsonResponse({'status': 'success', 'message': message})

            context = {
                'experiment': experiment,
                'title': f'Actions: {experiment.name}'
            }

            return render(request, 'admin/experiment_actions.html', context)

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error in experiment actions view: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class RecommendationInteractionAdmin(ModelAdmin):
    """Admin interface for recommendation interactions"""
    list_display = ['recommendation', 'event_type', 'occurred_at', 'user_display', 'time_to_decision_display']
    list_filter = ['event_type', 'occurred_at', 'session__conversation_type']
    search_fields = ['recommendation__recommendation_id', 'session__user__email']
    readonly_fields = ['interaction_id', 'occurred_at', 'features_display']

    fieldsets = (
        ('Basic Information', {
            'fields': ('interaction_id', 'session', 'recommendation', 'event_type', 'occurred_at')
        }),
        ('Interaction Data', {
            'fields': ('metadata', 'features_display'),
            'classes': ('collapse',)
        })
    )

    def user_display(self, obj):
        """Display user email"""
        if obj.session and obj.session.user:
            return obj.session.user.email
        return "No user"
    user_display.short_description = 'User'

    def time_to_decision_display(self, obj):
        """Display time to decision"""
        time_sec = obj.get_time_to_decision()
        if time_sec > 0:
            return f"{time_sec:.1f}s"
        return "N/A"
    time_to_decision_display.short_description = 'Decision Time'

    def features_display(self, obj):
        """Display extracted features"""
        try:
            features = obj.extract_features()
            html = "<table>"
            for key, value in features.items():
                html += f"<tr><td><strong>{key}:</strong></td><td>{value}</td></tr>"
            html += "</table>"
            return format_html(html)
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            return f"Error extracting features: {str(e)}"
    features_display.short_description = 'Extracted Features'


class ExperimentAssignmentAdmin(ModelAdmin):
    """Admin interface for experiment assignments"""
    list_display = ['experiment', 'user', 'client', 'arm', 'assigned_at', 'is_active_display']
    list_filter = ['arm', 'assigned_at', 'experiment__status']
    search_fields = ['experiment__name', 'user__email', 'client__buname']
    readonly_fields = ['assignment_id', 'assigned_at', 'arm_config_display']

    def is_active_display(self, obj):
        """Display if assignment is active"""
        active = obj.is_active()
        color = 'green' if active else 'red'
        return format_html(
            '<span style="color: {};">{}</span>',
            color, 'Active' if active else 'Inactive'
        )
    is_active_display.short_description = 'Status'

    def arm_config_display(self, obj):
        """Display arm configuration"""
        config = obj.get_arm_config()
        if not config:
            return "No configuration"

        html = "<pre>" + json.dumps(config, indent=2) + "</pre>"
        return format_html(html)
    arm_config_display.short_description = 'Arm Configuration'


# Custom Admin Views
@method_decorator(staff_member_required, name='dispatch')
class PersonalizationDashboardView(TemplateView):
    """Main personalization dashboard"""
    template_name = 'admin/personalization_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # Get monitoring services
            performance_monitor = get_performance_monitor()
            alert_manager = get_alert_manager()
            cost_tracker = get_cost_tracker()

            # Get current metrics
            slo_status = performance_monitor.check_slos(time_window_minutes=60)
            alerts = alert_manager.check_alerts()
            cost_summary = cost_tracker.get_cost_summary(time_window_hours=24)

            # Get experiment summary
            experiments = Experiment.objects.all()
            experiment_stats = {
                'total': experiments.count(),
                'running': experiments.filter(status='running').count(),
                'completed': experiments.filter(status='completed').count(),
                'draft': experiments.filter(status='draft').count()
            }

            # Get user engagement stats
            total_users = PreferenceProfile.objects.values('user').distinct().count()
            active_users = RecommendationInteraction.objects.filter(
                occurred_at__gte=timezone.now() - timedelta(days=7)
            ).values('session__user').distinct().count()

            context.update({
                'slo_status': slo_status,
                'alerts': alerts,
                'cost_summary': cost_summary,
                'experiment_stats': experiment_stats,
                'user_stats': {
                    'total_users': total_users,
                    'active_users_7d': active_users,
                    'engagement_rate': active_users / max(1, total_users)
                },
                'title': 'Personalization Dashboard'
            })

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error loading dashboard data: {str(e)}")
            context['error'] = str(e)

        return context


@method_decorator(staff_member_required, name='dispatch')
class MetricsDashboardView(TemplateView):
    """Metrics and observability dashboard"""
    template_name = 'admin/metrics_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            performance_monitor = get_performance_monitor()

            # Get detailed metrics
            slo_status = performance_monitor.check_slos(time_window_minutes=60)

            # Calculate trend data (last 24 hours)
            trend_data = self._calculate_trend_data()

            context.update({
                'slo_status': slo_status,
                'trend_data': trend_data,
                'title': 'Metrics Dashboard'
            })

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error loading metrics dashboard: {str(e)}")
            context['error'] = str(e)

        return context

    def _calculate_trend_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Calculate 24-hour trend data"""
        try:
            now = timezone.now()
            hours = []

            # Get hourly data for last 24 hours
            for i in range(24):
                hour_start = now - timedelta(hours=i+1)
                hour_end = now - timedelta(hours=i)

                interactions = RecommendationInteraction.objects.filter(
                    occurred_at__gte=hour_start,
                    occurred_at__lt=hour_end
                )

                total_interactions = interactions.count()
                approvals = interactions.filter(event_type='approved').count()
                rejections = interactions.filter(event_type='rejected').count()

                hours.append({
                    'hour': hour_start.strftime('%H:00'),
                    'timestamp': hour_start.isoformat(),
                    'total_interactions': total_interactions,
                    'approval_rate': approvals / max(1, total_interactions),
                    'rejection_rate': rejections / max(1, total_interactions)
                })

            return {
                'hourly_interactions': list(reversed(hours)),
                'summary': {
                    'peak_hour': max(hours, key=lambda x: x['total_interactions'])['hour'] if hours else 'N/A',
                    'total_24h': sum(h['total_interactions'] for h in hours),
                    'avg_approval_rate': sum(h['approval_rate'] for h in hours) / len(hours) if hours else 0
                }
            }

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error calculating trend data: {str(e)}")
            return {}


@staff_member_required
def experiment_analytics_api(request, experiment_id):
    """API endpoint for experiment analytics data"""
    try:
        experiment_monitor = get_experiment_monitor()
        monitoring_data = experiment_monitor.monitor_experiment(experiment_id)

        return JsonResponse(monitoring_data)

    except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error in experiment analytics API: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@cache_page(60)  # Cache for 1 minute
def system_health_api(request):
    """API endpoint for system health data"""
    try:
        performance_monitor = get_performance_monitor()
        alert_manager = get_alert_manager()
        cost_tracker = get_cost_tracker()

        # Get system health data
        slo_status = performance_monitor.check_slos(time_window_minutes=15)
        alerts = alert_manager.check_alerts()
        cost_summary = cost_tracker.get_cost_summary(time_window_hours=1)

        health_data = {
            'timestamp': timezone.now().isoformat(),
            'overall_health': 'healthy' if slo_status.get('overall', {}).get('compliant', False) else 'degraded',
            'slo_compliance': slo_status,
            'active_alerts': len(alerts),
            'critical_alerts': len([a for a in alerts if a.severity == 'critical']),
            'cost_burn_rate': cost_summary.get('cost_per_hour_cents', 0),
            'budget_utilization': cost_summary.get('budget_utilization', 0)
        }

        return JsonResponse(health_data)

    except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error in system health API: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def preference_analytics_api(request):
    """API endpoint for preference analytics"""
    try:
        # Get preference profile statistics
        profiles = PreferenceProfile.objects.all()

        analytics = {
            'total_profiles': profiles.count(),
            'profiles_with_vectors': profiles.exclude(preference_vector__isnull=True).count(),
            'avg_acceptance_rate': 0,
            'weight_distributions': {},
            'learning_progress': {}
        }

        # Calculate average acceptance rate
        acceptance_rates = []
        weight_distributions = {}

        for profile in profiles:
            # Acceptance rate
            rate = profile.calculate_acceptance_rate()
            if rate > 0:
                acceptance_rates.append(rate)

            # Weight distributions
            if profile.weights:
                for key, value in profile.weights.items():
                    if key not in weight_distributions:
                        weight_distributions[key] = []
                    if isinstance(value, (int, float)):
                        weight_distributions[key].append(value)

        analytics['avg_acceptance_rate'] = sum(acceptance_rates) / len(acceptance_rates) if acceptance_rates else 0

        # Calculate weight distribution statistics
        for weight_key, values in weight_distributions.items():
            if values:
                analytics['weight_distributions'][weight_key] = {
                    'mean': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }

        return JsonResponse(analytics)

    except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error in preference analytics API: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Register admin classes
admin.site.register(PreferenceProfile, PreferenceProfileAdmin)
admin.site.register(Experiment, ExperimentAdmin)
admin.site.register(RecommendationInteraction, RecommendationInteractionAdmin)
admin.site.register(ExperimentAssignment, ExperimentAssignmentAdmin)

# Add custom dashboard to admin
admin.site.index_template = 'admin/personalization_index.html'