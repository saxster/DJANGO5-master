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