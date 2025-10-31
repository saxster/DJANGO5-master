# Wellness Admin Module

Modular Django admin interface for the wellness application.

## Quick Reference

### Module Structure

```
apps/wellness/admin/
├── __init__.py                    # Package initialization (61 lines)
├── base.py                        # Shared utilities (168 lines)
├── content_admin.py               # Content management (232 lines)
├── progress_admin.py              # User progress (184 lines)
├── translation_admin.py           # Translations (270 lines)
└── wisdom_conversation_admin.py   # Conversations (565 lines)
```

### Admin Classes

| Admin Class | Module | Model | Purpose |
|------------|--------|-------|---------|
| `WellnessContentAdmin` | content_admin | WellnessContent | Education content library |
| `WellnessContentInteractionAdmin` | content_admin | WellnessContentInteraction | User engagement tracking |
| `WellnessUserProgressAdmin` | progress_admin | WellnessUserProgress | Progress & gamification |
| `WisdomConversationTranslationAdmin` | translation_admin | WisdomConversationTranslation | AI translations |
| `TranslationQualityFeedbackAdmin` | translation_admin | TranslationQualityFeedback | Translation feedback |
| `ConversationThreadAdmin` | wisdom_conversation_admin | ConversationThread | Conversation threads |
| `WisdomConversationAdmin` | wisdom_conversation_admin | WisdomConversation | Wisdom conversations |
| `ConversationEngagementAdmin` | wisdom_conversation_admin | ConversationEngagement | Engagement tracking |
| `ConversationBookmarkAdmin` | wisdom_conversation_admin | ConversationBookmark | User bookmarks |

### Usage

#### Importing Admin Classes

```python
# Backward compatible imports
from apps.wellness.admin import (
    WellnessContentAdmin,
    WellnessUserProgressAdmin,
    WisdomConversationTranslationAdmin,
)

# Direct module imports
from apps.wellness.admin.content_admin import WellnessContentAdmin
from apps.wellness.admin.progress_admin import WellnessUserProgressAdmin
from apps.wellness.admin.translation_admin import WisdomConversationTranslationAdmin
```

#### Creating New Admin Classes

```python
from django.contrib import admin
from apps.wellness.admin.base import WellnessBaseModelAdmin
from unfold.decorators import display

@admin.register(MyModel)
class MyModelAdmin(WellnessBaseModelAdmin):
    """Admin for MyModel with Unfold theme"""

    list_display = ['name', 'status_badge', 'user_link', 'created_display']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'description']
    list_select_related = ['user', 'tenant']

    @display(description='Status', label=True)
    def status_badge(self, obj):
        return obj.get_status_display()

    @display(description='User')
    def user_link(self, obj):
        return self.user_display_link(obj.user)
```

### Base Utilities

#### WellnessBaseModelAdmin

Base class for all wellness admin interfaces.

**Features:**
- Inherits from `apps.core.admin.IntelliWizModelAdmin` (Unfold theme)
- Automatic query optimization (select_related for tenant, user, created_by)
- List pagination (25 items per page)

#### WellnessAdminMixin

Mixin providing common display helpers.

**Methods:**

```python
# Display user link
self.user_display_link(user, short_name=False)
# Returns: <a href="/admin/peoples/people/123/">John Doe</a>

# Display percentage with color coding
self.percentage_display(0.75, decimal_places=1)
# Returns: <span style="color: green;">75.0%</span>

# Display count badge
self.count_badge(5, label='items', zero_text='None')
# Returns: <span class="badge badge-primary">5 items</span>

# Display status with color
self.status_color_display('active', status_label='Active')
# Returns: <span style="color: green; font-weight: bold;">Active</span>
```

### Bulk Actions

#### Content Admin
- `mark_needs_verification` - Flag content for verification
- `mark_verified` - Mark content as recently verified
- `activate_content` - Enable content delivery
- `deactivate_content` - Disable content delivery

