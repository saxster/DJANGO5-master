"""
CandidateProfile Model

Personal information and contact details for onboarding candidates.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import EnhancedTenantModel
from apps.peoples.fields import EnhancedSecureString


class CandidateProfile(EnhancedTenantModel):
    """
    Personal information for onboarding candidates.

    Stores sensitive data with encryption (email, phone, SSN).
    Once onboarded, this data transfers to the People model.
    """

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # Relationship
    onboarding_request = models.OneToOneField(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='candidate_profile'
    )

    # Personal Information
    first_name = models.CharField(_('First Name'), max_length=100)
    middle_name = models.CharField(_('Middle Name'), max_length=100, blank=True)
    last_name = models.CharField(_('Last Name'), max_length=100)

    date_of_birth = models.DateField(_('Date of Birth'), null=True, blank=True)
    gender = models.CharField(
        _('Gender'),
        max_length=20,
        choices=[
            ('MALE', _('Male')),
            ('FEMALE', _('Female')),
            ('OTHER', _('Other')),
            ('PREFER_NOT_TO_SAY', _('Prefer not to say')),
        ],
        blank=True
    )

    # Contact Information (Encrypted)
    primary_email = EnhancedSecureString(_('Primary Email'), max_length=500)
    secondary_email = EnhancedSecureString(_('Secondary Email'), max_length=500, null=True, blank=True)
    primary_phone = EnhancedSecureString(_('Primary Phone'), max_length=500)
    secondary_phone = EnhancedSecureString(_('Secondary Phone'), max_length=500, null=True, blank=True)

    # Address
    current_address = models.TextField(_('Current Address'), blank=True)
    permanent_address = models.TextField(_('Permanent Address'), blank=True)
    city = models.CharField(_('City'), max_length=100, blank=True)
    state = models.CharField(_('State/Province'), max_length=100, blank=True)
    postal_code = models.CharField(_('Postal Code'), max_length=20, blank=True)
    country = models.CharField(_('Country'), max_length=100, default='India')

    # Identification (Encrypted)
    aadhaar_number = EnhancedSecureString(_('Aadhaar Number'), max_length=500, null=True, blank=True)
    pan_number = EnhancedSecureString(_('PAN Number'), max_length=500, null=True, blank=True)
    passport_number = EnhancedSecureString(_('Passport Number'), max_length=500, null=True, blank=True)
    driving_license = EnhancedSecureString(_('Driving License'), max_length=500, null=True, blank=True)

    # Emergency Contact
    emergency_contact_name = models.CharField(_('Emergency Contact Name'), max_length=200, blank=True)
    emergency_contact_phone = EnhancedSecureString(_('Emergency Contact Phone'), max_length=500, null=True, blank=True)
    emergency_contact_relationship = models.CharField(_('Relationship'), max_length=100, blank=True)

    # Professional Details
    highest_education = models.CharField(_('Highest Education'), max_length=200, blank=True)
    total_experience_years = models.DecimalField(
        _('Total Experience (Years)'),
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )
    current_company = models.CharField(_('Current Company'), max_length=200, blank=True)
    current_designation = models.CharField(_('Current Designation'), max_length=200, blank=True)
    linkedin_url = models.URLField(_('LinkedIn Profile'), max_length=500, blank=True)

    # Skills (JSON for flexibility)
    skills = models.JSONField(_('Skills'), default=list, blank=True)
    certifications = models.JSONField(_('Certifications'), default=list, blank=True)

    # Preferences
    preferred_language = models.CharField(
        _('Preferred Language'),
        max_length=10,
        choices=[
            ('en', 'English'),
            ('hi', 'हिन्दी (Hindi)'),
            ('te', 'తెలుగు (Telugu)'),
            ('ta', 'தமிழ் (Tamil)'),
            ('kn', 'ಕನ್ನಡ (Kannada)'),
            ('ml', 'മലയാളം (Malayalam)'),
        ],
        default='en'
    )

    # Profile picture
    photo = models.ImageField(
        _('Photo'),
        upload_to='people_onboarding/photos/',
        null=True,
        blank=True
    )

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_candidate_profile'
        verbose_name = _('Candidate Profile')
        verbose_name_plural = _('Candidate Profiles')
        indexes = [
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['primary_email']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        """Get candidate's full name"""
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)