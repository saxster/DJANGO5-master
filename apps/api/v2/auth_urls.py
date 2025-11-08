"""
Authentication API URLs (V2)

Domain: /api/v2/auth/

Handles JWT-based authentication with V2 enhancements.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path
from apps.api.v2.views import auth_views

app_name = 'auth'

urlpatterns = [
    # Authentication endpoints (V2)
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('refresh/', auth_views.RefreshTokenView.as_view(), name='refresh'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('verify/', auth_views.VerifyTokenView.as_view(), name='verify'),
]
