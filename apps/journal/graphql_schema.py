"""
GraphQL Schema for Journal & Wellness System

Comprehensive GraphQL implementation for efficient mobile client data fetching:
- Privacy-aware queries with field-level permissions
- Optimized resolvers with dataloader patterns
- Real-time subscriptions for wellness content delivery
- Mutation operations with automatic pattern analysis
- Nested queries for related data fetching
"""

import graphene
from graphene_django import DjangoObjectType
from graphql_jwt.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta
import logging

from apps.journal.models import JournalEntry, JournalMediaAttachment, JournalPrivacySettings
from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from apps.journal.permissions import check_journal_permission, check_analytics_permission
from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer
from apps.journal.ml.analytics_engine import WellbeingAnalyticsEngine

logger = logging.getLogger(__name__)


# GraphQL Types
class JournalEntryType(DjangoObjectType):
    """GraphQL type for journal entries with privacy controls"""

    wellbeing_summary = graphene.JSONString()
    privacy_display = graphene.String()
    entry_type_display = graphene.String()
    is_wellbeing_entry = graphene.Boolean()
    has_wellbeing_metrics = graphene.Boolean()
    can_user_edit = graphene.Boolean()

    class Meta:
        model = JournalEntry
        fields = (
            'id', 'title', 'subtitle', 'content', 'entry_type', 'timestamp',
            'duration_minutes', 'privacy_scope', 'mood_rating', 'mood_description',
            'stress_level', 'energy_level', 'stress_triggers', 'coping_strategies',
            'gratitude_items', 'daily_goals', 'affirmations', 'achievements',
            'learnings', 'challenges', 'location_site_name', 'tags',
            'priority', 'severity', 'is_bookmarked', 'is_draft',
            'created_at', 'updated_at'
        )

    def resolve_wellbeing_summary(self, info):
        """Resolve wellbeing metrics summary"""
        if not self.has_wellbeing_metrics:
            return None

        summary = {}
        if self.mood_rating:
            summary['mood'] = f"{self.mood_rating}/10"
        if self.stress_level:
            summary['stress'] = f"{self.stress_level}/5"
        if self.energy_level:
            summary['energy'] = f"{self.energy_level}/10"

        return summary

    def resolve_privacy_display(self, info):
        """Resolve privacy scope display name"""
        return dict(JournalEntry.JournalPrivacyScope.choices).get(self.privacy_scope, self.privacy_scope)

    def resolve_entry_type_display(self, info):
        """Resolve entry type display name"""
        return dict(JournalEntry.JournalEntryType.choices).get(self.entry_type, self.entry_type)

    def resolve_is_wellbeing_entry(self, info):
        """Check if entry is wellbeing-focused"""
        return self.is_wellbeing_entry

    def resolve_has_wellbeing_metrics(self, info):
        """Check if entry has wellbeing metrics"""
        return self.has_wellbeing_metrics

    def resolve_can_user_edit(self, info):
        """Check if current user can edit this entry"""
        user = info.context.user
        if not user.is_authenticated:
            return False

        try:
            permission_result = check_journal_permission(user, self, 'update')
            return permission_result['allowed']
        except PermissionDenied:
            return False


class JournalMediaAttachmentType(DjangoObjectType):
    """GraphQL type for journal media attachments"""

    file_url = graphene.String()
    file_size_display = graphene.String()

    class Meta:
        model = JournalMediaAttachment
        fields = (
            'id', 'media_type', 'original_filename', 'mime_type',
            'file_size', 'caption', 'display_order', 'is_hero_image',
            'created_at', 'updated_at'
        )

    def resolve_file_url(self, info):
        """Resolve full file URL"""
        if self.file:
            request = info.context
            if request:
                return request.build_absolute_uri(self.file.url)
            return self.file.url
        return None

    def resolve_file_size_display(self, info):
        """Resolve human-readable file size"""
        if self.file_size:
            if self.file_size > 1024 * 1024:  # MB
                return f"{self.file_size / (1024 * 1024):.1f} MB"
            elif self.file_size > 1024:  # KB
                return f"{self.file_size / 1024:.1f} KB"
            else:
                return f"{self.file_size} bytes"
        return "Unknown"


