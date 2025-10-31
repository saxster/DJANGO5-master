"""
Wellness App for IntelliWiz - Evidence-based wellness intervention system

ARCHITECTURE OVERVIEW:
======================

The Wellness module serves as an **aggregator and intelligent delivery system** for
wellbeing support content, consuming journal entries from Kotlin mobile frontends.

DATA FLOW:
----------
1. Kotlin Mobile Client → Journal Entry (mood/stress/energy ratings)
2. Backend REST API → JournalEntry model (apps/journal/)
3. Pattern Analysis → JournalAnalyticsService analyzes urgency (0-10 scale)
4. Content Delivery → WellnessContent delivered contextually based on urgency
5. Interaction Tracking → User engagement monitored for effectiveness
6. Admin Aggregation → Site admins view anonymized wellbeing trends

KEY COMPONENTS:
---------------
- **WellnessContent**: Evidence-based content library (WHO/CDC compliant)
- **WellnessContentInteraction**: Tracks user engagement and effectiveness
- **WellnessUserProgress**: Gamification (streaks, achievements, scores)
- **JournalAnalyticsService**: Real-time pattern analysis and urgency scoring

ADMIN INTERFACES:
-----------------
Site administrators can view aggregated metrics through:
- Django Admin: /admin/wellness/wellnesscontent/
- Analytics Dashboard: /journal/analytics/
- Content Performance: /admin/wellness/wellnesscontentinteraction/
- User Progress: /admin/wellness/wellnessuserprogress/

PRIVACY & SECURITY:
-------------------
- Wellbeing data defaults to 'private' privacy scope
- Consent required for crisis interventions
- Analytics only shows aggregated/anonymized data unless consent given
- GDPR compliant with right to access/deletion

API ENDPOINTS:
--------------
- POST /api/wellness/contextual/     - Get contextual wellness content
- GET  /api/wellness/daily-tip/      - Daily personalized tip
- GET  /api/wellness/progress/       - User gamification progress
- POST /api/wellness/content/{id}/track_interaction/  - Track engagement

MOBILE INTEGRATION:
-------------------
Expected data from Kotlin clients (via /api/journal/entries/):
{
  "entry_type": "MOOD_CHECK_IN",
  "mood_rating": 1-10,
  "stress_level": 1-5,
  "energy_level": 1-10,
  "content": "Journal text",
  "stress_triggers": ["list", "of", "triggers"]
}

For complete documentation, see:
- docs/features/DOMAIN_SPECIFIC_SYSTEMS.md (Wellness & Journal System)
- apps/journal/services/analytics_service.py (Pattern analysis)
- apps/wellness/views.py (Content delivery logic)
"""