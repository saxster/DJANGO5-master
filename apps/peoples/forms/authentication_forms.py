from django import forms
from django.conf import settings
from django.core.validators import RegexValidator
from django.db.models import Q
from django.utils.html import format_html
from django.urls import reverse
import logging
import zlib
import binascii

import apps.peoples.models as pm  # people-models
from apps.activity.models.location_model import Location
from apps.activity.models.question_model import QuestionSet
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from django_select2 import forms as s2forms
from apps.core.utils_new.business_logic import (
    apply_error_classes,
    initailize_form_fields,
)
import re
from apps.peoples.utils import create_caps_choices_for_peopleform

from apps.core.utils_new.code_validators import (
    PEOPLECODE_VALIDATOR,
    LOGINID_VALIDATOR,
    MOBILE_NUMBER_VALIDATOR,
    NAME_VALIDATOR,
    validate_peoplecode,
    validate_loginid,
    validate_mobile_number,
    validate_name,
)

# Security form utilities
from apps.core.validation import SecureFormMixin, SecureCharField

# ============= BEGIN LOGIN FORM ====================#


class LoginForm(SecureFormMixin, forms.Form):
    """Secure login form with XSS protection."""

    # Define fields to protect from XSS
    xss_protect_fields = ["username"]

    username = SecureCharField(
        max_length=50,
        min_length=4,
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter your username",
                "class": "auth-input",
                "autocomplete": "username",
                "aria-describedby": "id_username_help",
                "aria-required": "true",
            }
        ),
        label="Username",
        help_text="Use your corporate IntelliWiz credentials.",
    )

    password = forms.CharField(
        max_length=25,
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter your password",
                "class": "auth-input",
                "autocomplete": "current-password",
                "aria-required": "true",
                "data-password": "true",
            }
        ),
        label="Password",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure consistent styling classes remain even after SecureForm processing
        for field_name, field in self.fields.items():
            classes = field.widget.attrs.get("class", "").split()
            if "auth-input" not in classes:
                classes.append("auth-input")
            field.widget.attrs["class"] = " ".join(filter(None, classes))
            field.widget.attrs.setdefault("aria-required", "true")

        self.fields["password"].widget.attrs.setdefault("data-password", "true")

    def clean(self):
        super().clean()
        username = self.cleaned_data.get("username")
        # Only perform user checks if username is provided
        if username:
            user = self.get_user(username)
            self.check_active(user)
            self.check_verified(user)
            self.check_user_hassite(user)

    def clean_username(self):
        import re

        if val := self.cleaned_data.get("username"):
            return val

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result

    def check_active(self, user):
        if not user.enable:
            raise forms.ValidationError(
                "Can't Login User Is Not Active, Please Contact Admin"
            )

    def check_verified(self, user):
        if not user.isverified:
            message = format_html(
                'User is not verified, Please verify your email address by clicking <a href="{}?userid={}">verify me</a>',
                reverse("people:verify_email"),
                user.id,
            )
            raise forms.ValidationError(message)

    def check_user_hassite(self, user):
        # Allow users with bu_id=1 to login - they will be redirected to no-site page
        if user.bu_id == 1:
            return  # Allow login, will be redirected to site selection
        # Check if user has no site at all
        if user.bu is None and len(user.people_extras.get("assignsitegroup", [])) == 0:
            raise forms.ValidationError("User has no site assigned")

    def get_user(self, username):
        try:
            return pm.People.objects.get(
                Q(loginid=username) | Q(email=username) | Q(mobno=username)
            )
        except pm.People.DoesNotExist as e:
            raise forms.ValidationError(
                "Login credentials incorrect. Please check the Username or Password"
            ) from e
