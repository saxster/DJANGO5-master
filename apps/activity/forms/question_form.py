import re
import django_select2.forms as s2forms
from django import forms
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from apps.core.utils_new.business_logic import initailize_form_fields
import apps.activity.utils as ac_utils
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
import apps.peoples.models as pm
from apps.core import utils


class QuestionForm(forms.ModelForm):
    error_msg = {
        "invalid_name": "[Invalid name] Only these special characters [-, _, @, #] are allowed in name field",
    }
    required_css_class = "required"
    alertbelow = forms.CharField(
        widget=forms.NumberInput(attrs={"step": "0.01"}),
        required=False,
        label="Alert Below",
    )
    alertabove = forms.CharField(
        widget=forms.NumberInput(attrs={"step": "0.01"}),
        required=False,
        label="Alert Above",
    )
    options = forms.CharField(
        max_length=2000,
        required=False,
        label="Options",
        widget=forms.TextInput(
            attrs={"placeholder": "Enter options separated by comma (,)"}
        ),
    )

    class Meta:
        model = Question
        fields = [
            "quesname",
            "answertype",
            "alerton",
            "isworkflow",
            "isavpt",
            "avpttype",
            "unit",
            "category",
            "options",
            "min",
            "max",
            "ctzoffset",
        ]
        labels = {
            "quesname": "Name",
            "answertype": "Type",
            "unit": "Unit",
            "category": "Category",
            "min": "Min Value",
            "max": "Max Value",
            "alerton": "Alert On",
            "isworkflow": "used in workflow?",
        }

        widgets = {
            "answertype": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            "category": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            "unit": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            "alerton": s2forms.Select2MultipleWidget(
                attrs={"data-theme": "bootstrap5"}
            ),
        }

    def __init__(self, *args, **kwargs):  # sourcery skip: use-named-expression
        """Initializes form add atttibutes and classes here."""
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["min"].initial = None
        self.fields["max"].initial = None
        self.fields["category"].required = False
        self.fields["unit"].required = False
        self.fields["alerton"].required = False

        # filters for dropdown fields
        self.fields["unit"].queryset = om.TypeAssist.objects.select_related(
            "tatype"
        ).filter(tatype__tacode="QUESTIONUNIT", client_id=S["client_id"])
        self.fields["category"].queryset = om.TypeAssist.objects.select_related(
            "tatype"
        ).filter(tatype__tacode="QUESTIONCATEGORY", client_id=S["client_id"])

        if self.instance.id:
            ac_utils.initialize_alertbelow_alertabove(self.instance, self)
        initailize_form_fields(self)

    def clean(self):
        import logging
        logger = logging.getLogger("django")
        
        cleaned_data = super().clean()
        data = cleaned_data
        alertabove = alertbelow = None
        
        logger.info(f"clean() - answertype: {data.get('answertype')}, options before: {data.get('options')}")
        
        # Only clear options for answer types that don't support options
        if data.get("answertype") in ["NUMERIC", "RATING", "DATE", "TIME", "SIGNATURE", 
                                       "SINGLELINE", "MULTILINE", "EMAILID", "METERREADING",
                                       "PEOPLELIST", "SITELIST"]:
            cleaned_data["options"] = None
            logger.info(f"Cleared options for answertype: {data.get('answertype')}")
            
        # Clear min/max for non-numeric types
        if data.get("answertype") not in ["NUMERIC", "RATING", "METERREADING"]:
            cleaned_data["min"] = cleaned_data["max"] = None
            cleaned_data["alertbelow"] = cleaned_data["alertabove"] = None
            
        # Clear numeric alert fields for types that support options
        if data.get("answertype") in ["CHECKBOX", "DROPDOWN", "MULTISELECT"]:
            cleaned_data["alertbelow"] = cleaned_data["alertabove"] = None
            # Keep alerton for DROPDOWN/CHECKBOX as it specifies which option triggers alert
            logger.info(f"Keeping options for answertype: {data.get('answertype')}, value: {cleaned_data.get('options')}")
            logger.info(f"Keeping alerton for answertype: {data.get('answertype')}, value: {cleaned_data.get('alerton')}")
            
        if data.get("alertbelow") and data.get("min") not in [None, ""]:
            alertbelow = ac_utils.validate_alertbelow(forms, data)
        if data.get("alertabove") and data.get("max") not in [None, ""]:
            alertabove = ac_utils.validate_alertabove(forms, data)
        if data.get("answertype") == "NUMERIC" and alertabove and alertbelow:
            alerton = f"<{alertbelow}, >{alertabove}"
            cleaned_data["alerton"] = alerton
        
        logger.info(f"clean() final - options: {cleaned_data.get('options')}")    
        return cleaned_data

    def clean_alerton(self):
        if val := self.cleaned_data.get("alerton"):
            return ac_utils.validate_alerton(forms, val)
        else:
            return val

    def clean_options(self):
        import logging
        logger = logging.getLogger("django")
        val = self.cleaned_data.get("options")
        logger.info(f"clean_options called with value: {val}")
        if val:
            cleaned_val = ac_utils.validate_options(forms, val)
            logger.info(f"clean_options returning: {cleaned_val}")
            return cleaned_val
        else:
            logger.info("clean_options returning None/empty")
            return val

    def clean_min(self):
        return val if (val := self.cleaned_data.get("min")) else 0.0

    def clean_max(self):
        val = val if (val := self.cleaned_data.get("max")) else 0.0
        return val
    
    def save(self, commit=True):
        import logging
        logger = logging.getLogger("django")
        
        instance = super().save(commit=False)
        
        # Explicitly set options field
        options_value = self.cleaned_data.get('options')
        logger.info(f"save() - setting options field to: {options_value}")
        instance.options = options_value
        
        if commit:
            instance.save()
            logger.info(f"save() - instance saved with options: {instance.options}")
        
        return instance


