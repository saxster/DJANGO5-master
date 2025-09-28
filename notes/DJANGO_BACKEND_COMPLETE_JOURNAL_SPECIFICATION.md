# COMPLETE DJANGO BACKEND SPECIFICATION
## IntelliWiz Journal & Wellness Education Platform Implementation

**FOR DJANGO5 BACKEND LLM: This document specifies EXACTLY what to implement for the complete journal system with wellness education integration.**

---

## 🔍 CURRENT SYSTEM ANALYSIS & MIGRATION REQUIREMENTS

### Critical Issues in Current Kotlin Implementation

**🚨 MAJOR ARCHITECTURAL PROBLEMS:**
1. **No Persistence**: Journal entries only stored in memory (`FeedManager.StateFlow`)
2. **No Privacy Controls**: Wellbeing data treated as regular work data
3. **Client-Side Analytics**: Complex calculations on mobile (battery drain)
4. **Limited Search**: Stubbed implementation with no real functionality
5. **Missing Positive Psychology**: No evidence-based wellbeing practices
6. **No Sync Infrastructure**: Offline-first design incomplete

### What Must Move from Kotlin to Django Backend

**🧠 Intelligence & Processing (MOVE TO DJANGO):**
- Journal analytics and insights generation
- Mood/stress/energy trend calculations
- Pattern recognition algorithms
- Recommendation engines
- Search algorithms and indexing
- Complex aggregations and statistical analysis
- ML-based personalization
- Wellbeing correlation analysis

**📱 What Stays in Kotlin (UI ONLY):**
- Content presentation and user interaction
- Offline caching and basic sync queue
- Media capture and display
- Simple state management for UI

---

## 🗃️ COMPREHENSIVE DATABASE SCHEMA

### Core Journal Models (Enhanced from Current Kotlin Implementation)

```python
# apps/journal/models.py

class JournalPrivacyScope(models.TextChoices):
    PRIVATE = 'private', 'Private - Only visible to me'
    MANAGER = 'manager', 'Manager - Visible to my direct manager'
    TEAM = 'team', 'Team - Visible to my team'
    AGGREGATE_ONLY = 'aggregate', 'Aggregate - Anonymous statistics only'
    SHARED = 'shared', 'Shared - Visible to selected stakeholders'

class JournalEntryType(models.TextChoices):
    # Work-related entries (EXISTING)
    SITE_INSPECTION = 'site_inspection', 'Site Inspection'
    EQUIPMENT_MAINTENANCE = 'equipment_maintenance', 'Equipment Maintenance'
    SAFETY_AUDIT = 'safety_audit', 'Safety Audit'
    TRAINING_COMPLETED = 'training_completed', 'Training Completed'
    PROJECT_MILESTONE = 'project_milestone', 'Project Milestone'
    TEAM_COLLABORATION = 'team_collaboration', 'Team Collaboration'
    CLIENT_INTERACTION = 'client_interaction', 'Client Interaction'
    PROCESS_IMPROVEMENT = 'process_improvement', 'Process Improvement'
    DOCUMENTATION_UPDATE = 'documentation_update', 'Documentation Update'
    FIELD_OBSERVATION = 'field_observation', 'Field Observation'
    QUALITY_NOTE = 'quality_note', 'Quality Note'
    INVESTIGATION_NOTE = 'investigation_note', 'Investigation Note'
    SAFETY_CONCERN = 'safety_concern', 'Safety Concern'

    # Wellbeing entries (NEW - from Kotlin implementation)
    PERSONAL_REFLECTION = 'personal_reflection', 'Personal Reflection'
    MOOD_CHECK_IN = 'mood_check_in', 'Mood Check-in'
    GRATITUDE = 'gratitude', 'Gratitude Entry'
    THREE_GOOD_THINGS = 'three_good_things', '3 Good Things'
    DAILY_AFFIRMATIONS = 'daily_affirmations', 'Daily Affirmations'
    STRESS_LOG = 'stress_log', 'Stress Log'
    STRENGTH_SPOTTING = 'strength_spotting', 'Strength Spotting'
    REFRAME_CHALLENGE = 'reframe_challenge', 'Reframe Challenge'
    DAILY_INTENTION = 'daily_intention', 'Daily Intention'
    END_OF_SHIFT_REFLECTION = 'end_of_shift_reflection', 'End of Shift Reflection'
    BEST_SELF_WEEKLY = 'best_self_weekly', 'Best Self Weekly'

class JournalSyncStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PENDING_SYNC = 'pending_sync', 'Pending Sync'
    SYNCED = 'synced', 'Synced'
    SYNC_ERROR = 'sync_error', 'Sync Error'
    PENDING_DELETE = 'pending_delete', 'Pending Delete'

class JournalEntry(models.Model):
    """
    COMPLETE journal entry model - ALL functionality from Kotlin moved here
    Replaces the memory-only FeedManager implementation
    """

    # Core identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey('core.User', on_delete=models.CASCADE)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)

    # Entry metadata
    entry_type = models.CharField(max_length=50, choices=JournalEntryType.choices)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    timestamp = models.DateTimeField()
    duration_minutes = models.IntegerField(null=True, blank=True)

    # Privacy and consent controls (CRITICAL - was missing in Kotlin)
    privacy_scope = models.CharField(max_length=20, choices=JournalPrivacyScope.choices, default='private')
    consent_given = models.BooleanField(default=False)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    sharing_permissions = models.JSONField(default=list)  # User IDs who can access

    # Enhanced wellbeing data (MOVED from Kotlin entities)
    mood_rating = models.IntegerField(null=True, blank=True)  # 1-10 scale
    mood_description = models.CharField(max_length=100, blank=True)
    stress_level = models.IntegerField(null=True, blank=True)  # 1-5 scale
    energy_level = models.IntegerField(null=True, blank=True)  # 1-10 scale
    stress_triggers = models.JSONField(default=list)
    coping_strategies = models.JSONField(default=list)

    # Positive psychology fields (NEW - from Kotlin JournalEntryFactory)
    gratitude_items = models.JSONField(default=list)
    daily_goals = models.JSONField(default=list)
    affirmations = models.JSONField(default=list)
    achievements = models.JSONField(default=list)
    learnings = models.JSONField(default=list)
    challenges = models.JSONField(default=list)

    # Location and work context
    location_site_name = models.CharField(max_length=200, blank=True)
    location_address = models.TextField(blank=True)
    location_coordinates = models.JSONField(null=True, blank=True)  # {"lat": 0.0, "lng": 0.0}
    location_area_type = models.CharField(max_length=100, blank=True)
    team_members = models.JSONField(default=list)

    # Searchable fields and categorization
    tags = models.JSONField(default=list)
    priority = models.CharField(max_length=20, blank=True)
    severity = models.CharField(max_length=20, blank=True)

    # Work performance metrics
    completion_rate = models.FloatField(null=True, blank=True)
    efficiency_score = models.FloatField(null=True, blank=True)
    quality_score = models.FloatField(null=True, blank=True)
    items_processed = models.IntegerField(null=True, blank=True)

    # Entry state management
    is_bookmarked = models.BooleanField(default=False)
    is_draft = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    # Sync and versioning (for offline mobile clients)
    sync_status = models.CharField(max_length=20, choices=JournalSyncStatus.choices, default='synced')
    mobile_id = models.UUIDField(null=True, blank=True)  # Client-generated ID for sync
    version = models.IntegerField(default=1)  # For conflict resolution
    last_sync_timestamp = models.DateTimeField(null=True, blank=True)

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict)  # Flexible additional data

    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['entry_type', 'user']),
            models.Index(fields=['privacy_scope', 'user']),
            models.Index(fields=['mood_rating', 'timestamp']),
            models.Index(fields=['stress_level', 'timestamp']),
            models.Index(fields=['sync_status', 'mobile_id']),
            models.Index(fields=['is_deleted', 'is_draft']),
            models.Index(fields=['tenant', 'timestamp']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(mood_rating__gte=1, mood_rating__lte=10) | models.Q(mood_rating__isnull=True),
                name='valid_mood_rating'
            ),
            models.CheckConstraint(
                check=models.Q(stress_level__gte=1, stress_level__lte=5) | models.Q(stress_level__isnull=True),
                name='valid_stress_level'
            ),
        ]

class JournalMediaAttachment(models.Model):
    """Media attachments for journal entries with sync support"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='media')

    # Media details
    media_type = models.CharField(max_length=20)  # PHOTO, VIDEO, DOCUMENT, AUDIO
    file = models.FileField(upload_to='journal_media/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()

    # Display properties
    caption = models.TextField(blank=True)
    display_order = models.IntegerField(default=0)
    is_hero_image = models.BooleanField(default=False)

    # Sync management for mobile clients
    mobile_id = models.UUIDField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, choices=JournalSyncStatus.choices, default='synced')
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['journal_entry', 'display_order']),
            models.Index(fields=['media_type']),
            models.Index(fields=['sync_status']),
        ]

class JournalPrivacySettings(models.Model):
    """User privacy preferences for journal data (CRITICAL - was missing)"""
    user = models.OneToOneField('core.User', on_delete=models.CASCADE)

    # Default privacy preferences
    default_privacy_scope = models.CharField(
        max_length=20,
        choices=JournalPrivacyScope.choices,
        default='private'
    )

    # Granular consent controls
    wellbeing_sharing_consent = models.BooleanField(default=False)
    manager_access_consent = models.BooleanField(default=False)
    analytics_consent = models.BooleanField(default=False)
    crisis_intervention_consent = models.BooleanField(default=False)

    # Data retention preferences
    data_retention_days = models.IntegerField(default=365)
    auto_delete_enabled = models.BooleanField(default=False)

    # Audit trail
    consent_timestamp = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    def get_effective_privacy_scope(self, entry_type):
        """Determine effective privacy scope based on entry type and consent"""
        if entry_type in ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']:
            return 'private'  # Always private for sensitive wellbeing data
        return self.default_privacy_scope
```

### Wellness Education Models (Integrated with Journal System)

