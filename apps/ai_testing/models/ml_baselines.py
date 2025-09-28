"""
ML-Enhanced Baselines Model
Semantic visual regression analysis and intelligent baseline management
"""

import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class MLBaseline(models.Model):
    """
    ML-powered visual and functional baselines with semantic understanding
    """
    BASELINE_TYPES = [
        ('visual', 'Visual/UI Baseline'),
        ('performance', 'Performance Baseline'),
        ('functional', 'Functional Baseline'),
        ('api', 'API Response Baseline'),
        ('accessibility', 'Accessibility Baseline'),
    ]

    APPROVAL_STATUS = [
        ('auto_approved', 'Auto-Approved'),
        ('pending_review', 'Pending Review'),
        ('community_approved', 'Community Approved'),
        ('rejected', 'Rejected'),
        ('deprecated', 'Deprecated'),
    ]

    SEMANTIC_CONFIDENCE_LEVELS = [
        ('low', 'Low (0-40%)'),
        ('medium', 'Medium (40-70%)'),
        ('high', 'High (70-90%)'),
        ('very_high', 'Very High (90%+)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Baseline identification
    baseline_type = models.CharField(max_length=20, choices=BASELINE_TYPES)
    component_name = models.CharField(max_length=200, help_text="UI component or API endpoint name")
    test_scenario = models.CharField(max_length=200, help_text="Test scenario description")

    # Platform and version
    platform = models.CharField(max_length=20, default='all', help_text="android, ios, web, or all")
    app_version = models.CharField(max_length=50)
    device_class = models.CharField(
        max_length=50,
        blank=True,
        help_text="Device class: phone, tablet, desktop, etc."
    )

    # Visual baseline data (for visual type)
    visual_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hash of visual baseline image"
    )
    visual_metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Visual analysis metadata (layout, colors, text, etc.)"
    )

    # ML semantic understanding
    semantic_elements = models.JSONField(
        default=dict,
        help_text="ML-identified semantic elements (buttons, text, images, etc.)"
    )
    element_hierarchy = models.JSONField(
        default=dict,
        help_text="UI element hierarchy and relationships"
    )
    interaction_regions = models.JSONField(
        default=list,
        help_text="Identified clickable/interactive regions"
    )

    # Performance baseline data (for performance type)
    performance_metrics = models.JSONField(
        null=True,
        blank=True,
        help_text="Performance baseline metrics"
    )

    # Baseline validation
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default='pending_review')
    semantic_confidence = models.CharField(max_length=20, choices=SEMANTIC_CONFIDENCE_LEVELS, default='medium')
    validation_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML validation score for baseline quality"
    )

    # Community validation
    approval_votes = models.IntegerField(default=0)
    rejection_votes = models.IntegerField(default=0)
    total_validations = models.IntegerField(default=0)

    # Change detection settings
    tolerance_threshold = models.FloatField(
        default=0.05,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Threshold for detecting meaningful changes (0.0-1.0)"
    )
    ignore_cosmetic_changes = models.BooleanField(
        default=True,
        help_text="Whether to ignore purely cosmetic changes"
    )

    # Lifecycle management
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_validated = models.DateTimeField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='superseded_baselines'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [
            ('baseline_type', 'component_name', 'test_scenario', 'platform', 'app_version')
        ]
        indexes = [
            models.Index(fields=['baseline_type', 'platform']),
            models.Index(fields=['component_name', 'app_version']),
            models.Index(fields=['approval_status', 'is_active']),
            models.Index(fields=['visual_hash']),
            models.Index(fields=['validation_score', 'semantic_confidence']),
        ]

    def __str__(self):
        return f"{self.baseline_type.title()}: {self.component_name} - {self.app_version}"

    @property
    def approval_ratio(self):
        """Calculate approval ratio for community validation"""
        if self.total_validations == 0:
            return 0.0
        return self.approval_votes / self.total_validations

    @property
    def confidence_score(self):
        """Calculate overall confidence in baseline quality"""
        semantic_score = {
            'low': 0.25,
            'medium': 0.5,
            'high': 0.75,
            'very_high': 0.9
        }.get(self.semantic_confidence, 0.5)

        return (self.validation_score * 0.6) + (semantic_score * 0.4)

    @property
    def requires_manual_review(self):
        """Determine if baseline requires manual review"""
        return (
            self.approval_status == 'pending_review' or
            self.confidence_score < 0.7 or
            self.semantic_confidence == 'low'
        )

    def analyze_visual_difference(self, new_visual_data):
        """Analyze visual differences using ML semantic understanding"""
        if self.baseline_type != 'visual':
            return None

        # This would call the ML visual processor service
        from apps.ai_testing.services.ml_visual_processor import MLVisualProcessor

        processor = MLVisualProcessor()
        diff_analysis = processor.analyze_semantic_difference(
            baseline=self,
            new_data=new_visual_data
        )

        return diff_analysis

    def detect_functional_changes(self, new_functional_data):
        """Detect functional changes in API or component behavior"""
        if self.baseline_type not in ['functional', 'api']:
            return None

        # Compare response structures, timing patterns, etc.
        changes = []

        # This would implement functional change detection logic
        return changes

    def vote_approve(self, user):
        """Community vote to approve baseline"""
        # Check if user already voted (would need separate voting tracking)
        self.approval_votes += 1
        self.total_validations += 1

        # Auto-approve if enough votes
        if self.approval_ratio > 0.8 and self.total_validations >= 3:
            self.approval_status = 'community_approved'

        self.save()

    def vote_reject(self, user, reason=""):
        """Community vote to reject baseline"""
        self.rejection_votes += 1
        self.total_validations += 1

        # Auto-reject if too many rejections
        if self.approval_ratio < 0.3 and self.total_validations >= 3:
            self.approval_status = 'rejected'

        self.save()

    def supersede_with(self, new_baseline):
        """Mark this baseline as superseded by a newer one"""
        self.superseded_by = new_baseline
        self.is_active = False
        self.save()

        new_baseline.is_active = True
        new_baseline.save()

    @classmethod
    def get_active_baseline(cls, baseline_type, component_name, platform='all', app_version=None):
        """Get active baseline for component"""
        query_params = {
            'baseline_type': baseline_type,
            'component_name': component_name,
            'platform': platform,
            'is_active': True,
            'approval_status__in': ['auto_approved', 'community_approved']
        }

        if app_version:
            query_params['app_version'] = app_version

        try:
            return cls.objects.get(**query_params)
        except cls.DoesNotExist:
            # Try fallback to 'all' platform or latest version
            if platform != 'all':
                query_params['platform'] = 'all'
                try:
                    return cls.objects.get(**query_params)
                except cls.DoesNotExist:
                    pass

            # Try latest approved baseline
            try:
                return cls.objects.filter(
                    baseline_type=baseline_type,
                    component_name=component_name,
                    is_active=True,
                    approval_status__in=['auto_approved', 'community_approved']
                ).order_by('-created_at').first()
            except:
                return None

    @classmethod
    def analyze_baseline_drift(cls, days=30):
        """Analyze how baselines are changing over time"""
        from django.db.models import Count
        from datetime import timedelta

        since_date = timezone.now() - timedelta(days=days)

        # New baselines created
        new_baselines = cls.objects.filter(created_at__gte=since_date).count()

        # Baselines superseded
        superseded = cls.objects.filter(
            superseded_by__isnull=False,
            updated_at__gte=since_date
        ).count()

        # Approval status distribution
        status_distribution = dict(
            cls.objects.filter(created_at__gte=since_date)
            .values('approval_status')
            .annotate(count=Count('id'))
            .values_list('approval_status', 'count')
        )

        # Confidence trends
        high_confidence = cls.objects.filter(
            created_at__gte=since_date,
            semantic_confidence__in=['high', 'very_high']
        ).count()

        total_recent = cls.objects.filter(created_at__gte=since_date).count()
        high_confidence_rate = (high_confidence / total_recent * 100) if total_recent > 0 else 0

        return {
            'new_baselines': new_baselines,
            'superseded_baselines': superseded,
            'approval_status_distribution': status_distribution,
            'high_confidence_rate': round(high_confidence_rate, 1),
            'baseline_turnover_rate': round((superseded / max(1, new_baselines)) * 100, 1),
            'analysis_period_days': days
        }


