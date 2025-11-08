"""
Knowledge Management API endpoints for production-grade knowledge base
Staff-only endpoints for curating, versioning, and managing authoritative knowledge

SECURITY NOTE (.claude/rules.md Rule #3):
- CSRF protection enabled via Django's default CSRF middleware
- All mutation endpoints (POST/PUT/DELETE) require valid CSRF tokens
- csrf_exempt REMOVED from all endpoints (was security violation)
- Staff-only access enforced via StaffRequiredMixin
- For non-browser API clients, use Session authentication with CSRF or migrate to JWT
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator

from apps.onboarding.models import (
    KnowledgeSource,
    KnowledgeIngestionJob,
    AuthoritativeKnowledge,
    KnowledgeReview,
)
from apps.core_onboarding.services.knowledge.exceptions import (
    DocumentParseError,
    SecurityError
)

# Sprint 3: All knowledge models now implemented ✅
# Stub classes removed - using real models from apps.onboarding.models

logger = logging.getLogger(__name__)


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only staff users can access knowledge management endpoints"""

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or
            self.request.user.capabilities.get('knowledge_curator', False) or
            self.request.user.capabilities.get('admin', False)
        )

    def handle_no_permission(self):
        return JsonResponse({
            'error': 'Access denied',
            'message': 'Knowledge management requires staff privileges or knowledge_curator role'
        }, status=403)


# =============================================================================
# KNOWLEDGE SOURCE MANAGEMENT
# =============================================================================


