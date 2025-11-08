"""
Refactored Scheduling Forms

This module contains the refactored versions of scheduling forms
using the new base classes and mixins to reduce code duplication.

Follows Rule 8: All methods < 50 lines
Follows SRP: Each form has single responsibility
"""

import logging
from datetime import datetime, time, date, timedelta
from django import forms
from django.db.models import Q
from django_select2 import forms as s2forms

from apps.activity.models.question_model import QuestionSet
from apps.activity.models.job_model import Job
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
import apps.peoples.models as pm
from apps.scheduler.forms.base_forms import BaseTourForm, BaseTaskForm, BaseJobneedForm
from apps.core.utils_new.business_logic import initailize_form_fields

logger = logging.getLogger(__name__)


class InternalTourForm(BaseTourForm):
    """
    Refactored Internal Tour Form.

    Significantly reduced from original by using base classes and mixins.
    Original: ~200 lines, Refactored: ~80 lines
    """

    # Configure cached dropdown fields for performance
    cached_dropdown_fields = {
        'ticketcategory': {
            'model': ob.TypeAssist,
            'filter_method': 'filter_for_dd_notifycategory_field',
            'sitewise': True,
            'version': '1.0'
        },
        'pgroup': {
            'model': pm.Pgroup,
            'filter_method': 'filter_for_dd_pgroup_field',
            'sitewise': True,
            'version': '1.0'
        },
        'people': {
            'model': pm.People,
            'filter_method': 'filter_for_dd_people_field',
            'sitewise': False,
            'version': '1.0'
        }
    }

    class Meta(BaseTourForm.Meta):
        exclude = ["shift"]
        widgets = {
            **BaseTourForm.Meta.widgets,
            "identifier": forms.TextInput(attrs={"style": "display:none;"}),
            "starttime": forms.TextInput(attrs={"style": "display:none;"}),
            "endtime": forms.TextInput(attrs={"style": "display:none;"}),
            "frequency": forms.TextInput(attrs={"style": "display:none;"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize internal tour form with specific configurations."""
        super().__init__(*args, **kwargs)

        # Set internal tour specific configurations
        self.set_required_false_for_dynamic()

        # Make ticketcategory required
        self.fields["ticketcategory"].required = True

        logger.debug("Initialized InternalTourForm with cached dropdowns")

    def clean(self):
        """Internal tour specific validation."""
        super().clean()
        self.set_instance_data_for_dynamic()
        return self.cleaned_data


class ExternalTourForm(BaseTourForm):
    """
    Refactored External Tour Form.

    Reduced complexity by using base classes.
    Original: ~180 lines, Refactored: ~70 lines
    """

    # External tour specific fields
    israndom = forms.BooleanField(
        initial=False,
        label="Random Tour",
        required=False
    )
    tourfrequency = forms.IntegerField(
        min_value=1,
        max_value=3,
        initial=1,
        label="Frequency",
        required=False
    )
    breaktime = forms.IntegerField(label="Break Time", required=False)

    class Meta(BaseTourForm.Meta):
        labels = {
            **BaseTourForm.Meta.labels,
            "sgroup": "Route Name",
            "qset": "Question Set",
            "planduration": "Plan Duration (mins)",
            "gracetime": "Grace Time (mins)",
        }
        widgets = {
            **BaseTourForm.Meta.widgets,
            "identifier": forms.TextInput(attrs={"style": "display:none;"}),
            "priority": forms.TextInput(attrs={"style": "display:none;"}),
            "seqno": forms.TextInput(attrs={"style": "display:none;"}),
            "ticketcategory": forms.TextInput(attrs={"style": "display:none;"}),
        }
        exclude = ["jobdesc"]

    def __init__(self, *args, **kwargs):
        """Initialize external tour form."""
        super().__init__(*args, **kwargs)

        # Setup external tour specific configurations
        self.setup_external_tour_fields()
        self.setup_external_dropdowns()

    def setup_external_tour_fields(self):
        """Setup external tour specific field configurations."""
        self.fields["israndom"].widget.attrs["class"] = "btdeciders"
        self.fields["tourfrequency"].widget.attrs["class"] = "btdeciders"

        # Set required fields for external tours
        required_fields = ["sgroup", "qset"]
        self.set_required_fields(required_fields, required=True)

        # Set initial value for ticketcategory
        try:
            autoclosed = ob.TypeAssist.objects.get(tacode="AUTOCLOSED")
            self.fields["ticketcategory"].initial = autoclosed
        except ob.TypeAssist.DoesNotExist:
            logger.warning("AUTOCLOSED TypeAssist not found")

    def setup_external_dropdowns(self):
        """Setup dropdown querysets for external tours."""
        if not self.request:
            return

        session = self.request.session

        # Question sets for external tours
        self.fields["qset"].queryset = (
            QuestionSet.objects.get_proper_checklist_for_scheduling(
                self.request, ["RPCHECKLIST"]
            )
        )

        # Site groups
        self.fields["sgroup"].queryset = pm.Pgroup.objects.filter(
            identifier__tacode="SITEGROUP",
            bu_id__in=session.get("assignedsites", []),
            enable=True,
        )

        # Other dropdowns using common patterns
        self.fields["people"].queryset = (
            pm.People.objects.filter_for_dd_people_field(self.request)
        )
        self.fields["pgroup"].queryset = (
            pm.Pgroup.objects.filter_for_dd_pgroup_field(self.request)
        )

        # Shifts
        self.fields["shift"].queryset = ob.Shift.objects.filter(
            ~Q(shiftname="NONE"),
            client_id=session.get("client_id"),
            bu_id=session.get("bu_id"),
            enable=True,
        )


class TaskForm(BaseTaskForm):
    """
    Refactored Task Form.

    Significantly simplified using base classes.
    Original: ~150 lines, Refactored: ~60 lines
    """

    class Meta(BaseTaskForm.Meta):
        exclude = ["shift"]
        widgets = {
            **BaseTaskForm.Meta.widgets,
            "ticketcategory": s2forms.Select2Widget(
                attrs={"data-theme": "bootstrap5"}
            ),
            "scantype": s2forms.Select2Widget(
                attrs={"data-theme": "bootstrap5"}
            ),
            "priority": s2forms.Select2Widget(
                attrs={"data-theme": "bootstrap5"}
            ),
        }

    def __init__(self, *args, **kwargs):
        """Initialize task form."""
        super().__init__(*args, **kwargs)

        # Task-specific field configurations
        self.setup_task_fields()
        self.setup_task_dropdowns()

    def setup_task_fields(self):
        """Setup task-specific field configurations."""
        # Optional description for tasks
        self.fields["jobdesc"].required = False

        # Update field labels
        self.fields["expirytime"].label = "Grace Time (After)"
        self.fields["gracetime"].label = "Grace Time (Before)"

    def setup_task_dropdowns(self):
        """Setup dropdown querysets for tasks."""
        if not self.request:
            return

        # Setup dropdowns using session context
        self.fields["ticketcategory"].queryset = (
            ob.TypeAssist.objects.filter_for_dd_notifycategory_field(
                self.request, sitewise=True
            )
        )

        self.fields["qset"].queryset = (
            QuestionSet.objects.filter_for_dd_qset_field(
                self.request, ["CHECKLIST"], sitewise=True
            )
        )

        # Use shared dropdown configuration methods
        dropdown_configs = {
            "asset": {
                "identifiers": ["ASSET", "CHECKPOINT"],
                "sitewise": True
            },
            "pgroup": {"sitewise": True},
            "people": {"sitewise": True},
        }

        for field, config in dropdown_configs.items():
            if field in self.fields:
                self._setup_field_queryset(field, config)

    def _setup_field_queryset(self, field_name, config):
        """Helper method to setup individual field querysets."""
        try:
            if field_name == "asset":
                from apps.activity.models.asset_model import Asset
                self.fields[field_name].queryset = (
                    Asset.objects.filter_for_dd_asset_field(
                        self.request,
                        identifiers=config["identifiers"],
                        sitewise=config["sitewise"]
                    )
                )
            elif field_name == "pgroup":
                self.fields[field_name].queryset = (
                    pm.Pgroup.objects.filter_for_dd_pgroup_field(
                        self.request, sitewise=config["sitewise"]
                    )
                )
            elif field_name == "people":
                self.fields[field_name].queryset = (
                    pm.People.objects.filter_for_dd_people_field(
                        self.request, sitewise=config["sitewise"]
                    )
                )
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to setup {field_name} queryset: {e}", exc_info=True)


class InternalTourJobneedForm(BaseJobneedForm):
    """
    Refactored Internal Tour Jobneed Form.

    Simplified using base jobneed functionality.
    """

    timeIn = forms.ChoiceField(
        choices=BaseJobneedForm.TIME_CHOICES,
        initial="MIN",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
    )

    def __init__(self, *args, **kwargs):
        """Initialize internal tour jobneed form."""
        super().__init__(*args, **kwargs)

        # Setup specific field configurations
        self.setup_jobneed_fields()

    def setup_jobneed_fields(self):
        """Setup jobneed specific field configurations."""
        # Field labels
        self.fields["qset"].label = "Checklist"
        self.fields["asset"].label = "Asset/Smartplace"

        # Disabled fields
        disabled_fields = ["starttime", "endtime", "performedby"]
        for field in disabled_fields:
            if field in self.fields:
                self.fields[field].widget.attrs["disabled"] = "disabled"

        # Setup ticket category if available
        if self.request:
            self.fields["ticketcategory"].queryset = (
                ob.TypeAssist.objects.filter_for_dd_notifycategory_field(
                    self.request, sitewise=True
                )
            )


class InternalTourCheckpointForm(BaseJobneedForm):
    """
    Simplified form for internal tour checkpoints.
    """

    class Meta(BaseJobneedForm.Meta):
        # Note: Jobneed uses expirydatetime (not expirytime like Job model)
        fields = ["qset", "people", "asset", "expirydatetime", "seqno"]

    def __init__(self, *args, **kwargs):
        """Initialize checkpoint form."""
        super().__init__(*args, **kwargs)

        # Make sequence number readonly
        self.fields["seqno"].widget.attrs = {"readonly": True}

        # Setup checkpoint-specific dropdowns
        if self.request:
            self.setup_checkpoint_dropdowns()

    def setup_checkpoint_dropdowns(self):
        """Setup dropdowns for checkpoint form."""
        # Question sets for checklists
        self.fields["qset"].queryset = (
            QuestionSet.objects.get_proper_checklist_for_scheduling(
                self.request, ["CHECKLIST", "QUESTIONSET"]
            )
        )

        # Assets for checkpoints
        try:
            from apps.activity.models.asset_model import Asset
            self.fields["asset"].queryset = Asset.objects.filter(
                identifier__in=["CHECKPOINT", "ASSET"],
                client_id=self.request.session.get("client_id"),
                enable=True,
            )
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to setup asset queryset: {e}", exc_info=True)


# Legacy compatibility - these will be gradually phased out
class Schd_I_TourJobForm(InternalTourForm):
    """Legacy compatibility for internal tour form."""
    pass


class Schd_E_TourJobForm(ExternalTourForm):
    """Legacy compatibility for external tour form."""
    pass


class SchdTaskFormJob(TaskForm):
    """Legacy compatibility for task form."""
    pass