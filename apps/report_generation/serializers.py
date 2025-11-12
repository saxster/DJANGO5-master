"""
Serializers for Report Generation API

Consolidated serializers for all report generation models.
"""

from rest_framework import serializers
from django.utils.dateparse import parse_datetime
from apps.report_generation.models import (
    ReportTemplate,
    GeneratedReport,
    ReportAIInteraction,
    ReportQualityMetrics,
    ReportExemplar,
    ReportIncidentTrend,
)
from apps.peoples.models import People


class ReportTemplateSerializer(serializers.ModelSerializer):
    """Serializer for report templates."""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'name', 'description', 'category', 'category_display',
            'schema', 'questioning_strategy', 'quality_gates',
            'is_system_template', 'is_active', 'version',
            'created_by', 'created_by_name', 
            'approved_by', 'approved_by_name', 'approved_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_system_template']


class ReportAIInteractionSerializer(serializers.ModelSerializer):
    """Serializer for AI interactions."""
    
    question_type_display = serializers.CharField(source='get_question_type_display', read_only=True)
    
    class Meta:
        model = ReportAIInteraction
        fields = [
            'id', 'question', 'answer', 'question_type', 'question_type_display',
            'iteration', 'depth', 'improved_clarity', 'quality_feedback',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReportQualityMetricsSerializer(serializers.ModelSerializer):
    """Serializer for quality metrics."""
    
    class Meta:
        model = ReportQualityMetrics
        fields = [
            'completeness_score', 'required_fields_filled', 'total_required_fields',
            'narrative_word_count', 'minimum_narrative_length',
            'clarity_score', 'readability_score', 'jargon_density', 'assumption_count',
            'causal_chain_strength', 'actionability_score', 'smart_criteria_met',
            'improvement_suggestions', 'jargon_examples', 'missing_details'
        ]


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Basic serializer for generated reports."""
    
    template_name = serializers.CharField(source='template.name', read_only=True)
    template_category = serializers.CharField(source='template.category', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'title', 'template', 'template_name', 'template_category',
            'author', 'author_name', 'status', 'status_display',
            'quality_score', 'completeness_score', 'clarity_score',
            'is_exemplar', 'created_at', 'updated_at', 'submitted_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class GeneratedReportDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with all report data and metrics."""
    
    template_name = serializers.CharField(source='template.name', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    ai_interactions_detailed = ReportAIInteractionSerializer(many=True, read_only=True)
    detailed_quality_metrics = ReportQualityMetricsSerializer(read_only=True)
    can_submit_check = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'title', 'template', 'template_name',
            'report_data', 'author', 'author_name', 'status',
            'related_content_type', 'related_object_id',
            'ai_interactions', 'ai_interactions_detailed',
            'quality_score', 'completeness_score', 'clarity_score',
            'detailed_quality_metrics', 'can_submit_check',
            'submitted_at', 'reviewed_by', 'reviewed_by_name', 'reviewed_at',
            'supervisor_feedback', 'is_exemplar', 'exemplar_category',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_can_submit_check(self, obj):
        """Check if report can be submitted."""
        can_submit, issues = obj.can_submit()
        return {
            'can_submit': can_submit,
            'issues': issues
        }


class GeneratedReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new reports."""
    
    class Meta:
        model = GeneratedReport
        fields = [
            'template', 'title', 'related_content_type', 'related_object_id',
            'report_data'
        ]
    
    def create(self, validated_data):
        """Create report with auto-population."""
        from apps.report_generation.services import ContextAutoPopulationService
        
        # Auto-populate from related entity if provided
        if validated_data.get('related_object_id') and validated_data.get('related_content_type'):
            content_type = validated_data['related_content_type']
            object_id = validated_data['related_object_id']
            
            # Try to auto-populate based on entity type
            model_name = content_type.model
            auto_data = {}
            
            if model_name == 'workorder':
                auto_data = ContextAutoPopulationService.populate_from_work_order(object_id)
            elif model_name == 'alert':
                auto_data = ContextAutoPopulationService.populate_from_incident(object_id)
            elif model_name == 'asset':
                auto_data = ContextAutoPopulationService.populate_from_asset(object_id)
            
            # Merge auto-populated data with provided data
            if auto_data:
                report_data = {**auto_data, **validated_data.get('report_data', {})}
                validated_data['report_data'] = report_data
        
        # Set author from request
        validated_data['author'] = self.context['request'].user
        validated_data['tenant'] = self.context['request'].user.tenant
        
        return super().create(validated_data)


class GeneratedReportUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating reports."""
    
    class Meta:
        model = GeneratedReport
        fields = ['report_data', 'ai_interactions']
    
    def update(self, instance, validated_data):
        """Update report and recalculate quality metrics."""
        from apps.report_generation.services import QualityGateService
        
        updated = super().update(instance, validated_data)
        
        # Recalculate quality metrics
        QualityGateService.calculate_quality_metrics(updated)
        
        return updated


class ReportExemplarSerializer(serializers.ModelSerializer):
    """Serializer for exemplar reports."""
    
    report_title = serializers.CharField(source='report.title', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = ReportExemplar
        fields = [
            'id', 'report', 'report_title', 'exemplar_category',
            'why_exemplar', 'learning_points', 'demonstrates_frameworks',
            'narrative_quality', 'root_cause_depth',
            'approved_by', 'approved_by_name', 'approval_date',
            'times_referenced'
        ]
        read_only_fields = ['id', 'approval_date', 'times_referenced']


class ReportIncidentTrendSerializer(serializers.ModelSerializer):
    """Serializer for incident trends."""
    
    related_reports_count = serializers.IntegerField(source='related_reports.count', read_only=True)
    addressed_by_name = serializers.CharField(source='addressed_by.get_full_name', read_only=True)
    
    class Meta:
        model = ReportIncidentTrend
        fields = [
            'id', 'trend_type', 'pattern_description',
            'related_reports_count', 'occurrence_count',
            'severity_level', 'predicted_recurrence_probability',
            'recommended_actions', 'first_occurrence', 'last_occurrence',
            'is_active', 'is_addressed', 'addressed_by', 'addressed_by_name',
            'addressed_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AskQuestionSerializer(serializers.Serializer):
    """Serializer for AI question request."""
    
    context = serializers.JSONField(required=False, default=dict)
    framework = serializers.ChoiceField(
        choices=['5_whys', 'sbar', '5w1h', 'ishikawa', 'star', 'auto'],
        required=False,
        default='auto'
    )


class QuestionResponseSerializer(serializers.Serializer):
    """Serializer for AI question response."""
    
    question = serializers.CharField()
    question_type = serializers.CharField()
    iteration = serializers.IntegerField()
    context_help = serializers.CharField(required=False)


class SubmitReportSerializer(serializers.Serializer):
    """Serializer for report submission."""
    
    final_review_notes = serializers.CharField(required=False, allow_blank=True)


class ApproveReportSerializer(serializers.Serializer):
    """Serializer for report approval."""
    
    feedback = serializers.CharField(required=False, allow_blank=True)
    mark_as_exemplar = serializers.BooleanField(required=False, default=False)
    exemplar_category = serializers.CharField(required=False, allow_blank=True)


class MarkExemplarSerializer(serializers.Serializer):
    """Serializer for marking report as exemplar."""
    
    exemplar_category = serializers.CharField()
    why_exemplar = serializers.CharField()
    learning_points = serializers.ListField(child=serializers.CharField())
    demonstrates_frameworks = serializers.ListField(child=serializers.CharField())
    narrative_quality = serializers.IntegerField(min_value=1, max_value=5)
    root_cause_depth = serializers.IntegerField(min_value=1, max_value=5)


class ReportSyncSerializer(serializers.Serializer):
    """
    Serializer for mobile sync (Kotlin Android app).
    Follows same pattern as TaskSyncSerializer, AttendanceSyncSerializer.
    """
    
    mobile_id = serializers.CharField(required=True, help_text="Temporary ID from Kotlin app")
    template_id = serializers.IntegerField(required=True)
    title = serializers.CharField(max_length=500)
    report_data = serializers.JSONField(default=dict)
    status = serializers.CharField(default='draft')
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)
    
    # For conflict detection
    version = serializers.IntegerField(required=False, help_text="Optimistic locking version")
    
    def create(self, validated_data):
        """Create report from mobile sync."""
        from apps.report_generation.models import ReportTemplate
        
        # Remove mobile-specific fields
        mobile_id = validated_data.pop('mobile_id')
        version = validated_data.pop('version', None)
        
        # Get template
        template = ReportTemplate.objects.get(id=validated_data.pop('template_id'))
        
        # Create report
        report = GeneratedReport.objects.create(
            template=template,
            author=self.context['user'],
            tenant=self.context['user'].tenant,
            **validated_data
        )
        
        logger.info(f"Created report {report.id} from mobile sync (mobile_id: {mobile_id})")
        
        return report
    
    def update(self, instance, validated_data):
        """Update report from mobile sync with conflict detection."""
        mobile_version = validated_data.pop('version', None)
        
        # Check for version conflict (optimistic locking)
        if mobile_version and hasattr(instance, 'version'):
            if instance.version != mobile_version:
                raise serializers.ValidationError({
                    'conflict': 'Version mismatch',
                    'mobile_version': mobile_version,
                    'server_version': instance.version,
                    'message': 'Report was modified on server. Please sync and resolve conflict.'
                })
        
        # Update fields
        validated_data.pop('mobile_id', None)
        validated_data.pop('template_id', None)  # Can't change template
        
        for key, value in validated_data.items():
            setattr(instance, key, value)
        
        instance.save()
        
        logger.info(f"Updated report {instance.id} from mobile sync")
        
        return instance


class AttachmentSyncSerializer(serializers.Serializer):
    """Serializer for attachment uploads from mobile."""
    
    mobile_id = serializers.CharField(required=True)
    report_mobile_id = serializers.CharField(required=False)
    report_server_id = serializers.IntegerField(required=False)
    
    filename = serializers.CharField(max_length=255)
    attachment_type = serializers.ChoiceField(choices=[
        ('photo', 'Photo'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document')
    ])
    evidence_category = serializers.ChoiceField(choices=[
        ('damage', 'Damage'),
        ('scene', 'Scene'),
        ('equipment', 'Equipment'),
        ('safety', 'Safety'),
        ('before_after', 'Before/After'),
        ('measurement', 'Measurement')
    ])
    
    # File data (one of these required)
    file_base64 = serializers.CharField(required=False, allow_blank=True)
    s3_url = serializers.URLField(required=False, allow_blank=True)
    
    file_size = serializers.IntegerField(required=False)
    mime_type = serializers.CharField(required=False)
    metadata = serializers.JSONField(default=dict)
    caption = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Ensure either file_base64 or s3_url provided."""
        if not attrs.get('file_base64') and not attrs.get('s3_url'):
            raise serializers.ValidationError("Either file_base64 or s3_url must be provided")
        
        if not attrs.get('report_mobile_id') and not attrs.get('report_server_id'):
            raise serializers.ValidationError("Either report_mobile_id or report_server_id required")
        
        return attrs
