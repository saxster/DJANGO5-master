"""
Knowledge Admin Module

Admin interfaces for Authoritative Knowledge Base management with chunking and vector embeddings.

Migrated from apps/onboarding/admin.py
Date: 2025-09-30
"""
from .base import *


class AuthoritativeKnowledgeChunkInline(admin.TabularInline):
    """Inline admin for viewing knowledge chunks within a knowledge document"""
    model = om.AuthoritativeKnowledgeChunk
    extra = 0
    readonly_fields = ('chunk_id', 'sequence_number')
    fields = ('chunk_id', 'sequence_number', 'content', 'chunk_type')


@admin.register(om.AuthoritativeKnowledge)
class AuthoritativeKnowledgeAdmin(admin.ModelAdmin):
    """Django admin for AuthoritativeKnowledge model with document versioning and verification"""
    list_display = ('knowledge_id', 'document_title', 'source_organization', 'authority_level', 'is_current', 'cdtz')
    list_filter = ('authority_level', 'is_current', 'language', 'industry', 'cdtz')
    search_fields = ('knowledge_id', 'document_title', 'source_organization', 'content_summary')
    readonly_fields = ('knowledge_id', 'last_verified', 'cdtz', 'mdtz', 'cuser', 'muser')
    inlines = [AuthoritativeKnowledgeChunkInline]

    fieldsets = (
        ('Document Information', {
            'fields': ('knowledge_id', 'source_organization', 'document_title', 'document_version', 'authority_level')
        }),
        ('Content', {
            'fields': ('content_summary', 'content_vector', 'tags')
        }),
        ('Source Details', {
            'fields': ('source_url', 'doc_checksum', 'jurisdiction', 'industry', 'language')
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
    """Django admin for AuthoritativeKnowledgeChunk model with vector embedding management"""
    list_display = ('chunk_id', 'knowledge', 'chunk_type', 'sequence_number', 'vector_embedding_status')
    list_filter = ('chunk_type', 'knowledge__knowledge_type')
    search_fields = ('chunk_id', 'knowledge__title', 'content')
    readonly_fields = ('chunk_id', 'vector_embedding_computed')

    fieldsets = (
        ('Basic Information', {
            'fields': ('chunk_id', 'knowledge', 'chunk_type', 'sequence_number')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Vector Embedding', {
            'fields': ('vector_embedding', 'vector_embedding_computed'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )

    def vector_embedding_status(self, obj):
        """Display vector embedding computation status"""
        return "Computed" if obj.vector_embedding_computed else "Pending"
    vector_embedding_status.short_description = "Embedding Status"
