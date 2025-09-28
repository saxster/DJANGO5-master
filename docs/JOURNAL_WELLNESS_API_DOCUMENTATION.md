# Journal & Wellness System API Documentation

Complete API documentation for the IntelliWiz Journal & Wellness Education Platform. This system provides seamless integration between personal journaling with privacy controls and evidence-based wellness education with ML-powered personalization.

## 🔗 Base URLs

- **Web Interface**: `/journal/` and `/wellness/`
- **REST API**: `/api/v1/journal/` and `/api/v1/wellness/`
- **GraphQL**: `/api/graphql/` (includes journal and wellness schemas)

## 🛡️ Authentication & Privacy

All endpoints require user authentication. Privacy controls are enforced at the model level:

- **Private entries**: Only accessible by the owner
- **Shared entries**: Accessible by users in `sharing_permissions`
- **Wellbeing entries**: Always treated as private regardless of privacy_scope
- **Multi-tenant isolation**: Users only see data from their tenant

## 📖 Journal API Endpoints

### Journal Entry Management

#### `GET /api/v1/journal/entries/`
List user's journal entries with privacy filtering.

**Query Parameters:**
- `entry_types`: Filter by entry types (comma-separated)
- `date_from`, `date_to`: Date range filtering
- `mood_min`, `mood_max`: Mood rating range (1-10)
- `stress_min`, `stress_max`: Stress level range (1-5)
- `location`: Filter by location name
- `tags`: Filter by tags (comma-separated)

**Response:**
```json
{
  "count": 25,
  "next": "http://example.com/api/v1/journal/entries/?page=2",
  "previous": null,
  "results": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "title": "Morning Reflection",
      "subtitle": "Starting the day with intention",
      "entry_type": "PERSONAL_REFLECTION",
      "timestamp": "2024-01-15T08:30:00Z",
      "privacy_scope": "private",
      "mood_rating": 7,
      "stress_level": 2,
      "energy_level": 8,
      "location_site_name": "Main Office",
      "is_bookmarked": false,
      "wellbeing_summary": {
        "mood": "7/10",
        "stress": "2/5",
        "energy": "8/10"
      },
      "media_count": 2,
      "created_at": "2024-01-15T08:30:00Z"
    }
  ]
}
```

#### `POST /api/v1/journal/entries/`
Create new journal entry with automatic pattern analysis.

**Request Body:**
```json
{
  "title": "Stressful Equipment Issue",
  "content": "The main pump failed during morning inspection. Feeling stressed about potential delays.",
  "entry_type": "EQUIPMENT_MAINTENANCE",
  "mood_rating": 4,
  "stress_level": 4,
  "energy_level": 6,
  "stress_triggers": ["equipment failure", "time pressure"],
  "coping_strategies": ["deep breathing", "called supervisor"],
  "location_site_name": "Plant A - Building 2",
  "location_coordinates": {"lat": 40.7128, "lng": -74.0060},
  "tags": ["equipment", "maintenance", "urgent"],
  "privacy_scope": "private",
  "consent_given": true
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Stressful Equipment Issue",
  "user_name": "John Smith",
  "entry_type": "EQUIPMENT_MAINTENANCE",
  "mood_rating": 4,
  "stress_level": 4,
  "pattern_analysis": {
    "urgency_score": 6,
    "urgency_level": "high",
    "intervention_categories": ["stress_management", "equipment_stress_management"],
    "crisis_detected": false,
    "recommended_content_count": 3
  },
  "triggered_wellness_content": [
    {
      "id": "wellness-content-uuid",
      "title": "Equipment Failure Stress Management",
      "category": "stress_management",
      "delivery_context": "stress_response"
    }
  ],
  "created_at": "2024-01-15T10:45:00Z"
}
```

