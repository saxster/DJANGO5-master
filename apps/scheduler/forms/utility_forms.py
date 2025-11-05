"""Scheduler utility and miscellaneous forms."""
from django import forms
from django_select2 import forms as s2forms
from apps.activity.models.question_model import QuestionSet
from apps.core.utils_new.business_logic import initailize_form_fields
import logging

logger = logging.getLogger(__name__)


class EditAssignedSiteForm(forms.Form):
    """Form for editing assigned site configuration."""
    br_time = forms.IntegerField(
        max_value=30, min_value=0, label="Breaktime", required=True
    )
    checklist = forms.ChoiceField(
        widget=s2forms.Select2Widget, label="Checklist", required=True, choices=[]
    )

    def __init__(self, *args, **kwargs):
        super(EditAssignedSiteForm, self).__init__(*args, **kwargs)
        self.fields["checklist"].choices = QuestionSet.objects.all().values_list(
            "id", "qsetname"
        )
        initailize_form_fields(self)