```python
# apps/wellness/models.py

class WellnessContentCategory(models.TextChoices):
    MENTAL_HEALTH = 'mental_health', 'Mental Health'
    PHYSICAL_WELLNESS = 'physical_wellness', 'Physical Wellness'
    WORKPLACE_HEALTH = 'workplace_health', 'Workplace Health'
    SUBSTANCE_AWARENESS = 'substance_awareness', 'Substance Awareness'
    PREVENTIVE_CARE = 'preventive_care', 'Preventive Care'
    SLEEP_HYGIENE = 'sleep_hygiene', 'Sleep Hygiene'
    NUTRITION_BASICS = 'nutrition_basics', 'Nutrition Basics'
    STRESS_MANAGEMENT = 'stress_management', 'Stress Management'
    PHYSICAL_ACTIVITY = 'physical_activity', 'Physical Activity'
    MINDFULNESS = 'mindfulness', 'Mindfulness'

class WellnessDeliveryContext(models.TextChoices):
    DAILY_TIP = 'daily_tip', 'Daily Wellness Tip'
    PATTERN_TRIGGERED = 'pattern_triggered', 'Pattern-Based Delivery'
    STRESS_RESPONSE = 'stress_response', 'High Stress Response'
    MOOD_SUPPORT = 'mood_support', 'Low Mood Support'
    ENERGY_BOOST = 'energy_boost', 'Low Energy Response'
    SHIFT_TRANSITION = 'shift_transition', 'Shift Start/End'
    STREAK_MILESTONE = 'streak_milestone', 'Milestone Reward'
    SEASONAL = 'seasonal', 'Seasonal Health'
    WORKPLACE_SPECIFIC = 'workplace_specific', 'Workplace Guidance'
    GRATITUDE_ENHANCEMENT = 'gratitude_enhancement', 'Positive Psychology Reinforcement'

class WellnessContentLevel(models.TextChoices):
    QUICK_TIP = 'quick_tip', 'Quick Tip (1 min)'
    SHORT_READ = 'short_read', 'Short Read (3 min)'
    DEEP_DIVE = 'deep_dive', 'Deep Dive (7 min)'
    INTERACTIVE = 'interactive', 'Interactive (5 min)'
    VIDEO_CONTENT = 'video_content', 'Video Content (4 min)'

class EvidenceLevel(models.TextChoices):
    WHO_CDC_GUIDELINE = 'who_cdc', 'WHO/CDC Guideline'
    PEER_REVIEWED_RESEARCH = 'peer_reviewed', 'Peer-Reviewed Research'
    PROFESSIONAL_CONSENSUS = 'professional', 'Professional Consensus'
    ESTABLISHED_PRACTICE = 'established', 'Established Practice'
    EDUCATIONAL_CONTENT = 'educational', 'General Education'

class WellnessContent(models.Model):
    """Evidence-based wellness education content with intelligent delivery"""

    # Content identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=200)
    summary = models.TextField(max_length=500)
    content = models.TextField()

    # Classification and targeting
    category = models.CharField(max_length=50, choices=WellnessContentCategory.choices)
    delivery_context = models.CharField(max_length=50, choices=WellnessDeliveryContext.choices)
    content_level = models.CharField(max_length=20, choices=WellnessContentLevel.choices)
    evidence_level = models.CharField(max_length=30, choices=EvidenceLevel.choices)

    # Smart targeting
    tags = models.JSONField(default=list)  # For pattern matching with journal entries
    trigger_patterns = models.JSONField(default=dict)  # Complex trigger conditions
    workplace_specific = models.BooleanField(default=False)
    field_worker_relevant = models.BooleanField(default=False)

    # Educational content structure
    action_tips = models.JSONField(default=list)  # Actionable advice
    key_takeaways = models.JSONField(default=list)  # Key learning points
    related_topics = models.JSONField(default=list)  # Related content IDs

    # Evidence and credibility (CRITICAL for medical compliance)
    source_name = models.CharField(max_length=100)  # WHO, CDC, Mayo Clinic, etc.
    source_url = models.URLField(blank=True, null=True)
    evidence_summary = models.TextField(blank=True)
    citations = models.JSONField(default=list)  # Academic citations
    last_verified_date = models.DateTimeField(null=True, blank=True)

    # Content management
    is_active = models.BooleanField(default=True)
    priority_score = models.IntegerField(default=50)  # 1-100, higher = more likely to show
    seasonal_relevance = models.JSONField(default=list)  # Months when most relevant
    frequency_limit_days = models.IntegerField(default=0)  # Days between showings

    # Publishing metadata
    estimated_reading_time = models.IntegerField()  # Minutes
    complexity_score = models.IntegerField(default=1)  # 1-5, reading difficulty
    content_version = models.CharField(max_length=10, default='1.0')

    # Multi-tenancy and audit
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['category', 'delivery_context']),
            models.Index(fields=['is_active', 'priority_score']),
            models.Index(fields=['workplace_specific', 'field_worker_relevant']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tags']),  # GIN index for JSON field
        ]

class WellnessUserProgress(models.Model):
    """User wellness education progress and gamification"""
    user = models.OneToOneField('core.User', on_delete=models.CASCADE)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)

    # Streak tracking (gamification)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_activity_date = models.DateTimeField(null=True, blank=True)

    # Learning metrics
    total_content_viewed = models.IntegerField(default=0)
    total_content_completed = models.IntegerField(default=0)
    total_time_spent_minutes = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)

    # Category-specific progress
    mental_health_progress = models.IntegerField(default=0)
    physical_wellness_progress = models.IntegerField(default=0)
    workplace_health_progress = models.IntegerField(default=0)
    substance_awareness_progress = models.IntegerField(default=0)
    preventive_care_progress = models.IntegerField(default=0)

    # User preferences
    preferred_content_level = models.CharField(
        max_length=20,
        choices=WellnessContentLevel.choices,
        default='short_read'
    )
    preferred_delivery_time = models.TimeField(null=True, blank=True)
    enabled_categories = models.JSONField(default=list)
    daily_tip_enabled = models.BooleanField(default=True)
    contextual_delivery_enabled = models.BooleanField(default=True)

    # Achievements and gamification
    achievements_earned = models.JSONField(default=list)
    milestone_alerts_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class WellnessContentInteraction(models.Model):
    """Detailed tracking of user engagement with wellness content"""

    INTERACTION_TYPES = [
        ('viewed', 'Viewed'),
        ('completed', 'Completed Reading'),
        ('bookmarked', 'Bookmarked'),
        ('shared', 'Shared'),
        ('dismissed', 'Dismissed'),
        ('rated', 'Rated'),
        ('acted_upon', 'Took Action'),
        ('requested_more', 'Requested More Info'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey('core.User', on_delete=models.CASCADE)
    content = models.ForeignKey(WellnessContent, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    delivery_context = models.CharField(max_length=50, choices=WellnessDeliveryContext.choices)

    # Engagement metrics
    time_spent_seconds = models.IntegerField(null=True, blank=True)
    completion_percentage = models.IntegerField(null=True, blank=True)  # 0-100
    user_rating = models.IntegerField(null=True, blank=True)  # 1-5 stars
    user_feedback = models.TextField(blank=True)
    action_taken = models.BooleanField(default=False)

    # Context when content was delivered (CRITICAL for effectiveness analysis)
    trigger_journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_wellness_content'
    )
    user_mood_at_delivery = models.IntegerField(null=True, blank=True)
    user_stress_at_delivery = models.IntegerField(null=True, blank=True)

    interaction_date = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'interaction_date']),
            models.Index(fields=['content', 'interaction_type']),
            models.Index(fields=['trigger_journal_entry']),
            models.Index(fields=['delivery_context']),
        ]
```

---

## 🌐 COMPLETE API SPECIFICATION

### Journal Entry CRUD APIs