@method_decorator([login_required], name='dispatch')
class KnowledgeSourceAPIView(StaffRequiredMixin, View):
    """
    CRUD operations for knowledge sources (allowlisted only)

    Security: CSRF protection enabled for all mutations
    """

    def get(self, request, source_id=None):
        """List knowledge sources or get specific source"""
        try:
            if source_id:
                try:
                    source = KnowledgeSource.objects.get(source_id=source_id)
                    return JsonResponse({
                        'source': self._serialize_source(source),
                        'status': 'success'
                    })
                except KnowledgeSource.DoesNotExist:
                    return JsonResponse({'error': 'Source not found'}, status=404)

            # List all sources with pagination
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', 20)), 100)

            sources = KnowledgeSource.objects.all().order_by('-cdtz')

            # Apply filters
            source_type = request.GET.get('source_type')
            if source_type:
                sources = sources.filter(source_type=source_type)

            is_active = request.GET.get('is_active')
            if is_active is not None:
                sources = sources.filter(is_active=is_active.lower() == 'true')

            paginator = Paginator(sources, page_size)
            page_obj = paginator.get_page(page)

            return JsonResponse({
                'sources': [self._serialize_source(source) for source in page_obj],
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                },
                'status': 'success'
            })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error in knowledge source GET: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Internal server error',
                'correlation_id': correlation_id
            }, status=500)

    def post(self, request):
        """Create new knowledge source"""
        try:
            data = json.loads(request.body)

            # Validate required fields
            required_fields = ['name', 'source_type']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({'error': f'Missing required field: {field}'}, status=400)

            # Validate allowlisted source
            if not self._is_source_allowlisted(data):
                return JsonResponse({
                    'error': 'Source not allowlisted',
                    'message': 'Only allowlisted sources can be created for security'
                }, status=403)

            # Create source
            source = KnowledgeSource.objects.create(
                name=data['name'],
                source_type=data['source_type'],
                base_url=data.get('base_url', ''),
                auth_config=data.get('auth_config', {}),
                jurisdiction=data.get('jurisdiction', ''),
                industry_tags=data.get('industry_tags', []),
                language=data.get('language', 'en'),
                fetch_policy=data.get('fetch_policy', 'manual'),
                is_active=data.get('is_active', True)
            )

            logger.info(f"Created knowledge source: {source.name} by {request.user.email}")

            return JsonResponse({
                'source': self._serialize_source(source),
                'status': 'created'
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error creating knowledge source: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to create source',
                'correlation_id': correlation_id
            }, status=500)

    def put(self, request, source_id):
        """Update knowledge source"""
        try:
            source = KnowledgeSource.objects.get(source_id=source_id)
            data = json.loads(request.body)

            # Validate allowlisted source for URL changes
            if 'base_url' in data and not self._is_source_allowlisted(data):
                return JsonResponse({
                    'error': 'Updated source not allowlisted',
                    'message': 'URL changes must maintain allowlist compliance'
                }, status=403)

            # Update fields
            updateable_fields = [
                'name', 'source_type', 'base_url', 'auth_config',
                'jurisdiction', 'industry_tags', 'language', 'fetch_policy', 'is_active'
            ]

            for field in updateable_fields:
                if field in data:
                    setattr(source, field, data[field])

            source.save()

            logger.info(f"Updated knowledge source {source_id} by {request.user.email}")

            return JsonResponse({
                'source': self._serialize_source(source),
                'status': 'updated'
            })

        except KnowledgeSource.DoesNotExist:
            return JsonResponse({'error': 'Source not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error updating knowledge source: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to update source',
                'correlation_id': correlation_id
            }, status=500)

    def delete(self, request, source_id):
        """Delete knowledge source (soft delete by deactivating)"""
        try:
            source = KnowledgeSource.objects.get(source_id=source_id)

            # Soft delete by deactivating
            source.is_active = False
            source.save()

            logger.info(f"Deactivated knowledge source {source_id} by {request.user.email}")

            return JsonResponse({
                'message': 'Source deactivated successfully',
                'status': 'deactivated'
            })

        except KnowledgeSource.DoesNotExist:
            return JsonResponse({'error': 'Source not found'}, status=404)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error deactivating knowledge source: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to deactivate source',
                'correlation_id': correlation_id
            }, status=500)

    def _serialize_source(self, source: KnowledgeSource) -> Dict[str, Any]:
        """Serialize knowledge source for API response"""
        return {
            'source_id': str(source.source_id),
            'name': source.name,
            'source_type': source.source_type,
            'base_url': source.base_url,
            'jurisdiction': source.jurisdiction,
            'industry_tags': source.industry_tags,
            'language': source.language,
            'fetch_policy': source.fetch_policy,
            'is_active': source.is_active,
            'last_fetch_attempt': source.last_fetch_attempt.isoformat() if source.last_fetch_attempt else None,
            'last_successful_fetch': source.last_successful_fetch.isoformat() if source.last_successful_fetch else None,
            'total_documents_fetched': source.total_documents_fetched,
            'fetch_error_count': source.fetch_error_count,
            'created_at': source.cdtz.isoformat(),
            'updated_at': source.mdtz.isoformat()
        }

    def _is_source_allowlisted(self, data: Dict[str, Any]) -> bool:
        """Check if source is allowlisted for security"""
        base_url = data.get('base_url', '')
        if not base_url:
            return True  # No URL means manual upload

        from django.conf import settings
        allowed_domains = getattr(settings, 'KB_ALLOWED_SOURCES', [])

        from urllib.parse import urlparse
        domain = urlparse(base_url).netloc.lower()

        return any(allowed_domain in domain for allowed_domain in allowed_domains)


# =============================================================================
# DOCUMENT INGESTION MANAGEMENT
# =============================================================================


