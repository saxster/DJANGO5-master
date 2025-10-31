"""
Migration to add encrypted fields for sensitive journal data.

Security Compliance:
- GDPR Article 32 (Security of Processing)
- HIPAA Security Rule 45 CFR § 164.312(a)(2)(iv)
- Encrypts PII/PHI at rest

Strategy:
1. Add new encrypted fields alongside existing fields
2. Data migration will copy data to encrypted fields (separate migration)
3. Final migration will remove old unencrypted fields (after validation)

Fields being encrypted:
- content (main journal content)
- mood_description (mood descriptions)
- stress_triggers (JSON - stress triggers)
- coping_strategies (JSON - coping strategies)
- gratitude_items (JSON - gratitude lists)
- affirmations (JSON - personal affirmations)
- challenges (JSON - challenges faced)
"""

from django.db import migrations, models
from apps.core.fields.encrypted_fields import EncryptedTextField, EncryptedJSONField


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0003_refactor_journal_entry_models'),
    ]

    operations = [
        # Add encrypted text fields
        migrations.AddField(
            model_name='journalentry',
            name='content_encrypted',
            field=EncryptedTextField(
                blank=True,
                null=True,
                help_text="Encrypted main entry content (replaces content field)"
            ),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='mood_description_encrypted',
            field=EncryptedTextField(
                blank=True,
                null=True,
                max_length=500,  # Encrypted fields need more space
                help_text="Encrypted mood description"
            ),
        ),

        # Add encrypted JSON fields
        migrations.AddField(
            model_name='journalentry',
            name='stress_triggers_encrypted',
            field=EncryptedJSONField(
                default=list,
                null=True,
                help_text="Encrypted list of stress triggers"
            ),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='coping_strategies_encrypted',
            field=EncryptedJSONField(
                default=list,
                null=True,
                help_text="Encrypted list of coping strategies"
            ),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='gratitude_items_encrypted',
            field=EncryptedJSONField(
                default=list,
                null=True,
                help_text="Encrypted list of gratitude items"
            ),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='affirmations_encrypted',
            field=EncryptedJSONField(
                default=list,
                null=True,
                help_text="Encrypted list of affirmations"
            ),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='challenges_encrypted',
            field=EncryptedJSONField(
                default=list,
                null=True,
                help_text="Encrypted list of challenges"
            ),
        ),

        # Add flag to track encryption migration status
        migrations.AddField(
            model_name='journalentry',
            name='is_encrypted',
            field=models.BooleanField(
                default=False,
                help_text="Flag indicating if this entry has been migrated to encrypted fields"
            ),
        ),
    ]
