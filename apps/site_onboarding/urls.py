from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'site_onboarding'

router = DefaultRouter()

urlpatterns = [
    path('api/', include(router.urls)),
]
