"""
Utility Views - Password Change, Email Verification, No Site

All view methods < 30 lines (Rule #8 compliant).
Business logic delegated to respective services.
"""

import logging
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from apps.peoples.services import (
    PasswordManagementService,
    EmailVerificationService
)
from apps.peoples.forms import NoSiteForm
from apps.client_onboarding.models import Bt
from apps.peoples.models import People

logger = logging.getLogger(__name__)


def _auth_layout_context(request: HttpRequest) -> dict:
    """Reusable brand context for authentication-related templates."""

    return {
        "product_name": "IntelliWiz",
        "company_name": "Youtility Technologies Pvt. Ltd.",
        "tagline": "Secure access to your field operations data.",
        "support_contact": "support@youtility.in",
        "env_hostname": request.get_host(),
        "current_year": datetime.now().year,
    }


@method_decorator(permission_required('peoples.change_people', raise_exception=True), name='dispatch')
class ChangePeoplePassword(LoginRequiredMixin, View):
    """
    Refactored password change view using PasswordManagementService.

    BEFORE: Direct form handling in view
    AFTER: Service delegation ✅
    """

    def __init__(self):
        super().__init__()
        self.password_service = PasswordManagementService()

    def post(self, request: HttpRequest) -> JsonResponse:
        """Handle password change request (< 20 lines)."""
        people_id = request.POST.get("people")
        new_password1 = request.POST.get("new_password1")
        new_password2 = request.POST.get("new_password2")

        result = self.password_service.change_password(
            people_id=people_id,
            new_password1=new_password1,
            new_password2=new_password2
        )

        if result.success:
            return JsonResponse(
                {"res": "Password changed successfully!", "status": 200}
            )
        else:
            return JsonResponse(
                {"res": result.errors or result.error_message, "status": 500}
            )


class EmailVerificationView(View):
    """
    Refactored email verification view using EmailVerificationService.

    BEFORE: 68 lines with complex error handling
    AFTER: < 25 lines ✅
    """

    def __init__(self):
        super().__init__()
        self.verification_service = EmailVerificationService()

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle email verification request (< 25 lines)."""
        user_id = request.GET.get("userid")

        if not user_id:
            messages.error(
                request,
                "Invalid request: No user ID provided",
                "alert alert-danger"
            )
            return redirect("login")

        request.session['pending_verification_user_id'] = user_id

        result = self.verification_service.send_verification_email(user_id)

        if result.success:
            messages.success(
                request,
                "Verification email sent to your email address",
                "alert alert-success"
            )
        else:
            messages.error(
                request,
                result.error_message or "Email verification failed",
                "alert alert-danger"
            )

        return redirect("login")


class NoSite(View):
    """
    No site assignment view (minimal refactoring needed).

    Already simple and compliant with Rule #8.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render no site form (< 5 lines)."""
        context = {"nositeform": NoSiteForm(session=request.session)}
        context.update(_auth_layout_context(request))
        return render(request, "peoples/nosite.html", context)

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle site selection (< 15 lines)."""
        form = NoSiteForm(request.POST, session=request.session)

        if form.is_valid():
            bu_id = form.cleaned_data["site"]
            bu = Bt.objects.get(id=bu_id)

            request.session["bu_id"] = bu_id
            request.session["sitename"] = bu.buname
            People.objects.filter(id=request.user.id).update(bu_id=bu_id)

            return redirect("/dashboard/")

        context = {"nositeform": form}
        context.update(_auth_layout_context(request))
        return render(request, "peoples/nosite.html", context)
