"""
Migration: Add Intelligence System Fields.

Adds to existing models:
- BaselineProfile: false_positive_rate, dynamic_threshold, last_threshold_update
- AuditFinding: escalated_to_ticket, escalation_ticket_id, escalated_at, evidence_summary
"""

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('noc_security_intelligence', '0001_initial'),
    ]

    operations = [
        # ========== BaselineProfile Fields (Gap #6) ==========
        migrations.AddField(
            model_name='baselineprofile',
            name='false_positive_rate',
            field=models.FloatField(
                default=0.0,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0)
                ],
                help_text="Rolling 30-day false positive rate (0.0-1.0)"
            ),
        ),
        migrations.AddField(
            model_name='baselineprofile',
            name='dynamic_threshold',
            field=models.FloatField(
                default=3.0,
                validators=[
                    django.core.validators.MinValueValidator(1.5),
                    django.core.validators.MaxValueValidator(5.0)
                ],
                help_text="Dynamically adjusted z-score threshold based on FP rate"
            ),
        ),
        migrations.AddField(
            model_name='baselineprofile',
            name='last_threshold_update',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="When threshold was last updated"
            ),
        ),

        # ========== AuditFinding Fields (Gap #5) ==========
        migrations.AddField(
            model_name='auditfinding',
            name='escalated_to_ticket',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Whether finding was escalated to a ticket"
            ),
        ),
        migrations.AddField(
            model_name='auditfinding',
            name='escalation_ticket_id',
            field=models.IntegerField(
                null=True,
                blank=True,
                db_index=True,
                help_text="ID of ticket created from escalation"
            ),
        ),
        migrations.AddField(
            model_name='auditfinding',
            name='escalated_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="When finding was escalated to ticket"
            ),
        ),
        migrations.AddField(
            model_name='auditfinding',
            name='evidence_summary',
            field=models.TextField(
                blank=True,
                help_text="Summarized evidence for dashboard display"
            ),
        ),
    ]