@method_decorator([login_required], name='dispatch')
class IngestionJobAPIView(StaffRequiredMixin, View):
    """
    Manage document ingestion jobs

    Security: CSRF protection enabled for all mutations
    """

    def get(self, request, job_id=None):
        """Get ingestion job status or list jobs"""
        try:
            if job_id:
                try:
                    job = KnowledgeIngestionJob.objects.get(job_id=job_id)
                    return JsonResponse({
                        'job': self._serialize_job(job),
                        'status': 'success'
                    })
                except KnowledgeIngestionJob.DoesNotExist:
                    return JsonResponse({'error': 'Job not found'}, status=404)

            # List jobs with pagination and filtering
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', 20)), 100)

            jobs = KnowledgeIngestionJob.objects.all().order_by('-cdtz')

            # Apply filters
            status_filter = request.GET.get('status')
            if status_filter:
                jobs = jobs.filter(status=status_filter)

            source_id = request.GET.get('source_id')
            if source_id:
                jobs = jobs.filter(source__source_id=source_id)

            paginator = Paginator(jobs, page_size)
            page_obj = paginator.get_page(page)

            return JsonResponse({
                'jobs': [self._serialize_job(job) for job in page_obj],
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count
                },
                'status': 'success'
            })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error in ingestion job GET: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Internal server error',
                'correlation_id': correlation_id
            }, status=500)

    def post(self, request):
        """Start new ingestion job"""
        try:
            data = json.loads(request.body)

            # Validate required fields
            if 'source_id' not in data or 'source_url' not in data:
                return JsonResponse({
                    'error': 'Missing required fields: source_id, source_url'
                }, status=400)

            # Get source
            try:
                source = KnowledgeSource.objects.get(source_id=data['source_id'])
            except KnowledgeSource.DoesNotExist:
                return JsonResponse({'error': 'Knowledge source not found'}, status=404)

            if not source.is_active:
                return JsonResponse({'error': 'Knowledge source is not active'}, status=400)

            # Create ingestion job
            job = KnowledgeIngestionJob.objects.create(
                source=source,
                source_url=data['source_url'],
                created_by=request.user,
                processing_config=data.get('processing_config', {}),
                status=KnowledgeIngestionJob.StatusChoices.QUEUED
            )

            # Queue background task
            from background_tasks.onboarding_tasks_phase2 import ingest_document
            task_result = ingest_document.delay(str(job.job_id))

            logger.info(f"Started ingestion job {job.job_id} for {data['source_url']} by {request.user.email}")

            return JsonResponse({
                'job': self._serialize_job(job),
                'task_id': task_result.id,
                'status': 'queued'
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error starting ingestion job: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to start ingestion',
                'correlation_id': correlation_id
            }, status=500)

    def _serialize_job(self, job: KnowledgeIngestionJob) -> Dict[str, Any]:
        """Serialize ingestion job for API response"""
        return {
            'job_id': str(job.job_id),
            'source': {
                'source_id': str(job.source.source_id),
                'name': job.source.name,
                'source_type': job.source.source_type
            },
            'source_url': job.source_url,
            'status': job.status,
            'error_log': job.error_log,
            'timings': job.timings,
            'chunks_created': job.chunks_created,
            'embeddings_generated': job.embeddings_generated,
            'processing_duration_ms': job.processing_duration_ms,
            'created_by': job.created_by.email,
            'created_at': job.cdtz.isoformat(),
            'document': {
                'knowledge_id': str(job.document.knowledge_id),
                'title': job.document.document_title
            } if job.document else None
        }


# =============================================================================
# DOCUMENT MANAGEMENT
# =============================================================================