#### `GET /api/v1/journal/entries/{id}/`
Get detailed journal entry with media attachments.

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Morning Reflection",
  "subtitle": "Starting with gratitude",
  "content": "Grateful for my team's support during yesterday's challenges...",
  "entry_type": "GRATITUDE",
  "timestamp": "2024-01-15T08:30:00Z",
  "mood_rating": 8,
  "stress_level": 2,
  "energy_level": 9,
  "gratitude_items": [
    "Supportive team members",
    "Successful equipment repair",
    "Beautiful sunrise on way to work"
  ],
  "location_site_name": "Main Office",
  "tags": ["gratitude", "team", "morning"],
  "privacy_scope": "private",
  "media_attachments": [
    {
      "id": "media-uuid",
      "media_type": "PHOTO",
      "file_url": "https://example.com/media/journal_media/2024/01/15/sunrise.jpg",
      "caption": "Beautiful sunrise",
      "is_hero_image": true
    }
  ],
  "is_wellbeing_entry": true,
  "has_wellbeing_metrics": true,
  "created_at": "2024-01-15T08:30:00Z"
}
```

### Analytics & Insights

#### `GET /api/v1/journal/analytics/?days=30`
Get comprehensive wellbeing analytics.

**Query Parameters:**
- `days`: Analysis period (default: 30)
- `user_id`: Specific user (admin only)

**Response:**
```json
{
  "wellbeing_trends": {
    "mood_analysis": {
      "average_mood": 7.2,
      "mood_variability": 1.8,
      "trend_direction": "improving",
      "best_days": ["2024-01-12", "2024-01-13"],
      "challenging_days": ["2024-01-08", "2024-01-09"],
      "mood_patterns": {
        "Monday": 6.5,
        "Tuesday": 7.2,
        "Wednesday": 7.8,
        "Thursday": 7.1,
        "Friday": 8.2
      }
    },
    "stress_analysis": {
      "average_stress": 2.8,
      "trend_direction": "improving",
      "common_triggers": [
        {"trigger": "equipment issues", "frequency": 8},
        {"trigger": "deadline pressure", "frequency": 5}
      ],
      "effective_coping_strategies": [
        {"strategy": "deep breathing", "effectiveness": 0.8},
        {"strategy": "team discussion", "effectiveness": 0.7}
      ]
    }
  },
  "recommendations": [
    {
      "type": "stress_management",
      "priority": "medium",
      "title": "Equipment Stress Preparation",
      "description": "Your stress often correlates with equipment issues. Consider proactive strategies.",
      "action_items": [
        "Learn equipment troubleshooting basics",
        "Develop backup plans for common failures",
        "Practice stress management before equipment inspections"
      ],
      "predicted_impact": "high"
    }
  ],
  "overall_wellbeing_score": 7.8,
  "analysis_metadata": {
    "analysis_date": "2024-01-15T12:00:00Z",
    "data_points_analyzed": 28,
    "algorithm_version": "2.1.0"
  }
}
```

#### `POST /api/v1/journal/search/`
Advanced search with privacy filtering.

**Request Body:**
```json
{
  "query": "equipment maintenance stress",
  "entry_types": ["EQUIPMENT_MAINTENANCE", "STRESS_LOG"],
  "date_from": "2024-01-01T00:00:00Z",
  "date_to": "2024-01-31T23:59:59Z",
  "mood_min": 1,
  "mood_max": 5,
  "tags": ["equipment", "stress"],
  "sort_by": "relevance"
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "entry-uuid",
      "title": "Equipment Breakdown",
      "entry_type": "EQUIPMENT_MAINTENANCE",
      "timestamp": "2024-01-10T14:30:00Z",
      "mood_rating": 3,
      "stress_level": 5,
      "highlight": "Equipment <em>maintenance</em> caused significant <em>stress</em>"
    }
  ],
  "total_results": 15,
  "search_time_ms": 42,
  "facets": {
    "entry_types": {"EQUIPMENT_MAINTENANCE": 8, "STRESS_LOG": 7},
    "mood_ranges": {"1-3": 5, "4-6": 7, "7-10": 3}
  }
}
```

### Mobile Sync

#### `POST /api/v1/journal/sync/`
Sync journal entries with mobile client.

**Request Body:**
```json
{
  "entries": [
    {
      "mobile_id": "mobile-uuid-1",
      "title": "Mobile Entry",
      "entry_type": "FIELD_OBSERVATION",
      "timestamp": "2024-01-15T16:00:00Z",
      "mood_rating": 6,
      "version": 1,
      "sync_status": "pending_sync"
    }
  ],
  "last_sync_timestamp": "2024-01-14T12:00:00Z",
  "client_id": "mobile-client-uuid"
}
```

**Response:**
```json
{
  "sync_timestamp": "2024-01-15T16:30:00Z",
  "created_count": 1,
  "updated_count": 0,
  "conflict_count": 0,
  "created_entries": [...],
  "server_changes": [
    {
      "id": "server-entry-uuid",
      "title": "Server Updated Entry",
      "updated_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

## 🌟 Wellness Education API Endpoints

### Daily Wellness Tips

#### `GET /api/v1/wellness/daily-tip/`
Get personalized daily wellness tip.

**Query Parameters:**
- `preferred_category`: Specific wellness category
- `content_level`: Complexity level preference
- `exclude_recent`: Exclude recently viewed content (default: true)

**Response:**
```json
{
  "daily_tip": {
    "id": "wellness-uuid",
    "title": "5-Minute Stress Reset Technique",
    "summary": "Quick grounding technique for immediate stress relief",
    "content": "When work stress builds, try the 5-4-3-2-1 technique...",
    "category": "stress_management",
    "content_level": "quick_tip",
    "evidence_level": "peer_reviewed",
    "estimated_reading_time": 2,
    "action_tips": [
      "Practice during your next stressful moment",
      "Use between tasks for mental reset"
    ],
    "source_name": "CDC"
  },
  "personalization_metadata": {
    "user_patterns": {
      "current_mood": 6,
      "avg_stress": 3.2,
      "recent_stress_entries": 3
    },
    "selection_reason": "Selected for recent stress patterns",
    "effectiveness_prediction": 0.85
  },
  "next_tip_available_at": "2024-01-16T08:00:00Z"
}
```

### Contextual Content Delivery

#### `POST /api/v1/wellness/contextual/`
Get contextual wellness content based on journal entry.

**Request Body:**
```json
{
  "journal_entry": {
    "entry_type": "STRESS_LOG",
    "mood_rating": 3,
    "stress_level": 5,
    "stress_triggers": ["equipment failure"],
    "content": "Frustrated with repeated equipment breakdowns"
  },
  "user_context": {
    "work_shift": "day",
    "location_type": "field"
  },
  "max_content_items": 3
}
```

**Response:**
```json
{
  "immediate_content": [
    {
      "id": "content-uuid-1",
      "title": "Emergency Stress Relief for Equipment Failures",
      "category": "stress_management",
      "delivery_context": "stress_response",
      "evidence_level": "who_cdc",
      "action_tips": ["Take 5 deep breaths", "Step away from equipment"],
      "estimated_reading_time": 1
    }
  ],
  "follow_up_content": [
    {
      "id": "content-uuid-2",
      "title": "Building Resilience for Technical Challenges",
      "category": "workplace_health",
      "estimated_reading_time": 4
    }
  ],
  "urgency_analysis": {
    "urgency_score": 8,
    "urgency_level": "high",
    "intervention_categories": ["stress_management", "equipment_stress_management"],
    "delivery_timing": "immediate"
  }
}
```

### Personalized Recommendations

#### `GET /api/v1/wellness/personalized/?limit=5`
Get ML-powered personalized content recommendations.

**Query Parameters:**
- `limit`: Number of recommendations (1-20, default: 5)
- `categories`: Filter by categories (comma-separated)
- `exclude_viewed`: Exclude recently viewed (default: true)
- `diversity_enabled`: Enable diversity constraints (default: true)

**Response:**
```json
{
  "personalized_content": [
    {
      "content": {
        "id": "content-uuid",
        "title": "Mindful Equipment Checks",
        "category": "mindfulness",
        "content_level": "short_read",
        "workplace_specific": true
      },
      "personalization_score": 0.87,
      "recommendation_reason": "Matches your equipment work patterns and stress management needs",
      "predicted_effectiveness": 0.82,
      "estimated_value": 0.845
    }
  ],
  "personalization_metadata": {
    "user_profile_features": {
      "preferred_categories": ["stress_management", "workplace_health"],
      "avg_engagement_score": 4.2,
      "completion_rate": 0.78
    },
    "recommendation_algorithm": "hybrid_cf_cbf_v2.1",
    "model_confidence": 0.91,
    "diversity_score": 0.8
  }
}
```

### User Progress & Gamification

#### `GET /api/v1/wellness/progress/`
Get user's wellness progress and achievements.

**Response:**
```json
{
  "user_name": "John Smith",
  "current_streak": 12,
  "longest_streak": 28,
  "total_content_viewed": 45,
  "total_content_completed": 38,
  "completion_rate": 0.84,
  "category_progress_summary": {
    "total_progress": 156,
    "top_category": "Stress Management",
    "top_category_score": 42,
    "categories": {
      "Mental Health": 38,
      "Stress Management": 42,
      "Workplace Health": 35,
      "Physical Wellness": 28,
      "Mindfulness": 13
    }
  },
  "achievements_earned": ["week_streak", "content_explorer", "stress_master"],
  "next_milestone": {
    "type": "streak",
    "name": "Month Streak",
    "description": "Maintain wellness engagement for 30 consecutive days",
    "current_progress": 12,
    "target": 30,
    "progress_percentage": 40.0
  }
}
```

## 🔍 Advanced Features

### Pattern Recognition Integration

When journal entries are created, the system automatically:

1. **Analyzes urgency** using ML pattern recognition
2. **Triggers wellness content** if urgency score ≥ 2
3. **Delivers crisis intervention** if urgency score ≥ 6
4. **Updates user analytics** in background
5. **Tracks effectiveness** for ML optimization

### Privacy & Consent Management

#### `GET /api/v1/journal/privacy-settings/`
Get user's privacy preferences.

#### `PUT /api/v1/journal/privacy-settings/`
Update privacy preferences.

**Request Body:**
```json
{
  "default_privacy_scope": "private",
  "wellbeing_sharing_consent": false,
  "analytics_consent": true,
  "crisis_intervention_consent": true,
  "data_retention_days": 365,
  "auto_delete_enabled": false
}
```

### Content Interaction Tracking

#### `POST /api/v1/wellness/content/{id}/track_interaction/`
Track user interaction with wellness content.

**Request Body:**
```json
{
  "interaction_type": "completed",
  "time_spent_seconds": 180,
  "completion_percentage": 100,
  "user_rating": 5,
  "action_taken": true,
  "user_feedback": "Very helpful for managing equipment stress"
}
```

## 📊 Data Models Overview

### Journal Entry Fields

- **Core**: `title`, `content`, `entry_type`, `timestamp`
- **Wellbeing**: `mood_rating` (1-10), `stress_level` (1-5), `energy_level` (1-10)
- **Psychology**: `gratitude_items`, `affirmations`, `achievements`, `learnings`
- **Location**: `location_site_name`, `location_coordinates`, `team_members`
- **Performance**: `completion_rate`, `efficiency_score`, `quality_score`
- **Privacy**: `privacy_scope`, `consent_given`, `sharing_permissions`
- **Sync**: `mobile_id`, `version`, `sync_status`, `last_sync_timestamp`

### Wellness Content Fields

- **Content**: `title`, `summary`, `content`, `action_tips`, `key_takeaways`
- **Classification**: `category`, `delivery_context`, `content_level`, `evidence_level`
- **Targeting**: `tags`, `trigger_patterns`, `workplace_specific`, `field_worker_relevant`
- **Evidence**: `source_name`, `source_url`, `citations`, `last_verified_date`
- **Management**: `priority_score`, `frequency_limit_days`, `seasonal_relevance`

## 🚀 Integration Examples

### Frontend Integration Example (React/Vue)

```javascript
// Create journal entry with automatic wellness content
const createJournalEntry = async (entryData) => {
  const response = await fetch('/api/v1/journal/entries/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`
    },
    body: JSON.stringify(entryData)
  });

  const result = await response.json();

  // Handle triggered wellness content
  if (result.triggered_wellness_content?.length > 0) {
    showWellnessContent(result.triggered_wellness_content);
  }

  // Handle crisis detection
  if (result.pattern_analysis?.crisis_detected) {
    showCrisisSupport();
  }

  return result;
};

