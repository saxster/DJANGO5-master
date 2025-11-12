"""
Knowledge Admin Module

Admin interfaces for Authoritative Knowledge Base management with chunking and vector embeddings.

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
from apps.core_onboarding import models as om


class AuthoritativeKnowledgeChunkInline(admin.TabularInline):
    """Inline admin for viewing knowledge chunks within a knowledge document"""
    model = om.AuthoritativeKnowledgeChunk
    extra = 0
    readonly_fields = ('chunk_id', 'chunk_index')
    fields = ('chunk_id', 'chunk_index', 'content_text', 'is_current')


@admin.register(om.AuthoritativeKnowledge)
class AuthoritativeKnowledgeAdmin(admin.ModelAdmin):
    list_per_page = 50
    """Django admin for AuthoritativeKnowledge model with document versioning and verification"""
    list_display = ('knowledge_id', 'document_title', 'source_organization', 'authority_level', 'is_current', 'cdtz')
    list_filter = ('authority_level', 'is_current', 'cdtz')
    search_fields = ('knowledge_id', 'document_title', 'source_organization', 'content_summary')
    readonly_fields = ('knowledge_id', 'last_verified', 'cdtz', 'mdtz', 'cuser', 'muser')
    inlines = [AuthoritativeKnowledgeChunkInline]

    fieldsets = (
        ('Document Information', {
            'fields': ('knowledge_id', 'source_organization', 'document_title', 'document_version', 'authority_level')
        }),
        ('Content', {
            'fields': ('content_summary', 'content_vector')
        }),
        ('Validity', {
            'fields': ('is_current', 'publication_date', 'last_verified')
        }),
        ('Timestamps', {
            'fields': ('cdtz', 'mdtz', 'cuser', 'muser'),
            'classes': ('collapse',)
        })
    )


@admin.register(om.AuthoritativeKnowledgeChunk)
class AuthoritativeKnowledgeChunkAdmin(admin.ModelAdmin):
    list_per_page = 50
    """Django admin for AuthoritativeKnowledgeChunk model with vector embedding management"""
    list_display = ('chunk_id', 'knowledge', 'chunk_index', 'is_current', 'vector_status')
    list_filter = ('is_current', 'last_verified')
    search_fields = ('chunk_id', 'knowledge__document_title', 'content_text')
    readonly_fields = ('chunk_id', 'last_verified')

    fieldsets = (
        ('Basic Information', {
            'fields': ('chunk_id', 'knowledge', 'chunk_index', 'is_current')
        }),
        ('Content', {
            'fields': ('content_text',)
        }),
        ('Vector Embedding', {
            'fields': ('content_vector',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('tags', 'last_verified'),
            'classes': ('collapse',)
        })
    )

    def vector_status(self, obj):
        """Display vector embedding computation status"""
        return "Computed" if obj.content_vector else "Pending"
    vector_status.short_description = "Embedding Status"