class SemanticElement(models.Model):
    """
    Individual semantic elements identified in UI baselines
    """
    ELEMENT_TYPES = [
        ('button', 'Button'),
        ('text_field', 'Text Field'),
        ('label', 'Text Label'),
        ('image', 'Image'),
        ('icon', 'Icon'),
        ('container', 'Container/Layout'),
        ('navigation', 'Navigation Element'),
        ('form', 'Form Element'),
        ('list_item', 'List Item'),
        ('modal', 'Modal/Dialog'),
    ]

    INTERACTION_TYPES = [
        ('clickable', 'Clickable'),
        ('scrollable', 'Scrollable'),
        ('input', 'Input Field'),
        ('display_only', 'Display Only'),
        ('navigation', 'Navigation'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    baseline = models.ForeignKey(
        MLBaseline,
        on_delete=models.CASCADE,
        related_name='elements'
    )

    # Element identification
    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPES)
    element_id = models.CharField(max_length=200, blank=True, help_text="UI element ID if available")
    element_text = models.TextField(blank=True, help_text="Visible text content")
    element_description = models.TextField(blank=True, help_text="AI-generated description")

    # Position and layout
    bounding_box = models.JSONField(
        help_text="Element bounding box: {x, y, width, height}"
    )
    z_index = models.IntegerField(default=0, help_text="Layer/depth information")

    # Interaction properties
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES, default='display_only')
    is_critical = models.BooleanField(
        default=False,
        help_text="Whether this element is critical for user flow"
    )

    # Visual properties
    visual_properties = models.JSONField(
        default=dict,
        help_text="Visual properties: colors, fonts, styles, etc."
    )

    # ML confidence
    detection_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML confidence in element detection and classification"
    )

    class Meta:
        ordering = ['baseline', 'element_type', 'z_index']
        indexes = [
            models.Index(fields=['baseline', 'element_type']),
            models.Index(fields=['interaction_type', 'is_critical']),
            models.Index(fields=['detection_confidence']),
        ]

    def __str__(self):
        return f"{self.element_type}: {self.element_text[:50] or self.element_description[:50]}"

    @property
    def element_center(self):
        """Calculate center point of element"""
        bbox = self.bounding_box
        return {
            'x': bbox['x'] + bbox['width'] / 2,
            'y': bbox['y'] + bbox['height'] / 2
        }

    @property
    def element_area(self):
        """Calculate element area in pixels"""
        bbox = self.bounding_box
        return bbox['width'] * bbox['height']

    def overlaps_with(self, other_element):
        """Check if this element overlaps with another"""
        bbox1 = self.bounding_box
        bbox2 = other_element.bounding_box

        return not (bbox1['x'] + bbox1['width'] < bbox2['x'] or
                   bbox2['x'] + bbox2['width'] < bbox1['x'] or
                   bbox1['y'] + bbox1['height'] < bbox2['y'] or
                   bbox2['y'] + bbox2['height'] < bbox1['y'])

    def distance_to(self, other_element):
        """Calculate distance to another element's center"""
        center1 = self.element_center
        center2 = other_element.element_center

        dx = center1['x'] - center2['x']
        dy = center1['y'] - center2['y']

        return (dx**2 + dy**2)**0.5


