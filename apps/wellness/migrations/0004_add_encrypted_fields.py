"""
Migration to add encrypted fields for sensitive wellness intervention data.

Security Compliance:
- GDPR Article 32 (Security of Processing)
- HIPAA Security Rule 45 CFR § 164.312(a)(2)(iv)
- Encrypts mental health PII/PHI at rest

Fields being encrypted:
- InterventionDeliveryLog.user_response (user's responses to mental health questions)
"""

from django.db import migrations, models
from apps.core.fields.encrypted_fields import EncryptedJSONField


class Migration(migrations.Migration):

    dependencies = [
        ('wellness', '0003_add_wisdom_conversations'),  # Update with actual previous migration
    ]

    operations = [
        # Add encrypted user_response field
        migrations.AddField(
            model_name='interventiondeliverylog',
            name='user_response_encrypted',
            field=EncryptedJSONField(
                default=dict,
                null=True,
                help_text="Encrypted user responses to guided mental health questions"
            ),
        ),

        # Add encryption flag
        migrations.AddField(
            model_name='interventiondeliverylog',
            name='is_encrypted',
            field=models.BooleanField(
                default=False,
                help_text="Flag indicating if this entry has been migrated to encrypted fields"
            ),
        ),
    ]