```python
# apps/journal/urls.py & apps/journal/views.py

# POST /api/journal/entries/
# Create journal entry with automatic wellness content triggering
class JournalEntryCreateView(APIView):
    def post(self, request):
        """
        EXACT IMPLEMENTATION: Create journal entry with intelligent wellness integration

        1. Validate and create journal entry
        2. Real-time pattern analysis of entry content
        3. Automatic wellness content recommendation
        4. Privacy scope enforcement
        5. Trigger background analytics update
        """

        serializer = JournalEntryCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Create journal entry
            journal_entry = serializer.save(user=request.user)

            # Real-time pattern analysis for wellness content
            pattern_analyzer = JournalPatternAnalyzer()
            analysis_result = pattern_analyzer.analyze_entry_urgency(journal_entry)

            # Get contextual wellness content
            wellness_content = []
            if analysis_result['urgency_score'] >= 3:  # Threshold for content delivery
                wellness_service = WellnessContentDeliveryService()
                wellness_content = wellness_service.get_contextual_content(
                    user=request.user,
                    journal_entry=journal_entry,
                    analysis_result=analysis_result
                )

            # Background tasks
            update_user_analytics.delay(request.user.id, journal_entry.id)
            check_wellness_milestones.delay(request.user.id)

            return Response({
                'journal_entry': JournalEntrySerializer(journal_entry).data,
                'triggered_wellness_content': WellnessContentSerializer(wellness_content, many=True).data,
                'pattern_analysis': analysis_result,
                'sync_status': 'synced'
            }, status=201)

# GET /api/journal/entries/
# Privacy-aware journal entry retrieval with filtering
class JournalEntryListView(ListAPIView):
    def get_queryset(self):
        """
        EXACT IMPLEMENTATION: Privacy-filtered journal entries

        1. Base queryset filtered by user and tenant
        2. Apply privacy scope filtering based on requesting user's permissions
        3. Respect consent settings for wellbeing data access
        4. Support advanced filtering (type, date, mood, stress, location)
        5. Optimize with select_related for performance
        """

        user = self.request.user
        base_queryset = JournalEntry.objects.filter(
            user=user,
            is_deleted=False
        ).select_related('user').prefetch_related('media')

        # Apply filters from query parameters
        entry_types = self.request.query_params.getlist('entry_types')
        if entry_types:
            base_queryset = base_queryset.filter(entry_type__in=entry_types)

        # Date range filtering
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from and date_to:
            base_queryset = base_queryset.filter(
                timestamp__range=[date_from, date_to]
            )

        # Wellbeing filters
        mood_min = self.request.query_params.get('mood_min')
        mood_max = self.request.query_params.get('mood_max')
        if mood_min and mood_max:
            base_queryset = base_queryset.filter(
                mood_rating__range=[mood_min, mood_max]
            )

        stress_min = self.request.query_params.get('stress_min')
        stress_max = self.request.query_params.get('stress_max')
        if stress_min and stress_max:
            base_queryset = base_queryset.filter(
                stress_level__range=[stress_min, stress_max]
            )

        # Location filtering
        location = self.request.query_params.get('location')
        if location:
            base_queryset = base_queryset.filter(location_site_name__icontains=location)

        # Tag filtering
        tags = self.request.query_params.getlist('tags')
        if tags:
            for tag in tags:
                base_queryset = base_queryset.filter(tags__contains=[tag])

        return base_queryset.order_by('-timestamp')

# POST /api/journal/search/
# Advanced search with Elasticsearch integration
class JournalSearchView(APIView):
    def post(self, request):
        """
        EXACT SEARCH IMPLEMENTATION: Full-text search with privacy and analytics

        1. Parse search query and filters
        2. Build Elasticsearch query with privacy enforcement
        3. Execute search with highlighting and faceting
        4. Post-process results for privacy compliance
        5. Generate search suggestions and analytics
        6. Track search patterns for personalization
        """

        search_params = JournalSearchSerializer(data=request.data)
        if search_params.is_valid():

            # Build Elasticsearch query
            es_query = self._build_elasticsearch_query(
                user=request.user,
                query=search_params.validated_data['query'],
                filters=search_params.validated_data.get('filters', {}),
                sort_by=search_params.validated_data.get('sort_by', 'relevance')
            )

            # Execute search
            search_results = self.elasticsearch_client.search(
                index='journal_entries',
                body=es_query
            )

            # Privacy filtering post-processing
            privacy_filtered_results = self._apply_privacy_filtering(
                search_results, request.user
            )

            # Generate search suggestions
            suggestions = self._generate_search_suggestions(
                query=search_params.validated_data['query'],
                user_history=request.user.journal_search_history
            )

            # Track search for personalization
            self._track_search_interaction(request.user, search_params.validated_data)

            return Response({
                'results': privacy_filtered_results,
                'total_results': search_results['hits']['total']['value'],
                'facets': search_results['aggregations'],
                'search_suggestions': suggestions,
                'search_time_ms': search_results['took']
            })

# GET /api/journal/analytics/comprehensive/?user_id={id}&days=30
# Complete wellbeing analytics (MOVED from Kotlin WellbeingInsightsViewModel)
class JournalAnalyticsView(APIView):
    def get(self, request):
        """
        EXACT ANALYTICS IMPLEMENTATION: Complete wellbeing insights generation

        ALL ALGORITHMS MOVED FROM KOTLIN:
        - Mood trend analysis with variability calculation
        - Stress pattern recognition and trigger analysis
        - Energy correlation with work patterns
        - Positive psychology engagement measurement
        - Predictive modeling for intervention timing
        - Personalized recommendation generation
        """

        user_id = request.query_params.get('user_id', request.user.id)
        days = int(request.query_params.get('days', 30))

        # Comprehensive analytics generation
        analytics_engine = JournalAnalyticsEngine()

        # 1. Mood Analysis (ALGORITHM from Kotlin)
        mood_trends = analytics_engine.calculate_mood_trends(user_id, days)

        # 2. Stress Analysis (ALGORITHM from Kotlin)
        stress_analysis = analytics_engine.calculate_stress_patterns(user_id, days)

        # 3. Energy Analysis (ALGORITHM from Kotlin)
        energy_patterns = analytics_engine.calculate_energy_trends(user_id, days)

        # 4. Positive Psychology Analysis (NEW from Kotlin)
        positive_insights = analytics_engine.analyze_positive_psychology_engagement(user_id, days)

        # 5. Pattern Recognition (COMPLEX ALGORITHM from Kotlin)
        behavioral_patterns = analytics_engine.detect_behavioral_patterns(user_id, days)

        # 6. Predictive Analytics (NEW - enterprise feature)
        predictions = analytics_engine.generate_wellbeing_predictions(user_id, days)

        # 7. Personalized Recommendations (ML-BASED)
        recommendations = analytics_engine.generate_ml_recommendations(user_id, days)

        # 8. Overall Wellbeing Score (MULTI-FACTOR ALGORITHM from Kotlin)
        wellbeing_score = analytics_engine.calculate_overall_wellbeing_score(
            mood_trends, stress_analysis, energy_patterns, positive_insights
        )

        return Response({
            'wellbeing_trends': {
                'mood_analysis': mood_trends,
                'stress_analysis': stress_analysis,
                'energy_analysis': energy_patterns,
                'positive_psychology_insights': positive_insights
            },
            'behavioral_patterns': behavioral_patterns,
            'predictive_insights': predictions,
            'recommendations': recommendations,
            'overall_wellbeing_score': wellbeing_score,
            'analysis_metadata': {
                'analysis_date': timezone.now(),
                'data_points_analyzed': mood_trends.get('data_points_count', 0),
                'privacy_compliance': True,
                'algorithm_version': '2.1.0'
            }
        })
```

### Wellness Education APIs (Integrated with Journal)

```python
# apps/wellness/views.py

# GET /api/wellness/daily-tip/
class DailyWellnessTipView(APIView):
    def get(self, request):
        """
        INTELLIGENT DAILY TIP: Personalized based on recent journal patterns

        ALGORITHM:
        1. Analyze user's last 7 days of journal entries
        2. Identify current stress/mood/energy patterns
        3. Check recent wellness content consumption to avoid repetition
        4. Select tip based on urgency, personalization, and seasonal relevance
        5. Track delivery for effectiveness measurement
        """

        user = request.user

        # Analyze recent journal patterns
        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).order_by('-timestamp')

        pattern_analyzer = WellnessPatternAnalyzer()
        user_patterns = pattern_analyzer.analyze_recent_patterns(recent_entries)

        # Get personalized tip
        tip_selector = WellnessTipSelector()
        daily_tip = tip_selector.select_personalized_tip(
            user=user,
            patterns=user_patterns,
            previously_seen=self._get_recent_content_ids(user)
        )

        if daily_tip:
            # Track delivery
            WellnessContentInteraction.objects.create(
                user=user,
                content=daily_tip,
                interaction_type='viewed',
                delivery_context='daily_tip',
                user_mood_at_delivery=user_patterns.get('current_mood'),
                user_stress_at_delivery=user_patterns.get('current_stress')
            )

        return Response({
            'daily_tip': WellnessContentSerializer(daily_tip).data if daily_tip else None,
            'personalization_metadata': {
                'user_patterns': user_patterns,
                'selection_reason': tip_selector.last_selection_reason,
                'effectiveness_prediction': tip_selector.predicted_effectiveness
            },
            'next_tip_available_at': timezone.now() + timedelta(days=1)
        })

# POST /api/wellness/contextual/
class ContextualWellnessContentView(APIView):
    def post(self, request):
        """
        REAL-TIME CONTEXTUAL CONTENT: Immediate wellness support based on journal entry

        EXACT ALGORITHM:
        1. Receive journal entry context from mobile client
        2. Real-time pattern analysis for urgency assessment
        3. ML-based content matching using user history and entry context
        4. Priority-based content ranking with effectiveness prediction
        5. Return immediate + follow-up content recommendations
        """

        journal_entry_data = request.data.get('journal_entry')
        user_context = request.data.get('user_context', {})

        # Create temporary journal entry object for analysis
        temp_entry = JournalEntry(**journal_entry_data)

        # Real-time pattern analysis
        pattern_analyzer = JournalPatternAnalyzer()
        urgency_analysis = pattern_analyzer.analyze_entry_for_immediate_action(temp_entry)

        # Get contextual content based on analysis
        content_engine = ContextualContentEngine()

        immediate_content = []
        follow_up_content = []

        if urgency_analysis['urgency_score'] >= 5:  # High urgency
            immediate_content = content_engine.get_urgent_support_content(
                user=request.user,
                entry_analysis=urgency_analysis,
                user_context=user_context
            )

        if urgency_analysis['urgency_score'] >= 2:  # Any notable patterns
            follow_up_content = content_engine.get_follow_up_content(
                user=request.user,
                entry_analysis=urgency_analysis,
                user_context=user_context
            )

        # Track contextual delivery
        for content in immediate_content:
            WellnessContentInteraction.objects.create(
                user=request.user,
                content=content,
                interaction_type='viewed',
                delivery_context='pattern_triggered',
                trigger_journal_entry=temp_entry if hasattr(temp_entry, 'id') else None,
                user_mood_at_delivery=journal_entry_data.get('mood_rating'),
                user_stress_at_delivery=journal_entry_data.get('stress_level')
            )

        return Response({
            'immediate_content': WellnessContentSerializer(immediate_content, many=True).data,
            'follow_up_content': WellnessContentSerializer(follow_up_content, many=True).data,
            'urgency_analysis': urgency_analysis,
            'delivery_metadata': {
                'analysis_timestamp': timezone.now(),
                'algorithm_version': '2.1.0',
                'user_pattern_confidence': urgency_analysis.get('confidence', 0.5)
            }
        })

# GET /api/wellness/personalized/?limit=5
class PersonalizedWellnessContentView(APIView):
    def get(self, request):
        """
        ML-POWERED PERSONALIZATION: Advanced recommendation engine

        EXACT ML ALGORITHM:
        1. Build comprehensive user profile from journal history
        2. Analyze wellness content engagement patterns
        3. Apply collaborative filtering with similar users
        4. Content-based filtering using entry patterns
        5. Rank content by predicted effectiveness
        6. Apply diversity constraints to avoid content type clustering
        """

        limit = int(request.query_params.get('limit', 5))

        # Build user profile for ML recommendations
        profile_builder = UserProfileBuilder()
        user_profile = profile_builder.build_comprehensive_profile(request.user)

        # ML-based recommendation engine
        recommendation_engine = WellnessRecommendationEngine()
        recommended_content = recommendation_engine.generate_recommendations(
            user_profile=user_profile,
            limit=limit,
            diversity_constraint=True,
            exclude_recent_views=True
        )

        return Response({
            'personalized_content': [
                {
                    'content': WellnessContentSerializer(item['content']).data,
                    'personalization_score': item['score'],
                    'recommendation_reason': item['reason'],
                    'predicted_effectiveness': item['effectiveness'],
                    'estimated_value': item['value_score']
                }
                for item in recommended_content
            ],
            'personalization_metadata': {
                'user_profile_features': user_profile.get_feature_summary(),
                'recommendation_algorithm': 'hybrid_cf_cbf_v2.1',
                'model_confidence': recommendation_engine.last_confidence_score,
                'diversity_score': recommendation_engine.calculate_diversity_score(recommended_content)
            }
        })
```

