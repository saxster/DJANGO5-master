# Journal App

## Purpose

Employee wellbeing tracking and personal reflection system with real-time analytics and evidence-based wellness content delivery.

## Key Features

- **Mood Tracking** - Daily mood, stress, and energy level monitoring (1-10 scales)
- **Positive Psychology** - Gratitude journals, affirmations, daily goals
- **Work Reflection** - End-of-shift reflections with performance metrics
- **Privacy Controls** - Granular consent management and data sharing permissions
- **Offline Sync** - Mobile-first with conflict resolution for offline entries
- **Real-Time Analytics** - Wellbeing trend analysis with pattern detection
- **Content Delivery** - Context-aware wellness content based on journal patterns
- **Multi-Tenant Isolation** - Secure tenant-aware data storage

---

## Architecture

### Models Overview

**Core Model:**
- `JournalEntry` - Complete journal entry with wellbeing metrics
  - Entry metadata (type, title, content, timestamp)
  - Privacy controls (scope, consent, sharing)
  - Wellbeing metrics (mood, stress, energy)
  - Positive psychology fields (gratitude, affirmations, goals)
  - Work context (location, team, performance)
  - Sync support (mobile_id, version, conflict resolution)

**Related Models:**
- `JournalMedia` - Photo/video attachments for entries
- `JournalPrivacyConsent` - User consent tracking for data processing

**Enums:**
- `JournalEntryType` - Entry type classification
- `JournalPrivacyScope` - Privacy level (PRIVATE, SHARED, MANAGER, etc.)
- `JournalSyncStatus` - Sync state (SYNCED, PENDING, CONFLICT)

**See:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/models/` for complete model definitions

### Database Schema

```
JournalEntry (Main Model)
  ├─ user (FK → People)
  ├─ tenant (FK → Tenant)
  ├─ media (1:M → JournalMedia)
  └─ privacy_consent (1:1 → JournalPrivacyConsent)
```

### Key Indexes

```python
indexes = [
    models.Index(fields=['user', '-timestamp']),  # User timeline
    models.Index(fields=['entry_type', '-timestamp']),  # Type filtering
    models.Index(fields=['privacy_scope', 'user']),  # Privacy queries
    models.Index(fields=['mood_rating', 'timestamp']),  # Mood trends
    models.Index(fields=['stress_level', 'timestamp']),  # Stress analysis
    models.Index(fields=['sync_status', 'mobile_id']),  # Sync resolution
]
```

---

## API Endpoints

### Journal Entries

```
GET    /api/journal/entries/                  # List entries
POST   /api/journal/entries/                  # Create entry
GET    /api/journal/entries/{id}/             # Entry details
PATCH  /api/journal/entries/{id}/             # Update entry
DELETE /api/journal/entries/{id}/             # Soft delete entry
```

### Analytics

```
GET    /api/journal/analytics/mood-trends/    # Mood trend analysis
GET    /api/journal/analytics/stress-patterns/ # Stress pattern detection
GET    /api/journal/analytics/wellbeing-score/ # Overall wellbeing score
GET    /api/journal/analytics/gratitude-insights/ # Gratitude analysis
```

### Wellness Content

```
GET    /api/wellness/content/                 # Context-aware content
GET    /api/wellness/content/daily-tip/       # Daily wellness tip
GET    /api/wellness/content/stress-response/ # Stress management content
```

### Admin Dashboard

```
GET    /journal/analytics/                    # Aggregated wellbeing dashboard
GET    /journal/analytics/trends/             # Trend visualization
GET    /journal/analytics/alerts/             # Wellbeing alerts
```

---

## Usage Examples

### Creating a Journal Entry (Kotlin Mobile)

```kotlin
// Mood check-in from mobile
val entry = JournalEntryCreate(
    entryType = "MOOD_CHECK_IN",
    title = "Morning Check-in",
    content = "Feeling energized and ready for the day",
    timestamp = Instant.now(),
    moodRating = 8,
    stressLevel = 2,
    energyLevel = 9,
    privacyScope = "PRIVATE",
    consentGiven = true
)

val response = journalApi.createEntry(entry)
```

### Creating a Gratitude Journal (Python)

```python
from apps.journal.models import JournalEntry
from apps.journal.models.enums import JournalEntryType, JournalPrivacyScope

entry = JournalEntry.objects.create(
    user=request.user,
    tenant=request.user.client,
    entry_type=JournalEntryType.GRATITUDE,
    title="Things I'm Grateful For",
    content="Today was a great day!",
    timestamp=timezone.now(),
    gratitude_items=[
        "Supportive team members",
        "Good health",
        "Meaningful work"
    ],
    privacy_scope=JournalPrivacyScope.PRIVATE,
    consent_given=True
)
```

### Work Reflection Entry

```python
entry = JournalEntry.objects.create(
    user=request.user,
    tenant=request.user.client,
    entry_type=JournalEntryType.END_OF_SHIFT_REFLECTION,
    title="End of Shift - November 12",
    content="Productive day with good team collaboration",
    timestamp=timezone.now(),

    # Performance metrics
    completion_rate=0.95,
    efficiency_score=8.5,
    quality_score=9.0,
    items_processed=45,

    # Work context
    location_site_name="Downtown Office",
    team_members=["Alice", "Bob", "Charlie"],

    # Wellbeing
    mood_rating=7,
    stress_level=3,
    energy_level=6,

    # Reflection
    achievements=[
        "Completed project milestone",
        "Resolved customer issue"
    ],
    learnings=[
        "Better time management reduces stress",
        "Short breaks improve focus"
    ],

    privacy_scope=JournalPrivacyScope.AGGREGATE_ONLY
)
```

### Analyzing Wellbeing Trends

```python
from apps.journal.services.analytics_service import JournalAnalyticsService

# Get user's wellbeing trends
trends = JournalAnalyticsService.analyze_wellbeing_trends(
    user=request.user,
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now()
)

# Results
print(f"Average mood: {trends['mood']['average']}")
print(f"Stress trend: {trends['stress']['trend']}")  # 'improving', 'stable', 'declining'
print(f"Energy pattern: {trends['energy']['pattern']}")
```

### Delivering Context-Aware Content

```python
from apps.wellness.services.content_delivery import WellnessContentDeliveryService

# Analyze recent entries and deliver appropriate content
content = WellnessContentDeliveryService.get_contextual_content(
    user=request.user,
    context='stress_response'
)

# Content delivered based on patterns:
# - High stress → stress management techniques
# - Low mood → mood support content
# - Low energy → energy boost tips
```

---

## Privacy and Security

### Privacy Scopes

```python
class JournalPrivacyScope(models.TextChoices):
    PRIVATE = 'private', 'Private (user only)'
    SHARED = 'shared', 'Shared (specific users)'
    MANAGER = 'manager', 'Manager Access'
    TEAM = 'team', 'Team Access'
    AGGREGATE_ONLY = 'aggregate_only', 'Aggregated Analytics Only'
```

### Consent Management

- **Explicit Consent:** Required for data processing
- **Granular Control:** User chooses privacy scope per entry
- **Audit Trail:** Consent timestamp tracked
- **Revocable:** Users can change privacy settings

### Access Control

```python
def can_user_access(self, user):
    """Check if user can access this journal entry"""
    # Owner always has access
    if user.id == self.user.id:
        return True

    # Check privacy scope
    if self.privacy_scope == JournalPrivacyScope.PRIVATE:
        return False
    elif self.privacy_scope == JournalPrivacyScope.SHARED:
        return user.id in self.sharing_permissions
    elif self.privacy_scope == JournalPrivacyScope.MANAGER:
        return user.is_manager_of(self.user)

    return False
```

### Multi-Tenant Isolation

```python
# All queries automatically filtered by tenant
entries = JournalEntry.objects.all()  # Only user's tenant entries

# Explicit filtering
entries = JournalEntry.objects.filter(
    user=request.user,
    tenant=request.user.client
)
```

---

## Offline Sync and Conflict Resolution

### Mobile Sync Strategy

1. **Client-Side ID:** Mobile generates UUID for offline entries
2. **Version Tracking:** Version field incremented on updates
3. **Sync Status:** Tracks sync state (SYNCED, PENDING, CONFLICT)
4. **Conflict Detection:** Server compares version numbers
5. **Resolution:** Last-write-wins with user override option

### Sync Flow

```python
# Mobile creates offline entry
entry = {
    'mobile_id': 'uuid-generated-on-mobile',
    'version': 1,
    'sync_status': 'PENDING',
    'content': 'Offline reflection...'
}

