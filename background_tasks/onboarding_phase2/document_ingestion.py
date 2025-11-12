"""
Document Ingestion Pipeline Tasks
Production-grade document ingestion: fetch→parse→chunk→embed→index
Includes SSRF protection and content sanitization
"""
import logging
import traceback
import time
import socket
import ipaddress
from typing import Dict, Any, List
from urllib.parse import urlparse

from celery import shared_task
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


# =============================================================================
# SECURITY VALIDATION HELPERS
# =============================================================================

# SSRF Protection: Blocked IP ranges
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local (AWS metadata)
    ipaddress.ip_network('10.0.0.0/8'),       # Private
    ipaddress.ip_network('172.16.0.0/12'),    # Private
    ipaddress.ip_network('192.168.0.0/16'),   # Private
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
    ipaddress.ip_network('fc00::/7'),         # IPv6 private
]

ALLOWED_URL_SCHEMES = ['https']  # Only HTTPS allowed for production


def validate_document_url(url: str) -> bool:
    """
    Validate URL for SSRF protection before fetching documents.

    Prevents access to:
    - Private IP ranges (10.0.0.0/8, 192.168.0.0/16, etc.)
    - Loopback addresses (127.0.0.0/8)
    - AWS/GCP metadata endpoints (169.254.169.254)
    - Link-local addresses

    Args:
        url: URL to validate

    Returns:
        True if URL is safe

    Raises:
        ValidationError: If URL is potentially malicious
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    # Parse URL
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Invalid URL format: {str(e)}")

    # Check scheme
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise ValidationError(
            f"URL scheme '{parsed.scheme}' not allowed. Only {ALLOWED_URL_SCHEMES} permitted."
        )

    # Check hostname exists
    if not parsed.hostname:
        raise ValidationError("URL must have a valid hostname")

    # Resolve hostname to IP address
    try:
        ip_address = socket.gethostbyname(parsed.hostname)
        task_logger.debug(f"URL {parsed.hostname} resolves to {ip_address}")
    except socket.gaierror as e:
        raise ValidationError(f"Cannot resolve hostname '{parsed.hostname}': {str(e)}")

    # Check if IP is in blocked ranges
    try:
        ip_obj = ipaddress.ip_address(ip_address)

        for blocked_range in BLOCKED_IP_RANGES:
            if ip_obj in blocked_range:
                task_logger.warning(
                    f"SSRF attempt blocked: URL {url} resolves to blocked IP {ip_address} "
                    f"in range {blocked_range}"
                )
                raise ValidationError(
                    f"Access denied: URL resolves to private/internal IP address. "
                    f"This may be an attempt to access internal resources."
                )
    except ValueError as e:
        raise ValidationError(f"Invalid IP address resolved: {str(e)}")

    task_logger.info(f"URL validation passed for: {url}")
    return True


# =============================================================================
# DOCUMENT INGESTION TASKS
# =============================================================================


@shared_task(bind=True, name='ingest_document')
def ingest_document(self, job_id: str):
    """
    Complete document ingestion pipeline: fetch→parse→chunk→embed→index
    """
    task_logger.info(f"Starting document ingestion for job {job_id}")

    try:
        from apps.core_onboarding.models import KnowledgeIngestionJob, AuthoritativeKnowledge, KnowledgeReview
        from apps.onboarding_api.services.knowledge import (
            get_document_fetcher,
            get_document_parser,
            get_document_chunker,
            get_embedding_generator,
            get_vector_store,
            ContentSanitizationService
        )

        # Get ingestion job
        job = KnowledgeIngestionJob.objects.get(job_id=job_id)
        start_time = time.time()

        # Stage 1: Fetch document
        task_logger.info(f"Stage 1: Fetching document from {job.source_url}")
        job.update_status(KnowledgeIngestionJob.StatusChoices.FETCHING)

        # SECURITY: Validate URL for SSRF protection
        try:
            validate_document_url(job.source_url)
        except ValidationError as e:
            task_logger.error(f"URL validation failed for {job.source_url}: {str(e)}")
            job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, str(e))
            job.source.fetch_error_count += 1
            job.source.save()
            raise

        fetcher = get_document_fetcher()
        fetch_start = time.time()
        fetch_result = fetcher.fetch_document(job.source_url, job.source)
        fetch_time = int((time.time() - fetch_start) * 1000)
        job.record_timing('fetch_ms', fetch_time)

        # Stage 2: Sanitize content (SECURITY CRITICAL)
        task_logger.info(f"Stage 2: Sanitizing content (security validation)")

        sanitizer = ContentSanitizationService()
        sanitize_start = time.time()

        try:
            sanitized_content, sanitization_report = sanitizer.sanitize_document_content(
                content=fetch_result['content'],
                mime_type=fetch_result['content_type'],
                source_url=job.source_url
            )
            sanitize_time = int((time.time() - sanitize_start) * 1000)
            job.record_timing('sanitize_ms', sanitize_time)

            task_logger.info(
                f"Content sanitized successfully: {sanitization_report['original_size_bytes']} → "
                f"{sanitization_report['sanitized_size_bytes']} bytes"
            )

            # Use sanitized content for parsing
            fetch_result['content'] = sanitized_content
            fetch_result['metadata']['sanitization_report'] = sanitization_report

        except (ValueError, TypeError, AttributeError) as sanitize_error:
            task_logger.error(
                f"Content sanitization failed (validation error): {str(sanitize_error)}",
                exc_info=True
            )
            job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, str(sanitize_error))
            job.source.fetch_error_count += 1
            job.source.save()
            raise
        except DATABASE_EXCEPTIONS as sanitize_error:
            task_logger.error(
                f"Content sanitization failed (database error): {str(sanitize_error)}",
                exc_info=True
            )
            job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, str(sanitize_error))
            job.source.fetch_error_count += 1
            job.source.save()
            raise

        # Stage 3: Parse document
        task_logger.info(f"Stage 3: Parsing document ({fetch_result['content_type']})")
        job.update_status(KnowledgeIngestionJob.StatusChoices.PARSING)

        parser = get_document_parser()
        parse_start = time.time()
        parse_result = parser.parse_document(
            fetch_result['content'],
            fetch_result['content_type'],
            fetch_result['metadata']
        )
        parse_time = int((time.time() - parse_start) * 1000)
        job.record_timing('parse_ms', parse_time)

        # Stage 4: Create knowledge document
        document_info = parse_result.get('document_info', {})
        document = AuthoritativeKnowledge.objects.create(
            source_organization=job.source.name,
            document_title=document_info.get('title', f"Document from {job.source.name}"),
            document_version=document_info.get('version', '1.0'),
            authority_level='medium',  # Default, can be updated later
            content_summary=parse_result['full_text'][:500] + "..." if len(parse_result['full_text']) > 500 else parse_result['full_text'],
            publication_date=timezone.now(),
            source_url=job.source_url,
            doc_checksum=fetch_result['content_hash'],
            jurisdiction=job.source.jurisdiction,
            industry=','.join(job.source.industry_tags) if job.source.industry_tags else '',
            language=job.source.language,
            tags={
                'ingestion_job_id': str(job.job_id),
                'fetch_metadata': fetch_result['metadata'],
                'parse_metadata': parse_result.get('parser_metadata', {}),
                'source_type': job.source.source_type
            },
            ingestion_version=1,
            is_current=False  # SECURITY: Will be set to True ONLY after two-person approval
        )

        # Link document to job
        job.document = document
        job.save()

        # PUBLISH GATE ENFORCEMENT: Create draft review requiring two-person approval
        # This ensures NO document is published without maker-checker review
        draft_review = KnowledgeReview.objects.create(
            document=document,
            status='draft',
            notes='Auto-generated review for ingested document. Requires two-person approval before publication.',
            provenance_data={
                'ingestion_job_id': str(job.job_id),
                'ingested_at': timezone.now().isoformat(),
                'ingested_by': job.created_by.email if job.created_by else 'system',
                'source': job.source.name,
                'source_type': job.source.source_type,
                'publish_gate': 'enforced'
            }
        )

        task_logger.info(
            f"PUBLISH GATE: Created draft review {draft_review.review_id} for document {document.knowledge_id}. "
            f"Requires two-person approval before publication."
        )

        # Stage 5: Chunk document
        task_logger.info(f"Stage 5: Chunking document into segments")
        job.update_status(KnowledgeIngestionJob.StatusChoices.CHUNKING)

        chunker = get_document_chunker()
        chunk_start = time.time()

        document_metadata = {
            'title': document.document_title,
            'organization': document.source_organization,
            'authority_level': document.authority_level,
            'version': document.document_version
        }

        chunks = chunker.chunk_document(
            parse_result['full_text'],
            document_metadata,
            parse_result  # Pass parsed data for enhanced chunking
        )
        chunk_time = int((time.time() - chunk_start) * 1000)
        job.record_timing('chunk_ms', chunk_time)

        # Stage 6: Generate embeddings and index
        task_logger.info(f"Stage 6: Generating embeddings for {len(chunks)} chunks")
        job.update_status(KnowledgeIngestionJob.StatusChoices.EMBEDDING)

        embedding_generator = get_embedding_generator()
        vector_store = get_vector_store()
        embed_start = time.time()

        # Generate embeddings for chunks
        embedded_chunks = []
        embeddings_generated = 0

        for i, chunk in enumerate(chunks):
            try:
                # Generate embedding
                vector = embedding_generator.generate_embedding(chunk['text'])
                chunk['vector'] = vector
                embedded_chunks.append(chunk)
                embeddings_generated += 1

                # Update progress periodically
                if (i + 1) % 10 == 0:
                    task_logger.info(f"Generated embeddings for {i + 1}/{len(chunks)} chunks")

            except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
                task_logger.warning(f"Failed to generate embedding for chunk {i}: {str(e)}")
                chunk['vector'] = None
                embedded_chunks.append(chunk)

        # Store chunks in vector store
        success = vector_store.store_document_chunks(str(document.knowledge_id), embedded_chunks)

        embed_time = int((time.time() - embed_start) * 1000)
        job.record_timing('embed_ms', embed_time)

        if not success:
            raise Exception("Failed to store chunks in vector store")

        # Update job completion
        total_time = int((time.time() - start_time) * 1000)
        job.status = KnowledgeIngestionJob.StatusChoices.READY
        job.chunks_created = len(chunks)
        job.embeddings_generated = embeddings_generated
        job.processing_duration_ms = total_time
        job.save()

        # Update source statistics
        job.source.total_documents_fetched += 1
        job.source.last_successful_fetch = timezone.now()
        job.source.fetch_error_count = 0  # Reset error count on success
        job.source.save()

        task_logger.info(f"Successfully ingested document {document.knowledge_id} in {total_time}ms")

        return {
            'status': 'completed',
            'job_id': str(job.job_id),
            'document_id': str(document.knowledge_id),
            'chunks_created': len(chunks),
            'embeddings_generated': embeddings_generated,
            'processing_time_ms': total_time,
            'completed_at': timezone.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Document ingestion failed for job {job_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # Update job status
        try:
            job = KnowledgeIngestionJob.objects.get(job_id=job_id)
            job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, str(e))

            # Update source error count
            job.source.fetch_error_count += 1
            job.source.save()

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as update_error:
            task_logger.error(f"Failed to update job status: {str(update_error)}")

        return {
            'status': 'failed',
            'job_id': job_id,
            'error': str(e)
        }


@shared_task(bind=True, name='reembed_document')
def reembed_document(self, knowledge_id: str, processing_config: Dict[str, Any] = None):
    """
    Re-embed existing document with updated embeddings
    """
    task_logger.info(f"Re-embedding document {knowledge_id}")

    try:
        from apps.core_onboarding.models import AuthoritativeKnowledge
        from apps.onboarding_api.services.knowledge import (
            get_document_chunker,
            get_embedding_generator,
            get_vector_store
        )

        # Get document
        document = AuthoritativeKnowledge.objects.get(knowledge_id=knowledge_id)
        start_time = time.time()

        # Use existing content or fetch fresh content
        content = document.content_summary  # Fallback - would normally fetch full content

        # Re-chunk with potentially updated configuration
        config = processing_config or {}
        chunk_size = config.get('chunk_size', 1000)
        chunk_overlap = config.get('chunk_overlap', 200)

        chunker = get_document_chunker(chunk_size, chunk_overlap)
        document_metadata = {
            'title': document.document_title,
            'organization': document.source_organization,
            'authority_level': document.authority_level,
            'version': document.document_version
        }

        # Re-chunk document
        chunks = chunker.chunk_document(content, document_metadata)

        # Generate new embeddings
        embedding_generator = get_embedding_generator()
        vector_store = get_vector_store()

        embedded_chunks = []
        embeddings_generated = 0

        for chunk in chunks:
            try:
                vector = embedding_generator.generate_embedding(chunk['text'])
                chunk['vector'] = vector
                embedded_chunks.append(chunk)
                embeddings_generated += 1
            except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
                task_logger.warning(f"Failed to generate embedding for chunk: {str(e)}")
                chunk['vector'] = None
                embedded_chunks.append(chunk)

        # Store new chunks (replaces old ones)
        success = vector_store.store_document_chunks(knowledge_id, embedded_chunks)

        if not success:
            raise Exception("Failed to store re-embedded chunks")

        # Update document metadata
        document.last_verified = timezone.now()
        document.ingestion_version += 1
        document.tags['reembedded_at'] = timezone.now().isoformat()
        document.tags['reembedding_config'] = config
        document.save()

        total_time = int((time.time() - start_time) * 1000)

        task_logger.info(f"Successfully re-embedded document {knowledge_id} in {total_time}ms")

        return {
            'status': 'completed',
            'knowledge_id': knowledge_id,
            'chunks_created': len(chunks),
            'embeddings_generated': embeddings_generated,
            'processing_time_ms': total_time,
            'ingestion_version': document.ingestion_version
        }

    except AuthoritativeKnowledge.DoesNotExist:
        error_msg = f"Document {knowledge_id} not found for re-embedding"
        task_logger.error(error_msg)
        return {'status': 'not_found', 'error': error_msg}

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Re-embedding failed for {knowledge_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, name='refresh_documents')
def refresh_documents(self, source_ids: List[str] = None, force_refresh: bool = False):
    """
    Refresh documents by checking for updates at source URLs
    """
    task_logger.info(f"Refreshing documents (force={force_refresh})")

    try:
        from apps.core_onboarding.models import KnowledgeSource, AuthoritativeKnowledge, KnowledgeIngestionJob
        from apps.onboarding_api.services.knowledge import get_document_fetcher
        from datetime import timedelta

        # Get sources to refresh
        sources = KnowledgeSource.objects.filter(is_active=True)
        if source_ids:
            sources = sources.filter(source_id__in=source_ids)

        # Only check sources that haven't been checked recently (unless forced)
        if not force_refresh:
            recent_threshold = timezone.now() - timedelta(hours=6)
            sources = sources.exclude(last_fetch_attempt__gte=recent_threshold)

        refreshed_count = 0
        updated_count = 0
        error_count = 0

        fetcher = get_document_fetcher()

        for source in sources:
            try:
                # Update last attempt timestamp
                source.last_fetch_attempt = timezone.now()
                source.save()

                # Get documents from this source
                documents = AuthoritativeKnowledge.objects.filter(
                    source_organization=source.name,
                    source_url__isnull=False,
                    is_current=True
                )

                for document in documents:
                    try:
                        # Check if document needs refresh
                        if _document_needs_refresh(document, force_refresh):
                            # SECURITY: Validate URL for SSRF protection
                            try:
                                validate_document_url(document.source_url)
                            except ValidationError as e:
                                task_logger.error(
                                    f"URL validation failed for document {document.knowledge_id} "
                                    f"({document.source_url}): {str(e)}"
                                )
                                error_count += 1
                                continue  # Skip this document

                            # Fetch current version
                            fetch_result = fetcher.fetch_document(document.source_url, source)

                            # Check if content changed
                            if fetch_result['content_hash'] != document.doc_checksum:
                                # Content changed - create new ingestion job
                                job = KnowledgeIngestionJob.objects.create(
                                    source=source,
                                    source_url=document.source_url,
                                    created_by_id=1,  # System user
                                    processing_config={'refresh': True, 'original_doc_id': str(document.knowledge_id)}
                                )

                                # Queue ingestion of updated document
                                ingest_document.delay(str(job.job_id))
                                updated_count += 1

                                task_logger.info(f"Queued refresh for updated document: {document.document_title}")

                            else:
                                # Content unchanged - just update verification timestamp
                                document.last_verified = timezone.now()
                                document.save()

                        refreshed_count += 1

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as doc_error:
                        task_logger.warning(f"Failed to refresh document {document.knowledge_id}: {str(doc_error)}")
                        error_count += 1

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as source_error:
                task_logger.warning(f"Failed to refresh source {source.source_id}: {str(source_error)}")
                error_count += 1

        task_logger.info(f"Document refresh completed: {refreshed_count} checked, {updated_count} updated, {error_count} errors")

        return {
            'status': 'completed',
            'documents_checked': refreshed_count,
            'documents_updated': updated_count,
            'errors': error_count,
            'completed_at': timezone.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Document refresh failed: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


def _document_needs_refresh(document, force: bool = False) -> bool:
    """Check if document needs to be refreshed"""
    if force:
        return True

    # Check if last verified more than 7 days ago
    if document.last_verified:
        from datetime import timedelta
        stale_threshold = timezone.now() - timedelta(days=7)
        return document.last_verified < stale_threshold

    return True  # Never verified, needs refresh


@shared_task(bind=True, name='retire_document')
def retire_document(self, knowledge_id: str, retirement_reason: str = "Manual retirement"):
    """
    Retire a document by marking it as not current and removing embeddings
    """
    task_logger.info(f"Retiring document {knowledge_id}")

    try:
        from apps.core_onboarding.models import AuthoritativeKnowledge
        from apps.onboarding_api.services.knowledge import get_vector_store

        # Get document
        document = AuthoritativeKnowledge.objects.get(knowledge_id=knowledge_id)

        # Mark as not current
        document.is_current = False
        document.tags['retired_at'] = timezone.now().isoformat()
        document.tags['retirement_reason'] = retirement_reason
        document.save()

        # Retire all chunks
        chunk_count = document.chunks.update(is_current=False)

        # Remove embeddings
        vector_store = get_vector_store()
        vector_store.delete_embedding(knowledge_id)

        task_logger.info(f"Successfully retired document {knowledge_id} with {chunk_count} chunks")

        return {
            'status': 'completed',
            'knowledge_id': knowledge_id,
            'chunks_retired': chunk_count,
            'retirement_reason': retirement_reason,
            'retired_at': timezone.now().isoformat()
        }

    except AuthoritativeKnowledge.DoesNotExist:
        error_msg = f"Document {knowledge_id} not found for retirement"
        task_logger.error(error_msg)
        return {'status': 'not_found', 'error': error_msg}

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Document retirement failed for {knowledge_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, name='batch_retire_stale_documents')
def batch_retire_stale_documents(self, max_age_days: int = 1095):
    """
    Batch retire documents older than specified age (default 3 years)
    """
    task_logger.info(f"Batch retiring documents older than {max_age_days} days")

    try:
        from apps.core_onboarding.models import AuthoritativeKnowledge
        from datetime import timedelta

        cutoff_date = timezone.now() - timedelta(days=max_age_days)

        # Find stale documents
        stale_documents = AuthoritativeKnowledge.objects.filter(
            publication_date__lt=cutoff_date,
            is_current=True
        )

        retired_count = 0
        for document in stale_documents:
            try:
                retire_result = retire_document(
                    str(document.knowledge_id),
                    f"Automatic retirement: older than {max_age_days} days"
                )
                if retire_result.get('status') == 'completed':
                    retired_count += 1
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                task_logger.warning(f"Failed to retire document {document.knowledge_id}: {str(e)}")

        task_logger.info(f"Batch retirement completed: {retired_count} documents retired")

        return {
            'status': 'completed',
            'documents_retired': retired_count,
            'cutoff_date': cutoff_date.isoformat(),
            'max_age_days': max_age_days
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Batch retirement failed: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


# Define exception classes for imports
class IntegrationException(Exception):
    """Integration exception placeholder"""
    pass


class LLMServiceException(Exception):
    """LLM service exception placeholder"""
    pass


# Define DATABASE_EXCEPTIONS placeholder
DATABASE_EXCEPTIONS = (DatabaseError, IntegrityError)
