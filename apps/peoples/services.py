from django.contrib.auth import authenticate, login
from django.core.exceptions import ValidationError
from apps.core.utils_new.business_logic import save_user_session
import apps.peoples.models as pm
from django.shortcuts import redirect


class AuthenticationService:
    """
    Handles user authentication and session preparation.
    """

    def authenticate_user(self, username, password):
        user = pm.People.objects.filter(loginid=username).values(
            "people_extras__userfor"
        )
        if not user.exists():
            raise ValidationError("user Not Found")

        if user[0]["people_extras__userfor"] not in ["Web", "Both"]:
            raise ValidationError("User is not Authorized for Web Access")

        people = authenticate(username=username, password=password)
        if not people:
            raise ValidationError("Invalid Credentials")
        return people

    def prepare_session_data(self, user, timezone_offset):
        session_data = {"ctzoffset": timezone_offset}
        return session_data

    def determine_redirect_url(self, user_session_data):
        """
        Determines where user should be redirected based on their profile.

        Returns:
            str: URL name for redirect
        """
        bu_id = user_session_data.get("bu_id")
        sitecode = user_session_data.get("sitecode")
        wizard_data = user_session_data.get("wizard_data")

        if bu_id in [1, None]:
            return "/people/no-site/"
        elif sitecode not in [
            "SPSESIC",
            "SPSPAYROLL",
            "SPSOPS",
            "SPSOPERATION",
            "SPSHR",
        ]:
            return (
                "onboarding:wizard_delete" if wizard_data else "onboarding:rp_dashboard"
            )
        elif sitecode == "SPSOPS":
            return "reports:generateattendance"
        elif sitecode == "SPSHR":
            return "employee_creation:employee_creation"
        elif sitecode == "SPSOPERATION":
            return "reports:generate_declaration_form"
        else:
            return "reports:generatepdf"
