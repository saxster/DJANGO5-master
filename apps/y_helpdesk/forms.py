from django import forms
from django.db.models import Q
from .models import Ticket, EscalationMatrix
from apps.onboarding.models import TypeAssist
from apps.core import utils
from apps.peoples.models import Pgroup, People
from apps.activity.models.location_model import Location
from apps.activity.models.asset_model import Asset
from apps.core.utils_new.business_logic import initailize_form_fields


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
            "isescalated",
            "ticketsource",
            "asset",
        ]
        labels = {
            "assignedtopeople": "User",
            "assignedtogroup": "User Group",
            "ticketdesc": "Subject",
            "cdtz": "Created On",
            "ticketcategory": "Category",
            "isescalated": "Escalated",
            "asset": "Asset/Checkpoint",
        }
        widgets = {
            "comments": forms.Textarea(attrs={"rows": 2, "cols": 40}),
            "isescalated": forms.TextInput(attrs={"readonly": True}),
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

        # Validate state transitions
        if self.instance and self.instance.pk:  # Existing ticket being updated
            current_status = self.instance.status
            new_status = cd.get("status")

            if current_status and new_status and current_status != new_status:
                # Define allowed transitions
                allowed_transitions = {
                    Ticket.Status.NEW.value: [Ticket.Status.OPEN.value, Ticket.Status.CANCEL.value],
                    Ticket.Status.OPEN.value: [Ticket.Status.RESOLVED.value, Ticket.Status.ONHOLD.value, Ticket.Status.CANCEL.value],
                    Ticket.Status.ONHOLD.value: [Ticket.Status.OPEN.value, Ticket.Status.RESOLVED.value, Ticket.Status.CANCEL.value],
                    Ticket.Status.RESOLVED.value: [Ticket.Status.CLOSED.value],
                    # Terminal states - no transitions allowed
                    Ticket.Status.CLOSED.value: [],
                    Ticket.Status.CANCEL.value: [],
                }

                if new_status not in allowed_transitions.get(current_status, []):
                    from django.core.exceptions import ValidationError
                    raise ValidationError(
                        f"Invalid status transition from '{current_status}' to '{new_status}'. "
                        f"Allowed transitions: {allowed_transitions.get(current_status, [])}"
                    )

        # Require comments for terminal states
        new_status = cd.get("status")
        terminal_states = [Ticket.Status.RESOLVED.value, Ticket.Status.CLOSED.value, Ticket.Status.CANCEL.value]

        if new_status in terminal_states and not cd.get("comments"):
            from django.core.exceptions import ValidationError
            raise ValidationError({
                "comments": f"Comments are required when setting status to '{new_status}'"
            })

        # Auto-assign if neither user nor group is assigned
        if cd.get("assignedtopeople") is None and cd.get("assignedtogroup") is None:
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