// Get personalized daily tip
const getDailyWellnessTip = async () => {
  const response = await fetch('/api/v1/wellness/daily-tip/', {
    headers: { 'Authorization': `Bearer ${authToken}` }
  });

  const data = await response.json();
  return data.daily_tip;
};

// Track wellness content interaction
const trackContentInteraction = async (contentId, interactionData) => {
  await fetch(`/api/v1/wellness/content/${contentId}/track_interaction/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`
    },
    body: JSON.stringify(interactionData)
  });
};
```

### Mobile Client Integration (Kotlin/Flutter)

```kotlin
// Mobile sync with conflict resolution
data class SyncRequest(
    val entries: List<JournalEntryDto>,
    val lastSyncTimestamp: String?,
    val clientId: String
)

suspend fun syncWithServer(entries: List<JournalEntry>): SyncResult {
    val syncRequest = SyncRequest(
        entries = entries.map { it.toDto() },
        lastSyncTimestamp = getLastSyncTimestamp(),
        clientId = getClientId()
    )

    val response = api.syncJournalEntries(syncRequest)

    // Handle conflicts
    response.conflicts.forEach { conflict ->
        handleSyncConflict(conflict)
    }

    // Update local database with server changes
    response.serverChanges.forEach { change ->
        updateLocalEntry(change)
    }

    return SyncResult(
        synced = response.createdCount + response.updatedCount,
        conflicts = response.conflictCount
    )
}
```

## 🔧 Deployment & Setup

### 1. Run Migrations
```bash
python manage.py migrate journal
python manage.py migrate wellness
```

### 2. Seed Wellness Content
```bash
python manage.py seed_wellness_content --tenant=your_tenant
```

### 3. Test Integration
```bash
python -m pytest apps/journal/tests/test_journal_integration.py -v
```

### 4. Verify API Endpoints
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/journal/entries/
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/wellness/daily-tip/
```