class WellnessContentType(DjangoObjectType):
    """GraphQL type for wellness content"""

    category_display = graphene.String()
    content_level_display = graphene.String()
    evidence_level_display = graphene.String()
    is_high_evidence = graphene.Boolean()
    effectiveness_score = graphene.Float()

    class Meta:
        model = WellnessContent
        fields = (
            'id', 'title', 'summary', 'content', 'category', 'delivery_context',
            'content_level', 'evidence_level', 'tags', 'workplace_specific',
            'field_worker_relevant', 'action_tips', 'key_takeaways',
            'source_name', 'priority_score', 'estimated_reading_time',
            'complexity_score', 'is_active', 'created_at'
        )

    def resolve_category_display(self, info):
        """Resolve category display name"""
        return dict(WellnessContent.WellnessContentCategory.choices).get(self.category, self.category)

    def resolve_content_level_display(self, info):
        """Resolve content level display name"""
        return dict(WellnessContent.WellnessContentLevel.choices).get(self.content_level, self.content_level)

    def resolve_evidence_level_display(self, info):
        """Resolve evidence level display name"""
        return dict(WellnessContent.EvidenceLevel.choices).get(self.evidence_level, self.evidence_level)

    def resolve_is_high_evidence(self, info):
        """Check if content has high evidence level"""
        return self.is_high_evidence

    def resolve_effectiveness_score(self, info):
        """Calculate content effectiveness score"""
        interactions = self.interactions.all()
        if not interactions:
            return 0.0

        total = interactions.count()
        positive = interactions.filter(
            interaction_type__in=['completed', 'bookmarked', 'acted_upon']
        ).count()

        return round(positive / total, 3) if total > 0 else 0.0


class WellnessUserProgressType(DjangoObjectType):
    """GraphQL type for user wellness progress"""

    completion_rate = graphene.Float()
    is_active_user = graphene.Boolean()
    achievement_count = graphene.Int()
    next_milestone = graphene.JSONString()

    class Meta:
        model = WellnessUserProgress
        fields = (
            'current_streak', 'longest_streak', 'total_content_viewed',
            'total_content_completed', 'total_score', 'preferred_content_level',
            'enabled_categories', 'daily_tip_enabled', 'contextual_delivery_enabled',
            'achievements_earned', 'last_activity_date'
        )

    def resolve_completion_rate(self, info):
        """Calculate completion rate"""
        return self.completion_rate

    def resolve_is_active_user(self, info):
        """Check if user is recently active"""
        return self.is_active_user

    def resolve_achievement_count(self, info):
        """Get count of achievements"""
        return len(self.achievements_earned)

    def resolve_next_milestone(self, info):
        """Get next milestone information"""
        # This would integrate with the milestone calculation from serializers
        return {}  # Placeholder


class WellbeingAnalyticsType(graphene.ObjectType):
    """GraphQL type for wellbeing analytics"""

    overall_score = graphene.Float()
    mood_trends = graphene.JSONString()
    stress_analysis = graphene.JSONString()
    energy_trends = graphene.JSONString()
    recommendations = graphene.JSONString()
    analysis_metadata = graphene.JSONString()


class PersonalizedContentType(graphene.ObjectType):
    """GraphQL type for personalized content recommendations"""

    content = graphene.Field(WellnessContentType)
    personalization_score = graphene.Float()
    recommendation_reason = graphene.String()
    predicted_effectiveness = graphene.Float()
    estimated_value = graphene.Float()