@method_decorator([login_required], name='dispatch')
class DocumentManagementAPIView(StaffRequiredMixin, View):
    """
    Document management operations (re-embed, publish)

    Security: CSRF protection enabled for all mutations
    """

    def post(self, request, doc_id, action):
        """Handle document actions (embed, publish)"""
        try:
            document = AuthoritativeKnowledge.objects.get(knowledge_id=doc_id)
        except AuthoritativeKnowledge.DoesNotExist:
            return JsonResponse({'error': 'Document not found'}, status=404)

        if action == 'embed':
            return self._handle_reembed(request, document)
        elif action == 'publish':
            return self._handle_publish(request, document)
        else:
            return JsonResponse({'error': f'Unknown action: {action}'}, status=400)

    def _handle_reembed(self, request, document: AuthoritativeKnowledge):
        """Re-embed document with new embeddings"""
        try:
            data = json.loads(request.body) if request.body else {}

            # Queue re-embedding task
            from background_tasks.onboarding_tasks_phase2 import reembed_document
            task_result = reembed_document.delay(
                str(document.knowledge_id),
                data.get('processing_config', {})
            )

            logger.info(f"Started re-embedding for document {document.knowledge_id} by {request.user.email}")

            return JsonResponse({
                'document_id': str(document.knowledge_id),
                'task_id': task_result.id,
                'status': 'reembedding_queued',
                'message': 'Re-embedding task started successfully'
            })

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error starting re-embedding: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to start re-embedding',
                'correlation_id': correlation_id
            }, status=500)

    def _handle_publish(self, request, document: AuthoritativeKnowledge):
        """Publish document after two-person approval (SECURITY CRITICAL)"""
        try:
            # ENFORCED: Two-person approval gate
            approved_review = KnowledgeReview.objects.filter(
                document=document,
                status='approved',
                approved_for_publication=True,
                first_reviewer__isnull=False,
                second_reviewer__isnull=False,
                first_reviewed_at__isnull=False,
                second_reviewed_at__isnull=False
            ).first()

            if not approved_review:
                # Find incomplete reviews for helpful error message
                incomplete_review = KnowledgeReview.objects.filter(document=document).first()
                if incomplete_review:
                    status = incomplete_review.status
                    error_details = {
                        'draft': 'Review not started - awaiting first reviewer',
                        'first_review': 'First review in progress',
                        'second_review': 'Second review in progress - awaiting approval',
                        'rejected': 'Document was rejected - revision required'
                    }.get(status, 'Unknown status')

                    return JsonResponse({
                        'error': 'Two-person approval required for publication',
                        'message': f'Current status: {error_details}',
                        'current_status': status,
                        'requires': 'Both first and second reviewer approval'
                    }, status=400)

                return JsonResponse({
                    'error': 'Document not approved for publication',
                    'message': 'Document requires two-person approval before publication'
                }, status=400)

            # Publish gate passed - mark document as published/current
            with transaction.atomic():
                document.is_current = True
                document.last_verified = datetime.now()
                document.save()

                # Update all chunks as current
                document.chunks.update(is_current=True, last_verified=datetime.now())

            logger.info(
                f"Published document {document.knowledge_id} by {request.user.email} "
                f"(approved by {approved_review.first_reviewer.email} and {approved_review.second_reviewer.email})"
            )

            return JsonResponse({
                'document_id': str(document.knowledge_id),
                'status': 'published',
                'approved_by': {
                    'first_reviewer': approved_review.first_reviewer.email,
                    'first_reviewed_at': approved_review.first_reviewed_at.isoformat(),
                    'second_reviewer': approved_review.second_reviewer.email,
                    'second_reviewed_at': approved_review.second_reviewed_at.isoformat()
                },
                'provenance': approved_review.provenance_data,
                'message': 'Document published successfully after two-person approval'
            })

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error publishing document: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to publish document',
                'correlation_id': correlation_id
            }, status=500)


# =============================================================================
# KNOWLEDGE SEARCH API
# =============================================================================