### Advanced Analytics APIs (MOVED from Kotlin)

```python
# GET /api/journal/analytics/wellbeing-insights/?days=30
class WellbeingInsightsView(APIView):
    def get(self, request):
        """
        COMPLETE WELLBEING ANALYTICS: All algorithms moved from Kotlin WellbeingInsightsViewModel

        EXACT IMPLEMENTATIONS of:
        - calculateMoodTrends()
        - calculateStressTrends()
        - calculateEnergyTrends()
        - calculateGratitudeInsights()
        - calculateAchievementInsights()
        - calculatePatternInsights()
        - generateRecommendations()
        - calculateOverallWellbeingScore()
        """

        days = int(request.query_params.get('days', 30))
        user = request.user

        # Get journal entries for analysis period
        journal_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=days),
            is_deleted=False
        ).order_by('timestamp')

        if not journal_entries.exists():
            return Response({
                'has_data': False,
                'message': 'No journal entries found for this period. Start journaling to see insights!'
            })

        # Advanced analytics engine (ALL ALGORITHMS from Kotlin)
        analytics_engine = WellbeingAnalyticsEngine()

        # 1. Mood Trends Analysis (EXACT algorithm from Kotlin calculateMoodTrends)
        mood_trends = analytics_engine.calculate_mood_trends(journal_entries)

        # 2. Stress Analysis (EXACT algorithm from Kotlin calculateStressTrends)
        stress_analysis = analytics_engine.calculate_stress_trends(journal_entries)

        # 3. Energy Patterns (EXACT algorithm from Kotlin calculateEnergyTrends)
        energy_trends = analytics_engine.calculate_energy_trends(journal_entries)

        # 4. Gratitude Insights (EXACT algorithm from Kotlin calculateGratitudeInsights)
        gratitude_insights = analytics_engine.calculate_gratitude_insights(journal_entries)

        # 5. Achievement Analysis (EXACT algorithm from Kotlin calculateAchievementInsights)
        achievement_insights = analytics_engine.calculate_achievement_insights(journal_entries)

        # 6. Pattern Recognition (EXACT algorithm from Kotlin calculatePatternInsights)
        pattern_insights = analytics_engine.calculate_pattern_insights(journal_entries)

        # 7. Recommendation Generation (EXACT algorithm from Kotlin generateRecommendations)
        recommendations = analytics_engine.generate_recommendations(
            mood_trends, stress_analysis, energy_trends, journal_entries
        )

        # 8. Overall Wellbeing Score (EXACT algorithm from Kotlin calculateOverallWellbeingScore)
        wellbeing_score = analytics_engine.calculate_overall_wellbeing_score(
            mood_trends, stress_analysis, energy_trends, journal_entries
        )

        # 9. Streak Data (EXACT algorithm from Kotlin calculateStreakData)
        streak_data = analytics_engine.calculate_streak_data(journal_entries)

        return Response({
            'wellbeing_insights': {
                'overall_score': wellbeing_score,
                'mood_trends': mood_trends,
                'stress_analysis': stress_analysis,
                'energy_patterns': energy_trends,
                'gratitude_insights': gratitude_insights,
                'achievement_insights': achievement_insights,
                'behavioral_patterns': pattern_insights,
                'streak_data': streak_data
            },
            'recommendations': recommendations,
            'metadata': {
                'analysis_period_days': days,
                'total_entries_analyzed': journal_entries.count(),
                'wellbeing_entries': journal_entries.filter(
                    entry_type__in=['MOOD_CHECK_IN', 'GRATITUDE', 'STRESS_LOG', 'THREE_GOOD_THINGS']
                ).count(),
                'analysis_timestamp': timezone.now(),
                'algorithm_versions': {
                    'mood_analysis': '2.1.0',
                    'stress_analysis': '2.0.5',
                    'pattern_recognition': '1.8.2',
                    'ml_recommendations': '3.0.1'
                }
            }
        })
```

---

## 🧠 BACKEND INTELLIGENCE ALGORITHMS

### Real-Time Pattern Recognition Service

```python
# apps/journal/services/pattern_analyzer.py

class JournalPatternAnalyzer:
    """
    EXACT ALGORITHMS: All pattern recognition moved from Kotlin to Django
    Real-time analysis of journal entries for immediate wellness interventions
    """

    def analyze_entry_for_immediate_action(self, journal_entry):
        """
        CRITICAL ALGORITHM: Immediate intervention detection
        MOVED FROM: Kotlin WellbeingInsightsViewModel.calculateOverallWellbeingScore()

        Urgency Scoring Algorithm:
        - Stress level ≥ 4: +3 points (high stress threshold)
        - Mood ≤ 2: +4 points (crisis mood threshold)
        - Energy ≤ 3: +1 point (fatigue threshold)
        - Equipment/safety triggers: +2 points (workplace safety)
        - Deadline/pressure triggers: +1 point (time management)

        Total Score ≥ 5: Immediate intervention required
        Total Score 3-4: Same-day intervention recommended
        Total Score 1-2: Next-session intervention
        """

        urgency_score = 0
        intervention_categories = []
        immediate_actions = []

        # Stress urgency analysis
        if journal_entry.stress_level and journal_entry.stress_level >= 4:
            urgency_score += 3
            intervention_categories.append('stress_management')
            immediate_actions.append('breathing_exercises')

            # Analyze stress triggers for targeted content
            triggers = journal_entry.stress_triggers or []
            if any('equipment' in trigger.lower() for trigger in triggers):
                urgency_score += 2
                intervention_categories.append('equipment_stress_management')
                immediate_actions.append('equipment_failure_protocol')

            if any('deadline' in trigger.lower() for trigger in triggers):
                urgency_score += 1
                intervention_categories.append('time_management')
                immediate_actions.append('priority_setting_technique')

        # Mood crisis detection
        if journal_entry.mood_rating and journal_entry.mood_rating <= 2:
            urgency_score += 4
            intervention_categories.append('mood_crisis_support')
            immediate_actions.append('immediate_mood_support')

            # Check for crisis indicators in content
            crisis_keywords = ['hopeless', 'overwhelmed', 'can\'t cope', 'breaking point']
            content_text = (journal_entry.content or '').lower()
            if any(keyword in content_text for keyword in crisis_keywords):
                urgency_score += 2
                intervention_categories.append('crisis_intervention')

        # Energy depletion analysis
        if journal_entry.energy_level and journal_entry.energy_level <= 3:
            urgency_score += 1
            intervention_categories.append('energy_management')
            immediate_actions.append('energy_boost_techniques')

        # Safety concern analysis
        if journal_entry.entry_type == 'SAFETY_CONCERN':
            urgency_score += 2
            intervention_categories.append('workplace_safety_education')
            immediate_actions.append('safety_protocols')

        return {
            'urgency_score': urgency_score,  # 0-10+ scale
            'urgency_level': self._categorize_urgency(urgency_score),
            'intervention_categories': intervention_categories,
            'immediate_actions': immediate_actions,
            'delivery_timing': self._calculate_delivery_timing(urgency_score),
            'follow_up_required': urgency_score >= 7,
            'crisis_indicators': urgency_score >= 6,
            'recommended_content_count': min(5, max(1, urgency_score // 2))
        }

    def detect_long_term_patterns(self, user_journal_history):
        """
        COMPLEX PATTERN DETECTION: Long-term trend analysis for proactive wellness
        MOVED FROM: Multiple Kotlin analytics methods

        Pattern Detection Algorithms:
        1. Stress Cycle Analysis - Weekly/monthly stress patterns
        2. Mood Seasonality - Seasonal affective patterns
        3. Energy-Work Correlation - Energy levels vs work type
        4. Trigger Pattern Recognition - Recurring stress triggers
        5. Coping Effectiveness - Which strategies work best for user
        6. Positive Psychology Engagement - Gratitude/affirmation patterns
        """

        # 1. Stress Cycle Analysis
        stress_entries = [e for e in user_journal_history if e.stress_level is not None]
        stress_cycles = self._detect_stress_cycles(stress_entries)

        # 2. Mood Seasonality Detection
        mood_entries = [e for e in user_journal_history if e.mood_rating is not None]
        mood_seasonality = self._analyze_mood_seasonality(mood_entries)

        # 3. Energy-Work Correlation
        energy_work_correlation = self._correlate_energy_with_work_context(user_journal_history)

        # 4. Trigger Pattern Recognition
        trigger_patterns = self._analyze_recurring_triggers(stress_entries)

        # 5. Coping Strategy Effectiveness
        coping_effectiveness = self._measure_coping_strategy_effectiveness(stress_entries)

        # 6. Positive Psychology Engagement Analysis
        positive_entries = [e for e in user_journal_history if e.entry_type in [
            'GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS', 'STRENGTH_SPOTTING'
        ]]
        positive_engagement = self._analyze_positive_psychology_patterns(positive_entries)

        return {
            'detected_patterns': {
                'stress_cycles': stress_cycles,
                'mood_seasonality': mood_seasonality,
                'energy_work_correlation': energy_work_correlation,
                'trigger_patterns': trigger_patterns,
                'coping_effectiveness': coping_effectiveness,
                'positive_engagement': positive_engagement
            },
            'risk_predictions': self._predict_wellbeing_risks(user_journal_history),
            'optimal_intervention_timing': self._calculate_optimal_intervention_timing(user_journal_history),
            'personalized_learning_path': self._generate_learning_path(user_journal_history),
            'confidence_metrics': {
                'pattern_confidence': self._calculate_pattern_confidence(user_journal_history),
                'prediction_confidence': self._calculate_prediction_confidence(user_journal_history),
                'data_sufficiency': len(user_journal_history) >= 30  # Minimum for reliable patterns
            }
        }

    def _detect_stress_cycles(self, stress_entries):
        """
        EXACT ALGORITHM: Weekly and monthly stress pattern detection
        MOVED FROM: Kotlin WellbeingInsightsViewModel.calculateStressTrends()
        """

        if len(stress_entries) < 14:  # Need minimum 2 weeks of data
            return {'insufficient_data': True}

        # Group by day of week
        day_patterns = {}
        for entry in stress_entries:
            day_name = entry.timestamp.strftime('%A')
            if day_name not in day_patterns:
                day_patterns[day_name] = []
            day_patterns[day_name].append(entry.stress_level)

        # Calculate average stress by day of week
        day_averages = {
            day: sum(stress_levels) / len(stress_levels)
            for day, stress_levels in day_patterns.items()
        }

        # Identify high-stress days
        overall_avg = sum(day_averages.values()) / len(day_averages)
        high_stress_days = [
            day for day, avg in day_averages.items()
            if avg > overall_avg + 0.5
        ]

        # Monthly pattern analysis
        monthly_patterns = self._analyze_monthly_stress_patterns(stress_entries)

        return {
            'weekly_patterns': day_averages,
            'high_stress_days': high_stress_days,
            'monthly_patterns': monthly_patterns,
            'cycle_confidence': self._calculate_cycle_confidence(day_patterns),
            'predicted_next_high_stress': self._predict_next_stress_spike(day_averages, high_stress_days)
        }
```