#### Progress Admin
- `reset_streak` - Reset user streak counters
- `award_bonus_points` - Award 50 bonus points
- `send_engagement_reminder` - Send reminders to inactive users

#### Translation Admin
- `mark_for_review` - Flag for human review
- `mark_as_reviewed` - Mark as reviewed
- `extend_cache_expiry` - Extend by 30 days
- `refresh_translation` - Queue translation refresh
- `bulk_quality_upgrade` - Upgrade high-confidence translations

#### Feedback Admin
- `mark_as_helpful` - Mark feedback as helpful
- `mark_as_not_helpful` - Mark feedback as not helpful

### Query Optimization

All admin classes use optimized queries:

```python
# Automatic select_related
list_select_related = ('user', 'tenant', 'created_by')

# Manual prefetch_related
def get_queryset(self, request):
    qs = super().get_queryset(request)
    return qs.prefetch_related('interactions', 'translations')
```

### Display Decorators

Use `@display` decorator from Unfold for enhanced displays:

```python
from unfold.decorators import display

@display(description='Status', label=True)
def status_badge(self, obj):
    """Display status as badge"""
    return obj.get_status_display()

@display(description='Created', ordering='created_at')
def created_display(self, obj):
    """Display creation date"""
    return obj.created_at.strftime('%Y-%m-%d')
```

### Search & Filters

#### Search Fields
Define comprehensive search across text fields:

```python
search_fields = ('title', 'content', 'user__peoplename', 'user__loginid')
```

#### List Filters
Add logical filters for quick access:

```python
list_filter = (
    'status',
    'category',
    'created_at',
    ('tenant', admin.RelatedOnlyFieldListFilter),
)
```

## File Size Compliance

| File | Lines | CLAUDE.md Status |
|------|-------|------------------|
| `__init__.py` | 61 | ✅ PASS |
| `base.py` | 168 | ✅ PASS |
| `progress_admin.py` | 184 | ✅ PASS |
| `content_admin.py` | 232 | ⚠️ +32 (justified) |
| `translation_admin.py` | 270 | ⚠️ +70 (justified) |
| `wisdom_conversation_admin.py` | 565 | ℹ️ Pre-existing |

**Note:** Files exceeding 200 lines contain multiple related admin classes with complex analytics. Splitting would break cohesion.

## Best Practices

1. **Always inherit from WellnessBaseModelAdmin**
   ```python
   class MyAdmin(WellnessBaseModelAdmin):
       pass
   ```

2. **Use @display decorator for display methods**
   ```python
   @display(description='Name', label=True)
   def name_display(self, obj):
       return obj.name
   ```

3. **Optimize queries with select_related**
   ```python
   list_select_related = ('user', 'tenant')
   ```

4. **Add comprehensive search fields**
   ```python
   search_fields = ('name', 'description', 'user__peoplename')
   ```

5. **Provide useful bulk actions**
   ```python
   actions = ['activate_items', 'deactivate_items']
   ```

## Migration from Old Admin

If updating from pre-refactored admin.py:

```python
# Old (still works)
from apps.wellness.admin import WellnessContentAdmin

# New (recommended)
from apps.wellness.admin.content_admin import WellnessContentAdmin

# Or use base class for new admins
from apps.wellness.admin.base import WellnessBaseModelAdmin
```

## Documentation

- **REFACTORING_SUMMARY.md** - Detailed refactoring documentation
- **CLAUDE.md** - Project-wide architectural guidelines
- **apps/core/admin/base_admin.py** - Core admin base classes

## Support

For questions or issues:
1. Check REFACTORING_SUMMARY.md for detailed documentation
2. Review existing admin classes for patterns
3. Consult CLAUDE.md for architectural guidelines

---

**Last Updated:** October 12, 2025
**Maintainer:** Development Team
**CLAUDE.md Compliance:** Mostly compliant (justified overages documented)
