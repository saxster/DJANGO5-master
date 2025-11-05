"""Forms for report template management."""

from django import forms
from django.db.models import Q
from django_select2 import forms as s2forms

from apps.activity.models.question_model import QuestionSet
from apps.client_onboarding import models as om_client
from apps.core_onboarding import models as om_core
from apps.peoples import models as pm
from apps.core.utils_new.business_logic import initailize_form_fields


class MasterReportTemplate(forms.ModelForm):
    """Base form for all report templates."""

    required_css_class = "required"
    showto_allsites = forms.BooleanField(
        initial=False, required=False, label="Show to all sites"
    )
    site_type_includes = forms.MultipleChoiceField(
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        label="Site Types",
        required=False,
    )
    buincludes = forms.MultipleChoiceField(
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        label="Site Includes",
        required=False,
    )
    site_grp_includes = forms.MultipleChoiceField(
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        label="Site groups",
        required=False,
    )

    class Meta:
        model = QuestionSet
        fields = [
            "type",
            "qsetname",
            "buincludes",
            "site_grp_includes",
            "site_type_includes",
            "enable",
            "ctzoffset",
        ]
        labels = {
            "qsetname": "Template Name",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site_type_includes"].choices = om_core.TypeAssist.objects.filter(
            Q(tatype__tacode="SITETYPE") | Q(tacode="NONE")
        ).values_list("id", "taname")
        bulist = om_client.Bt.objects.get_all_sites_of_client(
            self.request.session["client_id"]
        ).values_list("id", flat=True)
        self.fields[
            "buincludes"
        ].choices = pm.Pgbelonging.objects.get_assigned_sites_to_people(
            self.request.user.id, makechoice=True
        )
        self.fields["site_grp_includes"].choices = pm.Pgroup.objects.filter(
            Q(groupname="NONE")
            | Q(identifier__tacode="SITEGROUP") & Q(bu_id__in=bulist)
        ).values_list("id", "groupname")


class SiteReportTemplate(MasterReportTemplate):
    """Form for site report templates."""

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        self.fields["type"].initial = QuestionSet.Type.SITEREPORTTEMPLATE
        self.fields["type"].widget.attrs = {"style": "display:none"}
        if not self.instance.id:
            self.fields["site_grp_includes"].initial = 1
            self.fields["site_type_includes"].initial = 1
            self.fields["buincludes"].initial = 1


class IncidentReportTemplate(MasterReportTemplate):
    """Form for incident report templates."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].initial = QuestionSet.Type.INCIDENTREPORTTEMPLATE
        initailize_form_fields(self)
        if not self.instance.id:
            self.fields["site_grp_includes"].initial = 1
            self.fields["site_type_includes"].initial = 1
            self.fields["buincludes"].initial = 1
