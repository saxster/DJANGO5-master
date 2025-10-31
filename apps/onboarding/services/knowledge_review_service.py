"""
Knowledge Review Service - Two-Person Approval Workflow

Implements maker-checker pattern for knowledge base quality assurance.

Workflow States:
1. draft → First reviewer evaluates
2. first_review → Second reviewer evaluates
3. second_review → Both reviewers approve/reject
4. approved/rejected → Final state

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management

Sprint 1-2: Knowledge Management Completion
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

logger = logging.getLogger(__name__)


class KnowledgeReviewService:
    """Service for managing two-person knowledge review workflow."""

    @transaction.atomic
    def submit_first_review(
        self,
        review,
        reviewer,
        decision: str,
        notes: str,
        quality_scores: Dict[str, float],
        conditions: str = ''
    ) -> Dict[str, Any]:
        """
        Submit first review (Subject Matter Expert).

        Args:
            review: KnowledgeReview instance
            reviewer: First reviewer (People instance)
            decision: 'approve' or 'reject'
            notes: Review notes
            quality_scores: Dict with accuracy_score, completeness_score, relevance_score
            conditions: Optional approval conditions

        Returns:
            Dict with status and next steps

        Raises:
            ValidationError: If validation fails
            PermissionDenied: If reviewer not authorized
        """
        try:
            # Validate state
            if review.status not in ['draft', 'first_review']:
                raise ValidationError(
                    f"Cannot submit first review in state: {review.status}"
                )

            # Set first reviewer
            review.first_reviewer = reviewer
            review.status = 'first_review'

            # Set quality scores
            review.accuracy_score = quality_scores.get('accuracy_score')
            review.completeness_score = quality_scores.get('completeness_score')
            review.relevance_score = quality_scores.get('relevance_score')
            review.notes = notes
            review.approval_conditions = conditions

            # Track provenance
            review.provenance_data['first_review'] = {
                'reviewer_id': reviewer.id,
                'reviewer_name': reviewer.peoplename,
                'reviewer_email': reviewer.email,
                'decision': decision,
                'timestamp': timezone.now().isoformat(),
                'quality_scores': quality_scores,
                'notes_preview': notes[:100] if notes else ''
            }

            if decision == 'approve':
                review.first_reviewed_at = timezone.now()
                review.status = 'second_review'
                review.save()

                logger.info(
                    f"First review approved for document {review.document.knowledge_id} "
                    f"by {reviewer.peoplename}"
                )

                return {
                    'success': True,
                    'status': 'second_review',
                    'message': 'First review approved. Awaiting second review.',
                    'next_step': 'Assign second reviewer'
                }
            else:  # reject
                review.status = 'rejected'
                review.first_reviewed_at = timezone.now()
                review.save()

                logger.info(
                    f"First review rejected document {review.document.knowledge_id} "
                    f"by {reviewer.peoplename}"
                )

                return {
                    'success': True,
                    'status': 'rejected',
                    'message': 'Document rejected by first reviewer',
                    'next_step': 'Revision required'
                }

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in first review: {e}")
            raise ValidationError(f"Failed to save review: {str(e)}")

    @transaction.atomic
    def submit_second_review(
        self,
        review,
        reviewer,
        decision: str,
        notes: str,
        conditions: str = ''
    ) -> Dict[str, Any]:
        """
        Submit second review (Quality Assurance).

        Requires first review to be approved.
        """
        try:
            # Validate state
            if review.status != 'second_review':
                raise ValidationError(
                    f"Cannot submit second review in state: {review.status}"
                )

            if not review.first_reviewed_at:
                raise ValidationError("First review must be completed first")

            # Set second reviewer
            review.second_reviewer = reviewer
            review.second_reviewed_at = timezone.now()
            review.notes += f"\n\n[Second Review]\n{notes}"

            # Track provenance
            review.provenance_data['second_review'] = {
                'reviewer_id': reviewer.id,
                'reviewer_name': reviewer.peoplename,
                'reviewer_email': reviewer.email,
                'decision': decision,
                'timestamp': timezone.now().isoformat(),
                'notes_preview': notes[:100] if notes else ''
            }

            if decision == 'approve':
                review.status = 'approved'
                review.approved_for_publication = True
                review.approval_conditions += f"\n{conditions}" if conditions else ''
                review.save()

                logger.info(
                    f"Second review approved for document {review.document.knowledge_id} "
                    f"by {reviewer.peoplename}. Document ready for publication."
                )

                return {
                    'success': True,
                    'status': 'approved',
                    'message': 'Document approved by both reviewers. Ready for publication.',
                    'next_step': 'Publish document'
                }
            else:  # reject
                review.status = 'rejected'
                review.approved_for_publication = False
                review.save()

                logger.info(
                    f"Second review rejected document {review.document.knowledge_id} "
                    f"by {reviewer.peoplename}"
                )

                return {
                    'success': True,
                    'status': 'rejected',
                    'message': 'Document rejected by second reviewer',
                    'next_step': 'Revision required'
                }

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in second review: {e}")
            raise ValidationError(f"Failed to save review: {str(e)}")
