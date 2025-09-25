"""
Recommendation engine models for intelligent navigation suggestions
"""
import json
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta

User = get_user_model()


class UserBehaviorProfile(models.Model):
    """User behavior profile for personalized recommendations"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='behavior_profile'
    )
    
    # Navigation patterns
    preferred_pages = models.JSONField(default=dict, help_text="Page URLs and visit frequency")
    common_paths = models.JSONField(default=list, help_text="Common navigation paths")
    session_duration_avg = models.FloatField(default=0.0)
    click_patterns = models.JSONField(default=dict, help_text="Common click locations and elements")
    
    # Device and context preferences
    preferred_device_type = models.CharField(
        max_length=20, 
        choices=[('desktop', 'Desktop'), ('mobile', 'Mobile'), ('tablet', 'Tablet')],
        default='desktop'
    )
    timezone_preference = models.CharField(max_length=50, default='UTC')
    language_preference = models.CharField(max_length=10, default='en')
    
    # Behavioral characteristics
    exploration_tendency = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="0.0 = routine user, 1.0 = exploratory user"
    )
    task_completion_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    feature_adoption_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Content preferences
    preferred_content_types = models.JSONField(default=list)
    interaction_frequency = models.JSONField(default=dict)
    
    # Calculated metrics
    similarity_vector = models.JSONField(default=list, help_text="Vector for similarity calculations")
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_user_behavior_profile'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['preferred_device_type']),
            models.Index(fields=['last_updated']),
        ]
    
    def __str__(self):
        return f"Behavior Profile for {self.user.username}"
    
    def update_profile(self, session_data):
        """Update profile based on session data"""
        # Update preferred pages
        page_url = session_data.get('page_url', '')
        if page_url:
            if page_url in self.preferred_pages:
                self.preferred_pages[page_url] += 1
            else:
                self.preferred_pages[page_url] = 1
        
        # Update session duration
        duration = session_data.get('duration_seconds', 0)
        if duration > 0:
            # Calculate running average
            current_avg = self.session_duration_avg or 0
            self.session_duration_avg = (current_avg + duration) / 2
        
        # Update device preference
        device_type = session_data.get('device_type')
        if device_type:
            self.preferred_device_type = device_type
        
        self.save()
    
    def get_top_pages(self, limit=5):
        """Get user's most visited pages"""
        if not self.preferred_pages:
            return []
        
        sorted_pages = sorted(
            self.preferred_pages.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        return [page[0] for page in sorted_pages[:limit]]
    
    def calculate_similarity_vector(self):
        """Calculate similarity vector for collaborative filtering"""
        # Create a vector based on user behavior characteristics
        vector = [
            self.exploration_tendency,
            self.task_completion_rate,
            self.feature_adoption_rate,
            len(self.preferred_pages),
            self.session_duration_avg / 3600 if self.session_duration_avg else 0,  # normalize to hours
        ]
        
        # Add device type encoding
        device_encoding = {'desktop': 1.0, 'mobile': 0.5, 'tablet': 0.75}
        vector.append(device_encoding.get(self.preferred_device_type, 0.0))
        
        self.similarity_vector = vector
        self.save(update_fields=['similarity_vector'])
        return vector


class NavigationRecommendation(models.Model):
    """Recommendations for navigation improvements"""
    
    RECOMMENDATION_TYPES = [
        ('page_suggestion', 'Page Suggestion'),
        ('menu_optimization', 'Menu Optimization'),
        ('search_enhancement', 'Search Enhancement'),
        ('layout_improvement', 'Layout Improvement'),
        ('content_personalization', 'Content Personalization'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    recommendation_type = models.CharField(max_length=30, choices=RECOMMENDATION_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Target specification
    target_page = models.URLField(blank=True, null=True)
    target_element = models.CharField(max_length=200, blank=True)
    target_user_segment = models.JSONField(default=dict)
    
    # Recommendation data
    suggested_action = models.TextField()
    implementation_details = models.JSONField(default=dict)
    expected_impact = models.TextField()
    
    # Supporting data
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in the recommendation (0.0 - 1.0)"
    )
    supporting_data = models.JSONField(default=dict)
    user_behavior_data = models.JSONField(default=dict)
    
    # Priority and status
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('implemented', 'Implemented'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'core_navigation_recommendation'
        ordering = ['-priority', '-confidence_score', '-created_at']
        indexes = [
            models.Index(fields=['recommendation_type']),
            models.Index(fields=['target_page']),
            models.Index(fields=['priority']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['confidence_score']),
        ]
    
    def __str__(self):
        return f"{self.get_recommendation_type_display()}: {self.title}"
    
    def is_valid(self):
        """Check if recommendation is still valid"""
        if self.valid_until and timezone.now() > self.valid_until:
            return False
        return self.status in ['pending', 'approved']
    
    def apply_recommendation(self, user):
        """Mark recommendation as implemented"""
        self.status = 'implemented'
        self.save()
        
        # Log implementation
        RecommendationImplementation.objects.create(
            recommendation=self,
            implemented_by=user,
            implementation_notes=f"Applied recommendation: {self.title}"
        )


class ContentRecommendation(models.Model):
    """Content-based recommendations for users"""
    
    CONTENT_TYPES = [
        ('page', 'Page'),
        ('feature', 'Feature'),
        ('tool', 'Tool'),
        ('report', 'Report'),
        ('dashboard', 'Dashboard'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='content_recommendations')
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    content_title = models.CharField(max_length=200)
    content_url = models.URLField()
    content_description = models.TextField(blank=True)
    
    # Recommendation logic
    reason = models.TextField(help_text="Why this content is recommended")
    relevance_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    recommendation_algorithm = models.CharField(max_length=50, default='collaborative_filtering')
    
    # Context
    recommended_context = models.JSONField(
        default=dict,
        help_text="Context when recommendation should be shown"
    )
    display_conditions = models.JSONField(default=dict)
    
    # Interaction tracking
    shown_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    dismissed_count = models.IntegerField(default=0)
    last_shown = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'core_content_recommendation'
        ordering = ['-relevance_score', '-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['content_type']),
            models.Index(fields=['relevance_score']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['user', 'content_url']
    
    def __str__(self):
        return f"Recommend {self.content_title} to {self.user.username}"
    
    @property
    def click_through_rate(self):
        """Calculate click-through rate"""
        if self.shown_count == 0:
            return 0.0
        return self.clicked_count / self.shown_count
    
    def mark_shown(self):
        """Mark recommendation as shown to user"""
        self.shown_count += 1
        self.last_shown = timezone.now()
        self.save(update_fields=['shown_count', 'last_shown'])
    
    def mark_clicked(self):
        """Mark recommendation as clicked by user"""
        self.clicked_count += 1
        self.save(update_fields=['clicked_count'])
    
    def mark_dismissed(self):
        """Mark recommendation as dismissed by user"""
        self.dismissed_count += 1
        self.save(update_fields=['dismissed_count'])
    
    def is_expired(self):
        """Check if recommendation has expired"""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False
    
    def should_show(self):
        """Check if recommendation should be shown"""
        if not self.is_active or self.is_expired():
            return False
        
        # Don't show if dismissed too many times
        if self.dismissed_count >= 3:
            return False
        
        # Don't show if shown too recently
        if self.last_shown:
            time_since_shown = timezone.now() - self.last_shown
            if time_since_shown < timedelta(hours=1):
                return False
        
        return True


class RecommendationImplementation(models.Model):
    """Track implementation of navigation recommendations"""
    
    recommendation = models.ForeignKey(
        NavigationRecommendation, 
        on_delete=models.CASCADE,
        related_name='implementations'
    )
    implemented_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    implementation_date = models.DateTimeField(auto_now_add=True)
    implementation_notes = models.TextField(blank=True)
    implementation_method = models.CharField(max_length=100, blank=True)
    
    # Results tracking
    before_metrics = models.JSONField(default=dict)
    after_metrics = models.JSONField(default=dict)
    success_metrics = models.JSONField(default=dict)
    
    is_successful = models.BooleanField(null=True)
    effectiveness_score = models.FloatField(
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    class Meta:
        db_table = 'core_recommendation_implementation'
        ordering = ['-implementation_date']
        indexes = [
            models.Index(fields=['recommendation']),
            models.Index(fields=['implemented_by']),
            models.Index(fields=['implementation_date']),
            models.Index(fields=['is_successful']),
        ]
    
    def __str__(self):
        return f"Implementation of {self.recommendation.title}"
    
    def calculate_effectiveness(self):
        """Calculate implementation effectiveness based on before/after metrics"""
        if not self.before_metrics or not self.after_metrics:
            return None
        
        # Example effectiveness calculation
        improvements = 0
        total_metrics = 0
        
        for metric_name in self.before_metrics:
            if metric_name in self.after_metrics:
                before_value = self.before_metrics[metric_name]
                after_value = self.after_metrics[metric_name]
                
                if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
                    if after_value > before_value:
                        improvements += 1
                    total_metrics += 1
        
        if total_metrics > 0:
            effectiveness = improvements / total_metrics
            self.effectiveness_score = effectiveness
            self.is_successful = effectiveness >= 0.5
            self.save(update_fields=['effectiveness_score', 'is_successful'])
            return effectiveness
        
        return None


class UserSimilarity(models.Model):
    """Store user similarity scores for collaborative filtering"""
    
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='similarities_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='similarities_as_user2')
    
    similarity_score = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Cosine similarity score (-1.0 to 1.0)"
    )
    
    # Calculation details
    calculation_method = models.CharField(max_length=50, default='cosine_similarity')
    features_used = models.JSONField(default=list)
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_user_similarity'
        unique_together = ['user1', 'user2']
        indexes = [
            models.Index(fields=['user1', 'similarity_score']),
            models.Index(fields=['user2', 'similarity_score']),
            models.Index(fields=['calculated_at']),
        ]
    
    def __str__(self):
        return f"Similarity: {self.user1.username} <-> {self.user2.username} ({self.similarity_score:.3f})"


class RecommendationFeedback(models.Model):
    """User feedback on recommendations"""
    
    FEEDBACK_TYPES = [
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
        ('implemented', 'Implemented'),
        ('irrelevant', 'Irrelevant'),
    ]
    
    # Generic relation to any recommendation type
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    recommendation = GenericForeignKey('content_type', 'object_id')
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    comments = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_recommendation_feedback'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user']),
            models.Index(fields=['feedback_type']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['content_type', 'object_id', 'user']
    
    def __str__(self):
        return f"Feedback from {self.user.username}: {self.feedback_type}"