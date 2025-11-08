# AI Admin Help System

**User-friendly, intelligent help system that explains Django admin features in simple, non-technical language.**

## Overview

The Admin Help System provides contextual, AI-powered assistance to help users understand and use the Django admin interface without technical jargon. Instead of "Playbooks" or "SLA Breach Predictor," users see friendly terms like "Quick Actions" and "Priority Alerts."

## Features

### 🎯 Core Capabilities

1. **Contextual Help** - Shows relevant help based on the current admin page
2. **Semantic Search** - Find help topics using natural language
3. **Quick Tips** - Personalized tips based on user role and experience level
4. **Usage Analytics** - Track which help topics are most viewed and helpful
5. **Multi-language Ready** - Uses Django's translation framework
6. **Tenant-Aware** - Supports multi-tenant deployments

### 💡 User-Friendly Language

**Before (Technical):**
- "Playbooks" → **After:** "Quick Actions"
- "Admin Views" → **After:** "My Saved Views"
- "SLA Breach Predictor" → **After:** "Priority Alerts"
- "Intelligent Routing" → **After:** "Smart Assignment"
- "360° Entity Timeline" → **After:** "Activity Timeline"
- "Unified Operations Queue" → **After:** "Team Dashboard"

## Installation

### 1. Create Database Migration

```bash
python manage.py makemigrations core
python manage.py migrate
```

### 2. Seed Initial Help Content

```bash
# Standard seeding
python manage.py seed_admin_help

# Clear existing and reseed
python manage.py seed_admin_help --clear-existing

# Preview what would be created
python manage.py seed_admin_help --dry-run
```

### 3. Include Help Widget in Admin Templates

Add to your base admin template (e.g., `templates/admin/base_site.html`):

```django
{% extends "admin/base.html" %}

{% block extrahead %}
    {{ block.super }}
    {% include "admin/includes/help_widget.html" %}
{% endblock %}
```

## Usage

### For End Users

#### Accessing Help

1. **Help Button**: Click the floating 💡 button in the bottom-right corner
2. **Tabs**:
   - **Quick Tips**: Personalized tips based on your role
   - **This Page**: Help specific to the current admin page
   - **Popular**: Most-viewed help topics
3. **Search**: Type any question or topic to find relevant help

#### Providing Feedback

- Click any help topic to view it (increments view count)
- Mark topics as helpful to improve recommendations

### For Administrators

#### Managing Help Topics

Navigate to **Django Admin → Core → Admin Help Topics**

**Available Actions:**
- ✏️ **Edit Topics**: Update content, difficulty level, or active status
- 📊 **View Analytics**: See usage statistics and popular topics
- 📤 **Bulk Import**: Import topics from CSV file
- 🔍 **Search**: Find topics by keyword or category

#### Creating New Help Topics

1. Go to **Admin → Core → Admin Help Topics → Add**
2. Fill in the required fields:
   - **Category**: Where this feature belongs (Command Center, Workflows, etc.)
   - **Feature Name**: User-friendly name (NO technical jargon!)
   - **Short Description**: 1-2 sentence summary
   - **Detailed Explanation**: Full explanation in plain English
3. Add optional fields:
   - **Use Cases**: Real-world examples (array of strings)
   - **Advantages**: Benefits and advantages (array of strings)
   - **How to Use**: Step-by-step instructions
   - **Video URL**: Link to tutorial video
   - **Keywords**: Search keywords and alternative terms
   - **Difficulty Level**: Beginner, Intermediate, or Advanced
4. Click **Save**

#### Bulk Import from CSV

1. Navigate to **Admin Help Topics**
2. Click **"Bulk Import"** button
3. Upload CSV file with these columns:
   ```csv
   category,feature_name,short_description,detailed_explanation,use_cases,advantages,how_to_use,video_url,keywords,difficulty_level
   command_center,Quick Actions,One-click shortcuts for common tasks,...,Use case 1|Use case 2,Advantage 1|Advantage 2,...,http://...,keyword1,keyword2,beginner
   ```
   - Use `|` to separate multiple use cases/advantages
   - Use `,` to separate keywords
4. Click **Upload**

## API Endpoints

The help widget uses these API endpoints (create them in your views):

```python
# apps/core/api/views/admin_help_views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.core.services.admin_help_service import AdminHelpService
from apps.core.models.admin_help import AdminHelpTopic

@api_view(['GET'])
def quick_tips(request):
    """Get personalized quick tips for the user."""
    topics = AdminHelpService.get_quick_tips(request.user, limit=3)
    return Response({
        'topics': [
            {
                'id': t.pk,
                'feature_name': t.feature_name,
                'short_description': t.short_description,
                'difficulty': t.get_difficulty_level_display(),
            }
            for t in topics
        ]
    })

@api_view(['GET'])
def contextual_help(request):
    """Get help for the current page."""
    page_url = request.GET.get('url', '')
    topics = AdminHelpService.get_contextual_help(request.user, page_url)
    return Response({
        'topics': [
            {
                'id': t.pk,
                'feature_name': t.feature_name,
                'short_description': t.short_description,
                'difficulty': t.get_difficulty_level_display(),
            }
            for t in topics
        ]
    })

@api_view(['GET'])
def popular_topics(request):
    """Get most popular help topics."""
    topics = AdminHelpService.get_popular_topics(limit=5)
    return Response({
        'topics': [
            {
                'id': t.pk,
                'feature_name': t.feature_name,
                'short_description': t.short_description,
                'view_count': t.view_count,
            }
            for t in topics
        ]
    })

@api_view(['GET'])
def search_help(request):
    """Search help topics."""
    query = request.GET.get('q', '')
    results = AdminHelpService.search_help(query, limit=10)
    return Response({'results': results})

@api_view(['POST'])
def track_view(request, topic_id):
    """Track when a user views a help topic."""
    try:
        topic = AdminHelpTopic.objects.get(pk=topic_id)
        AdminHelpService.track_help_usage(request.user, topic, action='view')
        return Response({'success': True})
    except AdminHelpTopic.DoesNotExist:
        return Response({'error': 'Topic not found'}, status=404)
```

