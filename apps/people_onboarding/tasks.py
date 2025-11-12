"""
Celery tasks for People Onboarding document processing.
"""

import logging
from typing import Dict, Any

from celery import shared_task
from django.utils import timezone

from apps.core.exceptions.patterns import CELERY_EXCEPTIONS, NETWORK_EXCEPTIONS
from apps.people_onboarding.models import DocumentSubmission
from apps.people_onboarding.services.document_parser_service import DocumentParserService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    autoretry_for=NETWORK_EXCEPTIONS,
)
def extract_document_data(self, document_id: int) -> Dict[str, Any]:
    """
    Extract structured data from uploaded onboarding documents.
    """
    if not DocumentParserService.is_available():
        logger.info(
            "Document parser disabled; skipping extraction",
            extra={'document_id': document_id},
        )
        return {'status': 'disabled'}

    try:
        document = DocumentSubmission.objects.select_related(
            'onboarding_request'
        ).get(id=document_id)
    except DocumentSubmission.DoesNotExist:
        logger.warning(
            "Document submission no longer exists",
            extra={'document_id': document_id},
        )
        return {'status': 'missing'}

    service = DocumentParserService()
    validation = service.validate_document(
        document.document_file,
        document.document_type,
    )

    if not validation['is_valid']:
        logger.warning(
            "Document validation failed",
            extra={
                'document_id': document_id,
                'issues': validation['issues'],
            },
        )
        document.extracted_data = {
            'parser_version': DocumentParserService.PARSER_VERSION,
            'parsed_at': timezone.now().isoformat(),
            'validation_issues': validation['issues'],
        }
        document.verification_status = (
            DocumentSubmission.VerificationStatus.REQUIRES_REUPLOAD
        )
        document.verification_notes = "; ".join(validation['issues'])
        document.save(
            update_fields=['extracted_data', 'verification_status', 'verification_notes']
        )
        return {'status': 'invalid', 'issues': validation['issues']}

    try:
        parse_result = service.parse_document(
            document.document_type,
            document.document_file,
        )
    except CELERY_EXCEPTIONS as exc:
        logger.warning(
            "Transient document parsing error, retrying",
            extra={'document_id': document_id, 'error': str(exc)},
        )
        raise self.retry(exc=exc)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception(
            "Document parsing failed",
            extra={'document_id': document_id},
        )
        raise

    document.extracted_data = {
        **parse_result,
        'parsed_at': timezone.now().isoformat(),
        'document_type': document.document_type,
    }

    if parse_result.get('success'):
        document.verification_status = DocumentSubmission.VerificationStatus.PENDING
        document.verification_notes = (
            document.verification_notes or "Awaiting manual verification."
        )
    else:
        document.verification_status = (
            DocumentSubmission.VerificationStatus.REQUIRES_REUPLOAD
        )
        document.verification_notes = (
            "Unable to auto-parse document; please upload a clearer copy."
        )

    document.save(
        update_fields=['extracted_data', 'verification_status', 'verification_notes']
    )

    logger.info(
        "Document parsing completed",
        extra={
            'document_id': document_id,
            'document_type': document.document_type,
            'confidence': parse_result.get('confidence'),
        },
    )

    return {
        'status': 'parsed',
        'confidence': parse_result.get('confidence'),
        'document_type': document.document_type,
    }
