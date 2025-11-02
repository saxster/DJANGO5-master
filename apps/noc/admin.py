"""
NOC Django Admin Configuration.

Registers security intelligence models for admin interface.
Includes fraud detection model monitoring dashboard.

Follows .claude/rules.md:
- Rule #7: Admin < 200 lines per ModelAdmin
- Rule #11: Specific exception handling
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Avg, Q
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger('noc.admin')


# Import models
from apps.noc.security_intelligence.models import FraudDetectionModel


@admin.register(FraudDetectionModel)
class FraudDetectionModelAdmin(admin.ModelAdmin):
    """
    Admin interface for Fraud Detection Models.

    Features:
    - View model performance metrics
    - Activate/deactivate models
    - Monitor model versions
    """

    list_display = [
        'model_version',
        'tenant',
        'pr_auc_display',
        'precision_at_80_display',
        'train_samples',
        'fraud_ratio_display',
        'is_active_badge',
        'created_at_display',
    ]

    list_filter = [
        'is_active',
        'tenant',
        'cdtz',
    ]

    readonly_fields = [
        'model_version',
        'model_path',
        'pr_auc',
        'precision_at_80_recall',
        'optimal_threshold',
        'train_samples',
        'fraud_samples',
        'normal_samples',
        'class_imbalance_ratio',
        'training_duration_seconds',
        'xgboost_params',
        'feature_importance',
        'metadata',
        'cdtz',
        'mdtz',
        'feature_importance_chart',
    ]

    fieldsets = (
        ('Model Information', {
            'fields': ('tenant', 'model_version', 'model_path', 'is_active')
        }),
        ('Performance Metrics', {
            'fields': (
                'pr_auc',
                'precision_at_80_recall',
                'optimal_threshold',
                'feature_importance_chart',
            )
        }),
        ('Training Data', {
            'fields': (
                'train_samples',
                'fraud_samples',
                'normal_samples',
                'class_imbalance_ratio',
                'training_duration_seconds',
            )
        }),
        ('Model Configuration', {
            'fields': ('xgboost_params', 'feature_importance', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('cdtz', 'mdtz', 'activated_at', 'deactivated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_model']

    def pr_auc_display(self, obj):
        """Display PR-AUC with color coding."""
        if obj.pr_auc >= 0.7:
            color = 'green'
        elif obj.pr_auc >= 0.5:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.3f}</span>',
            color, obj.pr_auc
        )
    pr_auc_display.short_description = 'PR-AUC'

    def precision_at_80_display(self, obj):
        """Display precision @ 80% recall with color coding."""
        if obj.precision_at_80_recall >= 0.5:
            color = 'green'
        elif obj.precision_at_80_recall >= 0.3:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.3f}</span>',
            color, obj.precision_at_80_recall
        )
    precision_at_80_display.short_description = 'Precision @ 80% Recall'

    def fraud_ratio_display(self, obj):
        """Display fraud ratio."""
        return format_html(
            '{:.2f}%',
            obj.class_imbalance_ratio * 100
        )
    fraud_ratio_display.short_description = 'Fraud Ratio'

    def is_active_badge(self, obj):
        """Display active status as badge."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 8px; border-radius: 3px;">ACTIVE</span>'
            )
        else:
            return format_html(
                '<span style="background-color: gray; color: white; padding: 3px 8px; border-radius: 3px;">INACTIVE</span>'
            )
    is_active_badge.short_description = 'Status'

    def created_at_display(self, obj):
        """Display creation timestamp."""
        return obj.cdtz.strftime('%Y-%m-%d %H:%M')
    created_at_display.short_description = 'Created'

    def feature_importance_chart(self, obj):
        """Display feature importance as HTML chart."""
        if not obj.feature_importance:
            return "No feature importance data"

        # Sort features by importance
        sorted_features = sorted(
            obj.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]  # Top 10 features

        html = '<div style="font-family: monospace;">'
        max_importance = max(imp for _, imp in sorted_features)

        for feature, importance in sorted_features:
            bar_width = int((importance / max_importance) * 200)
            html += f'''
                <div style="margin: 5px 0;">
                    <span style="display: inline-block; width: 250px;">{feature}</span>
                    <span style="display: inline-block; width: {bar_width}px; height: 15px; background-color: #4CAF50;"></span>
                    <span style="margin-left: 5px;">{importance:.4f}</span>
                </div>
            '''

        html += '</div>'
        return format_html(html)
    feature_importance_chart.short_description = 'Feature Importance'

    def activate_model(self, request, queryset):
        """Action to activate selected model."""
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one model to activate.", level='warning')
            return

        model = queryset.first()
        success = model.activate()

        if success:
            self.message_user(request, f"Model {model.model_version} activated successfully.", level='success')
        else:
            self.message_user(request, "Failed to activate model.", level='error')

    activate_model.short_description = "Activate selected model"

    def get_urls(self):
        """Add custom admin URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'performance-dashboard/',
                self.admin_site.admin_view(self.performance_dashboard),
                name='fraud_model_performance_dashboard',
            ),
        ]
        return custom_urls + urls

    def performance_dashboard(self, request):
        """
        Custom admin view: Fraud Model Performance Dashboard.

        Displays:
        - Prediction volume (daily counts)
        - Accuracy metrics (TP, FP, FN)
        - Precision/Recall over time
        - Feature importance
        - False positive rate alerts
        """
        from apps.noc.security_intelligence.models import (
            FraudDetectionModel,
            FraudPredictionLog
        )

        try:
            # Get active models per tenant
            active_models = FraudDetectionModel.objects.filter(
                is_active=True
            ).select_related('tenant')

            # Get prediction statistics (last 30 days)
            since = timezone.now() - timedelta(days=30)

            dashboard_data = []

            for model in active_models:
                predictions = FraudPredictionLog.objects.filter(
                    tenant=model.tenant,
                    predicted_at__gte=since,
                    model_version=model.model_version
                )

                # Volume metrics
                total_predictions = predictions.count()
                high_risk_count = predictions.filter(risk_level__in=['HIGH', 'CRITICAL']).count()
                medium_risk_count = predictions.filter(risk_level='MEDIUM').count()
                low_risk_count = predictions.filter(risk_level__in=['LOW', 'MINIMAL']).count()

                # Accuracy metrics (only predictions with outcomes)
                predictions_with_outcomes = predictions.filter(
                    actual_fraud_detected__isnull=False
                )

                true_positives = predictions_with_outcomes.filter(
                    fraud_probability__gte=model.optimal_threshold,
                    actual_fraud_detected=True
                ).count()

                false_positives = predictions_with_outcomes.filter(
                    fraud_probability__gte=model.optimal_threshold,
                    actual_fraud_detected=False
                ).count()

                false_negatives = predictions_with_outcomes.filter(
                    fraud_probability__lt=model.optimal_threshold,
                    actual_fraud_detected=True
                ).count()

                true_negatives = predictions_with_outcomes.filter(
                    fraud_probability__lt=model.optimal_threshold,
                    actual_fraud_detected=False
                ).count()

                # Calculate metrics
                total_outcomes = predictions_with_outcomes.count()
                if total_outcomes > 0:
                    accuracy = (true_positives + true_negatives) / total_outcomes
                    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
                    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
                    false_positive_rate = false_positives / total_outcomes
                else:
                    accuracy = precision = recall = false_positive_rate = 0

                # Average prediction accuracy
                avg_accuracy = predictions_with_outcomes.aggregate(
                    avg=Avg('prediction_accuracy')
                )['avg'] or 0

                dashboard_data.append({
                    'model': model,
                    'total_predictions': total_predictions,
                    'high_risk_count': high_risk_count,
                    'medium_risk_count': medium_risk_count,
                    'low_risk_count': low_risk_count,
                    'predictions_with_outcomes': total_outcomes,
                    'true_positives': true_positives,
                    'false_positives': false_positives,
                    'false_negatives': false_negatives,
                    'true_negatives': true_negatives,
                    'accuracy': round(accuracy, 3),
                    'precision': round(precision, 3),
                    'recall': round(recall, 3),
                    'false_positive_rate': round(false_positive_rate, 3),
                    'avg_prediction_accuracy': round(avg_accuracy, 3),
                })

            context = {
                **self.admin_site.each_context(request),
                'title': 'Fraud Detection Model Performance Dashboard',
                'dashboard_data': dashboard_data,
                'opts': FraudDetectionModel._meta,
            }

            return render(request, 'admin/noc/fraud_model_dashboard.html', context)

        except Exception as e:
            logger.error(f"Dashboard error: {e}", exc_info=True)
            self.message_user(request, f"Dashboard error: {str(e)}", level='error')
            return render(request, 'admin/noc/fraud_model_dashboard.html', {
                **self.admin_site.each_context(request),
                'title': 'Fraud Detection Model Performance Dashboard',
                'dashboard_data': [],
                'error': str(e),
            })
