from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from apps.core.models import BaseModel
from apps.peoples.models import People
from apps.tenants.models import Tenant


class ReportTemplate(BaseModel):
    """
    Defines structure and AI guidance for different report types.
    Supports both system-provided and custom templates.
    """
    
    CATEGORY_CHOICES = [
        ('incident', 'Incident Report'),
        ('rca', 'Root Cause Analysis'),
        ('capa', 'Corrective/Preventive Action'),
        ('near_miss', 'Near-Miss Report'),
        ('shift_handover', 'Shift Handover'),
        ('safety', 'Safety Report'),
        ('quality', 'Quality Report'),
        ('environmental', 'Environmental Report'),
        ('custom', 'Custom Report'),
    ]
    
    MENTOR_DOMAIN_CHOICES = [
        ('security', 'Security Mentor (7 Pillars)'),
        ('facility', 'Facility Mentor (Asset Lifecycle)'),
        ('hybrid', 'Hybrid (Both Mentors)'),
        ('auto', 'Auto-Detect Domain'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    
    # Mentor domain configuration
    mentor_domain = models.CharField(
        max_length=20,
        choices=MENTOR_DOMAIN_CHOICES,
        default='auto',
        help_text="Which AI mentor should handle this report type"
    )
    domain_specific_config = models.JSONField(
        default=dict,
        help_text="Domain-specific frameworks: 7_pillars for security, asset_lifecycle for facility"
    )
    
    # Evidence requirements
    evidence_requirements = models.JSONField(
        default=list,
        help_text="Required photo/video types: damage, scene, before_after, equipment"
    )
    critical_unknowns_list = models.JSONField(
        default=list,
        help_text="Domain-specific critical fields that cannot be unknown"
    )
    
    # JSON schema defining fields, types, validation
    schema = models.JSONField(
        default=dict,
        help_text="Field definitions: name, type, required, validation rules, conditional logic"
    )
    
    # AI questioning strategy for this template
    questioning_strategy = models.JSONField(
        default=dict,
        help_text="AI frameworks to use: 5_whys, sbar, 5w1h, ishikawa, star"
    )
    
    # Quality gate configuration
    quality_gates = models.JSONField(
        default=dict,
        help_text="Validation rules: minimum scores, required fields, clarity thresholds"
    )
    
    # Template management
    is_system_template = models.BooleanField(
        default=False,
        help_text="System templates cannot be deleted, only customized"
    )
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    
    # Ownership and approval
    created_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates'
    )
    approved_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_templates'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='report_templates'
    )
    
    class Meta:
        db_table = 'report_templates'
        verbose_name = 'Report Template'
        verbose_name_plural = 'Report Templates'
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_category_display()} - {self.name}"


