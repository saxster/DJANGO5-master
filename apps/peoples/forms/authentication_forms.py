"""Authentication forms for login and password management."""

from django import forms
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html

import apps.peoples.models as pm
from apps.core.validation import SecureFormMixin, SecureCharField
from apps.core.utils_new.business_logic import apply_error_classes


class LoginForm(SecureFormMixin, forms.Form):
    """Secure login form with XSS protection."""

    # Define fields to protect from XSS
    xss_protect_fields = ["username"]

    username = SecureCharField(
        max_length=50,
        min_length=4,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Username or Phone or Email"}),
        label="Username",
    )

    password = forms.CharField(
        max_length=25,
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter Password",
                "autocomplete": "off",
                "data-toggle": "password",
            }
        ),
        label="Password",
    )

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