# Input Types for Mutations
class JournalEntryInput(graphene.InputObjectType):
    """Input type for creating/updating journal entries"""

    title = graphene.String(required=True)
    subtitle = graphene.String()
    content = graphene.String()
    entry_type = graphene.String(required=True)
    mood_rating = graphene.Int()
    mood_description = graphene.String()
    stress_level = graphene.Int()
    energy_level = graphene.Int()
    stress_triggers = graphene.List(graphene.String)
    coping_strategies = graphene.List(graphene.String)
    gratitude_items = graphene.List(graphene.String)
    daily_goals = graphene.List(graphene.String)
    affirmations = graphene.List(graphene.String)
    achievements = graphene.List(graphene.String)
    learnings = graphene.List(graphene.String)
    challenges = graphene.List(graphene.String)
    location_site_name = graphene.String()
    location_address = graphene.String()
    location_coordinates = graphene.JSONString()
    team_members = graphene.List(graphene.String)
    tags = graphene.List(graphene.String)
    priority = graphene.String()
    severity = graphene.String()
    completion_rate = graphene.Float()
    efficiency_score = graphene.Float()
    quality_score = graphene.Float()
    items_processed = graphene.Int()
    is_bookmarked = graphene.Boolean()
    is_draft = graphene.Boolean()
    privacy_scope = graphene.String()
    sharing_permissions = graphene.List(graphene.String)
    mobile_id = graphene.String()


class WellnessInteractionInput(graphene.InputObjectType):
    """Input type for wellness content interactions"""

    content_id = graphene.String(required=True)
    interaction_type = graphene.String(required=True)
    delivery_context = graphene.String()
    time_spent_seconds = graphene.Int()
    completion_percentage = graphene.Int()
    user_rating = graphene.Int()
    user_feedback = graphene.String()
    action_taken = graphene.Boolean()


