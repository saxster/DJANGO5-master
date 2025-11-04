from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'client_onboarding'

router = DefaultRouter()
# Add viewsets here when created

urlpatterns = [
    path('api/', include(router.urls)),
]
