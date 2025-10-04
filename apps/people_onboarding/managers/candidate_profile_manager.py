"""
CandidateProfile Manager

Custom manager for CandidateProfile model.
Complies with Rule #14: Keep methods < 50 lines
"""
from django.db import models


class CandidateProfileManager(models.Manager):
    """Custom manager for CandidateProfile with optimized queries"""

    def with_onboarding_request(self):
        """Optimize queries by pre-fetching onboarding request"""
        return self.select_related('onboarding_request')

    def search_by_name(self, query):
        """Search candidates by name"""
        return self.filter(
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query) |
            models.Q(middle_name__icontains=query)
        )

    def with_experience_range(self, min_years=None, max_years=None):
        """Filter by experience range"""
        qs = self.all()
        if min_years is not None:
            qs = qs.filter(total_experience_years__gte=min_years)
        if max_years is not None:
            qs = qs.filter(total_experience_years__lte=max_years)
        return qs