# Query Class
class JournalWellnessQueries(graphene.ObjectType):
    """GraphQL queries for journal and wellness system"""

    # Journal Entry Queries
    journal_entries = graphene.List(
        JournalEntryType,
        entry_types=graphene.List(graphene.String),
        date_from=graphene.DateTime(),
        date_to=graphene.DateTime(),
        mood_min=graphene.Int(),
        mood_max=graphene.Int(),
        stress_min=graphene.Int(),
        stress_max=graphene.Int(),
        tags=graphene.List(graphene.String),
        limit=graphene.Int(default_value=50)
    )

    journal_entry = graphene.Field(
        JournalEntryType,
        id=graphene.String(required=True)
    )

    # Wellness Content Queries
    wellness_content = graphene.List(
        WellnessContentType,
        category=graphene.String(),
        content_level=graphene.String(),
        evidence_level=graphene.String(),
        workplace_specific=graphene.Boolean(),
        limit=graphene.Int(default_value=20)
    )

    daily_wellness_tip = graphene.Field(
        WellnessContentType,
        preferred_category=graphene.String()
    )

    personalized_wellness_content = graphene.List(
        PersonalizedContentType,
        limit=graphene.Int(default_value=5),
        categories=graphene.List(graphene.String),
        exclude_viewed=graphene.Boolean(default_value=True)
    )

    # User Progress Queries
    my_wellness_progress = graphene.Field(WellnessUserProgressType)

    # Analytics Queries
    my_wellbeing_analytics = graphene.Field(
        WellbeingAnalyticsType,
        days=graphene.Int(default_value=30)
    )

    # Privacy Settings Query
    my_privacy_settings = graphene.Field('apps.journal.graphql_schema.JournalPrivacySettingsType')

    @login_required
    def resolve_journal_entries(self, info, **kwargs):
        """Resolve journal entries with privacy filtering"""
        user = info.context.user

        # Base queryset with privacy filtering
        queryset = JournalEntry.objects.filter(
            user=user,
            tenant=user.tenant,
            is_deleted=False
        ).order_by('-timestamp')

        # Apply filters
        entry_types = kwargs.get('entry_types')
        if entry_types:
            queryset = queryset.filter(entry_type__in=entry_types)

        date_from = kwargs.get('date_from')
        date_to = kwargs.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(timestamp__range=[date_from, date_to])

        # Wellbeing filters (only if user consented)
        try:
            privacy_settings = user.journal_privacy_settings
            if privacy_settings.analytics_consent:
                mood_min = kwargs.get('mood_min')
                mood_max = kwargs.get('mood_max')
                if mood_min and mood_max:
                    queryset = queryset.filter(mood_rating__range=[mood_min, mood_max])

                stress_min = kwargs.get('stress_min')
                stress_max = kwargs.get('stress_max')
                if stress_min and stress_max:
                    queryset = queryset.filter(stress_level__range=[stress_min, stress_max])

        except JournalPrivacySettings.DoesNotExist:
            pass

        # Tag filtering
        tags = kwargs.get('tags')
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])

        # Apply limit
        limit = kwargs.get('limit', 50)
        return queryset[:limit]

    @login_required
    def resolve_journal_entry(self, info, id):
        """Resolve single journal entry with permission check"""
        user = info.context.user

        try:
            journal_entry = JournalEntry.objects.get(id=id)

            # Check permission
            permission_result = check_journal_permission(user, journal_entry, 'read')
            if not permission_result['allowed']:
                raise PermissionDenied("Access denied to this journal entry")

            return journal_entry

        except JournalEntry.DoesNotExist:
            return None

    @login_required
    def resolve_wellness_content(self, info, **kwargs):
        """Resolve wellness content with filtering"""
        user = info.context.user

        queryset = WellnessContent.objects.filter(
            tenant=user.tenant,
            is_active=True
        ).order_by('-priority_score')

        # Apply filters
        category = kwargs.get('category')
        if category:
            queryset = queryset.filter(category=category)

        content_level = kwargs.get('content_level')
        if content_level:
            queryset = queryset.filter(content_level=content_level)

        evidence_level = kwargs.get('evidence_level')
        if evidence_level:
            queryset = queryset.filter(evidence_level=evidence_level)

        workplace_specific = kwargs.get('workplace_specific')
        if workplace_specific is not None:
            queryset = queryset.filter(workplace_specific=workplace_specific)

        limit = kwargs.get('limit', 20)
        return queryset[:limit]

    @login_required
    def resolve_daily_wellness_tip(self, info, **kwargs):
        """Resolve personalized daily wellness tip"""
        user = info.context.user

        try:
            from apps.wellness.services.content_delivery import WelnessTipSelector

            # Analyze recent patterns
            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=7),
                is_deleted=False
            ).order_by('-timestamp')

            patterns = {}
            if recent_entries.exists():
                mood_entries = recent_entries.exclude(mood_rating__isnull=True)
                if mood_entries.exists():
                    patterns['current_mood'] = mood_entries.first().mood_rating

                stress_entries = recent_entries.exclude(stress_level__isnull=True)
                if stress_entries.exists():
                    patterns['current_stress'] = stress_entries.first().stress_level

            # Get recently viewed content IDs
            recent_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                interaction_date__gte=timezone.now() - timedelta(days=7)
            ).values_list('content_id', flat=True)

            # Select tip
            tip_selector = WelnessTipSelector()
            daily_tip = tip_selector.select_personalized_tip(
                user, patterns, list(recent_interactions)
            )

            return daily_tip

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to resolve daily wellness tip for user {user.id}: {e}")
            return None

    @login_required
    def resolve_personalized_wellness_content(self, info, **kwargs):
        """Resolve personalized wellness content recommendations"""
        user = info.context.user

        try:
            from apps.wellness.services.content_delivery import (
                WellnessRecommendationEngine, UserProfileBuilder
            )

            # Build user profile
            profile_builder = UserProfileBuilder()
            user_profile = profile_builder.build_comprehensive_profile(user)

            # Generate recommendations
            recommendation_engine = WellnessRecommendationEngine()
            recommendations = recommendation_engine.generate_recommendations(
                user_profile=user_profile,
                limit=kwargs.get('limit', 5),
                diversity_constraint=True,
                exclude_recent_views=kwargs.get('exclude_viewed', True)
            )

            # Convert to GraphQL type
            personalized_content = []
            for rec in recommendations:
                personalized_content.append(
                    PersonalizedContentType(
                        content=rec['content'],
                        personalization_score=rec['score'],
                        recommendation_reason=rec['reason'],
                        predicted_effectiveness=rec['effectiveness'],
                        estimated_value=rec['value_score']
                    )
                )

            return personalized_content

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to resolve personalized content for user {user.id}: {e}")
            return []

    @login_required
    def resolve_my_wellness_progress(self, info):
        """Resolve user's wellness progress"""
        user = info.context.user

        try:
            return user.wellness_progress
        except WellnessUserProgress.DoesNotExist:
            return None

    @login_required
    def resolve_my_wellbeing_analytics(self, info, days=30):
        """Resolve user's wellbeing analytics"""
        user = info.context.user

        try:
            # Check analytics permission
            permission_result = check_analytics_permission(user, 'own')
            if not permission_result['allowed']:
                raise PermissionDenied("Analytics access denied")

            # Get journal entries for analysis
            journal_entries = list(JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=days),
                is_deleted=False
            ).order_by('timestamp'))

            if len(journal_entries) < 3:
                return WellbeingAnalyticsType(
                    overall_score=0.0,
                    analysis_metadata={'insufficient_data': True}
                )

            # Generate analytics
            analytics_engine = WellbeingAnalyticsEngine()

            mood_trends = analytics_engine.calculate_mood_trends(journal_entries)
            stress_analysis = analytics_engine.calculate_stress_trends(journal_entries)
            energy_trends = analytics_engine.calculate_energy_trends(journal_entries)
            recommendations = analytics_engine.generate_recommendations(
                mood_trends, stress_analysis, energy_trends, journal_entries
            )
            wellbeing_score = analytics_engine.calculate_overall_wellbeing_score(
                mood_trends, stress_analysis, energy_trends, journal_entries
            )

            return WellbeingAnalyticsType(
                overall_score=wellbeing_score['overall_score'],
                mood_trends=mood_trends,
                stress_analysis=stress_analysis,
                energy_trends=energy_trends,
                recommendations=recommendations,
                analysis_metadata={
                    'analysis_date': timezone.now().isoformat(),
                    'data_points': len(journal_entries),
                    'algorithm_version': '2.1.0'
                }
            )

        except PermissionDenied:
            raise
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to resolve analytics for user {user.id}: {e}")
            return None