### ML-Powered Analytics Engine

```python
# apps/journal/ml/analytics_engine.py

class WellbeingAnalyticsEngine:
    """
    COMPLETE ANALYTICS ENGINE: All Kotlin algorithms moved to Django with ML enhancement
    Implements ALL methods from Kotlin WellbeingInsightsViewModel
    """

    def calculate_mood_trends(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateMoodTrends()

        Mood Trend Calculation:
        1. Extract mood ratings from journal entries
        2. Group by date and calculate daily averages
        3. Calculate overall average mood and variability
        4. Determine trend direction (improving/stable/declining)
        5. Identify best and challenging days
        6. Analyze day-of-week mood patterns
        """

        mood_entries = [e for e in journal_entries if e.mood_rating is not None]

        if len(mood_entries) < 3:
            return {
                'average_mood': 0.0,
                'mood_variability': 0.0,
                'trend_direction': 'insufficient_data',
                'daily_moods': [],
                'best_days': [],
                'challenging_days': [],
                'mood_patterns': {}
            }

        # Group by date and calculate daily averages
        daily_moods = {}
        for entry in mood_entries:
            date = entry.timestamp.date()
            if date not in daily_moods:
                daily_moods[date] = []
            daily_moods[date].append(entry.mood_rating)

        daily_averages = {
            date: sum(moods) / len(moods)
            for date, moods in daily_moods.items()
        }

        # Calculate statistics
        mood_values = list(daily_averages.values())
        average_mood = sum(mood_values) / len(mood_values)

        # Mood variability calculation
        variance = sum((mood - average_mood) ** 2 for mood in mood_values) / len(mood_values)
        mood_variability = variance ** 0.5

        # Trend direction calculation
        first_half = mood_values[:len(mood_values)//2]
        second_half = mood_values[len(mood_values)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        trend_direction = 'stable'
        if second_avg > first_avg + 0.5:
            trend_direction = 'improving'
        elif second_avg < first_avg - 0.5:
            trend_direction = 'declining'

        # Best and challenging days
        sorted_days = sorted(daily_averages.items(), key=lambda x: x[1])
        best_days = [day for day, mood in sorted_days[-3:]]
        challenging_days = [day for day, mood in sorted_days[:3]]

        # Day-of-week patterns
        day_patterns = {}
        for entry in mood_entries:
            day_name = entry.timestamp.strftime('%A')
            if day_name not in day_patterns:
                day_patterns[day_name] = []
            day_patterns[day_name].append(entry.mood_rating)

        mood_patterns = {
            day: sum(moods) / len(moods)
            for day, moods in day_patterns.items()
        }

        return {
            'average_mood': round(average_mood, 2),
            'mood_variability': round(mood_variability, 2),
            'trend_direction': trend_direction,
            'daily_moods': [
                {
                    'date': date.isoformat(),
                    'mood': round(mood, 2),
                    'entry_count': len(daily_moods[date])
                }
                for date, mood in sorted(daily_averages.items())
            ],
            'best_days': [day.isoformat() for day in best_days],
            'challenging_days': [day.isoformat() for day in challenging_days],
            'mood_patterns': {day: round(avg, 2) for day, avg in mood_patterns.items()}
        }

    def calculate_stress_trends(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateStressTrends()

        Stress Analysis Algorithm:
        1. Extract stress levels and triggers from entries
        2. Calculate average stress and trend direction
        3. Analyze trigger frequency and patterns
        4. Evaluate coping strategy effectiveness
        5. Generate stress pattern insights
        """

        stress_entries = [e for e in journal_entries if e.stress_level is not None]

        if len(stress_entries) < 3:
            return {
                'average_stress': 0.0,
                'trend_direction': 'insufficient_data',
                'daily_stress': [],
                'common_triggers': [],
                'effective_coping_strategies': [],
                'stress_patterns': {}
            }

        # Group by date for daily stress analysis
        daily_stress = {}
        all_triggers = []
        all_coping_strategies = []

        for entry in stress_entries:
            date = entry.timestamp.date()
            if date not in daily_stress:
                daily_stress[date] = []
            daily_stress[date].append(entry.stress_level)

            # Collect triggers and coping strategies
            if entry.stress_triggers:
                all_triggers.extend(entry.stress_triggers)
            if entry.coping_strategies:
                all_coping_strategies.extend(entry.coping_strategies)

        # Calculate daily averages
        daily_averages = {
            date: sum(stress_levels) / len(stress_levels)
            for date, stress_levels in daily_stress.items()
        }

        # Overall statistics
        stress_values = list(daily_averages.values())
        average_stress = sum(stress_values) / len(stress_values)

        # Trend calculation (inverted - lower stress is better)
        first_half = stress_values[:len(stress_values)//2]
        second_half = stress_values[len(stress_values)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        trend_direction = 'stable'
        if first_avg > second_avg + 0.3:  # Stress decreased
            trend_direction = 'improving'
        elif first_avg < second_avg - 0.3:  # Stress increased
            trend_direction = 'declining'

        # Trigger frequency analysis
        from collections import Counter
        trigger_frequency = Counter(all_triggers)
        common_triggers = [
            {'trigger': trigger, 'frequency': freq}
            for trigger, freq in trigger_frequency.most_common(5)
        ]

        # Coping strategy effectiveness (simplified algorithm)
        coping_frequency = Counter(all_coping_strategies)
        effective_coping = [
            {
                'strategy': strategy,
                'frequency': freq,
                'effectiveness': 0.8  # Placeholder - would calculate based on stress reduction
            }
            for strategy, freq in coping_frequency.most_common(5)
        ]

        # Day-of-week stress patterns
        day_patterns = {}
        for entry in stress_entries:
            day_name = entry.timestamp.strftime('%A')
            if day_name not in day_patterns:
                day_patterns[day_name] = []
            day_patterns[day_name].append(entry.stress_level)

        stress_patterns = {
            day: sum(stress_levels) / len(stress_levels)
            for day, stress_levels in day_patterns.items()
        }

        return {
            'average_stress': round(average_stress, 2),
            'trend_direction': trend_direction,
            'daily_stress': [
                {
                    'date': date.isoformat(),
                    'stress': round(stress, 2),
                    'entry_count': len(daily_stress[date])
                }
                for date, stress in sorted(daily_averages.items())
            ],
            'common_triggers': common_triggers,
            'effective_coping_strategies': effective_coping,
            'stress_patterns': {day: round(avg, 2) for day, avg in stress_patterns.items()}
        }

    def calculate_gratitude_insights(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateGratitudeInsights()

        Gratitude Analysis:
        1. Count gratitude entries and extract gratitude items
        2. Calculate average gratitude items per entry
        3. Determine current gratitude streak
        4. Extract and categorize gratitude themes
        5. Calculate gratitude frequency over time period
        """

        gratitude_entries = [
            e for e in journal_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS']
            or (e.gratitude_items and len(e.gratitude_items) > 0)
        ]

        if len(gratitude_entries) == 0:
            return {
                'total_gratitude_entries': 0,
                'average_gratitude_per_entry': 0.0,
                'gratitude_streak': 0,
                'common_gratitude_themes': [],
                'gratitude_frequency': 0.0
            }

        # Extract all gratitude items
        all_gratitude_items = []
        for entry in gratitude_entries:
            if entry.gratitude_items:
                all_gratitude_items.extend(entry.gratitude_items)
            # Also check metadata for Three Good Things
            if entry.entry_type == 'THREE_GOOD_THINGS' and 'goodThings' in entry.metadata:
                all_gratitude_items.extend(entry.metadata['goodThings'])

        # Calculate statistics
        average_per_entry = len(all_gratitude_items) / len(gratitude_entries) if gratitude_entries else 0

        # Gratitude streak calculation
        gratitude_streak = self._calculate_gratitude_streak(gratitude_entries)

        # Theme extraction and categorization
        common_themes = self._extract_gratitude_themes(all_gratitude_items)

        # Frequency calculation
        if journal_entries:
            date_range = (journal_entries[-1].timestamp.date() - journal_entries[0].timestamp.date()).days
            gratitude_frequency = len(gratitude_entries) / max(1, date_range)
        else:
            gratitude_frequency = 0.0

        return {
            'total_gratitude_entries': len(gratitude_entries),
            'average_gratitude_per_entry': round(average_per_entry, 2),
            'gratitude_streak': gratitude_streak,
            'common_gratitude_themes': common_themes,
            'gratitude_frequency': round(gratitude_frequency, 3)
        }

    def generate_recommendations(self, mood_trends, stress_analysis, energy_trends, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.generateRecommendations()

        Recommendation Generation Algorithm:
        1. Analyze mood trends for improvement opportunities
        2. Evaluate stress patterns for management strategies
        3. Assess positive psychology engagement levels
        4. Generate priority-ranked actionable recommendations
        5. Link recommendations to specific wellness content
        """

        recommendations = []

        # Mood-based recommendations
        if mood_trends['average_mood'] < 5.0:
            recommendations.append({
                'type': 'mood_improvement',
                'priority': 'high',
                'title': 'Mood Enhancement Focus',
                'description': f"Your average mood ({mood_trends['average_mood']}) has been below optimal. Consider positive psychology practices.",
                'action_items': [
                    'Try daily gratitude journaling',
                    'Practice the "3 Good Things" exercise',
                    'Consider mindfulness or meditation content'
                ],
                'predicted_impact': 'high',
                'suggested_content_categories': ['gratitude', 'positive_psychology', 'mindfulness'],
                'estimated_improvement_timeline': '2_weeks'
            })

        # Stress-based recommendations
        if stress_analysis['average_stress'] > 3.0:
            recommendations.append({
                'type': 'stress_management',
                'priority': 'high',
                'title': 'Stress Management Priority',
                'description': f"Your stress level ({stress_analysis['average_stress']}) indicates need for targeted stress management.",
                'action_items': [
                    'Log stress triggers to identify patterns',
                    'Practice proven coping strategies',
                    'Consider workplace stress management techniques'
                ],
                'predicted_impact': 'high',
                'suggested_content_categories': ['stress_management', 'workplace_wellness', 'coping_techniques'],
                'trigger_analysis': stress_analysis.get('common_triggers', [])
            })

        # Positive psychology engagement assessment
        positive_entries = len([
            e for e in journal_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS', 'STRENGTH_SPOTTING']
        ])
        total_entries = len(journal_entries)
        positive_ratio = positive_entries / max(1, total_entries)

        if positive_ratio < 0.3:  # Less than 30% positive psychology entries
            recommendations.append({
                'type': 'positive_psychology_enhancement',
                'priority': 'medium',
                'title': 'Enhance Positive Practices',
                'description': f"Only {positive_ratio:.1%} of your entries focus on positive psychology. Research shows 30%+ optimal.",
                'action_items': [
                    'Try weekly "Best Self" reflections',
                    'Practice daily gratitude or affirmations',
                    'Add strength spotting exercises'
                ],
                'predicted_impact': 'medium',
                'suggested_content_categories': ['positive_psychology', 'gratitude', 'strength_identification'],
                'evidence_basis': 'Seligman et al. positive psychology research'
            })

        # Energy optimization recommendations
        if energy_trends.get('average_energy', 0) < 6.0:
            recommendations.append({
                'type': 'energy_optimization',
                'priority': 'medium',
                'title': 'Energy Management Focus',
                'description': f"Your energy levels ({energy_trends.get('average_energy', 0)}) could be optimized.",
                'action_items': [
                    'Review sleep hygiene practices',
                    'Consider physical activity integration',
                    'Explore nutrition and energy management'
                ],
                'predicted_impact': 'medium',
                'suggested_content_categories': ['sleep_hygiene', 'physical_activity', 'nutrition_basics']
            })

        # Consistency recommendations
        entry_days = len(set(e.timestamp.date() for e in journal_entries))
        total_days = (journal_entries[-1].timestamp.date() - journal_entries[0].timestamp.date()).days + 1
        consistency_ratio = entry_days / max(1, total_days)

        if consistency_ratio < 0.5:  # Less than 50% consistency
            recommendations.append({
                'type': 'consistency_improvement',
                'priority': 'low',
                'title': 'Build Journaling Consistency',
                'description': f"Your journaling consistency ({consistency_ratio:.1%}) could support better pattern recognition.",
                'action_items': [
                    'Set daily journaling reminders',
                    'Start with quick mood check-ins',
                    'Celebrate small consistency wins'
                ],
                'predicted_impact': 'low',
                'suggested_content_categories': ['habit_formation', 'consistency_tips']
            })

        return sorted(recommendations, key=lambda x: {'high': 3, 'medium': 2, 'low': 1}[x['priority']], reverse=True)

    def calculate_overall_wellbeing_score(self, mood_trends, stress_analysis, energy_trends, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateOverallWellbeingScore()

        Multi-Factor Wellbeing Score Calculation:
        - Mood factor (30% weight): 0-10 scale normalized
        - Stress factor (25% weight): 1-5 scale inverted and normalized
        - Energy factor (20% weight): 0-10 scale normalized
        - Positive psychology ratio (15% weight): % of positive entries
        - Consistency factor (10% weight): journaling frequency

        Final Score: 0-100 scale
        """

        if len(journal_entries) == 0:
            return 0.0

        score = 0.0

        # Mood factor (30% weight)
        mood_score = mood_trends.get('average_mood', 0) / 10.0 * 0.3
        score += mood_score

        # Stress factor (25% weight, inverted)
        avg_stress = stress_analysis.get('average_stress', 0)
        if avg_stress > 0:
            stress_score = (6.0 - avg_stress) / 5.0 * 0.25
            score += stress_score

        # Energy factor (20% weight)
        avg_energy = energy_trends.get('average_energy', 0)
        if avg_energy > 0:
            energy_score = avg_energy / 10.0 * 0.2
            score += energy_score

        # Positive psychology factor (15% weight)
        positive_entries = len([
            e for e in journal_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS', 'STRENGTH_SPOTTING']
        ])
        positive_ratio = positive_entries / len(journal_entries)
        positive_score = min(1.0, positive_ratio * 2.0) * 0.15  # Cap at 50% positive entries
        score += positive_score

        # Consistency factor (10% weight)
        entry_days = len(set(e.timestamp.date() for e in journal_entries))
        total_days = (journal_entries[-1].timestamp.date() - journal_entries[0].timestamp.date()).days + 1
        consistency_ratio = entry_days / max(1, total_days)
        consistency_score = consistency_ratio * 0.1
        score += consistency_score

        # Convert to 0-100 scale
        final_score = min(100.0, max(0.0, score * 100))

        return round(final_score, 1)
```

