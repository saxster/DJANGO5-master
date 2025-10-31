"""
Knowledge Review Admin Interface

Admin UI for knowledge document review workflow.
Part of Sprint 3: Knowledge Management Models implementation.

Review Workflow:
- Pending → Approved/Rejected
- Quality scoring (accuracy, completeness, relevance)
- Publication approval

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling

Created: 2025-10-11
"""

import logging
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from apps.onboarding.models import KnowledgeReview

logger = logging.getLogger(__name__)


@admin.register(KnowledgeReview)
class KnowledgeReviewAdmin(admin.ModelAdmin):
    """
    Admin interface for Knowledge Reviews.

    Features:
    - Review pending documents
    - Approve/reject for publication
    - View quality scores
    - Track review workflow
    """

    list_display = (
        'review_id_short', 'document_title', 'reviewer',
        'status_colored', 'overall_quality', 'approved_for_publication',
        'reviewed_at'
    )

    list_filter = ('status', 'approved_for_publication', 'reviewed_at', 'cdtz')
    search_fields = (
        'review_id', 'document__document_title',
        'reviewer__peoplename', 'notes'
    )
    readonly_fields = (
        'review_id', 'document', 'reviewed_at',
        'cdtz', 'mdtz'
    )

    fieldsets = (
        ('Review Information', {
            'fields': ('review_id', 'document', 'reviewer', 'status')
        }),
        ('Quality Scores', {
            'fields': (
                'accuracy_score', 'completeness_score',
                'relevance_score'
            ),
            'description': 'Score range: 0.00 (poor) to 1.00 (excellent)'
        }),
        ('Review Content', {
            'fields': ('notes', 'approval_conditions', 'feedback_data')
        }),
        ('Approval', {
            'fields': ('approved_for_publication', 'reviewed_at')
        }),
        ('Audit', {
            'fields': ('cdtz', 'mdtz'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_reviews', 'reject_reviews', 'export_review_data']
    list_select_related = ('document', 'reviewer')
    date_hierarchy = 'cdtz'

    def review_id_short(self, obj):
        """Show shortened UUID."""
        return f"{str(obj.review_id)[:8]}..."
    review_id_short.short_description = "Review ID"

    def document_title(self, obj):
        """Show document title."""
        return obj.document.document_title[:50] + '...' if len(obj.document.document_title) > 50 else obj.document.document_title
    document_title.short_description = "Document"

    def status_colored(self, obj):
        """Show status with color coding."""
        colors = {
            'pending': '#cc6600',   # Orange
            'approved': '#009933',  # Green
            'rejected': '#cc0000',  # Red
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = "Status"

    def overall_quality(self, obj):
        """Show overall quality score with color."""
        score = obj.get_overall_quality_score()

        if score >= 0.8:
            color = '#009933'  # Green
        elif score >= 0.6:
            color = '#cc6600'  # Orange/Amber
        else:
            color = '#cc0000'  # Red

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
            color,
            score
        )
    overall_quality.short_description = "Quality Score"

    def approve_reviews(self, request, queryset):
        """Approve selected pending reviews."""
        updated = 0
        for review in queryset.filter(status='pending'):
            try:
                review.approve(
                    notes=review.notes or 'Bulk approval',
                    conditions=''
                )
                updated += 1
            except Exception as e:
                logger.error(f"Error approving review {review.review_id}: {e}")

        self.message_user(request, f"Approved {updated} reviews.")
    approve_reviews.short_description = "Approve reviews"

    def reject_reviews(self, request, queryset):
        """Reject selected pending reviews."""
        updated = 0
        for review in queryset.filter(status='pending'):
            try:
                review.reject(notes=review.notes or 'Bulk rejection')
                updated += 1
            except Exception as e:
                logger.error(f"Error rejecting review {review.review_id}: {e}")

        self.message_user(request, f"Rejected {updated} reviews.", level='warning')
    reject_reviews.short_description = "Reject reviews"

    def export_review_data(self, request, queryset):
        """Export review data."""
        self.message_user(request, "Export functionality to be implemented.")
    export_review_data.short_description = "Export review data"
