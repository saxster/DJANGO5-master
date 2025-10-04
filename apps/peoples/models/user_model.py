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
from .base_model import BaseModel
from ..fields import EnhancedSecureString
from ..managers import PeopleManager
from ..constants import default_capabilities, default_device_id
from ..mixins import PeopleCompatibilityMixin, PeopleCapabilityMixin

logger = logging.getLogger("django")


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
        ]

    def __str__(self) -> str:
        """String representation of the user."""
        return f"{self.peoplename} ({self.peoplecode})"

    def get_absolute_wizard_url(self):
        """Get URL for wizard update view."""
        return f"/people/wizard/update/{self.pk}/"

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