---

## 🔍 ELASTICSEARCH INTEGRATION SPECIFICATION

### Advanced Search Implementation

```python
# apps/journal/search/elasticsearch_manager.py

class JournalElasticsearchManager:
    """
    EXACT IMPLEMENTATION: Enterprise-grade search replacing Kotlin stub
    Full-text search with privacy filtering and advanced analytics
    """

    JOURNAL_INDEX_MAPPING = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "journal_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop", "snowball"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                # Searchable content fields
                "title": {
                    "type": "text",
                    "analyzer": "journal_analyzer",
                    "fields": {
                        "raw": {"type": "keyword"},
                        "suggest": {"type": "completion"}
                    }
                },
                "content": {
                    "type": "text",
                    "analyzer": "journal_analyzer"
                },
                "tags": {
                    "type": "keyword"
                },

                # Filterable fields
                "entry_type": {"type": "keyword"},
                "mood_rating": {"type": "integer"},
                "stress_level": {"type": "integer"},
                "energy_level": {"type": "integer"},
                "privacy_scope": {"type": "keyword"},
                "location_site_name": {"type": "keyword"},
                "timestamp": {"type": "date"},

                # User and tenant for security
                "user_id": {"type": "keyword"},
                "tenant_id": {"type": "keyword"},

                # Positive psychology fields
                "gratitude_items": {"type": "text"},
                "achievements": {"type": "text"},
                "learnings": {"type": "text"},

                # Full-text searchable combined field
                "searchable_content": {
                    "type": "text",
                    "analyzer": "journal_analyzer"
                }
            }
        }
    }

    def search_journal_entries(self, user, search_params):
        """
        EXACT SEARCH ALGORITHM: Privacy-enforced full-text search
        REPLACES: Kotlin SocialJournalViewModel.toggleSearch() stub

        Search Algorithm:
        1. Build base query with user and privacy filtering
        2. Apply full-text search across title, content, tags
        3. Add filters for entry type, date range, mood, stress
        4. Execute with highlighting and search suggestions
        5. Post-process for privacy compliance
        6. Generate search analytics and suggestions
        """

        # Privacy-enforced base query
        base_query = {
            "bool": {
                "must": [
                    {"term": {"user_id": str(user.id)}},
                    {"term": {"is_deleted": False}}
                ],
                "should": []
            }
        }

        # Full-text search component
        query_text = search_params.get('query', '')
        if query_text:
            base_query["bool"]["should"] = [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": [
                            "title^3",          # Boost title matches
                            "content^2",        # Boost content matches
                            "tags^2",          # Boost tag matches
                            "gratitude_items",  # Search in gratitude items
                            "achievements",     # Search in achievements
                            "learnings"        # Search in learnings
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                }
            ]

        # Apply filters
        filters = []

        # Entry type filter
        if search_params.get('entry_types'):
            filters.append({
                "terms": {"entry_type": search_params['entry_types']}
            })

        # Date range filter
        if search_params.get('date_from') and search_params.get('date_to'):
            filters.append({
                "range": {
                    "timestamp": {
                        "gte": search_params['date_from'],
                        "lte": search_params['date_to']
                    }
                }
            })

        # Mood range filter
        if search_params.get('mood_range'):
            filters.append({
                "range": {
                    "mood_rating": {
                        "gte": search_params['mood_range']['min'],
                        "lte": search_params['mood_range']['max']
                    }
                }
            })

        # Stress range filter
        if search_params.get('stress_range'):
            filters.append({
                "range": {
                    "stress_level": {
                        "gte": search_params['stress_range']['min'],
                        "lte": search_params['stress_range']['max']
                    }
                }
            })

        # Tag filter
        if search_params.get('tags'):
            filters.append({
                "terms": {"tags": search_params['tags']}
            })

        # Location filter
        if search_params.get('locations'):
            filters.append({
                "terms": {"location_site_name": search_params['locations']}
            })

        # Privacy scope filter
        if search_params.get('privacy_scopes'):
            filters.append({
                "terms": {"privacy_scope": search_params['privacy_scopes']}
            })

        # Add filters to query
        if filters:
            base_query["bool"]["filter"] = filters

        # Build complete search body
        search_body = {
            "query": base_query,
            "highlight": {
                "fields": {
                    "title": {"fragment_size": 100, "number_of_fragments": 1},
                    "content": {"fragment_size": 150, "number_of_fragments": 2},
                    "gratitude_items": {"fragment_size": 80}
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            },
            "sort": self._build_sort_params(search_params.get('sort_by', 'relevance')),
            "aggs": {
                "entry_types": {
                    "terms": {"field": "entry_type", "size": 20}
                },
                "mood_distribution": {
                    "histogram": {"field": "mood_rating", "interval": 1}
                },
                "stress_distribution": {
                    "histogram": {"field": "stress_level", "interval": 1}
                },
                "location_distribution": {
                    "terms": {"field": "location_site_name", "size": 10}
                },
                "tags_distribution": {
                    "terms": {"field": "tags", "size": 15}
                }
            },
            "size": search_params.get('limit', 50),
            "from": search_params.get('offset', 0)
        }

        # Execute search
        try:
            search_results = self.es_client.search(
                index='journal_entries',
                body=search_body
            )

            # Generate search suggestions for empty results
            suggestions = []
            if search_results['hits']['total']['value'] == 0 and query_text:
                suggestions = self._generate_search_suggestions(query_text, user)

            return {
                'results': search_results['hits']['hits'],
                'total_results': search_results['hits']['total']['value'],
                'facets': search_results['aggregations'],
                'search_suggestions': suggestions,
                'search_time_ms': search_results['took'],
                'privacy_filtering_applied': True
            }

        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")
            # Fallback to database search
            return self._fallback_database_search(user, search_params)
```

