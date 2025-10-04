from apps.peoples.models import BaseModel, TenantAwareModel
from django.db import models
from .managers import TicketManager, ESCManager
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
import uuid
from concurrency.fields import VersionField

# Import workflow model for integration
from .models.ticket_workflow import TicketWorkflow


class TicketNumberField(models.AutoField):
    def get_next_value(self, model, created, value, using):
        if not created:
            return value
        if last_ticket := model.objects.order_by("-id").first():
            return "T{:05d}".format(last_ticket.id + 1)
        return "T00001"


def ticket_defaults():
    # elements in ticket_history will be like this:
    # element: {"when":"", "who":"", "action":"", "details":"", "previous_state":""}
    return {"ticket_history": []}


class Ticket(BaseModel, TenantAwareModel):
    class Priority(models.TextChoices):
        LOW = ("LOW", "Low")
        MEDIUM = ("MEDIUM", "Medium")
        HIGH = ("HIGH", "High")

    class Identifier(models.TextChoices):
        REQUEST = ("REQUEST", "Request")
        TICKET = ("TICKET", "Ticket")

    class Status(models.TextChoices):
        NEW = ("NEW", "New")  # ticket is created
        CANCEL = ("CANCELLED", "Cancel")  # ticket is cancelled
        RESOLVED = ("RESOLVED", "Resolved")  # ticket is resolved
        OPEN = ("OPEN", "Open")  # tickte is opened
        ONHOLD = (
            "ONHOLD",
            "On Hold",
        )  # ticket is opened but need more info before resolve
        CLOSED = ("CLOSED", "Closed")  # ticket is closed by the created user

    class TicketSource(models.TextChoices):
        SYSTEMGENERATED = ("SYSTEMGENERATED", "New Generated")
        USERDEFINED = ("USERDEFINED", "User Defined")

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    ticketno = models.CharField(unique=True, null=True, blank=False, max_length=200)
    ticketdesc = models.TextField()
    assignedtopeople = models.ForeignKey(
        "peoples.People",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ticket_people",
    )
    assignedtogroup = models.ForeignKey(
        "peoples.Pgroup",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ticket_grps",
    )
    comments = models.CharField(max_length=250, null=True)
    identifier = models.CharField(
        _("Identifier"),
        choices=Identifier.choices,
        max_length=50,
        default=Identifier.TICKET.value,
    )
    bu = models.ForeignKey(
        "onboarding.Bt", null=True, blank=True, on_delete=models.RESTRICT
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ticket_clients",
    )
    priority = models.CharField(
        _("Priority"), max_length=50, choices=Priority.choices, null=True, blank=True
    )
    ticketcategory = models.ForeignKey(
        "onboarding.TypeAssist",
        null=True,
        blank=True,
        related_name="ticketcategory_types",
        on_delete=models.RESTRICT,
    )
    location = models.ForeignKey(
        "activity.Location", null=True, blank=True, on_delete=models.RESTRICT
    )
    asset = models.ForeignKey(
        "activity.Asset", null=True, blank=True, on_delete=models.RESTRICT
    )
    qset = models.ForeignKey(
        "activity.QuestionSet", null=True, blank=True, on_delete=models.RESTRICT
    )
    status = models.CharField(
        _("Status"),
        max_length=50,
        choices=Status.choices,
        null=True,
        blank=True,
        default=Status.NEW.value,
    )
    performedby = models.ForeignKey(
        "peoples.People",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ticket_performedby",
    )
    # Workflow fields moved to TicketWorkflow model for better separation of concerns
    ticketsource = models.CharField(
        max_length=50, choices=TicketSource.choices, null=True, blank=True
    )
    attachmentcount = models.IntegerField(null=True)

    # Optimistic locking for concurrent updates (Rule #17)
    version = VersionField()

    objects = TicketManager()

    # Backward compatibility properties for workflow fields
    @property
    def level(self):
        """Backward compatibility: get escalation level from workflow."""
        try:
            return self.workflow.escalation_level
        except (AttributeError, TicketWorkflow.DoesNotExist):
            return 0

    @level.setter
    def level(self, value):
        """Backward compatibility: set escalation level via workflow."""
        workflow = self.get_or_create_workflow()
        workflow.escalation_level = value
        workflow.save(update_fields=['escalation_level'])

    @property
    def isescalated(self):
        """Backward compatibility: get escalation status from workflow."""
        try:
            return self.workflow.is_escalated
        except (AttributeError, TicketWorkflow.DoesNotExist):
            return False

    @isescalated.setter
    def isescalated(self, value):
        """Backward compatibility: set escalation status via workflow."""
        workflow = self.get_or_create_workflow()
        workflow.is_escalated = value
        workflow.save(update_fields=['is_escalated'])

    @property
    def modifieddatetime(self):
        """Backward compatibility: get last activity time from workflow."""
        try:
            return self.workflow.last_activity_at
        except (AttributeError, TicketWorkflow.DoesNotExist):
            return self.mdtz

    @modifieddatetime.setter
    def modifieddatetime(self, value):
        """Backward compatibility: set last activity time via workflow."""
        workflow = self.get_or_create_workflow()
        workflow.last_activity_at = value
        workflow.save(update_fields=['last_activity_at'])

    @property
    def ticketlog(self):
        """Backward compatibility: get workflow data as ticketlog."""
        try:
            workflow_data = self.workflow.workflow_data
            # Convert new format to legacy format for backward compatibility
            return {
                "ticket_history": workflow_data.get("workflow_history", []),
                **workflow_data  # Include all other workflow data
            }
        except (AttributeError, TicketWorkflow.DoesNotExist):
            return {"ticket_history": []}

    @ticketlog.setter
    def ticketlog(self, value):
        """Backward compatibility: set workflow data from ticketlog."""
        workflow = self.get_or_create_workflow()
        # Convert legacy format to new format
        if isinstance(value, dict):
            workflow.workflow_data = {
                "workflow_history": value.get("ticket_history", []),
                **{k: v for k, v in value.items() if k != "ticket_history"}
            }
        else:
            workflow.workflow_data = {"workflow_history": []}
        workflow.save(update_fields=['workflow_data'])

    @property
    def events(self):
        """Backward compatibility: get events from workflow data."""
        try:
            return self.workflow.workflow_data.get("events", "")
        except (AttributeError, TicketWorkflow.DoesNotExist):
            return ""

    @events.setter
    def events(self, value):
        """Backward compatibility: set events in workflow data."""
        workflow = self.get_or_create_workflow()
        if not workflow.workflow_data:
            workflow.workflow_data = {}
        workflow.workflow_data["events"] = value
        workflow.save(update_fields=['workflow_data'])

    def get_or_create_workflow(self):
        """Get or create associated TicketWorkflow instance."""
        try:
            return self.workflow
        except TicketWorkflow.DoesNotExist:
            # Create workflow instance for this ticket
            workflow = TicketWorkflow.objects.create(
                ticket=self,
                tenant=self.tenant,
                bu=getattr(self, 'bu', None),
                client=getattr(self, 'client', None),
                cuser=getattr(self, 'cuser', None),
                muser=getattr(self, 'muser', None)
            )
            return workflow

    def add_history(self):
        self.ticketlog["ticket_history"].append(
            {
                "record": model_to_dict(
                    self, exclude=["ticketlog", "uuid", "id", "ctzoffset"]
                )
            }
        )

    def get_changed_keys(self, dict1, dict2):
        """
        This function takes two dictionaries as input and returns a list of keys
        where the corresponding values have changed from the first dictionary to the second.
        """

        # Handle edge cases where either of the inputs is not a dictionary
        if not isinstance(dict1, dict) or not isinstance(dict2, dict):
            raise TypeError("Both arguments should be of dict type")

        return [key for key in dict1.keys() & dict2.keys() if dict1[key] != dict2[key]]

    class Meta(BaseModel.Meta):
        db_table = "ticket"
        get_latest_by = ["cdtz", "mdtz"]
        constraints = [
            models.UniqueConstraint(fields=["bu", "id", "client"], name="bu_id_uk")
        ]

    def __str__(self):
        return self.ticketdesc


