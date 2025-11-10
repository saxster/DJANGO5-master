"""
PostOrderAcknowledgement Model - Digital Post Orders Compliance

Tracks acknowledgement of digital post orders by workers before shift start.

Industry Best Practice: Workers must read and acknowledge post orders before
starting their shift. This ensures they understand:
- Duties and responsibilities
- Emergency procedures
- Reporting requirements
- Site-specific protocols

Compliance Requirement: Some facilities require documented acknowledgement
for regulatory compliance and liability protection.

Author: Claude Code
Created: 2025-11-03
Phase: 2 - Post Assignment Model
"""

from django.db import models
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.core.models import BaseModel, TenantAwareModel
from apps.tenants.managers import TenantAwareManager
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

import hashlib
import logging

logger = logging.getLogger(__name__)


class PostOrderAcknowledgement(BaseModel, TenantAwareModel):
    """
    Tracks worker acknowledgement of post orders.

    Each time post orders are updated (version incremented), workers must
    re-acknowledge before they can check in. This ensures workers always
    have current information.

    Workflow:
    1. Worker assigned to post
    2. Before check-in, mobile app shows post orders
    3. Worker reads and clicks "I Acknowledge"
    4. Record created with timestamp and version
    5. Worker can now check in

    Compliance:
    - Creates audit trail for liability protection
    - Proves worker was informed of procedures
    - Required for high-risk posts (armed, cash, critical assets)
    """

    # ========== Core Acknowledgement ==========

    worker = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='post_order_acknowledgements',
        db_index=True,
        help_text=_("Worker who acknowledged post orders")
    )

    post = models.ForeignKey(
        'attendance.Post',
        on_delete=models.CASCADE,
        related_name='acknowledgements',
        db_index=True,
        help_text=_("Post whose orders were acknowledged")
    )

    post_assignment = models.ForeignKey(
        'attendance.PostAssignment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='post_order_acknowledgements',
        help_text=_("Assignment this acknowledgement is for (optional)")
    )

    # ========== Post Orders Version ==========

    post_orders_version = models.IntegerField(
        help_text=_("Version of post orders that was acknowledged")
    )

    post_orders_content_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text=_("SHA-256 hash of post orders content for integrity verification")
    )

    # ========== Acknowledgement Details ==========

    acknowledged_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_("When post orders were acknowledged")
    )

    acknowledgement_date = models.DateField(
        auto_now_add=True,
        db_index=True,
        help_text=_("Date of acknowledgement (for daily queries)")
    )

    # ========== Device & Location Tracking ==========

    device_id = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Device ID where acknowledgement occurred")
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_("IP address where acknowledgement occurred")
    )

    user_agent = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Browser/app user agent")
    )

    gps_location = models.JSONField(
        null=True,
        blank=True,
        help_text=_("GPS location where acknowledgement occurred {'lat': float, 'lng': float}")
    )

    # ========== Acknowledgement Method ==========

    acknowledgement_method = models.CharField(
        max_length=50,
        default='mobile_app',
        choices=[
            ('mobile_app', _('Mobile App')),
            ('web_portal', _('Web Portal')),
            ('paper_signed', _('Paper Form (Digitized)')),
            ('verbal_confirmed', _('Verbal Confirmation (Documented)')),
            ('auto_assigned', _('Auto-assigned (System)')),
        ],
        help_text=_("How acknowledgement was obtained")
    )

    # ========== Read Time Tracking ==========

    time_to_acknowledge_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Seconds spent reading post orders before acknowledging")
    )

    minimum_read_time_met = models.BooleanField(
        default=True,
        help_text=_("Whether minimum required reading time was met")
    )

    # ========== Quiz/Comprehension (Optional) ==========

    quiz_taken = models.BooleanField(
        default=False,
        help_text=_("Whether comprehension quiz was taken")
    )

    quiz_score = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Quiz score (0-100)")
    )

    quiz_passed = models.BooleanField(
        default=False,
        help_text=_("Whether quiz was passed")
    )

    quiz_results = models.JSONField(
        null=True,
        blank=True,
        help_text=_("Detailed quiz results")
    )

    # ========== Signature (Digital) ==========

    digital_signature = models.TextField(
        blank=True,
        help_text=_("Digital signature data (base64 encoded image or signature string)")
    )

    signature_verified = models.BooleanField(
        default=False,
        help_text=_("Whether signature was verified")
    )

    # ========== Acknowledgement Text ==========

    acknowledgement_statement = models.TextField(
        default="I have read and understood the post orders for this duty station.",
        help_text=_("Statement that worker acknowledged")
    )

    worker_comments = models.TextField(
        blank=True,
        help_text=_("Optional comments from worker")
    )

    # ========== Validity & Expiration ==========

    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text=_("When this acknowledgement becomes valid")
    )

    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When this acknowledgement expires (null = indefinite)")
    )

    is_valid = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this acknowledgement is currently valid")
    )

    # ========== Supervisor Verification ==========

    supervisor_verified = models.BooleanField(
        default=False,
        help_text=_("Whether supervisor verified this acknowledgement")
    )

    verified_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_acknowledgements',
        help_text=_("Supervisor who verified acknowledgement")
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When acknowledgement was verified")
    )

    # ========== Metadata ==========

    acknowledgement_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Extensible metadata for acknowledgement tracking")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_post_order_acknowledgement'
        verbose_name = _('Post Order Acknowledgement')
        verbose_name_plural = _('Post Order Acknowledgements')
        unique_together = [
            ('worker', 'post', 'post_orders_version', 'acknowledgement_date', 'tenant'),
        ]
        indexes = [
            models.Index(
                fields=['tenant', 'worker', 'acknowledged_at'],
                name='poa_worker_time_idx'
            ),
            models.Index(
                fields=['tenant', 'post', 'post_orders_version'],
                name='poa_post_version_idx'
            ),
            models.Index(
                fields=['tenant', 'acknowledgement_date', 'is_valid'],
                name='poa_date_valid_idx'
            ),
            models.Index(
                fields=['tenant', 'is_valid', 'valid_until'],
                name='poa_validity_idx'
            ),
        ]
        ordering = ['-acknowledged_at']

    def __str__(self):
        worker_name = self.worker.get_full_name() if hasattr(self.worker, 'get_full_name') else str(self.worker)
        return f"{worker_name} acknowledged {self.post.post_code} v{self.post_orders_version} on {self.acknowledgement_date}"

    def save(self, *args, **kwargs):
        """Auto-populate acknowledgement_date from acknowledged_at"""
        if not self.acknowledgement_date and self.acknowledged_at:
            self.acknowledgement_date = self.acknowledged_at.date()

        # Generate content hash if not provided
        if not self.post_orders_content_hash and self.post:
            import hashlib
            content = f"{self.post.post_orders}{self.post.duties_summary}{self.post.emergency_procedures}"
            self.post_orders_content_hash = hashlib.sha256(content.encode()).hexdigest()

        super().save(*args, **kwargs)

    def is_expired(self):
        """Check if acknowledgement has expired"""
        if not self.valid_until:
            return False  # No expiration
        return timezone.now() > self.valid_until

    def invalidate(self, reason=""):
        """Invalidate this acknowledgement"""
        self.is_valid = False
        if reason:
            if not self.acknowledgement_metadata:
                self.acknowledgement_metadata = {}
            self.acknowledgement_metadata['invalidation_reason'] = reason
            self.acknowledgement_metadata['invalidated_at'] = timezone.now().isoformat()
        self.save(update_fields=['is_valid', 'acknowledgement_metadata'])

    def verify_by_supervisor(self, supervisor):
        """Mark acknowledgement as verified by supervisor"""
        self.supervisor_verified = True
        self.verified_by = supervisor
        self.verified_at = timezone.now()
        self.save(update_fields=['supervisor_verified', 'verified_by', 'verified_at'])

    def calculate_hash(self):
        """Calculate hash of current post orders content"""
        import hashlib
        content = f"{self.post.post_orders}{self.post.duties_summary}{self.post.emergency_procedures}"
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self):
        """Verify post orders haven't changed since acknowledgement"""
        current_hash = self.calculate_hash()
        return current_hash == self.post_orders_content_hash

    @classmethod
    def has_valid_acknowledgement(cls, worker, post, date=None):
        """
        Check if worker has valid acknowledgement for post

        Args:
            worker: People instance or ID
            post: Post instance or ID
            date: Date to check (defaults to today)

        Returns:
            bool: True if valid acknowledgement exists
        """
        if date is None:
            date = timezone.now().date()

        worker_id = worker if isinstance(worker, int) else worker.id
        post_id = post if isinstance(post, int) else post.id

        return cls.objects.filter(
            worker_id=worker_id,
            post_id=post_id,
            acknowledgement_date=date,
            is_valid=True
        ).exists()

    @classmethod
    def get_latest_acknowledgement(cls, worker, post):
        """Get worker's latest acknowledgement for post"""
        worker_id = worker if isinstance(worker, int) else worker.id
        post_id = post if isinstance(post, int) else post.id

        return cls.objects.filter(
            worker_id=worker_id,
            post_id=post_id,
            is_valid=True
        ).order_by('-acknowledged_at').first()

    @classmethod
    def bulk_invalidate_for_post(cls, post, reason="Post orders updated"):
        """Invalidate all acknowledgements when post orders change"""
        cls.objects.filter(
            post=post,
            is_valid=True
        ).update(
            is_valid=False
        )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'worker': {
                'id': self.worker.id,
                'name': self.worker.get_full_name() if hasattr(self.worker, 'get_full_name') else str(self.worker)
            },
            'post': {
                'id': self.post.id,
                'code': self.post.post_code,
                'name': self.post.post_name
            },
            'post_orders_version': self.post_orders_version,
            'acknowledged_at': self.acknowledged_at.isoformat(),
            'acknowledgement_date': self.acknowledgement_date.isoformat(),
            'is_valid': self.is_valid,
            'is_expired': self.is_expired(),
            'integrity_verified': self.verify_integrity(),
            'supervisor_verified': self.supervisor_verified,
            'quiz_passed': self.quiz_passed if self.quiz_taken else None,
        }
    objects = TenantAwareManager()
