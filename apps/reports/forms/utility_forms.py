"""Utility forms for report building and testing."""

from django import forms
from django_select2 import forms as s2forms


class TestForm(forms.Form):
    """Simple test form for development/testing."""

    firstname = forms.CharField(max_length=10, required=False)
    lastname = forms.CharField(max_length=10, required=True)
    middlename = forms.CharField(max_length=10, required=True)


class ReportBuilderForm(forms.Form):
    """Form for dynamically building custom reports."""

    model = forms.ChoiceField(
        label="Model",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        help_text="Select a model where you want data from",
    )
    columns = forms.MultipleChoiceField(
        label="Columns",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        help_text="Select columns required in the report",
    )