class EscalationMatrix(BaseModel, TenantAwareModel):
    class Frequency(models.TextChoices):
        MINUTE = ("MINUTE", "MINUTE")
        HOUR = ("HOUR", "HOUR")
        DAY = ("DAY", "DAY")
        WEEK = ("WEEK", "WEEK")

    # id               = models.BigIntegerField(primary_key = True)
    body = models.CharField(max_length=500, null=True)
    job = models.ForeignKey(
        "activity.Job", verbose_name=_("Job"), null=True, on_delete=models.RESTRICT
    )
    level = models.IntegerField(null=True, blank=True)
    frequency = models.CharField(
        max_length=10, default="DAY", choices=Frequency.choices
    )
    frequencyvalue = models.IntegerField(null=True, blank=True)
    assignedfor = models.CharField(max_length=50)
    assignedperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="escalation_people",
    )
    assignedgroup = models.ForeignKey(
        "peoples.Pgroup",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="escalation_grps",
    )
    bu = models.ForeignKey(
        "onboarding.Bt", null=True, blank=True, on_delete=models.RESTRICT
    )
    escalationtemplate = models.ForeignKey(
        "onboarding.TypeAssist",
        null=True,
        blank=True,
        related_name="esc_types",
        on_delete=models.RESTRICT,
    )
    notify = models.EmailField(blank=True, null=True)
    client = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="esc_clients",
    )

    objects = ESCManager()

    class Meta(BaseModel.Meta):
        db_table = "escalationmatrix"
        get_latest_by = ["mdtz", "cdtz"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(frequencyvalue__gte=0),
                name="frequencyvalue_gte_0_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(notify__isnull=True)
                | models.Q(notify="")
                | models.Q(
                    notify__regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                ),
                name="valid_notify_format",
            ),
        ]
