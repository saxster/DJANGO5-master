"""
Managers for People Onboarding models.

Custom managers for complex queries and business logic.
"""

from .onboarding_request_manager import OnboardingRequestManager
from .candidate_profile_manager import CandidateProfileManager

__all__ = [
    'OnboardingRequestManager',
    'CandidateProfileManager',
]