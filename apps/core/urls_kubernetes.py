"""
Kubernetes Health Check URLs

Endpoints for K8s liveness, readiness, and startup probes.
"""

from django.urls import path
from apps.core.views import kubernetes_health_views

urlpatterns = [
    # Liveness probe - is app responsive?
    path('healthz', kubernetes_health_views.healthz, name='kubernetes_healthz'),

    # Readiness probe - is app ready for traffic?
    path('readyz', kubernetes_health_views.readyz, name='kubernetes_readyz'),

    # Startup probe - has app finished starting?
    path('startup', kubernetes_health_views.startup, name='kubernetes_startup'),
]