---

## 🔄 REAL-TIME SYNC & OFFLINE SUPPORT

### Mobile Sync Manager

```python
# apps/journal/services/mobile_sync_manager.py

class JournalMobileSyncManager:
    """
    EXACT IMPLEMENTATION: Offline-first sync with intelligent conflict resolution
    Handles all mobile client synchronization requirements
    """

    def process_mobile_sync_batch(self, user, sync_data):
        """
        ALGORITHM: Bidirectional sync with conflict resolution

        Sync Process:
        1. Validate mobile sync data and user permissions
        2. Detect version conflicts using mobile_id and version fields
        3. Apply automatic resolution rules for non-conflicting changes
        4. Queue complex conflicts for user resolution
        5. Update mobile clients with sync results and server changes
        6. Trigger analytics updates for modified entries
        """

        sync_results = {
            'synced_entries': [],
            'conflicted_entries': [],
            'created_entries': [],
            'deleted_entries': [],
            'errors': []
        }

        for mobile_entry_data in sync_data.get('journal_entries', []):
            try:
                mobile_id = mobile_entry_data.get('mobile_id')
                mobile_version = mobile_entry_data.get('version', 1)

                # Check if entry exists on server
                try:
                    server_entry = JournalEntry.objects.get(
                        mobile_id=mobile_id,
                        user=user
                    )

                    # Version conflict detection
                    if mobile_version != server_entry.version:
                        conflict_resolution = self._resolve_version_conflict(
                            mobile_entry_data, server_entry
                        )
                        sync_results['conflicted_entries'].append(conflict_resolution)
                    else:
                        # No conflict - apply mobile changes
                        updated_entry = self._apply_mobile_changes(mobile_entry_data, server_entry)
                        sync_results['synced_entries'].append({
                            'mobile_id': mobile_id,
                            'server_id': str(updated_entry.id),
                            'new_version': updated_entry.version,
                            'sync_status': 'synced'
                        })

                except JournalEntry.DoesNotExist:
                    # New entry from mobile
                    new_entry = self._create_journal_entry_from_mobile(mobile_entry_data, user)
                    sync_results['created_entries'].append({
                        'mobile_id': mobile_id,
                        'server_id': str(new_entry.id),
                        'version': 1,
                        'sync_status': 'created'
                    })

            except Exception as e:
                sync_results['errors'].append({
                    'mobile_id': mobile_entry_data.get('mobile_id'),
                    'error': str(e)
                })

        # Process media attachments
        media_sync_results = self._sync_media_attachments(user, sync_data.get('media', []))
        sync_results.update(media_sync_results)

        # Trigger background analytics update
        if sync_results['synced_entries'] or sync_results['created_entries']:
            update_user_analytics.delay(user.id)

        return sync_results

    def _resolve_version_conflict(self, mobile_data, server_entry):
        """
        EXACT CONFLICT RESOLUTION ALGORITHM:

        Resolution Rules:
        1. Wellbeing data (mood, stress, energy): Keep most recent timestamp
        2. Content fields (title, content): Attempt merge, flag if impossible
        3. Privacy settings: Always use most restrictive setting
        4. Tags and metadata: Merge unique values
        5. Media attachments: Keep all, mark duplicates
        """

        mobile_timestamp = datetime.fromisoformat(mobile_data['updated_at'])
        server_timestamp = server_entry.updated_at

        if mobile_timestamp > server_timestamp:
            # Mobile is newer - check what can be auto-merged
            auto_merge_result = self._attempt_auto_merge(mobile_data, server_entry)

            if auto_merge_result['success']:
                merged_entry = auto_merge_result['merged_entry']
                merged_entry.version += 1
                merged_entry.save()

                return {
                    'mobile_id': mobile_data['mobile_id'],
                    'resolution_status': 'auto_merged',
                    'merged_entry': self._serialize_entry_for_mobile(merged_entry),
                    'merge_details': auto_merge_result['merge_details']
                }
            else:
                # Requires user resolution
                return {
                    'mobile_id': mobile_data['mobile_id'],
                    'resolution_status': 'user_resolution_required',
                    'mobile_version': mobile_data,
                    'server_version': self._serialize_entry_for_mobile(server_entry),
                    'conflict_fields': auto_merge_result['conflict_fields'],
                    'suggested_resolution': auto_merge_result['suggested_resolution']
                }
        else:
            # Server is newer - send server version to mobile
            return {
                'mobile_id': mobile_data['mobile_id'],
                'resolution_status': 'server_version_newer',
                'server_entry': self._serialize_entry_for_mobile(server_entry),
                'recommendation': 'accept_server_version'
            }

    def _attempt_auto_merge(self, mobile_data, server_entry):
        """
        AUTO-MERGE ALGORITHM for non-conflicting changes:

        Safe to auto-merge:
        - Adding new tags (merge unique tags)
        - Adding new team members
        - Updating metadata that doesn't conflict
        - Privacy scope changes (use most restrictive)
        - Adding new gratitude items or achievements

        Requires user resolution:
        - Conflicting content changes
        - Different mood/stress ratings for same timestamp
        - Conflicting location data
        - Different privacy scope with same restrictiveness level
        """

        merge_details = []
        conflict_fields = []
        merged_data = server_entry.__dict__.copy()

        # Safe merges
        try:
            # Merge tags
            server_tags = set(server_entry.tags or [])
            mobile_tags = set(mobile_data.get('tags', []))
            merged_tags = list(server_tags.union(mobile_tags))
            merged_data['tags'] = merged_tags
            merge_details.append(f"Merged tags: {len(merged_tags)} unique tags")

            # Merge team members
            server_team = set(server_entry.team_members or [])
            mobile_team = set(mobile_data.get('team_members', []))
            merged_team = list(server_team.union(mobile_team))
            merged_data['team_members'] = merged_team

            # Privacy scope (use most restrictive)
            privacy_hierarchy = ['private', 'manager', 'team', 'aggregate_only', 'shared']
            server_privacy_level = privacy_hierarchy.index(server_entry.privacy_scope)
            mobile_privacy_level = privacy_hierarchy.index(mobile_data.get('privacy_scope', 'private'))

            if server_privacy_level <= mobile_privacy_level:
                merged_data['privacy_scope'] = server_entry.privacy_scope
            else:
                merged_data['privacy_scope'] = mobile_data['privacy_scope']

            merge_details.append(f"Privacy scope: {merged_data['privacy_scope']}")

            # Check for conflicts in critical fields
            critical_fields = ['title', 'content', 'mood_rating', 'stress_level']
            for field in critical_fields:
                server_value = getattr(server_entry, field)
                mobile_value = mobile_data.get(field)

                if server_value != mobile_value and mobile_value is not None:
                    conflict_fields.append({
                        'field': field,
                        'server_value': server_value,
                        'mobile_value': mobile_value,
                        'suggested_resolution': self._suggest_field_resolution(field, server_value, mobile_value)
                    })

            # Auto-merge successful if no critical conflicts
            success = len(conflict_fields) == 0

            return {
                'success': success,
                'merged_entry': JournalEntry(**merged_data) if success else None,
                'merge_details': merge_details,
                'conflict_fields': conflict_fields,
                'suggested_resolution': 'accept_merge' if success else 'manual_resolution_required'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'suggested_resolution': 'manual_resolution_required'
            }
```

---

## 🔒 PRIVACY & COMPLIANCE FRAMEWORK

### GDPR-Compliant Privacy Manager

