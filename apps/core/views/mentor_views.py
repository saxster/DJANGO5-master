"""
AI Mentor Views - Dashboard and UI Views

Template-based views for AI mentor system.

Following .claude/rules.md:
- Rule #8: View methods <30 lines
- Rule #11: Specific exception handling
"""

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class MentorDashboardView(LoginRequiredMixin, TemplateView):
    """
    AI Mentor Dashboard.
    
    Shows personalized daily briefing, learning path,
    efficiency score, and achievements.
    """
    template_name = 'admin/mentor/dashboard.html'
    
    def get_context_data(self, **kwargs):
        """Add mentor-specific context"""
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'AI Mentor Dashboard'
        context['has_mentor_access'] = True
        return context
