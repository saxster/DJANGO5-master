"""
ML Models Django Admin

Register ML models for admin interface.

Following .claude/rules.md:
- Rule #7: Admin classes < 100 lines
"""

from django.contrib import admin
from django.utils.html import format_html
from apps.ml.models.ml_models import ConflictPredictionModel, PredictionLog


@admin.register(ConflictPredictionModel)
class ConflictPredictionModelAdmin(admin.ModelAdmin):
    """Admin interface for conflict prediction models."""

    list_display = [
        'version',
        'algorithm',
        'accuracy_display',
        'is_active',
        'trained_on_samples',
        'feature_count',
        'created_at'
    ]
    list_filter = ['is_active', 'algorithm', 'created_at']
    search_fields = ['version', 'algorithm']
    readonly_fields = [
        'version',
        'algorithm',
        'accuracy',
        'precision',
        'recall',
        'f1_score',
        'trained_on_samples',
        'feature_count',
        'model_path',
        'created_at'
    ]
    ordering = ['-created_at']
    actions = ['activate_model', 'deactivate_model']

    fieldsets = (
        ('Model Information', {
            'fields': (
                'version',
                'algorithm',
                'is_active',
                'model_path',
                'created_at'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'accuracy',
                'precision',
                'recall',
                'f1_score'
            )
        }),
        ('Training Details', {
            'fields': (
                'trained_on_samples',
                'feature_count'
            )
        }),
    )

    list_per_page = 50

    def accuracy_display(self, obj):
        """Display accuracy with color coding."""
        accuracy = obj.accuracy
        color = 'green' if accuracy > 0.75 else 'orange' if accuracy > 0.60 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2%}</span>',
            color,
            accuracy
        )
    accuracy_display.short_description = 'ROC-AUC'
    accuracy_display.admin_order_field = 'accuracy'

    @admin.action(description='Activate selected model')
    def activate_model(self, request, queryset):
        """Activate selected model."""
        if queryset.count() > 1:
            self.message_user(
                request,
                'Can only activate one model at a time',
                level='ERROR'
            )
            return

        model = queryset.first()
        model.activate()
        self.message_user(
            request,
            f'Activated model {model.version}',
            level='SUCCESS'
        )

    @admin.action(description='Deactivate selected model(s)')
    def deactivate_model(self, request, queryset):
        """Deactivate selected models."""
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f'Deactivated {count} model(s)',
            level='SUCCESS'
        )


@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    """Admin interface for prediction logs."""

    list_display = [
        'id',
        'model_type',
        'model_version',
        'entity_type',
        'predicted_status',
        'probability_display',
        'outcome_status',
        'created_at'
    ]
    list_filter = [
        'model_type',
        'predicted_conflict',
        'actual_conflict_occurred',
        'prediction_correct',
        'created_at'
    ]
    search_fields = ['entity_id', 'model_version']
    readonly_fields = [
        'model_type',
        'model_version',
        'entity_type',
        'entity_id',
        'predicted_conflict',
        'conflict_probability',
        'features_json',
        'created_at'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Prediction Details', {
            'fields': (
                'model_type',
                'model_version',
                'entity_type',
                'entity_id',
                'created_at'
            )
        }),
        ('Prediction Results', {
            'fields': (
                'predicted_conflict',
                'conflict_probability',
                'features_json'
            )
        }),
        ('Actual Outcome', {
            'fields': (
                'actual_conflict_occurred',
                'prediction_correct'
            )
        }),
    )

    list_per_page = 50

    def predicted_status(self, obj):
        """Display predicted conflict status."""
        if obj.predicted_conflict:
            return format_html(
                '<span style="color: red; font-weight: bold;">HIGH RISK</span>'
            )
        return format_html(
            '<span style="color: green;">LOW RISK</span>'
        )
    predicted_status.short_description = 'Prediction'

    def probability_display(self, obj):
        """Display probability with color coding."""
        prob = obj.conflict_probability
        color = 'red' if prob > 0.5 else 'orange' if prob > 0.2 else 'green'
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color,
            prob
        )
    probability_display.short_description = 'Probability'
    probability_display.admin_order_field = 'conflict_probability'

    def outcome_status(self, obj):
        """Display actual outcome status."""
        if obj.actual_conflict_occurred is None:
            return format_html(
                '<span style="color: gray;">⏳ Pending</span>'
            )
        elif obj.prediction_correct:
            return format_html(
                '<span style="color: green;">✓ Correct</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ Incorrect</span>'
            )
    outcome_status.short_description = 'Outcome'
