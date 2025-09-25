from django.urls import path
from django.views.generic import TemplateView

app_name = 'clientbilling'

urlpatterns = [
    path('features/', TemplateView.as_view(template_name='clientbilling/features.html'), name='features'),
]