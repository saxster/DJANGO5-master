"""
Phase 2 Celery tasks for Enhanced Conversational Onboarding
FACADE FILE - Imports from focused modules for backward compatibility

This file maintains backward compatibility with existing imports.
All task implementations have been moved to focused modules:
- conversation_orchestration.py - Enhanced LLM orchestration chains
- knowledge_management.py - Document embedding and knowledge base
- document_ingestion.py - Production document pipeline with SSRF protection
- maintenance_tasks.py - Cleanup, monitoring, and verification

New code should import directly from the focused modules.
"""

# Conversation orchestration tasks
from background_tasks.onboarding_phase2.conversation_orchestration import (
    process_conversation_step_enhanced,
    retrieve_knowledge_task,
    maker_generate_task,
    checker_validate_task,
    compute_consensus_task,
    persist_recommendations_task,
    notify_completion_task,
)

# Knowledge management tasks
from background_tasks.onboarding_phase2.knowledge_management import (
    embed_knowledge_document_task,
    batch_embed_documents_task,
)

# Document ingestion tasks (includes SSRF protection)
from background_tasks.onboarding_phase2.document_ingestion import (
    validate_document_url,
    ingest_document,
    reembed_document,
    refresh_documents,
    retire_document,
    batch_retire_stale_documents,
)

# Maintenance tasks
from background_tasks.onboarding_phase2.maintenance_tasks import (
    cleanup_old_traces_task,
    validate_knowledge_freshness_task,
    nightly_knowledge_maintenance,
    weekly_knowledge_verification,
)

__all__ = [
    # Conversation orchestration
    'process_conversation_step_enhanced',
    'retrieve_knowledge_task',
    'maker_generate_task',
    'checker_validate_task',
    'compute_consensus_task',
    'persist_recommendations_task',
    'notify_completion_task',
    # Knowledge management
    'embed_knowledge_document_task',
    'batch_embed_documents_task',
    # Document ingestion
    'validate_document_url',
    'ingest_document',
    'reembed_document',
    'refresh_documents',
    'retire_document',
    'batch_retire_stale_documents',
    # Maintenance
    'cleanup_old_traces_task',
    'validate_knowledge_freshness_task',
    'nightly_knowledge_maintenance',
    'weekly_knowledge_verification',
]
