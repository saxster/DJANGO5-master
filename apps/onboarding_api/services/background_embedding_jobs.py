"""
Background embedding generation jobs with django_celery_beat integration.

Provides automated, scheduled embedding generation for knowledge base documents
with chunk-level caching and production-grade error handling.
"""
import logging
from typing import Dict, Any
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from apps.onboarding.models import (
    AuthoritativeKnowledge,
    AuthoritativeKnowledgeChunk,
    KnowledgeIngestionJob,
)

# Sprint 3: KnowledgeIngestionJob model now implemented ✅
# Stub class removed - using real model from apps.onboarding.models

logger = logging.getLogger(__name__)


class BackgroundEmbeddingProcessor:
    """
    Processes knowledge documents for embedding generation in background
    """

    def __init__(self):
        self.batch_size = getattr(settings, 'EMBEDDING_BATCH_SIZE', 10)
        self.max_retries = getattr(settings, 'EMBEDDING_MAX_RETRIES', 3)
        self.retry_delay_minutes = getattr(settings, 'EMBEDDING_RETRY_DELAY_MINUTES', 15)

    def process_pending_embeddings(self, limit: int = None) -> Dict[str, Any]:
        """
        Process pending embedding jobs

        Args:
            limit: Maximum number of documents to process

        Returns:
            Processing results
        """
        # Find documents without embeddings
        pending_docs = AuthoritativeKnowledge.objects.filter(
            content_vector__isnull=True,
            is_current=True
        ).order_by('cdtz')

        if limit:
            pending_docs = pending_docs[:limit]

        results = {
            'processed_count': 0,
            'success_count': 0,
            'error_count': 0,
            'errors': [],
            'processing_time_seconds': 0
        }

        start_time = time.time()

        for doc in pending_docs:
            try:
                success = self.generate_document_embeddings(doc)
                results['processed_count'] += 1

                if success:
                    results['success_count'] += 1
                else:
                    results['error_count'] += 1

            except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
                results['error_count'] += 1
                results['errors'].append({
                    'document_id': str(doc.knowledge_id),
                    'document_title': doc.document_title,
                    'error': str(e)
                })
                logger.error(f"Error processing document {doc.knowledge_id}: {str(e)}")

        results['processing_time_seconds'] = time.time() - start_time

        logger.info(f"Background embedding processing: {results['success_count']}/{results['processed_count']} successful")

        return results

    def generate_document_embeddings(self, document: AuthoritativeKnowledge) -> bool:
        """
        Generate embeddings for a single document with chunking

        Args:
            document: Knowledge document to process

        Returns:
            True if successful, False otherwise
        """
        try:
            from .knowledge import get_knowledge_service, get_document_chunker
            from .production_embeddings import get_production_embedding_service

            # Get services
            knowledge_service = get_knowledge_service()
            chunker = get_document_chunker()
            embedding_service = get_production_embedding_service()

            # For documents without full content, use content_summary for embedding
            content_to_embed = getattr(document, 'full_content', None) or document.content_summary

            if not content_to_embed:
                logger.warning(f"No content to embed for document {document.knowledge_id}")
                return False

            # Create document metadata
            doc_metadata = {
                'title': document.document_title,
                'organization': document.source_organization,
                'authority_level': document.authority_level,
                'jurisdiction': getattr(document, 'jurisdiction', ''),
                'industry': getattr(document, 'industry', ''),
                'language': getattr(document, 'language', 'en')
            }

            # Chunk the document
            chunks = chunker.chunk_document(content_to_embed, doc_metadata)

            if not chunks:
                logger.warning(f"No chunks generated for document {document.knowledge_id}")
                return False

            # Generate embeddings for chunks
            chunk_texts = [chunk['text'] for chunk in chunks]
            embedding_results = embedding_service.generate_batch_embeddings(chunk_texts)

            # Store chunks with embeddings
            with transaction.atomic():
                # Delete existing chunks
                AuthoritativeKnowledgeChunk.objects.filter(knowledge=document).delete()

                # Create new chunks
                for i, (chunk, embedding_result) in enumerate(zip(chunks, embedding_results)):
                    # Handle both old and new embedding service interfaces
                    if hasattr(embedding_result, 'embedding'):
                        vector = embedding_result.embedding
                        embedding_metadata = {
                            'provider': embedding_result.provider,
                            'model': embedding_result.model,
                            'cost_cents': embedding_result.cost_cents
                        }
                    else:
                        vector = embedding_result
                        embedding_metadata = {'provider': 'legacy'}

                    AuthoritativeKnowledgeChunk.objects.create(
                        knowledge=document,
                        chunk_index=i,
                        content_text=chunk['text'],
                        content_vector=vector,
                        tags={
                            **chunk.get('tags', {}),
                            'embedding_metadata': embedding_metadata
                        },
                        is_current=True,
                        authority_level=document.authority_level,
                        source_organization=document.source_organization
                    )

                # Update document with document-level embedding (average of chunks)
                if embedding_results and hasattr(embedding_results[0], 'embedding'):
                    # Calculate document-level embedding as average of chunk embeddings
                    import numpy as np

                    chunk_vectors = [result.embedding for result in embedding_results if hasattr(result, 'embedding')]
                    if chunk_vectors:
                        doc_vector = np.mean(chunk_vectors, axis=0).tolist()
                        document.content_vector = doc_vector

                document.last_verified = timezone.now()
                document.save()

            logger.info(f"Generated embeddings for document {document.knowledge_id} ({len(chunks)} chunks)")
            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error generating embeddings for document {document.knowledge_id}: {str(e)}")
            return False

    def process_ingestion_jobs(self, limit: int = None) -> Dict[str, Any]:
        """
        Process pending knowledge ingestion jobs

        Args:
            limit: Maximum number of jobs to process

        Returns:
            Processing results
        """
        # Find pending ingestion jobs
        pending_jobs = KnowledgeIngestionJob.objects.filter(
            status__in=[
                KnowledgeIngestionJob.StatusChoices.QUEUED,
                KnowledgeIngestionJob.StatusChoices.FAILED  # Retry failed jobs
            ]
        ).order_by('cdtz')

        if limit:
            pending_jobs = pending_jobs[:limit]

        results = {
            'processed_jobs': 0,
            'successful_jobs': 0,
            'failed_jobs': 0,
            'total_chunks_created': 0,
            'total_embeddings_generated': 0,
            'errors': []
        }

        for job in pending_jobs:
            try:
                job_result = self.process_single_ingestion_job(job)
                results['processed_jobs'] += 1

                if job_result['success']:
                    results['successful_jobs'] += 1
                    results['total_chunks_created'] += job_result.get('chunks_created', 0)
                    results['total_embeddings_generated'] += job_result.get('embeddings_generated', 0)
                else:
                    results['failed_jobs'] += 1
                    results['errors'].append({
                        'job_id': str(job.job_id),
                        'source_url': job.source_url,
                        'error': job_result.get('error', 'Unknown error')
                    })

            except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
                results['failed_jobs'] += 1
                results['errors'].append({
                    'job_id': str(job.job_id),
                    'source_url': job.source_url,
                    'error': str(e)
                })
                logger.error(f"Error processing ingestion job {job.job_id}: {str(e)}")

        logger.info(f"Processed {results['processed_jobs']} ingestion jobs: {results['successful_jobs']} successful, {results['failed_jobs']} failed")

        return results

    def process_single_ingestion_job(self, job: KnowledgeIngestionJob) -> Dict[str, Any]:
        """
        Process a single knowledge ingestion job

        Args:
            job: Ingestion job to process

        Returns:
            Processing result
        """
        result = {
            'success': False,
            'chunks_created': 0,
            'embeddings_generated': 0,
            'error': None,
            'processing_time_ms': 0
        }

        start_time = time.time()

        try:
            # Update job status
            job.update_status(KnowledgeIngestionJob.StatusChoices.FETCHING)

            # Fetch document content
            from .knowledge import get_document_fetcher, get_document_parser

            fetcher = get_document_fetcher()
            parser = get_document_parser()

            # Fetch document
            fetch_result = fetcher.fetch_document(job.source_url, job.source)

            job.record_timing('fetch', int((time.time() - start_time) * 1000))
            job.update_status(KnowledgeIngestionJob.StatusChoices.PARSING)

            # Parse document
            parse_start = time.time()
            parsed_doc = parser.parse_document(
                fetch_result['content'],
                fetch_result['content_type'],
                fetch_result['metadata']
            )

            job.record_timing('parse', int((time.time() - parse_start) * 1000))
            job.update_status(KnowledgeIngestionJob.StatusChoices.CHUNKING)

            # Create knowledge document if not exists
            if not job.document:
                knowledge_doc = AuthoritativeKnowledge.objects.create(
                    source_organization=job.source.name,
                    document_title=parsed_doc.get('title', 'Imported Document'),
                    authority_level=job.source.source_type,
                    content_summary=parsed_doc['full_text'][:500] + '...' if len(parsed_doc['full_text']) > 500 else parsed_doc['full_text'],
                    publication_date=timezone.now(),
                    source_url=job.source_url,
                    doc_checksum=fetch_result['content_hash'],
                    jurisdiction=job.source.jurisdiction,
                    industry=', '.join(job.source.industry_tags),
                    language=job.source.language,
                    is_current=True
                )
                job.document = knowledge_doc
                job.save()

            # Generate embeddings
            chunk_start = time.time()
            success = self.generate_document_embeddings(job.document)

            job.record_timing('embedding', int((time.time() - chunk_start) * 1000))

            if success:
                # Count created chunks and embeddings
                chunks_created = AuthoritativeKnowledgeChunk.objects.filter(
                    knowledge=job.document
                ).count()

                embeddings_generated = AuthoritativeKnowledgeChunk.objects.filter(
                    knowledge=job.document,
                    content_vector__isnull=False
                ).count()

                job.chunks_created = chunks_created
                job.embeddings_generated = embeddings_generated
                job.update_status(KnowledgeIngestionJob.StatusChoices.READY)

                result.update({
                    'success': True,
                    'chunks_created': chunks_created,
                    'embeddings_generated': embeddings_generated
                })

            else:
                job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, "Embedding generation failed")
                result['error'] = "Embedding generation failed"

        except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, str(e))
            result['error'] = str(e)

        result['processing_time_ms'] = int((time.time() - start_time) * 1000)
        job.processing_duration_ms = result['processing_time_ms']
        job.save()

        return result

    def cleanup_failed_jobs(self, older_than_hours: int = 24) -> Dict[str, Any]:
        """
        Clean up old failed jobs

        Args:
            older_than_hours: Remove failed jobs older than this many hours

        Returns:
            Cleanup results
        """
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)

        failed_jobs = KnowledgeIngestionJob.objects.filter(
            status=KnowledgeIngestionJob.StatusChoices.FAILED,
            cdtz__lt=cutoff_time
        )

        cleanup_count = failed_jobs.count()
        failed_jobs.delete()

        logger.info(f"Cleaned up {cleanup_count} failed ingestion jobs older than {older_than_hours} hours")

        return {
            'cleaned_up_count': cleanup_count,
            'cutoff_time': cutoff_time.isoformat()
        }