class MasterQsetForm(forms.ModelForm):
    required_css_class = "required"
    error_msg = {
        'invalid_name'  : "[Invalid name] Only these special characters [-, _, @, #] are allowed in name field",
    }
    assetincludes = forms.MultipleChoiceField(
        required = True, label='Checkpoint', widget = s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}))
    site_type_includes = forms.MultipleChoiceField(widget=s2forms.Select2MultipleWidget(attrs={"data-theme":"bootstrap5"}), label="Site Types", required=False)
    buincludes         = forms.MultipleChoiceField(widget=s2forms.Select2MultipleWidget(attrs={"data-theme":"bootstrap5"}), label='Site Includes', required=False)
    site_grp_includes  = forms.MultipleChoiceField(widget=s2forms.Select2MultipleWidget(attrs={"data-theme":"bootstrap5"}), label='Site groups', required=False)

    class Meta:
        model = QuestionSet
        fields = ['qsetname', 'parent', 'enable', 'assetincludes', 'type', 'ctzoffset', 'site_type_includes', 'buincludes', 'site_grp_includes', 'show_to_all_sites']

        labels = {
            'parent': 'Parent',
            'qsetname': 'Name', }
        widgets = {
            'parent': s2forms.Select2Widget(),
            'type': s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"})
        }

    def __init__(self, *args, **kwargs):
        """Initializes form add atttibutes and classes here."""
        super().__init__(*args, **kwargs)
        self.fields['type'].initial      = 'ASSET'
        self.fields['site_type_includes'].choices = om.TypeAssist.objects.filter(Q(tatype__tacode = "SITETYPE") | Q(tacode='NONE'), client_id = self.request.session['client_id']).values_list('id', 'taname')
        bulist = om.Bt.objects.get_all_bu_of_client(self.request.session['client_id'])
        self.fields['buincludes'].choices = pm.Pgbelonging.objects.get_assigned_sites_to_people(self.request.user.id, makechoice=True)
        self.fields['site_grp_includes'].choices = pm.Pgroup.objects.filter(
            Q(groupname='NONE') |  Q(identifier__tacode='SITEGROUP') & Q(bu_id__in = bulist)).values_list('id', 'groupname')
        utils.initailize_form_fields(self)
    
    def clean_qsetname(self):
        if value := self.cleaned_data.get('qsetname'):
            regex = r"^[a-zA-Z0-9\-_@#\[\]\(\|\)\{\} ]*$"
            if not re.match(regex, value):
                raise forms.ValidationError("[Invalid name] Only these special characters [-, _, @, #] are allowed in name field")
        return value