class JournalPrivacySettingsType(DjangoObjectType):
    """GraphQL type for privacy settings"""

    class Meta:
        model = JournalPrivacySettings
        fields = (
            'default_privacy_scope', 'wellbeing_sharing_consent',
            'manager_access_consent', 'analytics_consent',
            'crisis_intervention_consent', 'data_retention_days',
            'auto_delete_enabled', 'consent_timestamp', 'updated_at'
        )


# Mutations
class CreateJournalEntry(graphene.Mutation):
    """Create new journal entry with pattern analysis"""

    class Arguments:
        entry_data = JournalEntryInput(required=True)

    journal_entry = graphene.Field(JournalEntryType)
    pattern_analysis = graphene.JSONString()
    triggered_wellness_content = graphene.List(WellnessContentType)
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)

    @login_required
    def mutate(self, info, entry_data):
        """Create journal entry with automatic processing"""
        user = info.context.user

        try:
            # Prepare entry data
            entry_kwargs = {
                'user': user,
                'tenant': user.tenant,
                'timestamp': timezone.now(),
                **entry_data
            }

            # Create entry
            journal_entry = JournalEntry.objects.create(**entry_kwargs)

            # Trigger pattern analysis
            analyzer = JournalPatternAnalyzer()
            analysis_result = analyzer.analyze_entry_for_immediate_action(journal_entry)

            # Get contextual wellness content if needed
            triggered_content = []
            if analysis_result['urgency_score'] >= 2:
                from apps.wellness.services.content_delivery import WellnessContentDeliveryService

                delivery_service = WellnessContentDeliveryService()
                triggered_content = delivery_service.get_contextual_content(
                    user, journal_entry, analysis_result
                )

            # Schedule background analytics update
            from background_tasks.journal_wellness_tasks import update_user_analytics
            update_user_analytics.delay(user.id, str(journal_entry.id))

            logger.info(f"Created journal entry {journal_entry.id} via GraphQL")

            return CreateJournalEntry(
                journal_entry=journal_entry,
                pattern_analysis=analysis_result,
                triggered_wellness_content=triggered_content,
                success=True,
                errors=[]
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to create journal entry via GraphQL: {e}")
            return CreateJournalEntry(
                success=False,
                errors=[str(e)]
            )


class TrackWellnessInteraction(graphene.Mutation):
    """Track wellness content interaction"""

    class Arguments:
        interaction_data = WellnessInteractionInput(required=True)

    interaction_id = graphene.String()
    engagement_score = graphene.Int()
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)

    @login_required
    def mutate(self, info, interaction_data):
        """Track wellness content interaction"""
        user = info.context.user

        try:
            content = WellnessContent.objects.get(id=interaction_data.content_id)

            # Create interaction
            interaction = WellnessContentInteraction.objects.create(
                user=user,
                content=content,
                interaction_type=interaction_data.interaction_type,
                delivery_context=interaction_data.get('delivery_context', 'manual'),
                time_spent_seconds=interaction_data.get('time_spent_seconds'),
                completion_percentage=interaction_data.get('completion_percentage'),
                user_rating=interaction_data.get('user_rating'),
                user_feedback=interaction_data.get('user_feedback', ''),
                action_taken=interaction_data.get('action_taken', False)
            )

            # Schedule content effectiveness update
            from background_tasks.journal_wellness_tasks import update_content_effectiveness_metrics
            update_content_effectiveness_metrics.delay(str(content.id))

            return TrackWellnessInteraction(
                interaction_id=str(interaction.id),
                engagement_score=interaction.engagement_score,
                success=True,
                errors=[]
            )

        except WellnessContent.DoesNotExist:
            return TrackWellnessInteraction(
                success=False,
                errors=['Wellness content not found']
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to track wellness interaction: {e}")
            return TrackWellnessInteraction(
                success=False,
                errors=[str(e)]
            )


class UpdatePrivacySettings(graphene.Mutation):
    """Update user's privacy settings"""

    class Arguments:
        wellbeing_sharing_consent = graphene.Boolean()
        manager_access_consent = graphene.Boolean()
        analytics_consent = graphene.Boolean()
        crisis_intervention_consent = graphene.Boolean()
        data_retention_days = graphene.Int()
        auto_delete_enabled = graphene.Boolean()

    privacy_settings = graphene.Field(JournalPrivacySettingsType)
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)

    @login_required
    def mutate(self, info, **kwargs):
        """Update privacy settings"""
        user = info.context.user

        try:
            # Get or create privacy settings
            privacy_settings, created = JournalPrivacySettings.objects.get_or_create(
                user=user,
                defaults={'consent_timestamp': timezone.now()}
            )

            # Update fields
            for field, value in kwargs.items():
                if value is not None:
                    setattr(privacy_settings, field, value)

            privacy_settings.save()

            logger.info(f"Updated privacy settings for user {user.id}")

            return UpdatePrivacySettings(
                privacy_settings=privacy_settings,
                success=True,
                errors=[]
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to update privacy settings for user {user.id}: {e}")
            return UpdatePrivacySettings(
                success=False,
                errors=[str(e)]
            )


# Mutation Class
class JournalWellnessMutations(graphene.ObjectType):
    """GraphQL mutations for journal and wellness system"""

    create_journal_entry = CreateJournalEntry.Field()
    track_wellness_interaction = TrackWellnessInteraction.Field()
    update_privacy_settings = UpdatePrivacySettings.Field()


# Subscription Class (for real-time wellness content delivery)
class JournalWellnessSubscriptions(graphene.ObjectType):
    """GraphQL subscriptions for real-time updates"""

    wellness_content_delivered = graphene.Field(
        WellnessContentType,
        description="Subscribe to wellness content deliveries"
    )

    crisis_alert = graphene.JSONString(
        description="Subscribe to crisis intervention alerts"
    )

    # TODO: Implement subscription resolvers
    # These would integrate with Django Channels or similar WebSocket solution