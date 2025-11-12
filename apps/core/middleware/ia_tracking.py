"""
Middleware for tracking Information Architecture metrics
"""
import time
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve, Resolver404
from django.conf import settings
from django.utils import timezone

import logging
logger = logging.getLogger(__name__)


from apps.core.url_router import URLRouter
from apps.core.models.monitoring import (
    PageView, NavigationClick, ErrorLog, LegacyURLAccess, NavigationPath
)
from apps.core.models.heatmap import (
    HeatmapSession, ClickHeatmap, ScrollHeatmap, AttentionHeatmap, 
    ElementInteraction, HeatmapAggregation
)


class IATrackingMiddleware(MiddlewareMixin):
    """Track page views, performance, and navigation patterns"""
    
    def process_request(self, request):
        """Start timing the request"""
        request._start_time = time.time()
        
        # Get or create session ID
        if not request.session.session_key:
            request.session.save()
        request._ia_session_id = request.session.session_key
        
        # Initialize navigation tracking
        if 'ia_navigation_path' not in request.session:
            request.session['ia_navigation_path'] = []
            request.session['ia_session_start'] = timezone.now().isoformat()
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Track view access"""
        request._view_start_time = time.time()
        
        # Track legacy URL access
        if URLRouter.should_show_deprecation_warning(request.path):
            self._track_legacy_url(request)
    
    def process_response(self, request, response):
        """Track page view and performance metrics"""
        # Skip if this is an AJAX request or static file
        if self._should_skip_tracking(request):
            return response
        
        # Calculate timings
        total_time = time.time() - getattr(request, '_start_time', time.time())
        view_time = time.time() - getattr(request, '_view_start_time', time.time())
        
        # Track successful page view
        if response.status_code == 200:
            self._track_page_view(request, response, total_time, view_time)
            self._update_navigation_path(request)
        
        # Track errors
        elif response.status_code >= 400:
            self._track_error(request, response)
        
        return response
    
    def _should_skip_tracking(self, request):
        """Determine if we should skip tracking this request"""
        # Skip AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return True
        
        # Skip static files
        if request.path.startswith(settings.STATIC_URL):
            return True
        
        # Skip media files
        if request.path.startswith(settings.MEDIA_URL):
            return True
        
        # Skip admin
        if request.path.startswith('/admin/'):
            return True
        
        # Skip API endpoints
        if request.path.startswith('/api/'):
            return True
        
        return False
    
    def _track_page_view(self, request, response, total_time, view_time):
        """Track successful page view"""
        try:
            # Determine page type
            page_type = self._determine_page_type(request)
            
            PageView.objects.create(
                session_id=request._ia_session_id,
                user=request.user if request.user.is_authenticated else None,
                path=request.path,
                page_type=page_type,
                load_time=total_time,
                content_render_time=view_time,
                menu_render_time=total_time - view_time,  # Approximate
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=self._get_client_ip(request),
                referer=request.META.get('HTTP_REFERER', '')
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            # Don't let tracking errors break the site
            if settings.DEBUG:
                logger.error(f"Error tracking page view: {e}")
    
    def _track_legacy_url(self, request):
        """Track access to legacy URLs"""
        try:
            new_url = URLRouter.get_new_url(request.path.lstrip('/'))
            
            LegacyURLAccess.objects.create(
                legacy_url=request.path,
                new_url=new_url,
                user=request.user if request.user.is_authenticated else None,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=self._get_client_ip(request),
                referer=request.META.get('HTTP_REFERER', '')
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            if settings.DEBUG:
                logger.error(f"Error tracking legacy URL: {e}")
    
    def _track_error(self, request, response):
        """Track error responses"""
        try:
            # Check if this is a legacy URL
            is_legacy = URLRouter.should_show_deprecation_warning(request.path)
            suggested_url = URLRouter.get_new_url(request.path.lstrip('/')) if is_legacy else ''
            
            ErrorLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                status_code=response.status_code,
                path=request.path,
                method=request.method,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=self._get_client_ip(request),
                referer=request.META.get('HTTP_REFERER', ''),
                error_message=getattr(response, 'reason_phrase', ''),
                is_legacy_url=is_legacy,
                suggested_url=suggested_url
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            if settings.DEBUG:
                logger.error(f"Error tracking error: {e}")
    
    def _update_navigation_path(self, request):
        """Update user's navigation path in session"""
        try:
            path_list = request.session.get('ia_navigation_path', [])
            
            # Add current page to path
            path_list.append({
                'path': request.path,
                'timestamp': timezone.now().isoformat(),
                'title': self._get_page_title(request)
            })
            
            # Keep last 20 pages
            path_list = path_list[-20:]
            
            request.session['ia_navigation_path'] = path_list
            
            # Check if this completes a goal
            goal = self._check_goal_completion(path_list)
            if goal:
                self._save_navigation_path(request, path_list, goal)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            if settings.DEBUG:
                logger.error(f"Error updating navigation path: {e}")
    
    def _check_goal_completion(self, path_list):
        """Check if the navigation path completes a known goal"""
        if len(path_list) < 2:
            return None
        
        # Define goal patterns
        goal_patterns = {
            'view_asset': lambda p: any('/assets/' in page['path'] and 
                                      not page['path'].endswith('/assets/') 
                                      for page in p[-3:]),
            'create_task': lambda p: any('/tasks/create' in page['path'] or 
                                       '/tasks/new' in page['path'] 
                                       for page in p[-5:]),
            'view_report': lambda p: any('/reports/' in page['path'] and 
                                       'download' in page['path'] 
                                       for page in p[-3:]),
        }
        
        for goal_type, check_func in goal_patterns.items():
            if check_func(path_list):
                return goal_type
        
        return None
    
    def _save_navigation_path(self, request, path_list, goal_type):
        """Save completed navigation path for analysis"""
        try:
            # Calculate total time
            if path_list:
                start_time = timezone.datetime.fromisoformat(
                    request.session.get('ia_session_start', path_list[0]['timestamp'])
                )
                end_time = timezone.datetime.fromisoformat(path_list[-1]['timestamp'])
                total_time = (end_time - start_time).total_seconds()
            else:
                total_time = 0
            
            # Extract just the paths
            path_sequence = [p['path'] for p in path_list]
            
            NavigationPath.objects.create(
                session_id=request._ia_session_id,
                user=request.user if request.user.is_authenticated else None,
                path_sequence=path_sequence,
                total_pages=len(path_sequence),
                total_time=total_time,
                goal_completed=True,
                goal_type=goal_type
            )
            
            # Reset path tracking
            request.session['ia_navigation_path'] = []
            request.session['ia_session_start'] = timezone.now().isoformat()
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            if settings.DEBUG:
                logger.error(f"Error saving navigation path: {e}")
    
    def _determine_page_type(self, request):
        """Determine the type of page being viewed"""
        try:
            resolved = resolve(request.path)
            view_name = resolved.view_name.lower()
            
            if 'list' in view_name:
                return 'list'
            elif 'detail' in view_name or 'view' in view_name:
                return 'detail'
            elif 'create' in view_name or 'update' in view_name or 'form' in view_name:
                return 'form'
            elif 'dashboard' in view_name:
                return 'dashboard'
            elif 'report' in view_name:
                return 'report'
            else:
                return 'other'
        except Resolver404:
            return 'other'
    
    def _get_page_title(self, request):
        """Try to determine page title"""
        try:
            resolved = resolve(request.path)
            return resolved.view_name.replace('_', ' ').title()
        except (ValueError, TypeError, AttributeError) as e:
            return request.path
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class NavigationClickTrackingMiddleware(MiddlewareMixin):
    """Track navigation menu clicks via AJAX"""
    
    def process_request(self, request):
        """Handle navigation click tracking requests"""
        if request.path == '/_track/navigation-click/' and request.method == 'POST':
            self._track_navigation_click(request)
            
            from django.http import JsonResponse
            return JsonResponse({'status': 'tracked'})
    
    def _track_navigation_click(self, request):
        """Track a navigation menu click"""
        try:
            import json
            data = json.loads(request.body)
            
            # Get click order for session
            session_clicks = request.session.get('ia_click_count', 0) + 1
            request.session['ia_click_count'] = session_clicks
            
            NavigationClick.objects.create(
                session_id=request.session.session_key,
                user=request.user if request.user.is_authenticated else None,
                menu_item=data.get('menu_item', ''),
                menu_depth=data.get('menu_depth', 1),
                clicked_url=data.get('url', ''),
                time_to_click=data.get('time_to_click', 0),
                click_order=session_clicks
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            if settings.DEBUG:
                logger.error(f"Error tracking navigation click: {e}")


class HeatmapTrackingMiddleware(MiddlewareMixin):
    """Middleware for processing heatmap tracking data from frontend"""
    
    def process_request(self, request):
        """Handle heatmap tracking API requests"""
        if request.path.startswith('/api/heatmap/'):
            return self._handle_heatmap_request(request)
    
    def _handle_heatmap_request(self, request):
        """Process different heatmap endpoints"""
        from django.http import JsonResponse
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Route to appropriate handler
        if request.path == '/api/heatmap/session/init/':
            return self._init_session(request, data)
        elif request.path == '/api/heatmap/session/end/':
            return self._end_session(request, data)
        elif request.path == '/api/heatmap/track/':
            return self._track_data(request, data)
        
        return JsonResponse({'error': 'Endpoint not found'}, status=404)
    
    def _init_session(self, request, data):
        """Initialize a new heatmap tracking session"""
        try:
            session = HeatmapSession.objects.create(
                session_id=data['sessionId'],
                user=request.user if request.user.is_authenticated else None,
                page_url=data['pageUrl'],
                page_title=data['pageTitle'],
                viewport_width=data['viewport']['width'],
                viewport_height=data['viewport']['height'],
                screen_width=data['screen']['width'],
                screen_height=data['screen']['height'],
                device_type=data['deviceType'],
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=self._get_client_ip(request),
                referrer=request.META.get('HTTP_REFERER', '')
            )
            
            from django.http import JsonResponse
            return JsonResponse({
                'status': 'success',
                'sessionId': session.session_id
            })
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handling import ErrorHandler
            correlation_id = ErrorHandler.handle_exception(e, context={'view': 'initialize_heatmap_session'})
            if settings.DEBUG:
                logger.error(f"Error initializing heatmap session: {e} [correlation_id={correlation_id}]")
            return ErrorHandler.create_error_response("Failed to initialize tracking session", error_code="TRACKING_ERROR", correlation_id=correlation_id)
    
    def _end_session(self, request, data):
        """End a heatmap tracking session"""
        try:
            session = HeatmapSession.objects.get(session_id=data['sessionId'])
            session.end_session()
            
            # Trigger aggregation if needed
            self._check_aggregation_needed(session.page_url)
            
            from django.http import JsonResponse
            return JsonResponse({'status': 'success'})
        except HeatmapSession.DoesNotExist:
            from django.http import JsonResponse
            return JsonResponse({'error': 'Session not found'}, status=404)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handling import ErrorHandler
            correlation_id = ErrorHandler.handle_exception(e, context={'view': 'end_heatmap_session'})
            if settings.DEBUG:
                logger.error(f"Error ending heatmap session: {e} [correlation_id={correlation_id}]")
            return ErrorHandler.create_error_response("Failed to end tracking session", error_code="TRACKING_ERROR", correlation_id=correlation_id)
    
    def _track_data(self, request, data):
        """Track heatmap data from frontend"""
        try:
            session = HeatmapSession.objects.get(session_id=data['sessionId'])
            
            # Track clicks
            for click in data.get('clicks', []):
                ClickHeatmap.objects.create(
                    session=session,
                    x_position=click['x'],
                    y_position=click['y'],
                    absolute_x=click['absoluteX'],
                    absolute_y=click['absoluteY'],
                    element_type=click['element']['tagName'],
                    element_id=click['element']['id'],
                    element_class=click['element']['className'],
                    element_text=click['element']['text'][:200],
                    is_navigation=click['element']['isNavigation'],
                    time_since_load=click['timeSinceLoad'],
                    click_type=click.get('clickType', 'left')
                )
            
            # Track scrolls
            for scroll in data.get('scrolls', []):
                ScrollHeatmap.objects.create(
                    session=session,
                    scroll_depth_pixels=scroll['scrollDepthPixels'],
                    scroll_depth_percentage=scroll['scrollDepthPercentage'],
                    max_scroll_depth=scroll['scrollDepthPercentage'],
                    scroll_velocity=scroll.get('velocity', 0)
                )
            
            # Track element interactions
            for interaction in data.get('interactions', []):
                ElementInteraction.objects.create(
                    session=session,
                    element_selector=interaction['element']['selector'],
                    element_type=interaction['element']['tagName'],
                    element_id=interaction['element']['id'],
                    element_class=interaction['element']['className'],
                    element_text=interaction['element']['text'][:200],
                    interaction_type=interaction['interactionType'],
                    duration=interaction.get('duration')
                )
            
            # Track attention zones
            for zone in data.get('attention', []):
                AttentionHeatmap.objects.create(
                    session=session,
                    x_start=zone['x_start'],
                    y_start=zone['y_start'],
                    x_end=zone['x_end'],
                    y_end=zone['y_end'],
                    attention_duration=zone['duration'],
                    attention_score=min(zone['duration'] / 60, 1.0)  # Normalize to 0-1
                )
            
            # Update session data points count
            session.data_points_collected += (
                len(data.get('clicks', [])) +
                len(data.get('scrolls', [])) +
                len(data.get('interactions', [])) +
                len(data.get('attention', []))
            )
            session.save()
            
            from django.http import JsonResponse
            return JsonResponse({'status': 'success'})
        except HeatmapSession.DoesNotExist:
            from django.http import JsonResponse
            return JsonResponse({'error': 'Session not found'}, status=404)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            from apps.core.error_handling import ErrorHandler
            correlation_id = ErrorHandler.handle_exception(e, context={'view': 'track_heatmap_data'})
            if settings.DEBUG:
                logger.error(f"Error tracking heatmap data: {e} [correlation_id={correlation_id}]")
            return ErrorHandler.create_error_response("Failed to track data", error_code="TRACKING_ERROR", correlation_id=correlation_id)
    
    def _check_aggregation_needed(self, page_url):
        """Check if aggregation is needed for this page"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Check if we have enough sessions to aggregate
        recent_sessions = HeatmapSession.objects.filter(
            page_url=page_url,
            start_time__gte=timezone.now() - timedelta(hours=1),
            is_active=False
        ).count()
        
        if recent_sessions >= 10:  # Aggregate every 10 sessions
            # Trigger async aggregation task
            try:
                from background_tasks.tasks import aggregate_heatmap_data
                aggregate_heatmap_data.delay(page_url)
            except ImportError:
                # If Celery not available, do synchronous aggregation
                self._perform_aggregation(page_url)
    
    def _perform_aggregation(self, page_url):
        """Perform heatmap data aggregation"""
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(hours=1)
            
            HeatmapAggregation.generate_aggregation(
                page_url=page_url,
                start_date=start_date,
                end_date=end_date
            )
        except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            if settings.DEBUG:
                logger.error(f"Error aggregating heatmap data: {e}")
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip