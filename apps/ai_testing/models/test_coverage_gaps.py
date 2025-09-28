"""
Test Coverage Gap Detection Model
Analyzes anomaly patterns to identify missing test coverage and generate recommendations
"""

import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class TestCoverageGap(models.Model):
    """
    Identified gaps in test coverage based on production anomalies and ML analysis
    """
    COVERAGE_TYPES = [
        ('visual', 'Visual Regression'),
        ('performance', 'Performance'),
        ('functional', 'Functional'),
        ('integration', 'Integration'),
        ('edge_case', 'Edge Case'),
        ('error_handling', 'Error Handling'),
        ('user_flow', 'User Flow'),
        ('api_contract', 'API Contract'),
        ('device_specific', 'Device-Specific'),
        ('network_condition', 'Network Condition'),
    ]

    PRIORITY_LEVELS = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    GAP_STATUS = [
        ('identified', 'Identified'),
        ('test_generated', 'Test Generated'),
        ('test_implemented', 'Test Implemented'),
        ('test_verified', 'Test Verified'),
        ('dismissed', 'Dismissed'),
    ]

    TEST_FRAMEWORKS = [
        ('paparazzi', 'Paparazzi (Visual)'),
        ('macrobenchmark', 'Macrobenchmark (Performance)'),
        ('espresso', 'Espresso (UI)'),
        ('junit', 'JUnit (Unit)'),
        ('robolectric', 'Robolectric (Unit/Integration)'),
        ('ui_testing', 'SwiftUI Testing (iOS)'),
        ('xctest', 'XCTest (iOS)'),
        ('custom', 'Custom Framework'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Gap identification
    coverage_type = models.CharField(max_length=20, choices=COVERAGE_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()

    # Related anomaly data
    anomaly_signature = models.ForeignKey(
        'issue_tracker.AnomalySignature',
        on_delete=models.CASCADE,
        related_name='coverage_gaps',
        help_text="Anomaly that revealed this coverage gap"
    )
    affected_endpoints = models.JSONField(
        default=list,
        help_text="List of affected API endpoints or UI components"
    )
    affected_platforms = models.JSONField(
        default=list,
        help_text="Platforms affected: android, ios, web"
    )

    # Gap analysis
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS)
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML confidence in gap identification (0.0-1.0)"
    )
    impact_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Estimated impact of filling this gap (0.0-10.0)"
    )

    # Auto-generated test details
    recommended_framework = models.CharField(
        max_length=20,
        choices=TEST_FRAMEWORKS,
        blank=True,
        help_text="Recommended test framework for this gap"
    )
    auto_generated_test_code = models.TextField(
        blank=True,
        help_text="AI-generated test code ready for implementation"
    )
    test_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Suggested file path for the test"
    )

    # Implementation tracking
    status = models.CharField(max_length=20, choices=GAP_STATUS, default='identified')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_coverage_gaps'
    )

    # Test implementation details
    implemented_test_file = models.CharField(
        max_length=500,
        blank=True,
        help_text="Actual path of implemented test file"
    )
    implementation_commit = models.CharField(
        max_length=40,
        blank=True,
        help_text="Git commit SHA of test implementation"
    )
    verification_notes = models.TextField(blank=True)

    # Pattern analysis
    similar_gaps_count = models.IntegerField(
        default=0,
        help_text="Number of similar gaps found in codebase"
    )
    pattern_metadata = models.JSONField(
        default=dict,
        help_text="Metadata about detected patterns and similarities"
    )

    # Lifecycle tracking
    identified_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    implemented_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-priority', '-confidence_score', '-impact_score', '-identified_at']
        indexes = [
            models.Index(fields=['coverage_type', 'priority']),
            models.Index(fields=['status', 'identified_at']),
            models.Index(fields=['confidence_score', 'impact_score']),
            models.Index(fields=['anomaly_signature', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['recommended_framework']),
        ]

    def __str__(self):
        return f"{self.coverage_type.title()} Gap: {self.title}"

    @property
    def effectiveness_score(self):
        """Calculate overall effectiveness score for prioritization"""
        return (self.confidence_score * 0.4) + (self.impact_score / 10 * 0.6)

    @property
    def urgency_level(self):
        """Determine urgency based on anomaly recurrence and severity"""
        if not self.anomaly_signature:
            return 'medium'

        signature = self.anomaly_signature

        # High urgency conditions
        if (signature.severity in ['critical', 'error'] and
            signature.occurrence_count > 5 and
            self.confidence_score > 0.8):
            return 'urgent'

        # Medium-high urgency
        if (signature.occurrence_count > 3 and
            self.confidence_score > 0.6):
            return 'high'

        return self.priority

    @property
    def estimated_implementation_time(self):
        """Estimate implementation time based on coverage type and complexity"""
        time_estimates = {
            'visual': 2,  # hours
            'performance': 4,
            'functional': 3,
            'integration': 6,
            'edge_case': 2,
            'error_handling': 3,
            'user_flow': 8,
            'api_contract': 4,
            'device_specific': 5,
            'network_condition': 4,
        }

        base_time = time_estimates.get(self.coverage_type, 3)

        # Adjust based on platforms
        platform_multiplier = len(self.affected_platforms) if self.affected_platforms else 1

        # Adjust based on pattern complexity
        complexity_factor = 1.0
        if self.pattern_metadata.get('complexity_level') == 'high':
            complexity_factor = 1.5
        elif self.pattern_metadata.get('complexity_level') == 'low':
            complexity_factor = 0.7

        return int(base_time * platform_multiplier * complexity_factor)

    def generate_test_code(self, test_framework=None):
        """Generate test code for this coverage gap"""
        framework = test_framework or self.recommended_framework

        if not framework:
            return None

        # This would call the test synthesizer service
        from apps.ai_testing.services.test_synthesizer import TestSynthesizer

        synthesizer = TestSynthesizer()
        generated_code = synthesizer.generate_test_for_gap(self, framework)

        if generated_code:
            self.auto_generated_test_code = generated_code
            self.status = 'test_generated'
            self.save()

        return generated_code

    def mark_implemented(self, test_file_path, commit_sha, user):
        """Mark coverage gap as implemented"""
        self.status = 'test_implemented'
        self.implemented_test_file = test_file_path
        self.implementation_commit = commit_sha
        self.implemented_at = timezone.now()
        self.assigned_to = user
        self.save()

    def mark_verified(self, notes="", user=None):
        """Mark test as verified and effective"""
        self.status = 'test_verified'
        self.verification_notes = notes
        self.verified_at = timezone.now()

        if user:
            self.assigned_to = user

        self.save()

    def dismiss_gap(self, reason="", user=None):
        """Dismiss coverage gap as not relevant"""
        self.status = 'dismissed'
        self.verification_notes = f"Dismissed: {reason}"

        if user:
            self.assigned_to = user

        self.save()

    @classmethod
    def get_high_priority_gaps(cls, limit=10):
        """Get highest priority coverage gaps for immediate attention"""
        return cls.objects.filter(
            status__in=['identified', 'test_generated']
        ).order_by(
            '-confidence_score',
            '-impact_score'
        )[:limit]

    @classmethod
    def analyze_coverage_trends(cls, days=30):
        """Analyze coverage gap trends over time"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta

        since_date = timezone.now() - timedelta(days=days)

        # Gap types by frequency
        gap_types = dict(
            cls.objects.filter(identified_at__gte=since_date)
            .values('coverage_type')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('coverage_type', 'count')
        )

        # Implementation success rate
        total_gaps = cls.objects.filter(identified_at__gte=since_date).count()
        implemented_gaps = cls.objects.filter(
            identified_at__gte=since_date,
            status='test_verified'
        ).count()

        success_rate = (implemented_gaps / total_gaps * 100) if total_gaps > 0 else 0

        # Platform distribution
        platform_distribution = {}
        for gap in cls.objects.filter(identified_at__gte=since_date):
            for platform in gap.affected_platforms:
                platform_distribution[platform] = platform_distribution.get(platform, 0) + 1

        # Average confidence and impact scores
        avg_metrics = cls.objects.filter(identified_at__gte=since_date).aggregate(
            avg_confidence=models.Avg('confidence_score'),
            avg_impact=models.Avg('impact_score')
        )

        return {
            'gap_types_frequency': gap_types,
            'implementation_success_rate': round(success_rate, 1),
            'platform_distribution': platform_distribution,
            'average_confidence': round(avg_metrics['avg_confidence'] or 0, 2),
            'average_impact': round(avg_metrics['avg_impact'] or 0, 2),
            'total_gaps_identified': total_gaps,
            'gaps_resolved': implemented_gaps
        }

    @classmethod
    def find_similar_gaps(cls, gap_instance, threshold=0.7):
        """Find similar coverage gaps for pattern analysis"""
        similar_gaps = []

        for other_gap in cls.objects.exclude(id=gap_instance.id):
            # Simple similarity based on coverage type and affected endpoints
            similarity_score = 0.0

            # Coverage type match
            if other_gap.coverage_type == gap_instance.coverage_type:
                similarity_score += 0.4

            # Platform overlap
            gap_platforms = set(gap_instance.affected_platforms)
            other_platforms = set(other_gap.affected_platforms)
            platform_overlap = len(gap_platforms.intersection(other_platforms))
            total_platforms = len(gap_platforms.union(other_platforms))

            if total_platforms > 0:
                similarity_score += 0.3 * (platform_overlap / total_platforms)

            # Endpoint/component similarity (simple string matching)
            gap_endpoints = set(gap_instance.affected_endpoints)
            other_endpoints = set(other_gap.affected_endpoints)
            endpoint_overlap = len(gap_endpoints.intersection(other_endpoints))
            total_endpoints = len(gap_endpoints.union(other_endpoints))

            if total_endpoints > 0:
                similarity_score += 0.3 * (endpoint_overlap / total_endpoints)

            if similarity_score >= threshold:
                similar_gaps.append({
                    'gap': other_gap,
                    'similarity_score': similarity_score
                })

        return sorted(similar_gaps, key=lambda x: x['similarity_score'], reverse=True)


class TestCoveragePattern(models.Model):
    """
    Detected patterns in test coverage gaps for automated insights
    """
    PATTERN_TYPES = [
        ('recurring_endpoint', 'Recurring Endpoint Issues'),
        ('platform_specific', 'Platform-Specific Gaps'),
        ('framework_weakness', 'Framework Coverage Weakness'),
        ('user_flow_gap', 'User Flow Coverage Gap'),
        ('error_scenario', 'Error Scenario Pattern'),
        ('performance_blind_spot', 'Performance Blind Spot'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pattern_type = models.CharField(max_length=30, choices=PATTERN_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()

    # Pattern definition
    pattern_signature = models.CharField(
        max_length=64,
        help_text="Hash signature of the pattern for deduplication"
    )
    pattern_criteria = models.JSONField(
        help_text="JSON criteria that define this pattern"
    )

    # Related gaps
    coverage_gaps = models.ManyToManyField(
        TestCoverageGap,
        related_name='patterns',
        help_text="Coverage gaps that match this pattern"
    )

    # Pattern statistics
    occurrence_count = models.IntegerField(default=1)
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in pattern validity"
    )

    # Recommendations
    recommended_actions = models.JSONField(
        default=list,
        help_text="List of recommended actions to address this pattern"
    )
    template_test_code = models.TextField(
        blank=True,
        help_text="Template test code for gaps matching this pattern"
    )

    # Tracking
    first_detected = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-occurrence_count', '-confidence_score']
        unique_together = [('pattern_type', 'pattern_signature')]
        indexes = [
            models.Index(fields=['pattern_type', 'is_active']),
            models.Index(fields=['confidence_score', 'occurrence_count']),
            models.Index(fields=['last_seen']),
        ]

    def __str__(self):
        return f"{self.pattern_type}: {self.title} ({self.occurrence_count} occurrences)"

    def add_coverage_gap(self, gap):
        """Add a coverage gap to this pattern"""
        self.coverage_gaps.add(gap)
        self.occurrence_count = self.coverage_gaps.count()
        self.last_seen = timezone.now()
        self.save()

    @property
    def pattern_strength(self):
        """Calculate pattern strength based on occurrences and confidence"""
        return (self.occurrence_count * 0.6) + (self.confidence_score * 0.4)