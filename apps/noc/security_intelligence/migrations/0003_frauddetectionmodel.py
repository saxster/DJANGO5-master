"""
Migration for FraudDetectionModel.

Adds model registry for XGBoost fraud detection models.
Tracks model versioning, performance metrics, and activation status.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('security_intelligence', '0002_add_intelligence_fields'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FraudDetectionModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, help_text='Creation timestamp')),
                ('mdtz', models.DateTimeField(auto_now=True, help_text='Last modification timestamp')),
                ('model_version', models.CharField(db_index=True, help_text="Model version identifier (e.g., 'v1_20251102_143000')", max_length=50)),
                ('model_path', models.CharField(help_text='Path to saved model file (.joblib)', max_length=500)),
                ('pr_auc', models.FloatField(help_text='Precision-Recall AUC (target: >0.70)')),
                ('precision_at_80_recall', models.FloatField(help_text='Precision at 80% recall (target: >0.50)')),
                ('optimal_threshold', models.FloatField(default=0.5, help_text='Optimal decision threshold for classification')),
                ('train_samples', models.IntegerField(help_text='Number of training samples')),
                ('fraud_samples', models.IntegerField(default=0, help_text='Number of fraud samples in training set')),
                ('normal_samples', models.IntegerField(default=0, help_text='Number of normal samples in training set')),
                ('class_imbalance_ratio', models.FloatField(default=0.0, help_text='Fraud samples / Total samples (e.g., 0.01 = 1% fraud)')),
                ('is_active', models.BooleanField(db_index=True, default=False, help_text='Whether this model is active for predictions')),
                ('activated_at', models.DateTimeField(blank=True, help_text='When model was activated', null=True)),
                ('deactivated_at', models.DateTimeField(blank=True, help_text='When model was deactivated', null=True)),
                ('metadata', models.JSONField(default=dict, help_text='Additional model metadata (feature importance, hyperparameters, etc.)')),
                ('training_duration_seconds', models.IntegerField(blank=True, help_text='Training duration in seconds', null=True)),
                ('xgboost_params', models.JSONField(default=dict, help_text='XGBoost hyperparameters used')),
                ('feature_importance', models.JSONField(default=dict, help_text='Feature importance scores')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fraud_detection_models', to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Fraud Detection Model',
                'verbose_name_plural': 'Fraud Detection Models',
                'db_table': 'noc_fraud_detection_model',
                'ordering': ['-cdtz'],
                'indexes': [
                    models.Index(fields=['tenant', 'is_active'], name='noc_fraud_d_tenant__idx'),
                    models.Index(fields=['model_version'], name='noc_fraud_d_model_v_idx'),
                    models.Index(fields=['pr_auc'], name='noc_fraud_d_pr_auc_idx'),
                ],
                'unique_together': {('tenant', 'model_version')},
            },
        ),
    ]
