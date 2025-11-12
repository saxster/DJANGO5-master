from django import forms
from django.db.models import Q
from .models import Ticket, EscalationMatrix
from apps.core_onboarding.models import TypeAssist
from apps.core import utils
from apps.peoples.models import Pgroup, People
from apps.activity.models.location_model import Location
from apps.activity.models.asset_model import Asset
from apps.core.utils_new.business_logic import initailize_form_fields
from .services.ticket_state_machine import (
    TicketStateMachine,
    TransitionContext,
    TransitionReason
)
from .services.ticket_assignment_service import (
    TicketAssignmentService,
    AssignmentContext,
    AssignmentReason,
    AssignmentType
)


class TicketForm(forms.ModelForm):
    required_css_class = "required"

    class Meta:
        model = Ticket
        fields = [
            "ticketdesc",
            "assignedtopeople",
            "assignedtogroup",
            "priority",
            "ctzoffset",
            "ticketcategory",
            "status",
            "comments",
            "location",
            "cdtz",
            # "isescalated",  # Removed - this is a @property, not a database field
            "ticketsource",
            "asset",
        ]
        labels = {
            "assignedtopeople": "User",
            "assignedtogroup": "User Group",
            "ticketdesc": "Subject",
            "cdtz": "Created On",
            "ticketcategory": "Category",
            # "isescalated": "Escalated",  # Removed - computed from workflow
            "asset": "Asset/Checkpoint",
        }
        widgets = {
            "comments": forms.Textarea(attrs={"rows": 2, "cols": 40}),
            # "isescalated": forms.TextInput(attrs={"readonly": True}),  # Removed
            "ticketsource": forms.TextInput(attrs={"style": "display:none"}),
            "ticketdesc": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["assignedtogroup"].required = False
        self.fields["ticketdesc"].required = True
        self.fields["ticketcategory"].required = True
        self.fields["priority"].required = True
        self.fields["comments"].required = False
        self.fields["ticketsource"].initial = Ticket.TicketSource.USERDEFINED

        # filters for dropdown fields
        self.fields[
            "assignedtogroup"
        ].queryset = Pgroup.objects.filter_for_dd_pgroup_field(
            self.request, sitewise=True
        )
        self.fields[
            "assignedtopeople"
        ].queryset = People.objects.filter_for_dd_people_field(
            self.request, sitewise=True
        )
        self.fields["ticketcategory"].queryset = TypeAssist.objects.filter(
            tatype__tacode="TICKETCATEGORY",
            client_id=S["client_id"],
            enable=True,
            bu_id=S["bu_id"],
        )
        self.fields[
            "location"
        ].queryset = Location.objects.filter_for_dd_location_field(
            self.request, sitewise=True
        )
        self.fields["asset"].queryset = Asset.objects.filter_for_dd_asset_field(
            self.request, ["ASSET", "CHECKPOINT"], sitewise=True
        )
        initailize_form_fields(self)
        if not self.instance.id:
            self.fields["status"].initial = "NEW"
            # Auto-assign new tickets to current user
            self.fields["assignedtopeople"].initial = self.request.user
            # self.fields['assignedtogroup'] = utils.get_or_create_none_pgroup()

    def clean(self):
        super().clean()
        cd = self.cleaned_data

        # Validate state transitions using centralized TicketStateMachine
        if self.instance and self.instance.pk:  # Existing ticket being updated
            current_status = self.instance.status
            new_status = cd.get("status")

            if current_status and new_status and current_status != new_status:
                # Create transition context
                context = TransitionContext(
                    user=getattr(self.request, 'user', None),
                    reason=TransitionReason.USER_ACTION,
                    comments=cd.get("comments"),
                    mobile_client=False
                )

                # Validate transition using state machine
                result = TicketStateMachine.validate_transition(
                    current_status, new_status, context
                )

                if not result.is_valid:
                    from django.core.exceptions import ValidationError

                    # Enhanced error message with allowed transitions
                    allowed = TicketStateMachine.get_allowed_transitions(
                        current_status, context.user
                    )
                    error_msg = result.error_message
                    if allowed:
                        error_msg += f" Allowed transitions: {allowed}"

                    raise ValidationError(error_msg)

                # Log transition attempt for audit trail
                if hasattr(self.instance, 'id'):
                    TicketStateMachine.log_transition_attempt(
                        ticket_id=self.instance.id,
                        current_status=current_status,
                        new_status=new_status,
                        context=context,
                        result=result
                    )

        # Enhanced auto-assignment using TicketAssignmentService
        if cd.get("assignedtopeople") is None and cd.get("assignedtogroup") is None:
            # Use intelligent auto-assignment if ticket exists (editing scenario)
            if self.instance and self.instance.pk:
                context = AssignmentContext(
                    user=self.request.user,
                    reason=AssignmentReason.AUTO_ASSIGNMENT,
                    assignment_type=AssignmentType.AUTO,
                    enforce_permissions=False  # Form validation context
                )

                # Determine best assignee using business rules
                # For now, fall back to current user but this could be enhanced
                assignee = TicketAssignmentService._determine_auto_assignee(
                    self.instance, context
                )

                if assignee and assignee['type'] == 'person':
                    cd["assignedtopeople"] = People.objects.get(pk=assignee['id'])
                elif assignee and assignee['type'] == 'group':
                    cd["assignedtogroup"] = Pgroup.objects.get(pk=assignee['id'])
                else:
                    # Fallback to current user
                    cd["assignedtopeople"] = self.request.user
            else:
                # For new tickets, default to current user
                cd["assignedtopeople"] = self.request.user

        self.cleaned_data = self.check_nones(self.cleaned_data)

    def clean_ticketdesc(self):
        if val := self.cleaned_data.get("ticketdesc"):
            val = val.strip()
            val.capitalize()
        return val

    def clean_comments(self):
        return val.strip() if (val := self.cleaned_data.get("comments")) else val

    def check_nones(self, cd):
        fields = {
            "location": "get_or_create_none_location",
            "assignedtopeople": "get_or_create_none_people",
            "assignedtogroup": "get_or_create_none_pgroup",
        }
        for field, func in fields.items():
            if cd.get(field) in [None, ""]:
                cd[field] = getattr(utils, func)()
        return cd


# create a ModelForm
class EscalationForm(forms.ModelForm):
    # specify the name of model to use
    class Meta:
        model = EscalationMatrix
        fields = ["escalationtemplate", "ctzoffset"]
        labels = {"escalationtemplate": "Escalation Template"}

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        self.fields["escalationtemplate"].queryset = TypeAssist.objects.select_related(
            "tatype"
        ).filter(
            Q(bu_id__in=self.request.session["assignedsites"] + [1])
            | Q(cuser_id=1)
            | Q(cuser__is_superuser=True),
            tatype__tacode__in=["TICKETCATEGORY", "TICKET_CATEGORY"],
        )
