"""
Worker document wrapper for OnboardingMedia.
Supports worker onboarding document types:
- Government IDs (front/back)
- Training certificates
- Background check results
- Medical clearance
- Reference letters
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import EnhancedTenantModel


class WorkerDocument(EnhancedTenantModel):
    """
    Worker onboarding document linked to OnboardingMedia.
    Supports 0-N documents per onboarding request.
    """

    class DocumentType(models.TextChoices):
        PHOTO_ID = 'PHOTO_ID', _('Government Photo ID')
        CERTIFICATE = 'CERTIFICATE', _('Training Certificate')
        BACKGROUND_CHECK = 'BACKGROUND_CHECK', _('Background Check Results')
        MEDICAL = 'MEDICAL', _('Medical Clearance')
        UNIFORM_PHOTO = 'UNIFORM_PHOTO', _('Uniform Photo')
        REFERENCE_LETTER = 'REFERENCE_LETTER', _('Reference Letter')
        POLICE_VERIFICATION = 'POLICE_VERIFICATION', _('Police Verification')
        ADDRESS_PROOF = 'ADDRESS_PROOF', _('Address Proof')

    class VerificationStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending Verification')
        VERIFIED = 'VERIFIED', _('Verified')
        REJECTED = 'REJECTED', _('Rejected')
        EXPIRED = 'EXPIRED', _('Expired')

    document_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='worker_documents'
    )
    media = models.OneToOneField(
        'core_onboarding.OnboardingMedia',
        on_delete=models.CASCADE
    )

    # Classification
    document_type = models.CharField(
        _('Document Type'),
        max_length=30,
        choices=DocumentType.choices
    )

    # Verification
    verification_status = models.CharField(
        _('Verification Status'),
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )
    verified_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    # Expiry (for certificates)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Expiration date for certificates/clearances')
    )

    # Rejection reason
    rejection_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'people_onboarding_worker_document'
        verbose_name = 'Worker Document'
        verbose_name_plural = 'Worker Documents'
        indexes = [
            models.Index(fields=['onboarding_request'], name='workerdoc_request_idx'),
            models.Index(fields=['verification_status'], name='workerdoc_status_idx'),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.onboarding_request.request_number}"
