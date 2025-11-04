# Generated manually for Feature 2: Sentiment Analysis on Tickets
# NL/AI Platform Quick Win Bundle

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('y_helpdesk', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='sentiment_score',
            field=models.FloatField(blank=True, help_text='Sentiment score: 0=Very Negative, 5=Neutral, 10=Very Positive', null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='sentiment_label',
            field=models.CharField(
                blank=True,
                choices=[
                    ('very_negative', 'Very Negative'),
                    ('negative', 'Negative'),
                    ('neutral', 'Neutral'),
                    ('positive', 'Positive'),
                    ('very_positive', 'Very Positive')
                ],
                help_text='Human-readable sentiment classification',
                max_length=20,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='ticket',
            name='emotion_detected',
            field=models.JSONField(blank=True, default=dict, help_text='Detected emotions with scores: {anger: 0.8, frustration: 0.6, ...}'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='sentiment_analyzed_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp of last sentiment analysis', null=True),
        ),
        # Add index for sentiment-based queries
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['sentiment_score'], name='ticket_sentiment_score_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['sentiment_label'], name='ticket_sentiment_label_idx'),
        ),
    ]
