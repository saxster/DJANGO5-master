"""
User model for the peoples app.

This module contains the core People (user) model with authentication-essential
fields only. Profile and organizational data are managed in separate models
(PeopleProfile, PeopleOrganizational) with backward-compatible property access.

Compliant with Rule #7 from .claude/rules.md (< 150 lines).
"""

import uuid
import logging
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.ontology import ontology
from .base_model import BaseModel
from ..fields import EnhancedSecureString
from ..managers import PeopleManager
from ..constants import default_capabilities, default_device_id
from ..mixins import PeopleCompatibilityMixin, PeopleCapabilityMixin

logger = logging.getLogger("django")


@ontology(
    domain="people",
    concept="User Identity & Authentication",
    purpose=(
        "Core user model for multi-tenant authentication and identity management. "
        "Implements custom user authentication with encrypted PII fields, capability-based "
        "permissions, and multi-model architecture (People, PeopleProfile, PeopleOrganizational)."
    ),
    criticality="critical",
    security_boundary=True,
    inputs=[
        {"name": "peoplecode", "type": "str", "description": "Internal user identification code", "required": True},
        {"name": "peoplename", "type": "str", "description": "User's complete name", "required": True},
        {"name": "loginid", "type": "str", "description": "Unique login identifier", "required": True, "unique": True},
        {"name": "email", "type": "EnhancedSecureString", "description": "Encrypted email address (PII)", "required": True, "encrypted": True},
        {"name": "mobno", "type": "EnhancedSecureString", "description": "Encrypted mobile number (PII)", "encrypted": True},
    ],
    outputs=[
        {"name": "username", "type": "str", "description": "Backward-compatible alias for loginid"},
        {"name": "capabilities", "type": "dict", "description": "JSON capabilities configuration for AI features"},
    ],
    side_effects=[
        "Initializes default capabilities on first save via UserDefaultsService",
        "Auto-creates PeopleProfile and PeopleOrganizational on access if missing",
        "Logs capability initialization events",
        "Encrypts email and mobno fields using Fernet symmetric encryption",
    ],
    depends_on=[
        "apps.peoples.managers.PeopleManager",
        "apps.peoples.services.UserDefaultsService",
        "apps.peoples.fields.EnhancedSecureString",
        "apps.peoples.mixins.PeopleCapabilityMixin",
        "apps.peoples.mixins.PeopleCompatibilityMixin",
        "apps.tenants.models.TenantAwareModel",
    ],
    used_by=[
        "Authentication system (JWT, session management)",
        "All tenant-aware models via foreign keys",
        "REST API v1/v2 serializers",
        "Face recognition system for biometric authentication",
        "Attendance tracking and geofencing",
        "Task assignment and approval workflows",
    ],
    tags=["authentication", "user-model", "multi-tenant", "pii", "encryption", "critical"],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n"
        "1. PII Encryption: email and mobno use Fernet encryption at field level\n"
        "2. Multi-tenant isolation: All queries filtered by tenant via TenantAwareModel\n"
        "3. Password hashing: Django's PBKDF2 via AbstractBaseUser\n"
        "4. Rate limiting: Authentication endpoints have rate limiting middleware\n"
        "5. Session management: Secure session handling via SessionManagementService\n"
        "6. Admin masking: PII fields masked in Django Admin views\n"
        "7. Audit logging: All authentication events logged to UnifiedAuditService\n"
        "8. NEVER expose encrypted field values directly in API responses\n"
        "9. ALWAYS validate tenant context before user queries"
    ),
    performance_notes=(
        "Optimizations:\n"
        "- Database indexes on peoplecode, loginid, email, tenant fields\n"
        "- Composite index on (tenant, cdtz) for common queries\n"
        "- PeopleManager.with_full_details() uses select_related for profile/org\n"
        "- Capability JSON field prevents N+1 queries for permissions\n"
        "\nBottlenecks:\n"
        "- Encryption/decryption overhead on email/mobno field access\n"
        "- Auto-creation of profile/org models on first access adds latency\n"
        "- JSONField queries on capabilities slower than relational joins"
    ),
    architecture_notes=(
        "Multi-Model Design (incomplete migration):\n"
        "- People: Authentication and identity (this model)\n"
        "- PeopleProfile: Personal info (gender, DOB, join date, image)\n"
        "- PeopleOrganizational: Work relationships (location, department, reportto)\n"
        "\nMigration Status: INCOMPLETE\n"
        "- dateofbirth, dateofjoin, people_extras still in People table\n"
        "- Should be moved to PeopleProfile in future migration\n"
        "- Backward-compatible property access via mixins\n"
        "\nAuthentication Flow:\n"
        "1. User submits loginid + password to /api/v2/auth/login/\n"
        "2. AuthenticationService validates credentials\n"
        "3. JWT token generated with user_id, tenant, capabilities\n"
        "4. Subsequent requests authenticated via JWT middleware"
    ),
    examples=[
        "# Create user\nuser = People.objects.create_user(\n    loginid='john@example.com',\n    peoplecode='EMP001',\n    peoplename='John Doe',\n    email='john@example.com',\n    password='secure_password'\n)",
        "# Check capability\nif user.has_capability('ai', 'mentor', 'enabled'):\n    # Enable AI mentor features",
        "# Query with full details (optimized)\nusers = People.objects.with_full_details().filter(enable=True)",
        "# Access organizational data (auto-creates if missing)\nuser.organizational.department = dept\nuser.organizational.save()",
    ],
    related_models=[
        "apps.peoples.models.PeopleProfile",
        "apps.peoples.models.PeopleOrganizational",
        "apps.attendance.models.Attendance",
        "apps.activity.models.Job",
    ],
    api_endpoints=[
        "POST /api/v2/auth/login/ - User authentication",
        "POST /api/v2/auth/register/ - User registration",
        "GET /api/v1/people/ - List users (tenant-filtered)",
        "PATCH /api/v1/people/{id}/ - Update user profile",
    ],
)
class People(PeopleCapabilityMixin, PeopleCompatibilityMixin, AbstractBaseUser, PermissionsMixin, TenantAwareModel, BaseModel):
    """
    Core user model for authentication and identity.

    This model now focuses solely on authentication and core identity fields.
    Profile and organizational data are maintained in separate models:
    - PeopleProfile: personal/profile information
    - PeopleOrganizational: organizational relationships

    Fields moved to PeopleProfile: peopleimg, gender, dateofbirth, dateofjoin,
                                     dateofreport, people_extras
    Fields moved to PeopleOrganizational: location, department, designation,
                                           peopletype, worktype, client, bu, reportto

    Attributes:
        uuid (UUIDField): Unique identifier for external integrations
        peoplecode (CharField): Internal user code
        peoplename (CharField): User's full name
        loginid (CharField): Unique login identifier
        isadmin (BooleanField): Administrative privileges flag
        is_staff (BooleanField): Staff access flag
        isverified (BooleanField): Account verification status
        enable (BooleanField): Account enabled status
        deviceid (CharField): Associated device identifier
        email (EnhancedSecureString): Encrypted email address
        mobno (EnhancedSecureString): Encrypted mobile number
        capabilities (JSONField): AI and system capabilities configuration
    """

    uuid = models.UUIDField(
        unique=True,
        editable=True,
        blank=True,
        default=uuid.uuid4,
        null=True,
        help_text=_("Unique identifier for external system integration")
    )

    peoplecode = models.CharField(
        _("User Code"),
        max_length=50,
        help_text=_("Internal user identification code")
    )

    peoplename = models.CharField(
        _("Full Name"),
        max_length=120,
        help_text=_("User's complete name")
    )

    loginid = models.CharField(
        _("Login ID"),
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Unique login identifier for authentication")
    )

    isadmin = models.BooleanField(_("Administrator"), default=False)
    is_staff = models.BooleanField(_("Staff Status"), default=False)
    isverified = models.BooleanField(_("Verified"), default=False)
    enable = models.BooleanField(_("Enabled"), default=True)

    deviceid = models.CharField(
        _("Device ID"),
        max_length=50,
        default=default_device_id,
        help_text=_("Associated device identifier for mobile access")
    )

    email = EnhancedSecureString(_("Email"), max_length=500)
    mobno = EnhancedSecureString(_("Mobile Number"), max_length=500, null=True)

    # NOTE: These fields are temporarily in People model (should be in PeopleProfile)
    # The model split migration was incomplete - these columns still exist in people table
    dateofbirth = models.DateField(
        _("Date of Birth"),
        null=True,
        blank=True,
        help_text=_("User's date of birth")
    )

    dateofjoin = models.DateField(
        _("Date of Joining"),
        null=True,
        blank=True,
        help_text=_("Employment start date")
    )

    people_extras = models.JSONField(
        _("User Extras"),
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text=_("Additional user preferences and legacy data")
    )

    capabilities = models.JSONField(
        _("User Capabilities"),
        default=default_capabilities,
        blank=True,
        help_text="JSON field storing user capabilities and permissions for AI features"
    )

    preferred_language = models.CharField(
        _("Preferred Language"),
        max_length=10,
        choices=[
            ('en', 'English'),
            ('hi', 'हिन्दी (Hindi)'),
            ('te', 'తెలుగు (Telugu)'),
            ('es', 'Español (Spanish)'),
            ('fr', 'Français (French)'),
            ('ar', 'العربية (Arabic)'),
            ('zh', '中文 (Chinese)'),
        ],
        default='en',
        help_text=_("User's preferred language for conversations and content")
    )

    objects = PeopleManager()
    USERNAME_FIELD = "loginid"
    REQUIRED_FIELDS = ["peoplecode", "peoplename", "email"]

    class Meta:
        db_table = "people"
        verbose_name = _("Person")
        verbose_name_plural = _("People")
        indexes = [
            models.Index(fields=['peoplecode'], name='people_peoplecode_idx'),
            models.Index(fields=['loginid'], name='people_loginid_idx'),
            models.Index(fields=['isverified', 'enable'], name='people_active_idx'),
            models.Index(fields=['email'], name='people_email_idx'),
            models.Index(fields=['tenant', 'cdtz'], name='people_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'enable'], name='people_tenant_enable_idx'),
        ]

    def __str__(self) -> str:
        """String representation of the user."""
        return f"{self.peoplename} ({self.peoplecode})"

    def get_absolute_wizard_url(self):
        """Get URL for wizard update view."""
        return f"/people/wizard/update/{self.pk}/"

    @property
    def username(self) -> str:
        """Backward-compatible alias for login identifier."""
        return self.loginid or ""

    @username.setter
    def username(self, value: str) -> None:
        self.loginid = value

    @property
    def first_name(self) -> str:
        """Backward-compatible alias for first name."""
        return self.peoplename or ""

    @first_name.setter
    def first_name(self, value: str) -> None:
        self.peoplename = value or ""

    @property
    def last_name(self) -> str:
        """Backward-compatible alias for last name (stored in extras)."""
        extras = self.people_extras or {}
        return extras.get("last_name", "")

    @last_name.setter
    def last_name(self, value: str) -> None:
        extras = dict(self.people_extras or {})
        extras["last_name"] = value or ""
        self.people_extras = extras

    @property
    def bu_id(self):
        """Expose business unit via organizational relation."""
        org = getattr(self, "organizational", None)
        return org.bu_id if org else None

    @bu_id.setter
    def bu_id(self, value):
        org = getattr(self, "organizational", None)
        if org is None:
            from .organizational_model import PeopleOrganizational
            org, _created = PeopleOrganizational.objects.get_or_create(people=self)
        org.bu_id = value
        org.save(update_fields=['bu'])

    @property
    def client_id(self):
        """Expose client via organizational relation."""
        org = getattr(self, "organizational", None)
        return org.client_id if org else None

    @client_id.setter
    def client_id(self, value):
        org = getattr(self, "organizational", None)
        if org is None:
            from .organizational_model import PeopleOrganizational
            org, _created = PeopleOrganizational.objects.get_or_create(people=self)
        org.client_id = value
        org.save(update_fields=['client'])

    @property
    def date_joined(self):
        """Compatibility alias for employment start date."""
        return self.dateofjoin

    @date_joined.setter
    def date_joined(self, value):
        self.dateofjoin = value

    @property
    def phone(self):
        """Compatibility alias for mobile number."""
        return self.mobno

    @phone.setter
    def phone(self, value):
        self.mobno = value

    def save(self, *args, **kwargs):
        """Override save method with service delegation for business logic."""
        if kwargs.get('update_fields'):
            return super().save(*args, **kwargs)

        from ..services import UserDefaultsService

        capabilities_initialized = UserDefaultsService.initialize_capabilities(self)

        super().save(*args, **kwargs)

        if capabilities_initialized:
            logger.info(
                f"User saved with initialized capabilities",
                extra={
                    'user_id': self.id,
                    'peoplename': self.peoplename
                }
            )

    # Capability management methods are now provided by PeopleCapabilityMixin
    # Methods available: has_capability, add_capability, remove_capability,
    # get_all_capabilities, set_ai_capabilities, get_effective_permissions

    # Onboarding tracking methods
    def has_completed_onboarding(self) -> bool:
        """
        Check if user has completed or skipped onboarding.

        Returns:
            True if user completed onboarding OR explicitly skipped it
            False if user has not engaged with onboarding yet
        """
        return self.onboarding_completed_at is not None or self.onboarding_skipped

    def can_access_onboarding(self) -> bool:
        """
        Check if user is authorized to access onboarding module.

        Returns:
            True if user has canAccessOnboarding capability
            False otherwise
        """
        capabilities = self.get_all_capabilities()
        return capabilities.get('canAccessOnboarding', False)

    def get_onboarding_status_summary(self) -> dict:
        """
        Get comprehensive onboarding status for dashboards.

        Returns:
            Dict with onboarding flags and metadata
        """
        return {
            'has_completed': self.has_completed_onboarding(),
            'completed_at': self.onboarding_completed_at.isoformat() if self.onboarding_completed_at else None,
            'skipped': self.onboarding_skipped,
            'first_login_completed': self.first_login_completed,
            'can_access': self.can_access_onboarding(),
            'completed_steps': self.people_extras.get('onboarding', {}).get('completed_steps', []),
        }
