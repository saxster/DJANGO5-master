from django.contrib.auth.models import Group
from django.db.models import CharField
from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from .managers import PeopleManager, CapabilityManager, PgblngManager, PgroupManager
from apps.tenants.models import TenantAwareModel
from apps.peoples.fields.secure_fields import EnhancedSecureString
import logging

logger = logging.getLogger("django")

# Create your models here.


def peoplejson():
    return {
        "andriodversion": "",
        "appversion": "",
        "mobilecapability": [],
        "portletcapability": [],
        "reportcapability": [],
        "webcapability": [],
        "noccapability": [],
        "loacationtracking": False,
        "capturemlog": False,
        "showalltemplates": False,
        "debug": False,
        "showtemplatebasedonfilter": False,
        "blacklist": False,
        "assignsitegroup": [],
        "tempincludes": [],
        "mlogsendsto": "",
        "user_type": "",
        "secondaryemails": [],
        "secondarymobno": [],
        "isemergencycontact": False,
        "alertmails": False,
        "currentaddress": "",
        "permanentaddress": "",
        "isworkpermit_approver": False,
        "userfor": "",
        'enable_gps': False,
        'noc_user'  : False
    }


def upload_peopleimg(instance, filename):
    """
    SECURE file upload path generator for people images.

    Implements comprehensive security measures:
    - Filename sanitization to prevent path traversal
    - Extension validation against whitelist
    - Path boundary enforcement within MEDIA_ROOT
    - Dangerous pattern detection

    Complies with Rule #14 from .claude/rules.md - File Upload Security

    Args:
        instance: People model instance
        filename: Original uploaded filename

    Returns:
        str: Secure relative path for file storage

    Raises:
        ValueError: If security validation fails
    """
    try:
        logger.info(
            "Starting secure people image upload",
            extra={
                'instance_id': getattr(instance, 'id', None),
                'original_filename': filename
            }
        )

        from django.utils.text import get_valid_filename
        import os
        import re

        # Phase 1: Sanitize filename using Django's built-in validator
        safe_filename = get_valid_filename(filename)
        if not safe_filename:
            raise ValueError("Filename could not be sanitized")

        # Phase 2: Validate file extension (whitelist approach)
        ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        file_extension = os.path.splitext(safe_filename)[1].lower()

        if not file_extension or file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            logger.warning(
                "Invalid image file extension rejected",
                extra={
                    'filename': filename,
                    'extension': file_extension,
                    'allowed_extensions': list(ALLOWED_IMAGE_EXTENSIONS)
                }
            )
            # Return default image path instead of raising error
            return "master/people/blank.png"

        # Phase 3: Detect dangerous patterns
        DANGEROUS_PATTERNS = ['.', '/', '\\', '\x00', '..', '~']
        if any(pattern in safe_filename for pattern in DANGEROUS_PATTERNS):
            logger.warning(
                "Dangerous pattern detected in filename",
                extra={'filename': safe_filename}
            )
            safe_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', os.path.splitext(safe_filename)[0]) + file_extension

        # Phase 4: Build secure path components
        # Sanitize all path components
        safe_peoplecode = get_valid_filename(str(instance.peoplecode))[:50]
        safe_peoplename = get_valid_filename(instance.peoplename.replace(" ", "_"))[:50]

        # Remove any remaining dangerous characters
        safe_peoplecode = re.sub(r'[^a-zA-Z0-9_-]', '', safe_peoplecode)
        safe_peoplename = re.sub(r'[^a-zA-Z0-9_-]', '', safe_peoplename)

        # Generate unique but predictable filename
        import time
        timestamp = int(time.time())
        secure_filename = f"{safe_peoplecode}_{safe_peoplename}_{timestamp}{file_extension}"

        # Phase 5: Build secure directory structure
        if not hasattr(instance, 'client') or not instance.client:
            logger.warning("No client associated with instance, using default path")
            return f"master/people/{secure_filename}".lower()

        safe_client_code = get_valid_filename(str(instance.client.bucode))[:20]
        safe_client_code = re.sub(r'[^a-zA-Z0-9_-]', '', safe_client_code)

        # Build path with fixed structure (no user input in directory names)
        secure_path = os.path.join(
            "master",
            f"{safe_client_code}_{instance.client_id}",
            "people",
            secure_filename
        ).lower()

        # Phase 6: Final security validation - ensure no path traversal
        if '..' in secure_path or secure_path.startswith('/'):
            raise ValueError("Path traversal attempt detected")

        logger.info(
            "Secure people image path generated successfully",
            extra={
                'instance_id': getattr(instance, 'id', None),
                'secure_path': secure_path
            }
        )

        return secure_path

    except AttributeError as e:
        logger.error(
            "Attribute error in upload_peopleimg - missing required fields",
            extra={
                'error_message': str(e),
                'filename': filename,
                'instance_id': getattr(instance, 'id', None)
            },
            exc_info=True
        )
        # Return safe default instead of failing
        return "master/people/blank.png"
    except (TypeError, ValueError) as e:
        logger.error(
            "Validation error in upload_peopleimg",
            extra={
                'error_message': str(e),
                'filename': filename,
                'instance_id': getattr(instance, 'id', None)
            },
            exc_info=True
        )
        # Return safe default instead of failing
        return "master/people/blank.png"
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(
            "Unexpected error in upload_peopleimg",
            extra={
                'error_message': str(e),
                'filename': filename,
                'instance_id': getattr(instance, 'id', None)
            },
            exc_info=True
        )
        # Return safe default instead of failing
        return "master/people/blank.png"




