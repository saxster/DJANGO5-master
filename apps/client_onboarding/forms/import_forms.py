"""Client onboarding bulk import forms."""
from django import forms
from django_select2 import forms as s2forms
from apps.core.utils_new.business_logic import initailize_form_fields


class ImportForm(forms.Form):
    """Bulk import form for various data types."""
    TABLECHOICES = [
        ("TYPEASSIST", "User Defined Types"),
        ("BU", "Business Unit"),
        ("LOCATION", "Location"),
        ("ASSET", "Asset"),
        ("VENDOR", "Vendor"),
        ("PEOPLE", "People"),
        ("QUESTION", "Question"),
        ("QUESTIONSET", "Question Set"),
        ("QUESTIONSETBELONGING", "Question Set Belonging"),
        ("GROUP", "Group"),
        ("GROUPBELONGING", "Group Belongings"),
        ("SCHEDULEDTASKS", "Scheduled Tasks"),
        ("SCHEDULEDTOURS", "Scheduled Tours"),
        ("TOURSCHECKPOINTS", "Tour Checkpoints"),
        ("GEOFENCE", "Geofence"),
        ("GEOFENCE_PEOPLE", "Geofence People"),
        ("SHIFT", "Shift"),
        ("BULKIMPORTIMAGE", "Bulk Import Image"),
    ]
    table = forms.ChoiceField(
        choices=TABLECHOICES, widget=forms.Select(attrs={"class": "form-control"})
    )
    importfile = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )
    ctzoffset = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)


class ImportFormUpdate(forms.Form):
    """Bulk import form for updating existing records."""
    TABLECHOICES = [
        ("TYPEASSIST", "User Defined Types"),
        ("BU", "Business Unit"),
        ("LOCATION", "Location"),
        ("ASSET", "Asset"),
        ("VENDOR", "Vendor"),
        ("PEOPLE", "People"),
        ("QUESTION", "Question"),
        ("QUESTIONSET", "Question Set"),
        ("QUESTIONSETBELONGING", "Question Set Belonging"),
        ("GROUP", "Group"),
        ("GROUPBELONGING", "Group Belongings"),
        ("SCHEDULEDTASKS", "Scheduled Tasks"),
        ("SCHEDULEDTOURS", "Scheduled Tours"),
        ("TOURSCHECKPOINTS", "Tour Checkpoints"),
    ]
    importfile = forms.FileField(
        required=True, label="Import File", max_length=50, allow_empty_file=False
    )
    ctzoffset = forms.IntegerField()
    table = forms.ChoiceField(
        required=True,
        choices=TABLECHOICES,
        label="Select Type of Data",
        initial="TYPEASSISTS",
        widget=s2forms.Select2Widget,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
