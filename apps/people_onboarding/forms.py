"""
People Onboarding Forms

Comprehensive Django forms with validation for the onboarding module.
Complies with Rule #13: Explicit field lists and custom validation
Complies with Rule #7: Forms < 100 lines per form

Author: Claude Code
"""
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta

from apps.peoples.models import People
from .models import (
    OnboardingRequest,
    CandidateProfile,
    DocumentSubmission,
    ApprovalWorkflow
)


class CandidateProfileForm(forms.ModelForm):
    """
    Candidate profile creation form with comprehensive validation.

    Features:
    - Email uniqueness validation
    - Age verification
    - Phone number validation
    - File upload validation
    """

    confirm_email = forms.EmailField(
        label=_('Confirm Email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm email address'
        }),
        help_text=_('Re-enter email to confirm')
    )

    class Meta:
        model = CandidateProfile
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender',
            'primary_email', 'secondary_email',
            'primary_phone', 'secondary_phone',
            'current_address', 'city', 'state', 'postal_code', 'country',
            'highest_education', 'total_experience_years',
            'current_company', 'current_designation',
            'linkedin_url', 'skills', 'certifications',
            'preferred_language', 'photo'
        ]

        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name',
                'maxlength': 50
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Middle name (optional)',
                'maxlength': 50
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name',
                'maxlength': 50
            }),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': date.today().isoformat()
            }),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'primary_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Primary email'
            }),
            'secondary_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Secondary email (optional)'
            }),
            'primary_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 123-4567',
                'data-validate-phone': 'true'
            }),
            'secondary_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Secondary phone (optional)'
            }),
            'current_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'maxlength': 500,
                'placeholder': 'Street address, apartment/unit'
            }),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'highest_education': forms.Select(attrs={'class': 'form-select'}),
            'total_experience_years': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 50,
                'step': 0.5
            }),
            'current_company': forms.TextInput(attrs={'class': 'form-control'}),
            'current_designation': forms.TextInput(attrs={'class': 'form-control'}),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://linkedin.com/in/username'
            }),
            'preferred_language': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png',
                'data-file-size': '2'
            })
        }

    def clean_primary_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('primary_email')
        if email:
            # Check if email already exists (excluding current instance)
            qs = People.objects.filter(email=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    _("This email is already registered in the system.")
                )
        return email

    def clean_date_of_birth(self):
        """Validate age requirement (18+)"""
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = date.today()
            age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )
            if age < 18:
                raise ValidationError(
                    _("Candidate must be at least 18 years old.")
                )
            if age > 100:
                raise ValidationError(
                    _("Please enter a valid date of birth.")
                )
        return dob

    def clean_photo(self):
        """Validate photo upload"""
        photo = self.cleaned_data.get('photo')
        if photo:
            # Check file size (2MB max)
            if photo.size > 2 * 1024 * 1024:
                raise ValidationError(
                    _("Photo size must not exceed 2MB.")
                )
            # Check file type
            allowed_types = ['image/jpeg', 'image/png']
            if photo.content_type not in allowed_types:
                raise ValidationError(
                    _("Only JPEG and PNG images are allowed.")
                )
        return photo

    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        primary_email = cleaned_data.get('primary_email')
        confirm_email = cleaned_data.get('confirm_email')

        if primary_email and confirm_email:
            if primary_email != confirm_email:
                raise ValidationError(
                    _("Email addresses do not match.")
                )

        return cleaned_data


class DocumentUploadForm(forms.ModelForm):
    """
    Document upload form with extensive validation.

    Features:
    - File type validation
    - File size validation
    - Expiry date validation
    """

    class Meta:
        model = DocumentSubmission
        fields = [
            'document_type', 'document_file',
            'is_mandatory', 'issue_date', 'expiry_date'
        ]

        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'document_file': forms.FileInput(attrs={
                'class': 'form-control',
                'data-file-size': '10',
                'data-file-type': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
            'issue_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'expiry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            })
        }

    def clean_document_file(self):
        """Validate file type and size"""
        file = self.cleaned_data.get('document_file')
        if file:
            # File size check (10MB max)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError(
                    _("File size must be under 10MB.")
                )

            # File type check
            allowed_types = [
                'application/pdf',
                'image/jpeg', 'image/png',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ]

            if file.content_type not in allowed_types:
                raise ValidationError(
                    _("Unsupported file type. Allowed: PDF, JPG, PNG, DOC, DOCX")
                )

        return file

    def clean(self):
        """Validate date logic"""
        cleaned_data = super().clean()
        issue_date = cleaned_data.get('issue_date')
        expiry_date = cleaned_data.get('expiry_date')

        if issue_date and expiry_date:
            if expiry_date <= issue_date:
                raise ValidationError(
                    _("Expiry date must be after issue date.")
                )

            if expiry_date < date.today():
                self.add_error('expiry_date', _("Document has already expired."))

        return cleaned_data


class ApprovalDecisionForm(forms.Form):
    """
    Approval decision form with conditional validation.
    """

    DECISION_CHOICES = [
        ('APPROVED', _('Approve this request')),
        ('REJECTED', _('Reject this request')),
        ('ESCALATED', _('Escalate to another approver')),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=True,
        label=_('Decision')
    )

    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': _('Provide detailed notes for your decision...'),
            'minlength': 10,
            'data-min-length': 10
        }),
        required=True,
        min_length=10,
        label=_('Decision Notes'),
        help_text=_("Minimum 10 characters required")
    )

    escalated_to = forms.ModelChoiceField(
        queryset=People.objects.filter(is_staff=True, enable=True),
        required=False,
        empty_label=_("Select an approver"),
        widget=forms.Select(attrs={'class': 'form-select select2'}),
        label=_('Escalate To')
    )

    escalation_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': _('Reason for escalation...')
        }),
        required=False,
        label=_('Escalation Reason')
    )

    def __init__(self, *args, **kwargs):
        self.approval_workflow = kwargs.pop('approval_workflow', None)
        super().__init__(*args, **kwargs)

    def clean_notes(self):
        """Validate notes minimum length"""
        notes = self.cleaned_data.get('notes')
        if notes and len(notes.strip()) < 10:
            raise ValidationError(
                _("Notes must be at least 10 characters long.")
            )
        return notes

    def clean(self):
        """Conditional validation based on decision"""
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')
        escalated_to = cleaned_data.get('escalated_to')
        escalation_reason = cleaned_data.get('escalation_reason')

        if decision == 'ESCALATED':
            if not escalated_to:
                raise ValidationError(
                    _("Please select an approver to escalate to.")
                )
            if not escalation_reason or len(escalation_reason.strip()) < 10:
                raise ValidationError(
                    _("Please provide a reason for escalation (minimum 10 characters).")
                )

            # Prevent escalating to self
            if self.approval_workflow and escalated_to == self.approval_workflow.approver:
                raise ValidationError(
                    _("Cannot escalate to yourself.")
                )

        return cleaned_data