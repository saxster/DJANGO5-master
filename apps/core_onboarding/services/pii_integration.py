"""
High-level PII integration helpers for OCR and voice services.

This module wraps the low-level `PIIRedactor` into a cohesive service that
exposes intent-focused helpers used by the OCR and Speech services. It keeps
the redaction logic centralized while returning a consistent payload expected
by the callers (`sanitized_*`, `redaction_metadata`, `safe_for_llm`).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from apps.core_onboarding.services.security import get_pii_redactor, PIIRedactor

logger = logging.getLogger(__name__)


class PIIIntegrationService:
    """Domain-specific façade around the generic PIIRedactor."""

    def __init__(self) -> None:
        self._redactor: PIIRedactor = get_pii_redactor()

    @staticmethod
    def _normalize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Ensure metadata always contains a redaction count."""
        metadata = metadata or {}
        if "redactions_count" not in metadata:
            metadata["redactions_count"] = len(metadata.get("redactions", []))
        return metadata

    def sanitize_ocr_result(
        self,
        ocr_text: str,
        session_id: str,
        document_type: str,
    ) -> Dict[str, Any]:
        """Sanitize OCR text output before downstream processing."""
        sanitized_text, metadata = self._redactor.redact_text(
            ocr_text,
            context="document_ingestion",
        )
        metadata = self._normalize_metadata(metadata)
        safe_for_llm = metadata["redactions_count"] == 0

        logger.debug(
            "OCR text sanitized",
            extra={
                "session_id": session_id,
                "document_type": document_type,
                "redactions": metadata["redactions_count"],
            },
        )

        return {
            "sanitized_text": sanitized_text,
            "redaction_metadata": metadata,
            "safe_for_llm": safe_for_llm,
            "session_id": session_id,
            "document_type": document_type,
        }

    def sanitize_voice_transcript(
        self,
        transcript: str,
        session_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Sanitize voice transcripts prior to storage or LLM usage."""
        sanitized_transcript, metadata = self._redactor.redact_text(
            transcript,
            context="voice_transcript",
        )
        metadata = self._normalize_metadata(metadata)
        safe_for_llm = metadata["redactions_count"] == 0

        logger.debug(
            "Voice transcript sanitized",
            extra={
                "session_id": session_id,
                "redactions": metadata["redactions_count"],
                "context": additional_context or {},
            },
        )

        return {
            "sanitized_transcript": sanitized_transcript,
            "redaction_metadata": metadata,
            "safe_for_llm": safe_for_llm,
            "session_id": session_id,
            "context": additional_context or {},
        }


@lru_cache(maxsize=1)
def get_pii_service() -> PIIIntegrationService:
    """Singleton accessor used by OCR and speech services."""
    return PIIIntegrationService()


__all__ = ["PIIIntegrationService", "get_pii_service"]