```python
# apps/journal/services/privacy_manager.py

class JournalPrivacyComplianceManager:
    """
    EXACT IMPLEMENTATION: Enterprise privacy controls for wellbeing data
    GDPR, HIPAA-compliant data handling with granular consent management
    """

    def enforce_privacy_filtering(self, queryset, requesting_user, access_context):
        """
        ALGORITHM: Dynamic privacy filtering based on user roles and explicit consent

        Privacy Enforcement Rules:
        1. PRIVATE: Only entry owner can access (always enforced)
        2. MANAGER: Direct manager + explicit consent + wellbeing consent (if applicable)
        3. TEAM: Team member + consent + work-content-only filter
        4. AGGREGATE_ONLY: Only for anonymized organizational analytics
        5. SHARED: Explicitly named users in sharing_permissions list

        Additional Rules:
        - Wellbeing entries (mood, stress, gratitude) require additional consent
        - Crisis-level entries (mood ≤ 2, stress ≥ 4) may bypass privacy for safety
        - Managers see aggregated trends, not individual entry details
        """

        if access_context == 'self_access':
            return queryset  # User can always see their own entries

        privacy_filtered = queryset.none()

        for entry in queryset:
            access_granted = False
            privacy_level = entry.privacy_scope

            # Privacy scope enforcement
            if privacy_level == 'private':
                access_granted = False

            elif privacy_level == 'manager':
                # Check manager relationship and consent
                is_manager = self._verify_manager_relationship(entry.user, requesting_user)
                privacy_settings = JournalPrivacySettings.objects.get(user=entry.user)
                has_manager_consent = privacy_settings.manager_access_consent

                # Additional wellbeing consent check
                is_wellbeing_entry = entry.entry_type in [
                    'MOOD_CHECK_IN', 'STRESS_LOG', 'GRATITUDE', 'THREE_GOOD_THINGS',
                    'DAILY_AFFIRMATIONS', 'PERSONAL_REFLECTION'
                ]

                if is_wellbeing_entry:
                    has_wellbeing_consent = privacy_settings.wellbeing_sharing_consent
                    access_granted = is_manager and has_manager_consent and has_wellbeing_consent
                else:
                    access_granted = is_manager and has_manager_consent

            elif privacy_level == 'team':
                is_team_member = self._verify_team_membership(entry.user, requesting_user)
                privacy_settings = JournalPrivacySettings.objects.get(user=entry.user)
                access_granted = is_team_member and privacy_settings.manager_access_consent

            elif privacy_level == 'shared':
                access_granted = str(requesting_user.id) in entry.sharing_permissions

            elif privacy_level == 'aggregate_only':
                access_granted = access_context == 'organizational_analytics'

            # Crisis intervention override (safety priority)
            if not access_granted and self._is_crisis_entry(entry):
                crisis_settings = JournalPrivacySettings.objects.get(user=entry.user)
                if crisis_settings.crisis_intervention_consent:
                    access_granted = self._verify_crisis_intervention_authority(requesting_user)

            if access_granted:
                # Apply field-level privacy filtering
                filtered_entry = self._apply_field_level_privacy(entry, requesting_user, access_context)
                privacy_filtered = privacy_filtered.union(
                    queryset.filter(id=filtered_entry.id)
                )

        return privacy_filtered

    def _apply_field_level_privacy(self, entry, requesting_user, access_context):
        """
        FIELD-LEVEL PRIVACY: Granular data filtering based on access level

        Field Privacy Rules:
        - Managers: See work content + anonymized wellbeing trends
        - Team: See work content only, no wellbeing data
        - Aggregate: Only contribute to statistics, no individual data
        - Shared: Full access as granted by entry owner
        """

        if requesting_user == entry.user:
            return entry  # Full access to own entries

        # Create filtered copy
        filtered_entry = copy.deepcopy(entry)

        if access_context == 'manager_access':
            # Managers see work content + aggregated wellbeing (no details)
            if entry.entry_type in ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']:
                # Anonymize sensitive fields
                filtered_entry.content = '[Wellbeing entry - details private]'
                filtered_entry.mood_description = None
                filtered_entry.stress_triggers = []
                filtered_entry.coping_strategies = []
                filtered_entry.gratitude_items = []

                # Keep only aggregatable data
                # mood_rating and stress_level kept for trends

        elif access_context == 'team_access':
            # Team sees work content only
            if entry.entry_type in ['MOOD_CHECK_IN', 'STRESS_LOG', 'GRATITUDE', 'PERSONAL_REFLECTION']:
                return None  # No access to wellbeing entries

            # Anonymize personal fields in work entries
            filtered_entry.mood_rating = None
            filtered_entry.stress_level = None
            filtered_entry.energy_level = None

        return filtered_entry

    def handle_offline_conflict_resolution(self, mobile_entries, server_entries):
        """
        OFFLINE CONFLICT RESOLUTION: Handle data conflicts from offline mobile usage

        Conflict Resolution Strategy:
        1. Timestamp-based resolution for wellbeing data (most recent wins)
        2. Content merge for text fields where possible
        3. Additive merge for lists (tags, team_members, achievements)
        4. Privacy scope: Most restrictive wins
        5. Flag complex conflicts for user review
        """

        resolved_entries = []
        user_resolution_required = []

        for mobile_entry in mobile_entries:
            mobile_id = mobile_entry['mobile_id']

            # Find corresponding server entry
            server_entry = next(
                (se for se in server_entries if se.mobile_id == mobile_id),
                None
            )

            if server_entry is None:
                # New entry - no conflict
                resolved_entries.append(mobile_entry)
                continue

            # Automatic resolution attempt
            resolution_result = self._attempt_automatic_resolution(mobile_entry, server_entry)

            if resolution_result['auto_resolvable']:
                resolved_entries.append(resolution_result['resolved_entry'])
            else:
                user_resolution_required.append({
                    'mobile_entry': mobile_entry,
                    'server_entry': server_entry,
                    'conflict_analysis': resolution_result['conflict_analysis'],
                    'suggested_resolutions': resolution_result['suggestions']
                })

        return {
            'resolved_entries': resolved_entries,
            'user_resolution_required': user_resolution_required,
            'auto_resolution_success_rate': len(resolved_entries) / len(mobile_entries) if mobile_entries else 0
        }
```

---

## 🎯 CRITICAL IMPLEMENTATION REQUIREMENTS

### Immediate Backend Development Priorities

1. **Journal Entry Models & APIs** (Week 1-2)
   - Implement complete `JournalEntry` model with all wellbeing fields
   - Create privacy-aware CRUD APIs replacing Kotlin memory storage
   - Implement real-time pattern analysis on entry creation
   - Add comprehensive privacy controls and consent management

2. **Elasticsearch Integration** (Week 2-3)
   - Set up Elasticsearch cluster with journal entry indexing
   - Implement advanced search API replacing Kotlin stub
   - Add privacy-filtered search with highlighting and facets
   - Create search suggestions and analytics

3. **Wellbeing Analytics Engine** (Week 3-4)
   - Move ALL algorithms from Kotlin WellbeingInsightsViewModel to Django
   - Implement mood/stress/energy trend calculations
   - Create positive psychology analytics and insights
   - Build ML-powered recommendation engine

4. **Wellness Education System** (Week 4-5)
   - Implement WHO/CDC content curation pipeline
   - Create contextual content delivery based on journal patterns
   - Build user progress tracking and gamification
   - Add content effectiveness measurement

5. **Mobile Sync Infrastructure** (Week 5-6)
   - Create bidirectional sync APIs for offline-first mobile clients
   - Implement conflict resolution algorithms
   - Add version control and data integrity checks
   - Create sync status tracking and error handling

### Performance & Scalability Requirements

- **API Response Times**: <200ms for content, <500ms for analytics
- **Real-Time Processing**: Journal analysis within 1 second of entry creation
- **Search Performance**: <100ms for basic search, <300ms for complex filtering
- **Offline Support**: Complete CRUD with conflict-free bidirectional sync
- **Privacy Compliance**: Field-level access controls with audit trails
- **Scalability**: 10,000+ users, 1M+ journal entries, 100K+ wellness content items

### Integration with Existing IntelliWiz Backend

- **User Management**: Integrate with existing User, Tenant, and Permission models
- **Site Data**: Link journal entries to existing Sites and Locations
- **MQTT Integration**: Real-time wellness notifications for urgent content delivery
- **Analytics Platform**: Connect with existing business intelligence infrastructure
- **Multi-Tenancy**: Leverage existing tenant isolation and security framework

---

## 📱 SIMPLIFIED KOTLIN FRONTEND SPECIFICATION

### What to Remove from Kotlin (Move to Django)

```kotlin
// DELETE THESE FILES - Logic moves to Django:
// - WellbeingInsightsViewModel.kt (complex analytics)
// - JournalRepositoryImpl.kt (business logic and algorithms)
// - EnhancedJournalSearchViewModel.kt (search algorithms)
// - All pattern recognition and ML logic
// - Complex database queries and aggregations
// - Analytics calculations and insights generation
```

### What to Keep in Kotlin (Pure UI + Offline)

```kotlin
// SIMPLIFIED IMPLEMENTATION - API consumption only:

class JournalViewModel @Inject constructor(
    private val journalApiService: JournalApiService,
    private val offlineCache: JournalOfflineCache
) : ViewModel() {

    // Simple API calls with offline fallback
    suspend fun createEntry(entry: JournalEntryRequest): Result<JournalEntryResponse> {
        return try {
            val response = journalApiService.createEntry(entry)
            offlineCache.cacheEntry(response.journalEntry)
            // Display any triggered wellness content
            displayWellnessContent(response.triggeredWellnessContent)
            Result.success(response)
        } catch (e: Exception) {
            // Queue for offline sync
            offlineCache.queueForSync(entry)
            Result.success(JournalEntryResponse(entry.toLocal()))
        }
    }

    suspend fun getWellbeingInsights(): Result<WellbeingInsights> {
        // Direct API call - no local processing
        return journalApiService.getWellbeingInsights()
    }

    suspend fun searchEntries(query: String, filters: SearchFilters): Result<SearchResults> {
        // Direct API call - no local search logic
        return journalApiService.searchEntries(query, filters)
    }
}

// Simplified data models - just DTOs
data class JournalEntryResponse(
    val journalEntry: JournalEntry,
    val triggeredWellnessContent: List<WellnessContent> = emptyList(),
    val syncStatus: String = "synced"
)

data class WellbeingInsights(
    val overallScore: Double,
    val moodTrends: MoodTrends,
    val stressAnalysis: StressAnalysis,
    val recommendations: List<Recommendation>
)
```

---

## 🏁 IMPLEMENTATION SUCCESS CRITERIA

### Backend Deliverables
- ✅ Complete Django models with privacy controls and multi-tenancy
- ✅ 25+ REST API endpoints for journal and wellness functionality
- ✅ Elasticsearch integration with privacy-filtered search
- ✅ ML-powered analytics and recommendation engines
- ✅ WHO/CDC content curation and delivery system
- ✅ Real-time sync with conflict resolution
- ✅ Enterprise-grade privacy and compliance framework

### Frontend Simplification
- ✅ Remove 4,500+ lines of complex analytics code from Kotlin
- ✅ Replace with simple API consumption and caching
- ✅ Maintain offline-first capabilities for field workers
- ✅ Preserve <3% battery usage with lightweight client
- ✅ Keep industrial UI compliance and user experience quality

### Integration Points
- ✅ Seamless integration with existing IntelliWiz infrastructure
- ✅ Real-time MQTT notifications for urgent wellness content
- ✅ Corporate wellness program APIs for enterprise customers
- ✅ Multi-platform support (iOS, web) using same backend intelligence

**This specification provides the Django backend LLM with EXACT implementation requirements to create a production-ready, enterprise-grade journal and wellness education platform that properly separates concerns between backend intelligence and frontend presentation.**