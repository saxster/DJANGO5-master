"""
PII Detection Scanner Service

Proactive security service that scans journal and wellness data for
accidental PII exposure. Detects patterns like emails, phones, SSNs
that shouldn't be in journal content.

Features:
- Automated scanning of journal entries
- Pattern-based PII detection
- Alert generation for admins
- Scheduled scanning via management command
- Compliance reporting

Usage:
    # Scan single entry
    scanner = PIIDetectionScanner()
    result = scanner.scan_journal_entry(entry)

    # Scan all entries
    results = scanner.scan_all_journal_entries()

    # Management command
    python manage.py scan_journal_pii --report

Author: Claude Code
Date: 2025-10-01
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from apps.core.security.pii_redaction import PIIRedactionService, PIIType
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)


class PIIDetectionScanner:
    """
    Service for detecting accidental PII in journal and wellness data.

    Scans for patterns that indicate PII was accidentally entered
    in fields where it shouldn't be (e.g., SSN in journal content).
    """

    # Severity levels for detected PII
    SEVERITY_CRITICAL = 'critical'  # SSN, credit card
    SEVERITY_HIGH = 'high'          # Email, phone
    SEVERITY_MEDIUM = 'medium'       # Full names
    SEVERITY_LOW = 'low'            # Partial matches

    # PII patterns by severity
    CRITICAL_PATTERNS = {
        PIIType.SSN: {
            'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
            'description': 'Social Security Number'
        },
        PIIType.CREDIT_CARD: {
            'pattern': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'description': 'Credit Card Number'
        },
    }

    HIGH_PATTERNS = {
        PIIType.EMAIL: {
            'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'description': 'Email Address'
        },
        PIIType.PHONE: {
            'pattern': r'(\+\d{1,3}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
            'description': 'Phone Number'
        },
    }

    def __init__(self):
        """Initialize PII detection scanner."""
        self.pii_service = PIIRedactionService()
        self.scan_results = []

    def scan_journal_entry(self, entry) -> Dict[str, Any]:
        """
        Scan a single journal entry for PII.

        Args:
            entry: JournalEntry instance

        Returns:
            dict: Scan results with detected PII

        Example:
            {
                'entry_id': 'uuid',
                'has_pii': True,
                'pii_found': [
                    {'type': 'email', 'severity': 'high', 'field': 'content'},
                    {'type': 'phone', 'severity': 'high', 'field': 'title'}
                ],
                'scanned_at': '2025-10-01T10:00:00Z'
            }
        """
        logger.debug(f"Scanning journal entry {entry.id} for PII")

        pii_found = []

        # Fields to scan in journal entry
        fields_to_scan = {
            'title': entry.title,
            'content': entry.content,
            'subtitle': entry.subtitle,
            'mood_description': entry.mood_description,
            'location_site_name': entry.location_site_name,
            'location_address': entry.location_address,
        }

        # Scan each field
        for field_name, field_value in fields_to_scan.items():
            if not field_value:
                continue

            field_pii = self._scan_text_for_pii(field_value, field_name)
            pii_found.extend(field_pii)

        # Scan JSON fields
        json_fields = {
            'gratitude_items': entry.gratitude_items,
            'affirmations': entry.affirmations,
            'achievements': entry.achievements,
            'learnings': entry.learnings,
            'stress_triggers': entry.stress_triggers,
            'tags': entry.tags,
        }

        for field_name, field_value in json_fields.items():
            if not field_value or not isinstance(field_value, list):
                continue

            for item in field_value:
                if isinstance(item, str):
                    item_pii = self._scan_text_for_pii(item, f"{field_name}[]")
                    pii_found.extend(item_pii)

        # Create scan result
        result = {
            'entry_id': str(entry.id),
            'user_id': str(entry.user.id),
            'entry_type': entry.entry_type,
            'has_pii': len(pii_found) > 0,
            'pii_count': len(pii_found),
            'pii_found': pii_found,
            'max_severity': self._get_max_severity(pii_found),
            'scanned_at': timezone.now().isoformat(),
        }

        # Log if PII found
        if pii_found:
            safe_pii_summary = self._get_safe_pii_summary(pii_found)
            logger.warning(
                f"PII detected in journal entry {entry.id}",
                extra={
                    'entry_id': str(entry.id),
                    'pii_count': len(pii_found),
                    'max_severity': result['max_severity'],
                    'pii_types_summary': safe_pii_summary
                }
            )

        return result

    def scan_wellness_interaction(self, interaction) -> Dict[str, Any]:
        """
        Scan a wellness interaction for PII.

        Args:
            interaction: WellnessContentInteraction instance

        Returns:
            dict: Scan results
        """
        logger.debug(f"Scanning wellness interaction {interaction.id} for PII")

        pii_found = []

        # Scan user feedback
        if interaction.user_feedback:
            feedback_pii = self._scan_text_for_pii(
                interaction.user_feedback,
                'user_feedback'
            )
            pii_found.extend(feedback_pii)

        result = {
            'interaction_id': str(interaction.id),
            'user_id': str(interaction.user.id),
            'has_pii': len(pii_found) > 0,
            'pii_count': len(pii_found),
            'pii_found': pii_found,
            'max_severity': self._get_max_severity(pii_found),
            'scanned_at': timezone.now().isoformat(),
        }

        if pii_found:
            logger.warning(
                f"PII detected in wellness interaction {interaction.id}",
                extra={
                    'interaction_id': str(interaction.id),
                    'pii_count': len(pii_found)
                }
            )

        return result

    def scan_all_journal_entries(
        self,
        days_back: int = 30,
        max_entries: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scan all recent journal entries for PII.

        Args:
            days_back: Number of days to look back
            max_entries: Maximum entries to scan (None = all)

        Returns:
            dict: Aggregate scan results
        """
        from apps.journal.models import JournalEntry

        logger.info(f"Starting bulk PII scan (days_back={days_back}, max={max_entries})")

        cutoff_date = timezone.now() - timedelta(days=days_back)

        # Query entries
        queryset = JournalEntry.objects.filter(
            created_at__gte=cutoff_date,
            is_deleted=False
        ).order_by('-created_at')

        if max_entries:
            queryset = queryset[:max_entries]

        total_entries = queryset.count()
        entries_with_pii = 0
        total_pii_found = 0
        pii_by_severity = {
            self.SEVERITY_CRITICAL: 0,
            self.SEVERITY_HIGH: 0,
            self.SEVERITY_MEDIUM: 0,
            self.SEVERITY_LOW: 0,
        }
        pii_by_type = {}

        # Scan each entry
        for entry in queryset:
            result = self.scan_journal_entry(entry)

            if result['has_pii']:
                entries_with_pii += 1
                total_pii_found += result['pii_count']

                # Aggregate statistics
                for pii_item in result['pii_found']:
                    severity = pii_item['severity']
                    pii_type = pii_item['type']

                    pii_by_severity[severity] = pii_by_severity.get(severity, 0) + 1
                    pii_by_type[pii_type] = pii_by_type.get(pii_type, 0) + 1

        # Generate report
        report = {
            'scan_summary': {
                'total_entries_scanned': total_entries,
                'entries_with_pii': entries_with_pii,
                'total_pii_instances': total_pii_found,
                'pii_detection_rate': (entries_with_pii / total_entries * 100) if total_entries > 0 else 0,
            },
            'pii_by_severity': pii_by_severity,
            'pii_by_type': pii_by_type,
            'scanned_at': timezone.now().isoformat(),
            'scan_parameters': {
                'days_back': days_back,
                'max_entries': max_entries,
            }
        }

        logger.info(
            f"Bulk PII scan complete: {entries_with_pii}/{total_entries} entries with PII",
            extra=report['scan_summary']
        )

        return report

    def _scan_text_for_pii(self, text: str, field_name: str) -> List[Dict[str, Any]]:
        """
        Scan text for PII patterns.

        Args:
            text: Text to scan
            field_name: Name of field being scanned

        Returns:
            list: List of PII items found
        """
        if not text or not isinstance(text, str):
            return []

        pii_found = []

        # Scan for critical patterns
        for pii_type, pattern_info in self.CRITICAL_PATTERNS.items():
            matches = re.finditer(pattern_info['pattern'], text)
            for match in matches:
                pii_found.append({
                    'type': pii_type.value,
                    'description': pattern_info['description'],
                    'severity': self.SEVERITY_CRITICAL,
                    'field': field_name,
                    'match_start': match.start(),
                    'match_end': match.end(),
                    'context': self._get_match_context(text, match.start(), match.end())
                })

        # Scan for high-severity patterns
        for pii_type, pattern_info in self.HIGH_PATTERNS.items():
            matches = re.finditer(pattern_info['pattern'], text)
            for match in matches:
                pii_found.append({
                    'type': pii_type.value,
                    'description': pattern_info['description'],
                    'severity': self.SEVERITY_HIGH,
                    'field': field_name,
                    'match_start': match.start(),
                    'match_end': match.end(),
                    'context': self._get_match_context(text, match.start(), match.end())
                })

        return pii_found

    def _get_match_context(self, text: str, start: int, end: int, window: int = 20) -> str:
        """
        Get context around a PII match.

        Args:
            text: Full text
            start: Match start position
            end: Match end position
            window: Characters to include before/after

        Returns:
            str: Context string with match redacted
        """
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)

        before = text[context_start:start]
        after = text[end:context_end]

        return f"...{before}[REDACTED]{after}..."

    def _get_max_severity(self, pii_found: List[Dict[str, Any]]) -> str:
        """
        Get maximum severity from list of PII items.

        Args:
            pii_found: List of PII items

        Returns:
            str: Maximum severity level
        """
        if not pii_found:
            return 'none'

        severity_order = [
            self.SEVERITY_CRITICAL,
            self.SEVERITY_HIGH,
            self.SEVERITY_MEDIUM,
            self.SEVERITY_LOW
        ]

        for severity in severity_order:
            if any(p['severity'] == severity for p in pii_found):
                return severity

        return 'low'

    def _get_safe_pii_summary(self, pii_found: list) -> list:
        """
        Create safe PII summary for logging (excludes context and matches).

        This method sanitizes PII detection results for safe logging,
        removing sensitive context and match text while preserving
        type and severity information needed for analytics.

        Args:
            pii_found: List of PII detections with full context

        Returns:
            list: Safe summary with only type and severity (GDPR/HIPAA compliant)

        Example:
            >>> pii_found = [
            ...     {'type': 'ssn', 'severity': 'critical', 'context': '...123-45-6789...'},
            ...     {'type': 'phone', 'severity': 'high', 'match': '555-1234'}
            ... ]
            >>> safe = scanner._get_safe_pii_summary(pii_found)
            >>> safe
            [{'type': 'ssn', 'severity': 'critical'}, {'type': 'phone', 'severity': 'high'}]
        """
        return [
            {
                'type': pii_item['type'],
                'severity': pii_item['severity']
            }
            for pii_item in pii_found
        ]
