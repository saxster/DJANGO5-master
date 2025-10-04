# Generated migration for mental health interventions

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import django.core.serializers.json
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('wellness', '0001_initial'),
        ('journal', '0003_refactor_journal_entry_models'),
        ('peoples', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MentalHealthIntervention',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('intervention_type', models.CharField(
                    choices=[
                        ('three_good_things', 'Three Good Things Exercise'),
                        ('gratitude_letter', 'Gratitude Letter Writing'),
                        ('gratitude_journal', 'Daily Gratitude Practice'),
                        ('strength_spotting', 'Character Strengths Identification'),
                        ('best_self', 'Best Possible Self Visualization'),
                        ('kindness', 'Random Acts of Kindness'),
                        ('behavioral_activation', 'Behavioral Activation Exercise'),
                        ('thought_record', 'CBT Thought Record'),
                        ('activity_scheduling', 'Pleasant Activity Scheduling'),
                        ('cognitive_reframing', 'Cognitive Reframing Exercise'),
                        ('progressive_relaxation', 'Progressive Muscle Relaxation'),
                        ('breathing_exercise', 'Guided Breathing Exercise'),
                        ('mindful_moment', 'Mindful Awareness Exercise'),
                        ('stress_reappraisal', 'Stress Reappraisal Technique'),
                        ('motivational_checkin', 'Motivational Check-in'),
                        ('values_clarification', 'Personal Values Reflection'),
                        ('change_readiness', 'Change Readiness Assessment'),
                        ('crisis_resource', 'Crisis Support Resource'),
                        ('safety_planning', 'Safety Planning Tool'),
                        ('professional_referral', 'Professional Help Information'),
                    ],
                    help_text='Specific intervention technique',
                    max_length=50
                )),
                ('evidence_base', models.CharField(
                    choices=[
                        ('seligman_validated', 'Seligman Positive Psychology Research'),
                        ('cbt_evidence', 'CBT Clinical Evidence Base'),
                        ('who_recommended', 'WHO Mental Health Guidelines'),
                        ('workplace_validated', 'Workplace Mental Health Research'),
                        ('meta_analysis', 'Meta-Analysis Evidence'),
                        ('rct_validated', 'Randomized Controlled Trial'),
                    ],
                    help_text='Research evidence supporting this intervention',
                    max_length=30
                )),
                ('expected_benefit_duration', models.CharField(
                    help_text="Research-backed duration of benefits (e.g., '6 months post-intervention')",
                    max_length=100
                )),
                ('effectiveness_percentage', models.IntegerField(
                    help_text='Research-reported effectiveness percentage',
                    validators=[django.core.validators.MinValueValidator(0),
                               django.core.validators.MaxValueValidator(100)]
                )),
                ('optimal_frequency', models.CharField(
                    choices=[
                        ('immediate', 'Immediate (Crisis Response)'),
                        ('within_hour', 'Within 1 Hour'),
                        ('same_day', 'Same Day'),
                        ('weekly', 'Weekly (Optimal for Gratitude)'),
                        ('bi_weekly', 'Bi-weekly'),
                        ('monthly', 'Monthly'),
                        ('pattern_triggered', 'Pattern-Triggered'),
                    ],
                    help_text='Research-optimal delivery frequency',
                    max_length=30
                )),
                ('intervention_duration_minutes', models.IntegerField(
                    help_text='Time required to complete intervention',
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(60)]
                )),
                ('mood_trigger_threshold', models.IntegerField(
                    blank=True,
                    help_text='Mood rating that triggers this intervention (≤ threshold)',
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(10)]
                )),
                ('stress_trigger_threshold', models.IntegerField(
                    blank=True,
                    help_text='Stress level that triggers this intervention (≥ threshold)',
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(5)]
                )),
                ('energy_trigger_threshold', models.IntegerField(
                    blank=True,
                    help_text='Energy level that triggers this intervention (≤ threshold)',
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(10)]
                )),
                ('crisis_escalation_level', models.IntegerField(
                    default=0,
                    help_text='Urgency level for crisis escalation (0=none, 10=immediate professional help)',
                    validators=[django.core.validators.MinValueValidator(0),
                               django.core.validators.MaxValueValidator(10)]
                )),
                ('workplace_context_tags', models.JSONField(
                    default=list,
                    help_text='Workplace contexts where this is most effective (equipment_failure, deadline_pressure, etc.)'
                )),
                ('guided_questions', models.JSONField(
                    default=list,
                    help_text='Step-by-step questions to guide user through intervention'
                )),
                ('template_structure', models.JSONField(
                    default=dict,
                    help_text='Template for structured interventions (thought records, gratitude formats, etc.)'
                )),
                ('follow_up_prompts', models.JSONField(
                    default=list,
                    help_text='Follow-up questions for next session'
                )),
                ('tenant', models.ForeignKey(
                    help_text='Organization/tenant that owns this data',
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('wellness_content', models.OneToOneField(
                    help_text='Links to base wellness content',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mental_health_intervention',
                    to='wellness.wellnesscontent'
                )),
            ],
            options={
                'verbose_name': 'Mental Health Intervention',
                'verbose_name_plural': 'Mental Health Interventions',
            },
        ),
        migrations.CreateModel(
            name='InterventionDeliveryLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('delivered_at', models.DateTimeField(auto_now_add=True)),
                ('delivery_trigger', models.CharField(
                    choices=[
                        ('daily_tip', 'Daily Wellness Tip'),
                        ('pattern_triggered', 'Pattern-Based Delivery'),
                        ('stress_response', 'High Stress Response'),
                        ('mood_support', 'Low Mood Support'),
                        ('energy_boost', 'Low Energy Response'),
                        ('shift_transition', 'Shift Start/End'),
                        ('streak_milestone', 'Milestone Reward'),
                        ('seasonal', 'Seasonal Health'),
                        ('workplace_specific', 'Workplace Guidance'),
                        ('gratitude_enhancement', 'Positive Psychology Reinforcement'),
                    ],
                    max_length=50
                )),
                ('user_mood_at_delivery', models.IntegerField(
                    blank=True,
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(10)]
                )),
                ('user_stress_at_delivery', models.IntegerField(
                    blank=True,
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(5)]
                )),
                ('user_energy_at_delivery', models.IntegerField(
                    blank=True,
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(10)]
                )),
                ('was_viewed', models.BooleanField(default=False)),
                ('was_completed', models.BooleanField(default=False)),
                ('completion_time_seconds', models.IntegerField(blank=True, null=True)),
                ('user_response', models.JSONField(
                    default=dict,
                    help_text="User's responses to guided questions"
                )),
                ('follow_up_mood_rating', models.IntegerField(
                    blank=True,
                    help_text="User's mood rating after intervention (if provided)",
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(10)]
                )),
                ('follow_up_stress_level', models.IntegerField(
                    blank=True,
                    help_text="User's stress level after intervention (if provided)",
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(5)]
                )),
                ('perceived_helpfulness', models.IntegerField(
                    blank=True,
                    help_text="User's rating of intervention helpfulness",
                    null=True,
                    validators=[django.core.validators.MinValueValidator(1),
                               django.core.validators.MaxValueValidator(5)]
                )),
                ('intervention', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deliveries',
                    to='wellness.mentalhealthintervention'
                )),
                ('triggering_journal_entry', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='triggered_interventions',
                    to='journal.journalentry'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='intervention_deliveries',
                    to='peoples.people'
                )),
            ],
            options={
                'verbose_name': 'Intervention Delivery Log',
                'verbose_name_plural': 'Intervention Delivery Logs',
                'ordering': ['-delivered_at'],
            },
        ),
        migrations.AddIndex(
            model_name='mentalhealthintervention',
            index=models.Index(fields=['intervention_type'], name='wellness_me_interve_b79e67_idx'),
        ),
        migrations.AddIndex(
            model_name='mentalhealthintervention',
            index=models.Index(fields=['evidence_base'], name='wellness_me_evidenc_9a4c82_idx'),
        ),
        migrations.AddIndex(
            model_name='mentalhealthintervention',
            index=models.Index(fields=['mood_trigger_threshold'], name='wellness_me_mood_tr_3f8e95_idx'),
        ),
        migrations.AddIndex(
            model_name='mentalhealthintervention',
            index=models.Index(fields=['stress_trigger_threshold'], name='wellness_me_stress__e4f2a1_idx'),
        ),
        migrations.AddIndex(
            model_name='mentalhealthintervention',
            index=models.Index(fields=['crisis_escalation_level'], name='wellness_me_crisis__7c9183_idx'),
        ),
        migrations.AddIndex(
            model_name='mentalhealthintervention',
            index=models.Index(fields=['optimal_frequency'], name='wellness_me_optimal_4a6e73_idx'),
        ),
        migrations.AddIndex(
            model_name='interventiondeliverylog',
            index=models.Index(fields=['user', 'delivered_at'], name='wellness_in_user_id_b8f4e2_idx'),
        ),
        migrations.AddIndex(
            model_name='interventiondeliverylog',
            index=models.Index(fields=['intervention', 'delivery_trigger'], name='wellness_in_interve_89c471_idx'),
        ),
        migrations.AddIndex(
            model_name='interventiondeliverylog',
            index=models.Index(fields=['was_completed'], name='wellness_in_was_com_d6f2a8_idx'),
        ),
    ]