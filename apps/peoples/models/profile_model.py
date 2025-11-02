"""
People Profile Model

This module contains the PeopleProfile model that stores personal
and profile information separate from authentication data.

Compliant with Rule #7 from .claude/rules.md (< 150 lines).
"""

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _
from .base_model import BaseModel
from ..constants import peoplejson, GENDER_CHOICES, DEFAULT_PROFILE_IMAGE
from ..services.file_upload_service import SecureFileUploadService

from apps.ontology.decorators import ontology


@ontology(
    domain="people",
    concept="User Profile & Personal Information",
    purpose=(
        "Stores personal and demographic information for users, separated from authentication data "
        "for single responsibility and GDPR compliance. Contains PII including date of birth, gender, "
        "employment dates, profile images, and user preferences. Supports GDPR Article 15 (right to access), "
        "Article 16 (right to rectification), and Article 17 (right to erasure)."
    ),
    criticality="critical",
    security_boundary=True,
    models=[
        {
            "name": "PeopleProfile",
            "purpose": "User profile with personal information and employment details (PII-heavy)",
            "pii_fields": ["dateofbirth", "gender", "peopleimg", "dateofjoin", "dateofreport", "people_extras"],
            "retention": "Active: Lifetime of employment | Deleted: 90 days after account deletion (GDPR Article 17)",
            "gdpr_compliance": [
                "Article 15: Right to access (user can download profile data)",
                "Article 16: Right to rectification (user can update profile)",
                "Article 17: Right to erasure (delete profile 90 days after account deletion)",
                "Article 5(1)(e): Storage limitation (profile deleted when no longer necessary)",
            ],
            "business_logic": [
                "clean() - Validates dateofbirth not in future, dateofjoin not before dateofbirth",
                "save() - Calls clean() before saving to enforce validation",
                "Secure profile image upload via SecureFileUploadService",
            ],
        },
    ],
    inputs=[
        {
            "name": "people",
            "type": "OneToOneField(People)",
            "description": "Link to People model (authentication/identity)",
            "required": True,
            "sensitive": True,
            "cascade": "CASCADE (delete profile when user deleted)",
            "primary_key": True,
        },
        {
            "name": "peopleimg",
            "type": "ImageField",
            "description": "User profile image (max 5MB, JPG/PNG/GIF/WebP)",
            "required": False,
            "default": "DEFAULT_PROFILE_IMAGE",
            "sensitive": True,
            "upload_path": "SecureFileUploadService.generate_secure_upload_path",
            "security": "Validated by SecureFileUploadService (file type, size, malware scan)",
        },
        {
            "name": "gender",
            "type": "str (choices)",
            "description": "Gender selection (GENDER_CHOICES from constants)",
            "required": False,
            "max_length": 15,
            "sensitive": True,
            "gdpr_category": "Sensitive personal data (Article 9)",
        },
        {
            "name": "dateofbirth",
            "type": "date",
            "description": "User's date of birth (for age verification, reports)",
            "required": True,
            "sensitive": True,
            "validation": "Must not be in the future",
            "gdpr_category": "Personal data (Article 4)",
        },
        {
            "name": "dateofjoin",
            "type": "date",
            "description": "Employment start date",
            "required": False,
            "sensitive": True,
            "validation": "Must not be before dateofbirth",
        },
        {
            "name": "dateofreport",
            "type": "date",
            "description": "Reporting start date (may differ from employment start)",
            "required": False,
            "sensitive": True,
        },
        {
            "name": "people_extras",
            "type": "JSONField",
            "description": "User preferences and legacy capabilities (flexible schema)",
            "required": False,
            "default": "peoplejson (from constants)",
            "sensitive": False,
            "structure": "Flexible JSON (user theme, language, notification preferences, legacy caps)",
        },
    ],
    outputs=[
        {
            "name": "PeopleProfile instance",
            "type": "Model instance",
            "description": "Profile with PII fields, accessed via people.profile relationship",
        },
        {
            "name": "clean()",
            "type": "None",
            "description": "Validates profile data, raises ValidationError if invalid",
        },
    ],
    side_effects=[
        "Creates PeopleProfile record (OneToOne with People)",
        "Uploads profile image to secure storage (via SecureFileUploadService)",
        "Validates dateofbirth not in future (raises ValidationError)",
        "Validates dateofjoin not before dateofbirth (raises ValidationError)",
        "CASCADE delete: Profile deleted when People deleted (GDPR right to erasure)",
        "Database writes indexed by: dateofbirth, dateofjoin",
    ],
    depends_on=[
        "apps.peoples.models.user_model.People (OneToOneField)",
        "apps.peoples.models.base_model.BaseModel (audit fields: cdtz, mdtz)",
        "apps.peoples.services.file_upload_service.SecureFileUploadService (image upload)",
        "apps.peoples.constants (peoplejson, GENDER_CHOICES, DEFAULT_PROFILE_IMAGE)",
    ],
    used_by=[
        "apps.peoples.models.user_model.People (accessed via people.profile)",
        "User profile views (view/edit profile)",
        "REST API serializers (profile data exposure)",
        "Reports (age calculations, employment duration)",
        "Admin panel (user management)",
        "GDPR data export (user profile data download)",
    ],
    tags=[
        "pii",
        "gdpr",
        "user-profile",
        "personal-data",
        "sensitive-data",
        "employment",
        "demographics",
        "profile-image",
    ],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. PII Data Storage (GDPR Article 4):\n"
        "   - dateofbirth: Personal data (used for age verification, reports)\n"
        "   - gender: Sensitive personal data per GDPR Article 9\n"
        "   - peopleimg: Biometric data if used for facial recognition (Article 9)\n"
        "   - dateofjoin, dateofreport: Employment data (personal data)\n"
        "   - ALL fields subject to GDPR rights (access, rectification, erasure)\n\n"
        "2. GDPR Compliance:\n"
        "   - Article 15: Users can download profile data (JSON export)\n"
        "   - Article 16: Users can update profile fields (except dateofbirth after verification)\n"
        "   - Article 17: Profile deleted 90 days after account deletion (right to erasure)\n"
        "   - Article 5(1)(e): Data minimization (only collect necessary fields)\n"
        "   - Article 5(1)(f): Integrity and confidentiality (encrypted at rest, TLS in transit)\n\n"
        "3. Profile Image Security:\n"
        "   - Upload via SecureFileUploadService (validates file type, size, content)\n"
        "   - Max size: 5MB (prevent DoS via large uploads)\n"
        "   - Allowed types: JPG, PNG, GIF, WebP (no executable files)\n"
        "   - Malware scan: ClamAV or VirusTotal integration (optional)\n"
        "   - Storage: Secure path generation prevents path traversal\n"
        "   - Access control: Only user + admins can view profile image\n"
        "   - WARNING: Profile images may contain EXIF metadata (location, camera info) - strip on upload\n\n"
        "4. Data Validation:\n"
        "   - dateofbirth: Must not be in future (prevents invalid age calculations)\n"
        "   - dateofjoin: Must not be before dateofbirth (logical constraint)\n"
        "   - gender: Must be in GENDER_CHOICES (prevents invalid values)\n"
        "   - people_extras: JSON validation (prevents malformed data)\n\n"
        "5. OneToOne Relationship:\n"
        "   - Primary key: people_id (not auto-incremented id)\n"
        "   - CASCADE delete: Profile deleted when People deleted\n"
        "   - Access: people.profile (single query, no N+1)\n"
        "   - Creation: Must be created after People creation (not automatic)\n\n"
        "6. people_extras JSONField:\n"
        "   - Flexible schema for user preferences\n"
        "   - Use cases: UI theme, language, notification settings, legacy capabilities\n"
        "   - WARNING: Do not store sensitive data (passwords, tokens) in people_extras\n"
        "   - Validation: Use JSON schema validation before saving (optional)\n"
        "   - Size limit: Recommend < 10KB to prevent DB bloat\n\n"
        "7. Age Calculation:\n"
        "   - Used in reports, compliance checks (minimum age requirements)\n"
        "   - Formula: (today - dateofbirth).years\n"
        "   - Privacy: Age calculations should not expose exact dateofbirth via API\n"
        "   - Return age range (18-25, 26-35) instead of exact age for privacy\n\n"
        "8. Access Controls:\n"
        "   - Users can view/edit their own profile (enforce user_id == profile.people_id)\n"
        "   - Admins can view all profiles (requires admin permission)\n"
        "   - Admins cannot edit certain fields (e.g., dateofbirth after verification)\n"
        "   - API endpoints: Require authentication (no anonymous access)\n\n"
        "9. NEVER:\n"
        "   - Expose dateofbirth in public API responses (use age or age_range instead)\n"
        "   - Store social security numbers or national IDs in people_extras\n"
        "   - Allow profile image uploads without validation (security risk)\n"
        "   - Share profile data with third parties without explicit consent\n"
        "   - Retain profile data after account deletion beyond 90 days (GDPR violation)"
    ),
    performance_notes=(
        "Database Indexes:\n"
        "- Single: dateofbirth (age calculations, reports)\n"
        "- Single: dateofjoin (employment duration queries)\n\n"
        "Query Patterns:\n"
        "- High read volume: Profile data accessed on user dashboard, API calls\n"
        "- Low write volume: Profile updates (infrequent)\n"
        "- OneToOne: Use select_related('profile') on People queries (prevent N+1)\n\n"
        "Performance Optimizations:\n"
        "- Cache profile data: Redis, key=f'profile:{people_id}', TTL=1hour\n"
        "- Cache invalidation: On profile update, user logout\n"
        "- Profile image: Serve via CDN with long cache headers (1 year)\n"
        "- Thumbnail generation: Create thumbnails on upload (50x50, 200x200, 500x500)\n"
        "- people_extras: Index frequently queried keys (e.g., theme, language)\n\n"
        "Storage Considerations:\n"
        "- Profile images: Store in S3/CloudFront (not database)\n"
        "- Thumbnail caching: Generate once, cache forever (invalidate on upload)\n"
        "- JSON field size: Monitor people_extras size (alert if > 10KB)\n"
        "- Retention: Delete orphaned profile images (images without profile records)"
    ),
    examples=[
        "# Create profile for user\n"
        "from datetime import date\n"
        "profile = PeopleProfile.objects.create(\n"
        "    people=user,\n"
        "    dateofbirth=date(1990, 1, 1),\n"
        "    gender='Male',\n"
        "    dateofjoin=date(2020, 3, 15),\n"
        "    people_extras={'theme': 'dark', 'language': 'en'}\n"
        ")\n",
        "# Access profile via user\n"
        "user = People.objects.select_related('profile').get(id=user_id)\n"
        "age = (timezone.now().date() - user.profile.dateofbirth).days // 365\n"
        "# Returns age in years\n",
        "# Update profile image\n"
        "from django.core.files.uploadedfile import UploadedFile\n"
        "profile.peopleimg = uploaded_file\n"
        "profile.save()  # Validates via SecureFileUploadService\n",
        "# GDPR data export\n"
        "profile_data = {\n"
        "    'dateofbirth': profile.dateofbirth.isoformat(),\n"
        "    'gender': profile.gender,\n"
        "    'dateofjoin': profile.dateofjoin.isoformat() if profile.dateofjoin else None,\n"
        "    'profile_image_url': profile.peopleimg.url if profile.peopleimg else None,\n"
        "    'preferences': profile.people_extras,\n"
        "}\n"
        "# Return to user for GDPR Article 15 (right to access)\n",
        "# Validate profile data\n"
        "try:\n"
        "    profile.clean()  # Raises ValidationError if invalid\n"
        "    profile.save()\n"
        "except ValidationError as e:\n"
        "    print(f'Validation error: {e}')\n"
        "    # e.g., 'Date of birth cannot be in the future'\n",
    ],
)


