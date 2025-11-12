"""
Django Admin Configuration for Core App

Provides admin interfaces for:
- TaskFailureRecord (DLQ Management)
- Health monitoring models
- Security audit models

Features:
- Bulk actions for DLQ management
- Custom filters and search
- Priority-based retry integration
- Export functionality
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta
import logging

from apps.core.models.task_failure_record import TaskFailureRecord
from apps.core.services.task_priority_service import priority_service
from background_tasks.dead_letter_queue import DeadLetterQueueService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)


# ============================================================================
# DLQ Admin Interface
# ============================================================================

@admin.register(TaskFailureRecord)
class TaskFailureRecordAdmin(admin.ModelAdmin):
    """
    Admin interface for Dead Letter Queue management.
    
    Features:
    - Custom list display with color-coded status
    - Advanced filtering (status, failure type, date ranges)
    - Bulk actions (retry, retry with priority, abandon)
    - Search by task name and exception message
    - Export to CSV functionality
    """
    
    list_display = [
        'task_name_display',
        'status_badge',
        'failure_type_badge',
        'retry_count_display',
        'first_failed_display',
        'next_retry_display',
        'actions_column',
    ]
    
    list_filter = [
        'status',
        'failure_type',
        ('first_failed_at', admin.DateFieldListFilter),
        'business_unit',
    ]
    
    search_fields = [
        'task_name',
        'task_id',
        'exception_message',
    ]
    
    readonly_fields = [
        'task_id',
        'task_name',
        'task_args',
        'task_kwargs',
        'exception_type',
        'exception_message',
        'exception_traceback',
        'first_failed_at',
        'last_retry_at',
        'resolved_at',
        'resolution_method',
    ]
    
    fieldsets = (
        ('Task Information', {
            'fields': ('task_id', 'task_name', 'task_args', 'task_kwargs')
        }),
        ('Failure Details', {
            'fields': ('failure_type', 'exception_type', 'exception_message', 'exception_traceback'),
            'classes': ('collapse',)
        }),
        ('Retry Management', {
            'fields': ('status', 'retry_count', 'max_retries', 'next_retry_at', 'retry_delay')
        }),
        ('Timeline', {
            'fields': ('first_failed_at', 'last_retry_at', 'resolved_at', 'resolution_method')
        }),
        ('Metadata', {
            'fields': ('business_unit', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'retry_selected_tasks',
        'retry_with_high_priority',
        'retry_with_critical_priority',
        'abandon_selected_tasks',
        'export_to_csv',
    ]

    list_per_page = 50
    
    # ========================================================================
    # Custom Display Methods
    # ========================================================================
    
    def task_name_display(self, obj):
        """Display task name with link to filtered view."""
        url = reverse('admin:core_taskfailurerecord_changelist') + f'?task_name={obj.task_name}'
        return format_html(
            '<a href="{}""><code>{}</code></a>',
            url,
            obj.task_name
        )
    task_name_display.short_description = 'Task Name'
    
    def status_badge(self, obj):
        """Color-coded status badge."""
        colors = {
            'PENDING': '#FFA500',      # Orange
            'RETRYING': '#0099CC',     # Blue
            'RESOLVED': '#00C9A7',     # Teal
            'ABANDONED': '#FF4D4F',    # Red
        }
        color = colors.get(obj.status, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    
    def failure_type_badge(self, obj):
        """Color-coded failure type badge."""
        colors = {
            'TRANSIENT': '#FFC107',         # Yellow
            'PERMANENT': '#FF4D4F',         # Red
            'CONFIGURATION': '#9C27B0',     # Purple
            'EXTERNAL': '#2196F3',          # Blue
            'UNKNOWN': '#9E9E9E',           # Gray
        }
        color = colors.get(obj.failure_type, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.failure_type
        )
    failure_type_badge.short_description = 'Failure Type'
    
    def retry_count_display(self, obj):
        """Display retry count with progress bar."""
        if obj.max_retries == 0:
            return format_html('<span style="color: #999;">N/A</span>')
        
        percentage = (obj.retry_count / obj.max_retries) * 100
        color = '#00C9A7' if percentage < 50 else ('#FFA500' if percentage < 80 else '#FF4D4F')
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<span style="font-weight: bold;">{}/{}</span>'
            '<div style="width: 60px; height: 8px; background: #eee; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background: {}; transition: width 0.3s;"></div>'
            '</div>'
            '</div>',
            obj.retry_count,
            obj.max_retries,
            min(percentage, 100),
            color
        )
    retry_count_display.short_description = 'Retries'
    
    def first_failed_display(self, obj):
        """Display first failed time with relative timestamp."""
        if not obj.first_failed_at:
            return '-'
        
        now = timezone.now()
        delta = now - obj.first_failed_at
        
        if delta < timedelta(hours=1):
            relative = f"{int(delta.total_seconds() / 60)} min ago"
        elif delta < timedelta(days=1):
            relative = f"{int(delta.total_seconds() / 3600)} hours ago"
        else:
            relative = f"{delta.days} days ago"
        
        return format_html(
            '<div>{}</div><small style="color: #999;">{}</small>',
            obj.first_failed_at.strftime('%Y-%m-%d %H:%M'),
            relative
        )
    first_failed_display.short_description = 'First Failed'
    
    def next_retry_display(self, obj):
        """Display next retry time or status."""
        if obj.status not in ('PENDING', 'RETRYING'):
            return format_html('<span style="color: #999;">-</span>')
        
        if not obj.next_retry_at:
            return format_html('<span style="color: #FFA500;">Queued</span>')
        
        now = timezone.now()
        if obj.next_retry_at <= now:
            return format_html('<span style="color: #00C9A7; font-weight: bold;">Ready</span>')
        
        delta = obj.next_retry_at - now
        if delta < timedelta(hours=1):
            time_str = f"in {int(delta.total_seconds() / 60)} min"
        elif delta < timedelta(days=1):
            time_str = f"in {int(delta.total_seconds() / 3600)} hours"
        else:
            time_str = f"in {delta.days} days"
        
        return format_html(
            '<div>{}</div><small style="color: #999;">{}</small>',
            obj.next_retry_at.strftime('%Y-%m-%d %H:%M'),
            time_str
        )
    next_retry_display.short_description = 'Next Retry'
    
    def actions_column(self, obj):
        """Quick action buttons."""
        if obj.status in ('RESOLVED', 'ABANDONED'):
            return '-'
        
        return format_html(
            '<a class="button" href="{}">Retry Now</a>',
            reverse('admin:retry_dlq_task', args=[obj.pk])
        )
    actions_column.short_description = 'Quick Actions'
    
    # ========================================================================
    # Bulk Actions
    # ========================================================================
    
    @admin.action(description='Retry selected tasks (normal priority)')
    def retry_selected_tasks(self, request, queryset):
        """Retry selected tasks with normal priority."""
        queryset = queryset.filter(status__in=['PENDING', 'RETRYING'])
        
        success_count = 0
        error_count = 0
        
        for record in queryset:
            try:
                result = DeadLetterQueueService._retry_task(record)
                if result['status'] == 'SUCCESS':
                    success_count += 1
                else:
                    error_count += 1
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error retrying task {record.task_id}: {e}", exc_info=True)
                error_count += 1
            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error retrying task {record.task_id}: {e}", exc_info=True)
                error_count += 1
            except (TypeError, ValueError, KeyError) as e:
                logger.error(f"Invalid task data for {record.task_id}: {e}", exc_info=True)
                error_count += 1
        
        if success_count > 0:
            self.message_user(
                request,
                f"Successfully queued {success_count} task(s) for retry",
                messages.SUCCESS
            )
        if error_count > 0:
            self.message_user(
                request,
                f"Failed to retry {error_count} task(s)",
                messages.ERROR
            )
    
    @admin.action(description='Retry with HIGH priority')
    def retry_with_high_priority(self, request, queryset):
        """Retry selected tasks with HIGH priority."""
        queryset = queryset.filter(status__in=['PENDING', 'RETRYING'])
        
        success_count = 0
        
        for record in queryset:
            try:
                from apps.core.services.task_priority_service import TaskPriority
                result = priority_service.requeue_task(
                    task_id=record.task_id,
                    task_name=record.task_name,
                    task_args=record.task_args,
                    task_kwargs=record.task_kwargs,
                    priority=TaskPriority.HIGH
                )
                if result['success']:
                    record.status = 'RETRYING'
                    record.save(update_fields=['status'])
                    success_count += 1
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error requeueing task {record.task_id} with HIGH priority: {e}", exc_info=True)
            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error requeueing task {record.task_id} with HIGH priority: {e}", exc_info=True)
            except (TypeError, ValueError, KeyError) as e:
                logger.error(f"Invalid task data for {record.task_id}: {e}", exc_info=True)
        
        self.message_user(
            request,
            f"Queued {success_count} task(s) for HIGH priority retry",
            messages.SUCCESS
        )
    
    @admin.action(description='Retry with CRITICAL priority')
    def retry_with_critical_priority(self, request, queryset):
        """Retry selected tasks with CRITICAL priority."""
        queryset = queryset.filter(status__in=['PENDING', 'RETRYING'])
        
        success_count = 0
        
        for record in queryset:
            try:
                from apps.core.services.task_priority_service import TaskPriority
                result = priority_service.requeue_task(
                    task_id=record.task_id,
                    task_name=record.task_name,
                    task_args=record.task_args,
                    task_kwargs=record.task_kwargs,
                    priority=TaskPriority.CRITICAL
                )
                if result['success']:
                    record.status = 'RETRYING'
                    record.save(update_fields=['status'])
                    success_count += 1
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error requeueing task {record.task_id} with CRITICAL priority: {e}", exc_info=True)
            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error requeueing task {record.task_id} with CRITICAL priority: {e}", exc_info=True)
            except (TypeError, ValueError, KeyError) as e:
                logger.error(f"Invalid task data for {record.task_id}: {e}", exc_info=True)
        
        self.message_user(
            request,
            f"Queued {success_count} task(s) for CRITICAL priority retry",
            messages.WARNING  # Warning to indicate this is high-impact
        )
    
    @admin.action(description='Abandon selected tasks')
    def abandon_selected_tasks(self, request, queryset):
        """Abandon selected tasks."""
        queryset = queryset.filter(status__in=['PENDING', 'RETRYING'])
        count = queryset.count()
        
        for record in queryset:
            record.mark_abandoned()
        
        self.message_user(
            request,
            f"Abandoned {count} task(s)",
            messages.WARNING
        )
    
    @admin.action(description='Export selected to CSV')
    def export_to_csv(self, request, queryset):
        """Export selected records to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="dlq_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Task Name', 'Status', 'Failure Type', 'Retry Count',
            'First Failed', 'Exception Type', 'Exception Message'
        ])
        
        for record in queryset:
            writer.writerow([
                record.task_name,
                record.status,
                record.failure_type,
                f"{record.retry_count}/{record.max_retries}",
                record.first_failed_at.strftime('%Y-%m-%d %H:%M:%S'),
                record.exception_type,
                record.exception_message[:100]
            ])
        
        return response
    
    # ========================================================================
    # Custom Admin Configuration
    # ========================================================================
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('business_unit')
    
    def has_add_permission(self, request):
        """Disable manual addition - records created automatically."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only allow deletion of abandoned or resolved records."""
        if obj and obj.status in ('ABANDONED', 'RESOLVED'):
            return True
        return False