## 📈 Performance & Scaling

### Database Optimizations
- **GIN indexes** on JSON fields for fast tag/pattern searching
- **Composite indexes** for user+timestamp queries
- **Partial indexes** for active content and non-deleted entries
- **Connection pooling** for high-concurrency mobile sync

### Caching Strategy
- **Redis caching** for daily tips and personalized content
- **Content delivery caching** for high-traffic wellness materials
- **Analytics caching** for expensive wellbeing calculations
- **User profile caching** for ML recommendation speed

### Security Features
- **Multi-tenant isolation** at database and API level
- **Privacy scope enforcement** for all journal data access
- **Consent validation** for data processing and sharing
- **Audit logging** for all privacy-sensitive operations
- **Crisis intervention logging** for safety monitoring

## 🆘 Crisis Intervention Workflow

When crisis indicators are detected:

1. **Immediate Analysis**: Pattern recognition scores urgency ≥ 6
2. **Content Delivery**: High-evidence crisis support content delivered immediately
3. **Logging**: Crisis indicators logged for monitoring and follow-up
4. **Escalation**: Based on consent settings, appropriate personnel may be notified
5. **Follow-up**: System schedules follow-up content and check-ins

## 🎯 Success Metrics

Track system effectiveness through:
- **Engagement metrics**: Content completion rates, user ratings
- **Wellbeing improvements**: Mood trends, stress reduction patterns
- **Usage patterns**: Daily active users, streak maintenance
- **Content effectiveness**: Which content drives best outcomes
- **Crisis prevention**: Early intervention success rates

This API enables seamless integration between the Django backend intelligence and any frontend framework (React, Vue, Flutter, iOS, etc.) while maintaining enterprise-grade privacy, security, and performance standards.