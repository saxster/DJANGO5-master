"""
AI Testing API Serializers
REST API serializers for AI testing data
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.ai_testing.models.test_coverage_gaps import TestCoverageGap, TestCoveragePattern
from apps.ai_testing.models.adaptive_thresholds import AdaptiveThreshold
from apps.ai_testing.models.regression_predictions import RegressionPrediction
from apps.issue_tracker.models import AnomalySignature

User = get_user_model()


class AnomalySignatureSerializer(serializers.ModelSerializer):
    """Serializer for anomaly signature data"""

    class Meta:
        model = AnomalySignature
        fields = [
            'id', 'anomaly_type', 'description', 'severity',
            'occurrence_count', 'last_seen', 'status'
        ]


class TestCoverageGapSerializer(serializers.ModelSerializer):
    """Serializer for test coverage gaps"""
    anomaly_signature = AnomalySignatureSerializer(read_only=True)
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name',
        read_only=True
    )
    effectiveness_score = serializers.ReadOnlyField()
    urgency_level = serializers.ReadOnlyField()
    estimated_implementation_time = serializers.ReadOnlyField()

    class Meta:
        model = TestCoverageGap
        fields = [
            'id', 'coverage_type', 'title', 'description',
            'priority', 'confidence_score', 'impact_score',
            'affected_endpoints', 'affected_platforms',
            'recommended_framework', 'status',
            'anomaly_signature', 'assigned_to_name',
            'effectiveness_score', 'urgency_level',
            'estimated_implementation_time',
            'similar_gaps_count', 'identified_at', 'updated_at'
        ]


class TestCoverageGapSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for coverage gap summaries"""

    class Meta:
        model = TestCoverageGap
        fields = [
            'id', 'title', 'coverage_type', 'priority', 'status',
            'confidence_score', 'impact_score', 'identified_at'
        ]


class TestCoveragePatternSerializer(serializers.ModelSerializer):
    """Serializer for test coverage patterns"""
    pattern_strength = serializers.ReadOnlyField()
    coverage_gaps_count = serializers.SerializerMethodField()

    class Meta:
        model = TestCoveragePattern
        fields = [
            'id', 'pattern_type', 'title', 'description',
            'occurrence_count', 'confidence_score',
            'pattern_strength', 'coverage_gaps_count',
            'recommended_actions', 'first_detected', 'last_seen', 'is_active'
        ]

    def get_coverage_gaps_count(self, obj):
        return obj.coverage_gaps.count()


class AdaptiveThresholdSerializer(serializers.ModelSerializer):
    """Serializer for adaptive thresholds"""

    class Meta:
        model = AdaptiveThreshold
        fields = [
            'id', 'metric_name', 'value', 'confidence_interval',
            'sample_count', 'accuracy', 'precision',
            'created_at', 'updated_at'
        ]


class RegressionPredictionSerializer(serializers.ModelSerializer):
    """Serializer for regression predictions"""
    risk_percentage = serializers.SerializerMethodField()

    class Meta:
        model = RegressionPrediction
        fields = [
            'id', 'version_identifier', 'risk_score', 'risk_percentage',
            'confidence', 'risk_factors', 'prediction_metadata',
            'created_at'
        ]

    def get_risk_percentage(self, obj):
        return round(obj.risk_score * 100, 1)


class AIInsightsSummarySerializer(serializers.Serializer):
    """Serializer for AI insights summary data"""
    health_score = serializers.IntegerField()
    last_updated = serializers.DateTimeField()

    # Coverage gaps summary
    coverage_gaps = serializers.DictField()

    # Regression risk summary
    regression_risk = serializers.DictField()

    # Threshold status summary
    threshold_status = serializers.DictField()

    # Pattern insights summary
    pattern_insights = serializers.DictField()


class CoverageGapStatsSerializer(serializers.Serializer):
    """Serializer for coverage gap statistics"""
    total = serializers.IntegerField()
    by_priority = serializers.DictField()
    by_type = serializers.DictField()
    by_status = serializers.DictField()
    recent_7d = serializers.IntegerField()
    implementation_rate = serializers.FloatField()


class TestGenerationRequestSerializer(serializers.Serializer):
    """Serializer for test generation requests"""
    gap_id = serializers.UUIDField()
    framework = serializers.ChoiceField(
        choices=['paparazzi', 'macrobenchmark', 'espresso', 'junit',
                'robolectric', 'ui_testing', 'xctest', 'custom']
    )
    include_setup = serializers.BooleanField(default=True)
    include_teardown = serializers.BooleanField(default=True)


class TestGenerationResponseSerializer(serializers.Serializer):
    """Serializer for test generation responses"""
    success = serializers.BooleanField()
    test_code = serializers.CharField()
    file_name = serializers.CharField()
    framework = serializers.CharField()
    file_size = serializers.IntegerField()
    line_count = serializers.IntegerField()
    generated_at = serializers.DateTimeField()


class AnalysisRequestSerializer(serializers.Serializer):
    """Serializer for pattern analysis requests"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)
    min_confidence = serializers.FloatField(default=0.6, min_value=0.0, max_value=1.0)
    force_refresh = serializers.BooleanField(default=False)
    analysis_type = serializers.ChoiceField(
        choices=['full', 'patterns_only', 'gaps_only'],
        default='full'
    )


class AnalysisResultSerializer(serializers.Serializer):
    """Serializer for analysis results"""
    analysis_id = serializers.UUIDField()
    status = serializers.CharField()
    gaps_identified = serializers.IntegerField()
    patterns_detected = serializers.IntegerField()
    confidence_score = serializers.FloatField()
    analysis_duration = serializers.FloatField()
    started_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField()


class ExportRequestSerializer(serializers.Serializer):
    """Serializer for export requests"""
    format = serializers.ChoiceField(choices=['csv', 'json', 'excel'])
    data_type = serializers.ChoiceField(
        choices=['coverage_gaps', 'patterns', 'thresholds', 'predictions', 'insights']
    )
    filters = serializers.DictField(default=dict)
    include_details = serializers.BooleanField(default=False)
    date_range = serializers.IntegerField(default=30, min_value=1, max_value=365)


class APIErrorSerializer(serializers.Serializer):
    """Serializer for API error responses"""
    success = serializers.BooleanField(default=False)
    error_code = serializers.CharField()
    error_message = serializers.CharField()
    timestamp = serializers.DateTimeField()
    correlation_id = serializers.CharField(required=False)