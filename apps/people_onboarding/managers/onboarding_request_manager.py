"""
OnboardingRequest Manager

Custom manager for OnboardingRequest model with business logic queries.
Complies with Rule #14: Keep methods < 50 lines
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class OnboardingRequestManager(models.Manager):
    """Custom manager for OnboardingRequest with optimized queries"""

    def active(self):
        """Get all active onboarding requests (not completed/rejected/cancelled)"""
        from apps.people_onboarding.models import OnboardingRequest
        return self.exclude(
            current_state__in=[
                OnboardingRequest.WorkflowState.COMPLETED,
                OnboardingRequest.WorkflowState.REJECTED,
                OnboardingRequest.WorkflowState.CANCELLED,
            ]
        )

    def overdue(self):
        """Get requests that are past their expected completion date"""
        today = timezone.now().date()
        return self.active().filter(
            expected_completion_date__lt=today
        )

    def by_person_type(self, person_type):
        """Filter by person type (employee, contractor, etc.)"""
        return self.filter(person_type=person_type)

    def pending_approval(self):
        """Get requests awaiting approval"""
        from apps.people_onboarding.models import OnboardingRequest
        return self.filter(
            current_state=OnboardingRequest.WorkflowState.PENDING_APPROVAL
        )

    def in_provisioning(self):
        """Get requests currently in provisioning stage"""
        from apps.people_onboarding.models import OnboardingRequest
        return self.filter(
            current_state=OnboardingRequest.WorkflowState.PROVISIONING
        )

    def completed_in_last_days(self, days=30):
        """Get requests completed in the last N days"""
        from apps.people_onboarding.models import OnboardingRequest
        since = timezone.now() - timedelta(days=days)
        return self.filter(
            current_state=OnboardingRequest.WorkflowState.COMPLETED,
            actual_completion_date__gte=since.date()
        )