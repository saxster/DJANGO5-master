"""
Wisdom Conversations Models

Data models for the "Conversations with Wisdom" feature that transforms fragmented
AI mental health interventions into continuous, chronological conversation flows
that read like "one continuous book that flows with no interruption".
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import json

User = get_user_model()


class ConversationThread(models.Model):
    """
    Thematic groupings for wisdom conversations (e.g., stress management journey,
    gratitude practice evolution, crisis recovery narrative)
    """

    THREAD_TYPES = [
        ('gratitude_journey', 'Gratitude Practice Journey'),
        ('stress_management', 'Stress Management Path'),
        ('three_good_things', 'Three Good Things Evolution'),
        ('cbt_cognitive', 'Cognitive Behavioral Insights'),
        ('crisis_recovery', 'Crisis Recovery Narrative'),
        ('workplace_wellness', 'Workplace Wellness Journey'),
        ('motivational_growth', 'Motivational Growth Story'),
        ('preventive_care', 'Preventive Mental Health'),
        ('achievement_celebration', 'Achievement & Milestone Celebrations'),
        ('reflection_insights', 'Deep Reflection Insights'),
    ]

    THREAD_STATUS = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_threads')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True)

    thread_type = models.CharField(max_length=50, choices=THREAD_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text="Brief description of this conversation thread")

    status = models.CharField(max_length=20, choices=THREAD_STATUS, default='active')
    priority_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1=Low, 5=Critical (for crisis threads)"
    )

    # Threading metadata
    conversation_count = models.PositiveIntegerField(default=0)
    first_conversation_date = models.DateTimeField(null=True, blank=True)
    last_conversation_date = models.DateTimeField(null=True, blank=True)

    # Narrative flow settings
    narrative_style = models.CharField(
        max_length=30,
        choices=[
            ('warm_supportive', 'Warm & Supportive'),
            ('professional_clinical', 'Professional Clinical'),
            ('gentle_encouraging', 'Gentle Encouraging'),
            ('motivational_energetic', 'Motivational Energetic'),
            ('crisis_stabilizing', 'Crisis Stabilizing'),
        ],
        default='warm_supportive'
    )

    personalization_data = models.JSONField(
        default=dict,
        help_text="User preferences and effectiveness data for this thread type"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wellness_conversation_threads'
        indexes = [
            models.Index(fields=['user', 'thread_type']),
            models.Index(fields=['status', 'priority_level']),
            models.Index(fields=['last_conversation_date']),
        ]
        unique_together = ['user', 'thread_type']

    def __str__(self):
        return f"{self.user.peoplename} - {self.get_thread_type_display()}"

    def update_conversation_stats(self):
        """Update conversation count and date range from related conversations"""
        conversations = self.wisdom_conversations.all()

        if conversations.exists():
            self.conversation_count = conversations.count()
            self.first_conversation_date = conversations.earliest('conversation_date').conversation_date
            self.last_conversation_date = conversations.latest('conversation_date').conversation_date
        else:
            self.conversation_count = 0
            self.first_conversation_date = None
            self.last_conversation_date = None

        self.save(update_fields=['conversation_count', 'first_conversation_date', 'last_conversation_date'])


class WisdomConversation(models.Model):
    """
    Individual wisdom conversation entries that form the continuous narrative.
    Each entry represents a transformed intervention delivery with contextual bridging.
    """

    CONVERSATION_SOURCES = [
        ('intervention_delivery', 'Mental Health Intervention'),
        ('crisis_response', 'Crisis Response'),
        ('milestone_celebration', 'Milestone Achievement'),
        ('weekly_reflection', 'Weekly Reflection'),
        ('contextual_bridge', 'Contextual Bridge'),
        ('manual_entry', 'Manual Entry'),
    ]

    CONVERSATION_TONES = [
        ('celebratory', 'Celebratory'),
        ('supportive', 'Supportive'),
        ('encouraging', 'Encouraging'),
        ('reflective', 'Reflective'),
        ('motivational', 'Motivational'),
        ('crisis_stabilizing', 'Crisis Stabilizing'),
        ('gentle_guidance', 'Gentle Guidance'),
        ('professional_clinical', 'Professional Clinical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wisdom_conversations')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True)
    thread = models.ForeignKey(
        ConversationThread,
        on_delete=models.CASCADE,
        related_name='wisdom_conversations'
    )

    # Core conversation content
    conversation_text = models.TextField(
        help_text="The main conversational text that feels like a continuous book narrative"
    )
    conversation_date = models.DateTimeField(default=timezone.now)
    conversation_tone = models.CharField(max_length=30, choices=CONVERSATION_TONES)

    # Source tracking
    source_type = models.CharField(max_length=30, choices=CONVERSATION_SOURCES)
    source_intervention_delivery = models.ForeignKey(
        'wellness.InterventionDeliveryLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Source intervention delivery that was transformed into this conversation"
    )
    source_journal_entry = models.ForeignKey(
        'journal.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Journal entry that triggered this conversation"
    )

    # Contextual bridging
    bridges_from_conversation = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bridges_to_conversations',
        help_text="Previous conversation this bridges from for narrative continuity"
    )

    contextual_bridge_text = models.TextField(
        blank=True,
        help_text="Bridging text that connects this conversation to the previous one seamlessly"
    )

    # Conversation metadata
    word_count = models.PositiveIntegerField(default=0)
    estimated_reading_time_seconds = models.PositiveIntegerField(default=0)

    # Personalization and effectiveness
    personalization_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How well personalized this conversation is (0.0-1.0)"
    )

    conversation_metadata = models.JSONField(
        default=dict,
        help_text="Additional metadata like intervention techniques used, keywords, etc."
    )

    # Narrative flow control
    sequence_number = models.PositiveIntegerField(
        help_text="Position in the chronological conversation sequence for this thread"
    )
    is_milestone_conversation = models.BooleanField(
        default=False,
        help_text="Marks significant conversations (achievements, breakthroughs, etc.)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wellness_wisdom_conversations'
        indexes = [
            models.Index(fields=['user', 'conversation_date']),
            models.Index(fields=['thread', 'sequence_number']),
            models.Index(fields=['source_type', 'conversation_date']),
            models.Index(fields=['is_milestone_conversation']),
        ]
        ordering = ['thread', 'sequence_number']
        unique_together = ['thread', 'sequence_number']

    def __str__(self):
        return f"Wisdom Conversation {self.sequence_number} - {self.thread.title}"

    def save(self, *args, **kwargs):
        # Auto-calculate word count and reading time
        if self.conversation_text:
            words = len(self.conversation_text.split())
            self.word_count = words
            # Average reading speed: 200 words per minute
            self.estimated_reading_time_seconds = int((words / 200) * 60)

        # Auto-assign sequence number if not provided
        if not self.sequence_number:
            last_conversation = WisdomConversation.objects.filter(
                thread=self.thread
            ).order_by('-sequence_number').first()

            self.sequence_number = (last_conversation.sequence_number + 1) if last_conversation else 1

        super().save(*args, **kwargs)

        # Update thread statistics
        if self.thread:
            self.thread.update_conversation_stats()

    def get_previous_conversation(self):
        """Get the immediately previous conversation in this thread"""
        return WisdomConversation.objects.filter(
            thread=self.thread,
            sequence_number__lt=self.sequence_number
        ).order_by('-sequence_number').first()

    def get_next_conversation(self):
        """Get the immediately next conversation in this thread"""
        return WisdomConversation.objects.filter(
            thread=self.thread,
            sequence_number__gt=self.sequence_number
        ).order_by('sequence_number').first()


class ConversationEngagement(models.Model):
    """
    Analytics model tracking user engagement with wisdom conversations
    for continuous improvement and personalization
    """

    ENGAGEMENT_TYPES = [
        ('view', 'Viewed'),
        ('read_complete', 'Read Completely'),
        ('bookmark', 'Bookmarked'),
        ('share', 'Shared'),
        ('reflection_note', 'Added Reflection Note'),
        ('positive_feedback', 'Positive Feedback'),
        ('request_more', 'Requested More'),
        ('skip', 'Skipped'),
        ('negative_feedback', 'Negative Feedback'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_engagements')
    conversation = models.ForeignKey(
        WisdomConversation,
        on_delete=models.CASCADE,
        related_name='engagements'
    )

    engagement_type = models.CharField(max_length=30, choices=ENGAGEMENT_TYPES)
    engagement_date = models.DateTimeField(auto_now_add=True)

    # Detailed engagement metrics
    time_spent_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Time user spent reading/engaging with this conversation"
    )

    scroll_percentage = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Percentage of conversation text scrolled through"
    )

    # User feedback
    effectiveness_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="User rating of conversation effectiveness (1-5)"
    )

    user_reflection_note = models.TextField(
        blank=True,
        help_text="Optional user reflection or notes about this conversation"
    )

    # Context information
    device_type = models.CharField(
        max_length=20,
        choices=[('mobile', 'Mobile'), ('tablet', 'Tablet'), ('desktop', 'Desktop')],
        default='mobile'
    )

    access_context = models.CharField(
        max_length=30,
        choices=[
            ('routine_check', 'Routine Check'),
            ('notification_prompt', 'Notification Prompt'),
            ('crisis_support', 'Crisis Support'),
            ('milestone_celebration', 'Milestone Celebration'),
            ('search_discovery', 'Search Discovery'),
            ('manual_browse', 'Manual Browse'),
        ],
        default='routine_check'
    )

    engagement_metadata = models.JSONField(
        default=dict,
        help_text="Additional engagement context and analytics data"
    )

    class Meta:
        db_table = 'wellness_conversation_engagements'
        indexes = [
            models.Index(fields=['user', 'engagement_date']),
            models.Index(fields=['conversation', 'engagement_type']),
            models.Index(fields=['effectiveness_rating']),
            models.Index(fields=['access_context', 'engagement_date']),
        ]

    def __str__(self):
        return f"{self.user.peoplename} - {self.get_engagement_type_display()} - {self.conversation.sequence_number}"

    @classmethod
    def get_conversation_effectiveness_score(cls, conversation):
        """Calculate effectiveness score for a conversation based on engagements"""
        engagements = cls.objects.filter(conversation=conversation)

        if not engagements.exists():
            return 0.0

        # Weight different engagement types
        engagement_weights = {
            'view': 0.1,
            'read_complete': 0.3,
            'bookmark': 0.2,
            'share': 0.25,
            'reflection_note': 0.3,
            'positive_feedback': 0.4,
            'request_more': 0.35,
            'skip': -0.2,
            'negative_feedback': -0.3,
        }

        total_score = 0.0
        total_engagements = 0

        for engagement in engagements:
            weight = engagement_weights.get(engagement.engagement_type, 0.0)
            total_score += weight
            total_engagements += 1

            # Factor in effectiveness rating if available
            if engagement.effectiveness_rating:
                rating_score = (engagement.effectiveness_rating - 3) * 0.1  # Convert 1-5 to -0.2 to 0.2
                total_score += rating_score

        # Normalize to 0.0-1.0 range
        if total_engagements > 0:
            avg_score = total_score / total_engagements
            return max(0.0, min(1.0, (avg_score + 0.5)))  # Shift and clamp to 0-1

        return 0.0


class ConversationBookmark(models.Model):
    """
    User bookmarks for important wisdom conversations
    """

    BOOKMARK_CATEGORIES = [
        ('breakthrough', 'Breakthrough Moment'),
        ('inspiration', 'Inspiration'),
        ('practical_tool', 'Practical Tool'),
        ('crisis_help', 'Crisis Help'),
        ('milestone', 'Personal Milestone'),
        ('daily_reminder', 'Daily Reminder'),
        ('professional_reference', 'Professional Reference'),
        ('share_worthy', 'Worth Sharing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_bookmarks')
    conversation = models.ForeignKey(
        WisdomConversation,
        on_delete=models.CASCADE,
        related_name='bookmarks'
    )

    category = models.CharField(max_length=30, choices=BOOKMARK_CATEGORIES, default='inspiration')
    personal_note = models.TextField(
        blank=True,
        help_text="Personal note about why this conversation was bookmarked"
    )

    reminder_enabled = models.BooleanField(
        default=False,
        help_text="Whether to send periodic reminders about this bookmarked conversation"
    )
    reminder_frequency_days = models.PositiveIntegerField(
        default=30,
        help_text="How often to remind user about this bookmark (in days)"
    )
    last_reminder_sent = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wellness_conversation_bookmarks'
        indexes = [
            models.Index(fields=['user', 'category']),
            models.Index(fields=['reminder_enabled', 'last_reminder_sent']),
        ]
        unique_together = ['user', 'conversation']

    def __str__(self):
        return f"{self.user.peoplename} - Bookmark: {self.conversation.thread.title} #{self.conversation.sequence_number}"