"""
HelpBot Context Service

Tracks user context and journey for context-aware help and suggestions.
Integrates with existing user session and navigation tracking.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.contrib.sessions.models import Session

from apps.helpbot.models import HelpBotContext, HelpBotSession
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class HelpBotContextService:
    """
    Service for managing user context and journey tracking.
    Enables context-aware help and intelligent suggestions.
    """

    def __init__(self):
        self.context_timeout_minutes = getattr(settings, 'HELPBOT_CONTEXT_TIMEOUT_MINUTES', 30)
        self.max_journey_length = getattr(settings, 'HELPBOT_MAX_JOURNEY_LENGTH', 20)
        self.cache_prefix = 'helpbot_context'
        self.cache_timeout = getattr(settings, 'HELPBOT_CACHE_TIMEOUT', 1800)  # 30 minutes

    def capture_context(self, user, request=None, session: HelpBotSession = None,
                       additional_context: Dict[str, Any] = None) -> HelpBotContext:
        """
        Capture current user context from request and session data.

        Args:
            user: Django user instance
            request: Django request object (if available)
            session: HelpBot session (optional)
            additional_context: Additional context data

        Returns:
            HelpBotContext instance
        """
        try:
            with transaction.atomic():
                context_data = self._extract_context_from_request(request) if request else {}

                # Merge additional context
                if additional_context:
                    context_data.update(additional_context)

                # Get or update user journey
                user_journey = self._update_user_journey(user, context_data.get('current_url'))

                # Extract error context if present
                error_context = self._extract_error_context(request, context_data)

                # Create context record
                context = HelpBotContext.objects.create(
                    user=user,
                    session=session,
                    current_url=context_data.get('current_url', ''),
                    page_title=context_data.get('page_title', ''),
                    app_name=context_data.get('app_name', ''),
                    view_name=context_data.get('view_name', ''),
                    user_role=self._determine_user_role(user),
                    form_data=context_data.get('form_data', {}),
                    error_context=error_context,
                    user_journey=user_journey,
                    browser_info=context_data.get('browser_info', {})
                )

                # Cache current context
                cache_key = f"{self.cache_prefix}_current_{user.id}"
                cache.set(cache_key, {
                    'context_id': str(context.context_id),
                    'app_name': context.app_name,
                    'view_name': context.view_name,
                    'current_url': context.current_url,
                    'timestamp': context.timestamp.isoformat(),
                }, self.cache_timeout)

                logger.debug(f"Captured context {context.context_id} for user {user.email}")
                return context

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error capturing context: {e}", exc_info=True)
            # Return minimal context to avoid breaking functionality
            return self._create_minimal_context(user, session)

    def _extract_context_from_request(self, request) -> Dict[str, Any]:
        """Extract context information from Django request."""
        try:
            context = {}

            # Basic request information
            if hasattr(request, 'path'):
                context['current_url'] = request.build_absolute_uri()
                context['path'] = request.path

            # Resolve URL to get app and view name
            if hasattr(request, 'resolver_match') and request.resolver_match:
                context['app_name'] = getattr(request.resolver_match, 'app_name', '')
                context['view_name'] = getattr(request.resolver_match, 'url_name', '')
                context['namespace'] = getattr(request.resolver_match, 'namespace', '')

            # Page title from context or headers
            page_title = ''
            if hasattr(request, 'META'):
                page_title = request.META.get('HTTP_X_PAGE_TITLE', '')

            # Try to get from breadcrumbs or page context
            if not page_title and hasattr(request, 'session'):
                page_title = request.session.get('page_title', '')

            context['page_title'] = page_title

            # Form data if POST request
            if request.method == 'POST' and hasattr(request, 'POST'):
                # Only capture non-sensitive form data
                safe_form_data = {}
                for key, value in request.POST.items():
                    if not self._is_sensitive_field(key):
                        # Limit value length and convert to string
                        safe_value = str(value)[:200]
                        safe_form_data[key] = safe_value

                context['form_data'] = safe_form_data

            # Browser and device information
            context['browser_info'] = self._extract_browser_info(request)

            return context

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error extracting context from request: {e}", exc_info=True)
            return {}

    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if a form field contains sensitive information."""
        sensitive_keywords = [
            'password', 'passwd', 'secret', 'key', 'token', 'csrf',
            'credit', 'card', 'ssn', 'social', 'bank', 'account',
            'email', 'phone', 'mobile', 'address'
        ]

        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in sensitive_keywords)

    def _extract_browser_info(self, request) -> Dict[str, Any]:
        """Extract browser and device information from request."""
        try:
            browser_info = {}

            if hasattr(request, 'META'):
                meta = request.META

                # User agent
                user_agent = meta.get('HTTP_USER_AGENT', '')
                browser_info['user_agent'] = user_agent[:500]  # Limit length

                # Client IP (be careful with privacy)
                # Only store for debugging purposes, respect privacy laws
                if settings.DEBUG:
                    browser_info['client_ip'] = meta.get('REMOTE_ADDR', '')

                # Accept language
                browser_info['accept_language'] = meta.get('HTTP_ACCEPT_LANGUAGE', '')[:100]

                # Referer
                browser_info['referer'] = meta.get('HTTP_REFERER', '')[:500]

                # Device hints
                browser_info['is_mobile'] = 'Mobile' in user_agent
                browser_info['is_tablet'] = 'Tablet' in user_agent

            return browser_info

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error extracting browser info: {e}", exc_info=True)
            return {}

    def _extract_error_context(self, request, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract error context if user encountered an error."""
        try:
            error_context = {}

            # Check for error information in session
            if hasattr(request, 'session'):
                session = request.session

                # Django error information
                if 'error_message' in session:
                    error_context['error_message'] = session['error_message']
                if 'error_type' in session:
                    error_context['error_type'] = session['error_type']

                # Custom error tracking
                if 'helpbot_last_error' in session:
                    error_context.update(session['helpbot_last_error'])

            # Check for error status codes
            if hasattr(request, 'status_code') and request.status_code >= 400:
                error_context['http_status'] = request.status_code

            # Check URL path for error pages
            path = context_data.get('path', '')
            if any(error_path in path for error_path in ['/error/', '/404/', '/500/', '/403/']):
                error_context['error_page'] = path

            return error_context

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error extracting error context: {e}", exc_info=True)
            return {}

    def _update_user_journey(self, user, current_url: str) -> List[Dict[str, Any]]:
        """Update and return user's navigation journey."""
        try:
            # Get existing journey from cache
            journey_cache_key = f"{self.cache_prefix}_journey_{user.id}"
            user_journey = cache.get(journey_cache_key, [])

            if current_url:
                # Add current page to journey
                journey_entry = {
                    'url': current_url,
                    'timestamp': datetime.now().isoformat(),
                    'path': urlparse(current_url).path if current_url else ''
                }

                # Avoid duplicate consecutive entries
                if not user_journey or user_journey[-1]['url'] != current_url:
                    user_journey.append(journey_entry)

                    # Limit journey length
                    if len(user_journey) > self.max_journey_length:
                        user_journey = user_journey[-self.max_journey_length:]

                    # Update cache
                    cache.set(journey_cache_key, user_journey, self.cache_timeout)

            return user_journey

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error updating user journey: {e}", exc_info=True)
            return []

    def _determine_user_role(self, user) -> str:
        """Determine user's role/permission level."""
        try:
            if user.is_superuser:
                return 'superuser'
            elif user.is_staff:
                return 'staff'
            elif hasattr(user, 'isadmin') and user.isadmin:
                return 'admin'
            else:
                return 'user'

        except Exception:
            return 'user'

    def _create_minimal_context(self, user, session: HelpBotSession = None) -> HelpBotContext:
        """Create minimal context when full context extraction fails."""
        try:
            return HelpBotContext.objects.create(
                user=user,
                session=session,
                current_url='',
                page_title='Unknown',
                app_name='',
                view_name='',
                user_role=self._determine_user_role(user),
                form_data={},
                error_context={},
                user_journey=[],
                browser_info={}
            )
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error creating minimal context: {e}", exc_info=True)
            raise

    def get_current_context(self, user) -> Optional[HelpBotContext]:
        """Get user's current context."""
        try:
            # Try cache first
            cache_key = f"{self.cache_prefix}_current_{user.id}"
            cached_context = cache.get(cache_key)

            if cached_context:
                # Get full context from database
                try:
                    return HelpBotContext.objects.get(
                        context_id=cached_context['context_id']
                    )
                except HelpBotContext.DoesNotExist:
                    pass

            # Get most recent context from database
            cutoff_time = timezone.now() - timedelta(minutes=self.context_timeout_minutes)

            return HelpBotContext.objects.filter(
                user=user,
                timestamp__gte=cutoff_time
            ).order_by('-timestamp').first()

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error getting current context: {e}", exc_info=True)
            return None

    def get_context_suggestions(self, user, current_context: HelpBotContext = None) -> List[Dict[str, str]]:
        """Generate context-aware suggestions for the user."""
        try:
            suggestions = []

            if not current_context:
                current_context = self.get_current_context(user)

            if not current_context:
                return self._get_default_suggestions()

            # App-specific suggestions
            app_suggestions = self._get_app_specific_suggestions(current_context.app_name)
            suggestions.extend(app_suggestions)

            # Error-specific suggestions
            if current_context.error_context:
                error_suggestions = self._get_error_suggestions(current_context.error_context)
                suggestions.extend(error_suggestions)

            # Journey-based suggestions
            journey_suggestions = self._get_journey_suggestions(current_context.user_journey)
            suggestions.extend(journey_suggestions)

            # Limit and deduplicate
            unique_suggestions = []
            seen = set()
            for suggestion in suggestions:
                key = suggestion['text'].lower()
                if key not in seen:
                    unique_suggestions.append(suggestion)
                    seen.add(key)

            return unique_suggestions[:6]  # Limit to 6 suggestions

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error getting context suggestions: {e}", exc_info=True)
            return self._get_default_suggestions()

    def _get_app_specific_suggestions(self, app_name: str) -> List[Dict[str, str]]:
        """Get suggestions specific to the current app."""
        app_suggestions = {
            'activity': [
                {'text': 'How to create a new task', 'category': 'how_to'},
                {'text': 'Task scheduling guide', 'category': 'guide'},
                {'text': 'Asset management help', 'category': 'feature'},
                {'text': 'Tour management overview', 'category': 'feature'},
            ],
            'peoples': [
                {'text': 'User account management', 'category': 'guide'},
                {'text': 'Attendance tracking help', 'category': 'feature'},
                {'text': 'Setting user permissions', 'category': 'how_to'},
                {'text': 'Employee directory guide', 'category': 'feature'},
            ],
            'reports': [
                {'text': 'How to generate reports', 'category': 'how_to'},
                {'text': 'Report scheduling guide', 'category': 'guide'},
                {'text': 'Export options explained', 'category': 'feature'},
                {'text': 'Custom report creation', 'category': 'how_to'},
            ],
            'y_helpdesk': [
                {'text': 'Creating support tickets', 'category': 'how_to'},
                {'text': 'Ticket escalation process', 'category': 'guide'},
                {'text': 'Help desk workflow', 'category': 'feature'},
                {'text': 'Ticket status management', 'category': 'guide'},
            ],
            'onboarding': [
                {'text': 'Setup and configuration guide', 'category': 'guide'},
                {'text': 'Business unit setup', 'category': 'how_to'},
                {'text': 'User onboarding process', 'category': 'feature'},
                {'text': 'System configuration help', 'category': 'guide'},
            ],
        }

        return app_suggestions.get(app_name, [])

    def _get_error_suggestions(self, error_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get suggestions based on error context."""
        suggestions = []

        if 'http_status' in error_context:
            status = error_context['http_status']
            if status == 404:
                suggestions.append({'text': 'Help finding the right page', 'category': 'troubleshooting'})
                suggestions.append({'text': 'Navigation guide', 'category': 'guide'})
            elif status == 403:
                suggestions.append({'text': 'Permission and access help', 'category': 'troubleshooting'})
                suggestions.append({'text': 'User roles explained', 'category': 'guide'})
            elif status >= 500:
                suggestions.append({'text': 'System error troubleshooting', 'category': 'troubleshooting'})
                suggestions.append({'text': 'Contact technical support', 'category': 'support'})

        if 'error_message' in error_context:
            suggestions.append({'text': 'Help with this error', 'category': 'troubleshooting'})

        return suggestions

    def _get_journey_suggestions(self, user_journey: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Get suggestions based on user's navigation journey."""
        suggestions = []

        if not user_journey:
            return suggestions

        # Analyze recent pages
        recent_paths = [entry.get('path', '') for entry in user_journey[-5:]]

        # Detect patterns
        if '/admin/' in str(recent_paths):
            suggestions.append({'text': 'Admin features guide', 'category': 'guide'})

        if '/api/' in str(recent_paths):
            suggestions.append({'text': 'API documentation', 'category': 'api'})

        # Multiple different apps = user exploring
        unique_apps = set()
        for path in recent_paths:
            if path.startswith('/'):
                parts = path.strip('/').split('/')
                if parts:
                    unique_apps.add(parts[0])

        if len(unique_apps) > 2:
            suggestions.append({'text': 'Platform overview and features', 'category': 'guide'})

        return suggestions

    def _get_default_suggestions(self) -> List[Dict[str, str]]:
        """Get default suggestions when no context is available."""
        return [
            {'text': 'Getting started guide', 'category': 'guide'},
            {'text': 'Platform features overview', 'category': 'feature'},
            {'text': 'Common tasks tutorial', 'category': 'tutorial'},
            {'text': 'Frequently asked questions', 'category': 'faq'},
            {'text': 'Navigation help', 'category': 'guide'},
            {'text': 'Contact support', 'category': 'support'},
        ]

    def get_user_journey_analysis(self, user) -> Dict[str, Any]:
        """Analyze user's journey for insights and help targeting."""
        try:
            # Get recent contexts
            recent_contexts = HelpBotContext.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-timestamp')[:50]

            if not recent_contexts:
                return {'analysis': 'insufficient_data', 'insights': []}

            # Analyze patterns
            app_usage = {}
            error_count = 0
            unique_pages = set()

            for context in recent_contexts:
                # App usage
                if context.app_name:
                    app_usage[context.app_name] = app_usage.get(context.app_name, 0) + 1

                # Error tracking
                if context.error_context:
                    error_count += 1

                # Page diversity
                if context.current_url:
                    unique_pages.add(context.current_url)

            # Generate insights
            insights = []

            # Most used app
            if app_usage:
                most_used_app = max(app_usage, key=app_usage.get)
                insights.append({
                    'type': 'app_usage',
                    'message': f"You've been working mostly in {most_used_app.title()} recently",
                    'suggestion': f"Need help with {most_used_app} features?"
                })

            # Error frequency
            if error_count > 0:
                error_rate = error_count / len(recent_contexts)
                if error_rate > 0.2:  # More than 20% errors
                    insights.append({
                        'type': 'errors',
                        'message': "You've encountered several errors recently",
                        'suggestion': "Would you like troubleshooting help?"
                    })

            # Exploration pattern
            exploration_rate = len(unique_pages) / len(recent_contexts)
            if exploration_rate > 0.8:  # High exploration
                insights.append({
                    'type': 'exploration',
                    'message': "You're exploring many different features",
                    'suggestion': "Would you like a guided tour?"
                })

            return {
                'analysis': 'completed',
                'insights': insights,
                'stats': {
                    'app_usage': app_usage,
                    'error_rate': error_count / len(recent_contexts),
                    'pages_visited': len(unique_pages),
                    'session_count': len(recent_contexts),
                }
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error analyzing user journey: {e}", exc_info=True)
            return {'analysis': 'error', 'insights': []}

    def cleanup_old_contexts(self, days: int = 30) -> int:
        """Clean up old context records."""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)

            deleted_count, _ = HelpBotContext.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()

            logger.info(f"Cleaned up {deleted_count} old context records")
            return deleted_count

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error cleaning up old contexts: {e}", exc_info=True)
            return 0