"""
Document Parser Service

AI-powered document parsing and OCR extraction for People Onboarding.
Complies with Rule #14: Methods < 50 lines (helpers keep public methods short).
"""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.core_onboarding.services.ocr_service import OCRService
from apps.people_onboarding.models import DocumentType

logger = logging.getLogger(__name__)


class DocumentParserService:
    """
    AI-powered document parsing service.

    Features:
    - Resume/CV parsing with entity extraction
    - ID document OCR (Aadhaar, PAN, Passport, DL)
    - Certificate and generic document keyword extraction
    """

    PARSER_VERSION = "2025.11"
    PDF_EXTENSIONS = {".pdf"}
    DOCX_EXTENSIONS = {".docx"}
    TEXT_EXTENSIONS = {".txt", ".md", ".rtf"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
    ID_DOCUMENT_TYPES = {
        DocumentType.AADHAAR,
        DocumentType.PAN,
        DocumentType.PASSPORT,
        DocumentType.DRIVING_LICENSE,
        DocumentType.ADDRESS_PROOF,
    }
    RESUME_SECTION_ALIASES = {
        "summary": ["summary", "objective", "profile"],
        "skills": ["skills", "core competencies", "technical skills"],
        "experience": [
            "experience",
            "work experience",
            "employment history",
            "professional experience",
        ],
        "education": ["education", "academic background", "academics"],
        "certifications": ["certifications", "licenses"],
    }
    EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    PHONE_PATTERN = re.compile(r"\+?\d[\d\s\-]{7,}\d")
    DATE_PATTERN = re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{2,4})\b")
    AADHAAR_PATTERN = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")
    PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
    PASSPORT_PATTERN = re.compile(r"\b[A-Z][0-9]{7}\b")

    def __init__(self):
        self._ocr_service: Optional[OCRService] = None

    @classmethod
    def is_available(cls) -> bool:
        """
        Feature flag indicating whether AI parsing is ready for use.

        Returns:
            bool: True when downstream OCR/LLM integrations are configured.
        """
        return getattr(settings, "PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING", False)

    def parse_document(self, document_type: str, document_file) -> Dict[str, Any]:
        """
        Route document parsing based on document type.
        """
        if document_type == DocumentType.RESUME:
            return self.parse_resume(document_file)

        if document_type in self.ID_DOCUMENT_TYPES:
            return self.extract_id_data(document_file, document_type)

        return self.parse_generic_document(document_file, document_type)

    def parse_resume(self, document_file) -> Dict[str, Any]:
        """
        Parse resume/CV and extract structured data.
        """
        text = self._extract_text(document_file, prefer_ocr=False)
        text_excerpt = text[:2000]

        sections = self._split_sections(text)
        name = self._extract_name(text)
        email = self._match_first(self.EMAIL_PATTERN, text)
        phone = self._normalize_phone(self._match_first(self.PHONE_PATTERN, text))
        skills = self._extract_list_from_section(sections.get("skills", ""))
        experience = self._extract_paragraphs(sections.get("experience", ""))
        education = self._extract_paragraphs(sections.get("education", ""))
        certifications = self._extract_list_from_section(
            sections.get("certifications", "")
        )
        keywords = self._extract_keywords(text_excerpt)
        confidence = self._calculate_confidence(
            bool(name), bool(email), bool(phone), bool(skills), bool(experience)
        )

        return {
            "parser_version": self.PARSER_VERSION,
            "success": bool(text),
            "confidence": confidence,
            "summary": sections.get("summary", "")[:500],
            "name": name,
            "email": email,
            "phone": phone,
            "skills": skills,
            "experience": experience,
            "education": education,
            "certifications": certifications,
            "keywords": keywords,
            "raw_text_excerpt": text_excerpt,
        }

    def extract_id_data(self, document_file, document_type: str) -> Dict[str, Any]:
        """
        Extract data from ID documents using OCR/text heuristics.
        """
        text = self._extract_text(
            document_file,
            prefer_ocr=True,
            ocr_context=document_type.lower(),
        )
        text_excerpt = text[:1500]

        if document_type == DocumentType.AADHAAR:
            identifier = self._match_first(self.AADHAAR_PATTERN, text)
        elif document_type == DocumentType.PAN:
            identifier = self._match_first(self.PAN_PATTERN, text)
        elif document_type == DocumentType.PASSPORT:
            identifier = self._match_first(self.PASSPORT_PATTERN, text)
        else:
            identifier = self._match_first(self.PHONE_PATTERN, text)

        dob = self._match_first(self.DATE_PATTERN, text)
        name = self._extract_name(text)
        address = self._extract_address_block(text)
        confidence = self._calculate_confidence(bool(identifier), bool(name), bool(dob))

        return {
            "parser_version": self.PARSER_VERSION,
            "success": bool(text),
            "confidence": confidence,
            "document_identifier": identifier,
            "name": name,
            "date_of_birth": dob,
            "address": address,
            "raw_text_excerpt": text_excerpt,
        }

    def parse_generic_document(self, document_file, document_type: str) -> Dict[str, Any]:
        """
        Fallback parser for certificates, letters, and other uploads.
        """
        text = self._extract_text(
            document_file,
            prefer_ocr=document_type in self.ID_DOCUMENT_TYPES,
            ocr_context=document_type.lower(),
        )
        keywords = self._extract_keywords(text)
        confidence = self._calculate_confidence(bool(text), len(keywords) > 3)
        sentences = self._extract_sentences(text)

        return {
            "parser_version": self.PARSER_VERSION,
            "success": bool(text),
            "confidence": confidence,
            "keywords": keywords,
            "important_sentences": sentences[:5],
            "raw_text_excerpt": text[:1500],
        }

    def validate_document(self, document_file, document_type: str) -> Dict[str, Any]:
        """
        Basic document validation for size and supported extension.
        """
        max_size_mb = getattr(
            settings, "PEOPLE_ONBOARDING_MAX_DOCUMENT_SIZE_MB", 10
        )
        max_size_bytes = max_size_mb * 1024 * 1024

        issues: List[str] = []
        file_size = getattr(document_file, "size", None)
        if file_size and file_size > max_size_bytes:
            issues.append(f"File exceeds {max_size_mb}MB limit")

        extension = self._get_extension(document_file)
        if extension and extension not in (
            self.PDF_EXTENSIONS
            | self.DOCX_EXTENSIONS
            | self.TEXT_EXTENSIONS
            | self.IMAGE_EXTENSIONS
        ):
            issues.append(f"Unsupported file type: {extension}")

        if document_type == DocumentType.RESUME and extension in self.IMAGE_EXTENSIONS:
            issues.append("Resumes must be PDF, DOCX, or TXT")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "size_bytes": file_size,
            "extension": extension,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _extract_text(
        self,
        document_file,
        *,
        prefer_ocr: bool,
        ocr_context: str | None = None,
    ) -> str:
        extension = self._get_extension(document_file)
        if prefer_ocr or extension in self.IMAGE_EXTENSIONS:
            return self._extract_text_via_ocr(document_file, ocr_context)
        if extension in self.PDF_EXTENSIONS:
            return self._extract_text_from_pdf(document_file)
        if extension in self.DOCX_EXTENSIONS:
            return self._extract_text_from_docx(document_file)
        if extension in self.TEXT_EXTENSIONS:
            return self._extract_text_from_plain(document_file)
        # Default fallback
        return self._extract_text_via_ocr(document_file, ocr_context)

    def _extract_text_from_pdf(self, document_file) -> str:
        try:
            from pypdf import PdfReader  # Imported lazily to avoid hard dependency
        except ImportError:
            logger.warning("pypdf not installed; falling back to OCR for PDF parsing")
            return self._extract_text_via_ocr(document_file, "pdf")

        raw_bytes = self._read_file_bytes(document_file)
        if not raw_bytes:
            return ""

        reader = PdfReader(io.BytesIO(raw_bytes))
        max_pages = getattr(settings, "PEOPLE_ONBOARDING_MAX_DOCUMENT_PAGES", 12)
        text_chunks: List[str] = []

        for idx, page in enumerate(reader.pages[:max_pages]):
            try:
                text_chunks.append(page.extract_text() or "")
            except ValueError as exc:
                logger.warning(
                    "PDF text extraction failed on page %s: %s", idx + 1, exc
                )

        return self._normalize_whitespace(" ".join(text_chunks))

    def _extract_text_from_docx(self, document_file) -> str:
        raw_bytes = self._read_file_bytes(document_file)
        if not raw_bytes:
            return ""

        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as docx:
                xml_bytes = docx.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile) as exc:
            logger.error("DOCX parsing failed: %s", exc)
            return ""

        text = re.sub(r"<(.|\n)*?>", " ", xml_bytes.decode("utf-8", errors="ignore"))
        return self._normalize_whitespace(text)

    def _extract_text_from_plain(self, document_file) -> str:
        raw_bytes = self._read_file_bytes(document_file)
        if not raw_bytes:
            return ""
        try:
            return self._normalize_whitespace(raw_bytes.decode("utf-8"))
        except UnicodeDecodeError:
            return self._normalize_whitespace(raw_bytes.decode("latin-1", errors="ignore"))

    def _extract_text_via_ocr(self, document_file, context: Optional[str]) -> str:
        raw_bytes = self._read_file_bytes(document_file)
        if not raw_bytes:
            return ""

        uploaded = SimpleUploadedFile(
            os.path.basename(getattr(document_file, "name", "document")),
            raw_bytes,
        )

        result = self._ocr_service_instance().extract_register_entry(
            uploaded, register_type=context or "generic"
        )
        return self._normalize_whitespace(
            result.get("text")
            or result.get("raw_text")
            or result.get("fields", {}).get("description", "")
        )

    def _split_sections(self, text: str) -> Dict[str, str]:
        sections: Dict[str, str] = defaultdict(str)
        current = "summary"
        buffer: List[str] = []

        normalized_aliases = {
            alias.lower(): key
            for key, aliases in self.RESUME_SECTION_ALIASES.items()
            for alias in aliases
        }

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            normalized = re.sub(r"[^a-zA-Z ]", "", line).strip().lower()
            target_section = normalized_aliases.get(normalized)
            if target_section:
                if buffer:
                    sections[current] = "\n".join(buffer).strip()
                buffer = []
                current = target_section
                continue

            buffer.append(line)

        if buffer:
            sections[current] = "\n".join(buffer).strip()
        return sections

    def _extract_list_from_section(self, section: str) -> List[str]:
        items: List[str] = []
        for raw_line in section.splitlines():
            line = raw_line.strip("-• \t")
            if not line:
                continue
            if "," in line and len(line) < 200:
                items.extend([part.strip() for part in line.split(",") if part.strip()])
            else:
                items.append(line)
        return list(dict.fromkeys(items))[:20]

    def _extract_paragraphs(self, section: str) -> List[str]:
        paragraphs = [para.strip() for para in section.split("\n\n") if para.strip()]
        if not paragraphs and section.strip():
            paragraphs = [section.strip()]
        return paragraphs[:10]

    def _extract_keywords(self, text: str) -> List[str]:
        keywords = re.findall(r"\b[A-Z][A-Za-z0-9\-\+]{3,}\b", text)
        unique_keywords: List[str] = []
        for keyword in keywords:
            if keyword not in unique_keywords:
                unique_keywords.append(keyword)
        return unique_keywords[:25]

    def _extract_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sanitized = [sentence.strip() for sentence in sentences if len(sentence.strip()) > 20]
        return sanitized

    def _extract_name(self, text: str) -> str:
        for line in text.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            if len(candidate.split()) in (2, 3) and candidate[0].isalpha():
                if not any(token.isdigit() for token in candidate):
                    return candidate.title()
        return ""

    def _extract_address_block(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 3:
            return ""
        return " ".join(lines[-3:])

    def _match_first(self, pattern: re.Pattern, text: str) -> str:
        match = pattern.search(text or "")
        return match.group(0) if match else ""

    def _normalize_phone(self, value: str) -> str:
        if not value:
            return ""
        digits = re.sub(r"[^\d+]", "", value)
        return digits[-15:]  # Keep last 15 digits max

    def _calculate_confidence(self, *signals: bool) -> float:
        base = 0.25
        bonus = sum(0.15 for signal in signals if signal)
        return round(min(0.95, base + bonus), 2)

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _get_extension(self, document_file) -> str:
        name = getattr(document_file, "name", "") or ""
        return os.path.splitext(name)[1].lower()

    def _read_file_bytes(self, document_file) -> bytes:
        if hasattr(document_file, "open"):
            with document_file.open("rb") as descriptor:
                return descriptor.read()
        if hasattr(document_file, "read"):
            position = None
            try:
                if document_file.seekable():
                    position = document_file.tell()
            except (OSError, AttributeError):
                position = None
            data = document_file.read()
            if position is not None:
                document_file.seek(position)
            return data
        logger.warning("Unsupported file object for document parser: %s", type(document_file))
        return b""

    def _ocr_service_instance(self) -> OCRService:
        if self._ocr_service is None:
            self._ocr_service = OCRService()
        return self._ocr_service