class BaselineComparison(models.Model):
    """
    Track comparisons between baselines and actual results for continuous learning
    """
    COMPARISON_TYPES = [
        ('visual_diff', 'Visual Difference'),
        ('functional_diff', 'Functional Difference'),
        ('performance_diff', 'Performance Difference'),
    ]

    COMPARISON_RESULTS = [
        ('identical', 'Identical'),
        ('acceptable_diff', 'Acceptable Difference'),
        ('significant_diff', 'Significant Difference'),
        ('regression', 'Regression Detected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    baseline = models.ForeignKey(
        MLBaseline,
        on_delete=models.CASCADE,
        related_name='comparisons'
    )

    # Comparison metadata
    comparison_type = models.CharField(max_length=20, choices=COMPARISON_TYPES)
    test_run_id = models.UUIDField(help_text="Reference to test run from streamlab")
    comparison_result = models.CharField(max_length=20, choices=COMPARISON_RESULTS)

    # Difference analysis
    difference_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Quantified difference score (0.0 = identical, 1.0 = completely different)"
    )
    significant_changes = models.JSONField(
        default=list,
        help_text="List of significant changes detected"
    )
    cosmetic_changes = models.JSONField(
        default=list,
        help_text="List of cosmetic/insignificant changes"
    )

    # ML analysis
    ml_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML confidence in comparison analysis"
    )
    false_positive_likelihood = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Likelihood this is a false positive"
    )

    # Human validation
    human_validated = models.BooleanField(default=False)
    human_agreement = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether human reviewer agreed with ML analysis"
    )
    validation_notes = models.TextField(blank=True)

    # Timeline
    compared_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-compared_at']
        indexes = [
            models.Index(fields=['baseline', 'comparison_type']),
            models.Index(fields=['comparison_result', 'compared_at']),
            models.Index(fields=['difference_score', 'ml_confidence']),
            models.Index(fields=['human_validated', 'human_agreement']),
        ]

    def __str__(self):
        return f"{self.comparison_type} - {self.comparison_result} (Score: {self.difference_score:.2f})"

    @property
    def needs_human_review(self):
        """Determine if comparison needs human validation"""
        return (
            not self.human_validated and
            (self.ml_confidence < 0.7 or
             self.difference_score > 0.3 or
             self.comparison_result in ['significant_diff', 'regression'])
        )

    def validate_with_human(self, agrees_with_ml, notes="", user=None):
        """Record human validation of the comparison"""
        self.human_validated = True
        self.human_agreement = agrees_with_ml
        self.validation_notes = notes
        self.validated_at = timezone.now()
        self.save()

        # Update ML model performance based on human feedback
        self._update_ml_performance_metrics()

    def _update_ml_performance_metrics(self):
        """Update ML model performance tracking based on human validation"""
        # This would feed back to the ML model performance tracking
        pass

    @classmethod
    def get_ml_accuracy_stats(cls, days=30):
        """Get ML accuracy statistics based on human validation"""
        from datetime import timedelta

        since_date = timezone.now() - timedelta(days=days)
        validated_comparisons = cls.objects.filter(
            compared_at__gte=since_date,
            human_validated=True
        )

        if not validated_comparisons.exists():
            return {'status': 'no_data'}

        total = validated_comparisons.count()
        agreed = validated_comparisons.filter(human_agreement=True).count()
        accuracy = (agreed / total) * 100

        return {
            'ml_accuracy_percentage': round(accuracy, 1),
            'total_validated': total,
            'ml_human_agreement': agreed,
            'disagreement_cases': total - agreed,
            'period_days': days
        }