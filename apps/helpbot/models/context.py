"""
HelpBot Context Model

Stores contextual information about user's current location and state.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel


class HelpBotContext(BaseModel, TenantAwareModel):
    """
    Stores contextual information about user's current location and state in the application.
    This enables context-aware help and suggestions.
    """

    context_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="helpbot_contexts",
        verbose_name=_("User")
    )
    session = models.ForeignKey(
        'helpbot.HelpBotSession',
        on_delete=models.CASCADE,
        related_name="contexts",
        verbose_name=_("Session"),
        null=True,
        blank=True
    )
    current_url = models.URLField(
        _("Current URL"),
        help_text="URL where user is seeking help"
    )
    page_title = models.CharField(
        _("Page Title"),
        max_length=200,
        blank=True,
        help_text="Title of the current page"
    )
    app_name = models.CharField(
        _("App Name"),
        max_length=50,
        blank=True,
        help_text="Django app name (e.g., 'activity', 'peoples')"
    )
    view_name = models.CharField(
        _("View Name"),
        max_length=100,
        blank=True,
        help_text="Django view name"
    )
    user_role = models.CharField(
        _("User Role"),
        max_length=50,
        blank=True,
        help_text="User's role/permission level"
    )
    form_data = models.JSONField(
        _("Form Data"),
        default=dict,
        blank=True,
        help_text="Current form data if user is on a form"
    )
    error_context = models.JSONField(
        _("Error Context"),
        default=dict,
        blank=True,
        help_text="Error information if user encountered an error"
    )
    user_journey = models.JSONField(
        _("User Journey"),
        default=list,
        blank=True,
        help_text="Recent pages visited by the user"
    )
    browser_info = models.JSONField(
        _("Browser Info"),
        default=dict,
        blank=True,
        help_text="Browser and device information"
    )
    timestamp = models.DateTimeField(
        _("Timestamp"),
        auto_now=True,
        help_text="When this context was captured"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_context"
        verbose_name = "HelpBot Context"
        verbose_name_plural = "HelpBot Contexts"
        get_latest_by = ["timestamp"]
        indexes = [
            models.Index(fields=['user', 'timestamp'], name='helpbot_context_user_time_idx'),
            models.Index(fields=['app_name', 'view_name'], name='helpbot_context_app_view_idx'),
        ]

    def __str__(self):
        return f"Context {self.context_id} - {self.user.email} at {self.current_url}"
