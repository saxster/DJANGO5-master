"""
Django Admin configuration for People Onboarding models.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    OnboardingRequest,
    CandidateProfile,
    DocumentSubmission,
    ApprovalWorkflow,
    BackgroundCheck,
    AccessProvisioning,
    TrainingAssignment,
    OnboardingTask,
)


@admin.register(OnboardingRequest)
class OnboardingRequestAdmin(admin.ModelAdmin):
    """Admin interface for OnboardingRequest"""
    list_display = ['request_number', 'person_type', 'current_state', 'start_date', 'created_at']
    list_filter = ['person_type', 'current_state', 'start_date']
    search_fields = ['request_number']
    readonly_fields = ['uuid', 'request_number', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'request_number', 'person_type', 'current_state')
        }),
        ('Relationships', {
            'fields': ('conversation_session', 'people', 'changeset', 'vendor')
        }),
        ('Dates', {
            'fields': ('start_date', 'expected_completion_date', 'actual_completion_date')
        }),
        ('Status Information', {
            'fields': ('rejection_reason', 'cancellation_reason', 'notes')
        }),
        ('Tenant Information', {
            'fields': ('client', 'bu')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    list_per_page = 50


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    """Admin interface for CandidateProfile"""
    list_display = ['full_name', 'primary_email', 'primary_phone', 'onboarding_request']
    search_fields = ['first_name', 'last_name', 'primary_email']
    readonly_fields = ['uuid']

    list_per_page = 50


@admin.register(DocumentSubmission)
class DocumentSubmissionAdmin(admin.ModelAdmin):
    """Admin interface for DocumentSubmission"""
    list_display = ['onboarding_request', 'document_type', 'verification_status', 'created_at']
    list_filter = ['document_type', 'verification_status']
    readonly_fields = ['uuid', 'file_size', 'file_hash']

    list_per_page = 50


@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    """Admin interface for ApprovalWorkflow"""
    list_display = ['onboarding_request', 'approval_level', 'approver', 'decision', 'sequence_number']
    list_filter = ['approval_level', 'decision']
    readonly_fields = ['uuid', 'request_sent_at']

    list_per_page = 50


@admin.register(BackgroundCheck)
class BackgroundCheckAdmin(admin.ModelAdmin):
    """Admin interface for BackgroundCheck"""
    list_display = ['onboarding_request', 'verification_type', 'status', 'result']
    list_filter = ['verification_type', 'status', 'result']
    readonly_fields = ['uuid']

    list_per_page = 50


@admin.register(AccessProvisioning)
class AccessProvisioningAdmin(admin.ModelAdmin):
    """Admin interface for AccessProvisioning"""
    list_display = ['onboarding_request', 'access_type', 'status', 'provisioned_at']
    list_filter = ['access_type', 'status']
    readonly_fields = ['uuid']

    list_per_page = 50


@admin.register(TrainingAssignment)
class TrainingAssignmentAdmin(admin.ModelAdmin):
    """Admin interface for TrainingAssignment"""
    list_display = ['onboarding_request', 'training_title', 'status', 'due_date']
    list_filter = ['training_type', 'status']
    readonly_fields = ['uuid']

    list_per_page = 50


@admin.register(OnboardingTask)
class OnboardingTaskAdmin(admin.ModelAdmin):
    """Admin interface for OnboardingTask"""
    list_display = ['onboarding_request', 'title', 'category', 'status', 'priority', 'assigned_to']
    list_filter = ['category', 'status', 'priority']
    readonly_fields = ['uuid']

    list_per_page = 50