@method_decorator([login_required], name='dispatch')
class KnowledgeSearchAPIView(StaffRequiredMixin, View):
    """
    Advanced knowledge search with filtering

    Security: CSRF protection enabled (read-only but follows consistent policy)
    """

    def get(self, request):
        """Search knowledge with advanced filtering"""
        try:
            # Get search parameters
            query = request.GET.get('q', '')
            jurisdiction = request.GET.get('jurisdiction', '')
            industry = request.GET.get('industry', '')
            authority_level = request.GET.get('authority_level', '')
            language = request.GET.get('language', '')
            max_results = min(int(request.GET.get('max_results', 10)), 50)
            search_mode = request.GET.get('mode', 'semantic')  # 'semantic', 'text', 'hybrid'

            if not query:
                return JsonResponse({'error': 'Search query required'}, status=400)

            # Get knowledge service
            knowledge_service = get_knowledge_service()

            # Build filters
            filters = {}
            if jurisdiction:
                filters['jurisdiction'] = jurisdiction.split(',')
            if industry:
                filters['industry'] = industry.split(',')
            if authority_level:
                filters['authority_level'] = authority_level.split(',')
            if language:
                filters['language'] = language

            # Perform search based on mode
            if search_mode == 'semantic':
                results = knowledge_service.search_with_reranking(
                    query=query,
                    top_k=max_results,
                    authority_filter=filters.get('authority_level')
                )
            elif search_mode == 'text':
                results = knowledge_service.search_knowledge(
                    query=query,
                    top_k=max_results,
                    authority_filter=filters.get('authority_level')
                )
            else:  # hybrid
                # Combine semantic and text search
                semantic_results = knowledge_service.search_with_reranking(
                    query=query,
                    top_k=max_results // 2,
                    authority_filter=filters.get('authority_level')
                )
                text_results = knowledge_service.search_knowledge(
                    query=query,
                    top_k=max_results // 2,
                    authority_filter=filters.get('authority_level')
                )

                # Merge and deduplicate
                seen_ids = set()
                results = []
                for result_set in [semantic_results, text_results]:
                    for result in result_set:
                        result_id = result.get('knowledge_id', result.get('source_id'))
                        if result_id not in seen_ids:
                            results.append(result)
                            seen_ids.add(result_id)

            # Apply additional filters
            filtered_results = self._apply_additional_filters(results, filters)

            # Enhance results with metadata
            enhanced_results = []
            for result in filtered_results[:max_results]:
                enhanced_result = self._enhance_search_result(result)
                enhanced_results.append(enhanced_result)

            logger.info(f"Knowledge search by {request.user.email}: query='{query}', results={len(enhanced_results)}")

            return JsonResponse({
                'results': enhanced_results,
                'search_metadata': {
                    'query': query,
                    'mode': search_mode,
                    'filters_applied': filters,
                    'total_results': len(enhanced_results),
                    'search_timestamp': datetime.now().isoformat()
                },
                'status': 'success'
            })

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error in knowledge search: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Search failed',
                'correlation_id': correlation_id
            }, status=500)

    def _apply_additional_filters(self, results: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Apply additional filters to search results"""
        filtered = results

        # Filter by jurisdiction
        if filters.get('jurisdiction'):
            jurisdictions = filters['jurisdiction']
            filtered = [r for r in filtered if any(j in r.get('metadata', {}).get('jurisdiction', '') for j in jurisdictions)]

        # Filter by industry
        if filters.get('industry'):
            industries = filters['industry']
            filtered = [r for r in filtered if any(i in r.get('metadata', {}).get('industry', '') for i in industries)]

        # Filter by language
        if filters.get('language'):
            lang = filters['language']
            filtered = [r for r in filtered if r.get('metadata', {}).get('language', 'en') == lang]

        return filtered

    def _enhance_search_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance search result with additional metadata"""
        enhanced = result.copy()

        # Add search result metadata
        enhanced['result_metadata'] = {
            'search_rank': enhanced.get('similarity_score', enhanced.get('relevance_score', 0.0)),
            'result_type': 'chunk' if 'chunk_id' in enhanced else 'document',
            'has_high_authority': enhanced.get('metadata', {}).get('authority_level') in ['high', 'official'],
            'is_recent': self._is_recent_publication(enhanced.get('metadata', {}).get('publication_date')),
            'estimated_tokens': len(enhanced.get('content', enhanced.get('content_summary', ''))) // 4
        }

        return enhanced

    def _is_recent_publication(self, pub_date_str: Optional[str]) -> bool:
        """Check if publication is recent (within 2 years)"""
        if not pub_date_str:
            return False

        try:
            pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
            age_days = (datetime.now() - pub_date.replace(tzinfo=None)).days
            return age_days < 730  # 2 years
        except (ValueError, TypeError, AttributeError) as e:
            return False


# =============================================================================
# DOCUMENT REVIEW WORKFLOW
# =============================================================================


@method_decorator([login_required], name='dispatch')
class DocumentReviewAPIView(StaffRequiredMixin, View):
    """
    Document review and approval workflow with two-person approval

    Two-Person Workflow:
    - First review: Subject Matter Expert evaluates accuracy/completeness
    - Second review: Quality Assurance validates and approves for publication

    Security: CSRF protection enabled for all mutations
    """

    def get(self, request):
        """Get pending reviews or review history"""
        try:
            review_type = request.GET.get('type', 'pending')  # 'pending', 'completed', 'all'
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', 20)), 100)

            # Updated query for two-person approval
            reviews = KnowledgeReview.objects.select_related(
                'document', 'first_reviewer', 'second_reviewer'
            )

            if review_type == 'pending':
                reviews = reviews.filter(status__in=['draft', 'first_review', 'second_review'])
            elif review_type == 'completed':
                reviews = reviews.filter(status__in=['approved', 'rejected'])
            elif review_type == 'my_pending':
                # Reviews assigned to current user
                reviews = reviews.filter(
                    models.Q(first_reviewer=request.user, status='first_review') |
                    models.Q(second_reviewer=request.user, status='second_review')
                )

            reviews = reviews.order_by('-cdtz')

            paginator = Paginator(reviews, page_size)
            page_obj = paginator.get_page(page)

            return JsonResponse({
                'reviews': [self._serialize_review(review) for review in page_obj],
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count
                },
                'status': 'success'
            })

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error in review GET: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Internal server error',
                'correlation_id': correlation_id
            }, status=500)

    def post(self, request):
        """Submit document review (first or second review)"""
        try:
            from apps.client_onboarding.services import KnowledgeReviewService
            from django.core.exceptions import ValidationError, PermissionDenied

            data = json.loads(request.body)

            # Validate required fields
            required_fields = ['document_id', 'decision', 'notes', 'review_type']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({'error': f'Missing required field: {field}'}, status=400)

            # Get document
            try:
                document = AuthoritativeKnowledge.objects.get(knowledge_id=data['document_id'])
            except AuthoritativeKnowledge.DoesNotExist:
                return JsonResponse({'error': 'Document not found'}, status=404)

            # Get or create review
            review, created = KnowledgeReview.objects.get_or_create(
                document=document,
                defaults={
                    'status': 'draft',
                    'notes': data['notes']
                }
            )

            review_service = KnowledgeReviewService()
            review_type = data['review_type']  # 'first' or 'second'
            decision = data['decision'].lower()

            # Build quality scores
            quality_scores = {
                'accuracy_score': data.get('accuracy_score'),
                'completeness_score': data.get('completeness_score'),
                'relevance_score': data.get('relevance_score')
            }

            # Handle review based on type
            if review_type == 'first':
                result = review_service.submit_first_review(
                    review=review,
                    reviewer=request.user,
                    decision=decision,
                    notes=data['notes'],
                    quality_scores=quality_scores,
                    conditions=data.get('approval_conditions', '')
                )
            elif review_type == 'second':
                result = review_service.submit_second_review(
                    review=review,
                    reviewer=request.user,
                    decision=decision,
                    notes=data['notes'],
                    conditions=data.get('approval_conditions', '')
                )
            else:
                return JsonResponse({'error': f'Invalid review_type: {review_type}'}, status=400)

            # Update feedback data
            review.feedback_data = data.get('feedback_data', {})
            review.save()

            logger.info(
                f"{review_type.title()} review {decision} for document {document.knowledge_id} "
                f"by {request.user.email}"
            )

            return JsonResponse({
                'review': self._serialize_review(review),
                'result': result,
                'status': 'submitted'
            })

        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except PermissionDenied as e:
            return JsonResponse({'error': str(e)}, status=403)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error submitting review: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to submit review',
                'correlation_id': correlation_id
            }, status=500)

    def _serialize_review(self, review: KnowledgeReview) -> Dict[str, Any]:
        """Serialize review for API response (two-person approval)"""
        return {
            'review_id': str(review.review_id),
            'document': {
                'knowledge_id': str(review.document.knowledge_id),
                'title': review.document.document_title,
                'source_organization': review.document.source_organization,
                'authority_level': review.document.authority_level
            },
            'status': review.status,
            'notes': review.notes,
            # Two-person approval fields
            'first_reviewer': review.first_reviewer.email if review.first_reviewer else None,
            'first_reviewed_at': review.first_reviewed_at.isoformat() if review.first_reviewed_at else None,
            'second_reviewer': review.second_reviewer.email if review.second_reviewer else None,
            'second_reviewed_at': review.second_reviewed_at.isoformat() if review.second_reviewed_at else None,
            # Legacy field for backward compatibility
            'reviewer': review.reviewer.email if review.reviewer else None,
            'reviewed_at': review.reviewed_at.isoformat() if review.reviewed_at else None,
            # Quality scores
            'accuracy_score': float(review.accuracy_score) if review.accuracy_score else None,
            'completeness_score': float(review.completeness_score) if review.completeness_score else None,
            'relevance_score': float(review.relevance_score) if review.relevance_score else None,
            'overall_quality_score': review.get_overall_quality_score(),
            # Approval
            'approved_for_publication': review.approved_for_publication,
            'approval_conditions': review.approval_conditions,
            'feedback_data': review.feedback_data,
            'provenance_data': review.provenance_data,
            # Timestamps
            'created_at': review.cdtz.isoformat(),
            'updated_at': review.mdtz.isoformat()
        }