class QsetBelongingForm(forms.ModelForm):
    required_css_class = "required"
    alertbelow = forms.CharField(
        widget=forms.NumberInput(attrs={"step": "0.01"}),
        required=False,
        label="Alert Below",
    )
    alertabove = forms.CharField(
        widget=forms.NumberInput(attrs={"step": "0.01"}),
        required=False,
        label="Alert Above",
    )
    options = forms.CharField(
        max_length=2000,
        required=False,
        label="Options",
        widget=forms.TextInput(
            attrs={"placeholder": 'Enter options separated by comma ","'}
        ),
    )
    
    # New fields for dependency configuration
    depends_on = forms.ChoiceField(
        required=False,
        label="Depends On",
        widget=forms.Select(attrs={
            "class": "form-control select2",
            "id": "id_depends_on",
            "data-placeholder": "None - Always show"
        }),
        help_text="Show this question only when..."
    )
    
    depends_on_value = forms.CharField(
        required=False,
        label="Show When Value Is",
        widget=forms.Select(attrs={
            "class": "form-control",
            "id": "id_depends_on_value",
            "disabled": "disabled"
        }),
        help_text="Select the value that triggers this question"
    )

    class Meta:
        model = QuestionSetBelonging
        fields = [
            "seqno",
            "qset",
            "question",
            "answertype",
            "min",
            "max",
            "isavpt",
            "avpttype",
            "alerton",
            "options",
            "ismandatory",
            "ctzoffset",
        ]
        widgets = {
            "answertype": forms.TextInput(attrs={"readonly": "readonly"}),
            "question": s2forms.Select2Widget,
            "alerton": s2forms.Select2MultipleWidget,
            "options": forms.Textarea(attrs={"rows": 3, "cols": 40}),
        }

    def __init__(self, *args, **kwargs):
        """Initializes form add atttibutes and classes here."""
        super().__init__(*args, **kwargs)
        self.fields["min"].initial = None
        self.fields["max"].initial = None
        for k in self.fields.keys():
            if k in ["min", "max"]:
                self.fields[k].required = True
            elif k in ["options", "alerton"]:
                self.fields[k].required = False
        if self.instance.id:
            ac_utils.initialize_alertbelow_alertabove(self.instance, self)
            
        # Initialize dependency fields
        self._initialize_dependency_fields()
        
        initailize_form_fields(self)
    
    def _initialize_dependency_fields(self):
        """Initialize the dependency dropdown with previous questions"""
        # Get all previous questions in this questionset
        if self.instance.qset_id:
            previous_questions = QuestionSetBelonging.objects.filter(
                qset_id=self.instance.qset_id
            ).exclude(
                pk=self.instance.pk if self.instance.pk else None
            ).select_related('question').order_by('seqno')
            
            # Build choices for depends_on field
            choices = [('', '--- None (Always show) ---')]
            for qsb in previous_questions:
                # Only show questions that come before this one
                if not self.instance.pk or qsb.seqno < self.instance.seqno:
                    choices.append((
                        str(qsb.pk),
                        f"Q{qsb.seqno}: {qsb.question.quesname[:50]}"
                    ))
            
            self.fields['depends_on'].choices = choices
            
            # If instance has display_conditions, populate the fields
            if self.instance.pk and self.instance.display_conditions:
                self._populate_dependency_values()
    
    def _populate_dependency_values(self):
        """Populate dependency fields from existing display_conditions"""
        try:
            conditions = self.instance.display_conditions
            if conditions and conditions.get('depends_on'):
                depends = conditions['depends_on']
                
                # Set the parent question
                parent_id = depends.get('question_id')
                if parent_id:
                    self.fields['depends_on'].initial = str(parent_id)
                    
                    # Get parent question's options to populate depends_on_value
                    parent_qsb = QuestionSetBelonging.objects.filter(pk=parent_id).first()
                    if parent_qsb:
                        # Build value choices based on parent's answer type
                        value_choices = self._get_value_choices_for_question(parent_qsb)
                        self.fields['depends_on_value'].widget = forms.Select(attrs={
                            "class": "form-control",
                            "id": "id_depends_on_value"
                        })
                        self.fields['depends_on_value'].widget.choices = value_choices
                        
                        # Set the selected value
                        values = depends.get('values', [])
                        if values:
                            self.fields['depends_on_value'].initial = values[0]
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error populating dependency values: {e}")
    
    def _get_value_choices_for_question(self, qsb):
        """Get appropriate value choices based on question type"""
        choices = []
        
        if qsb.answertype in ['DROPDOWN', 'CHECKBOX', 'MULTISELECT']:
            # Use the options from the question
            if qsb.options:
                options = [opt.strip() for opt in qsb.options.split(',')]
                choices = [(opt, opt) for opt in options]
        elif qsb.answertype == 'RATING':
            # Rating typically 1-5 or 1-10
            max_val = int(qsb.max) if qsb.max else 5
            choices = [(str(i), str(i)) for i in range(1, max_val + 1)]
        else:
            # For other types, provide common options
            choices = [
                ('', '--- Select Value ---'),
                ('Yes', 'Yes'),
                ('No', 'No'),
                ('Completed', 'Completed'),
                ('Not Completed', 'Not Completed')
            ]
        
        return choices

    def clean(self):
        cleaned_data = super().clean()
        data = cleaned_data
        alertabove = alertbelow = None
        if data.get("answertype") not in ["NUMERIC", "RATING", "CHECKBOX", "DROPDOWN"]:
            cleaned_data["min"] = cleaned_data["max"] = None
            cleaned_data["alertbelow"] = cleaned_data["alertabove"] = None
            cleaned_data["alerton"] = cleaned_data["options"] = None
        if data.get("answertype") in ["CHECKBOX", "DROPDOWN"]:
            cleaned_data["min"] = cleaned_data["max"] = None
            cleaned_data["alertbelow"] = cleaned_data["alertabove"] = None
        if data.get("answertype") in ["NUMERIC", "RATING"]:
            cleaned_data["options"] = None
        if data.get("alertbelow") and data.get("min"):
            alertbelow = ac_utils.validate_alertbelow(forms, data)
        if data.get("alertabove") and data.get("max"):
            alertabove = ac_utils.validate_alertabove(forms, data)
        if data.get("answertype") == "NUMERIC" and alertabove and alertbelow:
            alerton = f"<{alertbelow}, >{alertabove}"
            cleaned_data["alerton"] = alerton
        
        # Handle dependency configuration
        depends_on_id = cleaned_data.get('depends_on')
        depends_on_value = cleaned_data.get('depends_on_value')
        
        if depends_on_id:
            # Build the display_conditions JSON
            display_conditions = {
                "depends_on": {
                    "question_id": int(depends_on_id),
                    "operator": "EQUALS",
                    "values": [depends_on_value] if depends_on_value else []
                },
                "show_if": True,
                "cascade_hide": False,
                "group": None
            }
            # Store in the instance
            self.instance.display_conditions = display_conditions
        else:
            # Clear conditions if no dependency selected
            self.instance.display_conditions = {}
        
        return cleaned_data

    def clean_alerton(self):
        val = self.cleaned_data.get("alerton")
        if val:
            return ac_utils.validate_alerton(forms, val)
        return val

    def clean_options(self):
        val = self.cleaned_data.get("options")
        if val:
            return ac_utils.validate_options(forms, val)
        return val

    def validate_unique(self) -> None:
        super().validate_unique()
        if not self.instance.id:
            try:
                Question.objects.get(
                    quesname__exact=self.instance.quesname,
                    answertype__iexact=self.instance.answertype,
                    client_id__exact=self.request.session["client_id"],
                )
                msg = "This type of Question is already exist!"
                raise forms.ValidationError(message=msg, code="unique_constraint")
            except Question.DoesNotExist:
                pass
            except ValidationError as e:
                self._update_errors(e)


