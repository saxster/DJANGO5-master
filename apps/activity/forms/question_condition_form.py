"""
Form for managing question display conditions in admin interface
"""
import json
from django import forms
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from apps.activity.models.question_model import QuestionSetBelonging
import django_select2.forms as s2forms


class QuestionConditionForm(forms.ModelForm):
    """Form for editing question conditions via admin"""
    
    # Simplified fields for common use case
    depends_on_question = forms.ModelChoiceField(
        queryset=QuestionSetBelonging.objects.none(),
        required=False,
        label="Show this question only when",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        help_text="Select the question this depends on"
    )
    
    condition_operator = forms.ChoiceField(
        choices=[
            ('', '--- Always show ---'),
            ('EQUALS', 'Equals'),
            ('NOT_EQUALS', 'Not Equals'),
            ('CONTAINS', 'Contains'),
            ('GREATER_THAN', 'Greater Than'),
            ('LESS_THAN', 'Less Than'),
        ],
        required=False,
        label="Condition"
    )
    
    condition_values = forms.CharField(
        required=False,
        label="Has value(s)",
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., Yes or Yes,No for multiple',
            'class': 'form-control'
        }),
        help_text="Comma-separated values for EQUALS/NOT_EQUALS/CONTAINS"
    )
    
    show_if_true = forms.BooleanField(
        required=False,
        initial=True,
        label="Show when condition is TRUE",
        help_text="Uncheck to hide when condition is TRUE"
    )
    
    condition_group = forms.CharField(
        required=False,
        label="Group name",
        widget=forms.TextInput(attrs={
            'placeholder': 'Optional grouping',
            'class': 'form-control'
        }),
        help_text="Group related conditional questions"
    )
    
    class Meta:
        model = QuestionSetBelonging
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set up the depends_on_question queryset
        if self.instance and self.instance.qset_id:
            # Get all previous questions in the same questionset
            self.fields['depends_on_question'].queryset = QuestionSetBelonging.objects.filter(
                qset_id=self.instance.qset_id,
                seqno__lt=self.instance.seqno if self.instance.seqno else 999
            ).select_related('question').order_by('seqno')
            
            # Set initial values from display_conditions
            if self.instance.display_conditions:
                self._set_initial_from_display_conditions()
    
    def _set_initial_from_display_conditions(self):
        """Parse display_conditions JSON and set form initial values"""
        try:
            conditions = self.instance.display_conditions
            if conditions and conditions.get('depends_on'):
                depends_on = conditions['depends_on']
                
                # Find the parent question
                parent_seqno = depends_on.get('question_seqno')
                if parent_seqno:
                    parent_q = QuestionSetBelonging.objects.filter(
                        qset_id=self.instance.qset_id,
                        seqno=parent_seqno
                    ).first()
                    if parent_q:
                        self.initial['depends_on_question'] = parent_q
                
                # Set operator
                self.initial['condition_operator'] = depends_on.get('operator', 'EQUALS')
                
                # Set values
                values = depends_on.get('values', [])
                self.initial['condition_values'] = ','.join(values) if values else ''
                
                # Set show_if
                self.initial['show_if_true'] = conditions.get('show_if', True)
                
                # Set group
                self.initial['condition_group'] = conditions.get('group', '')
        except (json.JSONDecodeError, AttributeError):
            pass
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Build display_conditions from form fields
        depends_on_question = cleaned_data.get('depends_on_question')
        operator = cleaned_data.get('condition_operator')
        
        if depends_on_question and operator:
            # Parse values
            values_str = cleaned_data.get('condition_values', '')
            values = [v.strip() for v in values_str.split(',') if v.strip()]
            
            # Build the display_conditions dictionary
            display_conditions = {
                'depends_on': {
                    'question_seqno': depends_on_question.seqno,
                    'operator': operator,
                    'values': values
                },
                'show_if': cleaned_data.get('show_if_true', True),
                'cascade_hide': False,
                'group': cleaned_data.get('condition_group', '')
            }
            
            # Store in the model field
            self.instance.display_conditions = display_conditions
        else:
            # Clear conditions if no dependency selected
            self.instance.display_conditions = {}
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the form and update display_conditions"""
        instance = super().save(commit=False)
        
        # display_conditions is already set in clean()
        
        if commit:
            instance.save()
        
        return instance


class QuestionConditionInlineForm(forms.ModelForm):
    """Simplified inline form for question conditions"""
    
    condition_text = forms.CharField(
        required=False,
        label="Display Condition",
        widget=forms.TextInput(attrs={
            'readonly': True,
            'class': 'form-control-plaintext'
        })
    )
    
    class Meta:
        model = QuestionSetBelonging
        fields = ['seqno', 'question', 'ismandatory', 'display_conditions']
        widgets = {
            'display_conditions': forms.HiddenInput()
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Generate human-readable condition text
        if self.instance and self.instance.display_conditions:
            self.initial['condition_text'] = self._format_condition_text()
    
    def _format_condition_text(self):
        """Format display conditions as human-readable text"""
        try:
            conditions = self.instance.display_conditions
            if not conditions or not conditions.get('depends_on'):
                return "Always visible"
            
            depends_on = conditions['depends_on']
            seqno = depends_on.get('question_seqno', '?')
            operator = depends_on.get('operator', 'EQUALS')
            values = depends_on.get('values', [])
            show_if = conditions.get('show_if', True)
            
            # Build readable text
            text = f"Show when Q{seqno} "
            
            if operator == 'EQUALS':
                text += f"= {', '.join(values)}"
            elif operator == 'NOT_EQUALS':
                text += f"≠ {', '.join(values)}"
            elif operator == 'CONTAINS':
                text += f"contains {', '.join(values)}"
            elif operator == 'GREATER_THAN':
                text += f"> {values[0] if values else '?'}"
            elif operator == 'LESS_THAN':
                text += f"< {values[0] if values else '?'}"
            
            if not show_if:
                text = f"Hide when condition is met ({text})"
            
            return text
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            return "Invalid condition"
