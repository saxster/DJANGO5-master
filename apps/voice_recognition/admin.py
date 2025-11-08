"""
Voice Recognition Admin Interface

Admin configuration for voice biometrics and enrollment policies.

Following CLAUDE.md:
- Rule #7: <150 lines
- Admin UI for operational management

Sprint 4.4: Voice Enrollment Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
from apps.voice_recognition.models import (
    VoiceEmbedding,
    VoiceBiometricConfig,
    VoiceVerificationLog
)
from apps.voice_recognition.enrollment_policy import EnrollmentPolicy


@admin.register(EnrollmentPolicy)
class EnrollmentPolicyAdmin(admin.ModelAdmin):
    """Admin interface for enrollment policies."""

    list_display = [
        'policy_name',
        'is_active',
        'min_device_trust_score',
        'location_requirement',
        'require_supervisor_approval',
        'min_voice_samples'
    ]

    list_filter = [
        'is_active',
        'location_requirement',
        'require_supervisor_approval',
        'require_device_registration'
    ]

    search_fields = ['policy_name']

    fieldsets = (
        ('Basic Information', {
            'fields': ('policy_name', 'is_active')
        }),
        ('Device Security', {
            'fields': (
                'min_device_trust_score',
                'require_device_registration'
            )
        }),
        ('Location Requirements', {
            'fields': (
                'location_requirement',
                'approved_networks',
                'approved_sites'
            )
        }),
        ('Approval Workflow', {
            'fields': (
                'require_supervisor_approval',
                'supervisor_approval_timeout_hours'
            )
        }),
        ('Re-enrollment Controls', {
            'fields': (
                'min_reenrollment_interval_days',
                'force_reenrollment_after_days'
            )
        }),
        ('Step-up Authentication', {
            'fields': (
                'require_mfa_for_remote_enrollment',
                'require_face_biometrics'
            )
        }),
        ('Sample Collection', {
            'fields': (
                'min_voice_samples',
                'max_voice_samples',
                'min_voice_quality_score'
            )
        }),
    )

    readonly_fields = ['cdtz', 'mdtz']

    list_per_page = 50

    def save_model(self, request, obj, form, change):
        """Validate policy before saving."""
        obj.full_clean()  # Trigger model validation
        super().save_model(request, obj, form, change)


@admin.register(VoiceEmbedding)
class VoiceEmbeddingAdmin(admin.ModelAdmin):
    """Admin interface for voice embeddings."""

    list_display = [
        'user',
        'is_validated',
        'voice_confidence',
        'extraction_timestamp',
        'language_code'
    ]

    list_filter = [
        'is_validated',
        'is_primary',
        'language_code',
        'extraction_timestamp'
    ]

    search_fields = ['user__peoplename', 'user__email']

    readonly_fields = [
        'embedding_vector',
        'extraction_timestamp',
        'source_audio_hash',
        'validation_score'
    ]

    list_per_page = 50

    def has_add_permission(self, request):
        """Prevent manual creation (should be via enrollment API)."""
        return False


@admin.register(VoiceVerificationLog)
class VoiceVerificationLogAdmin(admin.ModelAdmin):
    """Admin interface for verification logs."""

    list_display = [
        'user',
        'result',
        'confidence_score',
        'verification_timestamp',
        'spoof_detected'
    ]

    list_filter = [
        'result',
        'spoof_detected',
        'verification_timestamp'
    ]

    search_fields = ['user__peoplename', 'user__email']

    readonly_fields = [
        'user',
        'result',
        'confidence_score',
        'verification_timestamp',
        'audio_quality_score',
        'liveness_score',
        'fraud_risk_score'
    ]

    list_per_page = 50

    def has_add_permission(self, request):
        """Prevent manual creation (auto-generated)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Read-only (audit trail)."""
        return False