class ChecklistForm(forms.ModelForm):
    required_css_class = "required"
    error_msg = {
        "invalid_name": "[Invalid name] Only these special characters [-, _, @, #] are allowed in name field",
    }
    # Explicitly define type field as ChoiceField with all available options
    type = forms.ChoiceField(
        choices=QuestionSet.Type.choices,
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        label="Type",
        initial="CHECKLIST"
    )
    assetincludes = forms.MultipleChoiceField(
        required=True,
        label="Checkpoint",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
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
            "qsetname",
            "enable",
            "type",
            "ctzoffset",
            "assetincludes",
            "show_to_all_sites",
            "site_type_includes",
            "buincludes",
            "site_grp_includes",
            "parent",
        ]
        widgets = {
            "parent": forms.TextInput(attrs={"style": "display:none"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["parent"].required = False
        if not self.instance.id:
            self.fields["site_grp_includes"].initial = 1
            self.fields["site_type_includes"].initial = 1
            self.fields["buincludes"].initial = 1
            self.fields["assetincludes"].initial = 1
        else:
            self.fields["type"].required = False
            # Keep existing type when editing
            self.fields["type"].initial = self.instance.type
            self.fields["type"].disabled = True  # Disable changing type when editing

        self.fields["site_type_includes"].choices = om.TypeAssist.objects.filter(
            Q(tacode="NONE")
            | Q(client_id=S["client_id"]) & Q(tatype__tacode="SITETYPE"),
            enable=True,
        ).values_list("id", "taname")
        bulist = om.Bt.objects.get_all_bu_of_client(self.request.session["client_id"])
        self.fields[
            "buincludes"
        ].choices = pm.Pgbelonging.objects.get_assigned_sites_to_people(
            self.request.user.id, makechoice=True
        )
        self.fields["site_grp_includes"].choices = pm.Pgroup.objects.filter(
            Q(groupname="NONE")
            | Q(identifier__tacode="SITEGROUP")
            & Q(bu_id__in=bulist)
            & Q(client_id=S["client_id"])
        ).values_list("id", "groupname")
        self.fields["assetincludes"].choices = ac_utils.get_assetsmartplace_choices(
            self.request, ["CHECKPOINT", "ASSET"]
        )
        initailize_form_fields(self)

    def clean(self):
        super().clean()
        self.cleaned_data = self.check_nones(self.cleaned_data)
        # Don't override type field - allow it to be changed

    def check_nones(self, cd):
        fields = {"parent": "get_or_create_none_qset"}
        for field, func in fields.items():
            if cd.get(field) in [None, ""]:
                cd[field] = getattr(utils, func)()
        return cd


class QuestionSetForm(MasterQsetForm):

    class Meta(MasterQsetForm.Meta):
        pass

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        S  = self.request.session
        super().__init__(*args, **kwargs)
        self.fields['type'].initial          = 'QUESTIONSET'    
        self.fields['assetincludes'].label   = 'Asset/Smartplace'
        self.fields['assetincludes'].choices = ac_utils.get_assetsmartplace_choices(self.request, ['ASSET', 'CHECKPOINT'])
        self.fields['site_type_includes'].choices = om.TypeAssist.objects.filter(Q(tatype__tacode='SITETYPE', client_id=S['client_id']) | Q(tacode='NONE')).values_list('id', 'tacode')
        if not self.instance.id:
            self.fields['parent'].initial = 1
            self.fields['site_grp_includes'].initial = 1
            self.fields['site_type_includes'].initial = 1
            self.fields['buincludes'].initial = 1
        utils.initailize_form_fields(self)