# Sync to server when online
response = sync_journal_entries([entry])

# Server detects conflict if version mismatch
if response['conflicts']:
    # User chooses resolution strategy
    resolve_conflict(
        mobile_entry=entry,
        server_entry=response['conflicts'][0],
        strategy='keep_mobile'  # or 'keep_server', 'merge'
    )
```

---

## Analytics and Insights

### Wellbeing Metrics

**Tracked Metrics:**
- Mood rating (1-10 scale)
- Stress level (1-5 scale)
- Energy level (1-10 scale)
- Gratitude frequency
- Achievement tracking
- Challenge identification

**Analytics:**
- 7-day moving average
- Trend detection (improving/declining)
- Pattern recognition
- Anomaly detection
- Correlation analysis

### Dashboard Views

**Admin Dashboard:**
- Aggregated wellbeing scores (anonymized)
- Trend visualization
- Risk identification (high stress, low mood patterns)
- Intervention recommendations

**User Dashboard:**
- Personal wellbeing timeline
- Mood calendar heatmap
- Gratitude insights
- Progress tracking

---

## Integration with Wellness App

The journal and wellness apps work together as an **aggregation system**:

1. **Journal App:** Collects wellbeing data from mobile
2. **Analytics Service:** Analyzes patterns in real-time
3. **Wellness App:** Delivers evidence-based content
4. **Feedback Loop:** Content effectiveness tracked

```python
# Flow
JournalEntry (user input)
  → JournalAnalyticsService (pattern detection)
    → WellnessContentDeliveryService (content selection)
      → WellnessContent (evidence-based recommendations)
        → UserProgress (engagement tracking)
```

---

## Testing

### Running Tests

```bash
# All journal tests
pytest apps/journal/tests/ -v

# Specific test module
pytest apps/journal/tests/test_analytics_service.py -v

# With coverage
pytest apps/journal/tests/ --cov=apps/journal --cov-report=html
```

### Test Factories

```python
from apps.journal.factories import (
    JournalEntryFactory,
    MoodCheckInFactory,
    GratitudeEntryFactory,
    StressLogFactory,
    WorkReflectionFactory
)

# Create mood check-in
entry = MoodCheckInFactory.create(
    user=user,
    mood_rating=8,
    stress_level=2
)

# Create gratitude entry
gratitude = GratitudeEntryFactory.create(
    user=user,
    gratitude_items=["Health", "Family", "Work"]
)
```

---

## Configuration

### Settings

```python
# intelliwiz_config/settings/journal.py

JOURNAL_SETTINGS = {
    'MAX_ENTRIES_PER_DAY': 10,
    'ANALYTICS_RETENTION_DAYS': 365,
    'SYNC_CONFLICT_RETENTION_DAYS': 30,
    'DEFAULT_PRIVACY_SCOPE': 'private',
}

# Celery tasks
CELERY_BEAT_SCHEDULE = {
    'analyze-wellbeing-patterns': {
        'task': 'apps.journal.tasks.analyze_wellbeing_patterns',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}
```

---

## Related Apps

- [wellness](../wellness/README.md) - Wellness content delivery
- [peoples](../peoples/README.md) - User authentication
- [attendance](../attendance/README.md) - Work schedule integration

---

## Troubleshooting

### Common Issues

**Issue:** Entries not syncing from mobile
**Solution:** Check sync_status field and mobile_id uniqueness

**Issue:** Privacy consent not recorded
**Solution:** Ensure consent_given=True and consent_timestamp set

**Issue:** Analytics dashboard empty
**Solution:** Verify aggregation queries use AGGREGATE_ONLY scope

**Issue:** Conflict resolution fails
**Solution:** Check version field consistency between mobile and server

---

**Last Updated:** November 12, 2025
**Maintainers:** Wellbeing Team
**Contact:** wellbeing-team@example.com