**URL Configuration:**

```python
# intelliwiz_config/urls.py or apps/core/urls.py
from apps.core.api.views import admin_help_views

urlpatterns = [
    path('api/admin-help/quick-tips/', admin_help_views.quick_tips),
    path('api/admin-help/contextual/', admin_help_views.contextual_help),
    path('api/admin-help/popular/', admin_help_views.popular_topics),
    path('api/admin-help/search/', admin_help_views.search_help),
    path('api/admin-help/<int:topic_id>/view/', admin_help_views.track_view),
]
```

## Architecture

### Models

**AdminHelpTopic** (`apps/core/models/admin_help.py`)
- Stores help content with user-friendly language
- Full-text search using PostgreSQL SearchVector
- Tenant-aware for multi-tenant deployments
- Tracks view and helpful counts for analytics

### Services

**AdminHelpService** (`apps/core/services/admin_help_service.py`)
- `get_contextual_help()` - Returns help for current page
- `search_help()` - Semantic search using PostgreSQL FTS
- `get_quick_tips()` - Personalized tips based on user role
- `track_help_usage()` - Analytics tracking
- Caching with 1-hour TTL for performance

### Admin Interface

**AdminHelpTopicAdmin** (`apps/core/admin/admin_help_admin.py`)
- Rich admin interface with Unfold theme
- Bulk import from CSV
- Analytics dashboard
- Color-coded badges for category and difficulty

### Templates

**help_widget.html** (`templates/admin/includes/help_widget.html`)
- Floating help button with modal panel
- Tabbed interface (Quick Tips, This Page, Popular)
- Real-time search
- Responsive design

## Examples

### Example Help Topic Structure

```python
{
    'category': 'workflows',
    'feature_name': 'Quick Actions',
    'short_description': 'Do common tasks with just one click.',
    'detailed_explanation': '''Quick Actions are like shortcuts...''',
    'use_cases': [
        'Approve multiple requests at once',
        'Send daily report with one click',
    ],
    'advantages': [
        'Save time on repetitive tasks',
        'Reduce mistakes',
    ],
    'how_to_use': '''1. Find Quick Actions button\n2. Click Add New...''',
    'keywords': ['playbook', 'automation', 'shortcut'],
    'difficulty_level': 'beginner',
}
```

### Writing User-Friendly Content

**✅ DO:**
- Use simple, everyday language
- Explain like you're talking to a friend
- Use analogies and real-world examples
- Break down into clear steps
- Focus on benefits, not features

**❌ DON'T:**
- Use technical jargon or acronyms
- Assume the user knows the system
- Write long paragraphs without structure
- Use passive voice
- Hide benefits behind technical details

**Before:**
> "The intelligent routing engine utilizes ML algorithms to optimize task distribution across available resources based on skills matrix and capacity metrics."

**After:**
> "Smart Assignment automatically sends tasks to the right person based on their skills and availability - like having a good office manager who knows everyone's workload."

## Performance

- **Full-Text Search**: PostgreSQL SearchVector for fast semantic search
- **Caching**: 1-hour cache for popular queries
- **Query Optimization**: select_related() for tenant joins
- **Lazy Loading**: Help panel content loads on demand

## Security

- ✅ Tenant-aware: Users only see help for their tenant
- ✅ Permission checks on all API endpoints
- ✅ CSRF protection on POST requests
- ✅ Input sanitization on search queries
- ✅ SQL injection protection via ORM

## Analytics

Track help system effectiveness:

1. **View Analytics Dashboard**: Admin → Admin Help Topics → Analytics
2. **Metrics Available**:
   - Total topics and views
   - Average helpful rate
   - Popular topics by views
   - Usage by category
   - Search queries (if implemented)

## Troubleshooting

### Help Widget Not Showing

1. Check template includes help_widget.html
2. Verify JavaScript isn't blocked by CSP
3. Check browser console for API errors

### Search Not Working

1. Verify PostgreSQL full-text search extension installed
2. Run migration to create search_vector field
3. Re-save help topics to populate search_vector

### No Contextual Help

1. Check URL pattern matching in `_extract_category_from_url()`
2. Verify help topics exist for that category
3. Check tenant filtering isn't excluding topics

## Future Enhancements

- 🎥 Video tutorial embedding
- 🌐 Multi-language support beyond i18n
- 🤖 AI-powered answer generation for custom questions
- 📧 Email digest of new help topics
- 📱 Mobile-optimized help interface
- 🔗 Deep linking to specific admin pages from help
- 📊 Advanced analytics (A/B testing, user paths)
- 💬 User comments and ratings on help topics

## Contributing

When adding new help topics:

1. **Use the language guide** - Write for non-technical users
2. **Test with real users** - Get feedback from actual end users
3. **Add screenshots** - Visual aids help comprehension
4. **Keep it short** - Break long topics into multiple shorter ones
5. **Update keywords** - Include alternative terms users might search

## License

Part of the IntelliWiz Django platform. All rights reserved.

---

**Last Updated**: 2025-11-07
**Author**: AI Admin Help System Team
**Version**: 1.0.0
