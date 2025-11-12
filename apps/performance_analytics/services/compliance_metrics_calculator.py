"""
Compliance Metrics Calculator Service

Calculates compliance scores based on:
- Certifications current/expired
- Training completion
- Safety documentation
- Daily report submission

Compliance:
- Rule #6: Service class < 150 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import date, timedelta
from typing import Dict
from decimal import Decimal

from django.db.models import Q, Count
from django.utils import timezone

from apps.peoples.models import People
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class ComplianceMetricsCalculator:
    """
    Calculates worker compliance score (0-100).
    
    Components:
    - Certifications: 40% (current vs. total)
    - Training: 30% (completion rate)
    - Safety: 20% (incident reports, near misses)
    - Documentation: 10% (daily reports, photos)
    """
    
    WEIGHTS = {
        'certifications': Decimal('0.40'),
        'training': Decimal('0.30'),
        'safety': Decimal('0.20'),
        'documentation': Decimal('0.10'),
    }
    
    def calculate_compliance_score(
        self,
        worker: People,
        target_date: date,
        certifications_current: int = 0,
        certifications_total: int = 0,
        training_completed: int = 0,
        training_required: int = 0,
        daily_reports_submitted: int = 0,
        daily_reports_expected: int = 0,
        evidence_photos_uploaded: int = 0,
        evidence_photos_expected: int = 0,
        incidents_reported: int = 0,
        near_misses_reported: int = 0
    ) -> Dict[str, Decimal]:
        """
        Calculate compliance score from component metrics.
        
        Args:
            worker: Worker being evaluated
            target_date: Date for calculation
            certifications_current: Number of current certifications
            certifications_total: Total certifications required
            training_completed: Training modules completed
            training_required: Training modules required
            daily_reports_submitted: Daily reports submitted
            daily_reports_expected: Daily reports expected
            evidence_photos_uploaded: Evidence photos uploaded
            evidence_photos_expected: Evidence photos expected
            incidents_reported: Safety incidents reported
            near_misses_reported: Near miss events reported
            
        Returns:
            Dict with 'compliance_score' and component scores
        """
        try:
            cert_score = self._calculate_certification_score(
                certifications_current,
                certifications_total
            )
            
            training_score = self._calculate_training_score(
                training_completed,
                training_required
            )
            
            safety_score = self._calculate_safety_score(
                incidents_reported,
                near_misses_reported
            )
            
            doc_score = self._calculate_documentation_score(
                daily_reports_submitted,
                daily_reports_expected,
                evidence_photos_uploaded,
                evidence_photos_expected
            )
            
            compliance_score = (
                cert_score * self.WEIGHTS['certifications'] +
                training_score * self.WEIGHTS['training'] +
                safety_score * self.WEIGHTS['safety'] +
                doc_score * self.WEIGHTS['documentation']
            )
            
            return {
                'compliance_score': round(compliance_score, 2),
                'certification_score': cert_score,
                'training_score': training_score,
                'safety_score': safety_score,
                'documentation_score': doc_score,
            }
            
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(
                f"Error calculating compliance score for worker {worker.id}: {e}",
                exc_info=True
            )
            return {
                'compliance_score': Decimal('0'),
                'certification_score': Decimal('0'),
                'training_score': Decimal('0'),
                'safety_score': Decimal('0'),
                'documentation_score': Decimal('0'),
            }
    
    def _calculate_certification_score(
        self,
        current: int,
        total: int
    ) -> Decimal:
        """Calculate certification compliance score."""
        if total == 0:
            return Decimal('100')
        
        rate = (current / total) * 100
        return Decimal(str(min(rate, 100)))
    
    def _calculate_training_score(
        self,
        completed: int,
        required: int
    ) -> Decimal:
        """Calculate training completion score."""
        if required == 0:
            return Decimal('100')
        
        rate = (completed / required) * 100
        return Decimal(str(min(rate, 100)))
    
    def _calculate_safety_score(
        self,
        incidents: int,
        near_misses: int
    ) -> Decimal:
        """
        Calculate safety score.
        
        Reporting incidents/near misses is POSITIVE (proactive safety culture).
        Score increases with appropriate reporting.
        """
        total_reports = incidents + near_misses
        
        if total_reports == 0:
            return Decimal('80')
        elif total_reports <= 2:
            return Decimal('100')
        elif total_reports <= 5:
            return Decimal('90')
        else:
            return Decimal('70')
    
    def _calculate_documentation_score(
        self,
        reports_submitted: int,
        reports_expected: int,
        photos_uploaded: int,
        photos_expected: int
    ) -> Decimal:
        """Calculate documentation compliance score."""
        if reports_expected == 0 and photos_expected == 0:
            return Decimal('100')
        
        report_score = 0
        photo_score = 0
        
        if reports_expected > 0:
            report_score = (reports_submitted / reports_expected) * 50
        
        if photos_expected > 0:
            photo_score = (photos_uploaded / photos_expected) * 50
        
        total_score = report_score + photo_score
        return Decimal(str(min(total_score, 100)))
