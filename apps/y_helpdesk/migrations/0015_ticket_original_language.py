# Generated migration for Feature 4: Multilingual Ticket Translation
# Date: November 3, 2025

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('y_helpdesk', '0014_populate_tenant_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='original_language',
            field=models.CharField(
                choices=[
                    ('en', 'English'),
                    ('hi', 'Hindi'),
                    ('te', 'Telugu'),
                    ('es', 'Spanish'),
                ],
                default='en',
                help_text='Language in which the ticket was originally created',
                max_length=10,
                verbose_name='Original Language',
            ),
        ),
    ]
