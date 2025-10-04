"""
Configurable PII Redaction Policies

Per-tenant and per-organization configurable PII redaction policies.
Allows customization of what gets redacted and how, based on compliance requirements.

Features:
- Tenant-specific redaction policies
- Field-level granular control
- Compliance templates (GDPR, HIPAA, SOC2)
- Inheritance from organization defaults
- Policy versioning for audit trail

Author: Claude Code
Date: 2025-10-01
"""

import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField, JSONField
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant

User = get_user_model()


class RedactionPolicy(models.Model):
    """
    Configurable PII redaction policy for tenants.

    Defines what data gets redacted and how, based on compliance requirements.
    """

    REDACTION_LEVEL_CHOICES = [
        ('minimal', 'Minimal - Development/Testing'),
        ('standard', 'Standard - General Use'),
        ('strict', 'Strict - Production'),
        ('maximum', 'Maximum - High Security'),
    ]

    COMPLIANCE_TEMPLATE_CHOICES = [
        ('none', 'No Template'),
        ('gdpr', 'GDPR (EU General Data Protection Regulation)'),
        ('hipaa', 'HIPAA (US Health Insurance Portability)'),
        ('ccpa', 'CCPA (California Consumer Privacy Act)'),
        ('soc2', 'SOC 2 (Service Organization Control)'),
        ('custom', 'Custom Compliance Requirements'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Policy ownership
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='redaction_policies',
        help_text="Tenant this policy applies to"
    )
    name = models.CharField(
        max_length=200,
        help_text="Policy name"
    )
    description = models.TextField(
        blank=True,
        help_text="Policy description"
    )

    # Policy configuration
    redaction_level = models.CharField(
        max_length=20,
        choices=REDACTION_LEVEL_CHOICES,
        default='standard',
        help_text="Overall redaction strictness level"
    )
    compliance_template = models.CharField(
        max_length=20,
        choices=COMPLIANCE_TEMPLATE_CHOICES,
        default='none',
        help_text="Compliance template to base policy on"
    )

    # Field-level configuration
    always_redact_fields = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Fields to always redact for non-owners (e.g., 'content', 'gratitude_items')"
    )
    admin_visible_fields = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Fields admins can see with partial redaction (e.g., 'title', 'user_name')"
    )
    never_redact_fields = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Fields that are safe to always show (e.g., 'id', 'mood_rating')"
    )

    # Advanced configuration
    custom_patterns = JSONField(
        default=dict,
        blank=True,
        help_text="Custom PII patterns to detect (regex patterns with replacement)"
    )
    redaction_markers = JSONField(
        default=dict,
        blank=True,
        help_text="Custom redaction markers (e.g., {'email': '[EMAIL_REDACTED]'})"
    )

    # Behavior settings
    enable_audit_logging = models.BooleanField(
        default=True,
        help_text="Log all redaction events for compliance"
    )
    partial_name_redaction = models.BooleanField(
        default=True,
        help_text="Partially redact names for admins (e.g., 'J*** D**')"
    )
    redact_in_logs = models.BooleanField(
        default=True,
        help_text="Apply redaction to application logs"
    )
    redact_in_api = models.BooleanField(
        default=True,
        help_text="Apply redaction to API responses"
    )
    redact_in_errors = models.BooleanField(
        default=True,
        help_text="Apply redaction to error messages"
    )

    # Exceptions and overrides
    exempt_user_roles = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="User roles exempt from redaction (use with caution)"
    )
    exempt_ip_ranges = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="IP ranges exempt from redaction (e.g., internal network)"
    )

    # Policy management
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this policy is currently active"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default policy for the tenant"
    )
    version = models.IntegerField(
        default=1,
        help_text="Policy version for audit trail"
    )

    # Audit trail
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_redaction_policies',
        help_text="User who created this policy"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time policy was reviewed"
    )

    class Meta:
        verbose_name = "Redaction Policy"
        verbose_name_plural = "Redaction Policies"
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'is_default']),
            models.Index(fields=['compliance_template']),
        ]
        unique_together = [
            ['tenant', 'name']
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.tenantname})"

    @classmethod
    def get_policy_for_tenant(cls, tenant):
        """
        Get the active redaction policy for a tenant.

        Args:
            tenant: Tenant instance

        Returns:
            RedactionPolicy: Active policy, or default if none exists
        """
        # Try to get active default policy
        policy = cls.objects.filter(
            tenant=tenant,
            is_active=True,
            is_default=True
        ).first()

        if not policy:
            # Get any active policy
            policy = cls.objects.filter(
                tenant=tenant,
                is_active=True
            ).first()

        if not policy:
            # Create default policy
            policy = cls.create_default_policy(tenant)

        return policy

    @classmethod
    def create_default_policy(cls, tenant, compliance_template='none'):
        """
        Create a default redaction policy for a tenant.

        Args:
            tenant: Tenant instance
            compliance_template: Compliance template to use

        Returns:
            RedactionPolicy: Created policy
        """
        policy = cls.objects.create(
            tenant=tenant,
            name="Default Redaction Policy",
            description="Automatically created default policy",
            redaction_level='standard',
            compliance_template=compliance_template,
            is_default=True,
            always_redact_fields=[
                'content', 'gratitude_items', 'affirmations',
                'learnings', 'challenges', 'stress_triggers',
                'coping_strategies', 'daily_goals', 'achievements',
                'user_feedback', 'notes', 'comments'
            ],
            admin_visible_fields=[
                'title', 'subtitle', 'user_name'
            ],
            never_redact_fields=[
                'id', 'created_at', 'updated_at', 'mood_rating',
                'stress_level', 'energy_level', 'entry_type',
                'privacy_scope', 'is_bookmarked', 'is_draft'
            ]
        )

        # Apply compliance template
        if compliance_template != 'none':
            policy.apply_compliance_template(compliance_template)

        return policy

    def apply_compliance_template(self, template_name):
        """
        Apply a compliance template to this policy.

        Args:
            template_name: Name of template (gdpr, hipaa, ccpa, soc2)
        """
        templates = {
            'gdpr': self._apply_gdpr_template,
            'hipaa': self._apply_hipaa_template,
            'ccpa': self._apply_ccpa_template,
            'soc2': self._apply_soc2_template,
        }

        if template_name in templates:
            templates[template_name]()
            self.compliance_template = template_name
            self.save()

    def _apply_gdpr_template(self):
        """Apply GDPR compliance template"""
        self.redaction_level = 'strict'
        self.enable_audit_logging = True
        self.partial_name_redaction = True
        self.redact_in_logs = True
        self.redact_in_api = True
        self.redact_in_errors = True

        # GDPR requires strict PII protection
        self.always_redact_fields.extend([
            'email', 'phone', 'address', 'ip_address'
        ])

    def _apply_hipaa_template(self):
        """Apply HIPAA compliance template"""
        self.redaction_level = 'maximum'
        self.enable_audit_logging = True
        self.partial_name_redaction = True
        self.redact_in_logs = True
        self.redact_in_api = True
        self.redact_in_errors = True

        # HIPAA requires maximum protection for health data
        self.always_redact_fields.extend([
            'diagnosis', 'medication', 'treatment', 'health_notes',
            'medical_history', 'symptoms'
        ])

    def _apply_ccpa_template(self):
        """Apply CCPA compliance template"""
        self.redaction_level = 'strict'
        self.enable_audit_logging = True
        self.partial_name_redaction = True

    def _apply_soc2_template(self):
        """Apply SOC 2 compliance template"""
        self.redaction_level = 'strict'
        self.enable_audit_logging = True
        self.partial_name_redaction = True
        self.redact_in_logs = True

    def should_redact_field(self, field_name, user_role):
        """
        Determine if a field should be redacted for a given user role.

        Args:
            field_name: Field name to check
            user_role: User role ('owner', 'admin', 'user', 'anonymous')

        Returns:
            tuple: (should_redact: bool, redaction_type: str)
        """
        # Owner never sees redaction (their own data)
        if user_role == 'owner':
            return (False, None)

        # Check never redact list
        if field_name in self.never_redact_fields:
            return (False, None)

        # Check always redact list
        if field_name in self.always_redact_fields:
            return (True, 'full')

        # Check admin visible list
        if field_name in self.admin_visible_fields:
            if user_role == 'admin':
                return (True, 'partial')
            else:
                return (True, 'full')

        # Default based on redaction level
        if self.redaction_level in ['strict', 'maximum']:
            return (True, 'full')

        return (False, None)

    def get_redaction_marker(self, field_type):
        """
        Get the redaction marker for a field type.

        Args:
            field_type: Field type (email, phone, content, etc.)

        Returns:
            str: Redaction marker
        """
        # Check custom markers
        if field_type in self.redaction_markers:
            return self.redaction_markers[field_type]

        # Default markers
        defaults = {
            'email': '[EMAIL]',
            'phone': '[PHONE]',
            'ssn': '[SSN]',
            'content': '[REDACTED]',
            'title': '[TITLE]',
            'name': '[NAME]',
        }

        return defaults.get(field_type, '[REDACTED]')

    def increment_version(self):
        """Increment policy version for audit trail"""
        self.version += 1
        self.save(update_fields=['version', 'updated_at'])

    def clone_as_new_version(self):
        """
        Create a new version of this policy.

        Returns:
            RedactionPolicy: New policy version
        """
        new_policy = RedactionPolicy.objects.create(
            tenant=self.tenant,
            name=f"{self.name} v{self.version + 1}",
            description=self.description,
            redaction_level=self.redaction_level,
            compliance_template=self.compliance_template,
            always_redact_fields=self.always_redact_fields.copy(),
            admin_visible_fields=self.admin_visible_fields.copy(),
            never_redact_fields=self.never_redact_fields.copy(),
            custom_patterns=self.custom_patterns.copy(),
            redaction_markers=self.redaction_markers.copy(),
            enable_audit_logging=self.enable_audit_logging,
            partial_name_redaction=self.partial_name_redaction,
            redact_in_logs=self.redact_in_logs,
            redact_in_api=self.redact_in_api,
            redact_in_errors=self.redact_in_errors,
            version=self.version + 1,
            created_by=self.created_by
        )

        # Deactivate old policy
        self.is_active = False
        self.is_default = False
        self.save()

        return new_policy


class RedactionPolicyLog(models.Model):
    """
    Audit log for redaction policy changes.

    Tracks all changes to redaction policies for compliance.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    policy = models.ForeignKey(
        RedactionPolicy,
        on_delete=models.CASCADE,
        related_name='change_logs',
        help_text="Policy that was changed"
    )

    action = models.CharField(
        max_length=50,
        help_text="Action performed (created, updated, activated, deactivated)"
    )
    changes = JSONField(
        default=dict,
        help_text="Details of what changed"
    )

    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text="User who made the change"
    )
    performed_at = models.DateTimeField(auto_now_add=True)

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of user making change"
    )

    class Meta:
        verbose_name = "Redaction Policy Log"
        verbose_name_plural = "Redaction Policy Logs"
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['policy', 'performed_at']),
            models.Index(fields=['performed_by', 'performed_at']),
        ]

    def __str__(self):
        return f"{self.action} on {self.policy.name} at {self.performed_at}"
