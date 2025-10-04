"""
DocumentSubmission Model

Document uploads and verification for onboarding candidates.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import EnhancedTenantModel


class DocumentType(models.TextChoices):
    """Document type choices"""
    RESUME = 'RESUME', _('Resume/CV')
    AADHAAR = 'AADHAAR', _('Aadhaar Card')
    PAN = 'PAN', _('PAN Card')
    PASSPORT = 'PASSPORT', _('Passport')
    DRIVING_LICENSE = 'DRIVING_LICENSE', _('Driving License')
    EDUCATIONAL_CERTIFICATE = 'EDUCATIONAL_CERTIFICATE', _('Educational Certificate')
    EXPERIENCE_CERTIFICATE = 'EXPERIENCE_CERTIFICATE', _('Experience Certificate')
    OFFER_LETTER = 'OFFER_LETTER', _('Offer Letter')
    SIGNED_CONTRACT = 'SIGNED_CONTRACT', _('Signed Contract')
    BANK_DETAILS = 'BANK_DETAILS', _('Bank Account Details')
    ADDRESS_PROOF = 'ADDRESS_PROOF', _('Address Proof')
    PHOTO = 'PHOTO', _('Photograph')
    MEDICAL_CERTIFICATE = 'MEDICAL_CERTIFICATE', _('Medical Fitness Certificate')
    POLICE_CLEARANCE = 'POLICE_CLEARANCE', _('Police Clearance Certificate')
    NDA = 'NDA', _('NDA/Confidentiality Agreement')
    PROFESSIONAL_LICENSE = 'PROFESSIONAL_LICENSE', _('Professional License')
    INSURANCE = 'INSURANCE', _('Insurance Documents')
    OTHER = 'OTHER', _('Other')


class DocumentSubmission(EnhancedTenantModel):
    """
    Document uploads for onboarding candidates.

    Supports OCR extraction, AI validation, and expiry tracking.
    """

    class VerificationStatus(models.TextChoices):
        """Document verification status"""
        PENDING = 'PENDING', _('Pending Verification')
        VERIFIED = 'VERIFIED', _('Verified')
        REJECTED = 'REJECTED', _('Rejected')
        EXPIRED = 'EXPIRED', _('Expired')
        REQUIRES_REUPLOAD = 'REQUIRES_REUPLOAD', _('Requires Re-upload')

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='documents'
    )

    # Document details
    document_type = models.CharField(
        _('Document Type'),
        max_length=40,
        choices=DocumentType.choices
    )

    document_file = models.FileField(
        _('Document File'),
        upload_to='people_onboarding/documents/%Y/%m/'
    )

    file_size = models.PositiveBigIntegerField(_('File Size (bytes)'), null=True, blank=True)
    file_hash = models.CharField(_('File Hash'), max_length=64, blank=True)

    # Verification
    verification_status = models.CharField(
        _('Verification Status'),
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )

    verified_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_onboarding_documents'
    )

    verified_at = models.DateTimeField(_('Verified At'), null=True, blank=True)
    verification_notes = models.TextField(_('Verification Notes'), blank=True)

    # OCR Extracted Data
    extracted_data = models.JSONField(
        _('Extracted Data'),
        default=dict,
        blank=True,
        help_text=_('Data extracted via OCR/AI')
    )

    # Dates
    issue_date = models.DateField(_('Issue Date'), null=True, blank=True)
    expiry_date = models.DateField(_('Expiry Date'), null=True, blank=True)

    # Rejection
    rejection_reason = models.TextField(_('Rejection Reason'), blank=True)

    # Flags
    is_mandatory = models.BooleanField(_('Is Mandatory'), default=False)
    is_sensitive = models.BooleanField(
        _('Is Sensitive'),
        default=False,
        help_text=_('Contains PII/sensitive information')
    )

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_document'
        verbose_name = _('Document Submission')
        verbose_name_plural = _('Document Submissions')
        indexes = [
            models.Index(fields=['onboarding_request', 'document_type']),
            models.Index(fields=['verification_status']),
            models.Index(fields=['expiry_date']),
        ]

    def __str__(self):
        return f"{self.onboarding_request.request_number} - {self.get_document_type_display()}"

    def is_expired(self):
        """Check if document has expired"""
        if self.expiry_date:
            from django.utils import timezone
            return timezone.now().date() > self.expiry_date
        return False