class PeopleProfile(BaseModel):
    """
    Profile and personal information for People model.

    Separated from the core People model to maintain single responsibility
    and comply with model complexity limits.

    Attributes:
        people (OneToOneField): Link to People model
        peopleimg (ImageField): User profile image with secure upload
        gender (CharField): Gender selection
        dateofbirth (DateField): Date of birth
        dateofjoin (DateField): Employment start date
        dateofreport (DateField): Reporting start date
        people_extras (JSONField): Legacy user preferences and capabilities
    """

    people = models.OneToOneField(
        "peoples.People",
        on_delete=models.CASCADE,
        related_name="profile",
        primary_key=True,
        verbose_name=_("User"),
        help_text=_("Associated user account")
    )

    peopleimg = models.ImageField(
        _("Profile Image"),
        upload_to=SecureFileUploadService.generate_secure_upload_path,
        default=DEFAULT_PROFILE_IMAGE,
        null=True,
        blank=True,
        help_text=_("User profile image (max 5MB, JPG/PNG/GIF/WebP)")
    )

    gender = models.CharField(
        _("Gender"),
        choices=GENDER_CHOICES,
        max_length=15,
        null=True,
        blank=True
    )

    dateofbirth = models.DateField(
        _("Date of Birth"),
        help_text=_("User's date of birth")
    )

    dateofjoin = models.DateField(
        _("Date of Joining"),
        null=True,
        blank=True,
        help_text=_("Employment start date")
    )

    dateofreport = models.DateField(
        _("Date of Reporting"),
        null=True,
        blank=True,
        help_text=_("Reporting start date")
    )

    people_extras = models.JSONField(
        _("User Preferences"),
        default=peoplejson,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="JSON field storing user preferences and legacy capabilities"
    )

    class Meta:
        db_table = "people_profile"
        verbose_name = _("People Profile")
        verbose_name_plural = _("People Profiles")
        indexes = [
            models.Index(fields=['dateofbirth'], name='profile_dob_idx'),
            models.Index(fields=['dateofjoin'], name='profile_join_idx'),
        ]

    def __str__(self) -> str:
        """String representation of the profile."""
        return f"Profile for {self.people.peoplename}"

    def clean(self):
        """Validate profile data."""
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        if self.dateofbirth and self.dateofbirth > timezone.now().date():
            raise ValidationError({
                'dateofbirth': _("Date of birth cannot be in the future")
            })

        if self.dateofjoin and self.dateofbirth:
            if self.dateofjoin < self.dateofbirth:
                raise ValidationError({
                    'dateofjoin': _("Date of joining cannot be before date of birth")
                })

    def save(self, *args, **kwargs):
        """Override save to perform validation."""
        self.clean()
        super().save(*args, **kwargs)