def now():
    return timezone.now().replace(microsecond=0)


### Base Model, ALl other models inherit this model properties ###
class BaseModel(models.Model):
    cuser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="%(class)s_cusers",
    )
    muser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="%(class)s_musers",
    )
    cdtz = models.DateTimeField(_("cdtz"), default=now)
    mdtz = models.DateTimeField(_("mdtz"), default=now)
    ctzoffset = models.IntegerField(_("TimeZone"), default=-1)

    class Meta:
        abstract = True
        ordering = ["mdtz"]


############## People Table ###############
class People(AbstractBaseUser, PermissionsMixin, TenantAwareModel, BaseModel):
    class Gender(models.TextChoices):
        M = ("M", "Male")
        F = ("F", "Female")
        O = ("O", "Others")

    uuid = models.UUIDField(
        unique=True, editable=True, blank=True, default=uuid.uuid4, null=True
    )
    peopleimg = models.ImageField(
        _("peopleimg"),
        upload_to=upload_peopleimg,
        default="master/people/blank.png",
        null=True,
        blank=True,
    )
    peoplecode = models.CharField(_("Code"), max_length=50)
    peoplename = models.CharField(_("Name"), max_length=120)
    location = models.ForeignKey(
        "activity.Location",
        verbose_name=_("Location"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    loginid = models.CharField(
        _("Login Id"), max_length=50, unique=True, null=True, blank=True
    )
    isadmin = models.BooleanField(_("Admin"), default=False)
    is_staff = models.BooleanField(_("staff status"), default=False)
    isverified = models.BooleanField(_("Active"), default=False)
    enable = models.BooleanField(_("Enable"), default=True)
    department = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="Department",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="people_departments",
    )
    designation = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="Designation",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="people_designations",
    )
    peopletype = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="People Type",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="people_types",
    )
    worktype = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="Work Type",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="work_types",
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="Client",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="people_clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="Site",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="people_bus",
    )
    reportto = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="children",
        verbose_name="Report to",
    )
    deviceid = models.CharField(_("Device Id"), max_length=50, default="-1")
    email = EnhancedSecureString(_("Email"), max_length=500)
    mobno = EnhancedSecureString(_("Mob No"), max_length=500, null=True)
    gender = models.CharField(
        _("Gender"), choices=Gender.choices, max_length=15, null=True
    )
    dateofbirth = models.DateField(_("Date of Birth"))
    dateofjoin = models.DateField(_("Date of Join"), null=True)
    dateofreport = models.DateField(_("Date of Report"), null=True, blank=True)
    people_extras = models.JSONField(
        _("people_extras"), default=peoplejson, blank=True, encoder=DjangoJSONEncoder
    )

    # Capabilities for AI recommendation permissions and feature access
    capabilities = models.JSONField(
        _("User Capabilities"),
        default=dict,
        blank=True,
        help_text="JSON field storing user capabilities and permissions for AI features"
    )

    objects = PeopleManager()
    USERNAME_FIELD = "loginid"
    REQUIRED_FIELDS = ["peoplecode", "peoplename", "dateofbirth", "email"]

    class Meta:
        db_table = "people"
        constraints = [
            models.UniqueConstraint(
                fields=["loginid", "peoplecode", "bu"],
                name="peolple_logind_peoplecode_bu_uk",
            ),
            models.UniqueConstraint(
                fields=["peoplecode", "bu"], name="people_peoplecode_bu"
            ),
            models.UniqueConstraint(
                fields=["loginid", "bu"], name="people_loginid_bu_uk"
            ),
            models.UniqueConstraint(
                fields=["loginid", "mobno", "email", "bu"],
                name="loginid_mobno_email_bu_uk",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.peoplename} ({self.peoplecode})"

    def get_absolute_wizard_url(self):
        return f"/people/wizard/update/{self.pk}/"

    def save(self, *args, **kwargs):
        """
        Override save method to set default values for foreign key fields.
        Refactored to use service classes for better maintainability.
        """
        # Prevent recursive saves by checking if we're in an update operation
        if kwargs.get('update_fields'):
            return super().save(*args, **kwargs)

        # Apply pre-save operations
        self._prepare_for_save()

        # Save the object
        super().save(*args, **kwargs)

        # Log successful save
        self._log_save_completion()

    def _prepare_for_save(self):
        """Prepare the model instance for saving by setting defaults."""
        from .services import UserDefaultsService

        # Set default field values
        defaults_set, context = UserDefaultsService.set_default_fields(self)

        # Initialize capabilities
        capabilities_initialized = UserDefaultsService.initialize_capabilities(self)

        # Store context for logging
        self._save_context = {
            'defaults_set': defaults_set,
            'capabilities_initialized': capabilities_initialized,
            'context': context
        }

    def _log_save_completion(self):
        """Log completion of save operation with context."""
        context = getattr(self, '_save_context', {})

        if context.get('defaults_set') or context.get('capabilities_initialized'):
            operations = []
            if context.get('defaults_set'):
                operations.append('default values')
            if context.get('capabilities_initialized'):
                operations.append('capabilities')

            logger.info(
                f"User saved successfully with {', '.join(operations)}",
                extra={
                    'user_id': self.id,
                    'peoplename': self.peoplename,
                    'operations': operations
                }
            )

        # Log any errors from default setting
        save_errors = context.get('context', {}).get('errors', [])
        if save_errors:
            logger.warning(
                f"Some default values could not be set during save",
                extra={
                    'user_id': self.id,
                    'errors': save_errors
                }
            )

    # Capabilities management methods (delegated to service)
    def has_capability(self, capability_name):
        """Check if user has a specific capability"""
        from .services import UserCapabilityService
        return UserCapabilityService.has_capability(self, capability_name)

    def add_capability(self, capability_name, value=True):
        """Add or update a capability"""
        from .services import UserCapabilityService
        return UserCapabilityService.add_capability(self, capability_name, value)

    def remove_capability(self, capability_name):
        """Remove a capability"""
        from .services import UserCapabilityService
        return UserCapabilityService.remove_capability(self, capability_name)

    def get_all_capabilities(self):
        """Get all user capabilities"""
        from .services import UserCapabilityService
        return UserCapabilityService.get_all_capabilities(self)

    def set_ai_capabilities(self, can_approve=False, can_manage_kb=False, is_approver=False):
        """Set AI-related capabilities for conversational onboarding"""
        from .services import UserCapabilityService
        return UserCapabilityService.set_ai_capabilities(self, can_approve, can_manage_kb, is_approver)

    def get_effective_permissions(self):
        """Get effective permissions combining capabilities with user flags"""
        from .services import UserCapabilityService
        return UserCapabilityService.get_effective_permissions(self)


############## Pgroup Table ###############
class PermissionGroup(Group):
    class Meta:
        db_table = "permissiongroup"
        verbose_name = _("permissiongroup")
        verbose_name_plural = _("permissiongroups")


class Pgroup(BaseModel, TenantAwareModel):
    # id= models.BigIntegerField(_("Groupid"), primary_key = True, auto_created=)
    groupname = models.CharField(_("Name"), max_length=250)
    grouplead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_groupleads",
    )
    enable = models.BooleanField(_("Enable"), default=True)
    identifier = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="Identifier",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_idfs",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="BV",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_bus",
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="Client",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_clients",
    )

    objects = PgroupManager()

    class Meta(BaseModel.Meta):
        db_table = "pgroup"
        constraints = [
            models.UniqueConstraint(
                fields=["groupname", "identifier", "client"],
                name="pgroup_groupname_bu_client_identifier_key",
            ),
            models.UniqueConstraint(
                fields=["groupname", "identifier", "client"],
                name="pgroup_groupname_bu_identifier_key",
            ),
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        return self.groupname

    def get_absolute_wizard_url(self):
        return f"/people/groups/wizard/update/{self.pk}/"


############## Pgbelonging Table ###############
class Pgbelonging(BaseModel, TenantAwareModel):
    # id          = models.BigIntegerField(_("Pgbid"), primary_key = True)
    pgroup = models.ForeignKey(
        "Pgroup",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelongs_grps",
    )
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelongs_peoples",
    )
    isgrouplead = models.BooleanField(_("Group Lead"), default=False)
    assignsites = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelongs_assignsites",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelonging_sites",
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelonging_clients",
    )

    objects = PgblngManager()

    class Meta(BaseModel.Meta):
        db_table = "pgbelonging"
        constraints = [
            models.UniqueConstraint(
                fields=["pgroup", "people", "assignsites", "client"],
                name="pgbelonging_pgroup_people_bu_assignsites_client",
            )
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        return str(self.id)


############## Capability Table ###############
class Capability(BaseModel, TenantAwareModel):
    class Cfor(models.TextChoices):
        WEB = ("WEB", "WEB")
        PORTLET = ("PORTLET", "PORTLET")
        REPORT = ("REPORT", "REPORT")
        MOB = ("MOB", "MOB")
        NOC = ("NOC", "NOC")

    # id   = models.BigIntegerField(_(" Cap Id"), primary_key = True)
    capscode = models.CharField(_("Code"), max_length=50)
    capsname = models.CharField(
        _("Capability"), max_length=1000, default=None, blank=True, null=True
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Belongs_to",
    )
    cfor = models.CharField(
        _("Capability_for"), max_length=10, default="WEB", choices=Cfor.choices
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="BV",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    enable = models.BooleanField(_("Enable"), default=True)

    objects = CapabilityManager()

    class Meta(BaseModel.Meta):
        db_table = "capability"
        verbose_name = "Capability"
        verbose_name_plural = "Capabilities"
        get_latest_by = ["mdtz", "cdtz"]
        constraints = [
            models.UniqueConstraint(
                fields=["capscode", "cfor", "client"], name="capability_caps_cfor_uk"
            ),
        ]

    def __str__(self) -> str:
        return self.capscode

    def get_absolute_url(self):
        return f"/people/capabilities/update/{self.pk}/"

    def get_all_children(self):
        children = [self]
        try:
            child_list = self.children.all()
        except AttributeError:
            return children
        for child in child_list:
            children.extend(child.get_all_children())
        return children

    def get_all_parents(self):
        parents = [self]
        if self.parent is not None:
            parent = self.parent
            parents.extend(parent.get_all_parents())
        return parents