class GeneratedReport(BaseModel):
    """
    Individual report instance created from a template.
    Stores all report data, AI interactions, and quality metrics.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    ]
    
    # Template and data
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.PROTECT,
        related_name='generated_reports'
    )
    report_data = models.JSONField(
        default=dict,
        help_text="All field values filled by user and auto-populated"
    )
    
    # Report metadata
    title = models.CharField(max_length=500)
    author = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='authored_reports'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Polymorphic relation to related entity (work order, incident, asset, etc.)
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_to = GenericForeignKey('related_content_type', 'related_object_id')
    
    # AI interaction history
    ai_interactions = models.JSONField(
        default=list,
        help_text="Q&A history with AI mentor"
    )
    
    # Quality metrics
    quality_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall quality score (0-100)"
    )
    completeness_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    clarity_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Review and approval
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    supervisor_feedback = models.TextField(blank=True)
    
    # Learning system
    is_exemplar = models.BooleanField(
        default=False,
        help_text="High-quality report used for AI learning"
    )
    exemplar_category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Category for exemplar classification"
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='generated_reports'
    )
    
    class Meta:
        db_table = 'generated_reports'
        verbose_name = 'Generated Report'
        verbose_name_plural = 'Generated Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'author']),
            models.Index(fields=['tenant', 'is_exemplar']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['related_content_type', 'related_object_id']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def can_submit(self) -> tuple[bool, list[str]]:
        """Check if report meets quality gates for submission."""
        from apps.report_generation.services.quality_gate_service import QualityGateService
        return QualityGateService.can_submit(self)


class ReportAIInteraction(BaseModel):
    """
    Tracks individual AI question/answer exchanges during report creation.
    Used for learning and improving AI questioning strategies.
    """
    
    QUESTION_TYPE_CHOICES = [
        ('5_whys', '5 Whys'),
        ('sbar', 'SBAR Framework'),
        ('5w1h', '5W1H Analysis'),
        ('ishikawa', 'Ishikawa/Fishbone'),
        ('star', 'STAR Method'),
        ('clarification', 'Clarification'),
        ('validation', 'Validation'),
    ]
    
    report = models.ForeignKey(
        GeneratedReport,
        on_delete=models.CASCADE,
        related_name='ai_interactions_detailed'
    )
    
    question = models.TextField()
    answer = models.TextField(blank=True)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    
    # Question flow tracking
    iteration = models.IntegerField(
        default=1,
        help_text="Question number in sequence"
    )
    depth = models.IntegerField(
        default=0,
        help_text="Depth level for frameworks like 5 Whys"
    )
    parent_interaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='follow_ups'
    )
    
    # Quality improvement tracking
    improved_clarity = models.BooleanField(
        default=False,
        help_text="Did this Q&A improve report clarity?"
    )
    quality_feedback = models.TextField(
        blank=True,
        help_text="What specific improvement resulted"
    )
    
    class Meta:
        db_table = 'report_ai_interactions'
        verbose_name = 'Report AI Interaction'
        verbose_name_plural = 'Report AI Interactions'
        ordering = ['report', 'iteration']
        indexes = [
            models.Index(fields=['report', 'iteration']),
            models.Index(fields=['question_type']),
        ]
    
    def __str__(self):
        return f"Q{self.iteration}: {self.question_type} - {self.report.title}"


class ReportQualityMetrics(BaseModel):
    """
    Detailed quality analysis of a report.
    Generated by AI quality gate service.
    """
    
    report = models.OneToOneField(
        GeneratedReport,
        on_delete=models.CASCADE,
        related_name='detailed_quality_metrics'
    )
    
    # Completeness metrics
    completeness_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    required_fields_filled = models.IntegerField()
    total_required_fields = models.IntegerField()
    narrative_word_count = models.IntegerField(default=0)
    minimum_narrative_length = models.IntegerField(default=100)
    
    # Clarity metrics
    clarity_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    readability_score = models.FloatField(
        help_text="Flesch-Kincaid readability (0-100, higher is easier)"
    )
    jargon_density = models.FloatField(
        help_text="Percentage of jargon/vague words"
    )
    assumption_count = models.IntegerField(default=0)
    
    # Logical structure
    causal_chain_strength = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quality of cause-effect reasoning"
    )
    
    # Actionability
    actionability_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    smart_criteria_met = models.IntegerField(
        default=0,
        help_text="How many SMART criteria met (0-5)"
    )
    
    # Detailed feedback
    improvement_suggestions = models.JSONField(
        default=list,
        help_text="Specific suggestions for improvement"
    )
    jargon_examples = models.JSONField(
        default=list,
        help_text="Examples of jargon/vague language found"
    )
    missing_details = models.JSONField(
        default=list,
        help_text="Required details not provided"
    )
    
    class Meta:
        db_table = 'report_quality_metrics'
        verbose_name = 'Report Quality Metrics'
        verbose_name_plural = 'Report Quality Metrics'
    
    def __str__(self):
        return f"Quality Metrics for {self.report.title}"


class ReportExemplar(BaseModel):
    """
    High-quality reports marked for AI learning and user reference.
    Supervisor-approved models of excellent reporting.
    """
    
    report = models.OneToOneField(
        GeneratedReport,
        on_delete=models.CASCADE,
        related_name='exemplar_details'
    )
    
    exemplar_category = models.CharField(
        max_length=100,
        help_text="Incident type, industry, severity, etc."
    )
    
    why_exemplar = models.TextField(
        help_text="What makes this report exemplary?"
    )
    
    learning_points = models.JSONField(
        default=list,
        help_text="Key lessons to extract from this report"
    )
    
    # Key characteristics
    demonstrates_frameworks = models.JSONField(
        default=list,
        help_text="Which frameworks are well-executed (5 Whys, SBAR, etc.)"
    )
    narrative_quality = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Narrative quality rating (1-5)"
    )
    root_cause_depth = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Depth of root cause analysis (1-5)"
    )
    
    # Approval
    approved_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_exemplars'
    )
    approval_date = models.DateTimeField(auto_now_add=True)
    
    # Usage tracking
    times_referenced = models.IntegerField(
        default=0,
        help_text="How often shown as example to users"
    )
    
    class Meta:
        db_table = 'report_exemplars'
        verbose_name = 'Report Exemplar'
        verbose_name_plural = 'Report Exemplars'
        ordering = ['-approval_date']
        indexes = [
            models.Index(fields=['exemplar_category']),
        ]
    
    def __str__(self):
        return f"Exemplar: {self.report.title}"


class ReportIncidentTrend(BaseModel):
    """
    Aggregated incident patterns identified by AI learning system.
    Enables predictive insights and preventive actions.
    """
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='incident_trends'
    )
    
    # Pattern identification
    trend_type = models.CharField(
        max_length=100,
        help_text="Type of pattern (recurring_cause, location_risk, temporal, etc.)"
    )
    pattern_description = models.TextField()
    
    # Associated reports
    related_reports = models.ManyToManyField(
        GeneratedReport,
        related_name='incident_trends',
        blank=True
    )
    occurrence_count = models.IntegerField(default=1)
    
    # Risk assessment
    severity_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    predicted_recurrence_probability = models.FloatField(
        help_text="Likelihood of recurrence (0-1)"
    )
    
    # Recommendations
    recommended_actions = models.JSONField(
        default=list,
        help_text="Preventive actions suggested by AI"
    )
    
    # Temporal data
    first_occurrence = models.DateTimeField()
    last_occurrence = models.DateTimeField()
    
    # Tracking
    is_active = models.BooleanField(default=True)
    is_addressed = models.BooleanField(default=False)
    addressed_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='addressed_trends'
    )
    addressed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'report_incident_trends'
        verbose_name = 'Incident Trend'
        verbose_name_plural = 'Incident Trends'
        ordering = ['-last_occurrence']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'severity_level']),
        ]
    
    def __str__(self):
        return f"{self.trend_type}: {self.pattern_description[:50]}"
