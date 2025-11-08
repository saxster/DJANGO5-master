"""
Changeset Admin Module

Admin interfaces for AI-generated changeset management with rollback capabilities.

Migrated from apps/onboarding/admin.py
Date: 2025-09-30
"""
from .base import (
    BaseResource,
    BaseFieldSet2,
    admin,
    resources,
    fields,
    wg,
    ImportExportModelAdmin,
    tm,
    clean_point_field,
    clean_string,
    pm,
    BtForm,
    ShiftForm,
    Bt,
    Shift,
    TypeAssist,
    GeofenceMaster,
    Bu,
    get_or_create_none_typeassist,
    get_or_create_none_bv,
    get_or_create_none_people,
    utils,
    ValidationError,
    OperationalError,
    ProgrammingError,
    DatabaseError,
    re,
    isnan,
    EnabledTypeAssistWidget,
    bulk_create_geofence,
    Job,
)


# Exception for LLM service errors (if not defined elsewhere)
try:
    from apps.core_onboarding.services.llm import LLMServiceException
except ImportError:
    class LLMServiceException(Exception):
        """LLM service exception placeholder"""
        pass


class AIChangeRecordInline(admin.TabularInline):
    """Inline admin for viewing change records within a changeset"""
    model = om.AIChangeRecord
    extra = 0
    readonly_fields = ('record_id', 'sequence_order', 'model_name', 'app_label', 'object_id', 'action', 'status')
    fields = ('record_id', 'sequence_order', 'model_name', 'object_id', 'action', 'status')
    can_delete = False


@admin.register(om.AIChangeSet)
class AIChangeSetAdmin(admin.ModelAdmin):
    """Django admin for AIChangeSet model with rollback functionality"""
    list_display = ('changeset_id', 'conversation_session', 'status', 'total_changes', 'successful_changes', 'applied_at', 'can_rollback_display')
    list_filter = ('status', 'applied_at', 'rolled_back_at')
    search_fields = ('changeset_id', 'conversation_session__session_id', 'description')
    readonly_fields = ('changeset_id', 'can_rollback', 'get_rollback_complexity')
    inlines = [AIChangeRecordInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('changeset_id', 'conversation_session', 'status', 'description')
        }),
        ('Change Summary', {
            'fields': ('total_changes', 'successful_changes', 'failed_changes')
        }),
        ('Approval & Rollback', {
            'fields': ('approved_by', 'applied_at', 'rolled_back_by', 'rolled_back_at', 'rollback_reason')
        }),
        ('Rollback Status', {
            'fields': ('can_rollback', 'get_rollback_complexity'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )

    def can_rollback_display(self, obj):
        """Display rollback availability status"""
        return obj.can_rollback()
    can_rollback_display.boolean = True
    can_rollback_display.short_description = "Rollback Available"

    actions = ['rollback_changesets']

    list_per_page = 50

    def rollback_changesets(self, request, queryset):
        """Admin action to rollback selected changesets"""
        rollback_count = 0
        for changeset in queryset:
            if changeset.can_rollback():
                try:
                    from apps.onboarding_api.integration.mapper import IntegrationAdapter
                    adapter = IntegrationAdapter()
                    adapter.rollback_changeset(
                        changeset=changeset,
                        rollback_reason=f"Admin rollback by {request.user}",
                        rollback_user=request.user
                    )
                    rollback_count += 1
                except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
                    self.message_user(request, f"Failed to rollback changeset {changeset.changeset_id}: {str(e)}", level='ERROR')

        if rollback_count > 0:
            self.message_user(request, f"Successfully rolled back {rollback_count} changesets", level='SUCCESS')

    rollback_changesets.short_description = "Rollback selected changesets"


@admin.register(om.AIChangeRecord)
class AIChangeRecordAdmin(admin.ModelAdmin):
    list_per_page = 50
    """Django admin for AIChangeRecord model"""
    list_display = ('record_id', 'changeset', 'model_name', 'object_id', 'action', 'status', 'sequence_order')
    list_filter = ('action', 'status', 'model_name', 'app_label')
    search_fields = ('record_id', 'changeset__changeset_id', 'object_id')
    readonly_fields = ('record_id', 'changeset', 'model_name', 'app_label', 'object_id')

    fieldsets = (
        ('Basic Information', {
            'fields': ('record_id', 'changeset', 'sequence_order')
        }),
        ('Target Object', {
            'fields': ('model_name', 'app_label', 'object_id', 'action', 'status')
        }),
        ('Change Data', {
            'fields': ('before_state', 'after_state', 'field_changes'),
            'classes': ('collapse',)
        }),
        ('Rollback Information', {
            'fields': ('has_dependencies', 'rollback_attempted_at', 'rollback_success'),
            'classes': ('collapse',)
        })
    )
