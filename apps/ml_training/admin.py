"""
Django admin configuration for ML Training platform.

Provides comprehensive admin interfaces for dataset management,
training examples, and labeling tasks with rich functionality.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required

from .models import TrainingDataset, TrainingExample, LabelingTask
from .monitoring import TrainingDataMetrics


@admin.register(TrainingDataset)
class TrainingDatasetAdmin(admin.ModelAdmin):
    """Admin interface for TrainingDataset model."""

    list_display = [
        'name',
        'dataset_type',
        'version',
        'status_badge',
        'progress_bar',
        'quality_badge',
        'created_by',
        'created_at',
    ]

    list_filter = [
        'dataset_type',
        'status',
        'created_at',
        'created_by',
    ]

    search_fields = [
        'name',
        'description',
        'tags',
        'created_by__peoplename',
    ]

    readonly_fields = [
        'uuid',
        'total_examples',
        'labeled_examples',
        'quality_score',
        'completion_percentage',
        'is_ready_for_training',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name',
                'description',
                'dataset_type',
                'version',
                'status',
                'tags',
            )
        }),
        ('Content Statistics', {
            'fields': (
                'total_examples',
                'labeled_examples',
                'completion_percentage',
                'quality_score',
                'is_ready_for_training',
            ),
            'classes': ('collapse',)
        }),
        ('Configuration', {
            'fields': (
                'labeling_guidelines',
                'metadata',
            )
        }),
        ('Management', {
            'fields': (
                'created_by',
                'last_modified_by',
            )
        }),
        ('System', {
            'fields': (
                'uuid',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'mark_as_active',
        'mark_as_archived',
        'update_statistics',
    ]

    list_per_page = 50

    def status_badge(self, obj):
        """Display status as a colored badge."""
        color_map = {
            'DRAFT': 'secondary',
            'ACTIVE': 'success',
            'TRAINING': 'warning',
            'ARCHIVED': 'info',
            'DEPRECATED': 'danger',
        }
        color = color_map.get(obj.status, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def progress_bar(self, obj):
        """Display completion progress as a progress bar."""
        percentage = obj.completion_percentage
        color = 'success' if percentage >= 80 else 'warning' if percentage >= 50 else 'danger'

        return format_html(
            '<div class="progress" style="width: 100px;">'
            '<div class="progress-bar bg-{}" role="progressbar" style="width: {}%">'
            '{:.1f}%'
            '</div>'
            '</div>',
            color,
            percentage,
            percentage
        )
    progress_bar.short_description = "Completion"

    def quality_badge(self, obj):
        """Display quality score as a badge."""
        if obj.quality_score is None:
            return mark_safe('<span class="badge badge-secondary">N/A</span>')

        if obj.quality_score >= 0.9:
            color = "success"
        elif obj.quality_score >= 0.7:
            color = "warning"
        else:
            color = "danger"

        return format_html(
            '<span class="badge badge-{}">{:.2f}</span>',
            color,
            obj.quality_score
        )
    quality_badge.short_description = "Quality"
    quality_badge.admin_order_field = "quality_score"

    def mark_as_active(self, request, queryset):
        """Mark selected datasets as active."""
        updated = queryset.update(status=TrainingDataset.Status.ACTIVE.value)
        self.message_user(request, f'{updated} datasets marked as active.')
    mark_as_active.short_description = "Mark as active"

    def mark_as_archived(self, request, queryset):
        """Mark selected datasets as archived."""
        updated = queryset.update(status=TrainingDataset.Status.ARCHIVED.value)
        self.message_user(request, f'{updated} datasets marked as archived.')
    mark_as_archived.short_description = "Mark as archived"

    def update_statistics(self, request, queryset):
        """Update statistics for selected datasets."""
        for dataset in queryset:
            dataset.update_stats()
        self.message_user(request, f'Statistics updated for {queryset.count()} datasets.')
    update_statistics.short_description = "Update statistics"


@admin.register(TrainingExample)
class TrainingExampleAdmin(admin.ModelAdmin):
    """Admin interface for TrainingExample model."""

    list_display = [
        'dataset_name',
        'image_thumbnail',
        'labeling_status_badge',
        'quality_badge',
        'uncertainty_badge',
        'example_type',
        'source_system',
        'created_at',
    ]

    list_filter = [
        'dataset__dataset_type',
        'labeling_status',
        'example_type',
        'is_labeled',
        'selected_for_labeling',
        'source_system',
        'created_at',
    ]

    search_fields = [
        'dataset__name',
        'ground_truth_text',
        'source_id',
        'image_path',
    ]

    readonly_fields = [
        'uuid',
        'image_hash',
        'image_width',
        'image_height',
        'file_size',
        'is_labeled',
        'needs_review',
        'is_high_value',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Dataset Assignment', {
            'fields': (
                'dataset',
                'example_type',
                'source_system',
                'source_id',
            )
        }),
        ('Image Data', {
            'fields': (
                'image_path',
                'image_hash',
                'image_width',
                'image_height',
                'file_size',
            )
        }),
        ('Ground Truth', {
            'fields': (
                'ground_truth_text',
                'ground_truth_data',
                'labeling_status',
                'is_labeled',
            )
        }),
        ('Quality Metrics', {
            'fields': (
                'quality_score',
                'difficulty_score',
                'uncertainty_score',
                'needs_review',
                'is_high_value',
            )
        }),
        ('Active Learning', {
            'fields': (
                'selected_for_labeling',
                'labeling_priority',
            )
        }),
        ('Metadata', {
            'fields': (
                'capture_metadata',
            ),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': (
                'uuid',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'mark_for_labeling',
        'mark_as_high_priority',
        'mark_for_review',
    ]

    list_per_page = 50

    def dataset_name(self, obj):
        """Display dataset name with link."""
        url = reverse('admin:ml_training_trainingdataset_change', args=[obj.dataset.pk])
        return format_html('<a href="{}">{}</a>', url, obj.dataset.name)
    dataset_name.short_description = "Dataset"
    dataset_name.admin_order_field = "dataset__name"

    def image_thumbnail(self, obj):
        """Display image thumbnail if available."""
        if obj.image_path:
            return format_html(
                '<img src="/media/thumbnails/{}" width="50" height="50" style="object-fit: cover;">',
                obj.image_hash[:16] + '.jpg'
            )
        return mark_safe('<span class="text-muted">No image</span>')
    image_thumbnail.short_description = "Image"

    def labeling_status_badge(self, obj):
        """Display labeling status as a badge."""
        color_map = {
            'UNLABELED': 'secondary',
            'IN_PROGRESS': 'warning',
            'LABELED': 'success',
            'REVIEWED': 'info',
            'DISPUTED': 'danger',
            'REJECTED': 'dark',
        }
        color = color_map.get(obj.labeling_status, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_labeling_status_display()
        )
    labeling_status_badge.short_description = "Status"
    labeling_status_badge.admin_order_field = "labeling_status"

    def quality_badge(self, obj):
        """Display quality score as a badge."""
        if obj.quality_score is None:
            return mark_safe('<span class="badge badge-secondary">N/A</span>')

        if obj.quality_score >= 0.9:
            color = "success"
        elif obj.quality_score >= 0.7:
            color = "warning"
        else:
            color = "danger"

        return format_html(
            '<span class="badge badge-{}">{:.2f}</span>',
            color,
            obj.quality_score
        )
    quality_badge.short_description = "Quality"
    quality_badge.admin_order_field = "quality_score"

    def uncertainty_badge(self, obj):
        """Display uncertainty score as a badge."""
        if obj.uncertainty_score is None:
            return mark_safe('<span class="badge badge-secondary">N/A</span>')

        if obj.uncertainty_score >= 0.8:
            color = "danger"
            icon = "🔥"
        elif obj.uncertainty_score >= 0.6:
            color = "warning"
            icon = "⚠️"
        else:
            color = "success"
            icon = "✅"

        return format_html(
            '<span class="badge badge-{}">{} {:.2f}</span>',
            color,
            icon,
            obj.uncertainty_score
        )
    uncertainty_badge.short_description = "Uncertainty"
    uncertainty_badge.admin_order_field = "uncertainty_score"

    def mark_for_labeling(self, request, queryset):
        """Mark selected examples for labeling."""
        updated = queryset.update(selected_for_labeling=True)
        self.message_user(request, f'{updated} examples marked for labeling.')
    mark_for_labeling.short_description = "Mark for labeling"

    def mark_as_high_priority(self, request, queryset):
        """Mark selected examples as high priority."""
        updated = queryset.update(labeling_priority=10)
        self.message_user(request, f'{updated} examples marked as high priority.')
    mark_as_high_priority.short_description = "Mark as high priority"

    def mark_for_review(self, request, queryset):
        """Mark selected examples for review."""
        updated = queryset.update(labeling_status=TrainingExample.LabelingStatus.DISPUTED.value)
        self.message_user(request, f'{updated} examples marked for review.')
    mark_for_review.short_description = "Mark for review"


@admin.register(LabelingTask)
class LabelingTaskAdmin(admin.ModelAdmin):
    """Admin interface for LabelingTask model."""

    list_display = [
        'dataset_name',
        'task_type',
        'status_badge',
        'assigned_to',
        'progress_bar',
        'priority',
        'due_date',
        'is_overdue',
    ]

    list_filter = [
        'task_type',
        'task_status',
        'priority',
        'assigned_to',
        'due_date',
        'assigned_at',
    ]

    search_fields = [
        'dataset__name',
        'assigned_to__peoplename',
        'instructions',
    ]

    readonly_fields = [
        'uuid',
        'assigned_at',
        'started_at',
        'completed_at',
        'total_examples',
        'examples_completed',
        'completion_percentage',
        'is_overdue',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Task Configuration', {
            'fields': (
                'dataset',
                'task_type',
                'task_status',
                'priority',
                'instructions',
            )
        }),
        ('Assignment', {
            'fields': (
                'assigned_to',
                'assigned_at',
                'due_date',
            )
        }),
        ('Progress', {
            'fields': (
                'started_at',
                'completed_at',
                'total_examples',
                'examples_completed',
                'completion_percentage',
                'is_overdue',
            )
        }),
        ('Quality Review', {
            'fields': (
                'reviewer',
                'quality_score',
                'review_notes',
            )
        }),
        ('Metadata', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': (
                'uuid',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'mark_as_completed',
        'assign_to_me',
        'set_high_priority',
    ]

    list_per_page = 50

    def dataset_name(self, obj):
        """Display dataset name with link."""
        url = reverse('admin:ml_training_trainingdataset_change', args=[obj.dataset.pk])
        return format_html('<a href="{}">{}</a>', url, obj.dataset.name)
    dataset_name.short_description = "Dataset"
    dataset_name.admin_order_field = "dataset__name"

    def status_badge(self, obj):
        """Display task status as a badge."""
        color_map = {
            'ASSIGNED': 'secondary',
            'IN_PROGRESS': 'warning',
            'COMPLETED': 'success',
            'REVIEWED': 'info',
            'REJECTED': 'danger',
        }
        color = color_map.get(obj.task_status, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_task_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "task_status"

    def progress_bar(self, obj):
        """Display task progress as a progress bar."""
        percentage = obj.completion_percentage
        color = 'success' if percentage >= 80 else 'warning' if percentage >= 50 else 'danger'

        return format_html(
            '<div class="progress" style="width: 100px;">'
            '<div class="progress-bar bg-{}" role="progressbar" style="width: {}%">'
            '{:.0f}%'
            '</div>'
            '</div>',
            color,
            percentage,
            percentage
        )
    progress_bar.short_description = "Progress"

    def mark_as_completed(self, request, queryset):
        """Mark selected tasks as completed."""
        for task in queryset:
            task.complete_task()
        self.message_user(request, f'{queryset.count()} tasks marked as completed.')
    mark_as_completed.short_description = "Mark as completed"

    def assign_to_me(self, request, queryset):
        """Assign selected tasks to current user."""
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, f'{updated} tasks assigned to you.')
    assign_to_me.short_description = "Assign to me"

    def set_high_priority(self, request, queryset):
        """Set selected tasks to high priority."""
        updated = queryset.update(priority=10)
        self.message_user(request, f'{updated} tasks set to high priority.')
    set_high_priority.short_description = "Set high priority"


# ============================================================================
# CUSTOM ADMIN VIEWS - ML TRAINING MONITORING DASHBOARD
# ============================================================================

@staff_member_required
def ml_training_metrics_dashboard(request):
    """
    Custom admin view showing ML training data capture metrics.

    Provides real-time health monitoring for:
    - Training data capture rate
    - Labeling task backlog
    - Data quality metrics
    - Active learning effectiveness
    """
    metrics = TrainingDataMetrics.get_comprehensive_dashboard()

    context = {
        **admin.site.each_context(request),
        'title': 'ML Training Metrics Dashboard',
        'metrics': metrics,
        'capture_rate': metrics.get('capture_rate', {}),
        'labeling': metrics.get('labeling_backlog', {}),
        'quality': metrics.get('quality', {}),
        'active_learning': metrics.get('active_learning', {}),
    }

    return render(request, 'admin/ml_training/metrics_dashboard.html', context)


# Custom admin site URLs
class MLTrainingAdminSite(admin.AdminSite):
    """Custom admin site with ML training dashboard."""

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('ml-training/metrics/', ml_training_metrics_dashboard, name='ml_training_metrics'),
        ]
        return custom_urls + urls