"""
Wisdom Conversation Views

Django views for the "Conversations with Wisdom" feature, providing web interfaces
and API endpoints for displaying, interacting with, and managing wisdom conversations.

Chain of Thought Reasoning:
1. Main view to display book-like conversation interface
2. API endpoints for bookmarking, reflection, and engagement tracking
3. Thread filtering and search functionality
4. Export and sharing capabilities
5. Mobile-optimized responses for field workers
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Prefetch
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib import messages

from ..models.wisdom_conversations import (
    ConversationThread, WisdomConversation, ConversationEngagement, ConversationBookmark
)
from ..services.wisdom_conversation_generator import WisdomConversationGenerator
from ..services.conversation_flow_manager import ConversationFlowManager
from ..services.conversation_personalization_system import ConversationPersonalizationSystem
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def conversations_with_wisdom_view(request):
    """
    Main view for displaying the book-like conversations interface.

    Ultra-think approach: Create immersive reading experience that feels like
    a personalized book of the user's mental health journey.
    """

    user = request.user
    thread_filter = request.GET.get('thread', 'all')
    search_query = request.GET.get('search', '')

    logger.info(f"Loading wisdom conversations for user {user.peoplename} with filter: {thread_filter}")

    # Get user's conversation threads
    threads_queryset = ConversationThread.objects.filter(user=user).order_by(
        '-last_conversation_date'
    )

    # Build base conversation query
    conversations_query = WisdomConversation.objects.filter(user=user).select_related(
        'thread', 'source_intervention_delivery__intervention'
    ).prefetch_related(
        'engagements', 'bookmarks'
    )

    # Apply thread filter
    if thread_filter != 'all':
        try:
            selected_thread = ConversationThread.objects.get(id=thread_filter, user=user)
            conversations_query = conversations_query.filter(thread=selected_thread)
        except (ConversationThread.DoesNotExist, ValueError):
            messages.warning(request, "Selected conversation thread not found.")
            thread_filter = 'all'

    # Apply search filter
    if search_query:
        conversations_query = conversations_query.filter(
            Q(conversation_text__icontains=search_query) |
            Q(contextual_bridge_text__icontains=search_query) |
            Q(conversation_metadata__keywords__icontains=search_query)
        )

    # Order conversations for book-like flow
    conversations = conversations_query.order_by(
        'thread__thread_type', 'sequence_number'
    )

    # Get conversation analytics
    analytics = _get_conversation_analytics(user)

    # Get personalization insights
    personalization_system = ConversationPersonalizationSystem()
    personalization_insights = personalization_system.get_personalization_insights(user)

    # Determine if this is a mobile request
    is_mobile = _is_mobile_request(request)

    # Track page view engagement
    _track_page_view(user, thread_filter, search_query)

    context = {
        'user': user,
        'conversations': conversations,
        'conversation_threads': threads_queryset,
        'current_thread': thread_filter,
        'search_query': search_query,
        'analytics': analytics,
        'personalization_insights': personalization_insights,
        'is_mobile': is_mobile,
        'total_conversations': conversations.count(),
        'total_threads': threads_queryset.count(),
    }

    # Use mobile template if on mobile device
    template_name = (
        'wellness/conversations_with_wisdom_mobile.html' if is_mobile
        else 'wellness/conversations_with_wisdom.html'
    )

    return render(request, template_name, context)


@login_required
@require_POST
def toggle_conversation_bookmark(request, conversation_id):
    """
    API endpoint to toggle bookmark status for a conversation.
    """

    try:
        conversation = get_object_or_404(
            WisdomConversation,
            id=conversation_id,
            user=request.user
        )

        # Parse request data
        data = json.loads(request.body)
        should_bookmark = data.get('bookmarked', True)

        if should_bookmark:
            # Create bookmark
            bookmark, created = ConversationBookmark.objects.get_or_create(
                user=request.user,
                conversation=conversation,
                defaults={
                    'category': 'inspiration',
                    'personal_note': '',
                }
            )

            # Track engagement
            ConversationEngagement.objects.create(
                user=request.user,
                conversation=conversation,
                engagement_type='bookmark',
                access_context=data.get('context', 'manual_browse')
            )

            response_data = {
                'success': True,
                'bookmarked': True,
                'message': 'Conversation bookmarked successfully'
            }

        else:
            # Remove bookmark
            deleted_count = ConversationBookmark.objects.filter(
                user=request.user,
                conversation=conversation
            ).delete()[0]

            response_data = {
                'success': True,
                'bookmarked': False,
                'message': 'Bookmark removed successfully'
            }

        logger.info(f"Bookmark toggled for conversation {conversation_id} by user {request.user.peoplename}")
        return JsonResponse(response_data)

    except WisdomConversation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Conversation not found'
        }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Error toggling bookmark for conversation {conversation_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating bookmark'
        }, status=500)


@login_required
@require_POST
def track_conversation_engagement(request, conversation_id):
    """
    API endpoint to track user engagement with a specific conversation.
    """

    try:
        conversation = get_object_or_404(
            WisdomConversation,
            id=conversation_id,
            user=request.user
        )

        # Parse engagement data
        data = json.loads(request.body)
        engagement_type = data.get('type', 'view')
        time_spent = data.get('time_spent_seconds', 0)
        scroll_percentage = data.get('scroll_percentage', 0)
        effectiveness_rating = data.get('effectiveness_rating')
        reflection_note = data.get('reflection_note', '')
        device_type = data.get('device_type', 'desktop')
        access_context = data.get('access_context', 'manual_browse')

        # Create engagement record
        engagement = ConversationEngagement.objects.create(
            user=request.user,
            conversation=conversation,
            engagement_type=engagement_type,
            time_spent_seconds=time_spent,
            scroll_percentage=scroll_percentage,
            effectiveness_rating=effectiveness_rating,
            user_reflection_note=reflection_note,
            device_type=device_type,
            access_context=access_context,
            engagement_metadata={
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now().isoformat(),
                'session_id': request.session.session_key,
            }
        )

        logger.info(f"Engagement tracked: {engagement_type} for conversation {conversation_id}")

        return JsonResponse({
            'success': True,
            'engagement_id': str(engagement.id),
            'message': 'Engagement tracked successfully'
        })

    except WisdomConversation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Conversation not found'
        }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Error tracking engagement for conversation {conversation_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while tracking engagement'
        }, status=500)


@login_required
def conversation_reflection_view(request, conversation_id):
    """
    View for adding personal reflections to a conversation.
    """

    conversation = get_object_or_404(
        WisdomConversation,
        id=conversation_id,
        user=request.user
    )

    if request.method == 'POST':
        reflection_note = request.POST.get('reflection_note', '').strip()
        effectiveness_rating = request.POST.get('effectiveness_rating')

        if reflection_note or effectiveness_rating:
            # Create reflection engagement
            ConversationEngagement.objects.create(
                user=request.user,
                conversation=conversation,
                engagement_type='reflection_note',
                effectiveness_rating=int(effectiveness_rating) if effectiveness_rating else None,
                user_reflection_note=reflection_note,
                access_context='reflection_page'
            )

            messages.success(request, 'Your reflection has been saved.')
            return redirect('wellness:conversations_with_wisdom')

    # Get existing reflections
    existing_reflections = ConversationEngagement.objects.filter(
        user=request.user,
        conversation=conversation,
        engagement_type='reflection_note'
    ).order_by('-engagement_date')

    context = {
        'conversation': conversation,
        'existing_reflections': existing_reflections,
    }

    return render(request, 'wellness/conversation_reflection.html', context)


@login_required
def conversation_export_view(request):
    """
    Export conversations in various formats (PDF, TXT, JSON).
    """

    user = request.user
    export_format = request.GET.get('format', 'pdf')
    thread_filter = request.GET.get('thread', 'all')
    date_range = request.GET.get('date_range', '30')  # days

    # Build conversation query
    conversations_query = WisdomConversation.objects.filter(user=user)

    # Apply filters
    if thread_filter != 'all':
        try:
            thread = ConversationThread.objects.get(id=thread_filter, user=user)
            conversations_query = conversations_query.filter(thread=thread)
        except ConversationThread.DoesNotExist:
            pass

    if date_range != 'all':
        try:
            days = int(date_range)
            start_date = timezone.now() - timedelta(days=days)
            conversations_query = conversations_query.filter(
                conversation_date__gte=start_date
            )
        except ValueError:
            pass

    conversations = conversations_query.order_by('thread__thread_type', 'sequence_number')

    # Generate export based on format
    if export_format == 'txt':
        return _export_conversations_txt(user, conversations)
    elif export_format == 'json':
        return _export_conversations_json(user, conversations)
    elif export_format == 'pdf':
        return _export_conversations_pdf(user, conversations)
    else:
        return JsonResponse({'error': 'Invalid export format'}, status=400)


@login_required
def conversation_analytics_api(request):
    """
    API endpoint for conversation analytics and insights.
    """

    user = request.user
    analytics = _get_comprehensive_analytics(user)

    return JsonResponse({
        'success': True,
        'analytics': analytics
    })


@login_required
def conversation_search_api(request):
    """
    API endpoint for searching conversations with advanced filters.
    """

    user = request.user
    query = request.GET.get('q', '')
    thread_type = request.GET.get('thread_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    tone = request.GET.get('tone', '')
    milestone_only = request.GET.get('milestone_only', '').lower() == 'true'

    # Build search query
    conversations_query = WisdomConversation.objects.filter(user=user)

    if query:
        conversations_query = conversations_query.filter(
            Q(conversation_text__icontains=query) |
            Q(contextual_bridge_text__icontains=query) |
            Q(thread__title__icontains=query)
        )

    if thread_type:
        conversations_query = conversations_query.filter(thread__thread_type=thread_type)

    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            conversations_query = conversations_query.filter(conversation_date__gte=from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            conversations_query = conversations_query.filter(conversation_date__lte=to_date)
        except ValueError:
            pass

    if tone:
        conversations_query = conversations_query.filter(conversation_tone=tone)

    if milestone_only:
        conversations_query = conversations_query.filter(is_milestone_conversation=True)

    # Paginate results
    page = int(request.GET.get('page', 1))
    paginator = Paginator(conversations_query.order_by('-conversation_date'), 20)
    conversations_page = paginator.get_page(page)

    # Serialize results
    results = []
    for conversation in conversations_page:
        results.append({
            'id': str(conversation.id),
            'title': conversation.thread.title,
            'date': conversation.conversation_date.isoformat(),
            'tone': conversation.get_conversation_tone_display(),
            'thread_type': conversation.thread.get_thread_type_display(),
            'is_milestone': conversation.is_milestone_conversation,
            'word_count': conversation.word_count,
            'reading_time': conversation.estimated_reading_time_seconds,
            'preview': conversation.conversation_text[:200] + '...' if len(conversation.conversation_text) > 200 else conversation.conversation_text,
            'url': f"/wellness/conversations/#{conversation.id}"
        })

    return JsonResponse({
        'success': True,
        'results': results,
        'pagination': {
            'page': page,
            'total_pages': paginator.num_pages,
            'total_results': paginator.count,
            'has_next': conversations_page.has_next(),
            'has_previous': conversations_page.has_previous(),
        }
    })


# Helper functions

def _get_conversation_analytics(user: User) -> Dict:
    """Get basic conversation analytics for the user"""

    threads = ConversationThread.objects.filter(user=user)
    conversations = WisdomConversation.objects.filter(user=user)
    engagements = ConversationEngagement.objects.filter(user=user)

    return {
        'total_conversations': conversations.count(),
        'total_threads': threads.count(),
        'total_words': sum(conv.word_count for conv in conversations),
        'total_reading_time': sum(conv.estimated_reading_time_seconds for conv in conversations),
        'avg_engagement_rating': engagements.aggregate(
            avg_rating=Avg('effectiveness_rating')
        )['avg_rating'] or 0,
        'milestone_conversations': conversations.filter(is_milestone_conversation=True).count(),
        'bookmarked_conversations': ConversationBookmark.objects.filter(user=user).count(),
    }


def _get_comprehensive_analytics(user: User) -> Dict:
    """Get comprehensive analytics including trends and insights"""

    basic_analytics = _get_conversation_analytics(user)

    # Add trend analysis
    last_30_days = timezone.now() - timedelta(days=30)
    recent_conversations = WisdomConversation.objects.filter(
        user=user,
        conversation_date__gte=last_30_days
    )

    # Engagement trends
    engagement_by_tone = ConversationEngagement.objects.filter(
        user=user,
        conversation__conversation_date__gte=last_30_days
    ).values('conversation__conversation_tone').annotate(
        avg_rating=Avg('effectiveness_rating'),
        count=Count('id')
    )

    # Reading patterns
    reading_times = list(recent_conversations.values_list('estimated_reading_time_seconds', flat=True))
    avg_reading_time = sum(reading_times) / len(reading_times) if reading_times else 0

    basic_analytics.update({
        'recent_activity': {
            'conversations_last_30_days': recent_conversations.count(),
            'avg_reading_time_recent': avg_reading_time,
            'engagement_by_tone': list(engagement_by_tone),
        },
        'trends': {
            'most_effective_tone': _get_most_effective_tone(user),
            'reading_frequency': _calculate_reading_frequency(user),
            'engagement_pattern': _analyze_engagement_pattern(user),
        }
    })

    return basic_analytics


def _is_mobile_request(request) -> bool:
    """Detect if request is from mobile device"""

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_indicators = ['mobile', 'android', 'iphone', 'ipad', 'tablet']

    return any(indicator in user_agent for indicator in mobile_indicators)


def _track_page_view(user: User, thread_filter: str, search_query: str):
    """Track page view analytics"""

    # Create a general page view engagement
    try:
        # Get most recent conversation for tracking
        recent_conversation = WisdomConversation.objects.filter(user=user).first()

        if recent_conversation:
            ConversationEngagement.objects.create(
                user=user,
                conversation=recent_conversation,
                engagement_type='view',
                access_context='routine_check',
                engagement_metadata={
                    'page_type': 'wisdom_conversations_main',
                    'thread_filter': thread_filter,
                    'search_query': search_query,
                    'timestamp': timezone.now().isoformat(),
                }
            )
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Error tracking page view for user {user.id}: {e}", exc_info=True)


def _export_conversations_txt(user: User, conversations) -> HttpResponse:
    """Export conversations as plain text"""

    content = f"Conversations with Wisdom - {user.peoplename}\n"
    content += f"Generated on {timezone.now().strftime('%B %d, %Y')}\n"
    content += "=" * 60 + "\n\n"

    current_thread = None
    for conversation in conversations:
        if current_thread != conversation.thread:
            current_thread = conversation.thread
            content += f"\n\n{current_thread.get_thread_type_display().upper()}\n"
            content += "-" * len(current_thread.get_thread_type_display()) + "\n\n"

        content += f"{conversation.conversation_date.strftime('%B %d, %Y')}\n"

        if conversation.contextual_bridge_text:
            content += f"\n{conversation.contextual_bridge_text}\n\n"

        content += f"{conversation.conversation_text}\n\n"
        content += "~" * 40 + "\n\n"

    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="wisdom_conversations_{user.id}.txt"'
    return response


def _export_conversations_json(user: User, conversations) -> HttpResponse:
    """Export conversations as JSON"""

    data = {
        'user': user.peoplename,
        'export_date': timezone.now().isoformat(),
        'conversations': []
    }

    for conversation in conversations:
        conv_data = {
            'id': str(conversation.id),
            'thread': {
                'title': conversation.thread.title,
                'type': conversation.thread.thread_type,
            },
            'date': conversation.conversation_date.isoformat(),
            'tone': conversation.conversation_tone,
            'bridge_text': conversation.contextual_bridge_text,
            'content': conversation.conversation_text,
            'word_count': conversation.word_count,
            'reading_time_seconds': conversation.estimated_reading_time_seconds,
            'is_milestone': conversation.is_milestone_conversation,
            'metadata': conversation.conversation_metadata,
        }
        data['conversations'].append(conv_data)

    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="wisdom_conversations_{user.id}.json"'
    return response


def _export_conversations_pdf(user: User, conversations) -> HttpResponse:
    """Export conversations as PDF (placeholder - would need reportlab)"""

    # For now, return HTML that can be printed to PDF
    html_content = render_to_string('wellness/conversations_export_pdf.html', {
        'user': user,
        'conversations': conversations,
        'export_date': timezone.now(),
    })

    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="wisdom_conversations_{user.id}.html"'
    return response


def _get_most_effective_tone(user: User) -> str:
    """Get the most effective conversation tone for user"""

    tone_effectiveness = ConversationEngagement.objects.filter(
        user=user,
        effectiveness_rating__isnull=False
    ).values('conversation__conversation_tone').annotate(
        avg_rating=Avg('effectiveness_rating')
    ).order_by('-avg_rating').first()

    return tone_effectiveness['conversation__conversation_tone'] if tone_effectiveness else 'warm_supportive'


def _calculate_reading_frequency(user: User) -> str:
    """Calculate user's reading frequency pattern"""

    conversations = WisdomConversation.objects.filter(user=user).order_by('-conversation_date')[:30]

    if conversations.count() < 7:
        return 'new_user'

    # Calculate average days between conversations
    dates = [conv.conversation_date for conv in conversations]
    if len(dates) < 2:
        return 'irregular'

    gaps = [(dates[i] - dates[i+1]).days for i in range(len(dates)-1)]
    avg_gap = sum(gaps) / len(gaps)

    if avg_gap <= 2:
        return 'daily'
    elif avg_gap <= 7:
        return 'weekly'
    elif avg_gap <= 14:
        return 'biweekly'
    else:
        return 'irregular'


def _analyze_engagement_pattern(user: User) -> str:
    """Analyze user's engagement pattern"""

    engagements = ConversationEngagement.objects.filter(user=user).order_by('-engagement_date')[:50]

    if engagements.count() < 10:
        return 'low_data'

    # Analyze engagement types
    engagement_types = {}
    for engagement in engagements:
        eng_type = engagement.engagement_type
        engagement_types[eng_type] = engagement_types.get(eng_type, 0) + 1

    total_engagements = sum(engagement_types.values())

    # Determine pattern
    if engagement_types.get('reflection_note', 0) / total_engagements > 0.3:
        return 'reflective'
    elif engagement_types.get('bookmark', 0) / total_engagements > 0.4:
        return 'collector'
    elif engagement_types.get('share', 0) / total_engagements > 0.2:
        return 'social'
    elif engagement_types.get('read_complete', 0) / total_engagements > 0.6:
        return 'thorough_reader'
    else:
        return 'casual_browser'