"""
Signal handlers for People Onboarding module.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OnboardingRequest, CandidateProfile
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=OnboardingRequest)
def on_onboarding_request_created(sender, instance, created, **kwargs):
    """Auto-generate request number on creation"""
    if created and not instance.request_number:
        from django.utils import timezone
        date_str = timezone.now().strftime('%Y%m%d')
        instance.request_number = f"POB-{date_str}-{instance.id:05d}"
        instance.save(update_fields=['request_number'])