class EmbeddingQueueManager:
    """
    Manages queuing and prioritization of embedding generation jobs
    """

    def __init__(self):
        self.priority_weights = {
            'official': 1.0,
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4
        }

    def queue_document_for_embedding(
        self,
        document: AuthoritativeKnowledge,
        priority: str = 'medium',
        force_regenerate: bool = False
    ) -> bool:
        """
        Queue a document for background embedding generation

        Args:
            document: Document to queue
            priority: Processing priority
            force_regenerate: Force regeneration even if embeddings exist

        Returns:
            True if queued successfully
        """
        try:
            # Check if already has embeddings (unless force regenerate)
            if not force_regenerate and document.content_vector is not None:
                logger.info(f"Document {document.knowledge_id} already has embeddings, skipping")
                return True

            # Create or update ingestion job
            from apps.onboarding.models import KnowledgeSource

            # Get or create a source for manual queuing
            manual_source, created = KnowledgeSource.objects.get_or_create(
                name='Manual Embedding Queue',
                source_type=KnowledgeSource.SourceTypeChoices.INTERNAL,
                defaults={
                    'fetch_policy': KnowledgeSource.FetchPolicyChoices.MANUAL,
                    'is_active': True
                }
            )

            # Create ingestion job
            job = KnowledgeIngestionJob.objects.create(
                source=manual_source,
                document=document,
                status=KnowledgeIngestionJob.StatusChoices.QUEUED,
                source_url=document.source_url or 'manual://queue',
                created_by_id=1,  # System user
                processing_config={
                    'priority': priority,
                    'force_regenerate': force_regenerate,
                    'queued_at': timezone.now().isoformat()
                }
            )

            logger.info(f"Queued document {document.knowledge_id} for embedding generation (job: {job.job_id})")
            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error queuing document for embedding: {str(e)}")
            return False

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current embedding queue status"""
        from django.db.models import Count

        # Count jobs by status
        status_counts = KnowledgeIngestionJob.objects.values('status').annotate(
            count=Count('job_id')
        )

        status_summary = {item['status']: item['count'] for item in status_counts}

        # Count documents without embeddings
        docs_without_embeddings = AuthoritativeKnowledge.objects.filter(
            content_vector__isnull=True,
            is_current=True
        ).count()

        # Calculate processing estimates
        queued_count = status_summary.get(KnowledgeIngestionJob.StatusChoices.QUEUED, 0)
        avg_processing_time = self._get_average_processing_time()

        return {
            'queue_summary': status_summary,
            'documents_without_embeddings': docs_without_embeddings,
            'queued_jobs': queued_count,
            'estimated_completion_time_minutes': queued_count * avg_processing_time,
            'last_updated': timezone.now().isoformat()
        }

    def _get_average_processing_time(self) -> float:
        """Get average processing time in minutes"""
        completed_jobs = KnowledgeIngestionJob.objects.filter(
            status=KnowledgeIngestionJob.StatusChoices.READY,
            processing_duration_ms__isnull=False
        ).order_by('-cdtz')[:50]  # Last 50 jobs

        if not completed_jobs:
            return 2.0  # Default estimate: 2 minutes

        total_time_ms = sum(job.processing_duration_ms for job in completed_jobs)
        avg_time_ms = total_time_ms / len(completed_jobs)

        return avg_time_ms / (1000 * 60)  # Convert to minutes

    def prioritize_queue(self) -> Dict[str, Any]:
        """
        Re-prioritize pending jobs based on authority level and age

        Returns:
            Prioritization results
        """
        queued_jobs = KnowledgeIngestionJob.objects.filter(
            status=KnowledgeIngestionJob.StatusChoices.QUEUED
        ).select_related('document')

        prioritized_count = 0

        for job in queued_jobs:
            if job.document:
                # Calculate priority score
                authority_weight = self.priority_weights.get(job.document.authority_level, 0.5)

                # Age factor (older jobs get higher priority)
                age_hours = (timezone.now() - job.cdtz).total_seconds() / 3600
                age_weight = min(1.0, age_hours / 24)  # Max weight after 24 hours

                priority_score = (authority_weight * 0.7) + (age_weight * 0.3)

                # Update processing config with priority score
                config = job.processing_config or {}
                config['priority_score'] = priority_score
                config['prioritized_at'] = timezone.now().isoformat()
                job.processing_config = config
                job.save()

                prioritized_count += 1

        logger.info(f"Re-prioritized {prioritized_count} queued embedding jobs")

        return {
            'prioritized_count': prioritized_count,
            'queue_length': queued_jobs.count()
        }


# Celery task functions (to be registered with django_celery_beat)
def process_embedding_queue_task():
    """
    Celery task for processing embedding queue
    """
    processor = BackgroundEmbeddingProcessor()
    return processor.process_pending_embeddings(limit=10)


def process_ingestion_jobs_task():
    """
    Celery task for processing knowledge ingestion jobs
    """
    processor = BackgroundEmbeddingProcessor()
    return processor.process_ingestion_jobs(limit=5)


def cleanup_old_jobs_task():
    """
    Celery task for cleaning up old failed jobs
    """
    processor = BackgroundEmbeddingProcessor()
    return processor.cleanup_failed_jobs(older_than_hours=48)


def prioritize_embedding_queue_task():
    """
    Celery task for re-prioritizing embedding queue
    """
    queue_manager = EmbeddingQueueManager()
    return queue_manager.prioritize_queue()


# Enhanced Celery Beat Schedule
ENHANCED_EMBEDDING_BEAT_SCHEDULE = {
    'process-embedding-queue': {
        'task': 'apps.onboarding_api.services.background_embedding_jobs.process_embedding_queue_task',
        'schedule': 300.0,  # Every 5 minutes
        'options': {
            'queue': 'embeddings',
            'routing_key': 'embeddings.process'
        }
    },
    'process-ingestion-jobs': {
        'task': 'apps.onboarding_api.services.background_embedding_jobs.process_ingestion_jobs_task',
        'schedule': 600.0,  # Every 10 minutes
        'options': {
            'queue': 'ingestion',
            'routing_key': 'ingestion.process'
        }
    },
    'cleanup-old-embedding-jobs': {
        'task': 'apps.onboarding_api.services.background_embedding_jobs.cleanup_old_jobs_task',
        'schedule': 3600.0,  # Every hour
        'options': {
            'queue': 'maintenance',
            'routing_key': 'maintenance.cleanup'
        }
    },
    'prioritize-embedding-queue': {
        'task': 'apps.onboarding_api.services.background_embedding_jobs.prioritize_embedding_queue_task',
        'schedule': 1800.0,  # Every 30 minutes
        'options': {
            'queue': 'maintenance',
            'routing_key': 'maintenance.prioritize'
        }
    }
}


# Service factory functions
def get_background_embedding_processor() -> BackgroundEmbeddingProcessor:
    """Get background embedding processor instance"""
    return BackgroundEmbeddingProcessor()


def get_embedding_queue_manager() -> EmbeddingQueueManager:
    """Get embedding queue manager instance"""
    return EmbeddingQueueManager()


# Administrative functions for manual control
def queue_all_documents_for_embedding(force_regenerate: bool = False) -> Dict[str, Any]:
    """
    Queue all knowledge documents for embedding generation

    Args:
        force_regenerate: Force regeneration even if embeddings exist

    Returns:
        Queuing results
    """
    queue_manager = get_embedding_queue_manager()

    if force_regenerate:
        documents = AuthoritativeKnowledge.objects.filter(is_current=True)
    else:
        documents = AuthoritativeKnowledge.objects.filter(
            content_vector__isnull=True,
            is_current=True
        )

    queued_count = 0
    error_count = 0

    for doc in documents:
        try:
            priority = 'high' if doc.authority_level in ['high', 'official'] else 'medium'
            success = queue_manager.queue_document_for_embedding(
                doc, priority, force_regenerate
            )
            if success:
                queued_count += 1
            else:
                error_count += 1
        except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            error_count += 1
            logger.error(f"Error queuing document {doc.knowledge_id}: {str(e)}")

    return {
        'queued_count': queued_count,
        'error_count': error_count,
        'total_documents': documents.count(),
        'force_regenerate': force_regenerate
    }


def get_embedding_processing_status() -> Dict[str, Any]:
    """
    Get comprehensive status of embedding processing

    Returns:
        Complete status including queue, progress, and performance metrics
    """
    queue_manager = get_embedding_queue_manager()
    processor = get_background_embedding_processor()

    queue_status = queue_manager.get_queue_status()

    # Add performance metrics
    from django.db.models import Avg

    recent_jobs = KnowledgeIngestionJob.objects.filter(
        status=KnowledgeIngestionJob.StatusChoices.READY,
        cdtz__gte=timezone.now() - timedelta(hours=24)
    )

    performance_metrics = {
        'jobs_completed_24h': recent_jobs.count(),
        'avg_processing_time_minutes': 0.0,
        'total_chunks_created_24h': sum(job.chunks_created for job in recent_jobs),
        'total_embeddings_generated_24h': sum(job.embeddings_generated for job in recent_jobs)
    }

    if recent_jobs.exists():
        avg_duration = recent_jobs.aggregate(
            avg_duration=Avg('processing_duration_ms')
        )['avg_duration']
        if avg_duration:
            performance_metrics['avg_processing_time_minutes'] = avg_duration / (1000 * 60)

    return {
        'queue_status': queue_status,
        'performance_metrics': performance_metrics,
        'system_health': {
            'embedding_service_available': True,  # Would check actual service health
            'queue_processing_active': queue_status['queued_jobs'] > 0,
            'last_successful_job': recent_jobs.order_by('-cdtz').first().cdtz.isoformat() if recent_jobs.exists() else None
        }
    }