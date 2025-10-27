"""
Authentication API URLs (v1)

Domain: /api/v1/auth/

Handles user authentication, session management, and token operations.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path

# Import views when they're created
# from apps.peoples.api import auth_views

app_name = 'auth'

urlpatterns = [
    # Authentication endpoints (to be implemented)
    # path('login/', auth_views.LoginView.as_view(), name='login'),
    # path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # path('refresh/', auth_views.RefreshTokenView.as_view(), name='refresh'),
    # path('password-reset/', auth_views.PasswordResetView.as_view(), name='password-reset'),
    # path('password-reset-confirm/', auth_views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
