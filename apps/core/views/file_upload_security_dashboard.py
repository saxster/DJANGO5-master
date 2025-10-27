"""
File Upload Security Dashboard - Real-time monitoring

Author: Claude Code  
Date: 2025-10-27
"""

import logging
from datetime import datetime, timedelta
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone

logger = logging.getLogger(__name__)


class FileUploadSecurityDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """File upload security monitoring dashboard"""
    
    template_name = 'core/monitoring/file_upload_security.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'File Upload Security',
            'last_updated': timezone.now(),
        })
        return context