# =============================================================================
# KNOWLEDGE STATISTICS AND MONITORING
# =============================================================================


@method_decorator([login_required], name='dispatch')
class KnowledgeStatsAPIView(StaffRequiredMixin, View):
    """
    Knowledge base statistics and health monitoring

    Security: CSRF protection enabled (read-only but follows consistent policy)
    """

    def get(self, request):
        """Get comprehensive knowledge base statistics"""
        try:
            knowledge_service = get_knowledge_service()

            # Get basic stats
            stats = knowledge_service.get_knowledge_stats()

            # Add detailed breakdowns
            stats['source_breakdown'] = self._get_source_breakdown()
            stats['ingestion_stats'] = self._get_ingestion_stats()
            stats['review_stats'] = self._get_review_stats()
            stats['freshness_analysis'] = self._get_freshness_analysis()

            return JsonResponse({
                'stats': stats,
                'status': 'success',
                'generated_at': datetime.now().isoformat()
            })

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handler import ErrorHandler
            correlation_id = ErrorHandler.generate_correlation_id()
            logger.error(
                f"Error getting knowledge stats: {str(e)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return JsonResponse({
                'error': 'Failed to get statistics',
                'correlation_id': correlation_id
            }, status=500)

    def _get_source_breakdown(self) -> Dict[str, Any]:
        """Get breakdown by source type and status"""
        sources = KnowledgeSource.objects.all()

        breakdown = {
            'by_type': {},
            'by_status': {
                'active': sources.filter(is_active=True).count(),
                'inactive': sources.filter(is_active=False).count()
            },
            'total_sources': sources.count()
        }

        for source_type in ['iso', 'asis', 'nist', 'internal', 'external']:
            breakdown['by_type'][source_type] = sources.filter(source_type=source_type).count()

        return breakdown

    def _get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion job statistics"""
        jobs = KnowledgeIngestionJob.objects.all()

        stats = {
            'total_jobs': jobs.count(),
            'by_status': {},
            'recent_jobs_24h': jobs.filter(cdtz__gte=datetime.now() - timedelta(days=1)).count(),
            'avg_processing_time_ms': 0
        }

        # Status breakdown
        for status in ['queued', 'fetching', 'parsing', 'chunking', 'embedding', 'ready', 'failed']:
            stats['by_status'][status] = jobs.filter(status=status).count()

        # Average processing time
        completed_jobs = jobs.filter(
            status=KnowledgeIngestionJob.StatusChoices.READY,
            processing_duration_ms__isnull=False
        )
        if completed_jobs.exists():
            total_time = sum(job.processing_duration_ms for job in completed_jobs)
            stats['avg_processing_time_ms'] = total_time // completed_jobs.count()

        return stats

    def _get_review_stats(self) -> Dict[str, Any]:
        """Get document review statistics (two-person approval)"""
        reviews = KnowledgeReview.objects.all()

        return {
            'total_reviews': reviews.count(),
            'draft_reviews': reviews.filter(status='draft').count(),
            'first_review_in_progress': reviews.filter(status='first_review').count(),
            'second_review_in_progress': reviews.filter(status='second_review').count(),
            'approved_reviews': reviews.filter(status='approved').count(),
            'rejected_reviews': reviews.filter(status='rejected').count(),
            'avg_first_review_time_hours': self._calculate_avg_first_review_time(reviews),
            'avg_second_review_time_hours': self._calculate_avg_second_review_time(reviews),
            'avg_total_review_time_hours': self._calculate_avg_total_review_time(reviews),
            'approval_rate': self._calculate_approval_rate(reviews)
        }

    def _get_freshness_analysis(self) -> Dict[str, Any]:
        """Analyze knowledge freshness"""
        from datetime import timedelta

        docs = AuthoritativeKnowledge.objects.filter(is_current=True)
        now = datetime.now()

        freshness = {
            'very_recent': docs.filter(publication_date__gte=now - timedelta(days=30)).count(),
            'recent': docs.filter(publication_date__gte=now - timedelta(days=180)).count(),
            'moderate': docs.filter(publication_date__gte=now - timedelta(days=365)).count(),
            'old': docs.filter(publication_date__lt=now - timedelta(days=365)).count(),
            'stale_docs_needing_refresh': docs.filter(
                last_verified__lt=now - timedelta(days=90)
            ).count()
        }

        return freshness

    def _calculate_avg_first_review_time(self, reviews) -> float:
        """Calculate average first review time in hours"""
        completed_first_reviews = reviews.filter(first_reviewed_at__isnull=False)
        if not completed_first_reviews.exists():
            return 0.0

        total_hours = sum(
            (review.first_reviewed_at - review.cdtz).total_seconds() / 3600
            for review in completed_first_reviews
            if review.first_reviewed_at and review.cdtz
        )
        count = completed_first_reviews.count()
        return total_hours / count if count > 0 else 0.0

    def _calculate_avg_second_review_time(self, reviews) -> float:
        """Calculate average second review time in hours"""
        completed_second_reviews = reviews.filter(second_reviewed_at__isnull=False, first_reviewed_at__isnull=False)
        if not completed_second_reviews.exists():
            return 0.0

        total_hours = sum(
            (review.second_reviewed_at - review.first_reviewed_at).total_seconds() / 3600
            for review in completed_second_reviews
            if review.second_reviewed_at and review.first_reviewed_at
        )
        count = completed_second_reviews.count()
        return total_hours / count if count > 0 else 0.0

    def _calculate_avg_total_review_time(self, reviews) -> float:
        """Calculate average total review time (draft to approved) in hours"""
        completed_reviews = reviews.filter(status='approved', second_reviewed_at__isnull=False)
        if not completed_reviews.exists():
            return 0.0

        total_hours = sum(
            (review.second_reviewed_at - review.cdtz).total_seconds() / 3600
            for review in completed_reviews
            if review.second_reviewed_at and review.cdtz
        )
        count = completed_reviews.count()
        return total_hours / count if count > 0 else 0.0

    def _calculate_approval_rate(self, reviews) -> float:
        """Calculate overall approval rate (two-person workflow)"""
        completed_reviews = reviews.filter(status__in=['approved', 'rejected'])

        if not completed_reviews.exists():
            return 0.0

        approved_count = completed_reviews.filter(status='approved').count()
        return (approved_count / completed_reviews.count()) * 100