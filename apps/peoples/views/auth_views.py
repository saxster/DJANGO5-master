"""
Authentication Views - Refactored with Service Layer

Demonstrates Rule #8 compliance:
- All view methods < 30 lines
- Business logic delegated to AuthenticationService
- Pure HTTP request/response handling
"""

import logging
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.http import HttpRequest, HttpResponse

from apps.peoples.services import AuthenticationService
from apps.peoples.forms import LoginForm
from apps.core import utils

logger = logging.getLogger(__name__)


class SignIn(View):
    """
    Refactored login view using AuthenticationService.

    BEFORE: 140+ lines with complex logic
    AFTER: < 30 lines per method ✅
    """
    template_path = "peoples/login.html"

    def __init__(self):
        super().__init__()
        self.auth_service = AuthenticationService()

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET request for login form."""
        if request.user.is_authenticated:
            return redirect('/dashboard/')

        request.session.set_test_cookie()
        form = LoginForm()
        return render(request, self.template_path, context={"loginform": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle POST request for user authentication."""
        form = LoginForm(request.POST)

        if not request.session.test_cookie_worked():
            form.add_error(None, "Please enable cookies in your browser")
            return render(request, self.template_path, context={"loginform": form})

        if not form.is_valid():
            return render(request, self.template_path, context={"loginform": form})

        loginid = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password")

        auth_result = self.auth_service.authenticate_user(
            loginid=loginid,
            password=password,
            access_type="Web"
        )

        if auth_result.success:
            return self._handle_success(request, auth_result)
        else:
            return self._handle_failure(request, form, auth_result)

    def _handle_success(
        self,
        request: HttpRequest,
        auth_result
    ) -> HttpResponse:
        """Handle successful authentication (< 25 lines)."""
        login(request, auth_result.user)

        if auth_result.session_data:
            for key, value in auth_result.session_data.items():
                request.session[key] = value

        request.session["ctzoffset"] = request.POST.get("timezone")
        utils.save_user_session(request, request.user)

        logger.info(f"User {auth_result.user.peoplecode} logged in")

        if auth_result.redirect_url == 'peoples:no_site':
            return redirect('peoples:no_site')

        return redirect(auth_result.redirect_url or '/dashboard/')

    def _handle_failure(
        self,
        request: HttpRequest,
        form,
        auth_result
    ) -> HttpResponse:
        """Handle authentication failure (< 15 lines)."""
        if auth_result.error_message:
            form.add_error(None, auth_result.error_message)

        logger.warning(
            "Authentication failed",
            extra={'correlation_id': auth_result.correlation_id}
        )

        return render(request, self.template_path, context={"loginform": form})


class SignOut(LoginRequiredMixin, View):
    """
    Refactored logout view using AuthenticationService.

    BEFORE: 35+ lines
    AFTER: < 20 lines ✅
    """

    def __init__(self):
        super().__init__()
        self.auth_service = AuthenticationService()

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle user logout."""
        logout_result = self.auth_service.logout_user(request)

        if logout_result.success:
            logger.info("User logged out successfully")
            return redirect('/')
        else:
            messages.error(
                request,
                logout_result.error_message or "Logout failed",
                "alert alert-danger"
            )
            return redirect('/dashboard/')