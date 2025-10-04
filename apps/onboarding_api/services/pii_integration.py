"""
PII Integration Service for Conversational Onboarding.

Provides centralized PII redaction capabilities across all onboarding services
including voice transcription, OCR extraction, and image analysis.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from django.conf import settings
from django.utils import timezone

from apps.onboarding_api.services.security import PIIRedactor

logger = logging.getLogger(__name__)
metrics_logger = logging.getLogger("metrics")


class OnboardingPIIService:
    """
    Centralized PII redaction service for onboarding workflows.

    Ensures all sensitive data (PII) is properly redacted before:
    - Sending to LLM providers
    - Logging to files
    - Storing in analytics databases
    """

    def __init__(self):
        """Initialize PII service with redactor"""
        self.redactor = PIIRedactor()
        self.enable_redaction = getattr(
            settings,
            'ENABLE_PII_REDACTION',
            True
        )

    def sanitize_voice_transcript(
        self,
        transcript: str,
        session_id: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sanitize voice transcript for PII before LLM processing.

        Args:
            transcript: Raw voice transcript text
            session_id: Conversation session ID for tracking
            additional_context: Additional context for redaction

        Returns:
            {
                'sanitized_transcript': str,
                'redaction_metadata': Dict,
                'safe_for_llm': bool,
                'safe_for_logging': bool
            }
        """
        if not self.enable_redaction:
            logger.warning(
                "PII redaction disabled - transcript NOT sanitized",
                extra={'session_id': session_id}
            )
            return {
                'sanitized_transcript': transcript,
                'redaction_metadata': {},
                'safe_for_llm': False,  # Not safe when redaction disabled
                'safe_for_logging': False
            }

        try:
            # Apply PII redaction
            redacted_transcript, redaction_metadata = self.redactor.redact_text(
                transcript,
                context='voice_input'
            )

            # Track redaction metrics
            self._log_redaction_metrics(
                session_id=session_id,
                source='voice_transcript',
                metadata=redaction_metadata,
                additional_context=additional_context
            )

            # Determine safety for different use cases
            safe_for_llm = redaction_metadata['redactions_count'] >= 0  # Always safe after redaction
            safe_for_logging = redaction_metadata['redactions_count'] >= 0

            return {
                'sanitized_transcript': redacted_transcript,
                'redaction_metadata': redaction_metadata,
                'safe_for_llm': safe_for_llm,
                'safe_for_logging': safe_for_logging,
                'original_length': len(transcript),
                'sanitized_length': len(redacted_transcript)
            }

        except (ValueError, TypeError) as e:
            logger.error(
                f"PII redaction failed for voice transcript: {str(e)}",
                extra={
                    'session_id': session_id,
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            # Fail-safe: return error indicator
            return {
                'sanitized_transcript': '[REDACTION_FAILED]',
                'redaction_metadata': {'error': str(e)},
                'safe_for_llm': False,
                'safe_for_logging': False
            }

    def sanitize_ocr_result(
        self,
        ocr_text: str,
        session_id: str,
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sanitize OCR extraction results for PII.

        Args:
            ocr_text: Raw OCR extracted text
            session_id: Conversation session ID for tracking
            document_type: Type of document (register, meter, etc.)

        Returns:
            Sanitized OCR result with metadata
        """
        if not self.enable_redaction:
            return {
                'sanitized_text': ocr_text,
                'redaction_metadata': {},
                'safe_for_llm': False,
                'safe_for_logging': False
            }

        try:
            # Apply PII redaction with OCR-specific context
            redacted_text, redaction_metadata = self.redactor.redact_text(
                ocr_text,
                context='ocr_extraction'
            )

            # Track redaction metrics
            self._log_redaction_metrics(
                session_id=session_id,
                source='ocr_result',
                metadata=redaction_metadata,
                additional_context={'document_type': document_type}
            )

            return {
                'sanitized_text': redacted_text,
                'redaction_metadata': redaction_metadata,
                'safe_for_llm': True,
                'safe_for_logging': True,
                'document_type': document_type
            }

        except (ValueError, TypeError) as e:
            logger.error(
                f"PII redaction failed for OCR result: {str(e)}",
                extra={
                    'session_id': session_id,
                    'document_type': document_type
                },
                exc_info=True
            )
            return {
                'sanitized_text': '[REDACTION_FAILED]',
                'redaction_metadata': {'error': str(e)},
                'safe_for_llm': False,
                'safe_for_logging': False
            }

    def sanitize_image_analysis_labels(
        self,
        labels: List[Dict[str, Any]],
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Sanitize image analysis labels for PII.

        Vision API may detect text or labels containing PII.

        Args:
            labels: List of image labels/annotations
            session_id: Session ID for tracking

        Returns:
            Sanitized labels list
        """
        if not self.enable_redaction:
            return labels

        try:
            sanitized_labels = []
            total_redactions = 0

            for label in labels:
                # Sanitize label name/description
                if 'name' in label:
                    redacted_name, metadata = self.redactor.redact_text(
                        str(label['name']),
                        context='image_analysis'
                    )
                    label['name'] = redacted_name
                    total_redactions += metadata['redactions_count']

                if 'description' in label:
                    redacted_desc, metadata = self.redactor.redact_text(
                        str(label['description']),
                        context='image_analysis'
                    )
                    label['description'] = redacted_desc
                    total_redactions += metadata['redactions_count']

                sanitized_labels.append(label)

            # Log if any redactions were made
            if total_redactions > 0:
                logger.info(
                    f"Image analysis labels sanitized: {total_redactions} redactions",
                    extra={'session_id': session_id}
                )

            return sanitized_labels

        except (ValueError, TypeError) as e:
            logger.error(
                f"PII redaction failed for image labels: {str(e)}",
                extra={'session_id': session_id},
                exc_info=True
            )
            # Return empty list on failure to prevent PII leakage
            return []

    def sanitize_user_input(
        self,
        user_input: str,
        session_id: str,
        input_type: str = 'text'
    ) -> Dict[str, Any]:
        """
        Sanitize general user input for PII.

        Args:
            user_input: Raw user input text
            session_id: Session ID for tracking
            input_type: Type of input (text, voice, etc.)

        Returns:
            Sanitized input with metadata
        """
        if not self.enable_redaction:
            return {
                'sanitized_input': user_input,
                'redaction_metadata': {},
                'safe_for_llm': False
            }

        try:
            redacted_input, metadata = self.redactor.redact_text(
                user_input,
                context='user_input'
            )

            self._log_redaction_metrics(
                session_id=session_id,
                source=f'user_input_{input_type}',
                metadata=metadata
            )

            return {
                'sanitized_input': redacted_input,
                'redaction_metadata': metadata,
                'safe_for_llm': True,
                'input_type': input_type
            }

        except (ValueError, TypeError) as e:
            logger.error(
                f"PII redaction failed for user input: {str(e)}",
                extra={'session_id': session_id, 'input_type': input_type},
                exc_info=True
            )
            return {
                'sanitized_input': '[REDACTION_FAILED]',
                'redaction_metadata': {'error': str(e)},
                'safe_for_llm': False
            }

    def _log_redaction_metrics(
        self,
        session_id: str,
        source: str,
        metadata: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """
        Log PII redaction metrics for monitoring.

        Rule #15 compliance: No sensitive data in logs.

        Args:
            session_id: Session ID for correlation
            source: Source of data (voice, ocr, etc.)
            metadata: Redaction metadata (safe to log)
            additional_context: Additional safe context
        """
        metrics_logger.info(
            f"PII redaction applied: {source}",
            extra={
                'session_id': session_id,
                'source': source,
                'redactions_count': metadata.get('redactions_count', 0),
                'redaction_timestamp': timezone.now().isoformat(),
                'additional_context': additional_context or {}
            }
        )


# Factory function for dependency injection
def get_pii_service() -> OnboardingPIIService:
    """
    Factory function to get PII service instance.

    Returns:
        Configured OnboardingPIIService instance
    """
    return OnboardingPIIService()
